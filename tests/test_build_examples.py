"""V2 예시 빌드 골든 (트리플 수·report·계약 JSON Schema·canonical — 골든은 시안 wf_build.py 의 출력) · 루프 몸통 · V5 P-Plan DAG."""

from __future__ import annotations

import json

import pytest

from engenius_wf.config import EXAMPLES_DIR
from engenius_wf.pipeline import run
from engenius_wf.report import Report
from wfhelp import GOLDEN, acyclic, codes

PP = "PREFIX p-plan: <http://purl.org/net/p-plan#> PREFIX wf: <http://en-genius.local/onto/wf/> "

# (예시, 골든 폴더, report 골든 파일) — textbook 은 survey.ttl 교차 확인이 있을 때와 없을 때 둘 다
REPORTS = [("short", "short", "report.txt"), ("textbook_nocat", "textbook", "report_nocat.txt"), ("textbook", "textbook", "report.txt")]


def _get(built, name):
    if name not in built:
        pytest.skip("형제 저장소 합성 survey.ttl 없음 — 교차 확인 빌드 생략")
    return built[name]


@pytest.mark.parametrize("name, n_auth, n_der, n_step, n_ifc, n_loop", [
    ("short", 104, 64, 2, 2, 1),
    ("textbook_nocat", 427, 221, 7, 7, 1),
    ("textbook", 427, 221, 7, 7, 1),
])
def test_triple_counts(built, name, n_auth, n_der, n_step, n_ifc, n_loop):
    b = _get(built, name)
    assert b.rc == 0, b.stdout
    assert f"TTL: 작성 {n_auth} + 파생 {n_der} 트리플 · 단계 {n_step} · 계약 {n_ifc} (JSON Schema {n_ifc}) · 루프 {n_loop}" in b.stdout
    for f in ("workflow.ttl", "workflow_derived.ttl", "workflow.trig", "workflow.html", "report.txt", "canonical.json"):
        assert (b.out / f).is_file()


@pytest.mark.parametrize("name, gold, rfile", REPORTS)
def test_report_golden(built, name, gold, rfile):
    b = _get(built, name)
    assert b.report == (GOLDEN / gold / rfile).read_text(encoding="utf-8")


def test_report_codes(built):
    assert codes(built["short"].report) == [("참고", "D07"), ("참고", "L08"), ("참고", "U03")]
    assert codes(built["textbook_nocat"].report) == [("참고", "D07"), ("참고", "L08"), ("참고", "U03")]
    if "textbook" in built:
        assert codes(built["textbook"].report) == [("경고", "X02"), ("참고", "D07"), ("참고", "L08"), ("참고", "U03"),
                                                     ("참고", "X05"), ("참고", "X04")]


@pytest.mark.parametrize("name, gold", [("short", "short"), ("textbook_nocat", "textbook")])
def test_contract_schemas_golden(built, name, gold):
    """계약 JSON Schema·골격 예시가 시안 출력과 내용까지 같다 (x-interface IRI 는 커밋된 레지스트리 기준)."""
    got = sorted(p.relative_to(built[name].out / "contracts").as_posix() for p in (built[name].out / "contracts").rglob("*.json"))
    want = sorted(p.relative_to(GOLDEN / gold / "contracts").as_posix() for p in (GOLDEN / gold / "contracts").rglob("*.json"))
    assert got == want
    for rel in want:
        a = json.loads((built[name].out / "contracts" / rel).read_text(encoding="utf-8"))
        assert a == json.loads((GOLDEN / gold / "contracts" / rel).read_text(encoding="utf-8")), rel


