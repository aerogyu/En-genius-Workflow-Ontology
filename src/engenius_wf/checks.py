"""검사 2·3층 — 모양(S)·참조(R)·단위·항목(U/C)·인명(P).

4층 검사 = ① 읽기(loader, Y) → ② 모양(여기 check_shape, S) → ③ 의미(여기 R·U·C·P + flow 의 D·F·L + versioning 의 V +
tools 의 T·X + registry 의 G) → ④ 산출(contracts 의 C09). 모양이 틀리면 그 자리에서 멈춘다 (연쇄 헛 오류 방지 — pipeline.run).
코드 체계: Y 읽기 · S 모양 · R 참조 · U 단위 · C 항목 · D 데이터 연결 · F 흐름 · L 루프 · V 판 · T/X 툴 · G 레지스트리 · P 인명.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import jsonschema

from engenius_wf.config import GEN_DIR
from engenius_wf.model import KINDS, NESTED, NUMERIC, SECTIONS, Terms
from engenius_wf.report import Report, suggest

KEY_HINT = {"key": "영문 소문자·숫자·하이픈 (예 cmp-meanline)", "renamed_from": "영문 소문자·숫자·하이픈",
            "version": "계약 판은 세 자리 (예 0.1.0)", "name": "영문으로 시작, 영문·숫자·_ (예 W2, PR_c; 묶음 이름은 대문자로 시작)",
            "tool_id": "TOOL-000123 꼴 (Tool 온톨로지 TOOL ID)", "formats": "소문자·점 없이 (csv, cas.h5)",
            "format": "소문자·점 없이 (csv)", "monitor": "계약key.항목 (예 if-perf-od.mismatch)"}
PERSON_FIELDS = {"담당", "담당자", "작성자", "문의", "실무 문의처", "owner_name", "person", "author"}


def shape_validator(gen_dir: Path | None = None):
    """YAML 파일 1개의 모양 검사기 — generated/wfo_file.schema.json(gen-json-schema --closed)의 WorkflowFile."""
    shape = json.loads((Path(gen_dir or GEN_DIR) / "wfo_file.schema.json").read_text(encoding="utf-8"))
    return jsonschema.Draft201909Validator({"$schema": shape["$schema"], "$defs": shape["$defs"], "$ref": "#/$defs/WorkflowFile"})


# =========================================================================== 2층: 모양 검사
def check_shape(fname, data, validator, terms: Terms, rep: Report):
    n0 = len(rep.errors)
    for e in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        node, line = data, getattr(data, "line", 0)
        for k in e.absolute_path:
            try:
                kl = getattr(node, "klines", {}).get(k) if isinstance(node, dict) else None
                il = node.ilines[k] if isinstance(node, list) and k < len(getattr(node, "ilines", [])) else None
                node = node[k]
                line = getattr(node, "line", 0) or kl or il or line
            except (KeyError, IndexError, TypeError):
                break
        path = "/".join(str(x) for x in e.absolute_path)
        field = next((str(x) for x in reversed(list(e.absolute_path)) if isinstance(x, str)), "")
        v = e.validator
        if v == "additionalProperties":
            bad = re.findall(r"'([^']+)' was unexpected", e.message) or re.findall(r"'([^']+)'", e.message)
            allowed = list(e.schema.get("properties", {}).keys())
            for b in bad:
                if b in PERSON_FIELDS:
                    rep.err("S01", (fname, line), f"'{b}' 칸은 둘 수 없다 — 인명은 저장하지 않는다 (절대 규칙 5)")
                else:
                    rep.err("S01", (fname, line), f"모르는 칸 '{b}'" + (f" ({path})" if path else ""), suggest(b, allowed))
        elif v == "required":
            miss = re.findall(r"'([^']+)' is a required property", e.message)
            rep.err("S03", (fname, line), f"{path or '파일'}: 필수 칸 '{', '.join(miss)}' 이 없다")
        elif v == "enum":
            rep.err("S02", (fname, line), f"{path}: '{e.instance}' 는 선택지 밖 — 허용: {', '.join(map(str, e.validator_value))}",
                    suggest(e.instance, e.validator_value))
        elif v == "pattern":
            rep.err("S02", (fname, line), f"{path}: '{e.instance}' 형식이 틀림", KEY_HINT.get(field, f"규칙 {e.validator_value}"))
        elif v == "type":
            want = e.validator_value if isinstance(e.validator_value, str) else "/".join(x for x in e.validator_value if x != "null")
            ko = {"boolean": "참/거짓 (true·false·예·아니오)", "integer": "정수", "number": "숫자", "string": "글자",
                  "array": "목록", "object": "{ … } 묶음"}.get(want, want)
            rep.err("S02", (fname, line), f"{path}: '{e.instance}' — {ko} 이어야 한다")
        elif v in ("minimum", "maximum"):
            rep.err("S02", (fname, line), f"{path}: 값 {e.instance} 이 허용 범위 밖 ({v} {e.validator_value})")
        else:
            rep.err("S02", (fname, line), f"{path}: {e.message}")

    # (빌드) 칸은 적지 않는다
    def walk(cls, d):
        if not isinstance(d, dict):
            return
        for k, val in d.items():
            sl = terms.slot(cls, k)
            if sl and sl.get("built"):
                rep.err("S04", (fname, d.klines.get(k, d.line)), f"'{k}' 는 빌드가 계산하는 칸 — 적지 마세요")
            nested = NESTED.get((cls, k))
            if nested:
                for x in (val if isinstance(val, list) else [val]):
                    walk(nested, x)
    walk("WorkflowFile", data)
    return len(rep.errors) == n0


# =========================================================================== 3층: 합치기·참조·항목
def collect(files, rep: Report):
    m = {k: {} for k in KINDS}
    where, lower = {}, {}
    for fname, data in files:
        head = data.get("discipline")
        for sec, kind in SECTIONS.items():
            objs = data.get(sec)
            if objs is None:
                continue
            objs = [objs] if sec == "plan" else objs
            for o in objs:
                k = o["key"]
                w = (fname, o.line)
                if k in where:
                    rep.err("R02", w, f"key '{k}' 가 이미 {where[k][0]} {where[k][1]}행에 있다 (key 는 모든 파일·종류에서 하나뿐)")
                    continue
                if k.lower() in lower and lower[k.lower()] != k:
                    rep.err("R03", w, f"key '{k}' 와 '{lower[k.lower()]}' 는 대소문자만 다르다")
                where[k], lower[k.lower()] = w, k
                o["_file"], o["_kind"], o["_head"] = fname, kind, head
                if kind in ("step", "interface") and "discipline" not in o and head:
                    o["discipline"] = head
                if kind == "step" and "discipline" not in o:
                    rep.err("R06", w, f"단계 '{k}' 의 분야가 없다", "파일 맨 위에 discipline: 을 적거나 단계에 discipline:")
                m[kind][k] = o
    if len(m["plan"]) != 1:
        rep.err("R04", "전체", f"plan(워크플로 머리)은 정확히 1개여야 한다 — 지금 {len(m['plan'])}개", "보통 _plan.yaml 에 한 번")
    return m, where


def ln(o, k=None):
    """메시지 자리 — (파일, 그 칸의 행 또는 객체의 행)."""
    return (o["_file"], (o.klines.get(k) if k and hasattr(o, "klines") else None) or o.line)


def check_refs(m, rep: Report):
    allkeys = {k: kind for kind in m for k in m[kind]}
    KO = {"step": "단계", "interface": "계약", "tool": "툴", "discipline": "분야", "component": "구성품", "loop": "루프", "plan": "워크플로"}

    def ref(o, field, val, kind):
        if val is None or val in m[kind]:
            return
        if val in allkeys:
            rep.err("R01", ln(o, field), f"{field}: '{val}' 는 {KO[allkeys[val]]} — {KO[kind]} 자리가 아니다",
                    "inputs/outputs 에는 계약, 순서는 after, 툴은 tools" if kind in ("interface", "step") else "")
        else:
            rep.err("R01", ln(o, field), f"{field}: '{val}' 없음", suggest(val, m[kind]))

    for k, s in m["step"].items():
        ref(s, "discipline", s.get("discipline"), "discipline")
        ref(s, "part_of", s.get("part_of"), "step")
        for a in s.get("after", []):
            ref(s, "after", a, "step")
        for c in s.get("components", []):
            ref(s, "components", c, "component")
        for t in s.get("tools", []):
            ref(s, "tools", t, "tool")
        for f in ("inputs", "outputs"):
            for b in s.get(f, []):
                ref(s, f, b["interface"], "interface")
                if b.get("tool"):
                    ref(s, f"{f}.tool", b["tool"], "tool")
        if s.get("discipline") in m["discipline"] and not k.startswith(s["discipline"] + "-"):
            rep.warn("R05", ln(s, "key"), f"단계 key '{k}' 앞부분이 분야 '{s['discipline']}' 와 다르다 (다른 파일에서 복사했나?)",
                     f"권장: {s['discipline']}-…")
    for k, c in m["component"].items():
        ref(c, "broader", c.get("broader"), "component")
    for k, i in m["interface"].items():
        ref(i, "discipline", i.get("discipline"), "discipline")
    for k, lp in m["loop"].items():
        ref(lp, "back_from", lp.get("back_from"), "step")
        ref(lp, "back_to", lp.get("back_to"), "step")
        for x in lp.get("include", []):
            ref(lp, "include", x, "step")


def check_items(m, units, aliases, rep: Report):
    alias_used = defaultdict(int)

    def one_list(owner, scope, items, records):
        seen = set()
        for it in items:
            w = (owner["_file"], it.line)
            nm = it["name"]
            if nm in seen:
                rep.err("C01", w, f"{scope}: 항목 '{nm}' 이 두 번")
            seen.add(nm)
            t, u = it.get("type", "number"), it.get("unit")
            if u is not None:
                if u in aliases:
                    alias_used[(u, aliases[u])] += 1
                    u = it["unit"] = aliases[u]
                elif u not in units:
                    case = [x for x in units if x.lower() == u.lower()]
                    rep.err("U02", w, f"{scope}.{nm}: 모르는 단위 '{u}'",
                            (f"대소문자만 다르다 — {case[0]} (자동으로 고치지 않는다: MPa ≠ mPa)" if case else suggest(u, units))
                            + " / 새 단위면 config/units.yaml 에 한 줄 추가")
            if t in NUMERIC and u is None:
                rep.err("U01", w, f"{scope}.{nm}: {t} 항목에 단위가 없다", "무차원이면 1 (한 줄 형식: '이름: 1 | 설명')")
            if t not in NUMERIC and u is not None:
                rep.warn("U04", w, f"{scope}.{nm}: {t} 항목에 단위 '{u}' — 숫자 항목에만 단위를 적는다")
            if t == "enum" and not it.get("values"):
                rep.err("C02", w, f"{scope}.{nm}: enum 항목에 values 가 없다")
            if t == "struct":
                r = it.get("ref")
                if not r:
                    rep.err("C03", w, f"{scope}.{nm}: struct 항목에 ref(품는 묶음·계약)가 없다")
                elif r not in records and r not in m["interface"]:
                    rep.err("C03", w, f"{scope}.{nm}: ref '{r}' 없음 (이 계약의 묶음 또는 다른 계약 key)",
                            suggest(r, list(records) + list(m["interface"])))
            elif it.get("ref"):
                rep.err("C03", w, f"{scope}.{nm}: ref 는 type struct 에만")
            if t == "file" and not it.get("formats"):
                rep.warn("C06", w, f"{scope}.{nm}: file 항목에 확장자(formats)가 없다 — Tool 온톨로지와 잇는 열쇠", "file:csv 처럼")
            if it.get("minimum") is not None and it.get("maximum") is not None and it["minimum"] > it["maximum"]:
                rep.err("C04", w, f"{scope}.{nm}: minimum > maximum")
            if it.get("min_items") is not None and not it.get("list"):
                rep.warn("C07", w, f"{scope}.{nm}: 목록이 아닌데 min_items")

    for k, i in m["interface"].items():
        recs = {}
        for r in i.get("records", []):
            if r["name"] in recs:
                rep.err("C01", (i["_file"], r.line), f"{k}: 묶음 '{r['name']}' 이 두 번")
            recs[r["name"]] = r
        i["_records"] = recs
        one_list(i, k, i["items"], recs)
        for rn, r in recs.items():
            one_list(i, f"{k}.{rn}", r["items"], recs)
        used = {it.get("ref") for it in i["items"]} | {it.get("ref") for r in recs.values() for it in r["items"]}
        for rn in recs:
            if rn not in used:
                rep.warn("C08", (i["_file"], recs[rn].line), f"{k}: 묶음 '{rn}' 을 쓰는 항목이 없다")
    for (a, b), n in alias_used.items():
        rep.info("U03", "전체", f"단위 별칭 '{a}' 를 '{b}' 로 읽음 ({n}곳)")

    # struct 순환 (묶음·계약이 자기 자신을 품음)
    def refs_of(ik, rn=None):
        i = m["interface"][ik]
        items = i["_records"][rn]["items"] if rn else i["items"]
        for it in items:
            if it.get("type") == "struct" and it.get("ref"):
                r = it["ref"]
                if r in i["_records"]:
                    yield (ik, r)
                elif r in m["interface"]:
                    yield (r, None)

    def walk(node, stack):
        if node in stack:
            k = node[0]
            rep.err("C05", (m["interface"][k]["_file"], m["interface"][k].line),
                    "묶음·계약이 자기 자신을 품는다: " + " → ".join(f"{a}{'.' + b if b else ''}" for a, b in stack + [node]))
            return
        for nx in refs_of(*node):
            walk(nx, stack + [node])

    if not rep.errors:
        for k in m["interface"]:
            walk((k, None), [])


# =========================================================================== 인명 (자유 텍스트 칸 경고)
PERSON_TEXT = ("label", "note", "when", "until", "initial", "description", "not_in_survey")


def person_hit(text, rules) -> bool:
    """자유 텍스트에 인명 유사 표기가 있나 (config/rules.yaml person_patterns) — YAML 칸(P01)·release 사유(V06)가 같이 쓴다."""
    return isinstance(text, str) and any(re.search(p, text) for p in rules["person_patterns"])


def check_person(files, rules, rep: Report):
    pats = [re.compile(p) for p in rules["person_patterns"]]

    def walk(fname, d):
        if isinstance(d, dict):
            for k, v in d.items():
                if k in PERSON_TEXT and isinstance(v, str) and any(p.search(v) for p in pats):
                    rep.warn("P01", (fname, d.klines.get(k, d.line)), f"'{k}' 칸에 인명으로 보이는 표기 (값은 옮기지 않음) — 인명은 적지 않는다")
                walk(fname, v)
        elif isinstance(d, list):
            for x in d:
                walk(fname, x)
    for fname, data in files:
        walk(fname, data)
