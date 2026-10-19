"""공통 어휘(이름공간)·종류표·스키마 용어 — 빌드 런타임은 linkml 을 import 하지 않고 generated/terms.json 만 읽는다
(linkml→curies→pystow 의 홈 폴더 쓰기 부작용 회피, 홈 폴더가 없는 사내 환경에서도 빌드가 돈다)."""

from __future__ import annotations

import json
from pathlib import Path

from rdflib import Namespace, URIRef

from engenius_wf.config import GEN_DIR

WF = Namespace("http://en-genius.local/onto/wf/")
EG = Namespace("http://en-genius.local/onto/")              # Tool 온톨로지 어휘 (읽기만)
EGID = Namespace("http://en-genius.local/id/")              # 두 저장소가 같은 egid: 를 쓰고 유형 접두만 겹치지 않는다
PPLAN = Namespace("http://purl.org/net/p-plan#")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")
G_AUTH = URIRef("http://en-genius.local/graph/workflow")              # 작성분 named graph
G_DER = URIRef("http://en-genius.local/graph/workflow-derived")      # 계산분 named graph

# 종류 → (클래스, IRI 접두, 일련번호 자릿수) — 레지스트리가 key 에 무의미 일련번호를 준다 (Q1)
KINDS = {"plan": ("Workflow", "PLAN", 4), "discipline": ("Discipline", "DSC", 4), "component": ("Component", "CPN", 4),
         "tool": ("ToolRef", "TRF", 4), "step": ("Step", "STEP", 6), "interface": ("Interface", "IFC", 6), "loop": ("Loop", "LOOP", 4)}
# 레지스트리 ID 에서 해시로 만드는 IRI 접두 (rdf.py) · 빌드 기록 접두 — KINDS 와 함께 Tool 온톨로지 egid: 접두와 겹치지 않아야 한다
# (tests/test_prefixes.py 가 빌드 출력이 이 목록 밖 접두를 쓰지 않는지, 형제 저장소가 있으면 겹침 0 인지 본다)
HASH_PREFIXES = ("INB", "OUB", "IFI", "REC", "VAR", "REL", "SPLAN")
RUN_PREFIXES = ("BUILD", "SRC")
# YAML 절 → 종류
SECTIONS = {"plan": "plan", "disciplines": "discipline", "components": "component", "tools": "tool",
            "steps": "step", "interfaces": "interface", "loops": "loop"}
NUMERIC = {"number", "integer"}


class Terms:
    """generated/terms.json — 클래스·슬롯 → RDF IRI·범위·다중값·'(빌드)' 표시."""

    def __init__(self, gen_dir: Path | None = None):
        t = json.loads((Path(gen_dir or GEN_DIR) / "terms.json").read_text(encoding="utf-8"))
        self.cls, self.enums = t["classes"], t["enums"]

    def slot(self, cls, name):
        return self.cls[cls]["slots"].get(name)

    def uri(self, cls, name):
        return URIRef(self.cls[cls]["slots"][name]["uri"])

    def curi(self, cls):
        return URIRef(self.cls[cls]["uri"])


# (클래스, 칸) → 품는 클래스 — 펼치기·모양 검사·RDF 가 같이 쓴다
NESTED = {("WorkflowFile", "plan"): "Workflow", ("Step", "inputs"): "InputBinding", ("Step", "outputs"): "OutputBinding",
          ("Interface", "items"): "InterfaceItem", ("Interface", "records"): "Record", ("Record", "items"): "InterfaceItem"}
for _sec, _kind in SECTIONS.items():
    NESTED[("WorkflowFile", _sec)] = KINDS[_kind][0]