def test_contract_schema_content(built):
    """계약 스키마의 핵심 꼴 — 봉투·닫힌 data·단위·범위·대소문자 무시 확장자·묶음 $defs."""
    s = json.loads((built["textbook_nocat"].out / "contracts" / "if-cycle-dp" / "0.1.0.schema.json").read_text(encoding="utf-8"))
    assert s["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert s["required"] == ["contract", "version", "data"] and s["additionalProperties"] is False
    assert s["properties"]["iteration"]["minimum"] == 0
    data = s["$defs"]["_data"]
    assert data["additionalProperties"] is False and data["required"] == ["OPR", "Tt4", "stations"]
    assert data["properties"]["Tt4"]["maximum"] == 2200.0 and data["properties"]["Tt4"]["x-qudt-unit"] == "http://qudt.org/vocab/unit/K"
    assert data["properties"]["stations"] == {"title": "스테이션 표", "type": "array", "items": {"$ref": "#/$defs/Station"}}
    assert s["$defs"]["Station"]["properties"]["Pt"]["x-unit"] == "kPa"
    m = json.loads((built["textbook_nocat"].out / "contracts" / "if-cmp-map" / "0.1.0.schema.json").read_text(encoding="utf-8"))
    assert m["$defs"]["_data"]["properties"]["map_file"]["pattern"] == r"\.([cC][sS][vV]|[tT][xX][tT])$"
    assert m["$defs"]["SpeedLine"]["properties"]["points"]["minItems"] == 3


@pytest.mark.parametrize("name, gold", [("short", "short"), ("textbook_nocat", "textbook")])
def test_canonical_golden(built, name, gold):
    a = json.loads((built[name].out / "canonical.json").read_text(encoding="utf-8"))
    assert a == json.loads((GOLDEN / gold / "canonical.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("src, members, carries, after", [
    ("short", ["cmp-meanline", "perf-cycle"], ["if-cmp-map"], []),
    ("textbook", ["cmp-map", "cmp-meanline", "perf-offdesign"], ["if-perf-od"], ["cmp-cfd-check"]),
])
def test_loop_body(src, members, carries, after):
    """루프 몸통·나르는 계약·수렴 뒤 단계 (빌드가 계산)."""
    rep = Report()
    ctx = run(EXAMPLES_DIR / src, None, [], rep, write=False)
    assert ctx is not None
    assert ctx["flow"]["loops"]["loop-cmp-match"] == {"members": members, "carries": carries, "after_convergence": after}


def test_input_kinds():
    ctx = run(EXAMPLES_DIR / "textbook", None, [], Report(), write=False)
    kinds = {(k, b["interface"]): b["_kind"] for k, s in ctx["m"]["step"].items() for b in s.get("inputs", [])}
    assert kinds[("perf-cycle-dp", "if-engine-reqs")] == "외부"
    assert kinds[("cmp-meanline", "if-perf-od")] == "루프"
    assert kinds[("cmp-meanline", "if-cycle-dp")] == "앞 단계"
    assert ctx["flow"]["real_prod"]["if-cmp-cfd-summary"] == ["cmp-cfd-solve"]        # 하위 단계가 있으면 가장 깊은 단계 하나


@pytest.mark.parametrize("name, n_prec, n_var", [("short", 1, 1), ("textbook_nocat", 6, 7)])
def test_pplan_graphs_are_dags(built, name, n_prec, n_var):
    """V5 — isPrecededBy DAG · P-Plan 변수 그래프 DAG · 루프 입력까지 hasInputVar 로 넣었다면 순환 · 생산 단계 둘인 변수 0."""
    g = built[name].union()
    prec = [(str(b), str(a)) for a, b in g.query(PP + "SELECT ?a ?b WHERE { ?a p-plan:isPrecededBy ?b }")]
    var = [(str(a), str(b)) for a, b in g.query(PP + "SELECT ?a ?b WHERE { ?v p-plan:isOutputVarOf ?a . ?b p-plan:hasInputVar ?v }")]
    loop = [(str(a), str(b)) for a, b in g.query(PP + "SELECT ?a ?b WHERE { ?v p-plan:isOutputVarOf ?a . ?b wf:loopInputVar ?v }")]
    multi = list(g.query(PP + "SELECT ?v (COUNT(?s) AS ?n) WHERE { ?v p-plan:isOutputVarOf ?s } GROUP BY ?v HAVING (COUNT(?s) > 1)"))
    assert (len(prec), len(var)) == (n_prec, n_var)
    assert acyclic(prec) and acyclic(var)
    assert not acyclic(var + loop)
    assert multi == []


def test_registry_unchanged_by_build(built):
    """커밋된 예시 레지스트리로 빌드하면 ID 가 그대로다 (새 ID·폐기 없음)."""
    for name, src in (("short", "short"), ("textbook_nocat", "textbook")):
        got = (built[name].src / "_registry" / "ids.csv").read_text(encoding="utf-8")
        assert got == (EXAMPLES_DIR / src / "_registry" / "ids.csv").read_text(encoding="utf-8")
        assert (built[name].src / "_registry" / "origin.txt").read_text(encoding="utf-8") == "example\n"


def test_html_is_offline(built):
    """그림 HTML 에 외부 JS·CSS·글꼴 참조가 없다 (폐쇄망)."""
    h = (built["textbook_nocat"].out / "workflow.html").read_text(encoding="utf-8")
    assert "<script" not in h and "http://" not in h and "https://" not in h
    assert "✋ 수기" in h and "↺" in h and "수렴 뒤" in h


def test_trig_has_two_graphs(built):
    from rdflib import Dataset

    ds = Dataset()
    ds.parse(built["short"].out / "workflow.trig", format="trig")
    sizes = {str(g.identifier): len(g) for g in ds.graphs() if len(g)}
    assert sizes == {"http://en-genius.local/graph/workflow": 104, "http://en-genius.local/graph/workflow-derived": 64}
