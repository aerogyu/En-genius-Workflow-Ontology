"""작성용 JSON Schema — VS Code(Red Hat YAML 확장 = yaml-language-server)에서 워크플로 YAML 을 쓰는 동안 자동완성·빨간 줄·설명.

빌드의 모양 검사(generated/wfo_file.schema.json)는 normalize 가 짧은 표기를 펼친 **뒤** 의 정본 모양을 본다. 사람이 손으로 쓰는
짧은 표기(tools: excel · 'a, b' 쉼표 목록 · 계약 항목 한 줄 '단위 | 설명 [| 선택]' · transfer 별칭 '수기' · 참거짓 낱말 '예/o/x')를
그 스키마에 대면 틀렸다고 나온다. 이 스키마(generated/wfo_authoring.schema.json)는 펼치기 **전** — 편집기가 읽은 그대로를 본다.

원칙 (tests/test_authoring.py 가 로더와 묶는다)
  ① 로더(loader → normalize → check_shape)가 받는 것은 받는다 — 거짓 빨간 줄 0.
     yaml-language-server 는 YAML 1.2 로 읽는다 ('version: 0.1' → 숫자, '1.10' → 숫자 1.1, 'true' → 참거짓, 'yes'·'o' → 글자).
     로더는 모든 값을 글자로 읽으므로 칸마다 '그 칸 형식에 맞는 글자가 YAML 1.2 에서 숫자·참거짓이 될 수 있으면' 그 형도 받는다.
     빈칸(null·'')은 로더가 '안 적은 것' 으로 넘기므로 필수가 아닌 칸에서는 받는다.
  ② 로더가 모양 단계에서 막는 것은 막는다 — S01 모르는 칸·담당자 칸, S02 형식(key·판·TOOL ID·확장자)·선택지 밖·형,
     S03 필수 칸 없음, S04 빌드 칸, 계약 항목 한 줄의 '|' 규칙(S02 · 첫칸이 비면 U01).
  ③ 참조 칸(tools·inputs·after·back_to …)은 key 형식만 본다 — 형식이 틀린 key 는 아무것도 가리킬 수 없다 (check 에서 R01 이 반드시 난다).
     있는지(R01)·중복(R02)·plan 한 번(R04)·단위(U)·흐름(F)·루프(L)·판(V)·레지스트리(G)·인명 메모(P)는 check.bat 몫.
  알려진 차이 (docs/02 1-1장) — 편집기가 더 엄격: 빈 값이라도 모르는 칸·빌드 칸·담당자 칸, 필수 칸에 글자로 쓴 'null'·'~',
  사내 오버레이에서 더한 전달 방법 별칭·참거짓 낱말. 편집기가 더 너그러움: YAML 1.2 가 숫자·참거짓으로 바꾼 값은 원래 글자를 모른다
  (예: 'key: True' 는 빨간 줄이 없지만 check 는 S02).
파일 하나에 어느 절이 와도 된다 — 로더가 모든 파일을 같은 WorkflowFile 모양으로 읽고, plan 이 전체에서 한 번인지는 파일을 합친 뒤(R04)
본다 → 스키마 하나 (_plan.yaml 용·분야 파일용으로 나누면 빌드는 받는데 편집기만 빨간 줄인 경우가 생긴다).

입력: LinkML 스키마의 클래스·슬롯 모형(schema_gen.authoring_model — linkml 은 거기서만 import) + config/rules.yaml(전달 방법 별칭·
참거짓 낱말) + config/units.yaml(단위 — 자동완성 후보·설명에만, 검사하지 않음). 저장소 config 기본값만 쓴다 (사내 오버레이는 넣지
않는다 — 드리프트 감시가 사내에서 흔들리지 않게). 명령: python -m engenius_wf schema (--check 가 드리프트 감시).
draft-07 (yaml-language-server 가 안정적으로 지원). 비표준 키워드 markdownDescription·patternErrorMessage·errorMessage·deprecationMessage·
doNotSuggest·defaultSnippets·enumDescriptions 는 VS Code 의 JSON/YAML 언어 서버가 읽고 다른 검사기(jsonschema)는 무시한다.
정규식은 JS(ECMA-262)와 파이썬 re 가 같은 뜻으로 읽는 것만 쓴다 ((?i) 같은 인라인 깃발 없음). 외부 참조 0 — $ref 는 전부 '#/definitions/…'.
"""

from __future__ import annotations

import re

from engenius_wf.checks import KEY_HINT, PERSON_FIELDS
from engenius_wf.model import NESTED
from engenius_wf.normalize import FLOAT_TEXT, INT_TEXT, OPTIONAL_WORDS, SHORT_TYPES

