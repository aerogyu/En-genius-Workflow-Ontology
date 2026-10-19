"""RDF — 작성분(authored)·계산분(derived) 2그래프 + trig. 술어 IRI 는 generated/terms.json 에서 (스키마가 정본).

- 작성 그래프 A: YAML 에 적힌 칸을 그대로 (참조는 레지스트리 IRI 로), key 는 skos:notation.
- 파생 그래프 D: 선후(p-plan:isPrecededBy — 되돌림 간선 제외, 늘 DAG)·P-Plan 이중 타입·변수(DataVariable)·
  루프 몸통·나르는 계약·수렴 뒤 단계·동결 기록(InterfaceRelease)·폐기 IRI(owl:deprecated)·PROV 빌드 기록.
- 루프로 되돌아오는 입력은 p-plan:hasInputVar 가 아니라 wf:loopInputVar (P-Plan 변수 그래프를 DAG 로).
- 하위 계획(SubPlan)은 p-plan:isSubPlanOfPlan 으로 상위 계획(워크플로 또는 위 하위 계획)에 잇는다.
  상위 단계(MultiStep)의 wf:produces·consumes 는 경계 표시 — isOutputVarOf 는 가장 깊은 단계 하나에만.
- 변수·바인딩·항목·묶음·하위 계획 IRI 는 레지스트리 ID 에서 해시로 (재빌드해도 같은 IRI).
"""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, PROV, RDF, RDFS, SKOS, XSD

from engenius_wf.model import EGID, G_AUTH, G_DER, NESTED, PPLAN, QUDT, UNIT, WF, Terms


def h10(*parts):
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()[:10]


