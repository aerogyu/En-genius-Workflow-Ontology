"""설치된 파이썬 패키지의 라이선스 점검 — 반입 심사 자료 겸 GPL 혼입 방지 장치.

절대 규칙 4: 허용형(Apache·MIT·BSD 계열)만. AGPL·GPL 금지.
패키지 메타데이터(License-Expression, License, 분류자)만 보고 분류한다 — 메타데이터가
틀리거나 비어 있으면 '미상'으로 올려 사람이 확인한다 (판정은 엔지니어·심사 담당).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib.metadata import distributions

# 분류 등급
FORBIDDEN = "금지(GPL)"
MULTI = "복수(GPL 포함)-확인"
WEAK = "약한copyleft-확인"
PERMISSIVE = "허용형"
UNKNOWN = "미상-확인"

_ORDER = {FORBIDDEN: 0, MULTI: 1, WEAK: 2, UNKNOWN: 3, PERMISSIVE: 4}

# 설치돼 있으면 안 되는 패키지 (이유)
DENYLIST = {
    "rfc3987": "GPLv3+ — linkml→jsonschema[format] 전이 의존. `pip uninstall -y rfc3987` "
               "(jsonschema 가 rfc3986-validator 로 대체)",
}

_LESSER = re.compile(r"LGPL|Lesser General Public|Library General Public", re.I)
_STRONG = re.compile(r"(?<![LA])GPL|AGPL|Affero|(?<!Lesser )(?<!Library )General Public License", re.I)
_WEAK = re.compile(r"MPL|Mozilla|EPL|Eclipse Public|CDDL", re.I)
_PERMISSIVE = re.compile(
    r"MIT|BSD|Apache|ISC|PSF|Python Software Foundation|0BSD|Unlicense|CC0|"
    r"Public Domain|W3C|zlib|HPND|Historical Permission", re.I)


@dataclass(frozen=True)
class LicenseRow:
    name: str
    version: str
    license: str
    cls: str


def _license_texts(meta) -> list[str]:
    texts = []
    expr = meta.get("License-Expression")
    if expr:
        texts.append(expr)
    for c in meta.get_all("Classifier") or []:
        if c.startswith("License ::"):
            texts.append(c.split("::")[-1].strip())
    lic = (meta.get("License") or "").strip()
    # License 필드에 전문을 넣는 패키지가 있다 — 짧을 때만, 또는 다른 근거가 없을 때만 쓴다
    if lic and lic.upper() != "UNKNOWN" and (len(lic) <= 120 or not texts):
        texts.append(lic if len(lic) <= 120 else lic[:120] + "…")
    return texts


def classify(texts: list[str]) -> str:
    joined = " ; ".join(texts)
    if not joined.strip():
        return UNKNOWN
    has_weak = bool(_WEAK.search(joined) or _LESSER.search(joined))
    stripped = _LESSER.sub("", joined)
    has_strong = bool(_STRONG.search(stripped))
    has_perm = bool(_PERMISSIVE.search(joined))
    if has_strong:
        return MULTI if (has_perm or has_weak) else FORBIDDEN
    if has_weak:
        return WEAK
    if has_perm:
        return PERMISSIVE
    return UNKNOWN


SELF = "engenius-wf"  # 이 저장소 자신 (사내 코드, 점검 대상 아님)


def audit() -> list[LicenseRow]:
    rows = {}
    for d in distributions():
        meta = d.metadata
        name = meta.get("Name") or "?"
        key = name.lower().replace("_", "-")
        if key in rows or key == SELF:
            continue
        texts = _license_texts(meta)
        cls = FORBIDDEN if key in DENYLIST else classify(texts)
        rows[key] = LicenseRow(name, meta.get("Version") or "?", " / ".join(texts) or "-", cls)
    return sorted(rows.values(), key=lambda r: (_ORDER[r.cls], r.name.lower()))


def denylisted(rows: list[LicenseRow]) -> list[LicenseRow]:
    return [r for r in rows if r.name.lower().replace("_", "-") in DENYLIST]


def to_markdown(rows: list[LicenseRow]) -> str:
    out = ["| 패키지 | 버전 | 라이선스(메타데이터) | 분류 |", "|---|---|---|---|"]
    for r in rows:
        lic = r.license.replace("|", "/")
        out.append(f"| {r.name} | {r.version} | {lic} | {r.cls} |")
    return "\n".join(out)
