"""레지스트리 — key → 무의미 일련번호 IRI (결정 Q1: YAML 은 사람이 읽는 key, RDF IRI 는 STEP-000001 꼴).

상태 파일은 YAML 폴더 안에 둔다: _registry/ids.csv (kind·key·id·status), _registry/origin.txt (example | real).
예시 레지스트리와 사내 data/real/workflows/ 레지스트리가 구조적으로 섞이지 않게 origin 이 다르면 G01 오류 (방향별 안내).
개명은 renamed_from 으로 옛 key 행을 이어받아 IRI 유지 (G03 참고), YAML 에서 사라진 key 는 폐기 — IRI 재사용 안 함 (G02 경고).

key 하나를 찾는 순서: ① 그 key 의 활성 행 ② renamed_from 의 옛 key 활성 행 (개명, G03) ③ 그 key 의 폐기 행 (되살림, G05 참고) ④ 새 번호.
같은 key 에 폐기 행과 활성 행이 함께 있을 수 있다 (폐기된 key 를 다른 IRI 가 이어받은 경우 — 폐기 행은 기록으로 남긴다).
renamed_from 무결성 (G04 오류): 옛 key 가 아직 YAML 에 있다 · 같은 옛 key 를 둘 이상이 적었다 · (방어) 두 key 가 같은 IRI.
renamed_from 을 잇지 못하는 경우 (G06 경고): 새 key 가 이미 자기 IRI 를 받았는데(빌드 뒤에 renamed_from 을 적음) 옛 key 행이 남아 있다,
또는 옛 key 가 이미 폐기됐다 — 폐기 IRI 를 되살려 잇는 것은 하지 않는다 (Leo 결정 대기).
레지스트리 파일은 빌드 산출이 모두 끝난 뒤에 쓴다 (write_registry — pipeline.run). check·release·link-tools 는 쓰지 않는다.
"""

from __future__ import annotations

import csv
import difflib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from engenius_wf.checks import ln
from engenius_wf.model import KINDS
from engenius_wf.report import Report

FIELDS = ("kind", "key", "id", "status")


def origin_of(src: Path):
    return "real" if "data/real" in src.resolve().as_posix() else "example"


@dataclass
class RegistryState:
    """assign_ids 가 계산한 레지스트리 — 산출이 끝난 뒤 write_registry 로 쓴다."""
    origin: str
    rows: list = field(default_factory=list)
    renames: list = field(default_factory=list)      # (kind, 옛 key, 새 key) — 이번에 renamed_from 으로 이어진 것


def _g01(rep: Report, org_path: Path, recorded: str, org: str):
    if recorded == "real" and org == "example":
        rep.err("G01", str(org_path), "레지스트리 출처가 'real'(실데이터) 인데 이 폴더는 data\\real\\ 밖이다 — 실데이터 레지스트리가 든 폴더는 data\\real\\ 아래에서만 빌드한다",
                "실험은 data\\real\\ 아래 다른 이름의 폴더에 복사해서 하거나, _registry 를 빼고 복사한다 (그러면 일련번호가 새로 붙는다)")
    elif recorded == "example" and org == "real":
        rep.err("G01", str(org_path), "레지스트리 출처가 'example' 인데 이 폴더는 'real' — 예시 레지스트리를 실데이터에 쓰지 않는다",
                "예시를 복사해 시작할 때는 _registry·_released 폴더를 빼고 복사한다")
    else:
        rep.err("G01", str(org_path), f"레지스트리 출처 '{recorded}' 를 모른다 (example 또는 real) — 이 폴더는 '{org}'",
                "origin.txt 를 손으로 고치지 않는다 — 다른 폴더의 _registry 를 복사해 왔는지 확인")


def _check_renames(m, rep: Report) -> bool:
    """renamed_from 무결성 (G04) — 문제가 없으면 True."""
    ok = True
    claimed = defaultdict(list)
    for kind, objs in m.items():
        for k, o in objs.items():
            for old in o.get("renamed_from", []):
                if old == k:
                    rep.err("G04", ln(o, "renamed_from"), f"renamed_from 에 자기 key '{k}' 를 적었다", "renamed_from 에는 예전 key 를 적는다")
                    ok = False
                elif old in objs:
                    rep.err("G04", ln(o, "renamed_from"), f"renamed_from '{old}' 의 옛 key 가 아직 YAML 에 있다 — 두 {kind} 가 한 IRI 를 받게 된다",
                            "복사해 새로 만든 것이면 renamed_from 을 지운다. 개명이면 옛 key 쪽을 지운다")
                    ok = False
                else:
                    claimed[(kind, old)].append(o)
    for (kind, old), objs in claimed.items():
        if len(objs) > 1:
            names = ", ".join(sorted(o["key"] for o in objs))
            for o in objs:
                rep.err("G04", ln(o, "renamed_from"), f"같은 옛 key '{old}' 를 여럿({names})이 renamed_from 으로 적었다 — IRI 는 하나만 이어받는다",
                        "이어받을 하나에만 renamed_from 을 남긴다")
            ok = False
    return ok


