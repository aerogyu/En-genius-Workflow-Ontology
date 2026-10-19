"""스키마 생성물 만들기·점검 — python -m engenius_wf schema [--check].

LinkML 스키마(schema/wfo.yaml)가 마스터다. **linkml 은 이 모듈에서만 import 한다** — 빌드 런타임은 생성물만 읽는다
(linkml→curies→pystow 가 홈 폴더에 쓰는 부작용 회피). 만드는 것 (schema/generated/):
  terms.json            클래스·슬롯 → RDF IRI·범위 (빌드가 술어 IRI 와 형 변환에 씀)
  wfo_file.schema.json  YAML 파일 모양 검사용 (gen-json-schema --closed)
  wfo.shacl.ttl         RDF 모양 검사용 (gen-shacl + 정리: @ko 라벨 = rdf:langString, YAML 용기 클래스 제외)
  wfo.owl.ttl           Protégé·Graph Studio 보기용 (gen-owl + 정리 + alignment.ttl)
  lint.txt              linkml lint 결과
--check: 다시 만들어 보고 지금 파일과 다르면 rc 1 (드리프트 감시).

LinkML 생성기 함정 정리: gen-owl 이 남의 어휘(외부 이름공간 주어)에 트리플을 써서 라벨을 덮어쓰거나 역방향 subClassOf 를
만든다 → 외부 주어 트리플 제거 + 정렬은 alignment.ttl 한 방향 공리로만. 이름 속성은 OWL 2 주석 속성 → 클래스 제약에서 뺀다.
선택지 = 이름 있는 데이터타입. xsd:pattern 앵커 제거. 열린 루트(WorkflowFile — YAML 용기)는 OWL·SHACL 에서 뺀다.
gen-owl·gen-shacl 은 실행마다 Turtle 줄 순서가 바뀌므로 빈 노드를 정규화(to_canonical_graph)해 직렬화한다.
"""

from __future__ import annotations

import json
import re
import sys
import warnings

import yaml
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.compare import to_canonical_graph
from rdflib.namespace import OWL, RDF, RDFS, SKOS, XSD, Namespace

from engenius_wf.config import ALIGN_FILE, GEN_DIR, SCHEMA_FILE

SCHEMA = SCHEMA_FILE
ALIGN = ALIGN_FILE
GEN = GEN_DIR
SH = Namespace("http://www.w3.org/ns/shacl#")
WFNS = "http://en-genius.local/onto/wf/"
BANNER = "# 자동 생성 — 직접 고치지 말 것. 원본: schema/wfo.yaml (+ alignment.ttl), 명령: python -m engenius_wf schema\n"
LABEL_PROPS = (RDFS.label,)
FILES = ("lint.txt", "wfo_file.schema.json", "wfo.shacl.ttl", "wfo.owl.ttl", "terms.json")


def canon_ttl(g: Graph) -> str:
    c = Graph()
    for p, ns in g.namespaces():
        c.bind(p, ns, override=True)
    for t in to_canonical_graph(g):
        c.add(t)
    return BANNER + c.serialize(format="turtle")


def lint() -> list[str]:
    from linkml.linter.linter import Linter
    cfg = {"extends": "recommended",
           "rules": {"standard_naming": {"exclude_type": ["permissible_value"]},
                     "canonical_prefixes": {"level": "disabled"},
                     "recommended": {"exclude_type": ["permissible_value"]}}}
    return [f"{p.level}: {p.message} ({p.rule_name})" for p in Linter(cfg).lint(str(SCHEMA))]


def build_json_schema() -> str:
    from linkml.generators.jsonschemagen import JsonSchemaGenerator
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return JsonSchemaGenerator(str(SCHEMA), not_closed=False, top_class="WorkflowFile").serialize()


def build_shacl() -> str:
    from linkml.generators.shaclgen import ShaclGenerator
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        g = Graph().parse(data=ShaclGenerator(str(SCHEMA)).serialize(), format="turtle")
    # 정리 1: 이름 속성은 @ko → rdf:langString + languageIn (형제 저장소 _shacl_tidy 와 같은 처리)
    for p in LABEL_PROPS:
        for ps in list(g.subjects(SH.path, p)):
            if (ps, SH.datatype, XSD.string) in g:
                g.remove((ps, SH.datatype, XSD.string))
                g.add((ps, SH.datatype, RDF.langString))
                langs = BNode()
                Collection(g, langs, [Literal("ko")])
                g.add((ps, SH.languageIn, langs))
    # 정리 2: WorkflowFile 은 YAML 용기 — RDF 에 없으므로 모양을 뺀다
    for shp in list(g.subjects(SH.targetClass, URIRef(WFNS + "WorkflowFile"))):
        _drop_node(g, shp)
    return canon_ttl(g)


def _drop_node(g, n):
    for _, p, o in list(g.triples((n, None, None))):
        g.remove((n, p, o))
        if isinstance(o, BNode):
            _drop_node(g, o)


