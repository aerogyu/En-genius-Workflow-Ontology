"""작성용 JSON Schema (schema/generated/wfo_authoring.schema.json) — VS Code(Red Hat YAML 확장 1.25.0 = yaml-language-server)의 '모양' 검사.

로더(loader → normalize → check_shape)와 어긋나지 않게 묶는다.
  ① 예시·fixture 의 정상 YAML 은 세 가지로 읽어도 통과한다 — 전부 글자(BaseLoader = 우리 로더) · YAML 1.1(PyYAML safe_load: yes/no·0.1 이
     참거짓·숫자) · YAML 1.2 core(yaml-language-server 가 읽는 방식: true·0.1·1.10 은 참거짓·숫자, yes·o 는 글자).
  ② 실수 주입 23종(test_mistakes.CASES) 중 '모양' 오류(S01·S02·S04)는 스키마도 잡는다. 의미 오류(R·U·C·D·F·L·P)는 모양이 맞는 YAML 이라
     스키마는 통과시킨다 — check.bat 몫 (MISTAKE_SCOPE 에 사유). YAML 읽기 오류(Y)는 스키마가 아니라 확장 자체·check 가 알린다.
     더해 모양 오류 주입(SHAPE_CASES)은 로더와 스키마가 둘 다 막는지 본다.
  ③ 변이 시험 (3천여 건, 10초 남짓): 예시의 값 하나를 까다로운 글자로 바꾸거나, 칸·항목 하나를 지우거나, 묶음에 모르는 칸·담당자 칸을
     (값이 있게·빈 값으로) 더해 로더와 스키마의 판정을 비교한다 — 로더가 받으면 스키마도 받는다(거짓 밑줄 0). YAML 1.2 가 글자로 읽는 값·지우기·더하기에서는
     로더가 막으면 스키마도 막는다. (스키마를 일부러 고장 내 보면 — 숫자 판 거부·key 형식 안 봄·참거짓 낱말 거부·필수 안 봄·모르는 칸 허용 —
     각각 이 시험이 잡는 것을 개발 때 확인했다.)
     (YAML 1.2 가 숫자·참거짓으로 바꾸는 값은 원래 글자를 모르므로 스키마가 너그러울 수 있다 — 알려진 차이, docs/02 1-1장.)
     로더 판정 = 읽기 + 펼치기 + 모양 검사 + 참조 칸의 key 형식 (형식이 틀린 key 는 R01 이 반드시 난다 — 스키마 원칙 ③).
  ④ 스키마 자체: Draft7Validator.check_schema · 외부 참조 0 · JS 와 파이썬이 같게 읽는 정규식 · 클래스 칸이 LinkML(terms.json)과 같다 ·
     설정(rules.yaml)에서 만든다. 드리프트(--check)는 test_schema.test_generated_files_up_to_date 가 본다.
yaml-language-server 자체는 이 PC 에 없다 — 메시지 문구·자동완성·마우스 설명은 사내 VS Code 에서 처음 확인한다.
(확장 1.25.0 은 스키마 위반을 전부 '경고' 로 낸다 — 편집기에서는 노란 물결, 빨간 물결은 YAML 문법 오류뿐. 이 파일의 '밑줄' = 스키마 오류.)
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

from engenius_wf.checks import PERSON_FIELDS, check_shape, shape_validator
from engenius_wf.config import EXAMPLES_DIR, GEN_DIR, REPO_ROOT, load_rules
from engenius_wf.loader import read_yaml, read_yaml_text
from engenius_wf.model import NESTED, Terms
from engenius_wf.normalize import Normalizer
from engenius_wf.report import Report
from test_mistakes import CASES
from wfhelp import copy_example, edit

AUTH_FILE = GEN_DIR / "wfo_authoring.schema.json"
FIXTURES = REPO_ROOT / "tests" / "fixtures"
EXAMPLE_FILES = sorted(EXAMPLES_DIR.glob("*/*.yaml")) + sorted(FIXTURES.glob("**/*.yaml"))


# --------------------------------------------------------------------------- YAML 세 가지 읽기
class Core12Loader(yaml.SafeLoader):
    """YAML 1.2 core schema 흉내 (yaml-language-server 가 읽는 방식) — 참거짓 true·True·TRUE·false…, 정수 10진·0o·0x, 실수(.5·1e3·.inf·.nan),
    null(~·null·빈칸). yes/no/on/off·날짜는 글자. 칸 이름은 원문 글자 (언어 서버의 JSON 모양에서 키는 늘 글자)."""


Core12Loader.yaml_implicit_resolvers = {}
for _tag, _rx, _first in [
    ("tag:yaml.org,2002:null", r"^(?:~|null|Null|NULL|)$", ["~", "n", "N", ""]),
    ("tag:yaml.org,2002:bool", r"^(?:true|True|TRUE|false|False|FALSE)$", list("tTfF")),
    ("tag:yaml.org,2002:int", r"^(?:[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+)$", list("-+0123456789")),
    ("tag:yaml.org,2002:float",
     r"^(?:[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$",
     list("-+0123456789.")),
]:
    Core12Loader.add_implicit_resolver(_tag, re.compile(_rx), _first)


def _c12_int(loader, node):
    v = loader.construct_scalar(node)
    return int(v[2:], 8) if v.startswith("0o") else int(v[2:], 16) if v.startswith("0x") else int(v)


def _c12_float(loader, node):
    v = loader.construct_scalar(node).lower()
    if v.lstrip("+-") == ".inf":
        return float("-inf") if v.startswith("-") else float("inf")
    return float("nan") if v == ".nan" else float(v)


def _c12_map(loader, node):
    return {(k.value if isinstance(k, yaml.ScalarNode) else str(loader.construct_object(k, deep=True))):
            loader.construct_object(v, deep=True) for k, v in node.value}


Core12Loader.add_constructor("tag:yaml.org,2002:int", _c12_int)
Core12Loader.add_constructor("tag:yaml.org,2002:float", _c12_float)
Core12Loader.add_constructor("tag:yaml.org,2002:map", _c12_map)


def _jsonish(x):
    """YAML 1.1(PyYAML) 결과를 JSON 모양으로 — 칸 이름은 글자, 날짜는 ISO 글자 (언어 서버의 JSON 모양에는 날짜 형이 없다)."""
    if isinstance(x, dict):
        return {str(k): _jsonish(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_jsonish(v) for v in x]
    if isinstance(x, (dt.date, dt.datetime)):
        return x.isoformat()
    return x


VIEWS = {
    "strings": lambda t: yaml.load(t, Loader=yaml.BaseLoader),        # 우리 로더와 같은 읽기 (전부 글자)
    "yaml11": lambda t: _jsonish(yaml.safe_load(t)),                  # PyYAML — yes/no·on/off 참거짓, 0.1·1.10 숫자
    "yaml12": lambda t: yaml.load(t, Loader=Core12Loader),            # yaml-language-server 흉내
}


class PlainDumper(yaml.SafeDumper):
    """글자를 될 수 있는 한 따옴표 없이 쓴다 (yes·1.10 도 맨 글자) — 사람이 메모장에 그렇게 친 것과 같은 YAML."""


PlainDumper.yaml_implicit_resolvers = {}


def dump_plain(data) -> str:
    return yaml.dump(data, Dumper=PlainDumper, allow_unicode=True, sort_keys=False, default_flow_style=False, width=1000)


# --------------------------------------------------------------------------- 검사기
@pytest.fixture(scope="module")
def auth():
    return json.loads(AUTH_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def av(auth):
    return Draft7Validator(auth)


def schema_errors(av, data) -> list[str]:
    return [f"{'/'.join(map(str, e.absolute_path))}: {e.message[:100]}" for e in av.iter_errors(data)]


T = Terms()
RULES = load_rules()
SHAPE = shape_validator()


def _ref_patterns() -> dict:
    """참조 칸 → 그 칸이 가리키는 것의 key 형식 (로더 판정 흉내 — 형식이 틀린 key 는 R01·C03 이 반드시 난다).
    패턴은 terms.json 에 없어 LinkML 원본(schema/wfo.yaml)에서 읽는다 — 작성용 스키마와 따로 (같은 것을 두 번 쓰지 않게)."""
    lk = yaml.safe_load((REPO_ROOT / "schema" / "wfo.yaml").read_text(encoding="utf-8"))
    key = lk["slots"]["key"]["pattern"]
    rec = lk["classes"]["Record"]["attributes"]["name"]["pattern"]
    out = {}
    for c, cd in T.cls.items():
        for sn, s in cd["slots"].items():
            if not s["built"] and s["range"] in T.cls and (c, sn) not in NESTED:
                out[(c, sn)] = key
    out[("InterfaceItem", "ref")] = f"(?:{rec[1:-1]})|(?:{key[1:-1]})"
    return out


REF_PATTERNS = _ref_patterns()


def _refs(cls, d):
    """펼친 데이터에서 참조 칸 값 (글자만 — 글자가 아니면 모양 검사가 이미 막았다)."""
    if not isinstance(d, dict):
        return
    for k, v in d.items():
        pat = REF_PATTERNS.get((cls, k))
        if pat:
            for x in (v if isinstance(v, list) else [v]):
                if isinstance(x, str):
                    yield x, pat
        n = NESTED.get((cls, k))
        if n:
            for x in (v if isinstance(v, list) else [v]):
                yield from _refs(n, x)


def loader_accepts(path: Path, text: str | None = None) -> tuple[bool, list[str]]:
    """로더 판정 — 읽기·펼치기·모양 검사(pipeline.load_all 과 같은 순서) 오류 0 이고 참조 칸이 key 형식이면 받는다. (받음, 오류 코드들).
    text 를 주면 파일 대신 그 글자를 읽는다 (변이 시험 — 디스크에 쓰지 않게)."""
    rep = Report()
    raw = read_yaml(path, rep) if text is None else read_yaml_text(text, path.name, rep)
    bad_refs = []
    if raw is not None:
        data = Normalizer(T, RULES, rep, path.name).obj("WorkflowFile", raw)
        if check_shape(path.name, data, SHAPE, T, rep) and not rep.errors:
            bad_refs = [v for v, p in _refs("WorkflowFile", data) if not re.fullmatch(p, v)]
    codes = [m.code for m in rep.errors] + (["R01(형식)"] if bad_refs else [])
    return not codes, codes


# =========================================================================== ① 정상 예시 — 세 가지 읽기
@pytest.mark.parametrize("view", list(VIEWS))
@pytest.mark.parametrize("path", EXAMPLE_FILES, ids=[str(p.relative_to(REPO_ROOT)) for p in EXAMPLE_FILES])
def test_examples_pass_every_reading(av, path, view):
    assert loader_accepts(path)[0]                              # 전제: 로더도 받는 정상 예시
    data = VIEWS[view](path.read_text(encoding="utf-8"))
    assert schema_errors(av, data) == []


def test_example_set_covers_short_forms():
    """정상 예시가 짧은 표기를 두루 품는지 (그래야 ① 이 의미가 있다). 예시에 없는 까다로운 표기는 fixtures/authoring/short_forms.yaml."""
    text = "\n".join(p.read_text(encoding="utf-8") for p in EXAMPLE_FILES)
    for frag in ("tools: meanline-py, excel", "transfer: 수기", "transfer: 파일", "| 선택", "file:csv,txt", "struct:Station[]",
                 "int  |", "퍼센트", "deliverable: true", "external: true", "version: 0.1\n", "inputs: if-cmp-1d",
                 "inputs: {interface:", "monitor: [", "max_iterations: 5", "minimum: 0", "- name: MapPoint",
                 # short_forms.yaml
                 "version: 1.10}", "external: 예", "deliverable: X", "required: o", "list: no", "list: TRUE", "values: [yes, no, 1.10, true]",
                 "tool_id: ''", "- key: true", "status:\n", "format: '001'", "if-y , , if-z", "| optional", "- PR_c: 1", "- z: true",
                 "FILE:cgns / cas.h5 []", "max_iterations: '05'", "monitor: if-y.W2, if-z.f", "disciplines: {key:", "enum:1D, CFD/시험"):
        assert frag in text, frag


# =========================================================================== ② 실수 주입 — 모양 오류는 스키마도 잡는다
MISTAKE_SCOPE = {
    # 스키마가 잡는다 (모양)
    "S01": "caught", "S02": "caught", "S04": "caught",
    # YAML 읽기 — 스키마가 아니라 확장 자체(문법 오류 빨간 물결·'Map keys must be unique')와 check 가 알린다.
    # 값 사이 탭(Y02)은 YAML 1.2 가 띄어쓰기로 받아 확장이 조용할 수 있다 — test_mistakes.test_tab_between_values
    "Y01": "encoding", "Y02": "unparsable", "Y03": "unparsable", "Y04": "reader",
    # 의미 — 모양은 맞으니 스키마는 통과시킨다 (check.bat 몫)
    "R01": "semantic", "R02": "semantic", "U01": "semantic", "U02": "semantic", "F01": "semantic", "D01": "semantic",
    "L05": "semantic", "L07": "semantic", "P01": "semantic", "C03": "semantic", "": "semantic",
}


def _schema_verdict(av, folder: Path) -> str:
    """'caught' (한 파일이라도 스키마 오류) · 'clean' · 'unparsable' (YAML 1.2 로 못 읽음)."""
    caught = False
    for f in sorted(folder.glob("*.yaml")):
        try:
            data = VIEWS["yaml12"](f.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            return "unparsable"
        caught |= bool(schema_errors(av, data))
    return "caught" if caught else "clean"


SCOPED = [c for c in CASES if MISTAKE_SCOPE[c[3]] != "encoding"]     # 메모장 ANSI 저장은 인코딩 문제 — VS Code 는 UTF-8 로 저장한다


@pytest.mark.parametrize("name, src, edits, code", [c[:4] for c in SCOPED], ids=[c[0] for c in SCOPED])
def test_mistakes_scope(av, tmp_path, name, src, edits, code):
    scope = MISTAKE_SCOPE[code]
    d = copy_example(tmp_path, src, state=False)
    for f, a, b in edits:
        edit(d / f, a, b)
    verdict = _schema_verdict(av, d)
    want = {"caught": "caught", "unparsable": "unparsable", "reader": "clean", "semantic": "clean"}[scope]
    assert verdict == want, (code, verdict)


def test_mistake_scope_covers_all_cases():
    assert {c[3] for c in CASES} <= set(MISTAKE_SCOPE)
    assert [c[3] for c in CASES if c not in SCOPED] == ["Y01"]
    assert sum(MISTAKE_SCOPE[c[3]] == "caught" for c in CASES) == 6       # 23종 중 모양 오류 6 (S01 2 · S02 3 · S04 1)


# 모양 오류 더 — (이름, 원본, 파일, 바꿀 것, 바꿀 값, 로더 코드). 로더와 스키마(YAML 1.2·전부 글자 두 읽기)가 둘 다 막는다
SHAPE_CASES = [
    ("필수 label 없음", "short", "perf.yaml", "    label: 설계점 사이클 해석\n", "", "S03"),
    ("필수 until 없음", "short", "cmp.yaml", "    until: 맵을 반영한 사이클 재정합에서 추력 오차 1 % 이내 (예시 값, 판정은 엔지니어)\n", "", "S03"),
    ("계약 version 없음", "short", "perf.yaml", "    version: 0.1.0\n", "", "S03"),
    ("필수 칸 빈칸", "short", "perf.yaml", "    label: 설계점 사이클 해석", "    label:", "S03"),
    ("items 비움", "short", "perf.yaml", "    items:                              # 한 줄 = 이름: 단위 | 한국어 설명 [| 선택]\n"
                                       "      W2:   kg/s | 압축기 입구 유량\n      PR_c: 1    | 압축기 압력비\n"
                                       "      Tt4:  K    | 터빈 입구 전온도\n      BPR:  1    | 바이패스비 | 선택\n", "    items:\n", "S03"),
    ("참거짓 칸에 다른 낱말", "textbook", "cmp.yaml", "deliverable: true", "deliverable: maybe", "S02"),
    ("참거짓 칸에 on", "textbook", "cmp.yaml", "deliverable: true", "deliverable: on", "S02"),
    ("정수 칸에 글자", "short", "cmp.yaml", "max_iterations: 5", "max_iterations: 다섯", "S02"),
    ("정수 칸 하한 밖", "short", "cmp.yaml", "max_iterations: 5", "max_iterations: 0", "S02"),
    ("실수 칸에 글자", "textbook", "perf.yaml", "minimum: 800", "minimum: 팔백", "S02"),
    ("phase 선택지 밖", "short", "_plan.yaml", "phase: 개념설계", "phase: 개념", "S02"),
    ("status 선택지 밖", "textbook", "perf.yaml", "status: 확정", "status: 완료", "S02"),
    ("항목 type 선택지 밖", "short", "cmp.yaml", "{type: enum,", "{type: float,", "S02"),
    ("TOOL ID 형식", "textbook", "_plan.yaml", "tool_id: TOOL-900002", "tool_id: TOOL-12", "S02"),
    ("확장자 대문자", "textbook", "cmp.yaml", "format: csv}", "format: CSV}", "S02"),
    ("formats 점", "textbook", "cmp.yaml", "file:cgns", "file:.cgns", "S02"),
    ("묶음 이름 소문자", "textbook", "cmp.yaml", "name: MapPoint", "name: mapPoint", "S02"),
    ("항목 이름 한글", "short", "perf.yaml", "W2:   kg/s", "유량:   kg/s", "S02"),
    ("한 줄 항목 셋째 칸", "short", "perf.yaml", "바이패스비 | 선택", "바이패스비 | 필수", "S02"),
    ("한 줄 항목 '|' 셋", "short", "perf.yaml", "바이패스비 | 선택", "바이패스비 | 선택 | 메모", "S02"),
    ("한 줄 항목 첫칸 빔", "short", "perf.yaml", "Tt4:  K    | 터빈 입구 전온도", "Tt4:  \" | 터빈 입구 전온도\"", "U01"),
    ("한 줄 항목 확장자 빈 조각", "textbook", "cmp.yaml", "file:csv,txt | 맵 파일", "file:csv,,txt | 맵 파일", "S02"),
    ("한 줄 항목 확장자 대문자", "short", "cmp.yaml", "file:csv | 맵 파일", "FILE:CSV | 맵 파일", "S02"),
    ("한 줄 항목 struct 이름", "textbook", "perf.yaml", "struct:Station[]", "struct:station_row[]", "R01(형식)"),
    ("renamed_from 형식", "short", "perf.yaml", "  - key: perf-cycle\n", "  - key: perf-cycle\n    renamed_from: Perf_Cycle\n", "S02"),
    ("monitor 형식", "short", "cmp.yaml", "monitor: if-cmp-map.surge_margin", "monitor: surge_margin", "S02"),
    ("빌드 칸 members", "short", "cmp.yaml", "    max_iterations: 5", "    max_iterations: 5\n    members: perf-cycle", "S04"),
    ("담당 칸 (툴 목록)", "short", "_plan.yaml", "{key: excel,   label: Excel}", "{key: excel,   label: Excel, 담당: 누구}", "S01"),
    ("맨 위 모르는 칸", "short", "_plan.yaml", "disciplines:", "disciplnes:", "S01"),
    ("key 앞 대문자", "short", "perf.yaml", "  - key: if-cycle-dp", "  - key: IF-cycle-dp", "S02"),
    ("label 에 목록", "short", "perf.yaml", "    label: 설계점 사이클 결과", "    label: [가, 나]", "S02"),
    ("참조 key 형식 (tools)", "short", "perf.yaml", "    tools: gasturb", "    tools: Gas Turb", "R01(형식)"),
    # { } 한 줄 안의 쉼표는 칸을 나눈다 — 쉼표 뒤 조각이 '값 없는 칸' 이 된다 (로더도 S01 — 예전에는 조용히 버려 값을 잃었다)
    ("{ } 안 쉼표 목록 (related_parts)", "short", "_plan.yaml", "{key: perf, label: 성능}",
     "{key: perf, label: 성능, related_parts: COOL, SAS}", "S01"),
    ("{ } 안 쉼표 목록 (formats)", "short", "cmp.yaml", "map_file:     file:csv | 맵 파일 (속도선별 수정유량·압력비·효율)",
     "map_file:     {type: file, formats: pdf, docx, label: 보고서}", "S01"),
    ("{ } 안 천 단위 쉼표", "short", "perf.yaml", "BPR:  1    | 바이패스비 | 선택", "BPR:  {unit: 1, minimum: 0, maximum: 1,000}", "S01"),
    ("값 없는 모르는 칸", "short", "cmp.yaml", "    max_iterations: 5", "    max_iterations: 5\n    oops:", "S01"),
    ("값 없는 담당자 칸", "short", "cmp.yaml", "    max_iterations: 5", "    max_iterations: 5\n    담당자:", "S01"),
]


@pytest.mark.parametrize("name, src, fname, a, b, code", SHAPE_CASES, ids=[c[0] for c in SHAPE_CASES])
def test_shape_mistakes_caught_by_both(av, tmp_path, name, src, fname, a, b, code):
    d = copy_example(tmp_path, src, state=False)
    edit(d / fname, a, b)
    ok, codes = loader_accepts(d / fname)
    assert not ok and code in codes, codes
    text = (d / fname).read_text(encoding="utf-8")
    for view in ("yaml12", "strings"):
        assert schema_errors(av, VIEWS[view](text)), (view, name)


def test_known_stricter_cases(av, tmp_path):
    """알려진 차이 (docs/02 1-1장) — 편집기가 더 엄격: 빈 값의 빌드 칸은 밑줄 (로더는 아는 칸의 빈칸을 '안 적은 것' 으로 넘긴다 —
    잃는 값이 없다), 필수 칸에 글자로 쓴 null 은 빈칸으로 본다 (로더는 글자 'null'). 빈 값의 모르는 칸·담당자 칸은 로더도 S01 이라
    이제 차이가 아니다 (SHAPE_CASES 의 '값 없는 …'·'{ } 안 쉼표 …')."""
    base = (EXAMPLES_DIR / "short" / "cmp.yaml").read_text(encoding="utf-8")
    cases = [base.replace("    max_iterations: 5", "    max_iterations: 5\n    members: ''"),
             base.replace("    label: 압축기 특성 맵", "    label: null")]
    for i, text in enumerate(cases):
        p = tmp_path / f"c{i}.yaml"
        p.write_text(text, encoding="utf-8")
        assert loader_accepts(p)[0], i
        assert schema_errors(av, VIEWS["yaml12"](text)), i


def test_known_lenient_case(av, tmp_path):
    """알려진 차이 — 편집기가 더 너그러움: YAML 1.2 가 참거짓으로 바꾼 'True' 는 원래 글자를 모른다 (로더는 대문자 key 라 S02)."""
    text = (EXAMPLES_DIR / "short" / "_plan.yaml").read_text(encoding="utf-8").replace("{key: excel,", "{key: True,")
    p = tmp_path / "_plan.yaml"
    p.write_text(text, encoding="utf-8")
    ok, codes = loader_accepts(p)
    assert not ok and "S02" in codes
    assert schema_errors(av, VIEWS["yaml12"](text)) == []
    assert schema_errors(av, VIEWS["strings"](text))                   # 글자 그대로였다면 잡는다


# =========================================================================== ③ 변이 시험 (예시 short·textbook)
STRING_TOKENS = ["yes", "on", "예", "o", "x", "", "Abc", "abc-def", "a, b", "kg/s | 설명", "W 2", "TOOL-000001", "0.1.0", "csv",
                 ["abc"], {"zz": "abc"}]                       # YAML 1.2 도 글자(또는 그 묶음)로 읽는 값 → 두 방향 다 같은 판정
TYPED_TOKENS = ["true", "True", "1.10", "0.1", "001", "3", "-1", "1e3"]      # YAML 1.2 가 숫자·참거짓으로 읽는 값 → 로더가 받으면 스키마도


def _paths(node, path=()):
    """맨 위를 뺀 모든 자리 (칸 값·목록 항목 — 글자든 묶음이든)."""
    items = node.items() if isinstance(node, dict) else enumerate(node) if isinstance(node, list) else ()
    for k, v in items:
        yield path + (k,)
        yield from _paths(v, path + (k,))


def _signature(path) -> tuple:
    """같은 자리의 값은 한 번만 — 목록 번호와 항목·묶음 이름은 지운다."""
    out, prev = [], None
    for x in path:
        out.append("#" if isinstance(x, int) else "*" if prev == "items" and isinstance(x, str) else x)
        prev = x
    return tuple(out)


_DELETE = object()


def _set(tree, path, value):
    """자리 하나만 바꾼(또는 지운) 사본 — 그 길의 묶음만 얕게 복사하고 나머지는 원본과 같이 쓴다."""
    head, rest = path[0], path[1:]
    t = dict(tree) if isinstance(tree, dict) else list(tree)
    if rest:
        t[head] = _set(tree[head], rest, value)
    elif value is _DELETE:
        del t[head]
    else:
        t[head] = value
    return t


def _prune(tree, path, top=True):
    """그 자리까지의 길만 남긴 나무와 새 자리 — 판정은 바꾼 자리와 그 조상 묶음에만 달렸다 (원본은 모양이 맞으므로).
    길 위의 목록은 그 항목 하나만, 맨 위는 그 절 하나만 남긴다. 길 위의 묶음(dict)은 형제 칸을 그대로 둔다 (필수 칸·모르는 칸 판정).
    PyYAML 순수 파이썬 읽기가 느려서 — 문서를 작게."""
    head, rest = path[0], path[1:]
    if rest:
        sub, rp = _prune(tree[head], rest, False)
    else:
        sub, rp = (tree.get(head) if isinstance(tree, dict) else tree[head]), ()       # 없는 칸 = 칸 더하기 변이
    if isinstance(tree, list):
        return [sub], (0,) + rp
    t = {head: sub} if top else {**tree, head: sub}
    return t, (head,) + rp


# 묶음마다 모르는 칸·담당자 칸 더하기 — 값이 빈 것도 ({ } 안 쉼표 조각). 계약 항목 묶음에서는 항목 이름이라 'abc'·'x' 는 받고 빈 값은 U01
ADDED_KEYS = {"zz": "abc", "담당자": "x", "yy": "", "작성자": ""}


def _mutations():
    """(파일, 나무, 자리, 바꿀 값, 두 방향 비교인지) — 같은 모양의 자리(_signature)는 예시 전체에서 한 번만:
    값 바꾸기 + 칸·항목 지우기 + 묶음에 칸 더하기."""
    seen = set()
    for src in ("short", "textbook"):
        for f in sorted((EXAMPLES_DIR / src).glob("*.yaml")):
            tree = yaml.load(f.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
            nodes = {(): tree}
            for path in _paths(tree):
                node = tree
                for x in path:
                    node = node[x]
                nodes[path] = node
            for path, node in nodes.items():
                sig = (f.name, _signature(path))
                if sig in seen:
                    continue
                seen.add(sig)
                if isinstance(node, dict):
                    for k, v in ADDED_KEYS.items():
                        small, spath = _prune(tree, path + (k,))
                        yield f, small, spath, v, True
                if not path:
                    continue
                small, spath = _prune(tree, path)
                for tok in STRING_TOKENS:
                    yield f, small, spath, tok, True
                for tok in TYPED_TOKENS:
                    yield f, small, spath, tok, False
                yield f, small, spath, _DELETE, True


def test_mutations_loader_and_schema_agree(av):
    """로더가 받으면 스키마도 받는다 (모든 변이) · 로더가 막으면 스키마도 막는다 (글자 값·칸 지우기). 어긋난 것을 모아 한 번에 보인다."""
    false_red, missed, n = [], [], 0
    for f, tree, path, tok, two_way in _mutations():
        text = dump_plain(_set(tree, path, tok))
        ok, codes = loader_accepts(f, text)
        sch = not schema_errors(av, VIEWS["yaml12"](text))
        n += 1
        what = f"{f.parent.name}/{f.name} {'/'.join(map(str, path))} ← {'(지움)' if tok is _DELETE else repr(tok)}"
        if ok and not sch:
            false_red.append(what)
        if two_way and not ok and sch:
            missed.append(f"{what} {codes}")
    assert n > 1000
    assert false_red == [], f"거짓 밑줄 {len(false_red)}건: " + "\n".join(false_red[:20])
    assert missed == [], f"스키마가 놓친 모양 오류 {len(missed)}건: " + "\n".join(missed[:20])


# =========================================================================== ④ 스키마 자체
def test_schema_is_valid_draft07(auth):
    assert auth["$schema"] == "http://json-schema.org/draft-07/schema#"
    Draft7Validator.check_schema(auth)


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def test_no_external_references(auth):
    """폐쇄망 — $ref 는 전부 이 파일 안(#/definitions/…), 그 정의가 있다. 주소(http)는 $schema 하나뿐."""
    refs = {n["$ref"] for n in _walk(auth) if "$ref" in n}
    assert refs and all(r.startswith("#/definitions/") for r in refs)
    assert {r.split("/")[-1] for r in refs} <= set(auth["definitions"])
    urls = re.findall(r"https?://[^\s\"']+", AUTH_FILE.read_text(encoding="utf-8"))
    assert urls == ["http://json-schema.org/draft-07/schema#"]


def test_patterns_mean_the_same_in_js_and_python(auth):
    """yaml-language-server 는 JS 정규식(u 깃발)으로 읽는다 — 파이썬 전용 문법을 쓰지 않는다 ((?i)·(?P<…>)·\\A·\\Z·뒤보기)."""
    pats = [n["pattern"] for n in _walk(auth) if isinstance(n.get("pattern"), str)]
    assert pats
    for p in pats:
        assert not re.search(r"\(\?[aiLmsux]|\(\?P|\(\?<|\\[AZ]", p), p
        assert p.startswith("^") and p.endswith("$"), p
        re.compile(p)


def test_classes_match_linkml(auth):
    """정의마다 칸 = terms.json(LinkML) 의 칸 + 담당자류 칸, 필수 = LinkML 필수 (항목 name 은 한 줄·칸 이름 형식이 대신한다), 빌드 칸은 막힘."""
    defs = auth["definitions"]
    for cname in ("Workflow", "Discipline", "Component", "ToolRef", "Step", "InputBinding", "OutputBinding", "Interface", "Record",
                  "InterfaceItem", "Loop"):
        slots = T.cls[cname]["slots"]
        d = defs[cname]
        assert set(d["properties"]) == set(slots) | PERSON_FIELDS, cname
        assert d["additionalProperties"] is False
        want = {s for s, v in slots.items() if v["required"] and not v["built"]} - ({"name"} if cname == "InterfaceItem" else set())
        assert set(d.get("required", [])) == want, cname
        for s, v in slots.items():
            if v["built"]:
                assert d["properties"][s].get("not") == {} and d["properties"][s].get("doNotSuggest"), (cname, s)
            else:
                assert d["properties"][s].get("markdownDescription") or "$ref" in d["properties"][s], (cname, s)
    root = T.cls["WorkflowFile"]["slots"]
    assert set(auth["properties"]) == set(root) | PERSON_FIELDS
    assert defs["_item_named"]["allOf"][1] == {"required": ["name"]}


def test_choices_come_from_schema_and_rules(auth):
    """선택지 = LinkML 선택지 (+ 전달 방법은 rules.yaml 별칭), 단위 후보 = units.yaml — 자동완성 목록."""
    from engenius_wf.config import load_units

    tr = auth["definitions"]["InputBinding"]["properties"]["transfer"]["anyOf"][0]
    assert tr["enum"] == T.enums["TransferMethod"] + [a for a in RULES["transfer_aliases"] if a not in T.enums["TransferMethod"]]
    assert len(tr["enumDescriptions"]) == len(tr["enum"])
    assert auth["definitions"]["Workflow"]["properties"]["phase"]["enum"] == T.enums["DevPhase"]
    units, aliases = load_units()
    assert auth["definitions"]["InterfaceItem"]["properties"]["unit"]["examples"] == list(units) + [a for a in aliases if a not in units]


def test_built_from_config():
    """설정을 바꾸면 스키마가 따라온다 — 사내에서 rules.yaml 에 별칭·참거짓 낱말을 더하고 schema 를 다시 만들면 편집기도 받는다."""
    from engenius_wf import schema_gen
    from engenius_wf.authoring import build_authoring_schema
    from engenius_wf.config import load_units

    rules = load_rules()
    rules = {**rules, "transfer_aliases": {**rules["transfer_aliases"], "메신저": "메일·수기 전달"},
             "true_words": [*rules["true_words"], "네"]}
    units, aliases = load_units()
    s = Draft7Validator(build_authoring_schema(schema_gen.authoring_model(), rules, units, aliases))
    doc = {"interfaces": [{"key": "if-a", "label": "가", "version": "0.1.0", "external": "네", "items": {"W": "1"}}],
           "steps": [{"key": "a-b", "label": "나", "inputs": [{"interface": "if-a", "transfer": "메신저"}]}]}
    assert list(s.iter_errors(doc)) == []
    doc["steps"][0]["inputs"][0]["transfer"] = "메신져"
    assert list(s.iter_errors(doc))
