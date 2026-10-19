"""계약 판 관리 (결정 Q4) — semver + release 동결(일자·사유) + 필요한 올림 자동 계산 + 옛 판 스키마 유지.

동결본은 YAML 폴더 안 _released/<계약>/<판>.json ({def, released_at, reason} — HITL 승인 기록, 인명 없음).
def 는 계약 정의 정본(canon_def) — 다른 계약을 struct 로 품으면 그 계약의 정의도 통째로 품는다(refs 스냅샷): 품은 계약이 나중에
바뀌어도 동결 판의 스키마는 그대로이고, 바뀐 내용은 품는 쪽의 올림 요구로 전해진다.
올림 규칙: MAJOR = 항목 삭제·필수 추가·형/단위/목록/ref 변경·선택→필수·범위 좁힘·선택지 삭제·묶음 삭제 /
MINOR = 선택 항목 추가·범위 넓힘·선택지 추가·묶음 추가 / PATCH = 계약·항목·묶음 이름(label)·설명만 변경 /
변화 아님 = 항목 순서, 기본값과 같은 명시(list: false·required: true), 계약 key 개명(renamed_from — IRI 가 정체), 판 번호.
품은 계약의 변화는 같은 규칙으로 품는 쪽에 더해진다.
renamed_from 으로 개명한 계약은 옛 key 폴더의 동결본도 이어서 읽고(build 가 새 key 폴더로 옮긴다), 스키마의 봉투 contract 는 지금 key.
코드: V01 판 역행 · V02 동결 판 내용 변경(→ 올릴 판 안내) · V03 올림 부족(→ 올릴 판 안내) · V04 '확정' 인데 이 판의 동결본 없음(경고) ·
V05 올림 내역(참고) · V06 release 입력 오류(계약 없음·사유 없음·사유에 인명) · V07 동결 결과 · V08 동결본을 읽을 수 없음(손상·빈 파일) ·
V09 판 이름이 아닌 파일(경고, 읽지 않음) · V10 동결본이 품은 계약을 찾을 수 없음.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path

from engenius_wf.checks import ln, person_hit
from engenius_wf.report import Report, suggest

ITEM_FIELDS = ("name", "label", "type", "unit", "list", "min_items", "required", "values", "formats", "minimum", "maximum", "ref", "description")
SEMVER = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")


def canon_item(x):
    d = {k: x.get(k) for k in ITEM_FIELDS if x.get(k) is not None}
    d.setdefault("required", True)
    if d.get("list") is False:                   # 기본값과 같은 명시는 적지 않는다 (list: false = 생략)
        del d["list"]
    return d


def cross_refs(d):
    """정의 d 의 항목이 품는 다른 계약 key (자기 묶음이 아닌 ref)."""
    own = {r["name"] for r in d.get("records", [])}
    lists = [d.get("items", [])] + [r.get("items", []) for r in d.get("records", [])]
    return sorted({it["ref"] for lst in lists for it in lst if it.get("ref") and it["ref"] not in own})


def canon_def(i, m=None, _stack=()):
    """계약 정의 정본 — 동결본·판 비교·스키마 생성이 같이 쓴다. m 을 주면 품은 다른 계약의 정의를 refs 에 통째로 넣는다."""
    d = {"key": i["key"], "label": i["label"], "version": i["version"], "items": [canon_item(x) for x in i["items"]],
         "records": [{"name": r["name"], "label": r.get("label"), "items": [canon_item(x) for x in r["items"]]} for r in i.get("records", [])]}
    if m is not None:
        refs = {r: canon_def(m["interface"][r], m, _stack + (i["key"],)) for r in cross_refs(d)
                if r in m["interface"] and r not in _stack and r != i["key"]}
        if refs:
            d["refs"] = refs
    return d


BUMP = {"PATCH": 0, "MINOR": 1, "MAJOR": 2}


def required_bump(old, new):
    """(필요한 올림 수준 -1·0·1·2, [(수준, 사유)]) — 두 정의(canon_def 꼴)를 비교. 항목 순서·key·판 번호는 보지 않는다."""
    why = []

    def norm(x, k):
        if k == "required":
            return x.get("required", True)
        if k == "list":
            return bool(x.get("list", False))
        return x.get(k)

    def cmp(scope, a, b):
        A, B = {x["name"]: x for x in a}, {x["name"]: x for x in b}
        for n in A.keys() - B.keys():
            why.append(("MAJOR", f"{scope}.{n} 삭제(또는 이름 바꿈)"))
        for n in B.keys() - A.keys():
            why.append(("MAJOR" if B[n].get("required", True) else "MINOR", f"{scope}.{n} 추가({'필수' if B[n].get('required', True) else '선택'})"))
        for n in A.keys() & B.keys():
            x, y = A[n], B[n]
            for k in ("type", "unit", "list", "ref"):
                if norm(x, k) != norm(y, k):
                    why.append(("MAJOR", f"{scope}.{n} {k} {norm(x, k)} → {norm(y, k)}"))
            if norm(x, "required") != norm(y, "required"):
                why.append(("MAJOR" if norm(y, "required") else "MINOR", f"{scope}.{n} 필수 {norm(x, 'required')} → {norm(y, 'required')}"))
            for k, narrower in (("minimum", lambda o, n_: n_ is not None and (o is None or n_ > o)),
                                ("maximum", lambda o, n_: n_ is not None and (o is None or n_ < o)),
                                ("min_items", lambda o, n_: n_ is not None and (o is None or n_ > o))):
                if x.get(k) != y.get(k):
                    why.append(("MAJOR" if narrower(x.get(k), y.get(k)) else "MINOR", f"{scope}.{n} {k} {x.get(k)} → {y.get(k)}"))
            for k in ("values", "formats"):
                if set(x.get(k) or []) != set(y.get(k) or []):
                    rm = set(x.get(k) or []) - set(y.get(k) or [])
                    why.append(("MAJOR" if rm else "MINOR", f"{scope}.{n} {k} {x.get(k)} → {y.get(k)}"))
            for k in ("label", "description"):
                if x.get(k) != y.get(k):
                    why.append(("PATCH", f"{scope}.{n} {k} 변경"))

    def walk(scope, o, n):
        cmp(scope, o["items"], n["items"])
        ro, rn = {r["name"]: r for r in o["records"]}, {r["name"]: r for r in n["records"]}
        for r in sorted(ro.keys() & rn.keys()):
            cmp(f"{scope}.{r}", ro[r]["items"], rn[r]["items"])
            if ro[r].get("label") != rn[r].get("label"):
                why.append(("PATCH", f"{scope}.{r} 묶음 이름 변경"))
        why.extend([("MINOR", f"{scope} 묶음 {r} 추가") for r in sorted(rn.keys() - ro.keys())]
                   + [("MAJOR", f"{scope} 묶음 {r} 삭제") for r in sorted(ro.keys() - rn.keys())])
        if o["label"] != n["label"]:
            why.append(("PATCH", f"{scope} 계약 이름 변경"))
        # 품은 계약 — 옛 동결본에 스냅샷이 있을 때만 비교한다 (스냅샷 없는 옛 동결본은 지금 정의를 쓴다)
        oref, nref = o.get("refs") or {}, n.get("refs") or {}
        for r in sorted(oref.keys() & nref.keys()):
            walk(f"{scope}→{r}", oref[r], nref[r])

    walk(old["key"], old, new)
    return max((BUMP[lv] for lv, _ in why), default=-1), why


def vt(v):
    return tuple(int(x) for x in v.split("."))


def next_version(base, level):
    """base 판에서 level(0 PATCH·1 MINOR·2 MAJOR) 만큼 올린 판."""
    a, b, c = vt(base)
    return f"{a + 1}.0.0" if level == 2 else f"{a}.{b + 1}.0" if level == 1 else f"{a}.{b}.{c + 1}"


BUMP_HINT = {2: "MAJOR = 첫 자리 +1 (0.x 도 1.0.0 으로)", 1: "MINOR = 둘째 자리 +1", 0: "PATCH = 셋째 자리 +1"}


def releases(src: Path, key, olds=(), rep: Report | None = None):
    """동결본 {판: {def, released_at, reason}} — _released/<key>/ 와 (개명이면) 옛 key 폴더. 같은 판은 지금 key 폴더가 이긴다.
    판 이름이 아닌 파일은 V09 경고로 건너뛰고, 읽을 수 없는 동결본은 V08 오류 (traceback 없이 파일을 가리킨다)."""
    out = {}
    for kk in (key, *olds):
        d = src / "_released" / kk
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.json")):
            where = f"_released/{kk}/{p.name}"
            if not SEMVER.fullmatch(p.stem):
                if rep is not None:
                    rep.warn("V09", where, "판 이름(예 0.1.0.json)이 아닌 파일 — 동결본으로 읽지 않는다", "복사본·임시 파일이면 지운다")
                continue
            if p.stem in out:
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                ok = (isinstance(data, dict) and isinstance(data.get("def"), dict) and isinstance(data["def"].get("items"), list)
                      and "released_at" in data and "reason" in data)
            except (ValueError, UnicodeDecodeError):
                ok = False
            if not ok:
                if rep is not None:
                    rep.err("V08", where, "동결본을 읽을 수 없다 (빈 파일·손상·형식이 다름)",
                            "그 파일을 지우고 release 로 다시 동결한다 (사유를 다시 적는다)")
                continue
            out[p.stem] = data
    return dict(sorted(out.items(), key=lambda kv: vt(kv[0])))


def renamed_olds(renames, key):
    """레지스트리가 이번에 이은 계약 개명 (옛 key 목록) — 그 폴더의 동결본도 이 계약 것이다."""
    return [old for kind, old, new in (renames or []) if kind == "interface" and new == key]


def resolve_ref(scope, r, m):
    """정의 scope 안의 struct ref r → ('rec', 묶음) | ('ifc', 계약 정의) | None. 품은 계약은 스냅샷(refs) → 지금 YAML 순."""
    own = {x["name"]: x for x in scope.get("records", [])}
    if r in own:
        return "rec", own[r]
    sub = (scope.get("refs") or {}).get(r)
    if sub is None and r in m["interface"]:
        sub = canon_def(m["interface"][r], m)
    return ("ifc", sub) if sub is not None else None


def _missing_refs(d, m, seen=()):
    out = []
    for r in cross_refs(d):
        got = resolve_ref(d, r, m)
        if got is None:
            out.append(r)
        elif got[0] == "ifc" and r not in seen:
            out += _missing_refs(got[1], m, seen + (r,))
    return out


def check_versions(m, src: Path, rep: Report, renames=()):
    rel_all = {}
    for k, i in m["interface"].items():
        rel = releases(src, k, renamed_olds(renames, k), rep)
        rel_all[k] = rel
        ver = i["version"]
        for v, r in rel.items():
            for miss in _missing_refs(r["def"], m):
                rep.err("V10", ln(i, "key"), f"{k} {v} 동결본이 품은 계약 '{miss}' 를 찾을 수 없다 (옛 동결본 — 품은 계약 스냅샷이 없다)",
                        f"'{miss}' 를 개명했으면 renamed_from 과 함께 되돌리거나, 이 판을 다시 동결한다 (release)")
        if i.get("status") == "확정" and ver not in rel:
            rep.warn("V04", ln(i, "status"), f"{k} {ver}: 상태 '확정' 인데 동결본이 없다" + (f" (동결된 판: {', '.join(rel)})" if rel else ""),
                     f"release.bat {k} 로 동결 (사유를 남김)")
        if not rel:
            continue
        last = list(rel)[-1]
        level, why = required_bump(rel[last]["def"], canon_def(i, m))
        need = {v: n for n, v in BUMP.items()}.get(level)
        txt = "; ".join(w for _, w in why[:4]) + (" …" if len(why) > 4 else "")
        hint = f"version: {next_version(last, level)} 로 올린다 ({BUMP_HINT[level]})" if level >= 0 else ""
        if not SEMVER.fullmatch(ver):
            continue                                      # 판 형식 오류는 모양 검사(S02)가 이미 냈다
        if vt(ver) < vt(last):
            rep.err("V01", ln(i, "version"), f"{k}: 판 {ver} 이 동결본 최신 {last} 보다 낮다")
        elif ver == last:
            if level >= 0:
                rep.err("V02", ln(i, "version"), f"{k} {ver}: 동결된 판의 내용이 바뀌었다 — 판을 올려라 (필요: {need}; {txt})", hint)
        else:
            o, n = vt(last), vt(ver)
            declared = 2 if n[0] > o[0] else 1 if n[1] > o[1] else 0
            if level > declared:
                rep.err("V03", ln(i, "version"), f"{k}: {last} → {ver} 인데 바뀐 내용은 {need} 올림이 필요 ({txt})", hint)
            else:
                rep.info("V05", ln(i, "version"), f"{k}: {last} → {ver} ({txt or '내용 변화 없음'})")
    return rel_all


def do_release(m, src: Path, key, reason, rep: Report, rules=None, renames=()):
    if key not in m["interface"]:
        rep.err("V06", "release", f"계약 '{key}' 없음", suggest(key, m["interface"]))
        return
    if not reason or not reason.strip():
        rep.err("V06", "release", "동결 사유(--reason)가 필요하다 (HITL 기록 — 인명 금지)")
        return
    if rules is not None and person_hit(reason, rules):
        rep.err("V06", "release", "동결 사유에 인명으로 보이는 표기가 있다 (값은 옮기지 않음) — 인명·직급은 적지 않는다 (절대 규칙 5)",
                "무엇을 확인했는지만 적는다 (예: 개념설계 1차 검토 통과)")
        return
    i = m["interface"][key]
    data = {"def": canon_def(i, m), "released_at": dt.date.today().isoformat(), "reason": reason.strip()}
    old = releases(src, key, renamed_olds(renames, key)).get(i["version"])
    if old is not None:
        level, why = required_bump(old["def"], data["def"])
        if level >= 0:
            rep.err("V02", "release", f"{key} {i['version']} 동결본이 이미 있고 내용이 다르다 — 판을 올려라 ({'; '.join(w for _, w in why[:4])})",
                    f"version: {next_version(i['version'], level)} 로 올린 뒤 release ({BUMP_HINT[level]})")
        else:
            rep.info("V07", "release", f"{key} {i['version']} 은 이미 동결됨 ({old['released_at']})")
        return
    p = src / "_released" / key / f"{i['version']}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")                    # 쓰다가 실패해도 빈 동결본이 남지 않게 — 임시 파일에 쓴 뒤 바꿔 끼운다
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        os.replace(tmp, p)
    finally:
        if tmp.exists():
            tmp.unlink()
    rep.info("V07", "release", f"{key} {i['version']} 동결 → {p.relative_to(src).as_posix()} (사유: {reason.strip()})")


def carry_releases(src: Path, renames):
    """build(쓰기) 때 — renamed_from 으로 이어진 계약의 동결본을 옛 key 폴더에서 새 key 폴더로 옮긴다 (같은 판이 이미 있으면 그대로 둔다)."""
    for kind, old, new in renames or []:
        if kind != "interface":
            continue
        od, nd = src / "_released" / old, src / "_released" / new
        if not od.is_dir():
            continue
        nd.mkdir(parents=True, exist_ok=True)
        for p in sorted(od.iterdir()):
            q = nd / p.name
            if p.is_file() and not q.exists():
                os.replace(p, q)
        try:
            od.rmdir()                                    # 비었을 때만 지워진다
        except OSError:
            pass