DRAFT07 = "http://json-schema.org/draft-07/schema#"
ROOT = "WorkflowFile"
DEF = "#/definitions/"
COMMENT = ("자동 생성 — 직접 고치지 말 것. 원본: schema/wfo.yaml + config/rules.yaml·units.yaml (저장소 기본값), "
           "명령: python -m engenius_wf schema. 쓰는 법: docs/02_작성안내.md 1-1장")

# YAML 1.2 core schema 가 참거짓·숫자로 읽는 글자 본보기 — 칸 형식(패턴)이 이 중 하나라도 받으면 그 형도 받는다 (원칙 ①)
YAML12_BOOL_TEXTS = ("true", "True", "TRUE", "false", "False", "FALSE")
YAML12_NUMBER_TEXTS = ("0", "1", "12", "007", "+1", "-1", "1.5", "1.", ".5", "1e3", "1E-3", "-1.5e+3", "0x1f", "0o17",
                       ".inf", "-.inf", ".nan")
FREE = ["string", "number", "boolean"]                 # 자유 글자 칸 — YAML 1.2 가 무엇으로 읽든 로더는 글자로 받는다

KO = {"Workflow": "워크플로", "Discipline": "분야", "Component": "구성품", "ToolRef": "툴", "Step": "단계", "Interface": "계약",
      "Loop": "루프", "Record": "묶음", "InputBinding": "받는 데이터 한 건", "OutputBinding": "내놓는 데이터 한 건",
      "InterfaceItem": "계약 항목", ROOT: "YAML 파일 하나"}
MULTI_NOTE = "여럿이면 `a, b` 처럼 쉼표로, 또는 목록(`- a`)."

