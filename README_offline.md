# En-Genius 워크플로 온톨로지 — 사내(폐쇄망) 설치·실행 안내

W0 판 (2026-10-19). 사내 반입·업데이트 방식은 W4 에서 Tool 온톨로지와 같은 '업데이트 텍스트 파일' 방식으로 정리한다 — 그 전까지는 저장소 zip 을 통째로 반입한다.
작성 방법은 `docs\02_작성안내.md` (메모장으로 분야 하나 쓰기).

## 0. 할 수 있는 것

- 인터넷 없이 설치 (Tool 온톨로지가 이미 반입한 파이썬 패키지를 그대로 쓴다 — **새로 반입할 패키지 0**)
- 저장소의 교과서 예시로 연습: 검사(`check`) → 빌드(`build`, 흐름 그림이 브라우저로 열림) → 계약 동결(`release`) → 데이터 검사(`validate`)
- 빌드 결과를 Protégé 로 보기 (`workflow_protege.ttl` 한 파일 — 보기 전용, 5-1장) · 질의 q01~q08 결과를 표로 (`query.bat`)
- (선택) VS Code 로 YAML 쓰기 — 칸 이름 자동완성·모양 오류 빨간 줄·칸 설명 (Red Hat YAML 확장 + 작성용 스키마, `docs\02_작성안내.md` 1-1장)
- 실제 워크플로 작성: `data\real\workflows\` 에 분야별 YAML (git 에 올라가지 않는 곳)
- Tool 온톨로지와 잇기: 사내 survey.ttl 로 TOOL ID 후보 CSV (`link_tools`) — 본격 교차는 W5
- 자기 점검(`selftest`)

## 1. 구성물

| 파일 | 용도 | 비고 |
|---|---|---|
| 저장소 zip (GitHub `aerogyu/En-genius-Workflow-Ontology`) | 코드·스키마·설정·예시·이 안내 | 풀어서 폴더 이름을 `engenius-workflow-ontology` 로 |
| 파이썬 패키지 | Tool 온톨로지의 `offline\wheels\` (또는 `wheels_win_amd64_cp310.zip`) | 이미 사내에 있다 — `requirements.lock` 이 같다 |
| Java 21 · Fuseki 6.2.0 | SHACL·Fuseki 테스트에만 (선택) | Tool 온톨로지 때 반입한 `C:\EnGenius\tools\` 그대로 |
| Protégé (5.x) | 빌드 결과 보기 (선택, 보기 전용 — 5-1장) | 사내 반입됨 (2026-10-20). 이 저장소가 설치·실행하지 않는다 |
| Red Hat YAML 확장 1.25.0 (`redhat.vscode-yaml-1.25.0.vsix`, MIT) | VS Code 로 YAML 쓸 때 자동완성·빨간 줄·설명 (선택 — `docs\02_작성안내.md` 1-1장) | 사내 VS Code 1.90.2 에 맞는 판 (2.0 이상은 VS Code 1.91 이상 필요). 파이썬 패키지가 아니라 편집기 확장 — `requirements.lock` 은 그대로. 설치 뒤 `yaml.schemaStore.enable`·`redhat.telemetry.enabled` 를 끈다 |

## 2. 준비

경로에 한글·공백이 없는 곳을 권장한다. **Tool 온톨로지 저장소 옆에** 두면 설치가 그 wheels 를 알아서 찾는다:

```text
C:\EnGenius\
  engenius-tool-ontology\            ← 이미 있는 Tool 온톨로지 (offline\wheels\ 가 있다 — 그쪽 설치 때 풀림)
  engenius-workflow-ontology\        ← 이 저장소 zip 을 푼 것
    scripts\env.bat                  ← 경로가 다르면 여기서 맞춘다
  tools\
    jdk-21.0.12.1+1\                 ← (선택) Java
    apache-jena-fuseki-6.2.0\        ← (선택) Fuseki