def write_rdf(m, flow, ids, deprecated, units, rel_all, sources, T: Terms, cat):
    A, D = Graph(), Graph()
    for g in (A, D):
        for pfx, ns in (("wf", WF), ("egid", EGID), ("p-plan", PPLAN), ("prov", PROV), ("skos", SKOS), ("dcterms", DCTERMS),
                        ("qudt", QUDT), ("unit", UNIT), ("owl", OWL)):
            g.bind(pfx, ns)
    I = lambda k: EGID[ids[k]]  # noqa: E731
    ko = lambda s: Literal(str(s), lang="ko")  # noqa: E731

    def lit(rng, v):
        if rng == "boolean":
            return Literal(bool(v))
        if rng == "integer":
            return Literal(int(v))
        if rng == "float":
            return Literal(float(v), datatype=XSD.float)
        return Literal(str(v))

    REFK = {"Step": "step", "Interface": "interface", "ToolRef": "tool", "Discipline": "discipline", "Component": "component", "Workflow": "plan"}

    def props(node, cls, o, skip=()):
        """YAML 에 적힌 칸을 그대로 RDF 로 (authored 그래프). 참조는 레지스트리 IRI 로."""
        for k, v in o.items():
            if k.startswith("_") or k in skip or k == "key":
                continue
            sl = T.slot(cls, k)
            if sl is None or sl["built"] or NESTED.get((cls, k)):
                continue
            p = URIRef(sl["uri"])
            for x in (v if isinstance(v, list) else [v]):
                if sl["range"] in REFK:
                    A.add((node, p, I(x)))
                elif p == RDFS.label:
                    A.add((node, p, ko(x)))
                else:
                    A.add((node, p, lit(sl["range"], x)))
        A.add((node, RDF.type, T.curi(cls)))
        if "key" in o:
            A.add((node, SKOS.notation, Literal(o["key"])))

    plan_key = next(iter(m["plan"]))
    plan = I(plan_key)
    props(plan, "Workflow", m["plan"][plan_key])
    D.add((plan, RDF.type, PPLAN.Plan)); D.add((plan, RDF.type, PROV.Plan))  # noqa: E702
    for kind, cls in (("discipline", "Discipline"), ("component", "Component")):
        for k, o in m[kind].items():
            props(I(k), cls, o)
            D.add((I(k), RDF.type, SKOS.Concept))
    for k, o in m["tool"].items():
        props(I(k), "ToolRef", o)
        if o.get("tool_id"):
            D.add((I(k), T.uri("ToolRef", "onto_tool"), EGID[o["tool_id"]]))
    # 하위 계획
    subplan = {p: EGID["SPLAN-" + h10(ids[p])] for p in flow["children"] if p is not None}
    for p, sp in subplan.items():
        D.add((sp, RDF.type, T.curi("SubPlan"))); D.add((sp, RDF.type, PPLAN.Plan))  # noqa: E702
        D.add((sp, RDFS.label, ko(m["step"][p]["label"] + " (하위 계획)"))); D.add((sp, SKOS.notation, Literal(p + "-sub")))  # noqa: E702
        up = m["step"][p].get("part_of")                       # 상위 단계가 속한 계획 — P-Plan 소비자가 계획 나무를 따라가게
        D.add((sp, T.uri("SubPlan", "sub_plan_of"), subplan[up] if up else plan))
    # 변수 (워크플로, 계약)
    var = {}
    for ik in m["interface"]:
        if flow["producers"][ik] or flow["consumers"][ik]:
            v = EGID["VAR-" + h10(ids[plan_key], ids[ik])]
            var[ik] = v
            D.add((v, RDF.type, T.curi("DataVariable"))); D.add((v, RDF.type, PPLAN.Variable))  # noqa: E702
            D.add((v, RDFS.label, ko(m["interface"][ik]["label"])))
            D.add((v, DCTERMS.conformsTo, I(ik))); D.add((v, PPLAN.isVariableOfPlan, plan))  # noqa: E702
            for s in flow["real_prod"][ik]:                    # 실제로 만드는 (가장 깊은) 단계 하나만
                D.add((v, PPLAN.isOutputVarOf, I(s)))
    for k, s in m["step"].items():
        n = I(k)
        props(n, "Step", s)
        D.add((n, RDF.type, PPLAN.Step))
        if k in subplan:
            D.add((n, RDF.type, PPLAN.MultiStep)); D.add((n, PPLAN.isDecomposedAsPlan, subplan[k]))  # noqa: E702
        D.add((n, PPLAN.isStepOfPlan, subplan[s["part_of"]] if s.get("part_of") else plan))
        for f, bcls, pfx in (("inputs", "InputBinding", "INB"), ("outputs", "OutputBinding", "OUB")):
            for b in s.get(f, []):
                bn = EGID[f"{pfx}-" + h10(ids[k], ids[b["interface"]])]
                A.add((n, T.uri("Step", f), bn))
                props(bn, bcls, b)
                ik = b["interface"]
                if ik in var:
                    D.add((bn, T.uri(bcls, "variable"), var[ik]))
                if f == "inputs":
                    D.add((n, T.uri("Step", "consumes"), I(ik)))
                    D.add((bn, T.uri("InputBinding", "kind"), Literal(b["_kind"])))
                    if ik in var:
                        D.add((n, T.uri("Step", "loop_input_vars" if b["_kind"] == "루프" else "input_vars"), var[ik]))
                else:
                    D.add((n, T.uri("Step", "produces"), I(ik)))
    for (u, v) in set(flow["data_edges"]) | flow["after_edges"]:
        if (u, v) not in flow["back"]:
            D.add((I(v), PPLAN.isPrecededBy, I(u)))
    for k, i in m["interface"].items():
        n = I(k)
        props(n, "Interface", i)
        D.add((n, T.uri("Interface", "json_schema"), Literal(f"contracts/{k}/{i['version']}.schema.json")))

        def items(owner, lst, scope):
            for o, it in enumerate(lst, 1):
                x = EGID["IFI-" + h10(ids[k], scope, it["name"])]
                A.add((owner, T.uri("Interface", "items"), x))
                props(x, "InterfaceItem", it, skip=("ref",))
                D.add((x, T.uri("InterfaceItem", "order"), Literal(o)))
                if it.get("unit") in units:
                    D.add((x, QUDT.hasUnit, UNIT[units[it["unit"]]["qudt"]]))
                r = it.get("ref")
                if r:
                    A.add((x, T.uri("InterfaceItem", "ref"), EGID["REC-" + h10(ids[k], r)] if r in i["_records"] else I(r)))
        items(n, i["items"], "")
        for rn, r in i["_records"].items():
            rnode = EGID["REC-" + h10(ids[k], rn)]
            A.add((n, T.uri("Interface", "records"), rnode))
            A.add((rnode, RDF.type, T.curi("Record"))); A.add((rnode, T.uri("Record", "name"), Literal(rn)))  # noqa: E702
            if r.get("label"):
                A.add((rnode, RDFS.label, ko(r["label"])))
            items(rnode, r["items"], rn)
        for ver, rel in rel_all.get(k, {}).items():
            rn = EGID["REL-" + h10(ids[k], ver)]
            D.add((rn, RDF.type, T.curi("InterfaceRelease"))); D.add((rn, RDF.type, PROV.Entity))  # noqa: E702
            D.add((rn, RDFS.label, ko(f"{i['label']} {ver} 동결")))
            D.add((rn, OWL.versionInfo, Literal(ver))); D.add((rn, DCTERMS.isVersionOf, n))  # noqa: E702
            D.add((rn, T.uri("InterfaceRelease", "released_at"), Literal(rel["released_at"], datatype=XSD.date)))
            D.add((rn, T.uri("InterfaceRelease", "reason"), Literal(rel["reason"])))
            D.add((rn, T.uri("InterfaceRelease", "json_schema"), Literal(f"contracts/{k}/{ver}.schema.json")))
    for lk, lp in m["loop"].items():
        n = I(lk)
        props(n, "Loop", lp)
        info = flow["loops"].get(lk, {})
        for f, sl in (("members", "members"), ("after_convergence", "after_convergence")):
            for s in info.get(f, []):
                D.add((n, T.uri("Loop", sl), I(s)))
        for c in info.get("carries", []):
            D.add((n, T.uri("Loop", "carries"), I(c)))
    for did in deprecated:
        D.add((EGID[did], OWL.deprecated, Literal(True)))
    now = dt.datetime.now().replace(microsecond=0)
    run = EGID["BUILD-" + now.strftime("%Y%m%dT%H%M%S")]
    D.add((run, RDF.type, PROV.Activity)); D.add((run, PROV.endedAtTime, Literal(now.isoformat(), datatype=XSD.dateTime)))  # noqa: E702
    for name, sha in sources:
        s = EGID["SRC-" + sha[:10]]
        D.add((s, RDF.type, PROV.Entity)); D.add((s, RDFS.label, Literal(name))); D.add((s, DCTERMS.identifier, Literal("sha256:" + sha)))  # noqa: E702
        D.add((run, PROV.used, s))
    return A, D


def write_graphs(out: Path, A: Graph, D: Graph):
    """workflow.ttl (작성) · workflow_derived.ttl (계산) · workflow.trig (named graph 2개 — Fuseki 에 한 번에)."""
    (out / "workflow.ttl").write_text(A.serialize(format="turtle"), encoding="utf-8", newline="\n")
    (out / "workflow_derived.ttl").write_text(D.serialize(format="turtle"), encoding="utf-8", newline="\n")
    ds = Dataset()
    for g, name in ((A, G_AUTH), (D, G_DER)):
        gg = ds.graph(name)
        for t in g:
            gg.add(t)
    (out / "workflow.trig").write_text(ds.serialize(format="trig"), encoding="utf-8", newline="\n")
