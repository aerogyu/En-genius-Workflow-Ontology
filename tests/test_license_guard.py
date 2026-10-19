"""라이선스 가드 — 절대 규칙 4 (GPL 금지) 가 현재 환경에서 지켜지는지.

사내 환경에서도 그대로 돌린다: linkml 을 새로 설치하면 rfc3987(GPLv3+) 이 딸려 오므로
`pip uninstall -y rfc3987` 을 빠뜨리면 여기서 실패한다.
"""

from __future__ import annotations

import pytest

from engenius_wf.licenses import (
    FORBIDDEN, MULTI, PERMISSIVE, UNKNOWN, WEAK, audit, classify, denylisted,
)


def test_no_forbidden_packages_installed():
    rows = audit()
    bad = [r for r in rows if r.cls == FORBIDDEN]
    assert not bad, "금지(GPL) 패키지 설치됨: " + ", ".join(f"{r.name}({r.license})" for r in bad)


def test_rfc3987_absent():
    assert not denylisted(audit()), "rfc3987 제거 필요: pip uninstall -y rfc3987"


def test_linkml_uri_format_check_survives_without_rfc3987():
    """rfc3987 없이도 jsonschema 'uri' 형식 검사가 살아 있다 (rfc3986-validator 대체)."""
    pytest.importorskip("rfc3986_validator")
    from jsonschema import Draft7Validator, FormatChecker

    v = Draft7Validator({"type": "string", "format": "uri"}, format_checker=FormatChecker())
    assert v.is_valid("https://example.org/a")
    assert not v.is_valid("not a uri with spaces")


@pytest.mark.parametrize("texts, expected", [
    (["MIT"], PERMISSIVE),
    (["Apache-2.0 OR BSD-2-Clause"], PERMISSIVE),
    (["GNU General Public License v3 or later (GPLv3+)"], FORBIDDEN),
    (["GNU Affero General Public License v3"], FORBIDDEN),
    (["GNU Lesser General Public License v2 or later (LGPLv2+)"], WEAK),
    (["Mozilla Public License 2.0 (MPL 2.0)"], WEAK),
    (["BSD License", "GNU General Public License (GPL)", "Public Domain"], MULTI),
    ([], UNKNOWN),
])
def test_classify(texts, expected):
    assert classify(texts) == expected
