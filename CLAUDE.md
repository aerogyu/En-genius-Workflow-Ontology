# En-Genius 개념설계 워크플로 온톨로지 (오픈소스 트랙)

한화에어로스페이스 엔진 개발 AI 플랫폼 En-Genius 의 두 번째 온톨로지 저장소 — Tool 온톨로지(`C:\EnGenius\engenius-tool-ontology`)의 형제.
분야(성능·압축기·연소기·터빈·냉각·이차유로)별 **단계·툴·단계 사이 데이터 계약(Interface, JSON)** 을 엔지니어가 **분야별 YAML 로 손으로 쓰고**,
명령 하나(`build`)가 검사·RDF(TTL 2그래프)·계약별 JSON Schema·흐름 그림 HTML 을 만든다. 흐름은 순서 + 병렬 + 반복 루프(수렴 조건은 메모).
목적: 워크플로 위의 **수기 전달 구간 = Tool Agent 후보**를 데이터로 뽑고, 계약을 나중에 Tool Agent·MCP 도구의 입출력 서명으로 쓴다.
최종 산출물은 사내 폐쇄망에 반입해 실제 워크플로로 돌릴 **스키마·코드·질의 묶음**이다. 이 PC 에서는 공개 교과서 수준 예시로 만들고 검증만 한다.

## 절대 규칙 (Tool 온톨로지에서 승계 — 이 저장소에 맞춤)

1. **실데이터·사내 워크플로·사내 문서·사내 툴 상세는 이 PC 에 두지 않는다.** 개발과 테스트는 공개 교과서 수준 예시(`workflows/examples/`)와 합성 카탈로그로 한다.
   실데이터로 보이는 내용(사내 단계 이름·계약 사양·툴명·경로)이 들어오면 작업 전에 멈추고 확인한다. Leo 가 채팅에 사내 내용을 적어도 저장소·메모리에 기록하지 않는다.
2. 예시에는 공개 상용 툴 이름(GasTurb, AxSTREAM, ANSYS CFX 등)이나 가상의 이름만 쓴다. 사내 툴명·경로·문서번호·인명·사내 워크플로를 지어내지 않는다. 공개 관례(SAE AS755 스테이션 번호 등)는 쓴다.
3. 실행 환경은 **인터넷이 없는 폐쇄망**이다. 런타임에 외부 네트워크·클라우드·CDN·원격 모델을 호출하지 않는다 (흐름 그림 HTML 도 외부 JS 0). 모든 의존성은 오프라인 wheel 로 설치 가능해야 한다.
4. 의존성은 최소로, **허용형 라이선스(Apache·MIT·BSD 계열)만**. AGPL·GPL 금지. **새 패키지 0 이 원칙** — `requirements.lock` 은 Tool 온톨로지와 같다 (반입 심사를 다시 받지 않으려고).
   새 패키지가 꼭 필요하면 Leo 승인 뒤 Tool 온톨로지 `docs/04_반입목록.md` 기준(라이선스·오프라인 wheel)으로. 전이 의존 `rfc3987`(GPLv3+)은 설치하지 않는다 — `python -m engenius_wf licenses` · `tests/test_license_guard.py` 가 감시한다.
5. **인명은 저장하지 않는다.** 담당자류 칸(담당·담당자·작성자·문의·실무 문의처·owner_name·person·author)은 스키마가 거부(S01), 자유 텍스트의 인명 유사 표기는 P01 경고. 동결 기록(release)도 일자·사유만.
6. 에이전트(코드)는 판정하지 않는다. TOOL ID 연결·루프 수렴 판정·계약 확정(release)은 엔지니어(HITL). 빌드·link-tools 는 후보와 안내만 낸다.
7. `data/real/` 은 git 에 올리지 않는다 (`.gitignore`) — 사내 실 YAML 은 `data/real/workflows/`(그 안의 `_registry`·`_released` 포함), 설정 오버레이는 `data/real/config/`.

## 확정된 결정 (재논의하지 않음 — 근거는 `docs/01_설계.md`)

