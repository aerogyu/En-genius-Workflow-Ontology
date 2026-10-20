"""V9 질의 골든 — queries/q01~q08.rq 를 rdflib 로 (골든 행은 시안 verify.py 의 질의를 시안 출력에 돌린 것)."""

from __future__ import annotations

import json
import re

import pytest

from engenius_wf.query import cell_width, is_cross, query_files, query_title, render_table, run_local, union_graph, with_from
from wfhelp import GOLDEN, run_cli

GOLD = json.loads((GOLDEN / "queries.json").read_text(encoding="utf-8"))
LOCAL = [f"q0{i}" for i in range(1, 7)]


def test_query_files_present():
    files = query_files()
    assert list(files) == [f"q0{i}" for i in range(1, 9)]
    for p in files.values():
        assert query_title(p).startswith("Q")


@pytest.mark.parametrize("q", LOCAL)
@pytest.mark.parametrize("name, gold", [("short", "short"), ("textbook_nocat", "textbook")])
def test_query_rows_golden(built, name, gold, q):
    g = union_graph(built[name].out)
    _, rows = run_local(g, query_files()[q].read_text(encoding="utf-8"))
    assert [list(r) for r in rows] == GOLD[gold][q]


@pytest.mark.parametrize("q", ["q07", "q08"])
def test_cross_queries_golden(built, survey_cats, q):
    """교차 질의 — 워크플로 + Tool 온톨로지(합성 카탈로그 + 형제 저장소 합성 survey.ttl)."""
    g = union_graph(built["textbook_nocat"].out, survey_cats)
    _, rows = run_local(g, query_files()[q].read_text(encoding="utf-8"))
    assert [list(r) for r in rows] == GOLD["textbook_cross"][q]


def test_q08_manual_handoff_matches_survey():
    """시안 실측: 수기 입력을 받는 Excel 의 조사 툴사용 USE-000002 는 csv 를 '메일·수기 전달' 로 받는다고 신고 — 워크플로와 조사가 일치."""
    assert ["cmp-meanline", "if-cycle-dp", "USE-000002", "모름", "csv", "메일·수기 전달"] in GOLD["textbook_cross"]["q08"]


def test_with_from_inserts_before_where():
    text = query_files()["q06"].read_text(encoding="utf-8")
    out = with_from(text, ["urn:a", "urn:b"])
    assert "SELECT ?unit (COUNT(?i) AS ?n)\nFROM <urn:a> FROM <urn:b> WHERE {" in out
    assert out.count("FROM <") == 2
    with pytest.raises(ValueError):
        with_from("# 주석만\nPREFIX x: <urn:x>\n", ["urn:a"])


def test_query_command(built):
    rc, out = run_cli(["query", built["textbook_nocat"].out, "q02", "q03"])
    assert rc == 0, out
    assert "== q02 Q2 수기 전달 입력" in out and "— 2행" in out
    assert "perf-offdesign\tGasTurb\tcmp-meanline\tExcel\tif-perf-od" in out
    rc, out = run_cli(["query", built["textbook_nocat"].out, "q99"])
    assert rc == 2 and "모르는 질의" in out
    rc, out = run_cli(["query", built["textbook_nocat"].out / "없음"])
    assert rc == 1


def test_query_table(built):
    """--table (query.bat) — 칸을 맞춘 표: 머리 줄·구분 줄·행, 한글은 2칸으로 세어 열이 맞는다. 교차 질의는 카탈로그 없이 돌면 참고 한 줄."""
    rc, out = run_cli(["query", built["textbook_nocat"].out, "q02", "q07", "--table"])
    assert rc == 0, out
    lines = out.splitlines()
    head = next(i for i, ln in enumerate(lines) if ln.startswith("== q02"))
    assert lines[head + 1].split() == ["from", "|", "ftool", "|", "to", "|", "ttool", "|", "contract"]
    assert set(lines[head + 2].strip()) <= {"-", "+"}
    rows = lines[head + 3:head + 5]
    assert rows[0].split(" | ")[0].strip() == "perf-cycle-dp" and rows[1].split(" | ")[0].strip() == "perf-offdesign"
    bars = {tuple(cell_width(ln[:m.start()]) for m in re.finditer(r" \| ", ln)) for ln in [lines[head + 1]] + rows}
    assert len(bars) == 1                                       # 모든 줄의 '|' 가 같은 칸에 (한글 툴 이름이 없어도 같은 계산)
    assert "참고: q07 는 Tool 온톨로지 교차 질의" in out
    rc, out = run_cli(["query", built["textbook_nocat"].out, "q02"])
    assert "-+-" not in out and "\t" in out                      # 기본은 탭으로 나눈 줄 그대로


def test_render_table_east_asian_width():
    lines = render_table(["단계", "n"], [("압축기", "1"), ("cmp", "12")])
    assert lines[0] == "단계   | n"
    assert lines[1] == "-------+---"
    assert lines[2] == "압축기 | 1" and lines[3] == "cmp    | 12"
    assert {cell_width(ln.split("|")[0]) for ln in [lines[0]] + lines[2:]} == {7}
    assert render_table(["a"], []) == ["a", "-", "(결과 없음)"]
    assert render_table(["a"], [("x\ty\nz",)])[2] == "x y z"


def test_is_cross():
    files = query_files()
    assert [n for n, p in files.items() if is_cross(p.read_text(encoding="utf-8"))] == ["q07", "q08"]
