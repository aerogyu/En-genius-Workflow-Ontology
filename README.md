# En-genius Workflow Ontology — 개념설계 워크플로 온톨로지

한화에어로스페이스 엔진 개발 AI 플랫폼 En-Genius 의 두 번째 온톨로지 (오픈소스 트랙, Tool 온톨로지의 형제 저장소).
분야(성능·압축기·연소기·터빈·냉각·이차유로)별 **단계(Step)**, 단계가 쓰는 **툴**, 단계 사이 **데이터 계약(Interface, JSON)** 을
엔지니어가 분야별 YAML 로 손으로 쓰면, 명령 하나(`build`)가 검사하고 다음을 만든다.

- TTL 2그래프 (작성분·계산분 — 선후·병렬·반복 루프 몸통은 빌드가 데이터에서 계산) + trig
- 계약별 JSON Schema 2020-12 + 골격 예시 JSON (실제 데이터 검사는 `validate`)
- 흐름 그림 `workflow.html` (분야 레인, 수기 전달 ✋ = Tool Agent 후보, 반복 루프 ↺)
- 한국어 검사 보고서 (코드·파일·행·고치는 법)

툴은 Tool 온톨로지의 TOOL ID 로 잇는다 (RDF 4술어 연결 계약, 같은 `egid:` IRI 공간). 이 PC 의 데이터는 공개 교과서 수준 예시와 합성 카탈로그뿐이다.

## 시작하기

**개발 PC** (Python 3.10, 패키지는 Tool 온톨로지와 같은 `requirements.lock`):

```bat
cd C:\EnGenius\engenius-workflow-ontology
scripts\build.bat                     :: 예시 workflows\examples\textbook 을 빌드하고 흐름 그림을 연다
scripts\selftest.bat                  :: doctor + pytest
```

직접 치려면 `set PYTHONPATH=src` · `set PYTHONUTF8=1` 뒤 `.venv\Scripts\python -m engenius_wf --help`
(명령: build · check · release · validate · link-tools · query · schema · doctor · licenses).

**사내(폐쇄망)**: `README_offline.md` — 설치는 `scripts\setup_offline.bat` 더블클릭 한 번 (Tool 온톨로지의 wheels 를 그대로 쓴다, 새 반입 0).

## 문서

| 문서 | 내용 |
|---|---|
| `docs/01_설계.md` | 개념 모델·작성 형식·검사 코드·Tool 온톨로지 연결·마일스톤 W0~W6·결정 Q1~Q4·위험·검증 기록 |
| `docs/02_작성안내.md` | 메모장으로 분야 하나 쓰기 — 규칙 5줄·완결 예시·칸 목록·단위·전달 방법·실수 23종·결과 읽는 법 |
| `docs/03_인수인계.md` | 지금 상태·환경 살리기·W1 검토 수리 기록·다음 작업(남은 결함 목록·Leo 결정 거리)·함정 기록 |
| `README_offline.md` | 사내 설치·실행 (더블클릭 .bat) |
| `CLAUDE.md` | 이 저장소의 규칙 (절대 규칙·확정된 결정·코드 규칙) |
