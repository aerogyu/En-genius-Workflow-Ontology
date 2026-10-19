"""egid: 유형 접두 — 워크플로 접두(레지스트리·해시·빌드 기록)가 Tool 온톨로지 접두와 겹치지 않는다 (W1 검토 수리, 지적 36).

두 저장소는 같은 egid:(http://en-genius.local/id/) 를 쓰고 유형 접두만 다르다 — 겹치면 Fuseki 한 데이터셋에서 IRI 가 섞인다.
Tool 온톨로지 접두 목록(TOOL_PREFIXES)은 CLAUDE.md·docs/01 5장의 목록과 같다. 형제 저장소가 있으면 그 스키마와도 대조한다 (없으면 skip).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from rdflib import URIRef

from engenius_wf.config import REPO_ROOT
from engenius_wf.model import EGID, HASH_PREFIXES, KINDS, RUN_PREFIXES

WF_PREFIXES = {pfx for _, pfx, _ in KINDS.values()} | set(HASH_PREFIXES) | set(RUN_PREFIXES)
TOOL_PREFIXES = {"TOOL", "USE", "IO", "CAT", "FLD", "LOAD", "FEED", "RECON", "ISO", "HANDOFF"}
SIBLING_SCHEMA = Path(os.environ.get("WF_TOOL_SCHEMA")
                      or REPO_ROOT.parent / "engenius-tool-ontology" / "schema" / "engenius_tool.yaml")


def test_workflow_and_tool_prefixes_do_not_overlap():
    assert WF_PREFIXES & TOOL_PREFIXES == set()


@pytest.mark.parametrize("name", ["short", "textbook_nocat"])
def test_build_uses_only_listed_prefixes(built, name):
    """빌드 출력의 egid: IRI 는 목록에 있는 접두만 쓴다 (TOOL = ToolRef.onto_tool 이 가리키는 Tool 온톨로지 IRI)."""
    base = str(EGID)
    used = {str(x)[len(base):].split("-")[0] for t in built[name].union() for x in t if isinstance(x, URIRef) and str(x).startswith(base)}
    assert used <= WF_PREFIXES | {"TOOL"}, used - WF_PREFIXES


def test_sibling_tool_schema_prefixes():
    """형제 저장소 스키마의 id 패턴 접두 = 문서의 목록, 그리고 워크플로 접두와 겹침 0 (읽기만)."""
    if not SIBLING_SCHEMA.is_file():
        pytest.skip(f"형제 저장소 스키마 없음 ({SIBLING_SCHEMA}) — WF_TOOL_SCHEMA 로 지정 가능")
    found = set(re.findall(r"egid:([A-Z]+)-", SIBLING_SCHEMA.read_text(encoding="utf-8")))
    assert found == TOOL_PREFIXES, "Tool 온톨로지 접두가 바뀌었다 — CLAUDE.md·docs/01 5장 목록과 이 테스트를 함께 고친다"
    assert found & WF_PREFIXES == set()
