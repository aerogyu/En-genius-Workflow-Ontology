"""V8 입문자 실수 주입 23종 — 기대 코드의 첫 메시지 (수준·파일·행) 와 rc 를 고정한다 (골든 = 시안 wf_build.py 실측).

예시를 _registry·_released 없이 복사(새로 쓰는 사람 흉내)해 한 곳만 고친 뒤 check 를 돌린다.
"""

from __future__ import annotations

import re

import pytest

from wfhelp import catalogs_or_none, copy_example, edit, run_cli

# (이름, 원본 예시, [(파일, 바꿀 것, 바꿀 값 — None 이면 그 자리부터 끝까지 지움)], 기대 코드, 수준, 파일, 행, rc, 메시지·안내 일부)
CASES = [
    ("같은 키 두 번", "short", [("cmp.yaml", "    outputs: if-cmp-map", "    outputs: if-cmp-map\n    outputs: if-cmp-map")],
     "Y04", "오류", "cmp.yaml", 10, 1, "'outputs' 가 같은 묶음 안에 두 번 (앞은 9행)"),
    ("탭 들여쓰기", "short", [("perf.yaml", "    label: 설계점 사이클 해석", "\tlabel: 설계점 사이클 해석")],
     "Y02", "오류", "perf.yaml", 5, 1, "들여쓰기에 탭 문자"),
    ("% 따옴표 없이", "short", [("cmp.yaml", "surge_margin: 퍼센트   | 설계점 서지 마진", "surge_margin: % | 설계점 서지 마진")],
     "Y03", "오류", "cmp.yaml", 17, 1, "퍼센트는 '퍼센트' 로 쓰거나"),
    ("칸 이름 오타", "short", [("cmp.yaml", "    outputs: if-cmp-map", "    ouputs: if-cmp-map")],
     "S01", "오류", "cmp.yaml", 4, 1, "혹시 outputs, inputs ?"),
    ("담당자 칸", "short", [("cmp.yaml", "    tools: excel", "    tools: excel\n    담당자: 누구")],
     "S01", "오류", "cmp.yaml", 4, 1, "인명은 저장하지 않는다"),
    ("key 형식", "short", [("cmp.yaml", "key: cmp-meanline", "key: cmp_meanline")],
     "S02", "오류", "cmp.yaml", 4, 1, "영문 소문자·숫자·하이픈"),
    ("계약 판 두 자리", "short", [("perf.yaml", "version: 0.1.0", "version: 0.1")],
     "S02", "오류", "perf.yaml", 13, 1, "계약 판은 세 자리"),
    ("전달 방법 선택지 밖", "short", [("cmp.yaml", "transfer: 수기", "transfer: 이메일")],
     "S02", "오류", "cmp.yaml", 8, 1, "'이메일' 는 선택지 밖"),
    ("빌드 칸을 적음", "short", [("cmp.yaml", "    tools: excel", "    tools: excel\n    consumes: if-cycle-dp")],
     "S04", "오류", "cmp.yaml", 7, 1, "빌드가 계산하는 칸"),
    ("참조 오타", "short", [("cmp.yaml", "{interface: if-cycle-dp,", "{interface: if-cycle-db,")],
     "R01", "오류", "cmp.yaml", 7, 1, "혹시 if-cycle-dp ?"),
    ("자리 틀림 (계약 자리에 단계)", "short", [("perf.yaml", "    inputs: if-cmp-map", "    inputs: cmp-meanline")],
     "R01", "오류", "perf.yaml", 7, 1, "단계 — 계약 자리가 아니다"),
    ("key 중복 (다른 파일)", "short", [("cmp.yaml", "  - key: if-cmp-map", "  - key: if-cycle-dp")],
     "R02", "오류", "perf.yaml", 11, 1, "가 이미 cmp.yaml 12행에 있다"),
    ("단위 누락", "short", [("perf.yaml", "W2:   kg/s | 압축기 입구 유량", "W2:   {label: 압축기 입구 유량}")],
     "U01", "오류", "perf.yaml", 15, 1, "number 항목에 단위가 없다"),
    ("단위 대소문자", "short", [("perf.yaml", "Tt4:  K    |", "Tt4:  k    |")],
     "U02", "오류", "perf.yaml", 17, 1, "대소문자만 다르다 — K"),
    ("루프 선언 빠뜨림 → 순환", "short", [("cmp.yaml", "loops:", None)],
     "F01", "오류", "cmp.yaml", 4, 1, "loops 에 back_from: perf-cycle, back_to: cmp-meanline (추정)"),
    ("만드는 단계 둘", "short", [("perf.yaml", "    outputs: if-cycle-dp", "    outputs: if-cycle-dp, if-cmp-map")],
     "D01", "오류", "cmp.yaml", 12, 1, "만드는 단계가 둘 이상: cmp-meanline, perf-cycle"),
    ("monitor 오타", "short", [("cmp.yaml", "monitor: if-cmp-map.surge_margin", "monitor: if-cmp-map.surge_margn")],
     "L05", "오류", "cmp.yaml", 27, 1, "혹시 surge_margin ?"),
    ("첫 바퀴 값 없음", "short", [("cmp.yaml", "    initial: 첫 바퀴는 맵 없이 설계점 효율 가정값\n", "")],
     "L07", "경고", "cmp.yaml", 21, 0, "첫 바퀴 값의 출처(initial)가 없다"),
    ("인명 메모", "short", [("cmp.yaml", "    tools: excel", "    tools: excel\n    note: 홍길동 책임 확인 필요")],
     "P01", "경고", "cmp.yaml", 7, 0, "인명으로 보이는 표기 (값은 옮기지 않음)"),
    ("struct ref 오타", "textbook", [("cmp.yaml", "ref: MapPoint", "ref: MapPiont")],
     "C03", "오류", "cmp.yaml", 67, 1, "혹시 MapPoint ?"),
    ("루프 방향 뒤바뀜", "textbook", [("perf.yaml", "back_from: perf-offdesign", "back_from: cmp-meanline"),
                                    ("perf.yaml", "back_to: cmp-meanline ", "back_to: perf-offdesign ")],
     "F01", "오류", "cmp.yaml", 5, 1, "루프 'loop-cmp-match' 의 back_from/back_to 가 뒤바뀐 것 같다"),
    ("YAML 1.1 함정 (yes/no·0.1) — 오류 아님", "short", [("cmp.yaml", "values: [1D 상관식, 3D CFD, 시험]", "values: [yes, no, 1.10]")],
     "", "", "", 0, 0, ""),
    ("메모장 ANSI(cp949) 저장", "short", [],
     "Y01", "경고", "perf.yaml", 0, 0, "UTF-8 이 아니다 (ANSI/cp949 로 읽음)"),
]
LINE = re.compile(r"\[(오류|경고|참고) ([A-Z]\d\d)\] (\S+)(?: (\d+)행)?  ")


