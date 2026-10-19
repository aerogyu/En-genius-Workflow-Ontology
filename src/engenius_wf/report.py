"""검사 보고 — 메시지 하나 = 수준(오류·경고·참고) + 코드 + 파일·행 + 문구 + 고치는 법.

사내에서 밖으로 가져갈 수 있는 것은 코드별 건수뿐이다 (기존 Tool 온톨로지 diag 방식). 수준은 config/rules.yaml 의
levels 로 코드별로 바꿀 수 있다 (사내에서 코드 수정 없이).
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass


@dataclass
class Msg:
    level: str
    code: str
    file: str
    line: int
    text: str
    hint: str = ""


class Report:
    ORDER = {"오류": 0, "경고": 1, "참고": 2}

    def __init__(self, levels=None):
        self.items: list[Msg] = []
        self.levels = levels or {}

    def add(self, level, code, where, text, hint=""):
        f, ln = where if isinstance(where, tuple) else (where, 0)
        self.items.append(Msg(self.levels.get(code, level), code, f, ln or 0, text, hint))

    def err(self, code, where, text, hint=""):
        self.add("오류", code, where, text, hint)

    def warn(self, code, where, text, hint=""):
        self.add("경고", code, where, text, hint)

    def info(self, code, where, text, hint=""):
        self.add("참고", code, where, text, hint)

    @property
    def errors(self):
        return [m for m in self.items if m.level == "오류"]

    def count(self):
        return {k: sum(1 for m in self.items if m.level == k) for k in self.ORDER}

    def render(self):
        out = []
        for m in sorted(self.items, key=lambda m: (self.ORDER[m.level], m.code[0], m.file, m.line, m.code)):
            where = f"{m.file} {m.line}행" if m.line else m.file
            out.append(f"[{m.level} {m.code}] {where}  {m.text}")
            if m.hint:
                out.append(f"        → {m.hint}")
        n = self.count()
        out.append(f"== 오류 {n['오류']} · 경고 {n['경고']} · 참고 {n['참고']}"
                   + ("  (오류가 있으면 결과 파일을 만들지 않는다)" if n["오류"] else ""))
        return "\n".join(out)


def suggest(word, pool, n=3):
    """'혹시 …?' 안내 — 비슷한 이름 (없으면 대소문자만 다른 것)."""
    m = difflib.get_close_matches(str(word), sorted(str(p) for p in pool), n=n, cutoff=0.6)
    if not m:
        low = {str(p).lower(): p for p in pool}
        if str(word).lower() in low:
            m = [low[str(word).lower()]]
    return f"혹시 {', '.join(map(str, m))} ?" if m else ""
