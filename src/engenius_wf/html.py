"""흐름 그림 HTML — 외부 JS 0 (폐쇄망), 인라인 SVG, 다크 모드.

레인 = 분야, 열 = 위상 층. 데이터 선후는 실선, 순서만은 점선, 수기 전달은 굵은 주황 ✋, 루프는 보라 ↺ (툴팁: 몸통·나르는
계약·수렴 메모·첫 바퀴), 수렴 뒤 단계는 배지. 아래에 루프 표와 계약 표.
"""

from __future__ import annotations

import html as _html
import unicodedata
from collections import defaultdict
from pathlib import Path


def fit(text, px, size):
    """글자 폭을 어림해 상자 폭에 맞게 자른다 (한글·전각 ≈ 1.0em, 그 밖 ≈ 0.58em)."""
    out, w = "", 0.0
    for ch in str(text):
        cw = size * (1.0 if unicodedata.east_asian_width(ch) in "WF" else 0.58)
        if w + cw > px - size:
            return out + "…"
        out, w = out + ch, w + cw
    return out


def write_html(m, flow, rules, path: Path):
    e = _html.escape
    steps = m["step"]
    manual = set(rules["manual_transfer_values"])
    top = [k for k, s in steps.items() if not s.get("part_of")]
    fwd = {u: {v for v in vs if v in top} for u, vs in flow["forward"].items() if u in top}
    layer = {}

    def L(k):
        if k not in layer:
            preds = [u for u in top if k in fwd.get(u, set())]
            layer[k] = 0 if not preds else 1 + max(L(u) for u in preds)
        return layer[k]
    for k in top:
        L(k)
    lanes = [d for d in m["discipline"] if any(steps[k]["discipline"] == d for k in top)]
    cell = defaultdict(list)
    for k in top:
        cell[(steps[k]["discipline"], layer[k])].append(k)
    lane_n = {d: max([len(v) for (dd, _), v in cell.items() if dd == d] + [1]) for d in lanes}
    W, H, GX, GY, LW = 200, 62, 80, 30, 86
    y, lane_y = 34, {}
    for d in lanes:
        lane_y[d] = y
        y += lane_n[d] * (H + GY) + GY
    pos = {}
    for (d, l), ks in cell.items():
        for j, k in enumerate(sorted(ks)):
            pos[k] = (LW + 20 + l * (W + GX), lane_y[d] + GY / 2 + j * (H + GY))
    width, height = LW + 40 + (max(layer.values(), default=0) + 1) * (W + GX), y + 30
    manual_edges = defaultdict(set)
    for k, s in steps.items():
        for b in s.get("inputs", []):
            if b.get("transfer") in manual:
                for p in flow["real_prod"].get(b["interface"], []):
                    ed = flow["lift"](p, k)
                    if ed:
                        manual_edges[ed].add(b["interface"])
    svg = [f'<svg viewBox="0 0 {width} {height}" width="{width}" role="img" aria-label="워크플로 그림">',
           '<defs>' + "".join(f'<marker id="{i}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                              f'<path d="M0,0 L10,5 L0,10 z" class="{c}"/></marker>' for i, c in (("a", "ah"), ("m", "mh"), ("b", "lh"))) + '</defs>']
    for d in lanes:
        svg.append(f'<rect x="0" y="{lane_y[d]}" width="{width}" height="{lane_n[d] * (H + GY) + GY}" class="lane"/>'
                   f'<text x="12" y="{lane_y[d] + 22}" class="lt">{e(m["discipline"][d]["label"])}</text>')
    for (u, v) in sorted(set(flow["data_edges"]) | flow["after_edges"]):
        if u in pos and v in pos and (u, v) not in flow["back"]:
            x1, y1, x2, y2 = pos[u][0] + W, pos[u][1] + H / 2, pos[v][0], pos[v][1] + H / 2
            mx = (x1 + x2) / 2
            data = sorted(flow["data_edges"].get((u, v), []))
            man = (u, v) in manual_edges
            cls, mk = ("ed man", "m") if man else ("ed", "a")
            dash = "" if data else ' stroke-dasharray="5 4"'
            tip = (", ".join(data) or "순서만") + (" — ✋ 수기 전달 (Tool Agent 후보)" if man else "")
            svg.append(f'<path d="M{x1},{y1} C{mx},{y1} {mx},{y2} {x2},{y2}" class="{cls}"{dash} marker-end="url(#{mk})"><title>{e(tip)}</title></path>')
            if man:
                svg.append(f'<text x="{mx}" y="{(y1 + y2) / 2 - 6}" class="mt" text-anchor="middle">✋ 수기</text>')
    for lk, info in flow["loops"].items():
        lp = m["loop"][lk]
        f, t = lp["back_from"], lp["back_to"]
        if f in pos and t in pos:
            x1, y1, x2, y2 = pos[f][0] + W / 2, pos[f][1], pos[t][0] + W / 2, pos[t][1]
            ty = min(y1, y2) - 26
            tip = (f"{lp['label']}\n몸통: {', '.join(info['members'])}\n나르는 데이터: {', '.join(info['carries'])}\n"
                   f"수렴: {lp['until']}\n첫 바퀴: {lp.get('initial', '(없음)')}\n수렴 뒤 단계: {', '.join(info['after_convergence']) or '없음'}")
            svg.append(f'<path d="M{x1},{y1} C{x1},{ty} {x2},{ty} {x2},{y2}" class="lp" marker-end="url(#b)"><title>{e(tip)}</title></path>'
                       f'<text x="{(x1 + x2) / 2}" y="{ty + 2}" class="ll" text-anchor="middle">↺ {e(lp["label"])}</text>')
    after_conv = {s for info in flow["loops"].values() for s in info["after_convergence"]}
    for k in top:
        x, yy = pos[k]
        kids = flow["children"].get(k, [])
        tools = ", ".join(m["tool"][t]["label"] for t in steps[k].get("tools", []) if t in m["tool"]) or \
            ", ".join(sorted({m["tool"][t]["label"] for c in kids for t in steps[c].get("tools", []) if t in m["tool"]}))
        sub = f'<text x="{x + 8}" y="{yy + 53}" class="sub">{e(fit("▸ 하위 " + str(len(kids)) + ": " + ", ".join(steps[c]["label"] for c in kids), W - 60, 11))}</text>' if kids else ""
        badge = f'<text x="{x + W - 8}" y="{yy + H - 7}" class="bd" text-anchor="end">수렴 뒤</text>' if k in after_conv else ""
        ins = "\n".join(f"  ← {b['interface']} ({b.get('_kind', '')}{', ' + b['transfer'] if b.get('transfer') else ''})" for b in steps[k].get("inputs", []))
        outs = "\n".join(f"  → {b['interface']}" for b in steps[k].get("outputs", []))
        svg.append(f'<g tabindex="0"><rect x="{x}" y="{yy}" width="{W}" height="{H}" rx="6" class="st"/>'
                   f'<text x="{x + 8}" y="{yy + 20}" class="sl">{e(fit(steps[k]["label"], W - 16, 12.5))}</text>'
                   f'<text x="{x + 8}" y="{yy + 37}" class="tl">{e(fit(tools, W - 16, 11))}</text>{sub}{badge}'
                   f'<title>{e(k)}\n입력:\n{e(ins)}\n출력:\n{e(outs)}</title></g>')
    svg.append("</svg>")
    rows = []
    for ik, i in m["interface"].items():
        def tr(lst, pre=""):
            return "".join(f"<tr><td><code>{e(pre + it['name'])}</code></td><td>{e(str(it.get('label', '')))}</td>"
                           f"<td>{e(it.get('type', 'number'))}{'[]' if it.get('list') else ''}{' → ' + e(it['ref']) if it.get('ref') else ''}</td>"
                           f"<td>{e(str(it.get('unit', '')))}</td><td>{'필수' if it.get('required', True) else '선택'}</td></tr>" for it in lst)
        body = tr(i["items"]) + "".join(tr(r["items"], f"{rn}.") for rn, r in i["_records"].items())
        rows.append(f"<details><summary><b>{e(i['label'])}</b> <code>{e(ik)}</code> {e(i['version'])}</summary>"
                    f"<div class=tw><table><tr><th>JSON 키</th><th>이름</th><th>형</th><th>단위</th><th>필수</th></tr>{body}</table></div></details>")
    lrows = "".join(f"<tr><td>{e(m['loop'][lk]['label'])}</td><td>{e(', '.join(v['members']))}</td><td>{e(', '.join(v['carries']))}</td>"
                    f"<td>{e(', '.join(v['after_convergence']) or '없음')}</td><td>{e(m['loop'][lk]['until'])}</td><td>{e(m['loop'][lk].get('initial', ''))}</td></tr>"
                    for lk, v in flow["loops"].items())
    css = """:root{--bg:#fff;--fg:#1d1d1f;--lane:#f4f5f7;--lane2:#e3e5ea;--box:#fff;--bd:#5b6b84;--ed:#7a8699;--man:#b45309;--lp:#7c3aed;--mut:#6b7280}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#15171c;--fg:#e8e8ea;--lane:#1d2027;--lane2:#2a2e37;--box:#232733;--bd:#8fa1bf;--ed:#8f9bb0;--man:#f59e0b;--lp:#a78bfa;--mut:#9aa1ad}}
:root[data-theme=dark]{--bg:#15171c;--fg:#e8e8ea;--lane:#1d2027;--lane2:#2a2e37;--box:#232733;--bd:#8fa1bf;--ed:#8f9bb0;--man:#f59e0b;--lp:#a78bfa;--mut:#9aa1ad}
body{background:var(--bg);color:var(--fg);font-family:'Malgun Gothic',system-ui,sans-serif;margin:16px;max-width:100%}
.wrap,.tw{overflow-x:auto}.lane{fill:var(--lane);stroke:var(--lane2)}.lt{fill:var(--mut);font-size:13px;font-weight:600}
.st{fill:var(--box);stroke:var(--bd)}.sl{fill:var(--fg);font-size:12.5px}.tl,.sub{fill:var(--mut);font-size:11px}.bd{fill:var(--lp);font-size:10.5px}
.ed{fill:none;stroke:var(--ed);stroke-width:1.4}.ah{fill:var(--ed)}.man{stroke:var(--man);stroke-width:2.6}.mh{fill:var(--man)}.mt{fill:var(--man);font-size:11px}
.lp{fill:none;stroke:var(--lp);stroke-width:1.8;stroke-dasharray:6 3}.lh{fill:var(--lp)}.ll{fill:var(--lp);font-size:11.5px}
table{border-collapse:collapse;margin:6px 0 12px}td,th{border:1px solid var(--lane2);padding:3px 8px;font-size:13px;text-align:left}"""
    path.write_text(
        f"<!doctype html><html lang=ko><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>워크플로 그림</title><style>{css}</style><h1>{e(next(iter(m['plan'].values()))['label'])}</h1>"
        f"<p>실선 = 데이터로 이어진 선후 (선에 마우스: 계약), 점선 = 순서만, <b style='color:var(--man)'>굵은 주황 ✋</b> = 수기 전달(Tool Agent 후보), "
        f"<b style='color:var(--lp)'>보라 ↺</b> = 반복 루프. 같은 열에 선후 없이 놓인 단계는 병렬. '수렴 뒤' = 루프가 끝난 뒤에 도는 단계.</p>"
        f"<div class=wrap>{''.join(svg)}</div><h2>반복 루프</h2><div class=tw><table><tr><th>루프</th><th>몸통</th><th>나르는 데이터</th>"
        f"<th>수렴 뒤 단계</th><th>수렴 조건</th><th>첫 바퀴</th></tr>{lrows}</table></div><h2>데이터 계약</h2>{''.join(rows)}</html>",
        encoding="utf-8", newline="\n")
