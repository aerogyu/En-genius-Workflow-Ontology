"""계약별 JSON Schema (2020-12, 직접 생성) · 골격 예시 · 실제 데이터 검사(validate).

봉투: {contract, version, produced_by, case, iteration, data} — data 는 닫힌 객체, 항목마다 x-unit·x-qudt-unit.
iteration 0 = 첫 바퀴 가정값(Loop.initial). 파일 확장자 검사는 대소문자를 가리지 않는다. 동결된 옛 판의 스키마도 계속 만들고,
동결된 판(현재 판 포함)은 동결본의 정의로 만든다 (품은 계약도 동결본의 스냅샷으로).
코드: C09 골격 예시가 자기 스키마를 통과 못함(경고) · J00 통과 · J01 JSON 읽기 실패(NaN·Infinity·같은 칸 두 번·맨 위가 객체 아님 포함) ·
J02 계약·판 스키마 없음(폴더 이름은 대소문자까지 정확히) · J03 계약 위반.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema

from engenius_wf.checks import ln
from engenius_wf.model import EGID, UNIT
from engenius_wf.report import Report, suggest
from engenius_wf.versioning import canon_def, resolve_ref


def ci_ext(e):
    return "".join(f"[{c.lower()}{c.upper()}]" if c.isalpha() else re.escape(c) for c in e)


def contract_schema(d, m, units, ifc_iri=None, key=None):
    """d = canon_def 꼴 (현재 판 또는 동결본). 봉투(contract·version·produced_by·case·iteration·data) + data 는 닫힌 객체.
    key = 봉투의 계약 key (개명한 계약의 동결본이면 지금 key — 없으면 d 의 key).
    $defs 이름: 이 계약의 묶음 = 묶음 이름(SpeedLine), 품은 다른 계약 = 그 계약 key(+ x-interface 판), 그 계약의 묶음 = '계약key.묶음' —
    두 계약에 같은 이름의 묶음이 있어도 섞이지 않는다. 품은 계약은 동결본의 스냅샷(refs)을 먼저, 없으면 지금 YAML 을 쓴다."""
    defs = {}

    def obj(items, title, scope, pfx):
        props, req = {}, []
        for it in items:
            t = it.get("type", "number")
            if t in ("number", "integer", "string", "boolean"):
                p = {"type": t}
            elif t == "enum":
                p = {"type": "string", "enum": [str(v) for v in it.get("values", [])]}
            elif t == "file":
                exts = it.get("formats") or []
                p = {"type": "string"} | ({"pattern": rf"\.({'|'.join(ci_ext(e) for e in exts)})$"} if exts else {})
            else:
                r = it["ref"]
                got = resolve_ref(scope, r, m)
                if got is None:                       # check_versions(V10)·check_items(C03) 가 먼저 막는다
                    raise KeyError(f"struct ref '{r}' 를 찾을 수 없다")
                kind, x = got
                name = pfx + r if kind == "rec" else r
                if name not in defs:
                    defs[name] = None
                    if kind == "rec":
                        defs[name] = obj(x["items"], x.get("label") or r, scope, pfx)
                    else:
                        defs[name] = obj(x["items"], x["label"], x, r + ".") | {"x-interface": {"key": r, "version": x["version"]}}
                p = {"$ref": f"#/$defs/{name}"}
            for a in ("minimum", "maximum"):
                if it.get(a) is not None:
                    p[a] = it[a]
            if it.get("list"):
                p = {"type": "array", "items": p} | ({"minItems": it["min_items"]} if it.get("min_items") is not None else {})
            meta = {"title": it.get("label") or it["name"]}
            if it.get("description"):
                meta["description"] = it["description"]
            u = it.get("unit")
            if u is not None:
                meta["x-unit"] = u
                if u in units:
                    meta["x-qudt-unit"] = str(UNIT[units[u]["qudt"]])
                    meta["description"] = (meta.get("description", "") + f" [{u}]").strip()
            props[it["name"]] = meta | p
            if it.get("required", True):
                req.append(it["name"])
        return {"type": "object", "title": title, "properties": props, "required": req, "additionalProperties": False}

    data = obj(d["items"], d["label"], d, "")
    key, ver = key or d["key"], d["version"]
    out = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": f"http://en-genius.local/schema/{key}/{ver}.json",
           "title": f"{d['label']} {ver}", "x-interface": {"key": key, "version": ver} | ({"iri": ifc_iri} if ifc_iri else {}),
           "type": "object", "required": ["contract", "version", "data"], "additionalProperties": False,
           "properties": {"contract": {"const": key}, "version": {"const": ver},
                          "produced_by": {"type": "string", "description": "만든 단계 key"},
                          "case": {"type": "string", "description": "사례 이름 (자유)"},
                          "iteration": {"type": "integer", "minimum": 0, "description": "루프 반복 회차 — 0 = 첫 바퀴 가정값(Loop.initial)"},
                          "data": {"$ref": "#/$defs/_data"}},
           "$defs": {"_data": data} | {k: v for k, v in defs.items()}}
    return out


def skeleton(schema):
    defs = schema.get("$defs", {})

    def val(s):
        if "$ref" in s:
            return val(defs[s["$ref"].split("/")[-1]])
        if s.get("type") == "array":
            return [val(s["items"]) for _ in range(max(1, s.get("minItems", 1)))]
        if s.get("type") == "object":
            return {k: val(v) for k, v in s["properties"].items() if k in s.get("required", [])}
        if "enum" in s:
            return s["enum"][0]
        if s.get("type") == "string":
            if "pattern" in s:
                m_ = re.search(r"\(\[(\w)\w\]", s["pattern"])  # noqa: F841  (시안 그대로 — W1 검토 대상)
                ext = re.findall(r"\[(\w)\w\]", s["pattern"].split("|")[0])
                return "example." + "".join(ext) if ext else "example"
            return ""
        if s.get("type") in ("number", "integer"):
            lo = s.get("minimum", 0)
            return lo if s["type"] == "number" else int(lo)
        if s.get("type") == "boolean":
            return False
        return None
    return {"contract": schema["properties"]["contract"]["const"], "version": schema["properties"]["version"]["const"],
            "case": "골격", "data": val(defs["_data"])}


def write_contracts(out: Path, m, ids, units, rel_all, rep: Report) -> int:
    """contracts/<계약>/<판>.schema.json (현재 판 + 동결된 옛 판) + 현재 판의 .example.json. 만든 스키마 수를 돌려준다.
    동결된 판(현재 판 포함)은 동결본의 정의로 만든다 — YAML 이 달라졌으면 V02 가 이미 났다 (수준을 낮춰도 동결 판 스키마는 그대로)."""
    n_schema = 0
    for k, i in m["interface"].items():
        cdir = out / "contracts" / k
        cdir.mkdir(parents=True, exist_ok=True)
        defs = {v: r["def"] for v, r in rel_all.get(k, {}).items()}
        defs.setdefault(i["version"], canon_def(i, m))
        for ver, d in defs.items():
            sch = contract_schema(d, m, units, str(EGID[ids[k]]), key=k)
            jsonschema.Draft202012Validator.check_schema(sch)
            (cdir / f"{ver}.schema.json").write_text(json.dumps(sch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            n_schema += 1
            if ver == i["version"]:
                sk = skeleton(sch)
                errs = list(jsonschema.Draft202012Validator(sch).iter_errors(sk))
                if errs:
                    rep.warn("C09", ln(i, "key"), f"{k}: 골격 예시가 자기 스키마를 통과하지 못함 — {errs[0].message}")
                (cdir / f"{ver}.example.json").write_text(json.dumps(sk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return n_schema


def _strict_pairs(pairs):
    """JSON 객체 — 같은 칸이 두 번이면 거절 (json 기본값은 뒤 값이 조용히 이긴다)."""
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError(f"같은 칸 '{k}' 가 두 번 나온다 (뒤 값이 조용히 이기므로 거절)")
        d[k] = v
    return d


def _no_constant(name):
    """NaN·Infinity 는 JSON 값이 아니다 (RFC 8259) — NaN 은 범위 검사도 통과해 버린다 (비교가 모두 거짓)."""
    raise ValueError(f"{name} 는 JSON 값이 아니다 — 해석기 수렴 실패 값이면 데이터를 만들지 않는다")


def validate_payloads(out: Path, paths, rep: Report):
    cdir = Path(out) / "contracts"
    if not cdir.is_dir():
        rep.err("J02", str(out), "build 출력 폴더가 아니다 (contracts 폴더 없음)", "build 출력 폴더 output\\<시각>_<폴더>\\ 를 준다")
        return
    names = sorted(x.name for x in cdir.iterdir() if x.is_dir())     # 폴더 이름은 정확히 맞춘다 (Windows 는 대소문자를 가리지 않는다)
    for p in map(Path, paths):
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"), object_pairs_hook=_strict_pairs, parse_constant=_no_constant)
        except Exception as ex:  # noqa: BLE001
            rep.err("J01", p.name, f"JSON 읽기 실패 — {ex}")
            continue
        if not isinstance(data, dict):
            rep.err("J01", p.name, "맨 위가 { … } 객체가 아니다", '봉투: {"contract": 계약 key, "version": 판, "data": {…}}')
            continue
        key, ver = data.get("contract"), data.get("version")
        if not isinstance(key, str) or key not in names:
            rep.err("J02", p.name, f"계약 '{key}' 의 스키마가 없다", suggest(key, names))
            continue
        d = cdir / key
        vers = sorted(x.name[: -len(".schema.json")] for x in d.glob("*.schema.json"))
        if not isinstance(ver, str) or ver not in vers:
            rep.err("J02", p.name, f"계약 '{key}' 판 '{ver}' 스키마가 없다 — 있는 판: {', '.join(vers)}")
            continue
        sp = d / f"{ver}.schema.json"
        sch = json.loads(sp.read_text(encoding="utf-8"))
        errs = sorted(jsonschema.Draft202012Validator(sch).iter_errors(data), key=lambda e: list(e.absolute_path))
        for e in errs:
            path = "/".join(map(str, e.absolute_path)) or "(맨 위)"
            if e.validator == "additionalProperties":
                allowed = list(e.schema.get("properties", {}))
                for b in re.findall(r"'([^']+)' was unexpected", e.message):
                    rep.err("J03", p.name, f"{path}: 계약에 없는 칸 '{b}'", suggest(b, allowed))
            elif e.validator == "required":
                rep.err("J03", p.name, f"{path}: 필수 칸 없음 — {e.message.split(' is a')[0]}")
            elif e.validator in ("minimum", "maximum"):
                rep.err("J03", p.name, f"{path}: 범위 밖 {e.instance} ({'최소' if e.validator == 'minimum' else '최대'} {e.validator_value})")
            elif e.validator == "minItems":
                rep.err("J03", p.name, f"{path}: 개수 부족 {len(e.instance)} (최소 {e.validator_value})")
            elif e.validator == "enum":
                rep.err("J03", p.name, f"{path}: 선택지 밖 '{e.instance}' — 허용: {', '.join(e.validator_value)}")
            elif e.validator == "pattern":
                rep.err("J03", p.name, f"{path}: 파일 확장자가 계약과 다르다 '{e.instance}'")
            elif e.validator == "type":
                rep.err("J03", p.name, f"{path}: 형이 틀림 '{e.instance}' ({e.validator_value} 이어야)")
            elif e.validator == "const":
                rep.err("J03", p.name, f"{path}: 값 '{e.instance}' 이 이 스키마와 다르다 (스키마: '{e.validator_value}')")
            else:
                rep.err("J03", p.name, f"{path}: {e.message}")
        if not errs:
            rep.info("J00", p.name, f"통과 ({key} {ver})")
