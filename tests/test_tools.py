"""Tool 온톨로지 연결 — 4술어 연결 계약, X 검사 (합성 카탈로그만으로도), link-tools 후보 CSV (사람이 확정)."""

from __future__ import annotations

import csv

from rdflib.namespace import RDF, SKOS

from engenius_wf.model import EG
from engenius_wf.tools import LINK_PREDICATES, load_catalog, tool_norm
from wfhelp import SYN_CATALOG, codes, copy_example, edit, run_cli


def test_link_contract_is_four_predicates():
    """연결 계약: eg:Tool(타입) · skos:prefLabel/altLabel · eg:status · eg:merged_into — 이것만 읽는다."""
    assert set(LINK_PREDICATES) == {RDF.type, EG.Tool, SKOS.prefLabel, SKOS.altLabel, EG.status, EG.merged_into}


def test_load_synthetic_catalog():
    tools, by_name = load_catalog([str(SYN_CATALOG)])
    assert tools["TOOL-900005"] == {"status": "통합됨", "merged": "TOOL-900001", "label": "GasTurb 13"}
    assert by_name[tool_norm("CFX")] == {"TOOL-900003"}
    assert tool_norm("ANSYS CFX") == "ansyscfx"


def test_x_codes_with_synthetic_catalog_only(tmp_path):
    """합성 카탈로그만 주면 excel 의 TOOL-000002 는 없는 ID (X01 오류), 나머지 X02·X04·X05 는 그대로."""
    d = copy_example(tmp_path, "textbook")
    rc, out = run_cli(["check", d, "--catalog", SYN_CATALOG])
    assert rc == 1
    assert "[오류 X01] _plan.yaml 25행  툴 'excel' 의 TOOL-000002 가 Tool 온톨로지에 없다" in out
    got = {c for _, c in codes(out)}
    assert {"X01", "X02", "X04", "X05"} <= got
    assert "[경고 X02] _plan.yaml 23행  툴 'gasturb' 의 TOOL-900005 는 TOOL-900001(GasTurb) 로 통합됨" in out
    assert "[참고 X04] _plan.yaml 27행  툴 'cfx' 미연결 — 같은 이름의 Tool 온톨로지 툴: TOOL-900003" in out


def test_x03_label_changed(tmp_path):
    d = copy_example(tmp_path, "textbook")
    edit(d / "_plan.yaml", "label_at_link: AxSTREAM}", "label_at_link: AxSTREAM 옛 이름}")
    rc, out = run_cli(["check", d, "--catalog", SYN_CATALOG])
    assert "[경고 X03] _plan.yaml 24행  툴 'axstream': 연결할 때 이름 'AxSTREAM 옛 이름' ≠ 지금 Tool 온톨로지 이름 'AxSTREAM'" in out


def test_unused_tool_t01(tmp_path):
    d = copy_example(tmp_path, "short")
    edit(d / "_plan.yaml", "  - {key: excel,   label: Excel}", "  - {key: excel,   label: Excel}\n  - {key: notepad, label: 메모장}")
    rc, out = run_cli(["check", d])
    assert rc == 0 and "[경고 T01] _plan.yaml 11행  툴 'notepad' 를 쓰는 단계가 없다" in out


def test_link_tools_csv(tmp_path):
    """후보만 낸다 — 빌드는 tool_id 를 자동으로 채우지 않는다 (HITL)."""
    d = copy_example(tmp_path, "textbook")
    before = (d / "_plan.yaml").read_bytes()
    out_csv = tmp_path / "cand.csv"
    rc, out = run_cli(["link-tools", d, "--catalog", SYN_CATALOG, "--csv", out_csv])
    assert rc == 0, out
    assert (d / "_plan.yaml").read_bytes() == before
    with out_csv.open(encoding="utf-8-sig", newline="") as f:
        rows = {r["툴 key"]: r for r in csv.DictReader(f)}
    assert list(rows) == ["gasturb", "axstream", "excel", "turbogrid", "cfx", "meanline-py"]
    assert rows["gasturb"]["후보 TOOL ID"] == "TOOL-900001" and rows["gasturb"]["근거"] == "이름 일치 — 확인 후 적기"
    assert rows["cfx"]["후보 TOOL ID"] == "TOOL-900003" and rows["cfx"]["후보 이름"] == "ANSYS CFX"
    assert rows["turbogrid"]["근거"] == "없음 — 조사 누락 후보"
    assert rows["excel"]["지금 tool_id"] == "TOOL-000002"