# 칸 설명에 덧붙이는 작성 안내 (markdown). 키 = (클래스, 칸) 또는 (None, 칸 — 모든 클래스). <<이름>> 은 설정에서 채운다.
NOTES = {
    (None, "key"): "모든 파일·종류에서 하나뿐 (중복은 check 의 R02).",
    (None, "renamed_from"): "key 를 바꿀 때 **첫 build 전에** 새 key 아래 적는다 (G03 승계 · 빌드 뒤에 적으면 G06). " + MULTI_NOTE,
    (None, "label"): "한국어 이름.",
    (None, "note"): "인명·직급·내선 번호는 적지 않는다 (check 의 P01 경고).",
    (ROOT, "discipline"): "분야 파일 맨 위 한 줄 (예 `discipline: perf`) — 이 파일의 단계·계약의 분야.",
    (ROOT, "plan"): "전체 파일 중 **한 번만** (보통 `_plan.yaml` — 없거나 둘이면 check 의 R04).",
    (ROOT, "disciplines"): "보통 `_plan.yaml` 에. 한 줄 `- {key: perf, label: 성능}`.",
    (ROOT, "components"): "보통 `_plan.yaml` 에. 한 줄 `- {key: hpc, label: 고압압축기, broader: compressor}`.",
    (ROOT, "tools"): "보통 `_plan.yaml` 에. 한 줄 `- {key: gasturb, label: GasTurb}` — tool_id 는 link-tools 후보를 보고 사람이 적는다.",
    (ROOT, "steps"): "단계 목록 — 새 단계는 `- key: …` 로 시작한다.",
    (ROOT, "interfaces"): "계약 목록 — 내놓는 분야의 파일에 둔다.",
    (ROOT, "loops"): "루프 목록 — back_from 단계가 있는 파일에 둔다.",
    ("Workflow", "version"): "워크플로 판 — 자유 글자 (예 `0.1`). 계약 판과 달리 세 자리가 아니어도 된다.",
    ("Discipline", "related_parts"): "사내 파트 약칭 (Tool 온톨로지 툴사용으로 좁힐 때만). " + MULTI_NOTE,
    ("Component", "broader"): "상위 구성품 key.",
    ("ToolRef", "tool_id"): "`TOOL-000123` 꼴 — link-tools 후보 CSV 를 보고 **사람이** 적는다 (빌드는 채우지 않는다).",
    ("ToolRef", "label_at_link"): "tool_id 를 적을 때의 Tool 온톨로지 이름 (바뀌면 check 의 X03).",
    ("ToolRef", "not_in_survey"): "조사 대상이 아닌 이유 (적으면 X04·X05 안내를 끈다).",
    ("Step", "tools"): "툴 key (`_plan.yaml` tools 의 key). " + MULTI_NOTE,
    ("Step", "inputs"): ("받는 계약 — `inputs: if-a, if-b` (key 만) · 목록 `- {interface: if-a, transfer: 수기}` · "
                         "한 건이면 `{interface: if-a, transfer: 수기}` 하나도 된다. 앞 단계는 빌드가 계산한다."),
    ("Step", "outputs"): "내놓는 계약 — `outputs: if-a` (key 만) 또는 `- {interface: if-a, format: csv}`. 계약 하나를 만드는 단계는 하나 (D01).",
    ("Step", "after"): "데이터 없이 **순서만** 있는 앞 단계 key — 데이터로 이어진 선후는 빌드가 inputs 로 계산하니 적지 않는다. " + MULTI_NOTE,
    ("Step", "part_of"): "이 단계가 하위 단계일 때 상위 단계 key (상위 단계도 steps 에 한 항목으로 둔다).",
    ("Step", "components"): "구성품 key. " + MULTI_NOTE,
    ("Step", "discipline"): "파일 머리 `discipline:` 과 다를 때만.",
    ("Step", "when"): "조건 메모 (계산하지 않는다).",
    ("InputBinding", "interface"): "받는 계약 key.",
    ("OutputBinding", "interface"): "내놓는 계약 key.",
    ("InputBinding", "transfer"): "정식 값 또는 짧은 별칭 (<<transfer_aliases>>). 수기 구간은 그림의 ✋ · 질의 Q2 에 나온다.",
    ("InputBinding", "tool"): "이 데이터를 받는 툴 key — 그 단계 tools 중 하나 (아니면 check 의 D05).",
    ("OutputBinding", "tool"): "이 데이터를 내놓는 툴 key — 그 단계 tools 중 하나.",
    (None, "format"): "실제로 주고받는 파일 확장자 — 소문자·점 없이 (예 `csv`).",
    ("Interface", "version"): "계약 판 세 자리 (예 `0.1.0`). 동결(release) 뒤 계약을 고치면 올린다 (check 의 V02·V03 이 올릴 판을 알려 준다).",
    ("Interface", "discipline"): "파일 머리 `discipline:` 과 다를 때만.",
    ("Interface", "records"): "계약 안의 묶음 (표 모양 데이터) — 항목에서 `struct:묶음이름[]` 로 품는다.",
    ("Interface", "external"): "적으면 check 의 D02(만드는 단계 없음) 경고를 끈다.",
    ("Interface", "deliverable"): "적으면 check 의 D03(받는 단계 없음) 경고를 끈다.",
    ("Record", "name"): "묶음 이름 — 대문자로 시작 (예 `MapPoint`). 항목에서 `struct:MapPoint` 로 부른다.",
    ("InterfaceItem", "name"): "JSON 키 — 영문으로 시작, 영문·숫자·`_` (예 `W2`, `PR_c`). 한 줄 형식에서는 칸 이름이 곧 name.",
    ("InterfaceItem", "unit"): "number·integer 는 필수, 무차원은 `1`. 목록에 없는 단위는 check 의 U02 (편집기는 단위를 검사하지 않는다).\n\n<<units>>",
    ("InterfaceItem", "values"): "type=enum 의 선택지 — 늘 글자로 읽는다 (`[yes, no, 1.10]` 도 글자). " + MULTI_NOTE,
    ("InterfaceItem", "formats"): "type=file 의 확장자 — 소문자·점 없이 (`csv`, `cas.h5`). " + MULTI_NOTE,
    ("InterfaceItem", "ref"): "한 줄 형식으로는 `struct:MapPoint` (목록이면 `struct:MapPoint[]`).",
    ("InterfaceItem", "min_items"): "목록(list) 항목의 최소 개수.",
    ("Loop", "back_from"): "루프 **끝** 단계 key — 여기서 되돌아간다.",
    ("Loop", "back_to"): "루프 **처음** 단계 key — 여기로 되돌아온다.",
    ("Loop", "until"): "수렴 조건 메모 (판정은 엔지니어).",
    ("Loop", "initial"): "첫 바퀴 값의 출처 메모 (예 '설계점 값, 차이 0 가정') — 없으면 check 의 L07 경고.",
    ("Loop", "include"): "경로 밖이지만 매 반복 같이 도는 곁가지 단계 key. " + MULTI_NOTE,
    ("Loop", "monitor"): "수렴을 지켜보는 항목 `계약key.항목` (예 `if-cmp-map.surge_margin`). " + MULTI_NOTE,
}

