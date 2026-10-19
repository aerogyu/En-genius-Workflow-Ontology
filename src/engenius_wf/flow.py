"""흐름 계산·검사 (D 데이터 연결 · F 흐름 · L 루프).

- 선후는 데이터에서 계산한다: "B 의 입력 = A 의 출력" 이면 A→B (하위 단계는 같은 묶음 수준으로 올려서 잇는다 — lift).
  순서만 있는 선후는 after. 루프로 되돌아가는 간선(Loop.back_from → back_to)은 선후에 넣지 않는다 → 늘 DAG.
  표시 없는 순환은 오타로 보고 F01 + 'loops 에 back_from·back_to (추정)' 안내.
- 루프 몸통 = back_to 에서 앞으로 가서 back_from 에 닿는 길 위의 단계 + include ('길' 에는 안쪽 루프의 되돌림 간선도 든다).
  나르는 계약 = 되돌아가는 간선의 데이터. 같은 back_to 로 되돌아가는 루프 여럿은 한 반복으로 본다.
  수렴 뒤 단계(afterConvergence) = back_to 의 하류인데 그 반복(같은 back_to 루프 몸통의 합집합) 밖 (루프 안에서 바뀌는 데이터를 받아 수렴 뒤 1회).
  엇갈림(L04) = back_to 가 다른 두 루프의 몸통이 일부만 겹침 — 경고만, 몸통·수렴 뒤는 루프마다 따로 계산.
- 입력 종류: 앞 단계 / 루프 / 외부 / 생산자 없음. 계약의 '실제 생산자' 는 가장 깊은 단계 하나 (상위 단계 선언은 경계 표시).
"""

from __future__ import annotations

from collections import defaultdict

from engenius_wf.checks import ln
from engenius_wf.report import Report, suggest


def ancestors(m, k):
    out, cur, guard = [], m["step"][k].get("part_of"), set()
    while cur and cur in m["step"] and cur not in guard:
        guard.add(cur)
        out.append(cur)
        cur = m["step"][cur].get("part_of")
    return out


