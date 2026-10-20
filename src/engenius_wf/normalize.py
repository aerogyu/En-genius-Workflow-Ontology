"""검사 2층 앞: 짧은 문법을 정본 모양으로 펼친다. 모르는 것은 그대로 두어 모양 검사(checks.check_shape)가 잡게 한다.

  inputs: if-a, if-b              → [{interface: if-a}, {interface: if-b}]
  items: {W2: "kg/s | 유량 | 선택"} → [{name: W2, type: number, unit: kg/s, label: 유량, required: false}]
  transfer: 수기                  → 메일·수기 전달 (config/rules.yaml transfer_aliases)
참/거짓·정수·실수는 스키마상 그 형인 칸에서만 바꾼다 (loader 가 모든 값을 글자로 읽었다).
"""

from __future__ import annotations

import re

from engenius_wf.loader import LDict, LList
from engenius_wf.model import NESTED, Terms
from engenius_wf.report import Report

# 한 줄 항목의 첫 칸 → (자료형, 기본 단위)
SHORT_TYPES = {"int": ("integer", "1"), "정수": ("integer", "1"), "text": ("string", None), "문자": ("string", None),
               "bool": ("boolean", None), "참거짓": ("boolean", None), "file": ("file", None), "파일": ("file", None)}
# 정수·실수 칸에서 숫자로 바꾸는 글자 (앞뒤 공백을 뗀 뒤 전체 일치) — 작성용 JSON Schema(authoring)도 같은 식을 쓴다
INT_TEXT = r"[+-]?\d+"
FLOAT_TEXT = r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?"
# 한 줄 항목 셋째 칸에 쓸 수 있는 낱말 (안 쓰면 필수)
OPTIONAL_WORDS = ("선택", "optional")


