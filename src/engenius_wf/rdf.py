"""RDF — 작성분(authored)·계산분(derived) 2그래프 + trig. 술어 IRI 는 generated/terms.json 에서 (스키마가 정본).

- 작성 그래프 A: YAML 에 적힌 칸을 그대로 (참조는 레지스트리 IRI 로), key 는 skos:notation.
- 파생 그래프 D: 선후(p-plan:isPrecededBy — 되돌림 간선 제외, 늘 DAG)·P-Plan 이중 타입·변수(DataVariable)·
  루프 몸통·나르는 계약·수렴 뒤 단계·동결 기록(InterfaceRelease)·폐기 IRI(owl:deprecated)·PROV 빌드 기록.
- 루프로 되돌아오는 입력은 p-plan:hasInputVar 가 아니라 wf:loopInputVar (P-Plan 변수 그래프를 DAG 로).
- 하위 계획(SubPlan)은 p-plan:isSubPlanOfPlan 으로 상위 계획(워크플로 또는 위 하위 계획)에 잇는다.
  상위 단계(MultiStep)의 wf:produces·consumes 는 경계 표시 — isOutputVarOf 는 가장 깊은 단계 하나에만.
- 변수·바인딩·항목·묶음·하위 계획 IRI 는 레지스트리 ID 에서 해시로 (재빌드해도 같은 IRI).
- Protégé 보기용 합본 workflow_protege.ttl (write_protege): 스키마 OWL + 작성 + 파생 + 외부 어휘 선언을 Turtle 한 파일로.
  xsd:date(동결 일자)는 이 파일에서만 xsd:dateTime 으로 (OWL 2 데이터타입 목록 밖 — HermiT 가 받지 않는다).
"""

from __future__ import annotations

import datetime as dt
import functools
import hashlib
import re
from itertools import chain
from pathlib import Path

from rdflib import BNode, Dataset, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.compare import to_canonical_graph
from rdflib.namespace import DCTERMS, OWL, PROV, RDF, RDFS, SKOS, XSD

from engenius_wf.config import GEN_DIR
from engenius_wf.model import EGID, G_AUTH, G_DER, NESTED, PPLAN, QUDT, UNIT, WF, Terms


def h10(*parts):
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()[:10]


