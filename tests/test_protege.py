"""Protégé 보기용 합본 workflow_protege.ttl — 스키마 OWL + 작성 + 파생 + 외부 어휘 선언 (Leo 2026-10-20, 사내 Protégé 반입).

Protégé(OWL API)는 선언 없는 술어를 주석으로 읽어 개체 사이 관계가 '관계'(Property assertions)로 보이지 않는다 → 선언이 핵심.
선언은 이 합본에만 넣고 정본 OWL(schema/generated/wfo.owl.ttl)은 남의 어휘에 트리플을 쓰지 않는다.
이 PC 에는 Protégé·OWL API 가 없다 — 실제로 열어 보는 것은 사내에서. 여기서는 RDF 문법(Jena riot)·선언 규칙·건수·결정성을 본다.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from itertools import chain
from pathlib import Path

import pytest
import yaml
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS, XSD

from engenius_wf.config import GEN_DIR, REPO_ROOT
from engenius_wf.model import EGID, PPLAN, QUDT, WF
from engenius_wf.rdf import PROTEGE_FILE
from wfhelp import build_copy, copy_example, find_jena

PROV = "http://www.w3.org/ns/prov#"
NAMES = ["short", "textbook_nocat", "textbook"]
BUILTIN = (str(RDF), str(RDFS), str(OWL), str(XSD))
PROP_KINDS = (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty)


def _get(built, name):
    if name not in built:
        pytest.skip("형제 저장소 합성 survey.ttl 없음 — 교차 확인 빌드 생략")
    assert built[name].rc == 0, built[name].stdout
    return built[name]


def _builtin(x) -> bool:
    return str(x).startswith(BUILTIN)


def _parts(b):
    """(합본 P, 스키마 S(머리 뗌), 작성 A, 파생 D(빌드 시각 기록 뗌), 빌드 기록 주어) — 각 파일을 따로 읽어서."""
    P = Graph().parse(b.out / PROTEGE_FILE, format="turtle")
    S = Graph().parse(GEN_DIR / "wfo.owl.ttl", format="turtle")
    for ont in list(S.subjects(RDF.type, OWL.Ontology)):
        S.remove((ont, None, None))
    A = Graph().parse(b.out / "workflow.ttl", format="turtle")
    D = Graph().parse(b.out / "workflow_derived.ttl", format="turtle")
    builds = {s for s in D.subjects() if str(s).startswith(str(EGID) + "BUILD-")}
    for s in builds:
        D.remove((s, None, None))
    return P, S, A, D, builds


def _kinds(g: Graph) -> dict:
    out = {}
    for k in PROP_KINDS:
        for p in g.subjects(RDF.type, k):
            out.setdefault(p, set()).add(k)
    return out


@pytest.mark.parametrize("name", NAMES)
def test_one_ontology_head_from_plan(built, name):
    """머리(owl:Ontology)는 하나 — IRI 는 워크플로 plan IRI 기준, owl:versionInfo 는 plan 의 version (빌드 시각 아님). imports 없음."""
    b = _get(built, name)
    P = Graph().parse(b.out / PROTEGE_FILE, format="turtle")
    heads = list(P.subjects(RDF.type, OWL.Ontology))
    plans = list(P.subjects(RDF.type, WF.Workflow))
    assert len(heads) == 1 and len(plans) == 1
    assert heads[0] == URIRef(f"{plans[0]}/protege")
    plan = yaml.load((b.src / "_plan.yaml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)["plan"]
    assert list(P.objects(heads[0], OWL.versionInfo)) == [Literal(plan["version"])]
    assert (None, OWL.imports, None) not in P            # 폐쇄망 — Protégé 가 인터넷으로 가져오러 가지 않게
    assert P.value(heads[0], RDFS.label).language == "ko"


@pytest.mark.parametrize("name", NAMES)
def test_every_predicate_and_class_declared_once(built, name):
    """쓰인 술어(내장 rdf·rdfs·owl·xsd 제외)는 전부 선언, 종류는 술어마다 하나 (OWL 2 DL punning 금지). rdf:type 대상·상위 클래스도 선언."""
    P = Graph().parse(_get(built, name).out / PROTEGE_FILE, format="turtle")
    kinds = _kinds(P)
    assert {p: k for p, k in kinds.items() if len(k) != 1} == {}
    used = {p for p in P.predicates() if not _builtin(p)} | {p for p in P.objects(None, OWL.onProperty) if not _builtin(p)}
    assert sorted(p for p in used if p not in kinds) == []
    classes = {c for k in (OWL.Class, RDFS.Datatype) for c in P.subjects(RDF.type, k)}
    typed = {o for o in P.objects(None, RDF.type) if not _builtin(o)} | \
            {o for o in P.objects(None, RDFS.subClassOf) if isinstance(o, URIRef) and not _builtin(o)}
    assert sorted(typed - classes) == []
    assert not classes & set(kinds)                       # 클래스이면서 속성인 IRI 없음


@pytest.mark.parametrize("name", NAMES)
def test_declared_kind_matches_values(built, name):
    """객체 속성 값은 전부 IRI, 데이터 속성 값은 전부 글자, 주석 속성은 클래스 제약(owl:onProperty)에 쓰이지 않는다."""
    P = Graph().parse(_get(built, name).out / PROTEGE_FILE, format="turtle")
    restricted = set(P.objects(None, OWL.onProperty))
    for p, (k,) in _kinds(P).items():
        vals = list(P.objects(None, p))
        if k == OWL.ObjectProperty:
            assert all(isinstance(v, URIRef) for v in vals), p
        elif k == OWL.DatatypeProperty:
            assert all(isinstance(v, Literal) for v in vals), p
        else:
            assert p not in restricted, p


@pytest.mark.parametrize("name", NAMES)
def test_triple_count_is_schema_authored_derived_declared(built, name):
    """트리플 수 = 스키마(머리 뗌) + 작성 + 파생(빌드 시각 기록 뗌) + 머리 + 선언 — 겹침 없이. 선언은 남의 어휘(wf: 밖)에만.
    빈 노드는 스키마의 클래스 제약뿐 (데이터 쪽은 0). 빌드 화면의 건수 줄도 같은 숫자."""
    b = _get(built, name)
    P, S, A, D, builds = _parts(b)
    assert builds and not any(str(s).startswith(str(EGID) + "BUILD-") for s in P.subjects())
    head = next(P.subjects(RDF.type, OWL.Ontology))
    H = set(P.triples((head, None, None)))
    ground = lambda g: {t for t in g if not any(isinstance(x, BNode) for x in t)}  # noqa: E731
    expected = ground(S) | set(A) | set(D)
    decl = {t for t in ground(P) - expected - H if t[1] == RDF.type}
    assert ground(P) - expected - H == decl                # 그 밖에 새로 생긴 트리플 없음
    assert decl and all(t[2] in PROP_KINDS + (OWL.Class,) and not str(t[0]).startswith(str(WF)) for t in decl)
    assert expected <= ground(P)
    assert len(P) == len(S) + len(A) + len(D) + len(H) + len(decl)
    n_bn = lambda g: sum(1 for t in g if any(isinstance(x, BNode) for x in t))  # noqa: E731
    assert n_bn(P) == n_bn(S) and not any(isinstance(x, BNode) for t in chain(A, D) for x in t)
    assert (f"Protégé 보기용: {PROTEGE_FILE} (트리플 {len(P)} = 스키마 {len(S)} + 작성 {len(A)} + 파생 {len(D)} + "
            f"머리 {len(H)} + 외부 어휘 선언 {len(decl)})") in b.stdout
    if name == "short":                                    # 빈 노드까지 — 같은 그래프 (정규화 비교, 한 번만)
        rest = Graph()
        for t in P:
            if t not in decl and t[0] != head:
                rest.add(t)
        assert isomorphic(rest, S + A + D)


def test_external_vocab_kinds(built):
    """외부 어휘 선언 — P-Plan·PROV·DC·QUDT 관계는 객체 속성, 이름·key·정의는 주석 속성, 외부 클래스는 owl:Class.
    wf: 속성은 스키마의 선언 그대로. 정본 OWL 은 남의 어휘에 트리플이 없다 (선언은 합본에만)."""
    P = Graph().parse(_get(built, "textbook_nocat").out / PROTEGE_FILE, format="turtle")
    k = {p: next(iter(v)) for p, v in _kinds(P).items()}
    for p in (PPLAN.isPrecededBy, PPLAN.isStepOfPlan, PPLAN.hasInputVar, PPLAN.isOutputVarOf, PPLAN.isVariableOfPlan,
              QUDT.hasUnit, DCTERMS.conformsTo, DCTERMS.isVersionOf, SKOS.broader):
        assert k[p] == OWL.ObjectProperty, p
    for p in (SKOS.notation, SKOS.definition, SKOS.inScheme, SKOS.exactMatch):
        assert k[p] == OWL.AnnotationProperty, p
    assert k[DCTERMS.identifier] == OWL.DatatypeProperty
    assert k[WF.hasInput] == OWL.ObjectProperty and k[WF.transfer] == OWL.DatatypeProperty
    for c in (PPLAN.Plan, PPLAN.Step, PPLAN.Variable, URIRef(PROV + "Entity"), URIRef(PROV + "Plan"), SKOS.Concept):
        assert (c, RDF.type, OWL.Class) in P, c
    assert any(True for _ in P.triples((None, PPLAN.isPrecededBy, None)))   # 단계 사이 관계가 개체에 실제로 있다
    S = Graph().parse(GEN_DIR / "wfo.owl.ttl", format="turtle")
    assert sorted({s for s in S.subjects() if isinstance(s, URIRef) and not str(s).startswith(str(WF))}) == []


def test_same_input_same_bytes(built, tmp_path):
    """같은 입력이면 바이트까지 같은 파일 — 같은 프로세스(스키마 캐시)와 새 프로세스(다른 해시 시드) 모두."""
    again = build_copy(tmp_path, "short", name="short_again")
    assert again.rc == 0
    assert (again.out / PROTEGE_FILE).read_bytes() == (_get(built, "short").out / PROTEGE_FILE).read_bytes()
    d = copy_example(tmp_path, "textbook")
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT / "src"), PYTHONUTF8="1", PYTHONHASHSEED="4242")
    p = subprocess.run([sys.executable, "-m", "engenius_wf", "build", str(d), "--out", str(tmp_path / "o")],
                       capture_output=True, cwd=tmp_path, env=env, timeout=300)
    assert p.returncode == 0, p.stderr.decode("utf-8", errors="replace")[-800:]
    assert (tmp_path / "o" / PROTEGE_FILE).read_bytes() == (_get(built, "textbook_nocat").out / PROTEGE_FILE).read_bytes()


@pytest.mark.parametrize("name", ["short", "textbook_nocat"])
def test_jena_riot_validates(built, name):
    """Jena riot --validate (Fuseki 배포본 jar) — 문법·리터럴 형식 경고 0. Java·Fuseki 가 없으면 skip.
    Jena 는 Windows 절대경로를 IRI 로 받지 못하므로 임시 폴더에 복사해 상대경로로 넘긴다."""
    jena = find_jena()
    if not jena:
        pytest.skip("Java·Fuseki 없음 (FUSEKI_HOME/JAVA_HOME 설정 시 실행)")
    java, jar = jena
    with tempfile.TemporaryDirectory() as t:
        shutil.copyfile(_get(built, name).out / PROTEGE_FILE, Path(t) / "p.ttl")
        p = subprocess.run([java, "-cp", str(jar), "riotcmd.riot", "--validate", "p.ttl"], cwd=t, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=300)
    assert p.returncode == 0, (p.stdout + p.stderr)[-800:]
    assert "WARN" not in p.stdout + p.stderr and "ERROR" not in p.stdout + p.stderr, (p.stdout + p.stderr)[-800:]
