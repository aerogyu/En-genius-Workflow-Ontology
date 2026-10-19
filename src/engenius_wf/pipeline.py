"""빌드 파이프라인 — 검사 4층 + 생성 (build·check·release·link-tools 가 같이 쓴다).

  ① 읽기(loader) → ② 펼치기(normalize) + 모양(checks.check_shape) — 모양이 틀리면 의미 검사를 하지 않는다 (연쇄 헛 오류 방지)
  → ③ 의미: 참조·항목(checks) → 흐름·루프(flow) → 툴(tools) → 인명(checks) → 레지스트리(registry, 계산만) → 판(versioning)
  → ④ 산출(out 이 있을 때): TTL 2그래프·trig(rdf) · 계약 JSON Schema·골격(contracts) · 그림(html) · canonical.json
  → 산출이 끝난 뒤에만 YAML 폴더의 상태 파일(_registry)을 쓴다.
오류가 있으면 결과 파일을 만들지 않는다. 런타임 의존: pyyaml · jsonschema · rdflib — linkml 은 import 하지 않는다.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engenius_wf.checks import (check_items, check_person, check_refs, check_shape, collect, shape_validator)
from engenius_wf.config import default_overlay_dir, load_rules, load_units
from engenius_wf.contracts import write_contracts
from engenius_wf.flow import analyse_flow
from engenius_wf.html import write_html
from engenius_wf.loader import read_yaml
from engenius_wf.model import SECTIONS, Terms
from engenius_wf.normalize import Normalizer
from engenius_wf.rdf import write_graphs, write_rdf
from engenius_wf.registry import assign_ids, origin_of, write_registry
from engenius_wf.report import Report
from engenius_wf.tools import check_tools, load_catalog
from engenius_wf.versioning import carry_releases, check_versions

AUTO = "auto"


def load_all(src: Path, rep: Report, rules, T: Terms):
    files, sources = [], []
    validator = shape_validator()
    ymls = sorted(src.glob("*.yaml"))
    if not ymls:
        rep.err("Y00", str(src), "YAML 파일이 없다")
    for p in ymls:
        raw = read_yaml(p, rep)
        sources.append((p.name, hashlib.sha256(p.read_bytes()).hexdigest()))
        if raw is None:
            continue
        data = Normalizer(T, rules, rep, p.name).obj("WorkflowFile", raw)
        if check_shape(p.name, data, validator, T, rep):
            files.append((p.name, data))
    return files, sources


def resolve_overlay(src: Path, overlay_dir=AUTO):
    """설정 오버레이 폴더 — 'auto' 면 실데이터 폴더(data/real/…)를 빌드할 때만 data/real/config (있을 때). None 이면 쓰지 않는다."""
    if overlay_dir == AUTO:
        return default_overlay_dir() if origin_of(src) == "real" else None
    return overlay_dir


def run(src: Path, out: Path | None, catalogs, rep: Report, write=True, overlay_dir=AUTO):
    overlay = resolve_overlay(src, overlay_dir)
    rules = load_rules(overlay_dir=overlay)
    rep.levels = rules.get("levels") or {}
    T = Terms()
    files, sources = load_all(src, rep, rules, T)
    if rep.errors:                      # 모양이 틀리면 의미 검사를 하지 않는다 (연쇄 헛 오류 방지)
        return None
    m, _, heads = collect(files, rep)
    if not m["plan"]:                   # _plan.yaml 이 없으면 분야·툴 참조가 줄줄이 '없음' 이 된다 — 원인(R04)만 보이고 멈춘다
        return None
    check_refs(m, rep, heads)
    units, aliases = load_units(overlay_dir=overlay)
    if rep.errors:
        return None
    check_items(m, units, aliases, rep)
    flow = None if rep.errors else analyse_flow(m, rules, rep)
    cat = load_catalog(catalogs) if catalogs else None
    check_tools(m, cat, rep)
    check_person(files, rules, rep)
    ids, deprecated, reg = assign_ids(m, src, rep)          # 계산만 — 쓰기는 산출 뒤. 계약 개명(renamed_from)이면 옛 key 동결본도 읽는다
    rel_all = check_versions(m, src, rep, renames=reg.renames if reg else [])
    if rep.errors or flow is None or ids is None:
        return None
    ctx = {"m": m, "flow": flow, "ids": ids, "units": units, "rules": rules, "rel_all": rel_all, "T": T, "files": files, "cat": cat,
           "overlay": overlay, "registry": reg}
    if out is None:
        return ctx
    out.mkdir(parents=True, exist_ok=True)
    A, D = write_rdf(m, flow, ids, deprecated, units, rel_all, sources, T, cat)
    write_graphs(out, A, D)
    n_schema = write_contracts(out, m, ids, units, rel_all, rep)
    write_html(m, flow, rules, out / "workflow.html")
    canon = {"plan": {k: v for k, v in m["plan"][next(iter(m["plan"]))].items() if not k.startswith("_")}}
    for sec, kind in SECTIONS.items():
        if sec != "plan":
            canon[sec] = [strip_private(o) for o in m[kind].values()]
    (out / "canonical.json").write_text(json.dumps(canon, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    if write:                           # YAML 폴더의 상태 파일은 산출이 모두 끝난 뒤에만 쓴다 (중간에 실패하면 대장은 그대로)
        write_registry(src, reg)
        carry_releases(src, reg.renames)   # 개명한 계약의 동결본을 새 key 폴더로
    ctx.update({"A": A, "D": D, "n_schema": n_schema})
    return ctx


def strip_private(o):
    if isinstance(o, dict):
        return {k: strip_private(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, list):
        return [strip_private(x) for x in o]
    return o
