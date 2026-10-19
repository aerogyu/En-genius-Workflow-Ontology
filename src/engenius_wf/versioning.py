"""계약 판 관리 (결정 Q4) — semver + release 동결(일자·사유) + 필요한 올림 자동 계산 + 옛 판 스키마 유지.

동결본은 YAML 폴더 안 _released/<계약>/<판>.json ({def, released_at, reason} — HITL 승인 기록, 인명 없음).
올림 규칙: MAJOR = 항목 삭제·필수 추가·형/단위/목록/ref 변경·선택→필수·범위 좁힘·선택지 삭제 /
MINOR = 선택 항목 추가·범위 넓힘·선택지 추가·묶음 추가 / PATCH = 이름·설명만 변경.
코드: V01 판 역행 · V02 동결 판 내용 변경 · V03 올림 부족 · V04 '확정' 인데 동결 없음(경고) · V05 올림 내역(참고) · V06 release 입력 오류 · V07 동결 결과.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from engenius_wf.checks import ln
from engenius_wf.report import Report, suggest

ITEM_FIELDS = ("name", "label", "type", "unit", "list", "min_items", "required", "values", "formats", "minimum", "maximum", "ref", "description")


def canon_def(i):
    def it(x):
        d = {k: x.get(k) for k in ITEM_FIELDS if x.get(k) is not None}
        d.setdefault("required", True)
        return d
    return {"key": i["key"], "label": i["label"], "version": i["version"], "items": [it(x) for x in i["items"]],
            "records": [{"name": r["name"], "label": r.get("label"), "items": [it(x) for x in r["items"]]} for r in i.get("records", [])]}


BUMP = {"PATCH": 0, "MINOR": 1, "MAJOR": 2}


def required_bump(old, new):
    why = []

    def cmp(scope, a, b):
        A, B = {x["name"]: x for x in a}, {x["name"]: x for x in b}
        for n in A.keys() - B.keys():
            why.append(("MAJOR", f"{scope}.{n} 삭제(또는 이름 바꿈)"))
        for n in B.keys() - A.keys():
            why.append(("MAJOR" if B[n].get("required", True) else "MINOR", f"{scope}.{n} 추가({'필수' if B[n].get('required', True) else '선택'})"))
        for n in A.keys() & B.keys():
            x, y = A[n], B[n]
            for k in ("type", "unit", "list", "ref"):
                if x.get(k) != y.get(k):
                    why.append(("MAJOR", f"{scope}.{n} {k} {x.get(k)} → {y.get(k)}"))
            if x.get("required", True) != y.get("required", True):
                why.append(("MAJOR" if y.get("required", True) else "MINOR", f"{scope}.{n} 필수 {x.get('required', True)} → {y.get('required', True)}"))
            for k, narrower in (("minimum", lambda o, n_: n_ is not None and (o is None or n_ > o)),
                                ("maximum", lambda o, n_: n_ is not None and (o is None or n_ < o)),
                                ("min_items", lambda o, n_: n_ is not None and (o is None or n_ > o))):
                if x.get(k) != y.get(k):
                    why.append(("MAJOR" if narrower(x.get(k), y.get(k)) else "MINOR", f"{scope}.{n} {k} {x.get(k)} → {y.get(k)}"))
            for k in ("values", "formats"):
                if x.get(k) != y.get(k):
                    rm = set(x.get(k) or []) - set(y.get(k) or [])
                    why.append(("MAJOR" if rm else "MINOR", f"{scope}.{n} {k} {x.get(k)} → {y.get(k)}"))
            for k in ("label", "description"):
                if x.get(k) != y.get(k):
                    why.append(("PATCH", f"{scope}.{n} {k} 변경"))
    cmp(old["key"], old["items"], new["items"])
    ro, rn = {r["name"]: r for r in old["records"]}, {r["name"]: r for r in new["records"]}
    for r in ro.keys() & rn.keys():
        cmp(f"{old['key']}.{r}", ro[r]["items"], rn[r]["items"])
    why += [("MINOR", f"묶음 {r} 추가") for r in rn.keys() - ro.keys()] + [("MAJOR", f"묶음 {r} 삭제") for r in ro.keys() - rn.keys()]
    if old["label"] != new["label"]:
        why.append(("PATCH", "계약 이름 변경"))
    return max((BUMP[l] for l, _ in why), default=-1), why


def vt(v):
    return tuple(int(x) for x in v.split("."))


def releases(src: Path, key):
    d = src / "_released" / key
    out = {}
    for p in d.glob("*.json") if d.exists() else []:
        out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    return dict(sorted(out.items(), key=lambda kv: vt(kv[0])))


def check_versions(m, src: Path, rep: Report):
    rel_all = {}
    for k, i in m["interface"].items():
        rel = releases(src, k)
        rel_all[k] = rel
        ver = i["version"]
        if not rel:
            if i.get("status") == "확정":
                rep.warn("V04", ln(i, "status"), f"{k} {ver}: 상태 '확정' 인데 동결본이 없다", f"release.bat {k} 로 동결 (사유를 남김)")
            continue
        last = list(rel)[-1]
        level, why = required_bump(rel[last]["def"], canon_def(i))
        need = {v: n for n, v in BUMP.items()}.get(level)
        txt = "; ".join(w for _, w in why[:4]) + (" …" if len(why) > 4 else "")
        if vt(ver) < vt(last):
            rep.err("V01", ln(i, "version"), f"{k}: 판 {ver} 이 동결본 최신 {last} 보다 낮다")
        elif ver == last:
            if level >= 0:
                rep.err("V02", ln(i, "version"), f"{k} {ver}: 동결된 판의 내용이 바뀌었다 — 판을 올려라 (필요: {need}; {txt})")
        else:
            o, n = vt(last), vt(ver)
            declared = 2 if n[0] > o[0] else 1 if n[1] > o[1] else 0
            if level > declared:
                rep.err("V03", ln(i, "version"), f"{k}: {last} → {ver} 인데 바뀐 내용은 {need} 올림이 필요 ({txt})")
            else:
                rep.info("V05", ln(i, "version"), f"{k}: {last} → {ver} ({txt or '내용 변화 없음'})")
    return rel_all


def do_release(m, src: Path, key, reason, rep: Report):
    if key not in m["interface"]:
        rep.err("V06", "release", f"계약 '{key}' 없음", suggest(key, m["interface"]))
        return
    if not reason or not reason.strip():
        rep.err("V06", "release", "동결 사유(--reason)가 필요하다 (HITL 기록 — 인명 금지)")
        return
    i = m["interface"][key]
    p = src / "_released" / key / f"{i['version']}.json"
    data = {"def": canon_def(i), "released_at": dt.date.today().isoformat(), "reason": reason.strip()}
    if p.exists():
        old = json.loads(p.read_text(encoding="utf-8"))
        if old["def"] != data["def"]:
            rep.err("V02", "release", f"{key} {i['version']} 동결본이 이미 있고 내용이 다르다 — 판을 올려라")
        else:
            rep.info("V07", "release", f"{key} {i['version']} 은 이미 동결됨 ({old['released_at']})")
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    rep.info("V07", "release", f"{key} {i['version']} 동결 → {p.relative_to(src).as_posix()} (사유: {reason.strip()})")
