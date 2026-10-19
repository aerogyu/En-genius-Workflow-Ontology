"""V4 생성된 SHACL 을 실제 엔진(Jena SHACL — Fuseki 배포본 jar)으로 — 예시(작성 ∪ 파생)는 conforms, 고장 6종 주입은 위반 7건.

Java·Fuseki 가 없으면 skip — FUSEKI_HOME/JAVA_HOME 환경변수, 없으면 개발 PC 배치(<저장소 상위>/tools/…)를 찾는다 (형제 저장소 관례).
"""

from __future__ import annotations

import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, RDFS

from wfhelp import find_jena, shacl

pytestmark = pytest.mark.shacl

WF = "http://en-genius.local/onto/wf/"
EGID = "http://en-genius.local/id/"


@pytest.fixture(scope="module")
def jena():
    t = find_jena()
    if not t:
        pytest.skip("Java·Fuseki 없음 (FUSEKI_HOME/JAVA_HOME 설정 시 실행)")
    return t


@pytest.mark.parametrize("name", ["short", "textbook_nocat"])
def test_examples_conform(built, jena, name):
    conf, res = shacl(built[name].union(), *jena)
    assert conf == [True], res


def test_injected_faults_detected(built, jena):
    g = built["textbook_nocat"].union()
    step = next(g.subjects(RDF.type, URIRef(WF + "Step")))
    g.remove((step, RDFS.label, None))                                              # 1 라벨 삭제
    b = next(g.subjects(RDF.type, URIRef(WF + "InputBinding")))
    g.add((b, URIRef(WF + "transfer"), Literal("이메일")))                           # 2 전달 방법 선택지 밖
    g.add((step, URIRef(WF + "inptus"), URIRef(EGID + "IFC-000001")))               # 3 스키마에 없는 속성 (닫힌 모양)
    g.add((step, URIRef(WF + "discipline"), URIRef(EGID + "CPN-0001")))             # 4 분야 자리에 구성품 (+ 분야 둘)
    lp = next(g.subjects(RDF.type, URIRef(WF + "Loop")))
    g.remove((lp, URIRef(WF + "convergenceNote"), None))                            # 5 수렴 메모 삭제
    item = next(g.subjects(RDF.type, URIRef(WF + "InterfaceItem")))
    g.add((item, URIRef(WF + "fileFormat"), Literal("CSV")))                        # 6 확장자 꼴 (대문자)
    conf, res = shacl(g, *jena)
    assert conf == [False]
    assert sorted(set(res)) == [("convergenceNote", "MinCountConstraintComponent"), ("discipline", "ClassConstraintComponent"),
                                ("discipline", "MaxCountConstraintComponent"), ("fileFormat", "PatternConstraintComponent"),
                                ("inptus", "ClosedConstraintComponent"), ("label", "MinCountConstraintComponent"),
                                ("transfer", "InConstraintComponent")]
    assert len(res) == 7