**Leo 결정 Q1~Q4 (2026-10-19, 전부 권장안)**
- Q1 ID: YAML 은 사람이 읽는 key, RDF IRI 는 레지스트리가 주는 무의미 일련번호(`STEP-000001` 등). 개명은 `renamed_from` 으로 IRI 유지, 사라진 key 는 폐기(재사용 안 함).
- Q2 '계약 하나 = 만드는 단계 하나' — 어기면 오류(D01). 판이 다르면(= 다른 단계가 고친 결과 — 계약 semver 가 아님) 계약을 나누고 반복 갱신은 loops 로. (실제 분야를 써 보고 막히면 from_step 확장 검토)
- Q3 툴 연결은 Tool(제품) 수준 + `Discipline.related_parts` 로 필요할 때 툴사용(파트×툴)으로 좁힌다.
- Q4 계약 판 = semver + release 동결(일자·사유) + 필요한 올림 자동 계산(V02·V03) + 옛 판 스키마 유지. 판 규칙표는 config 로 뺀다(W3 남은 일).

**설계 결정 (제안서, 승인)**
- 루프 = **되돌아가는 간선 1개를 객체로** (back_from → back_to). 몸통·나르는 계약·수렴 뒤 단계(afterConvergence)는 빌드가 계산. 첫 바퀴는 `initial` 메모 + 봉투 `iteration: 0`.
- **선후는 데이터에서 계산**한다 ("B 의 입력 = A 의 출력" 이면 A→B). 되돌림 간선은 선후에 넣지 않아 isPrecededBy 는 늘 DAG. 표시 없는 순환은 F01 + loops 추정 안내. 병렬은 적지 않는다(경로 없는 단계끼리). 순서만은 `after`.
- 루프로 되돌아온 입력은 `p-plan:hasInputVar` 가 아니라 **`wf:loopInputVar`** (P-Plan 변수 그래프도 DAG). 상위 단계(MultiStep)의 입출력은 경계 표시, 생산자는 가장 깊은 단계 하나.
- 상태 파일은 **YAML 폴더 안**: `_registry/ids.csv`·`origin.txt`(example|real, 다르면 G01), `_released/<계약>/<판>.json`. 예시와 사내 상태가 구조적으로 섞이지 않는다.
- 스키마: **LinkML 하나**(`schema/wfo.yaml`)가 YAML 모양 검사·RDF 술어·SHACL 을 만든다. 표준 정렬은 `schema/alignment.ttl` 에 한 방향으로만 (P-Plan·PROV·SKOS, 단위는 QUDT IRI).
  **linkml 은 `schema` 명령에서만 import** — 빌드 런타임은 `schema/generated/` 만 읽는다 (홈 폴더 없는 환경 V11).
