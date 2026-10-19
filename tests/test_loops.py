"""루프 여럿 (W1 검토 수리) — 같은 처음(back_to)으로 되돌아가는 루프는 한 반복 · 안쪽 루프의 곁가지는 바깥 몸통 ·
진짜 엇갈림만 L04 · 그림의 '수렴 뒤' 배지는 어느 루프 몸통에도 들지 않는 단계만.

fixtures/loops/ 는 공개 교과서 수준의 가상 예시다 (6분야 흉내·최소 중첩·엇갈림·형제 가지).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from engenius_wf.pipeline import run
from engenius_wf.report import Report
from wfhelp import codes, copy_example, edit, run_cli

FIX = Path(__file__).resolve().parent / "fixtures" / "loops"
WF = "http://en-genius.local/onto/wf/"


def _flow(name, src=None):
    rep = Report()
    ctx = run(src or FIX / name, None, [], rep, write=False)
    assert ctx is not None, rep.render()
    return ctx["flow"]["loops"], rep


def _copy(tmp_path, name):
    d = tmp_path / name
    shutil.copytree(FIX / name, d)
    return d


def test_same_head_loops_are_one_iteration():
    """압축기·터빈·이차유로가 각각 사이클로 되돌아오는 6분야 꼴 — 거짓 L04 없음, 형제 분기 단계를 '수렴 뒤' 로 세지 않음."""
    loops, rep = _flow("six")
    assert loops["loop-cmp"] == {"members": ["cmp-map", "cmp-meanline", "perf-cycle"], "carries": ["if-cmp-map"],
                                 "after_convergence": ["comb-sizing"]}
    assert loops["loop-trb"]["members"] == ["cool-flow", "perf-cycle", "trb-map", "trb-meanline"]
    assert loops["loop-sas"]["members"] == ["cool-flow", "perf-cycle", "sas-network", "trb-meanline"]
    for lk in ("loop-cmp", "loop-trb", "loop-sas"):
        assert loops[lk]["after_convergence"] == ["comb-sizing"]
    assert loops["loop-cool"] == {"members": ["cool-flow", "trb-meanline"], "carries": ["if-cool-flows"],
                                  "after_convergence": ["sas-network", "trb-map"]}
    assert [c for c in codes(rep.render()) if c[0] != "참고"] == []
    assert "같은 처음 'perf-cycle' 로 되돌아가는 루프 ['loop-sas', 'loop-trb'] 와 한 반복" in rep.render()


def test_inner_loop_side_branch_is_in_outer_body(tmp_path):
    """사이클 루프 안의 냉각↔터빈 안쪽 루프 — 냉각 유량 단계는 바깥 반복마다 다시 돈다 (몸통). L04·L06 거짓 경고 없음."""
    loops, rep = _flow("mini_nested")
    assert loops["loop-trb"] == {"members": ["cool-flow", "perf-cycle", "trb-map", "trb-meanline"], "carries": ["if-trb-map"],
                                 "after_convergence": []}
    assert loops["loop-cool"]["members"] == ["cool-flow", "trb-meanline"]
    assert set(loops["loop-cool"]["members"]) <= set(loops["loop-trb"]["members"])
    assert [c for c in codes(rep.render()) if c[0] != "참고"] == []
    d = _copy(tmp_path, "mini_nested")
    edit(d / "trb.yaml", "    initial: 첫 바퀴는 설계점 효율 가정값", "    initial: 첫 바퀴는 설계점 효율 가정값\n    monitor: if-cool-flows.W_cool")
    _, rep = _flow("mini_nested", d)
    assert "L06" not in {c for _, c in codes(rep.render())}


def test_true_cross_still_warns():
    """처음이 다른 두 루프가 합류 단계만 같다 — 진짜 엇갈림은 L04 를 그대로 내고, 고치는 법(→ 줄)을 붙인다."""
    _, rep = _flow("mini_cross")
    lines = rep.render().splitlines()
    i = next(i for i, ln in enumerate(lines) if "[경고 L04]" in ln)
    assert "겹치는 단계 ['z-step'] 만 같다" in lines[i]
    assert lines[i + 1].strip().startswith("→") and "include" in lines[i + 1]


def test_sibling_loop_is_not_absorbed():
    """다른 가지의 루프(처음이 바깥 루프 하류지만 끝이 바깥 루프 끝에 닿지 않음)는 바깥 몸통에 들어오지 않는다."""
    loops, _ = _flow("mini_sibling")
    assert loops["loop-trb"]["members"] == ["perf-cycle", "trb-map", "trb-meanline"]
    assert loops["loop-sas"]["members"] == ["cool-flow", "sas-network"]


@pytest.mark.parametrize("src, members, after", [
    ("short", {"loop-cmp-match": ["cmp-meanline", "perf-cycle"]}, {"loop-cmp-match": []}),
    ("textbook", {"loop-cmp-match": ["cmp-map", "cmp-meanline", "perf-offdesign"]}, {"loop-cmp-match": ["cmp-cfd-check"]}),
])
def test_single_loop_examples_unchanged(src, members, after):
    from engenius_wf.config import EXAMPLES_DIR

    loops, _ = _flow(src, EXAMPLES_DIR / src)
    assert {k: v["members"] for k, v in loops.items()} == members
    assert {k: v["after_convergence"] for k, v in loops.items()} == after


def _badged(html: str) -> set[str]:
    """그림에서 '수렴 뒤' 배지가 붙은 단계 key."""
    out = set()
    for g in re.findall(r'<g tabindex="0">(.*?)</g>', html, flags=re.S):
        if 'class="bd"' in g:
            out.add(re.search(r"<title>([^\n<]+)", g).group(1))
    return out


@pytest.mark.parametrize("name, badged", [("six", {"comb-sizing"}), ("mini_nested", set()), ("mini_sibling", set())])
def test_html_badge_only_outside_every_loop_body(tmp_path, name, badged):
    d = _copy(tmp_path, name)
    out = tmp_path / "out"
    rc, text = run_cli(["build", d, "--out", out])
    assert rc == 0, text
    assert _badged((out / "workflow.html").read_text(encoding="utf-8")) == badged


def test_html_badge_textbook(tmp_path):
    d = copy_example(tmp_path, "textbook")
    rc, text = run_cli(["build", d, "--out", tmp_path / "out"])
    assert rc == 0, text
    assert _badged((tmp_path / "out" / "workflow.html").read_text(encoding="utf-8")) == {"cmp-cfd-check"}


def test_rdf_loop_members_and_after_convergence(tmp_path):
    """RDF 파생 그래프 — 안쪽 루프 곁가지가 바깥 몸통(wf:loopMember), 같은 처음 루프의 형제 몸통 단계는 wf:afterConvergence 아님."""
    from rdflib import Graph

    d = _copy(tmp_path, "six")
    out = tmp_path / "out"
    rc, text = run_cli(["build", d, "--out", out])
    assert rc == 0, text
    g = Graph().parse(out / "workflow_derived.ttl", format="turtle")
    g.parse(out / "workflow.ttl", format="turtle")
    q = ("PREFIX wf: <%s> PREFIX skos: <http://www.w3.org/2004/02/skos/core#> "
         "SELECT ?lk ?sk WHERE { ?l wf:%s ?s . ?l skos:notation ?lk . ?s skos:notation ?sk }")
    members = {(str(a), str(b)) for a, b in g.query(q % (WF, "loopMember"))}
    after = {(str(a), str(b)) for a, b in g.query(q % (WF, "afterConvergence"))}
    assert ("loop-trb", "cool-flow") in members
    assert {s for lk, s in after if lk in ("loop-cmp", "loop-trb", "loop-sas")} == {"comb-sizing"}