# 새 항목 골격 (VS Code 자동완성 목록의 '스니펫'). ${n:값} = 탭으로 옮겨 다니며 고칠 자리
SNIPPETS = {
    ROOT: [
        {"label": "_plan.yaml 골격 (워크플로 머리·분야·툴)", "description": "전체에서 한 번 — 보통 _plan.yaml",
         "body": {"plan": {"key": "${1:concept-design}", "label": "${2:개념설계 워크플로}", "phase": "${3|개념설계,기본설계,상세설계|}",
                           "version": "${4:0.1}"},
                  "disciplines": [{"key": "${5:perf}", "label": "${6:성능}"}],
                  "tools": [{"key": "${7:gasturb}", "label": "${8:GasTurb}"}]}},
        {"label": "분야 파일 골격 (단계·계약)", "description": "분야 하나 = 파일 하나",
         "body": {"discipline": "${1:perf}",
                  "steps": [{"key": "${2:perf-cycle}", "label": "${3:단계 이름}", "tools": "${4:gasturb}", "inputs": "${5:if-in}",
                             "outputs": "${6:if-out}"}],
                  "interfaces": [{"key": "${6:if-out}", "label": "${7:계약 이름}", "version": "0.1.0",
                                  "items": {"${8:W2}": "${9:kg/s} | ${10:설명}"}}]}},
    ],
    "Discipline": [{"label": "분야", "body": {"key": "${1:perf}", "label": "${2:성능}"}}],
    "Component": [{"label": "구성품", "body": {"key": "${1:hpc}", "label": "${2:고압압축기}"}}],
    "ToolRef": [{"label": "툴", "body": {"key": "${1:gasturb}", "label": "${2:GasTurb}"}}],
    "Step": [{"label": "단계", "description": "선후는 빌드가 inputs·outputs 로 계산한다",
              "body": {"key": "${1:perf-cycle}", "label": "${2:단계 이름}", "tools": "${3:gasturb}", "inputs": "${4:if-in}",
                       "outputs": "${5:if-out}"}}],
    "Interface": [{"label": "계약", "description": "항목 한 줄 = 이름: 단위 | 설명 [| 선택]",
                   "body": {"key": "${1:if-name}", "label": "${2:계약 이름}", "version": "${3:0.1.0}",
                            "items": {"${4:W2}": "${5:kg/s} | ${6:설명}"}}}],
    "Record": [{"label": "묶음", "body": {"name": "${1:MapPoint}", "label": "${2:묶음 이름}", "items": {"${3:W}": "${4:kg/s} | ${5:설명}"}}}],
    "Loop": [{"label": "루프", "description": "back_from = 끝(여기서), back_to = 처음(여기로)",
              "body": {"key": "${1:loop-name}", "label": "${2:루프 이름}", "back_from": "${3:cmp-meanline}", "back_to": "${4:perf-cycle}",
                       "until": "${5:수렴 조건 메모}", "initial": "${6:첫 바퀴 값의 출처}"}}],
}
ITEM_SNIPPETS = [
    {"label": "항목 한 줄 (숫자)", "body": {"${1:W2}": "${2:kg/s} | ${3:설명}"}},
    {"label": "항목 한 줄 (선택 항목)", "body": {"${1:BPR}": "${2:1} | ${3:설명} | 선택"}},
    {"label": "항목 긴 형식 (선택지)", "body": {"${1:source}": {"type": "enum", "values": ["${2:A}", "${3:B}"], "label": "${4:설명}"}}},
    {"label": "항목 긴 형식 (범위)", "body": {"${1:eta}": {"unit": "1", "label": "${2:효율}", "minimum": 0, "maximum": 1}}},
]


# --------------------------------------------------------------------------- 정규식 도우미
def _inner(pattern: str) -> str:
    """'^…$' → '…' (다른 식 안에 넣을 때)."""
    if not (pattern.startswith("^") and pattern.endswith("$")):
        raise ValueError(f"패턴은 ^…$ 로 감싼다: {pattern}")
    return pattern[1:-1]


def _js_escape(text: str) -> str:
    """JS 'u' 깃발 정규식에서도 맞는 이스케이프 — 문법 글자만 (re.escape 는 공백·하이픈도 이스케이프해 'u' 모드에서 틀린 식이 된다)."""
    return re.sub(r"([\\^$.*+?()\[\]{}|/])", r"\\\1", text)


def _any_case(word: str) -> str:
    """대소문자를 가리지 않는 글자 묶음 — JS 정규식에는 (?i) 인라인 깃발이 없다."""
    out = []
    for ch in word:
        lo, up = ch.lower(), ch.upper()
        out.append(f"[{_js_escape(lo)}{_js_escape(up)}]" if lo != up and len(lo) == len(up) == 1 else _js_escape(ch))
    return "".join(out)


def _admits(pattern: str, texts) -> bool:
    return any(re.search(pattern, t) for t in texts)


def _yaml12_types(pattern: str) -> list[str]:
    """그 칸 형식에 맞는 글자가 YAML 1.2 에서 숫자·참거짓이 될 수 있으면 그 형 (원칙 ①)."""
    return (["number"] if _admits(pattern, YAML12_NUMBER_TEXTS) else []) + \
           (["boolean"] if _admits(pattern, YAML12_BOOL_TEXTS) else [])


def comma_list(pattern: str) -> str:
    """'a, b' 쉼표 목록 — normalize.split 처럼 빈 조각은 버리고 조각마다 그 형식 (빈 목록도 받는다)."""
    p = f"(?:{_inner(pattern)})"
    return rf"^[\s,]*(?:{p}(?:\s*,[\s,]*{p})*)?[\s,]*$"


