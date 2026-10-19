"""Tool 온톨로지 연결 — 그쪽 RDF(survey.ttl 또는 합성 카탈로그)를 읽기만 한다.

**연결 계약 (두 저장소 사이, 4술어)** — 이 저장소가 Tool 온톨로지에서 읽는 것은 아래 넷뿐이다:
  eg:Tool (rdf:type) · skos:prefLabel / skos:altLabel · eg:status ('활성'·'통합됨'·'폐기') · eg:merged_into
워크플로 쪽은 egid:TOOL-… 노드에 타입·라벨을 쓰지 않는다 (ToolRef 가 wf:ontoTool 로 가리키기만). TOOL ID 는 _plan.yaml 의
tools 표 한 곳에만 사람이 적고(HITL), link-tools 는 후보 CSV 만 낸다 — 빌드는 자동으로 채우지 않는다.
코드: T01 안 쓰는 툴 · X01 TOOL ID 가 카탈로그에 없음 · X02 통합됨·폐기 · X03 연결 당시 이름 ≠ 지금 이름 · X04 미연결+같은 이름 후보 · X05 조사 누락 후보.
"""

from __future__ import annotations

import csv
import difflib
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from rdflib import Graph
from rdflib.namespace import RDF, SKOS

from engenius_wf.checks import ln
from engenius_wf.model import EG
from engenius_wf.report import Report

# 연결 계약 — 이 저장소가 의존하는 Tool 온톨로지 술어 (바뀌면 X 검사가 깨진다)
LINK_PREDICATES = (RDF.type, EG.Tool, SKOS.prefLabel, SKOS.altLabel, EG.status, EG.merged_into)


def tool_norm(s):
    return re.sub(r"[^0-9a-z가-힣]", "", unicodedata.normalize("NFKC", str(s)).lower())


def load_catalog(paths):
    g = Graph()
    for p in paths:
        g.parse(p, format="turtle")
    tools, by_name = {}, defaultdict(set)
    for t in g.subjects(RDF.type, EG.Tool):        # 의존하는 술어 4개: eg:Tool · skos:prefLabel/altLabel · eg:status · eg:merged_into
        tid = str(t).rsplit("/", 1)[-1]
        merged = g.value(t, EG.merged_into)
        pref = g.value(t, SKOS.prefLabel)
        labels = [str(x) for x in list(g.objects(t, SKOS.prefLabel)) + list(g.objects(t, SKOS.altLabel))]
        tools[tid] = {"status": str(g.value(t, EG.status) or "활성"), "merged": str(merged).rsplit("/", 1)[-1] if merged else None,
                      "label": str(pref) if pref else tid}
        for lb in labels:
            by_name[tool_norm(lb)].add(tid)
    return tools, by_name


def check_tools(m, cat, rep: Report):
    used = {t for s in m["step"].values() for t in s.get("tools", [])}
    for k, t in m["tool"].items():
        if k not in used:
            rep.warn("T01", ln(t, "key"), f"툴 '{k}' 를 쓰는 단계가 없다")
    if cat is None:
        return
    tools, by_name = cat
    for k, t in m["tool"].items():
        tid = t.get("tool_id")
        if tid:
            if tid not in tools:
                rep.err("X01", ln(t, "tool_id"), f"툴 '{k}' 의 {tid} 가 Tool 온톨로지에 없다", "카탈로그(survey.ttl)가 최신인지, ID 오타인지 확인")
                continue
            info = tools[tid]
            if info["status"] == "통합됨" and info["merged"]:
                rep.warn("X02", ln(t, "tool_id"), f"툴 '{k}' 의 {tid} 는 {info['merged']}({tools.get(info['merged'], {}).get('label', '?')}) 로 통합됨",
                         f"tool_id 를 {info['merged']} 로 바꾸고 label_at_link 도 갱신")
            elif info["status"] == "폐기":
                rep.warn("X02", ln(t, "tool_id"), f"툴 '{k}' 의 {tid} 는 폐기 상태")
            if t.get("label_at_link") and tool_norm(t["label_at_link"]) != tool_norm(info["label"]):
                rep.warn("X03", ln(t, "label_at_link"), f"툴 '{k}': 연결할 때 이름 '{t['label_at_link']}' ≠ 지금 Tool 온톨로지 이름 '{info['label']}'",
                         "같은 툴인지 확인 (Tool 온톨로지 재적재로 ID 가 바뀌었을 수 있음)")
        elif not t.get("not_in_survey"):
            cand = sorted(by_name.get(tool_norm(t["label"]), set()))
            if cand:
                rep.info("X04", ln(t, "key"), f"툴 '{k}' 미연결 — 같은 이름의 Tool 온톨로지 툴: {', '.join(cand)}", "맞으면 tool_id 에 적는다 (사람이 판정)")
            else:
                rep.info("X05", ln(t, "key"), f"툴 '{k}'({t['label']}) 이 Tool 온톨로지에 없다 — 조사 누락 후보")


def link_tools(m, cat, csv_path: Path):
    """TOOL ID 후보 CSV (근거: 이름 일치 / 비슷한 이름 / 조사 누락 후보) — 엔지니어가 보고 _plan.yaml 에 적는다."""
    tools, by_name = cat
    rows = []
    for k, t in m["tool"].items():
        exact = sorted(by_name.get(tool_norm(t["label"]), set()))
        near = [] if exact else sorted({tid for n in difflib.get_close_matches(tool_norm(t["label"]), list(by_name), n=3, cutoff=0.75)
                                        for tid in by_name[n]})
        basis = "이름 일치 — 확인 후 적기" if exact else ("비슷한 이름 — 같은 툴인지 판정" if near else "없음 — 조사 누락 후보")
        rows.append({"툴 key": k, "적은 이름": t["label"], "지금 tool_id": t.get("tool_id", ""),
                     "후보 TOOL ID": " ".join(exact or near), "후보 이름": " / ".join(tools[x]["label"] for x in exact or near), "근거": basis})
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return rows