class Normalizer:
    """짧은 문법을 정본 모양으로 펼친다. 모르는 것은 그대로 두어 모양 검사가 잡게 한다."""

    def __init__(self, terms: Terms, rules, rep: Report, fname):
        self.T, self.rules, self.rep, self.f = terms, rules, rep, fname
        self.tw = {str(x).lower() for x in rules["true_words"]}
        self.fw = {str(x).lower() for x in rules["false_words"]}

    def obj(self, cls, d, line=0):
        if not isinstance(d, dict):
            return d
        out = LDict()
        out.line = getattr(d, "line", line)
        for k, v in d.items():
            kl = getattr(d, "klines", {}).get(k, out.line)
            sl = self.T.slot(cls, k)
            if (v == "" or v is None) and sl is not None:      # 아는 칸의 빈칸 = 안 적은 것
                continue
            out.klines[k] = kl
            if sl is None:                        # 모르는 칸·담당자 칸은 값이 비어도 남겨 모양 검사가 S01 을 낸다 — { } 안 쉼표 목록
                out[k] = v                        # ('formats: pdf, docx' → 칸 'docx')·천 단위 쉼표('maximum: 1,000' → 칸 '000')가 조용히 사라지지 않게
                continue
            nested = NESTED.get((cls, k))
            if cls == "Interface" and k == "items" or cls == "Record" and k == "items":
                out[k] = self.items(v, kl)
            elif nested and not sl["multivalued"]:
                out[k] = self.obj(nested, v, kl)
            elif sl["multivalued"]:
                vals = v if isinstance(v, list) else ([v] if isinstance(v, dict) else self.split(v))
                lines = getattr(v, "ilines", None)
                if not lines or len(lines) != len(vals):
                    lines = [kl] * len(vals)
                res = LList()
                res.line = kl
                for x, xl in zip(vals, lines):
                    if nested and isinstance(x, str):                 # inputs: [if-a] → {interface: if-a}
                        x = LDict({"interface": x})
                        x.line = xl
                        x.klines = {"interface": xl}
                    res.append(self.obj(nested, x, xl) if nested else self.scalar(sl["range"], x))
                    res.ilines.append(xl)
                out[k] = res
            else:
                out[k] = self.scalar(sl["range"], v)
                if cls == "InputBinding" and k == "transfer" and isinstance(out[k], str):   # 목록·묶음이면 모양 검사(S02)가 잡게 그대로
                    out[k] = self.rules["transfer_aliases"].get(out[k], out[k])
        if cls == "InterfaceItem" and "type" not in out:
            out["type"] = "number"
        return out

    @staticmethod
    def split(v):
        return [x.strip() for x in str(v).split(",") if x.strip()] if isinstance(v, str) else [v]

    def scalar(self, rng, v):
        if not isinstance(v, str):
            return v
        s = v.strip()
        if rng == "boolean":
            if s.lower() in self.tw:
                return True
            if s.lower() in self.fw:
                return False
        elif rng == "integer" and re.fullmatch(INT_TEXT, s):
            return int(s)
        elif rng == "float" and re.fullmatch(FLOAT_TEXT, s):
            return float(s)
        return s

    def items(self, v, kl):
        out = LList()
        out.line = kl
        if isinstance(v, dict):                   # items: {W2: "kg/s | 유량", ...}  — 이름이 칸 이름
            pairs = [(k, x, v.klines.get(k, kl)) for k, x in v.items()]
        elif isinstance(v, list):
            pairs = []
            for x, xl in zip(v, getattr(v, "ilines", [kl] * len(v))):
                if isinstance(x, dict) and len(x) == 1 and next(iter(x)) not in self.T.cls["InterfaceItem"]["slots"]:
                    k = next(iter(x))
                    pairs.append((k, x[k], xl))
                else:
                    pairs.append((None, x, xl))
        else:
            return v
        for name, x, xl in pairs:
            if isinstance(x, str) and name is not None:
                d = self.short_item(name, x, xl)
            elif isinstance(x, dict):
                d = LDict(x)
                d.line, d.klines = getattr(x, "line", xl), dict(getattr(x, "klines", {}))
                if name is not None:
                    d["name"] = name
                    d.klines["name"] = xl
            else:
                d = x
            out.append(self.obj("InterfaceItem", d, xl))
            out.ilines.append(xl)
        return out

    def short_item(self, name, s, line):
        """'kg/s[] | 설명 | 선택' → 항목. 첫 칸: 단위 기호 → number / int / text / bool / file:csv,txt / struct:이름 / enum:A/B (enum:A,B).
        file:·enum: 뒤는 '/' 와 ',' 로 나눈다 — 선택지 글자에 '/'·',' 가 들면 긴 형식 {type: enum, values: [...]}."""
        d = LDict({"name": name})
        d.line = line
        d.klines = {}
        parts = [p.strip() for p in s.split("|")]
        spec = parts[0]
        if spec.endswith("[]"):
            d["list"] = "true"
            spec = spec[:-2].strip()
        low = spec.lower()
        if low in SHORT_TYPES:
            d["type"], u = SHORT_TYPES[low]
            if u:
                d["unit"] = u
        elif low.startswith(("file:", "파일:")):
            d["type"] = "file"
            d["formats"] = LList(re.split(r"[,/]", spec.split(":", 1)[1].strip()))
        elif low.startswith("struct:"):
            d["type"], d["ref"] = "struct", spec.split(":", 1)[1].strip()
        elif low.startswith("enum:"):                 # 선택지는 file: 처럼 '/' 와 ',' 둘 다로 나눈다 (enum:A/B · enum:A, B)
            d["type"] = "enum"
            d["values"] = LList([x.strip() for x in re.split(r"[,/]", spec.split(":", 1)[1]) if x.strip()])
        elif spec == "":
            self.rep.err("U01", (self.f, line), f"항목 '{name}' 의 첫 칸(단위·형식)이 비었다",
                         "숫자면 단위(무차원은 1), 글자면 text, 파일이면 file:csv")
        else:
            d["type"], d["unit"] = "number", spec
        if len(parts) > 1 and parts[1]:
            d["label"] = parts[1]
        if len(parts) > 2:
            if parts[2] in OPTIONAL_WORDS:
                d["required"] = "false"
            elif parts[2]:
                self.rep.err("S02", (self.f, line), f"항목 '{name}' 셋째 칸 '{parts[2]}' — 셋째 칸에는 '선택' 만 쓴다")
        if len(parts) > 3:
            self.rep.err("S02", (self.f, line), f"항목 '{name}' 에 '|' 가 너무 많다 (단위 | 설명 | 선택 까지)",
                         "설명에 '|' 를 쓰려면 긴 형식 {label: ...}")
        return d
