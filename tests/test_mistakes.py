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
