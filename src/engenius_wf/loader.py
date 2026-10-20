"""검사 1층: 읽기 — 엄격 YAML, 모든 값을 글자로.

yaml.BaseLoader 를 쓴다: yes/no/0.1/1.10 을 바꾸지 않고 글자 그대로 (YAML 1.1 함정 원천 차단). 참/거짓·정수는 스키마상
그 형인 칸에서만 normalize 가 바꾼다. 묶음·목록은 행 번호를 품는 LDict·LList 로 읽어 모든 메시지가 파일 행을 가리킨다.
코드: Y01 cp949(ANSI) 저장(경고) · Y02 탭(들여쓰기·값 사이·주석 앞)·전각 공백 · Y03 YAML 문법(한국어 번역) · Y04 같은 칸 두 번 · Y05 둥근 따옴표(경고).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from engenius_wf.report import Report


class LDict(dict):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.line = 0
        self.klines: dict = {}


class LList(list):
    def __init__(self, *a):
        super().__init__(*a)
        self.line = 0
        self.ilines: list = []


class _Loader(yaml.BaseLoader):          # BaseLoader: yes/no/0.1/1.10 를 바꾸지 않고 글자 그대로 (YAML 1.1 함정 원천 차단)
    pass


DUP_HINT = "YAML 은 뒤의 것으로 조용히 덮어쓴다 — 하나로 합치거나 지우세요"
# 목록 항목의 머리 칸(key·name)이 같은 묶음 안에 두 번 = 대개 새 단계·계약·루프·묶음 앞의 '- ' 를 빠뜨린 것
NEW_ITEM_HINT = "새 단계·계약·루프(또는 묶음)를 적은 것이면 그 항목 첫 줄(key: 또는 name:) 앞에 '- ' 를 붙인다 — 같은 칸을 두 번 적은 것이면 하나로 합친다"


def _map(loader, node):
    m = LDict()
    m.line = node.start_mark.line + 1
    dups = []
    for kn, vn in node.value:
        kl = kn.start_mark.line + 1
        k = kn.value.strip() if isinstance(kn, yaml.ScalarNode) else str(kn)
        if k in m:
            dups.append((kl, k, m.klines[k]))
        m[k] = loader.construct_object(vn, deep=True)
        m.klines[k] = kl
    new_item = any(k in ("key", "name") for _, k, _ in dups)
    for kl, k, first in dups:
        loader.dups.append((kl, f"'{k}' 가 같은 묶음 안에 두 번 (앞은 {first}행)", NEW_ITEM_HINT if new_item else DUP_HINT))
    return m


def _seq(loader, node):
    s = LList()
    s.line = node.start_mark.line + 1
    for it in node.value:
        s.append(loader.construct_object(it, deep=True))
        s.ilines.append(it.start_mark.line + 1)
    return s


_Loader.add_constructor("tag:yaml.org,2002:map", _map)
_Loader.add_constructor("tag:yaml.org,2002:seq", _seq)

# PyYAML 영문 오류 → (한국어 설명, 고치는 법)
YAML_HINTS = [
    ("mapping values are not allowed", "값 안에 ': '(콜론+공백)이 있다", "설명에 콜론을 쓰려면 값 전체를 큰따옴표로: \"kg/s | 유량: 입구\""),
    ("cannot start any token", "값의 첫 글자로 쓸 수 없는 기호 (% @ ` 등)", "퍼센트는 '퍼센트' 로 쓰거나 값 전체를 큰따옴표로"),
    ("sequence entries are not allowed", "값이 '- ' 로 시작한다", "무차원은 '-' 대신 1"),
    ("could not find expected ':'", "':' 가 빠졌거나 들여쓰기가 어긋났다", "위아래 줄과 들여쓰기 칸 수를 맞추세요"),
    ("did not find expected key", "들여쓰기가 위 줄과 맞지 않는다", "같은 수준의 칸은 같은 칸에서 시작"),
    ("expected ',' or '}'", "{ … } 안에 쉼표·콜론이 든 값이 있다", "그 값만 큰따옴표로 감싸세요: {label: \"a, b\"}"),
    ("expected ',' or ']'", "[ … ] 안에 쉼표가 든 값이 있다", "그 값만 큰따옴표로 감싸세요"),
    ("expected <block end>", "들여쓰기가 맞지 않는다 (또는 따옴표 뒤에 글자가 더 있음)", "값의 일부만 따옴표로 감쌀 수 없다 — 값 전체를"),
    ("found unexpected end of stream", "따옴표가 닫히지 않았다", "여는·닫는 따옴표 짝 확인"),
    ("while scanning a quoted scalar", "따옴표가 닫히지 않았다", "여는·닫는 따옴표 짝 확인"),
]


def read_yaml(path: Path, rep: Report):
    """YAML 파일 하나 → LDict (문제가 있으면 rep 에 남기고 None)."""
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp949", errors="replace")
        rep.warn("Y01", path.name, "UTF-8 이 아니다 (ANSI/cp949 로 읽음)", "메모장 '다른 이름으로 저장' → 인코딩 UTF-8")
    return read_yaml_text(text, path.name, rep)


TAB_HINT = "탭 대신 스페이스로 — 칸·주석을 맞추려고 Tab 키를 눌렀거나 엑셀 표를 붙여 넣으면 생긴다 (화면에서는 띄어쓰기처럼 보인다)"


def tab_stops(text: str) -> list[int]:
    """PyYAML 이 걸려 넘어지는 탭의 행 — 들여쓰기만이 아니라 콜론 뒤·주석 앞·값 사이·'- ' 자리도 ('found character \\t that cannot
    start any token' — 그대로 두면 Y03 '% @ ` 같은 기호' 라는 엉뚱한 안내가 된다). 따옴표 안·주석 안·블록 글자(|·>) 안의 탭은 YAML 이
    받으므로 걸리지 않는다. 걸린 탭을 스페이스로 바꿔 가며 다시 훑어 전부 찾는다 (한 번에 다 알린다 — 탭은 눈에 안 보인다)."""
    if "\t" not in text:
        return []
    found = []
    for _ in range(text.count("\t")):
        try:
            for _tok in yaml.scan(text, Loader=_Loader):
                pass
            break
        except yaml.MarkedYAMLError as e:
            m = e.problem_mark
            if m is None or "'\\t'" not in str(e.problem or "") or text[m.index: m.index + 1] != "\t":
                break                                  # 탭이 아닌 문법 오류 — 본 읽기(Y03)가 알린다
            found.append(m.line + 1)
            text = text[: m.index] + " " + text[m.index + 1:]
    return sorted(set(found))


def read_yaml_text(text: str, name: str, rep: Report):
    """YAML 글자 → LDict (문제가 있으면 rep 에 남기고 None). name = 메시지에 쓰는 파일 이름. read_yaml 이 파일을 디코드한 뒤 부른다."""
    bad = False
    lines = text.splitlines()
    lead_tabs = set()
    for i, ln in enumerate(lines, 1):
        lead = ln[: len(ln) - len(ln.lstrip(" \t　"))]
        if "\t" in lead:
            rep.err("Y02", (name, i), "들여쓰기에 탭 문자", "탭 대신 스페이스로")
            lead_tabs.add(i)
            bad = True
        if "　" in ln:
            rep.err("Y02", (name, i), "전각 공백(한글 입력 중 스페이스)", "한/영 키를 영문으로 바꾸고 스페이스를 다시")
            bad = True
        if any(q in ln for q in "“”‘’"):
            rep.warn("Y05", (name, i), "둥근 따옴표(“ ” ‘ ’) — YAML 은 곧은 따옴표(\" ')만 안다")
    for i in tab_stops(text):
        if i not in lead_tabs and 0 < i <= len(lines):
            src = lines[i - 1].strip(" ").replace("\t", "<탭>")        # 줄 끝 탭도 보이게 (공백만 뗀다)
            rep.err("Y02", (name, i), f"값 사이에 탭 문자 (콜론 뒤·주석 앞·'-' 뒤 등):  {src}", TAB_HINT)
            bad = True
    if bad:
        return None
    loader = _Loader(text)
    loader.dups = []
    try:
        data = loader.get_single_data()
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        line = mark.line + 1 if mark else 0
        context = getattr(e, "context", "") or ""
        prob = f"{context} {getattr(e, 'problem', '') or ''}"
        msg, hint = "YAML 문법 오류", str(getattr(e, "problem", e))
        for key, m_, h in YAML_HINTS:
            if key in prob:
                msg, hint = m_, h
                break
        lines = text.splitlines()
        cmark = getattr(e, "context_mark", None)
        if "while scanning a simple key" in context and cmark is not None:
            line = cmark.line + 1                      # 원인은 칸 이름이 시작된 줄 — problem_mark 는 멈춘 다음 줄을 가리킨다
            src = lines[line - 1] if 0 < line <= len(lines) else ""
            if "：" in src:
                msg, hint = "전각 콜론(：) — YAML 은 영문 콜론(:)만 안다", "전각 콜론을 영문 콜론으로 — 한/영 키를 영문으로 바꾸고 다시 (콜론 뒤에는 공백 한 칸)"
            elif re.match(r"^\s*(-\s+)?[^\s:#]+:\S", src):
                msg, hint = "콜론 뒤에 공백이 없다", "'칸: 값' 처럼 콜론 뒤에 공백 한 칸 (예 tools: cfx)"
        src = lines[line - 1].strip() if 0 < line <= len(lines) else ""
        rep.err("Y03", (name, line), f"{msg}:  {src}", hint)
        return None
    finally:
        loader.dispose()
    for line, m_, h in loader.dups:
        rep.err("Y04", (name, line), m_, h)
    if loader.dups:
        return None
    if data is None or data == "":
        return LDict()
    if not isinstance(data, dict):
        rep.err("S02", name, "파일 맨 위는 'steps:' 같은 칸 이름이어야 한다")
        return None
    return data