```

`scripts\env.bat` 을 메모장으로 열어 확인할 것 (위 배치 그대로면 고칠 것 없음):
`FUSEKI_HOME`·`JAVA_HOME` (선택) · `PYTHON` (기본 `python` — 3.10 이 아니면 `set PYTHON=py -3.10`) · `TOOL_ONTO_DIR` (Tool 온톨로지 저장소 자리).

## 3. 설치 (한 번)

`scripts\setup_offline.bat` 을 **더블클릭**. 하는 일:

0. 패키지 폴더 찾기 — 이 저장소 `offline\wheels\` → `offline\wheels_win_amd64_cp310.zip` → Tool 온톨로지 `offline\wheels\` → 그 zip 순서 (찾은 것을 `[wheels] …` 로 보여 준다)
1. `.venv` 가상환경 생성
2. pip·setuptools·wheel 갱신 (인터넷 없음)
3. `requirements.lock` 의 90개 패키지 설치 (`--no-index --no-deps`). 우리 코드 자체는 설치하지 않고 `src\` 에서 바로 실행한다 (스크립트가 `PYTHONPATH=src` 를 잡는다)
4. `doctor` — `[OK]` 가 줄줄이 나오면 성공. Java 줄은 `[--]` 여도 된다 (SHACL·Fuseki 테스트에만 필요)

끝나면 `scripts\build.bat` 더블클릭 → 예시가 빌드되고 흐름 그림이 열리면 설치 끝.

(선택) **설치 판 표식** — 메모장으로 `offline\installed_commit.txt` 를 만들고 1행에 받은 zip 의 커밋(7자리 이상)을 적어 두면 `selftest` 결과 파일 이름·첫 줄에 그 판이 찍힌다 (없으면 `unknown`). W4 업데이트 방식이 생기면 자동으로 쓴다.

## 4. 쓰는 법 — 더블클릭과 끌어다 놓기

모든 `.bat` 은 끝에 `계속하려면 아무 키나…` 로 멈춰 결과를 읽을 수 있게 한다. `.bat` 안내문은 영어(아래 8장), 파이썬 메시지는 한국어다.
'기본 폴더' = `data\real\workflows\` 가 있으면 그것, 없으면 예시 `workflows\examples\textbook\`.

| .bat | 더블클릭 | 끌어다 놓기 | 결과 |
|---|---|---|---|
| `check.bat` | 기본 폴더 검사 | YAML 폴더(또는 그 안의 .yaml 하나) | 검사만 (1초 남짓) — 작성 중에 자주 |
| `build.bat` | 기본 폴더 빌드 | YAML 폴더 (+ survey.ttl 을 같이 놓으면 TOOL ID 검사까지) | `output\<시각>_<폴더>\` + 흐름 그림이 브라우저로 열림. 오류가 있으면 결과 파일 없음 |
| `release.bat` | `data\real\workflows` 만 (예시는 기본으로 안 씀) | YAML 폴더 | 계약 목록을 보여 주고 **계약 key·사유**를 묻는다 → `_released\<계약>\<판>.json` (일자·사유, 인명 없음 — 사유에 이름·직급이 보이면 다시 묻고, 끝내 그러면 거절 V06) |
| `validate.bat` | — | 데이터 JSON 파일들 (+ 다른 빌드면 그 출력 폴더도) | 가장 최근 build 의 계약으로 검사 |
| `query.bat` | 가장 최근에 오류 없이 끝난 build 출력 | build 출력 폴더 `output\<시각>_<폴더>\` (또는 그 안의 `workflow.ttl`) + (선택) Tool 온톨로지 `survey.ttl` | 질의 q01~q08 결과를 표로 (읽기만 — 파일을 만들지 않는다). survey.ttl 을 같이 놓으면 교차 질의 q07·q08 도 채워진다 |
| `link_tools.bat` | 연습: 예시 + 합성 카탈로그 | YAML 폴더 + Tool 온톨로지 `survey.ttl` | `output\<시각>_<폴더>_tool_candidates.csv` — 보고 `_plan.yaml` 에 사람이 적는다 |
| `schema.bat` | 스키마 재생성 (`schema\wfo.yaml` 을 고친 뒤) | — | `schema\generated\` · cmd 에서 `schema.bat --check` = 드리프트만 |
| `doctor.bat` | 환경 점검 | — | `[OK]`/`[NG]`/`[--]` 줄 |
| `selftest.bat` | 자기 점검 (7장) | — | `offline\selftest_<커밋>.txt` |

Tool 온톨로지의 survey.ttl 은 `C:\EnGenius\engenius-tool-ontology\output\<실행ID>\survey.ttl` (가장 최근 적재). 읽기만 한다.
cmd 에서 직접: `scripts\build.bat <폴더> [survey.ttl …]` · `scripts\release.bat <폴더> <계약 key> <사유 …>` · `scripts\validate.bat [출력 폴더] <JSON …>` ·
`scripts\query.bat [출력 폴더] [survey.ttl …] [q02 q03 …]` (질의 이름을 주면 그것만).

## 5. 예시로 연습

1. `check.bat`·`build.bat` 더블클릭 — 예시 textbook (오류 0 · 경고 0 · 참고 3, 단계 7 · 계약 7 · 루프 1).
2. `workflows\examples\short` 를 바탕화면에 복사 → 메모장으로 고치며 그 폴더를 `check.bat` 위에 끌어다 놓기. `docs\02_작성안내.md` 6장의 실수를 일부러 넣어 보면 화면 문구가 익숙해진다.
3. 그 복사본을 `release.bat` 위에 끌어다 놓아 계약 하나를 동결 → 계약 항목을 하나 지우고 다시 `check.bat` → V02 '필요: MAJOR'.
4. 빌드 출력 `contracts\<계약>\0.1.0.example.json` 을 `validate.bat` 위에 끌어다 놓기 → J00 통과. 값을 바꿔 보면 J03.
5. `query.bat` 더블클릭 → 방금 build 한 출력에 질의 q01~q08 을 돌려 표로 (예: q02 = 수기 전달 구간 = Tool Agent 후보).

예시 폴더 자체는 고치지 않는다 (저장소 파일이다 — 고치지 않은 예시를 그대로 빌드하면 저장소 파일은 바뀌지 않는다).

## 5-1. Protégé 로 보기 (선택, 보기 전용)

build 가 출력 폴더에 **`workflow_protege.ttl`** 을 같이 만든다 — 스키마(클래스·속성 정의) + 작성분 + 계산분 + 외부 어휘(p-plan·prov·dcterms·qudt·skos) 선언을 Turtle 한 파일로 합친 것.
`workflow.ttl` 만 열면 클래스 정의가 없고 `schema\generated\wfo.owl.ttl` 만 열면 개체가 없어서 합본을 만든다. 빌드 화면의 `Protégé 보기용: workflow_protege.ttl (트리플 …)` 줄이 그 파일이다 (흐름 그림 `workflow.html` 과 같은 폴더).

1. Protégé → **File > Open** → `output\<시각>_<폴더>\workflow_protege.ttl`. 인터넷이 필요 없다 (가져오기 `owl:imports` 없음).
2. 한국어 이름으로: **View > Render by label (rdfs:label)** — Protégé 판에 따라 메뉴 이름이 조금 다를 수 있다 (View 메뉴의 'Render by …' 중 label).
   한국어가 안 나오면 File > Preferences > Renderer 에서 언어 `ko` 를 앞에 둔다 (판에 따라 자리가 다를 수 있다).
3. **Entities** 탭 (없으면 Window > Tabs > Entities): **Classes**(Step·Interface·Loop … 와 p-plan:Step 같은 표준 클래스) · **Individuals**(단계·계약·변수·루프·툴) ·
   **Object properties**(개체 사이 관계 — p-plan:isPrecededBy = 앞 단계, produces·consumes = 내놓는·받는 계약, tools = 쓰는 툴 …).
4. 개체(예: 단계) 하나를 누르면 오른쪽 **Property assertions** 에 관계가 나온다 (어느 단계 뒤인지·받고 내놓는 계약·쓰는 툴). key·설명은 Annotations 에 나온다.
5. **Protégé 에서 고친 것은 YAML 로 돌아가지 않는다 (보기 전용).** 고칠 것은 YAML 에 적고 `build.bat` 을 다시 누른다. build 는 새 출력 폴더에 새 파일을 만든다.
6. 추론기(Reasoner > HermiT 등)는 돌려도 되지만 **결과를 판정으로 쓰지 않는다** — 판정은 build 검사와 엔지니어.
   추론기는 합본에서 돌린다 — 합본의 동결 일자는 `2026-10-19T00:00:00` 처럼 시각이 붙어 보인다 (HermiT 가 `xsd:date` 를 받지 않아 합본에서만 `xsd:dateTime` 으로 바꿈,
   정본은 날짜 그대로). `wfo.owl.ttl` 만 따로 열어 HermiT 를 돌리면 이 때문에 멈춘다. HermiT 로 실제 돌린 것은 사내가 처음이다.

같은 YAML 이면 같은 파일이 나온다 (빌드 시각 기록을 뺐다). 자세한 읽는 법은 `docs\02_작성안내.md` 7장 'Protégé 로 보기'.
Protégé 로 실제 연 확인은 사내에서 처음 한다 — 열리지 않거나 관계가 안 보이면 그 증상만(값 없이) 알려 준다 (8장).

## 6. 실제 워크플로 작성

- `data\real\workflows\` 를 만들고 거기에 `_plan.yaml` + 분야별 `<분야>.yaml`. 이 폴더가 생기면 `check`·`build` 더블클릭의 기본이 된다.
- 예시를 복사해 시작할 때는 **`_registry`·`_released` 폴더는 빼고** 복사한다 (예시 일련번호 대장을 쓰면 G01 오류).
- 거꾸로 실데이터 폴더(대장 포함)는 **`data\real\` 아래에서만** 빌드된다 — 바탕화면 등으로 복사해 실험하면 G01 오류. 실험은 `data\real\` 아래 다른 이름의 폴더에 복사하거나 `_registry` 를 빼고 복사한다 (일련번호가 새로 붙는다).
- 빌드가 그 폴더 안에 `_registry\`(key → 일련번호 대장)·`_released\`(동결본)를 만든다. 손으로 고치지 않는다. 지우면 일련번호가 새로 붙는다 (IRI 가 바뀐다).
- 설정 조정은 `data\real\config\rules.yaml`·`units.yaml` 에 **바꿀 키만** 적는다 (저장소 `config\` 위에 덮인다 — 예: 새 단위 한 줄, 메시지 수준 `levels: {R05: 참고}`).
  이 덮어쓰기는 `data\real\` 아래 폴더를 빌드할 때만 쓰인다 (예시·연습 사본에는 섞지 않는다).
- 사내 툴명·실 워크플로·계약 사양은 `data\real\` 에만. 인명은 어디에도 적지 않는다 (담당자 칸은 오류, 메모 속 인명 유사 표기는 P01 경고).

## 7. 자기 점검 — `scripts\selftest.bat`

더블클릭 → `doctor` → 테스트 전체(`pytest`, 1분 남짓) → 결과 두 파일:

- `offline\selftest_<커밋>.txt` — **밖으로 가져가도 되는 것**: `PASS`/`FAIL`, 설치 판, `doctor` 줄, 통과·건너뜀 건수, 실패한 테스트 **이름만** (값 없음)
- `offline\selftest_<커밋>.log` — 전체 출력 (사내에만)

Java·Fuseki 가 없으면 그 테스트만, Tool 온톨로지 합성 survey.ttl(`engenius-tool-ontology\output\20260930T230632\survey.ttl`)이 없으면 교차 테스트만 건너뛴다 (실패 아님).
실데이터(`data\real\`)는 읽지 않는다 — 저장소 예시만.

## 8. 무엇을 밖으로 가져올 수 있나

밖(개발 PC)으로는 **값이 없는 것만**: `selftest_<커밋>.txt`, `doctor` 의 `[OK]`/`[NG]` 줄, 검사 보고(화면·`report.txt`) **맨 끝의 `== 코드별 건수 (값 없음 — 밖으로 가져갈 수 있는 줄): …` 한 줄** (예: "오류 U02 3, F01 1 · 경고 R05 2" — 그 위의 메시지 줄은 값을 품으니 손으로 세지 말고 이 줄만), `[NG] 설정 오류: <파일> <키>` 한 줄, 파이썬 traceback 의 마지막 몇 줄.
메시지 문구·key·툴명·계약 항목·경로·인명·흐름 그림·후보 CSV·`workflow_protege.ttl`·Protégé 화면·`query.bat` 의 표·VS Code 화면은 옮기지 않는다 (사내 내용이 들어 있다).

## 9. 자주 걸리는 것

- `[NG] .venv not found` → `scripts\setup_offline.bat` 을 먼저.
- `[NG] no wheels found` → Tool 온톨로지 저장소가 옆에 없거나 이름이 다르다 — `scripts\env.bat` 의 `TOOL_ONTO_DIR` 을 맞추거나 `wheels_win_amd64_cp310.zip` 을 이 저장소 `offline\` 에 둔다.
- `python` 이 3.10 이 아니다 → `scripts\env.bat` 에서 `set PYTHON=py -3.10`.
- `.bat` 메시지가 영어인 이유: 한국어 Windows 의 cmd 가 .bat 을 cp949 로 읽어 한글이 깨지기 때문. 파이썬 출력은 한국어다.
- 흐름 그림이 안 열린다 → 화면의 `[build] 흐름 그림: …\workflow.html` 을 직접 연다. 열지 않게 하려면 `env.bat` 에 `set WF_NO_OPEN=1`.
- VS Code 에 빨간 줄·설명이 안 나온다 → YAML 맨 위 `# yaml-language-server: $schema=file:///…` 경로가 이 저장소의 `schema\generated\wfo_authoring.schema.json` 과 맞는지
  (설치 자리가 다르면 그 경로로), 확장이 1.25.0 인지 본다. 빨간 줄과 check 결과가 다르면 **check 가 정본**이다 (`docs\02_작성안내.md` 1-1장 '알려진 차이').
- `.bat` 없이 직접 치려면 (cmd, 저장소 폴더에서): `set PYTHONPATH=src` · `set PYTHONUTF8=1` 뒤 `.venv\Scripts\python -m engenius_wf --help`.
  `PYTHONUTF8=1` 을 빼면 한국어 YAML 을 cp949 로 읽어 `schema` 가 실패하고 테스트는 `Exit: Python UTF-8 모드가 꺼져 있다` 한 줄로 멈춘다 (.bat 은 `env.bat` 이 켠다).
- 업데이트 (W4 전까지): 새 저장소 zip 을 같은 자리에 풀어 덮어쓴다. `data\real\`·`.venv\`·`output\` 은 zip 에 없어 그대로 남는다
  (새 판에서 지워진 파일은 남는다 — 문제가 되면 새 폴더에 풀고 `data\real\` 만 옮긴 뒤 `setup_offline.bat`). 그 뒤 `selftest.bat`.
