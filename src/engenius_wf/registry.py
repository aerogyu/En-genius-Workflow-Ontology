"""레지스트리 — key → 무의미 일련번호 IRI (결정 Q1: YAML 은 사람이 읽는 key, RDF IRI 는 STEP-000001 꼴).

상태 파일은 YAML 폴더 안에 둔다: _registry/ids.csv (kind·key·id·status), _registry/origin.txt (example | real).
예시 레지스트리와 사내 data/real/workflows/ 레지스트리가 구조적으로 섞이지 않게 origin 이 다르면 G01 오류.
개명은 renamed_from 으로 옛 key 행을 이어받아 IRI 유지 (G03 참고), YAML 에서 사라진 key 는 폐기 — IRI 재사용 안 함 (G02 경고).
"""

from __future__ import annotations

import csv
import difflib
from collections import defaultdict
from pathlib import Path

from engenius_wf.checks import ln
from engenius_wf.model import KINDS
from engenius_wf.report import Report


def origin_of(src: Path):
    return "real" if "data/real" in src.resolve().as_posix() else "example"


def assign_ids(m, src: Path, rep: Report, write=True):
    reg_dir = src / "_registry"
    reg_path, org_path = reg_dir / "ids.csv", reg_dir / "origin.txt"
    org = origin_of(src)
    if org_path.exists() and org_path.read_text(encoding="utf-8").strip() != org:
        rep.err("G01", str(org_path), f"레지스트리 출처가 '{org_path.read_text(encoding='utf-8').strip()}' 인데 이 폴더는 '{org}' — 예시 레지스트리를 실데이터에 쓰지 않는다")
        return None, None
    rows = []
    if reg_path.exists():
        with reg_path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    by_key = {(r["kind"], r["key"]): r for r in rows}
    old_keys = set(by_key)
    nxt = defaultdict(int)
    for r in rows:
        nxt[r["kind"]] = max(nxt[r["kind"]], int(r["id"].rsplit("-", 1)[-1]))
    ids = {}
    for kind, objs in m.items():
        for k, o in objs.items():
            r = by_key.get((kind, k))
            if r is None:
                for old in o.get("renamed_from", []):
                    r = by_key.pop((kind, old), None)
                    if r:
                        r["key"] = k
                        by_key[(kind, k)] = r
                        rep.info("G03", ln(o, "renamed_from"), f"key 개명 {old} → {k}: IRI {r['id']} 유지")
                        break
            if r is None:
                nxt[kind] += 1
                _, pfx, width = KINDS[kind]
                r = {"kind": kind, "key": k, "id": f"{pfx}-{nxt[kind]:0{width}d}", "status": "활성"}
                by_key[(kind, k)] = r
            r["status"] = "활성"
            ids[k] = r["id"]
    new_keys = {kk for kk in by_key if kk not in old_keys}
    for (kind, k), r in by_key.items():
        if (kind, k) not in {(kd, kk) for kd, objs in m.items() for kk in objs} and r["status"] == "활성":
            r["status"] = "폐기"
            near = difflib.get_close_matches(k, [nk for (kd, nk) in new_keys if kd == kind], n=1, cutoff=0.6)
            rep.warn("G02", "레지스트리", f"{kind} '{k}'({r['id']}) 가 YAML 에서 사라짐 → 폐기 (IRI 재사용 안 함)",
                     f"새 key '{near[0]}' 로 개명한 것이면 거기에 renamed_from: {k}" if near else "")
    if write:
        reg_dir.mkdir(parents=True, exist_ok=True)
        org_path.write_text(org + "\n", encoding="utf-8", newline="\n")
        with reg_path.open("w", encoding="utf-8", newline="\n") as f:
            w = csv.DictWriter(f, fieldnames=["kind", "key", "id", "status"], lineterminator="\n")
            w.writeheader()
            for r in sorted(by_key.values(), key=lambda r: (r["kind"], r["id"])):
                w.writerow({x: r[x] for x in ("kind", "key", "id", "status")})
    deprecated = sorted(r["id"] for r in by_key.values() if r["status"] == "폐기")
    return ids, deprecated