def assign_ids(m, src: Path, rep: Report):
    """(key → IRI ID, 폐기 ID 목록, RegistryState) — 문제가 있으면 (None, None, None). 파일은 쓰지 않는다 (write_registry)."""
    reg_dir = src / "_registry"
    reg_path, org_path = reg_dir / "ids.csv", reg_dir / "origin.txt"
    org = origin_of(src)
    if org_path.exists():
        recorded = org_path.read_text(encoding="utf-8").strip()
        if recorded != org:
            _g01(rep, org_path, recorded, org)
            return None, None, None
    if not _check_renames(m, rep):
        return None, None, None
    rows = []
    if reg_path.exists():
        with reg_path.open(encoding="utf-8", newline="") as f:
            rows = [{x: r.get(x, "") for x in FIELDS} for r in csv.DictReader(f)]
    active, dead = {}, defaultdict(list)
    for r in rows:
        if r["status"] == "활성":
            active[(r["kind"], r["key"])] = r
        else:
            dead[(r["kind"], r["key"])].append(r)
    nxt = defaultdict(int)
    for r in rows:
        nxt[r["kind"]] = max(nxt[r["kind"]], int(r["id"].rsplit("-", 1)[-1]))
    before = {id(r) for r in rows}
    state = RegistryState(org, rows)
    ids, used = {}, set()
    for kind, objs in m.items():
        for k, o in objs.items():
            olds = o.get("renamed_from", [])
            r = active.get((kind, k))
            if r is not None:
                for old in olds:                       # 빌드 뒤에 renamed_from 을 적었다 — 이미 자기 IRI 가 있어 잇지 못한다
                    left = active.get((kind, old)) or (dead[(kind, old)][-1] if dead.get((kind, old)) else None)
                    if left is not None and left is not r:
                        rep.warn("G06", ln(o, "renamed_from"),
                                 f"renamed_from '{old}' 을 잇지 못한다 — '{k}' 는 이미 {r['id']} 를 받았다 (옛 key 는 {left['id']}, "
                                 f"{'이번에 폐기' if left['status'] == '활성' else '이미 폐기'})",
                                 "renamed_from 은 key 를 바꾼 뒤 첫 build 전에 적는다 (check 로 먼저 보면 G02 가 미리 알려 준다). "
                                 "지금 IRI 그대로 쓸 것이면 renamed_from 을 지운다")
            else:
                for old in olds:
                    cand = active.get((kind, old))
                    if cand is not None and id(cand) not in used:
                        r = cand
                        del active[(kind, old)]
                        r["key"] = k
                        active[(kind, k)] = r
                        state.renames.append((kind, old, k))
                        rep.info("G03", ln(o, "renamed_from"), f"key 개명 {old} → {k}: IRI {r['id']} 유지")
                        break
                if r is None:
                    for old in olds:
                        if dead.get((kind, old)):
                            rep.warn("G06", ln(o, "renamed_from"),
                                     f"renamed_from '{old}' 을 잇지 못한다 — 옛 key 는 이미 폐기됐다 ({dead[(kind, old)][-1]['id']})",
                                     "폐기된 IRI 는 되살려 잇지 않는다 — 새 IRI 를 받는다. 지금은 renamed_from 을 지워도 된다")
                if r is None and dead.get((kind, k)):
                    r = dead[(kind, k)].pop()
                    active[(kind, k)] = r
                    rep.info("G05", ln(o, "key"), f"{kind} '{k}' 는 폐기됐던 IRI {r['id']} 를 다시 쓴다",
                             "예전의 그것과 다른 것이면 key 를 바꾼다 (같은 key = 같은 IRI)")
                if r is None:
                    nxt[kind] += 1
                    _, pfx, width = KINDS[kind]
                    r = {"kind": kind, "key": k, "id": f"{pfx}-{nxt[kind]:0{width}d}", "status": "활성"}
                    rows.append(r)
                    active[(kind, k)] = r
            r["status"] = "활성"
            used.add(id(r))
            ids[k] = r["id"]
    seen = {}
    for k, i in ids.items():                           # 방어 — 두 key 가 한 IRI 를 받으면 그래프가 조용히 합쳐진다
        if i in seen:
            rep.err("G04", "레지스트리", f"key '{seen[i]}' 와 '{k}' 가 같은 IRI {i} 를 받았다", "_registry/ids.csv 를 손으로 고쳤는지 확인")
            return None, None, None
        seen[i] = k
    new_keys = {(r["kind"], r["key"]) for r in rows if id(r) not in before}
    for r in rows:
        if r["status"] == "활성" and id(r) not in used:
            r["status"] = "폐기"
            kind, k = r["kind"], r["key"]
            near = difflib.get_close_matches(k, [nk for (kd, nk) in new_keys if kd == kind], n=1, cutoff=0.6)
            rep.warn("G02", "레지스트리", f"{kind} '{k}'({r['id']}) 가 YAML 에서 사라짐 → 폐기 (IRI 재사용 안 함)",
                     f"새 key '{near[0]}' 로 개명한 것이면 거기에 renamed_from: {k} — build 하기 전에 적어야 IRI 가 이어진다 "
                     f"(build 하면 '{near[0]}' 가 새 IRI 를 받아 잇지 못한다, G06)" if near else "")
    deprecated = sorted(r["id"] for r in rows if r["status"] == "폐기")
    return ids, deprecated, state


def write_registry(src: Path, state: RegistryState):
    """_registry/origin.txt·ids.csv 쓰기 — 빌드 산출이 모두 끝난 뒤에만 (중간에 실패하면 대장은 그대로)."""
    reg_dir = src / "_registry"
    reg_dir.mkdir(parents=True, exist_ok=True)
    (reg_dir / "origin.txt").write_text(state.origin + "\n", encoding="utf-8", newline="\n")
    with (reg_dir / "ids.csv").open("w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        for r in sorted(state.rows, key=lambda r: (r["kind"], r["id"])):
            w.writerow({x: r[x] for x in FIELDS})
