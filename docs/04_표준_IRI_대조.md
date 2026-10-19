# 표준 IRI 원본 대조 (2026-10-19, 개발 PC — 인터넷 가능)

제안서 '위험 5'(P-Plan·QUDT IRI 는 기억에 기반) 해소. 사내에서는 할 수 없으므로 여기서 1회 대조하고 결과를 저장소 문서에 남긴다.

## P-Plan (http://purl.org/net/p-plan → https://vocab.linkeddata.es/p-plan/p-plan.owl, 200, 16.7 KB)

쓰는 용어 전부 원본에 선언돼 있음. domain/range 도 시안의 사용 방향과 일치:

| 용어 | 원본 선언 | 시안에서의 사용 | 일치 |
|---|---|---|---|
| p-plan:Plan | ⊑ prov:Entity, ⊑ prov:Plan | wf:Workflow·wf:SubPlan ⊑ | ○ |
| p-plan:Step | 클래스 | wf:Step ⊑ | ○ |
| p-plan:Variable | 클래스 | wf:DataVariable ⊑ | ○ |
| p-plan:MultiStep | ⊑ p-plan:Plan **그리고** ⊑ p-plan:Step | 하위 단계 있는 Step 의 이중 타입 | ○ (MultiStep 은 Plan 이기도 하다 — isDecomposedAsPlan 의 대상 SubPlan 과 별개 개체로 두는 시안 구조와 모순 없음) |
| p-plan:isStepOfPlan | Step → Plan | Step → Workflow | ○ |
| p-plan:isPrecededBy | Step → Step | 파생 선후 (DAG) | ○ |
| p-plan:hasInputVar | Step → Variable (inverse isInputVarOf) | Step → DataVariable | ○ |
| p-plan:isOutputVarOf | Variable → Step (inverse hasOutputVar) | DataVariable → 생산 Step 1개 | ○ |
| p-plan:isVariableOfPlan | Variable → Plan | DataVariable → Workflow | ○ |
| p-plan:isDecomposedAsPlan | MultiStep → Plan | MultiStep → SubPlan | ○ |

참고: p-plan:isSubPlanOfPlan(Plan → Plan)·correspondsToVariable·correspondsToStep 도 있다 — SubPlan ↔ Workflow 관계에 isSubPlanOfPlan 을 더 달 수 있다(선택, W1 검토 결과에 따라).

## QUDT 단위 (https://qudt.org/vocab/unit/<꼬리>, Accept: text/turtle)

units.yaml 의 22개 꼬리 전부 200 (존재하지 않는 꼬리는 404 — NOT-A-UNIT-XYZ 로 확인):
UNITLESS · PERCENT · K · DEG_C · PA · KiloPA · MegaPA · BAR · KiloGM-PER-SEC · M · MilliM · M2 · M-PER-SEC · DEG · REV-PER-MIN · SEC · KiloW · MegaW · N · KiloN · J-PER-KiloGM · J-PER-KiloGM-K.
`qudt:hasUnit`(http://qudt.org/schema/qudt/hasUnit) 200. REV-PER-MIN 의 conversionMultiplier 0.10471975… = units.yaml factor 0.104719755 와 일치.

## PROV-O · SKOS · DCTERMS

prov:Entity·prov:Plan, skos:Concept·broader·notation·note·definition, dcterms:conformsTo·isVersionOf — W3C/DCMI 표준 용어, 모두 존재(널리 쓰이는 핵심 용어라 별도 대조 생략).

## 결론

alignment.ttl·wfo.yaml·units.yaml 의 외부 IRI 에 오타·존재하지 않는 용어 없음. '위험 5' 는 해소. 남는 것은 P-Plan 이 W3C 정식 표준이 아니라는 점(정렬은 파일 하나라 교체 용이)뿐.