def write_rdf(m, flow, ids, deprecated, units, rel_all, sources, T: Terms, cat):
    A, D = Graph(), Graph()
    for g in (A, D):
        for pfx, ns in (("wf", WF), ("egid", EGID), ("p-plan", PPLAN), ("prov", PROV), ("skos", SKOS), ("dcterms", DCTERMS),
                        ("qudt", QUDT), ("unit", UNIT), ("owl", OWL)):
            g.bind(pfx, ns)
    I = lambda k: EGID[ids[k]]  # noqa: E731
    ko = lambda s: Literal(str(s), lang="ko")  # noqa: E731

    def lit(rng, v):
        if rng == "boolean":
            return Literal(bool(v))
        if rng == "integer":
            return Literal(int(v))
        if rng == "float":
            return Literal(float(v), datatype=XSD.float)
        return Literal(str(v))

    REFK = {"Step": "step", "Interface": "interface", "ToolRef": "tool", "Discipline": "discipline", "Component": "component", "Workflow": "plan"}

    def props(node, cls, o, skip=()):
        """YAML 에 적힌 칸을 그대로 RDF 로 (authored 그래프). 참조는 레지스트리 IRI 로."""
        for k, v in o.items():
            if k.startswith("_") or k in skip or k == "key":
                continue
            sl = T.slot(cls, k)
            if sl is None or sl["built"] or NESTED.get((cls, k)):
                continue
            p = URIRef(sl["uri"])
            for x in (v if isinstance(v, list) else [v]):
                if sl["range"] in REFK:
                    A.add((node, p, I(x)))
                elif p == RDFS.label:
                    A.add((node, p, ko(x)))
                else:
                    A.add((node, p, lit(sl["range"], x)))
        A.add((node, RDF.type, T.curi(cls)))
        if "key" in o:
            A.add((node, SKOS.notation, Literal(o["key"])))

    plan_key = next(iter(m["plan"]))
    plan = I(plan_key)
    props(plan, "Workflow", m["plan"][plan_key])
    D.add((plan, RDF.type, PPLAN.Plan)); D.add((plan, RDF.type, PROV.Plan))  # noqa: E702
    for kind, cls in (("discipline", "Discipline"), ("component", "Component")):
        for k, o in m[kind].items():
            props(I(k), cls, o)
            D.add((I(k), RDF.type, SKOS.Concept))
    for k, o in m["tool"].items():
        props(I(k), "ToolRef", o)
        if o.get("tool_id"):
            D.add((I(k), T.uri("ToolRef", "onto_tool"), EGID[o["tool_id"]]))
    # 하위 계획
    subplan = {p: EGID["SPLAN-" + h10(ids[p])] for p in flow["children"] if p is not None}
    for p, sp in subplan.items():
        D.add((sp, RDF.type, T.curi("SubPlan"))); D.add((sp, RDF.type, PPLAN.Plan))  # noqa: E702
        D.add((sp, RDFS.label, ko(m["step"][p]["label"] + " (하위 계획)"))); D.add((sp, SKOS.notation, Literal(p + "-sub")))  # noqa: E702
        up = m["step"][p].get("part_of")                       # 상위 단계가 속한 계획 — P-Plan 소비자가 계획 나무를 따라가게
        D.add((sp, T.uri("SubPlan", "sub_plan_of"), subplan[up] if up else plan))
    # 변수 (워크플로, 계약)
    var = {}
    for ik in m["interface"]:
        if flow["producers"][ik] or flow["consumers"][ik]:
            v = EGID["VAR-" + h10(ids[plan_key], ids[ik])]
            var[ik] = v
            D.add((v, RDF.type, T.curi("DataVariable"))); D.add((v, RDF.type, PPLAN.Variable))  # noqa: E702
            D.add((v, RDFS.label, ko(m["interface"][ik]["label"])))
            D.add((v, DCTERMS.conformsTo, I(ik))); D.add((v, PPLAN.isVariableOfPlan, plan))  # noqa: E702
            for s in flow["real_prod"][ik]:                    # 실제로 만드는 (가장 깊은) 단계 하나만
                D.add((v, PPLAN.isOutputVarOf, I(s)))
    for k, s in m["step"].items():
        n = I(k)
        props(n, "Step", s)
        D.add((n, RDF.type, PPLAN.Step))
        if k in subplan:
            D.add((n, RDF.type, PPLAN.MultiStep)); D.add((n, PPLAN.isDecomposedAsPlan, subplan[k]))  # noqa: E702
        D.add((n, PPLAN.isStepOfPlan, subplan[s["part_of"]] if s.get("part_of") else plan))
        for f, bcls, pfx in (("inputs", "InputBinding", "INB"), ("outputs", "OutputBinding", "OUB")):
            for b in s.get(f, []):
                bn = EGID[f"{pfx}-" + h10(ids[k], ids[b["interface"]])]
                A.add((n, T.uri("Step", f), bn))
                props(bn, bcls, b)
                ik = b["interface"]
                if ik in var:
                    D.add((bn, T.uri(bcls, "variable"), var[ik]))
                if f == "inputs":
                    D.add((n, T.uri("Step", "consumes"), I(ik)))
                    D.add((bn, T.uri("InputBinding", "kind"), Literal(b["_kind"])))
                    if ik in var:
                        D.add((n, T.uri("Step", "loop_input_vars" if b["_kind"] == "루프" else "input_vars"), var[ik]))
                else:
                    D.add((n, T.uri("Step", "produces"), I(ik)))
    for (u, v) in set(flow["data_edges"]) | flow["after_edges"]:
        if (u, v) not in flow["back"]:
            D.add((I(v), PPLAN.isPrecededBy, I(u)))
    for k, i in m["interface"].items():
        n = I(k)
        props(n, "Interface", i)
        D.add((n, T.uri("Interface", "json_schema"), Literal(f"contracts/{k}/{i['version']}.schema.json")))

        def items(owner, lst, scope):
            for o, it in enumerate(lst, 1):
                x = EGID["IFI-" + h10(ids[k], scope, it["name"])]
                A.add((owner, T.uri("Interface", "items"), x))
                props(x, "InterfaceItem", it, skip=("ref",))
                D.add((x, T.uri("InterfaceItem", "order"), Literal(o)))
                if it.get("unit") in units:
                    D.add((x, QUDT.hasUnit, UNIT[units[it["unit"]]["qudt"]]))
                r = it.get("ref")
                if r:
                    A.add((x, T.uri("InterfaceItem", "ref"), EGID["REC-" + h10(ids[k], r)] if r in i["_records"] else I(r)))
        items(n, i["items"], "")
        for rn, r in i["_records"].items():
            rnode = EGID["REC-" + h10(ids[k], rn)]
            A.add((n, T.uri("Interface", "records"), rnode))
            A.add((rnode, RDF.type, T.curi("Record"))); A.add((rnode, T.uri("Record", "name"), Literal(rn)))  # noqa: E702
            if r.get("label"):
                A.add((rnode, RDFS.label, ko(r["label"])))
            items(rnode, r["items"], rn)
        for ver, rel in rel_all.get(k, {}).items():
            rn = EGID["REL-" + h10(ids[k], ver)]
            D.add((rn, RDF.type, T.curi("InterfaceRelease"))); D.add((rn, RDF.type, PROV.Entity))  # noqa: E702
            D.add((rn, RDFS.label, ko(f"{i['label']} {ver} 동결")))
            D.add((rn, OWL.versionInfo, Literal(ver))); D.add((rn, DCTERMS.isVersionOf, n))  # noqa: E702
            D.add((rn, T.uri("InterfaceRelease", "released_at"), Literal(rel["released_at"], datatype=XSD.date)))
            D.add((rn, T.uri("InterfaceRelease", "reason"), Literal(rel["reason"])))
            D.add((rn, T.uri("InterfaceRelease", "json_schema"), Literal(f"contracts/{k}/{ver}.schema.json")))
    for lk, lp in m["loop"].items():
        n = I(lk)
        props(n, "Loop", lp)
        info = flow["loops"].get(lk, {})
        for f, sl in (("members", "members"), ("after_convergence", "after_convergence")):
            for s in info.get(f, []):
                D.add((n, T.uri("Loop", sl), I(s)))
        for c in info.get("carries", []):
            D.add((n, T.uri("Loop", "carries"), I(c)))
    for did in deprecated:
        D.add((EGID[did], OWL.deprecated, Literal(True)))
    now = dt.datetime.now().replace(microsecond=0)
    run = EGID["BUILD-" + now.strftime("%Y%m%dT%H%M%S")]
    D.add((run, RDF.type, PROV.Activity)); D.add((run, PROV.endedAtTime, Literal(now.isoformat(), datatype=XSD.dateTime)))  # noqa: E702
    for name, sha in sources:
        s = EGID["SRC-" + sha[:10]]
        D.add((s, RDF.type, PROV.Entity)); D.add((s, RDFS.label, Literal(name))); D.add((s, DCTERMS.identifier, Literal("sha256:" + sha)))  # noqa: E702
        D.add((run, PROV.used, s))
    return A, D