def short_item_pattern(formats_pattern: str, ref_pattern: str) -> str:
    """계약 항목 한 줄 '첫칸 | 설명 | 선택' — normalize.short_item 과 같은 규칙:
    첫칸은 비울 수 없다(U01 — '[]' 만 있어도 빈 것). 'file:'·'파일:'(대소문자 무시) 뒤 확장자는 [,/] 로 나눈 조각마다(앞뒤 공백은 뗀다)
    확장자 형식 — 빈 조각도 틀림 (S02). 'struct:' 뒤는 묶음 이름·계약 key 형식(원칙 ③). 그 밖의 첫칸(단위·int·text·enum:…)은 글자 아무거나
    (단위는 check 의 U02). '|' 는 두 번까지, 셋째 칸은 '선택' 만 (S02). 끝의 '[]' = 목록."""
    opt = "|".join(_js_escape(w) for w in OPTIONAL_WORDS)
    file_pfx = "(?:" + "|".join(_any_case(w) for w, (t, _) in SHORT_TYPES.items() if t == "file") + "):"
    struct_pfx = _any_case("struct") + ":"
    f = rf"\s*(?:{_inner(formats_pattern)})\s*"
    lst = r"\s*(?:\[\]\s*)?"
    first = (rf"\s*(?:{file_pfx}{f}(?:[,/]{f})*{lst}"
             rf"|{struct_pfx}\s*(?:{_inner(ref_pattern)})?{lst}"
             rf"|(?!{file_pfx}|{struct_pfx}|\[\]\s*(?:\||$))[^|\s][^|]*)")
    return rf"^{first}(?:\|[^|]*(?:\|\s*(?:{opt})?\s*)?)?$"


def int_text_pattern(minimum=None) -> str:
    """정수 칸의 글자 (normalize.INT_TEXT) — 하한 0·1 은 글자에서도 본다."""
    core = {None: INT_TEXT, 0: r"\+?\d+|-0+", 1: r"\+?0*[1-9]\d*"}.get(minimum, INT_TEXT)
    return rf"^\s*(?:{core})\s*$"


def float_text_pattern() -> str:
    return rf"^\s*(?:{FLOAT_TEXT})\s*$"


def bool_text_pattern(rules) -> str:
    """참거짓 칸의 글자 — config/rules.yaml true_words·false_words, 대소문자 무시 (normalize 와 같은 규칙)."""
    words = [str(w).lower() for w in list(rules["true_words"]) + list(rules["false_words"])]
    return rf"^\s*(?:{'|'.join(_any_case(w) for w in words)})\s*$"


# --------------------------------------------------------------------------- 형 묶음 도우미
def _types(branch) -> list[str]:
    t = branch.get("type")
    return [] if t is None else ([t] if isinstance(t, str) else list(t))


def _one(branches: list[dict]) -> dict:
    """여러 갈래 → anyOf (형만 있는 갈래는 하나로 합친다). 순서 = 오류 문구 우선순위 (언어 서버는 동점이면 앞 갈래의 문구를 보인다)."""
    out, pure, at = [], [], None
    for b in branches:
        if set(b) == {"type"}:
            if at is None:
                at = len(out)
                out.append(None)
            pure += [t for t in _types(b) if t not in pure]
        else:
            out.append(b)
    if at is not None:
        out[at] = {"type": pure[0] if len(pure) == 1 else pure}
    return out[0] if len(out) == 1 else {"anyOf": out}


def _optional(branches: list[dict]) -> list[dict]:
    """필수가 아닌 칸 — 빈칸(YAML 1.2 null, 따옴표 '')은 로더가 '안 적은 것' 으로 넘긴다."""
    takes_empty = any("string" in _types(b) and (not {"pattern", "enum", "minLength", "maxLength"} & set(b)
                                                 or ("pattern" in b and set(b) <= {"type", "pattern", "patternErrorMessage", "errorMessage"}
                                                     and re.search(b["pattern"], "")))
                      for b in branches)
    return list(branches) + [{"type": "null"}] + ([] if takes_empty else [{"type": "string", "maxLength": 0}])


def _pattern_branches(pattern: str, msg: str) -> list[dict]:
    b = [{"type": "string", "pattern": pattern, "patternErrorMessage": msg, "errorMessage": msg}]
    extra = _yaml12_types(pattern)
    return b + ([{"type": extra[0] if len(extra) == 1 else extra}] if extra else [])


def _md_plain(md: str) -> str:
    return re.sub(r"\*\*", "", md).replace("\n\n", " ").replace("\n", " ")