def analyse_flow(m, rules, rep: Report):
    steps = m["step"]
    for k in steps:                                          # part_of 순환
        cur, seen = k, []
        while cur and cur in steps:
            if cur in seen:
                rep.err("F02", ln(steps[k], "part_of"), "part_of 가 돌고 돈다: " + " → ".join(seen + [cur]))
                break
            seen.append(cur)
            cur = steps[cur].get("part_of")
    if rep.errors:
        return None
    children = defaultdict(list)
    for k, s in steps.items():
        children[s.get("part_of")].append(k)

    def deepest(ks):
        ks = set(ks)
        return sorted(k for k in ks if not any(k in ancestors(m, d) for d in ks if d != k))

    producers, consumers = defaultdict(list), defaultdict(list)
    for k, s in steps.items():
        outs = [b["interface"] for b in s.get("outputs", [])]
        ins = [b["interface"] for b in s.get("inputs", [])]
        for i in set(outs) & set(ins):
            rep.err("D08", ln(s, "inputs"), f"단계 '{k}' 가 계약 '{i}' 을 받고 내놓기도 한다",
                    "고친 판이면 새 계약(…-v2)으로, 반복이면 loops 로")
        for i in outs:
            producers[i].append(k)
        for i in ins:
            consumers[i].append(k)
    struct_refs = {it["ref"] for i in m["interface"].values() for lst in [i["items"]] + [r["items"] for r in i["_records"].values()]
                   for it in lst if it.get("ref") in m["interface"]}
    real_prod = {}
    for ik, i in m["interface"].items():
        real = deepest(producers[ik])
        real_prod[ik] = real
        if len(real) > 1:
            rep.err("D01", ln(i, "key"), f"계약 '{ik}' 을 만드는 단계가 둘 이상: {', '.join(real)}",
                    "계약 하나에 만드는 단계 하나 — 판이 다르면 계약을 나누세요 (반복이면 loops)")
        if not producers[ik] and not i.get("external") and ik not in struct_refs:
            rep.warn("D02", ln(i, "key"), f"계약 '{ik}' 을 만드는 단계가 없다", "워크플로 밖에서 오면 external: true")
        if producers[ik] and i.get("external"):
            rep.warn("D04", ln(i, "external"), f"external 계약 '{ik}' 을 만드는 단계가 있다: {', '.join(producers[ik])}")
        if not consumers[ik] and not i.get("deliverable") and ik not in struct_refs:
            rep.warn("D03", ln(i, "key"), f"계약 '{ik}' 을 받는 단계가 없다", "최종 산출물이면 deliverable: true")

    def lift(a, b):
        pa, pb = [a] + ancestors(m, a), [b] + ancestors(m, b)
        if a in pb or b in pa:
            return None
        for x in pa:
            for y in pb:
                if steps[x].get("part_of") == steps[y].get("part_of"):
                    return x, y
        return None

    data_edges = defaultdict(set)
    for ik in m["interface"]:
        for p in producers[ik]:
            for c in consumers[ik]:
                if p != c:
                    e = lift(p, c)
                    if e:
                        data_edges[e].add(ik)
    after_edges = set()
    for k, s in steps.items():
        for a in s.get("after", []):
            if steps[a].get("part_of") != s.get("part_of"):
                rep.warn("F04", ln(s, "after"), f"after '{a}' 는 다른 묶음의 단계 — 같은 묶음 안의 선후만 적기를 권장")
            e = lift(a, k)
            if e:
                after_edges.add(e)
                if e in data_edges:
                    rep.info("F05", ln(s, "after"), f"after '{a}' 는 데이터({', '.join(sorted(data_edges[e]))})로 이미 이어져 있다 — 지워도 된다")
    back = {}
    for lk, lp in m["loop"].items():
        f, t = lp["back_from"], lp["back_to"]
        if steps[f].get("part_of") != steps[t].get("part_of"):
            rep.err("L02", ln(lp, "back_from"), f"루프 끝 '{f}' 와 처음 '{t}' 는 같은 묶음(계획)에 있어야 한다")
            continue
        back[(f, t)] = lk
    forward = defaultdict(set)
    for e in set(data_edges) | after_edges:
        if e not in back:
            forward[e[0]].add(e[1])
    color, cycles = {}, []

    def dfs(u, path):
        color[u] = 1
        for v in sorted(forward[u]):
            if color.get(v) == 1:
                cycles.append(path[path.index(v):] + [v])
            elif not color.get(v):
                dfs(v, path + [v])
        color[u] = 2
    indeg = defaultdict(int)
    for u in list(forward):
        for v in forward[u]:
            indeg[v] += 1
    for u in [k for k in steps if not indeg[k]] + list(steps):  # 시작 단계부터 — 되돌아가는 간선 추정이 맞도록
        if not color.get(u):
            dfs(u, [u])
    rev = {(t, f): lk for (f, t), lk in back.items()}
    for cyc in cycles:
        u, v = cyc[-2], cyc[-1]
        hops = cyc[0] + "".join(f" -({','.join(sorted(data_edges.get((a, b), {'순서'})))})→ {b}" for a, b in zip(cyc, cyc[1:]))
        hint = f"반복 루프라면 loops 에 back_from: {u}, back_to: {v} (추정)"
        if (u, v) in rev:
            hint += f" — 루프 '{rev[(u, v)]}' 의 back_from/back_to 가 뒤바뀐 것 같다"
        rep.err("F01", ln(steps[cyc[0]], "key"), "선후가 돌고 돈다: " + hops, hint)
    if cycles:
        return None

    def reach(a, extra=None):
        """a 에서 앞으로 닿는 단계 (a 포함). extra = 길로 더 볼 간선 {from: {to}} (안쪽 루프의 되돌림 간선)."""
        seen, todo = {a}, [a]
        while todo:
            x = todo.pop()
            for y in forward[x] | (extra.get(x, set()) if extra else set()):
                if y not in seen:
                    seen.add(y)
                    todo.append(y)
        return seen
    # 루프 몸통 = 처음(back_to)의 하류 중 끝(back_from)에 닿는 단계 + include. '닿는다' 에는 안쪽 루프(처음이 다르고 두 끝이 모두
    # 이 루프 처음의 하류)의 되돌림 간선도 길로 본다 — 안쪽 루프의 곁가지(예 터빈 1D → 냉각 유량 → 되돌림)도 바깥 반복마다 다시 돈다.
    # 선후(forward·isPrecededBy)와 F01 순환 검사는 지금처럼 되돌림 간선을 전부 뺀 그래프 그대로다 (늘 DAG).
    loops, reach_of = {}, {}
    for (f, t), lk in back.items():
        lp = m["loop"][lk]
        rt = reach(t)
        if f not in rt:
            rep.err("L01", ln(lp, "back_to"), f"루프 처음 '{t}' 에서 앞으로 가서 끝 '{f}' 에 닿는 길이 없다", "back_from/back_to 가 바뀌었나?")
            continue
        inner = defaultdict(set)
        for (f2, t2) in back:
            if t2 != t and t2 in rt and f2 in rt:
                inner[f2].add(t2)
        members = {x for x in rt if f in reach(x, inner)}
        for x in lp.get("include", []):
            if x not in rt:
                rep.err("L09", ln(lp, "include"), f"include '{x}' 는 루프 처음 '{t}' 의 하류가 아니다 — 매 반복 다시 돌 이유가 없다")
            members.add(x)
        reach_of[lk] = rt
        loops[lk] = {"members": sorted(members), "carries": sorted(data_edges.get((f, t), set()))}
    # 같은 처음(back_to)으로 되돌아가는 루프 여럿은 한 반복이다 (예: 압축기·터빈·이차유로 결과가 각각 사이클 해석으로 되돌아옴).
    # 수렴 뒤 단계 = 처음의 하류 중 그 반복(같은 처음 루프 몸통의 합집합) 밖 — 형제 분기 단계를 '수렴 뒤' 로 세지 않는다.
    group = defaultdict(list)
    for (f, t), lk in back.items():
        if lk in loops:
            group[t].append(lk)
    same_head = {}
    for t, lks in group.items():
        union = set().union(*(loops[lk]["members"] for lk in lks))
        for lk in lks:
            loops[lk]["after_convergence"] = sorted(reach_of[lk] - union)
            same_head[lk] = (sorted(x for x in lks if x != lk), union)
    for (f, t), lk in back.items():
        if lk not in loops:
            continue
        lp, info = m["loop"][lk], loops[lk]
        carries, downstream = info["carries"], info["after_convergence"]
        others, union = same_head[lk]
        if not carries:
            rep.warn("L03", ln(lp, "back_to"), "되돌아가는 간선이 나르는 데이터가 없다 (순서만 되돌아감)", f"'{t}' 의 inputs 확인")
        if not lp.get("initial"):
            rep.warn("L07", ln(lp, "key"), "첫 바퀴 값의 출처(initial)가 없다 — 되돌아오는 데이터는 첫 반복에 없다",
                     "예: initial: 첫 바퀴는 설계점 값 (차이 0 가정)")
        prod_in_loop = {b["interface"] for s in union for b in steps[s].get("outputs", [])}     # 같은 반복 안에서 바뀌는 계약
        for mo in lp.get("monitor", []):
            ik, item = mo.split(".", 1)
            if ik not in m["interface"]:
                rep.err("L05", ln(lp, "monitor"), f"monitor '{mo}': 계약 '{ik}' 없음", suggest(ik, m["interface"]))
            elif item not in {it["name"] for it in m["interface"][ik]["items"]}:
                rep.err("L05", ln(lp, "monitor"), f"monitor '{mo}': 항목 '{item}' 없음",
                        suggest(item, [it["name"] for it in m["interface"][ik]["items"]]))
            elif ik not in prod_in_loop:
                rep.warn("L06", ln(lp, "monitor"), f"monitor '{mo}': 루프 몸통이 만드는 계약이 아니다 (반복 중 바뀌지 않음)")
        same = f" · 같은 처음 '{t}' 로 되돌아가는 루프 {others} 와 한 반복 (수렴 뒤 단계는 합쳐서 계산)" if others else ""
        rep.info("L08", ln(lp, "key"), f"루프 '{lk}': 몸통 {info['members']} · 나르는 데이터 {carries} · 수렴 뒤 단계 {downstream or '없음'}{same}")
    # 엇갈림: 처음이 다른 두 루프가 몸통 일부만 겹친다 (같은 처음 루프끼리는 한 반복이라 해당 없음)
    ls = [(lk, m["loop"][lk]["back_to"]) for lk in loops]
    for i in range(len(ls)):
        for j in range(i + 1, len(ls)):
            (la, ta), (lb, tb) = ls[i], ls[j]
            a, b = set(loops[la]["members"]), set(loops[lb]["members"])
            if ta != tb and a & b and not (a <= b or b <= a):
                rep.warn("L04", ln(m["loop"][la], "key"),
                         f"루프 '{la}'(처음 {ta}) 와 '{lb}'(처음 {tb}) 가 엇갈려 겹친다 — 겹치는 단계 {sorted(a & b)} 만 같다",
                         "한 루프가 다른 루프를 통째로 품으면(중첩) 해석이 분명하다 — 바깥 루프 include 에 안쪽 몸통 단계를 더하거나"
                         " (바깥 루프 처음의 하류일 때만, L09) back_to 를 고친다. 따로 도는 반복이면 그대로 둬도 된다 (몸통·수렴 뒤는 루프마다 따로 계산)")
    # 상위 단계 경계
    for p, kids in children.items():
        if p is None:
            continue
        desc, todo = set(), list(kids)
        while todo:
            x = todo.pop()
            desc.add(x)
            todo.extend(children.get(x, []))
        ins = set().union(*[{b["interface"] for b in steps[x].get("inputs", [])} for x in desc])
        outs = set().union(*[{b["interface"] for b in steps[x].get("outputs", [])} for x in desc])
        b_in, b_out = ins - outs, outs - ins
        d_in = {b["interface"] for b in steps[p].get("inputs", [])}
        d_out = {b["interface"] for b in steps[p].get("outputs", [])}
        if (d_in or d_out) and (d_in != b_in or d_out != b_out):
            rep.warn("F03", ln(steps[p], "key"), f"상위 단계 '{p}' 입력·출력이 하위 단계 경계와 다르다 — 선언 in={sorted(d_in)} out={sorted(d_out)}, "
                                                f"하위 경계 in={sorted(b_in)} out={sorted(b_out)}")
    # 고립 단계
    touched = {x for e in set(data_edges) | after_edges for x in e} | set(children) | {k for k, s in steps.items() if s.get("part_of")}
    for k, s in steps.items():
        if k not in touched and len(steps) > 1:
            rep.warn("F06", ln(s, "key"), f"단계 '{k}' 가 어떤 단계와도 이어지지 않는다", "inputs/outputs 또는 after 확인 (밑그림이면 무시)")
    # 입력 종류 (앞 단계 / 루프 / 외부 / 생산자 없음) + 툴·형식 대조
    manual = set(rules["manual_transfer_values"])
    no_transfer = 0
    for k, s in steps.items():
        tools = set(s.get("tools", []))
        for b in s.get("inputs", []):
            ik = b["interface"]
            prods = real_prod.get(ik, [])
            kind = "외부" if m["interface"][ik].get("external") else "생산자 없음"
            for p in prods:
                e = lift(p, k)
                kind = "루프" if e in back else "앞 단계"
            b["_kind"] = kind
            if "transfer" not in b and kind in ("앞 단계", "루프") and not children.get(k):
                no_transfer += 1
        for f in ("inputs", "outputs"):
            for b in s.get(f, []):
                if b.get("tool") and b["tool"] not in tools:
                    rep.warn("D05", ln(s, f), f"{f}.tool '{b['tool']}' 가 단계 '{k}' 의 tools 에 없다")
                fm = b.get("format")
                if fm:
                    fmts = {x for it in m["interface"][b["interface"]]["items"] for x in it.get("formats", [])}
                    if fmts and fm not in fmts:
                        rep.warn("D06", ln(s, f), f"{f} '{b['interface']}' 의 format '{fm}' 이 계약의 file 항목 확장자 {sorted(fmts)} 에 없다")
    if no_transfer:
        rep.info("D07", "전체", f"전달 방법(transfer)을 안 적은 입력 {no_transfer}건 — Tool Agent 후보(수기 구간)를 찾으려면 적어 주세요",
                 f"수기 = {', '.join(manual)}")
    return {"data_edges": data_edges, "after_edges": after_edges, "back": back, "forward": forward, "loops": loops,
            "children": children, "producers": producers, "real_prod": real_prod, "consumers": consumers, "lift": lift}