- W3C 표준(RDF·OWL·SHACL·SPARQL 1.1)만 — rdflib 와 Fuseki 가 같은 결과 (`tests/test_fuseki.py`). 그래프 저장소는 Tool 온톨로지와 같은 Jena Fuseki (Java 21 + 6.2.0, `C:\EnGenius\tools\`).
- 코드는 설치하지 않고 `PYTHONPATH=src` 로 실행 (경로는 저장소 루트 기준 — `config.REPO_ROOT`). 사내 사용은 **더블클릭 `scripts\*.bat`** (env.bat 이 `PYTHONUTF8=1`).
- 지멘스 Graph Studio PoC 와 무관한 플랜 B 이며, PoC 산출물(OWL/TTL)과 대조할 수 있어야 한다 (P-Plan·PROV 인식 여부는 미확인 — 위험 1).

## 형제 저장소(Tool 온톨로지)와의 관계

- 위치 `C:\EnGenius\engenius-tool-ontology` (GitHub `aerogyu/En-genius-Tool-Ontology`). **이 저장소 작업 중에는 그쪽을 고치지 않는다.** 그쪽 변경(4술어 유지 테스트 등)은 Leo 결정 뒤 그 저장소 세션에서.
  합성 survey.ttl(`output/20260930T230632/survey.ttl`, git 제외)은 교차 테스트가 **읽기만** 한다 (`WF_SURVEY_TTL` 로 바꿀 수 있음, 없으면 skip).
- 툴은 **TOOL ID 로 참조**: `_plan.yaml` 의 tools 표 한 곳에만 `tool_id`(+ `label_at_link` 스냅샷)를 사람이 적는다 (`link-tools` 후보 CSV 를 보고). 단계는 툴 key 로만 부른다.
- **4술어 연결 계약** — 이 저장소가 Tool 온톨로지에서 읽는 것: `eg:Tool` · `skos:prefLabel/altLabel` · `eg:status` · `eg:merged_into` (`src/engenius_wf/tools.py` LINK_PREDICATES).
  워크플로 쪽은 `egid:TOOL-…` 노드에 타입·라벨을 쓰지 않는다. 교차 질의 Q8 은 그 밖의 6술어(usage_tool·automation_if·io_owner·direction·extensions·transfer_method)도 읽는다 — W5 유지 테스트 범위.
- **IRI 공간 `egid:`(`http://en-genius.local/id/`) 공유, 유형 접두는 겹치지 않는다** — Tool: TOOL·USE·IO·CAT·FLD·LOAD·FEED·RECON·ISO·HANDOFF (스키마 id 패턴 10개, FEED·RECON·ISO·HANDOFF 는 파생 — 인스턴스는 M4 부터) /
  워크플로: PLAN·DSC·CPN·TRF·STEP·IFC·LOOP(일련번호) · INB·OUB·IFI·REC·VAR·REL·SPLAN(해시) · BUILD·SRC. 술어 이름공간은 `http://en-genius.local/onto/wf/`. Fuseki 한 데이터셋에 그래프만 나란히 올리면 매핑 없이 조인된다.
- `transfer`(전달 방법) 값 = Tool 온톨로지 '전달 방법' 선택지 5개 + '미상' (짧은 별칭은 `config/rules.yaml`). '메일·수기 전달' = Tool Agent 후보.
- 같은 `requirements.lock`·wheels·Java·Fuseki. 사내 설치는 Tool 온톨로지의 `offline\wheels` 를 그대로 쓴다 (`scripts/setup_offline.bat`, `TOOL_ONTO_DIR`).

## 문서 안내 (필요할 때 읽는다)

- **`docs/03_인수인계.md` — 새 세션은 이것부터** (지금 어디까지 왔나, 환경 살리기, 다음 작업 = W1 결함 목록, 함정 기록, 검증 기록)
- `docs/01_설계.md` — 개념 모델·작성 형식·검사 코드 전체 표·Tool 온톨로지 연결·마일스톤 W0~W6·결정 Q1~Q4·위험·검증 기록 **← 구현 전 필독**
- `docs/02_작성안내.md` — 메모장으로 분야 하나 쓰기 (규칙 5줄·완결 예시·칸 목록·단위·전달 방법·실수 23종 표·결과 읽는 법·VS Code 로 쓰기 1-1장·query.bat 7장). **메시지·칸·단위를 바꾸면 이 문서도 고친다**
- `docs/04_표준_IRI_대조.md` — P-Plan·QUDT·PROV·SKOS IRI 원본 대조 기록 (2026-10-19, 인터넷 되는 개발 PC 에서 1회). 단위를 더하면 여기에 한 줄
- `README_offline.md` — 사내(폐쇄망) 설치·실행 (더블클릭 .bat, 밖으로 가져올 수 있는 것)
- `schema/wfo.yaml` — 스키마 마스터. 고친 뒤 `python -m engenius_wf schema` (드리프트는 `--check`·테스트가 잡음)
- `config/rules.yaml`·`units.yaml` — 전달 방법 별칭·메시지 수준(levels)·인명 패턴·단위 (사내 오버레이 `data/real/config/`, 키 단위 덮어쓰기)
- Tool 온톨로지 `CLAUDE.md`·`reference/엔진개발_지식스키마_v0.2.md` — 상위 원칙 (URI 정책·provenance·보안)

## 현재 상태

- [x] **설계 승인 + Leo 결정 Q1~Q4** (2026-10-19, 전부 권장안 — `docs/01` 7장)
- [x] **W0 골격 (2026-10-19)** — 골격(`4c3de62`) · 시안 이식 `wf_build.py`/`wf_schema.py` → `src/engenius_wf/` 동작 그대로(`bbd4e21`, 시안과 나란히 비교해 출력 같음) ·
  예시 2(short·textbook)+합성 카탈로그+질의 q01~q08(`102b5a8`) · 시안 검증 V1~V12 를 pytest 로(`0cd1f6e`) · .bat 10개 + `scripts/bat_helper.py`(`1120b69`) · 문서·이 파일.
  pytest 156 통과 skip 0 (Java·Fuseki·형제 합성 survey.ttl 있을 때). 깨끗한 복사본에서 setup_offline → build → selftest PASS. 새 wheel 0.
- [~] **W1 검토 + 작성 형식 ← 진행 중** — **독립 검토 지적 40건(같은 것 4쌍) 수리 완료 (2026-10-20, `docs/03` 4-0)**: 루프 여럿(같은 back_to = 한 반복·안쪽 루프 곁가지·L04·배지, `e9431e1`) ·
  생성 OWL·SHACL(객체 속성·versionInfo·머리 하나·생산 단계 하나·isSubPlanOfPlan, `8fd4ecc`) · 레지스트리(G04~G06·G01 방향·산출 뒤 쓰기, `8252536`) ·
  계약 판(품은 계약 스냅샷·개명 승계·동결 판 스키마·V08~V10·사유 인명, `bfe0e7f`) · 항목·validate(C10·C11·NaN·같은 칸 두 번, `88b9c98`) ·
  작성 메시지·그림(U02·R01·R04·Y03·Y04·하위 단계, `4e5cd26`) · 반출 줄·문서(`bd27c74`). pytest 228 통과 skip 0.
  **P-Plan·QUDT IRI 원본 대조 완료** (2026-10-19, `docs/04_표준_IRI_대조.md` — 용어·단위 전부 원본에 존재, 위험 5 해소).
  남은 것: `docs/03` 4-1 미수리 항목(#1·2·4·5·7·10·12·13·15·17~21 — 작음, W2 에서) · 4-0b Leo 결정 거리 6 · 4-0c(OWL API 프로파일 잔여) · 작성 안내 다듬기(Leo 확인 ① 결과 반영).
  끝에 **★ Leo 확인 ①** (멈춤): Leo 가 메모장으로 공개 수준 분야 하나(예: 이차유로)를 써 보고 막힌 곳 모으기 · 분야 key 6개·단위 시작 목록 결정.
  **작성 도움 (2026-10-20, Leo 요청)**: 사내 VS Code 1.90.2 + Red Hat YAML 1.25.0 VSIX(반입, MIT)용 **작성용 JSON Schema** `schema/generated/wfo_authoring.schema.json`
  (`authoring.py`, `schema` 명령이 LinkML + rules.yaml·units.yaml 에서 생성·드리프트 감시, YAML 맨 위 한 줄 `# yaml-language-server: $schema=file:///…`) ·
  `query.bat` (q01~q08 표, `query --table`) · `docs/02` 1-1장. 로더와 묶는 `tests/test_authoring.py` 의 변이 시험이 `transfer: [목록]` traceback 을 찾아 normalize 수리.
  확장 자체로 연 확인은 사내에서 처음 (개발 PC 에는 확장 없음 — jsonschema·YAML 1.2 흉내로만).
  **독립 검증 수리 5건 (2026-10-20, `docs/03` 7-3)**: `{ }` 안 쉼표 목록·천 단위 쉼표가 조용히 사라지던 로더 결함 → 값이 빈 모르는 칸도 S01 ·
  값 사이·주석 앞 탭 → Y02(`<탭>` 표시) · `enum:A, B` 도 `[,/]` 로 나눔 · 문서 '빨간 줄' → 노란 물결(확장은 스키마 위반을 경고로, check 에서는 오류) ·
  cmd 직접 명령은 `call scripts\env.bat` 먼저. pytest 404.
- [ ] W2 검사기 + 오류 골든 (실수 주입 30종 이상, rules.yaml 수준 조정 제한)
- [ ] W3 RDF·계약 — V1~V12 는 W0 에서 통과, **판 규칙표 config 화**가 남음
- [ ] W4 그림(클릭 패널·분야 필터)·질의·사내 반입(저장소 zip 첫 반입 + Tool 온톨로지 `build_update.py` 방식 복사 + 설치 판 표식) — 끝에 **★ Leo 확인 ②**
- [ ] W5 Tool 온톨로지 교차 (Tool 온톨로지 M4 뒤 — 사내 survey.ttl 로 link-tools·X 검사·Q8·Q9, 4술어 유지 테스트는 그쪽 저장소·Leo 결정) — 끝에 **★ Leo 확인 ③**
- [ ] W6 (선택) 6분야 교과서 예시·계약 항목 엑셀 가져오기·AS755 공통 항목 사전·PoC 매핑(SSSOM)·MCP 도구·실행 기록(PROV)

마일스톤을 끝낼 때마다 이 체크리스트와 아래 '미확정 사항', `docs/03` 을 갱신한다.

## 저장소 구조

```
schema/          wfo.yaml (LinkML 마스터) · alignment.ttl (표준 정렬, 손으로) · generated/ (terms.json · wfo_file.schema.json · wfo_authoring.schema.json · wfo.shacl.ttl · wfo.owl.ttl · lint.txt)
src/engenius_wf/ cli · config · loader · normalize · checks · flow · registry · versioning · contracts · rdf · html · tools · report · model · pipeline · query · schema_gen · authoring · licenses
config/          rules.yaml · units.yaml (사내 오버레이 data/real/config/)
workflows/examples/  short · textbook (각 폴더 안 _registry·_released) · catalog/tools_synthetic.ttl
queries/         q01~q08.rq (SPARQL 1.1 표준만)
scripts/         env · build · check · validate · release · link_tools · query · schema · doctor · selftest · setup_offline (.bat) + bat_helper.py
tests/           pytest + golden/ (골든은 시안 출력에서) · fixtures/loops/ (루프 여럿 가상 예시) · wfhelp.py (예시 복사·Jena 찾기)
docs/            01_설계 · 02_작성안내 · 03_인수인계
data/real/       (git 제외) 사내에서만 — workflows/ · config/
output/          (git 제외) 실행 결과 output/<시각>_<폴더>/
offline/         (git 제외 파일만) selftest 결과·설치 판 표식·wheels
```

## 코드 규칙

- Python 3.10+. 표준 라이브러리 우선. 런타임 의존은 pyyaml·jsonschema·rdflib 뿐 (linkml 은 `schema` 명령만).
- YAML 은 **엄격하게 읽는다** — `yaml.BaseLoader` 로 모든 값을 글자로, 참/거짓·정수는 스키마상 그 형인 칸에서만 바꾼다. 모든 메시지는 파일·행을 가리킨다.
- 메시지 = 수준(오류·경고·참고) + **코드**(Y·S·R·U·C·D·F·L·V·T/X·G·P·J) + 파일 행 + 문구 + 고치는 법. 새 검사는 코드를 주고 `docs/01` 4장 표·`docs/02` 를 함께 고친다.
  오류가 있으면 결과 파일을 만들지 않는다 (rc 1). 설정 오류는 `[NG] 설정 오류: …` 한 줄 rc 2 (traceback 금지). 사내 반출은 코드별 건수만 (보고서 맨 끝 값 없는 한 줄 `== 코드별 건수 …`).
- 규칙에 쓰이는 값(전달 방법 별칭·수기 값·참거짓 글자·메시지 수준·인명 패턴·단위)은 `config/` 에 둔다 — 사내에서 코드 수정 없이 오버레이로 조정.
- ID 는 레지스트리의 무의미 일련번호(결정 Q1). 사람이 읽는 이름은 `rdfs:label`@ko, key 는 `skos:notation`. 파생 결과는 derived named graph 에 따로, 매번 전체 재계산, provenance(BUILD·SRC·일시).
- 모든 기능은 **rdflib 와 Fuseki 에서 같은 결과**. SPARQL 은 표준 1.1 문법만 (`queries/`).
- Windows·Linux 양쪽에서 돈다 (pathlib, `python -m engenius_wf`). 파일은 UTF-8·LF (`newline="\n"`).
- `.bat` 은 **영어 ASCII + CRLF**, `env.bat` 을 거치고 끝에 `pause`. 인자·경로 판단은 `scripts/bat_helper.py` 에서 (cmd 변수로 경로를 되받지 않는다).
- 테스트는 pytest + 골든 (외부 네트워크 없이). 예시는 임시 폴더에 복사해서 빌드한다 (저장소 `_registry` 를 건드리지 않게). Java·Fuseki·형제 survey.ttl 이 없으면 skip.
- 코드 식별자는 영문, 주석·문서·레이블은 한국어.
- 커밋: `.venv\Scripts\python -m pytest -q -p no:warnings` 녹색 + `git diff --check` 뒤. 한국어 제목 한 줄 + 본문, `git add` 는 경로 지정, 커밋 즉시 `git push origin main`.

## Leo 와 일하는 방식

- 한국어로 소통한다.
- **구조 먼저.** 큰 구현 전에 설계를 짧게 제안하고 확인받는다. **★ Leo 확인 ①(W1 끝)·②(W4 끝)·③(W5 끝)에서는 반드시 멈춘다.**
- 주장은 보수적으로 한다. 확인하지 못한 것(예: QUDT·P-Plan IRI, Protégé, Graph Studio, 사내 실행)은 그렇다고 적는다.
- Leo 는 SAS(이차유로) 도메인 엔지니어로 파이썬에 능숙하고, 시맨틱웹은 입문 단계다. 개념은 DB 비유로 설명한다 (스키마=ERD, YAML=입력 양식, build=ETL, Fuseki=DBMS, SPARQL=SQL, 계약=표 정의).
- 시각 자료를 좋아한다 (흐름 그림). CLI 에 부담을 느낀다 → 사내 사용은 더블클릭 .bat + 한국어 안내.
- 개발 PC 는 집에 있고 원격으로 지시하는 경우가 많다 → 커밋 즉시 push. 변경은 판(v0.1, v0.2 …)으로 쌓는다.

## 미확정 사항 (Leo 에게 확인)

- **분야 key 6개·단위 시작 목록** — 지금 예시: perf·cmp·comb·trb·cool·sas, 단위 23개. W1 Leo 확인 ① 때 정한다.
- **교차 골든 fixture** — textbook 카탈로그 report·q07·q08 골든이 형제 저장소의 git 제외 합성 survey.ttl 에 의존 (사내 selftest 에서는 skip). 합성 fixture 로 이 저장소에 복사할지 (`docs/03` 4-1 #14).
- **4술어 유지 테스트** — Tool 온톨로지 저장소에 넣을지, Q8 의 6술어까지 범위에 넣을지 (W5, 그쪽 저장소 변경이라 Leo 결정).
- **사내 반입 방식 세부** (W4) — 저장소 zip 첫 반입 뒤 업데이트 텍스트 파일(Tool 온톨로지 `build_update.py` 복사)과 설치 판 표식. 그 전까지는 zip 덮어쓰기 (`README_offline.md` 9장).
- **실수 예시의 가명** — 실수 주입 '인명 메모' 사례가 관용 가명 '홍길동 책임' 을 쓴다 (실명 아님). 그대로 둘지 (`docs/03` 4-1 #16).
- **Graph Studio PoC 산출물 대조** — P-Plan·PROV 를 아는지, OWL 을 받아 대조 (위험 1).
- 결정 Q2 의 확장(from_step) 필요 여부 — 실제 분야를 써 본 뒤 (Leo 확인 ①).
- **W1 검토에서 나온 결정 거리** (`docs/03` 4-0b, 권장안 있음): 폐기 IRI 를 renamed_from 으로 되살려 잇기(지금 G06 경고만) · 폐기 key 재사용 시 옛 IRI 되살림(지금 G05 참고) ·
  옛 key 봉투를 validate 가 찾아 줄지 · 품은 계약 key 개명 = MAJOR 유지할지 · 판 규칙 작은 결정(묶음 이름 PATCH·순서 무시·C11 오류 — 권장안으로 넣음) · 루프 back_from 여러 개(권장: 하지 않음).