def build_owl() -> tuple[str, int]:
    from linkml.generators.owlgen import OwlSchemaGenerator
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ttl = OwlSchemaGenerator(str(SCHEMA), type_objects=False, metaclasses=False, use_native_uris=False,
                                 default_permissible_value_type="http://www.w3.org/2000/01/rdf-schema#Literal",
                                 skip_vacuous_min_zero_cardinality_axioms=True, skip_vacuous_local_range_axioms=True,
                                 consolidate_cardinality_axioms=True).serialize()
    g = Graph().parse(data=ttl, format="turtle")
    # 정리 1: 남의 어휘(외부 이름공간 주어)에 붙은 트리플 제거 — 라벨 덮어쓰기·역방향 subClassOf 방지 (standards 실측)
    removed = 0
    for s, p, o in list(g):
        if isinstance(s, URIRef) and not str(s).startswith(WFNS) and not (p == RDF.type and o == OWL.Ontology):
            g.remove((s, p, o))
            removed += 1
    # 정리 2: 이름 속성은 OWL 2 주석 속성 — 클래스 제약에서 뺀다 (형제 저장소 _owl_dl_tidy 1번)
    for p in LABEL_PROPS + (SKOS.notation, SKOS.note, SKOS.definition, SKOS.broader):
        for r in list(g.subjects(OWL.onProperty, p)):
            for s2, p2 in list(g.subject_predicates(r)):
                g.remove((s2, p2, r))
            _drop_node(g, r)
    # 정리 3: 선택지 = 이름 있는 데이터타입 (형제 저장소 _owl_dl_tidy 2번)
    enums = {e for e in g.subjects(RDF.type, RDFS.Datatype) if (e, OWL.oneOf, None) in g}
    for e in enums:
        vals = g.value(e, OWL.oneOf)
        g.remove((e, OWL.oneOf, vals))
        g.remove((e, RDF.type, OWL.Class))
        dt = BNode()
        g.add((dt, RDF.type, RDFS.Datatype))
        g.add((dt, OWL.oneOf, vals))
        g.add((e, OWL.equivalentClass, dt))
    for p in {g.value(r, OWL.onProperty) for r in g.subjects(OWL.onProperty, None)
              if {g.value(r, OWL.allValuesFrom), g.value(r, OWL.someValuesFrom)} & enums} | \
             {p for p, e in g.subject_objects(RDFS.range) if e in enums}:
        g.remove((p, RDF.type, OWL.ObjectProperty))
        g.add((p, RDF.type, OWL.DatatypeProperty))
    # 정리 4: xsd:pattern 앵커 제거 (XSD 정규식은 전체 일치가 암묵)
    for s, p, o in list(g.triples((None, XSD.pattern, None))):
        g.remove((s, p, o))
        g.add((s, p, Literal(re.sub(r"^\^|\$$", "", str(o)))))
    # 정리 5: YAML 용기 클래스 제거
    _drop_node(g, URIRef(WFNS + "WorkflowFile"))
    for s in list(g.subjects(None, URIRef(WFNS + "WorkflowFile"))):
        _drop_node(g, s)
    # 고아 빈 노드
    while True:
        ref = {o for o in g.objects() if isinstance(o, BNode)}
        orphan = {s for s in g.subjects() if isinstance(s, BNode) and s not in ref}
        if not orphan:
            break
        for s in orphan:
            g.remove((s, None, None))
    g.parse(ALIGN, format="turtle")
    ver = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))["version"]
    for ont in g.subjects(RDF.type, OWL.Ontology):
        g.add((ont, OWL.versionInfo, Literal(str(ver))))
    return canon_ttl(g), removed


def build_terms() -> str:
    from linkml_runtime.utils.schemaview import SchemaView
    sv = SchemaView(str(SCHEMA))
    out = {"classes": {}, "enums": {}}
    for e in sv.all_enums():
        out["enums"][e] = list(sv.get_enum(e).permissible_values)
    for c in sv.all_classes():
        slots = {}
        for sn in sv.class_slots(c):
            s = sv.induced_slot(sn, c)
            rng = s.range
            if not rng and s.any_of:
                rng = "|".join(x.range for x in s.any_of)
            slots[sn] = {"uri": sv.expand_curie(s.slot_uri) if s.slot_uri else WFNS + sn,
                         "range": rng, "multivalued": bool(s.multivalued), "required": bool(s.required),
                         "built": (s.description or "").startswith("(빌드)")}
        out["classes"][c] = {"uri": sv.get_uri(c, expand=True), "slots": slots}
    return json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def generate() -> tuple[dict[str, str], int, list[str]]:
    """(생성물 이름 → 내용, OWL 정리에서 지운 외부 주어 트리플 수, lint 문제 목록) — 파일은 쓰지 않는다."""
    probs = lint()
    owl, removed = build_owl()
    files = {"lint.txt": "\n".join(probs) + "\n", "wfo_file.schema.json": build_json_schema(),
             "wfo.shacl.ttl": build_shacl(), "wfo.owl.ttl": owl, "terms.json": build_terms()}
    return files, removed, probs


def drift(files: dict[str, str]) -> list[str]:
    """커밋된 생성물과 다른 파일 이름 (없거나 내용이 다르면)."""
    out = []
    for name, text in files.items():
        p = GEN / name
        if not p.exists() or p.read_text(encoding="utf-8") != text:
            out.append(name)
    return out


def run(check: bool = False) -> int:
    files, removed, probs = generate()
    errs = [p for p in probs if p.startswith("error")]
    print(f"lint: 오류 {len(errs)} · 경고 {len(probs) - len(errs)}  /  OWL: 외부 어휘 주어 트리플 {removed}개 제거")
    if check:
        d = drift(files)
        print("드리프트:", d or "없음")
        return 1 if d else 0
    GEN.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (GEN / name).write_text(text, encoding="utf-8", newline="\n")
    print("생성:", ", ".join(files))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(run(check="--check" in sys.argv[1:]))