# --------------------------------------------------------------------------- 만들기
class _Builder:
    def __init__(self, model: dict, rules: dict, units: dict, unit_aliases: dict):
        self.cls, self.enums = model["classes"], model["enums"]
        self.rules, self.units, self.unit_aliases = rules, units, unit_aliases
        self.bool_pattern = bool_text_pattern(rules)
        tw = "·".join(f"`{str(w).lower()}`" for w in rules["true_words"])
        fw = "·".join(f"`{str(w).lower()}`" for w in rules["false_words"])
        self.bool_words_md = f"참 {tw} / 거짓 {fw}, 대소문자 무시"
        aliases = rules.get("transfer_aliases") or {}
        self.transfer_aliases = {str(k): str(v) for k, v in aliases.items()}
        self.manual = {str(v) for v in rules.get("manual_transfer_values") or []}
        self.fill = {"transfer_aliases": " · ".join(f"`{k}`→{v}" for k, v in self.transfer_aliases.items()),
                     "units": self.units_md()}
        self.reach = self.reachable()

    # 모형에서 읽기
    def reachable(self) -> list[str]:
        out, todo = [], [ROOT]
        while todo:
            c = todo.pop(0)
            if c in out:
                continue
            out.append(c)
            todo += [n for (owner, _), n in NESTED.items() if owner == c and n not in out]
        return out

    def id_pattern(self, cname: str) -> str:
        for s in self.cls[cname]["slots"].values():
            if s["identifier"]:
                return s["pattern"]
        raise ValueError(f"{cname}: 식별자 칸이 없다")

    def ref_targets(self, s) -> list[str]:
        rng = s["range"] or ""
        names = [r for r in rng.split("|") if r]
        return names if names and all(r in self.cls for r in names) else []

    # 설명
    def units_md(self) -> str:
        units = " ".join(f"`{u}`" for u in self.units)
        al = " · ".join(f"`{a}`→`{u}`" for a, u in self.unit_aliases.items())
        return f"단위 (config/units.yaml): {units}" + (f"  \n별칭: {al}" if al else "")

    def note(self, cname, sn) -> str:
        text = NOTES.get((cname, sn)) or NOTES.get((None, sn)) or ""
        for k, v in self.fill.items():
            text = text.replace(f"<<{k}>>", v)
        return text

    def doc(self, desc: str, *extra: str) -> dict:
        md = "\n\n".join(x for x in (desc, *extra) if x)
        return {"description": _md_plain(md), "markdownDescription": md}

    # 칸 하나
    def built(self, sn, s) -> dict:
        msg = f"'{sn}' 는 빌드가 계산하는 칸 — 적지 않는다 (check 의 S04)"
        return {**self.doc(s["description"], msg), "not": {}, "errorMessage": msg, "deprecationMessage": msg, "doNotSuggest": True}

    def scalar(self, cname, sn, s) -> tuple[list[dict], str]:
        """칸 값 하나의 갈래들 + 설명에 덧붙일 말."""
        rng = s["range"]
        targets = self.ref_targets(s)
        if rng in self.enums:
            vals = [v for v, _ in self.enums[rng]]
            descs = [d for _, d in self.enums[rng]]
            if rng == "TransferMethod":
                descs = [("Tool Agent 후보 (수기 구간)" if v in self.manual else d) for v, d in zip(vals, descs)]
                for a, v in self.transfer_aliases.items():
                    if a not in vals:
                        vals.append(a)
                        descs.append(f"= {v} (짧은 별칭)")
            br = {"type": "string", "enum": vals}
            if any(descs):
                br["enumDescriptions"] = descs
            return [br], "선택지: " + " · ".join(f"`{v}`" for v in vals)
        if rng == "boolean":
            msg = f"참/거짓 칸 — {self.bool_words_md.replace('`', '')} (check 의 S02)"
            return [{"type": "boolean"}, {"type": "string", "pattern": self.bool_pattern, "patternErrorMessage": msg,
                                          "errorMessage": msg}], "참/거짓 — " + self.bool_words_md
        if rng == "integer":
            m = s["minimum"]
            msg = "정수 칸" + (f" — {m} 이상" if m is not None else "") + " (check 의 S02)"
            b = {"type": "integer", "errorMessage": msg}
            if m is not None:
                b["minimum"] = m
            return [b, {"type": "string", "pattern": int_text_pattern(m), "patternErrorMessage": msg, "errorMessage": msg}], ""
        if rng == "float":
            msg = "숫자 칸 (check 의 S02)"
            return [{"type": "number", "errorMessage": msg},
                    {"type": "string", "pattern": float_text_pattern(), "patternErrorMessage": msg, "errorMessage": msg}], ""
        if targets:
            pats = []
            for t in targets:
                p = _inner(self.id_pattern(t))
                if p not in pats:
                    pats.append(p)
            pattern = f"^{pats[0]}$" if len(pats) == 1 else "^(?:" + "|".join(f"(?:{p})" for p in pats) + ")$"
            if len(targets) == 1:
                msg = f"형식이 틀림 — {KO[targets[0]]} key 는 {KEY_HINT['key']}. 그런 key 가 있는지는 check 가 본다 (R01)"
            else:
                msg = ("형식이 틀림 — " + " 또는 ".join(f"{KO[t]} {'이름' if t == 'Record' else 'key'}" for t in targets)
                       + f": {KEY_HINT['name']} / {KEY_HINT['key']}. 있는지는 check 가 본다")
            return _pattern_branches(pattern, msg), ""
        if s["pattern"]:
            hint = KEY_HINT.get(sn, f"규칙 {s['pattern']}")
            return _pattern_branches(s["pattern"], f"형식이 틀림 — {hint} (check 의 S02)"), ""
        if s["required"]:
            return [{"type": "string", "minLength": 1}, {"type": ["number", "boolean"]}], ""
        return [{"type": list(FREE)}], ""

    def multi_scalar(self, cname, sn, s) -> tuple[list[dict], str]:
        single, extra = self.scalar(cname, sn, s)
        if any("enum" in b for b in single):
            raise ValueError(f"{cname}.{sn}: 여러 값 선택지 칸은 작성용 스키마가 아직 모른다 — authoring.py 에 더한다")
        main = next((b for b in single if "pattern" in b), None)
        if main is None:                        # 자유 글자 목록 — 'a, b' 도 글자 하나로 받는다, 목록의 빈 줄('- ')은 글자 ''
            return [{"type": list(FREE)}, {"type": "array", "items": {"type": [*FREE, "null"]}}], extra
        msg = main["patternErrorMessage"] + " — 여럿이면 'a, b' 처럼 쉼표로, 또는 목록"
        return _pattern_branches(comma_list(main["pattern"]), msg) + [{"type": "array", "items": _one(single)}], extra

    def nested(self, cname, sn, s, ncls) -> list[dict]:
        ref = {"$ref": DEF + ncls}
        if not s["multivalued"]:
            return [ref]
        nslots = self.cls[ncls]["slots"]
        if "interface" in nslots:               # inputs: if-a, if-b · - if-a · {interface: …} 하나 (normalize: 글자 → {interface: 글자})
            single, _ = self.scalar(ncls, "interface", nslots["interface"])
            many, _ = self.multi_scalar(ncls, "interface", {**nslots["interface"], "multivalued": True})
            strings = [b for b in many if b.get("type") != "array"]
            return strings + [{"type": "array", "items": _one(single + [ref])}, ref]
        return [{"type": "array", "items": ref}, ref]

    def slot(self, cname, sn, s) -> dict:
        if sn == "items" and NESTED.get((cname, sn)) == "InterfaceItem":
            return {"$ref": DEF + "_items"}                 # 설명은 _items 정의에 (같은 설명 — LinkML 슬롯 하나)
        ncls = NESTED.get((cname, sn))
        extra = ""
        if ncls:
            branches = self.nested(cname, sn, s, ncls)
        elif s["multivalued"]:
            branches, extra = self.multi_scalar(cname, sn, s)
        else:
            branches, extra = self.scalar(cname, sn, s)
        if not s["required"]:
            branches = _optional(branches)
        out = {**self.doc(s["description"], self.note(cname, sn), extra), **_one(branches)}
        if cname == "InterfaceItem" and sn == "unit":
            out["examples"] = list(self.units) + [a for a in self.unit_aliases if a not in self.units]
        if cname == "Interface" and sn == "version":
            out["examples"] = ["0.1.0", "1.0.0"]
        return out

    # 클래스 하나
    def obj(self, cname) -> dict:
        c = self.cls[cname]
        props, req = {}, []
        for sn, s in c["slots"].items():
            if s["built"]:
                props[sn] = self.built(sn, s)
                continue
            props[sn] = self.slot(cname, sn, s)
            if s["required"] and not (cname == "InterfaceItem" and sn == "name"):   # 한 줄·칸 이름 형식에서는 이름이 칸 이름
                req.append(sn)
        for pf in sorted(PERSON_FIELDS):
            props[pf] = {"$ref": DEF + "_person"}
        d = {"type": "object", "title": f"{cname} — {KO[cname]}", **self.doc(c["description"]), "properties": props,
             "additionalProperties": False}
        if req:
            d["required"] = req
        if cname in SNIPPETS:
            d["defaultSnippets"] = SNIPPETS[cname]
        return d

    def item_defs(self, item_desc: str) -> dict:
        islots = self.cls["InterfaceItem"]["slots"]
        name_pat = islots["name"]["pattern"]
        name_msg = f"항목 이름 형식이 틀림 — {KEY_HINT['name']} (check 의 S02)"
        slots = list(islots)
        first = self.first_column_md()
        ref_pat = next(b["pattern"] for b in self.scalar("InterfaceItem", "ref", islots["ref"])[0] if "pattern" in b)
        short_msg = ("한 줄 항목은 '첫칸 | 설명' 또는 '첫칸 | 설명 | 선택' — 첫칸(단위·형식)은 비울 수 없고(U01), file: 뒤 확장자는 "
                     "소문자·점 없이 쉼표로 붙여(file:csv,txt), 셋째 칸에는 '선택' 만, '|' 는 두 번까지 (S02). "
                     "설명에 '|' 를 쓰려면 긴 형식 {label: …}")
        return {
            "_items": {**self.doc(item_desc, "한 줄 `이름: 첫칸 | 설명 [| 선택]` 또는 긴 형식 `이름: {type: …, unit: …}`. "
                                             "목록으로 `- 이름: …` · `- {name: …, …}` 도 된다.", first),
                       "anyOf": [{"type": "object", "propertyNames": {"pattern": name_pat, "patternErrorMessage": name_msg},
                                  "additionalProperties": {"$ref": DEF + "_item_value"}},
                                 {"type": "array", "items": {"$ref": DEF + "_item_entry"}}],
                       "defaultSnippets": ITEM_SNIPPETS},
            "_item_value": {**self.doc("계약 항목 하나 — 한 줄 `첫칸 | 설명 [| 선택]` 또는 긴 형식 `{type: …, unit: …, label: …}`.", first),
                            "anyOf": [{"type": "string", "pattern": short_item_pattern(islots["formats"]["pattern"], ref_pat),
                                       "patternErrorMessage": short_msg,
                                       "errorMessage": short_msg},
                                      {"$ref": DEF + "InterfaceItem"},
                                      {"type": ["number", "boolean"]}],       # YAML 1.2 의 'PR: 1' — 로더는 글자 '1' (첫칸 = 단위 1)
                            "examples": ["kg/s | 설명", "1 | 설명", "퍼센트 | 설명", "int | 설명", "text | 설명", "file:csv | 설명",
                                         "enum:A/B/C | 설명", "struct:MapPoint[] | 설명", "kg/s | 설명 | 선택"]},
            "_item_entry": {"anyOf": [{"$ref": DEF + "_item_named"},
                                      {"type": "object", "minProperties": 1, "maxProperties": 1,
                                       "propertyNames": {"pattern": name_pat, "not": {"enum": slots}, "patternErrorMessage": name_msg},
                                       "additionalProperties": {"$ref": DEF + "_item_value"}}]},
            "_item_named": {"allOf": [{"$ref": DEF + "InterfaceItem"}, {"required": ["name"]}]},
        }

    def first_column_md(self) -> str:
        groups: dict = {}
        for word, (typ, _) in SHORT_TYPES.items():
            groups.setdefault(typ, []).append(word)
        ko = {"integer": "정수 (단위 1)", "string": "글자", "boolean": "참/거짓", "file": "파일"}
        rows = ["| 첫칸 | 뜻 |", "|---|---|", "| 단위 기호 (`kg/s`, `K` …) | 숫자 (number) |", "| `1` · `퍼센트` | 무차원 · % |"]
        for typ, words in groups.items():
            shown = " · ".join(f"`{w}`" for w in words)
            if typ == "file":
                shown = " · ".join(f"`{w}:csv,txt`" for w in words)
            rows.append(f"| {shown} | {ko.get(typ, typ)} |")
        rows += ["| `enum:A/B/C` | 선택지 |", "| `struct:묶음이름` | 같은 계약의 묶음 또는 다른 계약 key |", "| 끝에 `[]` | 목록 |",
                 "", "셋째 칸 `선택` = 필수 아님. " + self.units_md()]
        return "\n".join(rows)

    def schema(self) -> dict:
        defs = {}
        for c in self.reach:
            if c != ROOT:
                defs[c] = self.obj(c)
        items_desc = self.cls["Interface"]["slots"]["items"]["description"]
        defs.update(self.item_defs(items_desc))
        msg = "인명은 저장하지 않는다 — 이 칸을 지운다 (check 의 S01, 절대 규칙 5)"
        defs["_person"] = {"description": msg, "markdownDescription": f"**{msg}**", "not": {}, "errorMessage": msg,
                           "deprecationMessage": msg, "doNotSuggest": True}
        root = self.obj(ROOT)
        for k in ("type", "title", "description", "markdownDescription"):
            root.pop(k)
        head = ("워크플로 YAML 파일 하나 — `_plan.yaml`(plan·disciplines·tools·components)과 분야 파일(discipline·steps·interfaces·loops)이 "
                "같은 모양이고 절은 전부 선택이다. 편집기는 **모양**만 본다 — 참조·단위·흐름·루프·판은 `check.bat`.")
        return {"$schema": DRAFT07, "$comment": COMMENT, "title": "En-Genius 워크플로 YAML (작성용)", **self.doc(head),
                "type": "object", **root, "definitions": defs}


def build_authoring_schema(model: dict, rules: dict, units: dict, unit_aliases: dict) -> dict:
    """작성용 JSON Schema (draft-07) — model = schema_gen.authoring_model(), rules·units = 저장소 config 기본값."""
    return _Builder(model, rules, units, unit_aliases).schema()
