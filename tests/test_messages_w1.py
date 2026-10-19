"""작성자 메시지 W1 검토 수리 — U02 안내·단위 별칭 · 파일 머리 discipline R01 한 번 · _plan.yaml 없음(R04)만 ·
Y03 원인 줄(콜론 뒤 공백·전각 콜론) · Y04 '- ' 빠뜨림 안내 · 그림의 하위 단계 (지적 14~19).

예시를 _registry·_released 없이 복사(새로 쓰는 사람 흉내)해 한 곳만 고친 뒤 check 를 돌린다.
"""

from __future__ import annotations

import re

import pytest

from wfhelp import codes, copy_example, edit, run_cli

LINE = re.compile(r"\[(오류|경고|참고) ([A-Z]\d\d)\] (\S+)(?: (\d+)행)?  (.*)")
UNITS_HINT = "새 단위면 units.yaml 에 한 줄 (연습 폴더: 저장소 config\\units.yaml"


def _check(tmp_path, src, edits):
    d = copy_example(tmp_path, src, state=False)
    for f, a, b in edits:
        edit(d / f, a, b)
    return run_cli(["check", d])


def _msg(out, code):
    """(본문 줄, 다음 → 줄) — 그 코드의 첫 메시지."""
    lines = out.splitlines()
    i = next(i for i, ln in enumerate(lines) if LINE.match(ln) and LINE.match(ln).group(2) == code)
    nxt = lines[i + 1].strip() if i + 1 < len(lines) and lines[i + 1].strip().startswith("→") else ""
    return lines[i], nxt


W2 = "      W2:   kg/s | 압축기 입구 유량\n"


@pytest.mark.parametrize("unit, hint_part", [
    ("kg/h", "혹시 kg/s(질량유량) ? — 같은 단위의 다른 표기일 때만 고른다 (배율·종류가 다르면 새 단위)"),
    ("number", "첫칸에는 단위를 적는다"),
    ("k", "대소문자만 다르다 — K"),
])
def test_u02_hint(tmp_path, unit, hint_part):
    rc, out = _check(tmp_path, "short", [("perf.yaml", W2, W2 + f"      X1: {unit} | 시험 항목\n")])
    assert rc == 1
    line, hint = _msg(out, "U02")
    assert f"모르는 단위 '{unit}'" in line and hint_part in hint and UNITS_HINT in hint


def test_u02_hint_without_suggestion_is_clean(tmp_path):
    """비슷한 표기가 없으면 '→  / 새 단위면 …' 처럼 깨지지 않는다."""
    rc, out = _check(tmp_path, "short", [("perf.yaml", W2, W2 + "      X1: zzqq | 시험 항목\n")])
    _, hint = _msg(out, "U02")
    assert hint.startswith("→ 새 단위면 units.yaml")


@pytest.mark.parametrize("unit, want", [("°C", "degC"), ("℃", "degC"), ("m²", "m2"), ("m^2", "m2")])
def test_common_unit_spellings_are_aliases(tmp_path, unit, want):
    rc, out = _check(tmp_path, "short", [("perf.yaml", W2, W2 + f"      X1: {unit} | 시험 항목\n")])
    assert rc == 0, out
    assert f"단위 별칭 '{unit}' 를 '{want}' 로 읽음" in out


def test_discipline_head_typo_reported_once_at_its_line(tmp_path):
    """파일 머리 discipline 오타는 그 줄(1행)에서 R01 한 번 — 단계·계약마다 되풀이하지 않는다 (지적 16)."""
    rc, out = _check(tmp_path, "textbook", [("cmp.yaml", "discipline: cmp\n", "discipline: CMP\n")])
    assert rc == 1
    r01 = [ln for ln in out.splitlines() if "[오류 R01]" in ln]
    assert len(r01) == 1 and r01[0].startswith("[오류 R01] cmp.yaml 2행  discipline: 'CMP' 없음"), r01


def test_missing_plan_shows_only_cause(tmp_path):
    """_plan.yaml 이 없으면 원인 R04 만 — 분야·툴 R01 이 줄줄이 먼저 나오지 않는다 (지적 19)."""
    d = copy_example(tmp_path, "short", state=False)
    (d / "_plan.yaml").unlink()
    rc, out = run_cli(["check", d])
    assert rc == 1
    assert [c for c in codes(out) if c[0] == "오류"] == [("오류", "R04")]
    assert "_plan.yaml 이 이 폴더에 있는지 확인" in out


@pytest.mark.parametrize("old, new, line, frag, hint", [
    ("    tools: excel\n", "    tools:excel\n", 6, "콜론 뒤에 공백이 없다:  tools:excel", "콜론 뒤에 공백 한 칸"),
    ("    label: 압축기 1D 평균반경 설계\n", "    label： 압축기 1D 평균반경 설계\n", 5, "전각 콜론", "영문 콜론"),
])
def test_y03_points_at_cause_line(tmp_path, old, new, line, frag, hint):
    """콜론 뒤 공백 빠짐·전각 콜론 — 멀쩡한 다음 줄이 아니라 원인 줄과 맞는 고치는 법 (지적 17)."""
    rc, out = _check(tmp_path, "short", [("cmp.yaml", old, new)])
    assert rc == 1
    msg, h = _msg(out, "Y03")
    assert msg.startswith(f"[오류 Y03] cmp.yaml {line}행  ") and frag in msg and hint in h, (msg, h)


def test_y04_missing_dash_hint(tmp_path):
    """새 단계 앞 '- ' 를 빠뜨리면 key 가 같은 묶음에 두 번 — '합치거나 지우라' 가 아니라 '- ' 를 붙이라고 (지적 18)."""
    rc, out = _check(tmp_path, "short", [("cmp.yaml", "    outputs: if-cmp-map\n",
                                          "    outputs: if-cmp-map\n\n    key: cmp-extra\n    label: 추가 단계\n")])
    assert rc == 1
    msg, hint = _msg(out, "Y04")
    assert "'key' 가 같은 묶음 안에 두 번" in msg and "앞에 '- ' 를 붙인다" in hint
    assert "합치거나 지우세요" not in out


def test_y04_plain_duplicate_keeps_merge_hint(tmp_path):
    rc, out = _check(tmp_path, "short", [("cmp.yaml", "    outputs: if-cmp-map", "    outputs: if-cmp-map\n    outputs: if-cmp-map")])
    _, hint = _msg(out, "Y04")
    assert "하나로 합치거나 지우세요" in hint


def test_html_shows_sub_steps(tmp_path):
    """상위 단계 상자의 말풍선과 그림 아래 '하위 단계' 표에 하위 단계 이름·툴·받는 데이터가 보인다 (지적 14)."""
    d = copy_example(tmp_path, "textbook", state=False)
    rc, out = run_cli(["build", d, "--out", tmp_path / "out"])
    assert rc == 0, out
    h = (tmp_path / "out" / "workflow.html").read_text(encoding="utf-8")
    box = next(g for g in re.findall(r'<g tabindex="0">(.*?)</g>', h, flags=re.S) if "<title>cmp-cfd-check" in g)
    assert "cmp-cfd-mesh — 압축기 유로 메시 생성 [ANSYS TurboGrid]" in box and "cmp-cfd-solve" in box and "← if-cmp-mesh" in box
    assert "<h2>하위 단계</h2>" in h and "ANSYS CFX" in h