def write_graphs(out: Path, A: Graph, D: Graph):
    """workflow.ttl (작성) · workflow_derived.ttl (계산) · workflow.trig (named graph 2개 — Fuseki 에 한 번에)."""
    (out / "workflow.ttl").write_text(A.serialize(format="turtle"), encoding="utf-8", newline="\n")
    (out / "workflow_derived.ttl").write_text(D.serialize(format="turtle"), encoding="utf-8", newline="\n")
    ds = Dataset()
    for g, name in ((A, G_AUTH), (D, G_DER)):
        gg = ds.graph(name)
        for t in g:
            gg.add(t)
    (out / "workflow.trig").write_text(ds.serialize(format="trig"), encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------- Protégé 보기용 합본
PROTEGE_FILE = "workflow_protege.ttl"
OWL_FILE = GEN_DIR / "wfo.owl.ttl"
PROTEGE_BANNER = (
    "# 자동 생성 (build) — Protégé 보기용 합본: 스키마 OWL(schema/generated/wfo.owl.ttl) + 작성(workflow.ttl) + 파생(workflow_derived.ttl)\n"
    "# + 이 파일에만 넣은 외부 어휘 선언(p-plan·prov·dcterms·qudt·skos …). 빌드 시각 기록(BUILD)은 뺐다 — 같은 입력이면 같은 파일.\n"
    "# 동결 일자(wf:releasedAt)는 이 파일에서만 xsd:date → xsd:dateTime (그날 00:00:00) — xsd:date 는 OWL 2 데이터타입 목록 밖이라\n"
    "# HermiT 가 시작하지 않는다. 정본(wfo.owl.ttl·workflow_derived.ttl)은 xsd:date 그대로.\n"
    "# 보기 전용: 여기서 고친 것은 YAML 로 돌아가지 않는다 (원본은 YAML 폴더). Fuseki 적재는 workflow.trig.\n")
# OWL 2 데이터타입 목록(datatype map) 밖의 xsd:date — HermiT 는 목록 안의 데이터타입만 받는다(UnsupportedDatatypeException).
# 보기용 합본에서만 xsd:dateTime 으로 바꿔 넣는다 (정본 스키마는 SHACL·JSON Schema format: date 가 xsd:date 에 기댄다)
DATE_LEX = re.compile(r"(-?\d{4,}-\d{2}-\d{2})(Z|[+-]\d{2}:\d{2})?")
BUILTIN_NS = (str(RDF), str(RDFS), str(OWL), str(XSD))   # 내장 어휘 — 선언하지 않는다
# 설명 술어 — 값이 IRI 든 글자든 주석 속성 (이름·key·메모·정의는 관계가 아니다)
DESCRIPTIVE = frozenset({SKOS.notation, SKOS.note, SKOS.definition, SKOS.prefLabel, SKOS.altLabel, SKOS.hiddenLabel,
                         SKOS.scopeNote, SKOS.example, SKOS.editorialNote, SKOS.changeNote, SKOS.historyNote,
                         DCTERMS.title, DCTERMS.description, DCTERMS.license})
PROP_KINDS = (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty)
CLASS_KINDS = (OWL.Class, RDFS.Datatype)


def _builtin(x) -> bool:
    return str(x).startswith(BUILTIN_NS)


def owl2_view(t):
    """트리플 하나를 보기용으로 — xsd:date 를 xsd:dateTime 으로 (클래스 제약의 필러, 동결 일자 리터럴 'YYYY-MM-DD' → 'YYYY-MM-DDT00:00:00',
    시간대가 적혀 있으면 그대로 붙인다). 날짜 모양이 아닌 xsd:date 글자(손으로 고친 동결본 등)는 형 없는 글자로 둔다 — 추론기가
    형 오류로 멈추지 않고, 값은 그대로 보인다. 그 밖의 트리플은 그대로."""
    s, p, o = t
    if isinstance(o, URIRef) and o == XSD.date:
        return s, p, XSD.dateTime
    if isinstance(o, Literal) and o.datatype == XSD.date:
        m = DATE_LEX.fullmatch(str(o))
        return s, p, (Literal(f"{m[1]}T00:00:00{m[2] or ''}", datatype=XSD.dateTime) if m else Literal(str(o)))
    return t


@functools.lru_cache(maxsize=2)
def _schema_view(path: str, mtime_ns: int, size: int):
    """스키마 OWL 트리플 — 머리(owl:Ontology)를 떼고 빈 노드(클래스 제약)를 정규화한 것. 정규화가 1초 남짓이라 프로세스 안에서 한 번
    (파일이 바뀌면 mtime·크기로 다시). 빈 노드 이름이 고정돼야 Turtle 줄 순서가 실행마다 같다. → (트리플, 접두, 스키마 판)"""
    g = Graph().parse(path, format="turtle")
    ver = ""
    for ont in list(g.subjects(RDF.type, OWL.Ontology)):
        ver = ver or str(g.value(ont, OWL.versionInfo) or "")
        g.remove((ont, None, None))
    return tuple(to_canonical_graph(g)), tuple(g.namespaces()), ver


def _is_datarange(g: Graph, f) -> bool:
    if isinstance(f, URIRef) and (str(f).startswith(str(XSD)) or f in (RDFS.Literal, RDF.PlainLiteral, RDF.langString)):
        return True
    return (f, RDF.type, RDFS.Datatype) in g


def _prop_kind(g: Graph, p, vocab: set):
    """술어 하나의 종류 하나 (같은 술어를 두 종류로 선언하면 OWL 2 DL punning 위반)."""
    if p in DESCRIPTIVE:
        return OWL.AnnotationProperty
    vals = list(g.objects(None, p))
    restrictions = list(g.subjects(OWL.onProperty, p))
    if restrictions:                    # 클래스 제약에 쓰인 술어 — 주석 속성은 제약에 둘 수 없다. 필러가 데이터타입이면 데이터 속성
        fillers = [f for r in restrictions for pf in (OWL.allValuesFrom, OWL.someValuesFrom, OWL.onClass, OWL.onDataRange)
                   if (f := g.value(r, pf)) is not None]
        if fillers:
            return OWL.DatatypeProperty if all(_is_datarange(g, f) for f in fillers) else OWL.ObjectProperty
        return OWL.DatatypeProperty if vals and all(isinstance(v, Literal) for v in vals) else OWL.ObjectProperty
    if any(s in vocab for s in g.subjects(p, None)):   # 어휘(클래스·속성·데이터타입)에 붙은 것 = 어휘 설명
        return OWL.AnnotationProperty
    if vals and all(isinstance(v, URIRef) for v in vals):
        return OWL.ObjectProperty
    if vals and all(isinstance(v, Literal) for v in vals):
        return OWL.DatatypeProperty
    return OWL.AnnotationProperty


def declarations(g: Graph) -> list:
    """g 에 쓰였는데 선언이 없는 술어·클래스의 OWL 선언 (외부 어휘 — p-plan·prov·dcterms·qudt·skos 등).

    Protégé(OWL API)는 선언 없는 술어를 주석으로 읽어 개체 사이 관계가 '관계'(Property assertions)로 보이지 않는다.
    정본 OWL(schema/generated)은 남의 어휘에 트리플을 쓰지 않으므로(schema_gen 정리 1) 이 선언은 보기용 합본에만 넣는다.
    술어: 설명 술어 → 주석 속성 · 클래스 제약에 쓰인 것 → 필러로 객체/데이터 속성 · 어휘에 붙은 것 → 주석 속성 ·
    나머지는 값 모양 (전부 IRI → 객체 속성, 전부 글자 → 데이터 속성, 섞이면 주석 속성). 클래스: rdf:type 대상·상위 클래스·
    객체 속성 제약 필러·정의역·치역·합집합 구성원 중 선언 없는 것 → owl:Class."""
    kind = {}
    for k in PROP_KINDS:
        for p in g.subjects(RDF.type, k):
            kind.setdefault(p, k)
    classes = {c for k in CLASS_KINDS for c in g.subjects(RDF.type, k)}
    vocab = set(kind) | classes | set(g.subjects(RDF.type, OWL.Ontology))
    preds = {p for p in g.predicates() if not _builtin(p)}
    preds |= {p for p in g.objects(None, OWL.onProperty) if isinstance(p, URIRef) and not _builtin(p)}
    out = []
    for p in sorted(preds - set(kind)):
        kind[p] = _prop_kind(g, p, vocab)
        out.append((p, RDF.type, kind[p]))
    cands = set(g.objects(None, RDF.type)) | set(g.objects(None, RDFS.subClassOf)) | set(g.objects(None, RDFS.domain))
    for r in g.subjects(OWL.onProperty, None):
        if kind.get(g.value(r, OWL.onProperty)) == OWL.ObjectProperty:
            cands |= {g.value(r, pf) for pf in (OWL.allValuesFrom, OWL.someValuesFrom, OWL.onClass)}
    cands |= {o for p, o in g.subject_objects(RDFS.range) if kind.get(p) == OWL.ObjectProperty}
    for lst in chain(g.objects(None, OWL.unionOf), g.objects(None, OWL.intersectionOf)):
        cands |= set(Collection(g, lst))
    out += [(c, RDF.type, OWL.Class) for c in sorted(c for c in cands if isinstance(c, URIRef) and not _builtin(c) and c not in classes)]
    return out


def protege_graph(A: Graph, D: Graph, plan: URIRef, plan_label: str, plan_version, owl_file: Path = OWL_FILE):
    """보기용 합본 그래프와 건수 — 스키마(머리 뗌) + 작성 + 파생(빌드 시각 기록 BUILD 뺌) + 머리 하나 + 선언.

    머리(owl:Ontology)는 워크플로 plan IRI 기준 하나(<plan>/protege), owl:versionInfo 는 plan 의 version (빌드 시각이 아니다).
    owl:imports 는 두지 않는다 (폐쇄망에서 Protégé 가 인터넷으로 찾으러 가지 않게). 건수는 단계마다 새로 더해진 트리플 수라 합 = 전체.
    스키마·작성·파생 트리플은 owl2_view 를 거친다 (xsd:date → xsd:dateTime, 한 트리플이 한 트리플로 — 건수는 그대로, 바꾼 수는 n['retyped'])."""
    st = Path(owl_file).stat()
    s_triples, s_ns, s_ver = _schema_view(str(Path(owl_file).resolve()), st.st_mtime_ns, st.st_size)
    g = Graph()
    for pfx, ns in chain(s_ns, A.namespaces(), D.namespaces()):
        g.bind(pfx, ns, override=True)
    n = {"retyped": 0}

    def add(t):
        v = owl2_view(t)
        n["retyped"] += v != t
        g.add(v)

    for t in s_triples:
        add(t)
    n["schema"] = len(g)
    for t in A:
        add(t)
    n["authored"] = len(g) - n["schema"]
    builds = {s for s in D.subjects(RDF.type, PROV.Activity) if str(s).startswith(str(EGID) + "BUILD-")}
    for t in D:
        if t[0] not in builds:
            add(t)
    n["derived"] = len(g) - n["schema"] - n["authored"]
    onto = URIRef(f"{plan}/protege")
    g.add((onto, RDF.type, OWL.Ontology))
    g.add((onto, RDFS.label, Literal(f"{plan_label} — Protégé 보기용 합본", lang="ko")))
    retyped = (" 동결 일자(wf:releasedAt)는 이 파일에서만 xsd:date 대신 xsd:dateTime(그날 00:00:00) — xsd:date 는 OWL 2 데이터타입 목록 밖이라 "
               "HermiT 가 시작하지 않는다 (정본은 xsd:date)." if n["retyped"] else "")
    g.add((onto, RDFS.comment, Literal(f"스키마(wfo {s_ver}) + 작성 + 파생(빌드 시각 기록 제외) + 외부 어휘 선언. 보기 전용 — "
                                       "Protégé 에서 고친 것은 YAML 로 돌아가지 않는다. 추론 결과는 판정이 아니다." + retyped, lang="ko")))
    if plan_version not in (None, ""):
        g.add((onto, OWL.versionInfo, Literal(str(plan_version))))
    n["header"] = len(g) - n["schema"] - n["authored"] - n["derived"]
    decl = declarations(g)
    for t in decl:
        g.add(t)
    n["declared"] = len(decl)
    n["total"] = len(g)
    if any(isinstance(x, BNode) for t in chain(A, D) for x in t):   # 지금 데이터에는 빈 노드가 없다 — 생기면 전체를 정규화해 순서를 고정
        c = Graph()
        for pfx, ns in g.namespaces():
            c.bind(pfx, ns, override=True)
        for t in to_canonical_graph(g):
            c.add(t)
        g = c
    return g, n


def write_protege(out: Path, A: Graph, D: Graph, plan: URIRef, plan_label: str, plan_version) -> dict:
    """workflow_protege.ttl — Protégé 에서 File > Open 하나로 클래스·개체·관계를 함께 보는 Turtle 한 파일 (trig 는 named graph 용 — Protégé 보기에 맞지 않는다)."""
    g, n = protege_graph(A, D, plan, plan_label, plan_version)
    (out / PROTEGE_FILE).write_text(PROTEGE_BANNER + g.serialize(format="turtle"), encoding="utf-8", newline="\n")
    return n