@pytest.mark.parametrize("name, src, edits, code, level, fname, line, rc_want, frag", CASES, ids=[c[0] for c in CASES])
def test_mistake(tmp_path, name, src, edits, code, level, fname, line, rc_want, frag):
    d = copy_example(tmp_path, src, state=False)
    for f, a, b in edits:
        edit(d / f, a, b)
    if code == "Y01":
        t = (d / "perf.yaml").read_text(encoding="utf-8")
        (d / "perf.yaml").write_bytes(t.encode("cp949", errors="replace"))
    cats = catalogs_or_none() if src == "textbook" else None
    rc, out = run_cli(["check", d] + (["--catalog", *cats] if cats else []))
    assert rc == rc_want, out
    if not code:
        assert "[오류" not in out, out
        return
    lines = out.splitlines()
    idx = next(i for i, ln in enumerate(lines) if LINE.match(ln) and LINE.match(ln).group(2) == code)
    mt = LINE.match(lines[idx])
    assert (mt.group(1), mt.group(3), int(mt.group(4) or 0)) == (level, fname, line), lines[idx]
    hint = lines[idx + 1] if idx + 1 < len(lines) and lines[idx + 1].strip().startswith("→") else ""
    assert frag in lines[idx] + hint, (lines[idx], hint)


def test_case_count():
    assert len(CASES) == 23


# 23종 밖 — 독립 검증(2026-10-20)이 찾은 조용한 실수. 예전에는 엉뚱한 안내(Y03 '% @ ` 기호')이거나 값이 조용히 사라졌다.
# 값 사이 탭: 메모장에서 칸·주석을 맞추려고 Tab 을 누르거나 엑셀 표를 붙여 넣으면 생긴다 (화면에서는 띄어쓰기처럼 보인다)
TAB_CASES = [
    ("콜론 뒤 (항목 한 줄)", "perf.yaml", "W2:   kg/s | 압축기 입구 유량", "W2:\tkg/s | 압축기 입구 유량", 15),
    ("콜론 뒤 (label)", "perf.yaml", "    label: 설계점 사이클 해석", "    label:\t탈설계점 해석", 5),
    ("주석 앞", "perf.yaml", "    outputs: if-cycle-dp", "    outputs: if-cycle-dp\t# 메모", 8),
    ("설명 안 ('|' 뒤)", "perf.yaml", "PR_c: 1    | 압축기 압력비", "PR_c: 1    |\t압축기 압력비", 16),
    ("'-' 뒤", "cmp.yaml", "      - {interface: if-cycle-dp, transfer: 수기}", "      -\t{interface: if-cycle-dp, transfer: 수기}", 8),
    ("줄 끝 (보이지 않음)", "cmp.yaml", "    tools: excel", "    tools: excel\t", 6),
]


