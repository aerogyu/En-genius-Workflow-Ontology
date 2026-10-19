"""V1 스키마 — lint·생성물 드리프트·OWL 정리 결과 / V3 LinkML 검증 (canonical → WorkflowFile).

linkml 은 schema 명령에서만 쓰는 의존성이다 — 이 테스트들만 linkml 을 import 한다 (빌드 런타임은 generated/ 만 읽는다).
"""

from __future__ import annotations

import copy
import json

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from engenius_wf import schema_gen
from engenius_wf.config import GEN_DIR, SCHEMA_FILE

WF = "http://en-genius.local/onto/wf/"
PPLAN = "http://purl.org/net/p-plan#"


@pytest.fixture(scope="module")
def gen():
    """(생성물 이름 → 내용, 지운 외부 주어 트리플 수, lint 문제) — 한 번만 만든다 (linkml 생성기는 느리다)."""
    return schema_gen.generate()


@pytest.fixture(scope="module")
def owl(gen):
    return Graph().parse(data=gen[0]["wfo.owl.ttl"], format="turtle")


def test_lint_clean(gen):
    assert gen[2] == []


def test_generated_files_up_to_date(gen):
    """커밋된 schema/generated/ 가 스키마에서 다시 만든 것과 같다 (python -m engenius_wf schema --check 와 같은 검사)."""
    assert schema_gen.drift(gen[0]) == []
    assert set(gen[0]) == set(schema_gen.FILES)


def test_owl_classes(owl):
    classes = {str(c)[len(WF):] for c in owl.subjects(RDF.type, OWL.Class) if isinstance(c, URIRef) and str(c).startswith(WF)}
    assert classes == {"Workflow", "Discipline", "Component", "ToolRef", "Step", "InputBinding", "OutputBinding", "Interface",
                       "Record", "InterfaceItem", "Loop", "SubPlan", "DataVariable", "InterfaceRelease"}


def test_owl_external_vocab_untouched(gen, owl):
    """gen-owl 이 남의 어휘(P-Plan·PROV·SKOS…)에 쓴 트리플은 지우고, 정렬은 alignment.ttl 의 한 방향 공리만 (역방향 0)."""
    assert gen[1] == 62
    external = {(s, p, o) for s, p, o in owl if isinstance(s, URIRef) and not str(s).startswith(WF)
                and not (p == RDF.type and o == OWL.Ontology)}
    assert external == set()
    assert (URIRef(WF + "Step"), RDFS.subClassOf, URIRef(PPLAN + "Step")) in owl
    assert (URIRef(PPLAN + "Step"), RDFS.subClassOf, URIRef(WF + "Step")) not in owl
    assert (URIRef(WF + "WorkflowFile"), None, None) not in owl


def test_shacl_has_no_yaml_container():
    g = Graph().parse(GEN_DIR / "wfo.shacl.ttl", format="turtle")
    sh = "http://www.w3.org/ns/shacl#"
    targets = {str(o) for o in g.objects(None, URIRef(sh + "targetClass"))}
    assert WF + "WorkflowFile" not in targets
    assert WF + "Step" in targets and WF + "Loop" in targets


def test_terms_built_flags():
    """'(빌드)' 표시 슬롯은 YAML 에 적지 못하고(S04) 빌드가 RDF 에 넣는다."""
    t = json.loads((GEN_DIR / "terms.json").read_text(encoding="utf-8"))
    step = t["classes"]["Step"]["slots"]
    assert step["consumes"]["built"] and step["input_vars"]["built"] and not step["inputs"]["built"]
    assert step["input_vars"]["uri"] == PPLAN + "hasInputVar"
    assert step["loop_input_vars"]["uri"] == WF + "loopInputVar"
    assert t["classes"]["Loop"]["slots"]["after_convergence"]["built"]


# --------------------------------------------------------------------------- V3 LinkML 검증
def _linkml_validate(inst):
    from linkml.validator import validate

    return validate(inst, str(SCHEMA_FILE), target_class="WorkflowFile").results


@pytest.mark.parametrize("name", ["short", "textbook_nocat"])
def test_canonical_passes_linkml(built, name):
    inst = json.loads((built[name].out / "canonical.json").read_text(encoding="utf-8"))
    res = _linkml_validate(inst)
    assert res == [], [r.message[:120] for r in res]


def test_linkml_catches_broken(built):
    """고장 3종 (모르는 칸 · 판 '0.1' · until 누락) 을 LinkML 검증기도 잡는다."""
    bad = copy.deepcopy(json.loads((built["short"].out / "canonical.json").read_text(encoding="utf-8")))
    bad["steps"][0]["owner"] = "누군가"
    bad["interfaces"][0]["version"] = "0.1"
    bad["loops"][0].pop("until")
    assert len(_linkml_validate(bad)) >= 3