@pytest.mark.parametrize("name, fname, a, b, line", TAB_CASES, ids=[c[0] for c in TAB_CASES])
def test_tab_between_values(tmp_path, name, fname, a, b, line):
    """들여쓰기가 아닌 자리의 탭도 Y02 — 그 줄을 가리키고 탭 자리를 <탭> 으로 보인다 (Y03 '% @ ` 기호' 안내가 아니다)."""
    d = copy_example(tmp_path, "short", state=False)
    edit(d / fname, a, b)
    rc, out = run_cli(["check", d])
    assert rc == 1, out
    first = next(ln for ln in out.splitlines() if LINE.match(ln))
    mt = LINE.match(first)
    assert (mt.group(1), mt.group(2), mt.group(3), int(mt.group(4) or 0)) == ("오류", "Y02", fname, line), first
    assert "값 사이에 탭 문자" in first and "<탭>" in first, first
    assert "탭 대신 스페이스로" in out and "Y03" not in out and "퍼센트" not in out, out


def test_tabs_found_all_at_once(tmp_path):
    """탭은 눈에 안 보이므로 한 번에 다 알린다 (줄마다 check 를 다시 누르지 않게). 따옴표·주석 안의 탭은 YAML 이 받는다 — 오류 아님."""
    d = copy_example(tmp_path, "short", state=False)
    edit(d / "perf.yaml", "W2:   kg/s", "W2:\tkg/s")
    edit(d / "perf.yaml", "Tt4:  K    |", "Tt4:  K\t|")
    edit(d / "perf.yaml", "    label: 설계점 사이클 해석", "    label: '설계점\t사이클 해석'   # 메모\t메모")
    rc, out = run_cli(["check", d])
    assert rc == 1
    hits = [(m.group(2), int(m.group(4))) for m in map(LINE.match, out.splitlines()) if m]
    assert hits == [("Y02", 15), ("Y02", 17)], out


def test_comma_inside_braces_is_not_lost(tmp_path):
    """{ } 한 줄 안에서 쉼표는 칸을 나눈다 — 'formats: pdf, docx' 의 docx·'maximum: 1,000' 의 000 이 '값 없는 칸' 이 된다.
    예전에는 빈 칸으로 조용히 버려 값을 잃었다 (오류 0) → 이제 S01 + { } 안 목록은 [a, b] 안내."""
    d = copy_example(tmp_path, "short", state=False)
    edit(d / "cmp.yaml", "map_file:     file:csv | 맵 파일 (속도선별 수정유량·압력비·효율)",
         "map_file:     {type: file, formats: pdf, docx, label: 보고서}")
    edit(d / "perf.yaml", "BPR:  1    | 바이패스비 | 선택", "BPR:  {unit: 1, minimum: 0, maximum: 1,000}")
    edit(d / "_plan.yaml", "{key: perf, label: 성능}", "{key: perf, label: 성능, related_parts: COOL, SAS}")
    rc, out = run_cli(["check", d])
    assert rc == 1
    s01 = [ln for ln in out.splitlines() if "[오류 S01]" in ln]
    assert len(s01) == 3, out
    for bad in ("'docx'", "'000'", "'SAS'"):
        assert any(bad in ln for ln in s01), (bad, out)
    assert out.count("{ } 안의 목록은 [a, b]") == 3, out
    # 고친 꼴은 통과 — { } 안에서 목록은 [a, b], 숫자에 천 단위 쉼표 없이
    edit(d / "cmp.yaml", "formats: pdf, docx,", "formats: [pdf, docx],")
    edit(d / "perf.yaml", "maximum: 1,000}", "maximum: 1000}")
    edit(d / "_plan.yaml", "related_parts: COOL, SAS}", "related_parts: [COOL, SAS]}")
    rc, out = run_cli(["check", d])
    assert "[오류" not in out, out


def test_enum_short_form_splits_on_comma(tmp_path):
    """한 줄 항목 'enum:A, B, C' 도 선택지 셋 (file: 처럼 ',' 와 '/' 둘 다로 나눈다) — 예전에는 값 하나 '1D, CFD, 시험' 으로 조용히 들어갔다."""
    import json

    d = copy_example(tmp_path, "short", state=False)
    edit(d / "perf.yaml", "      BPR:  1    | 바이패스비 | 선택\n",
         "      BPR:  1    | 바이패스비 | 선택\n      how:  enum:1D, CFD, 시험 | 계산 방법\n      src:  enum:A/B, C | 출처\n")
    out_dir = tmp_path / "out"
    rc, out = run_cli(["build", d, "--out", out_dir])
    assert rc == 0, out
    canon = json.loads((out_dir / "canonical.json").read_text(encoding="utf-8"))
    items = {it["name"]: it for i in canon["interfaces"] if i["key"] == "if-cycle-dp" for it in i["items"]}
    assert items["how"]["values"] == ["1D", "CFD", "시험"]
    assert items["src"]["values"] == ["A", "B", "C"]
