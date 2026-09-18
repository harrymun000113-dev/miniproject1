# TEAM_RULES.md
### 협업 규칙 및 AI 수정 규칙

> `BLUE_OCEAN_SCORE.md`, `DATA_SCHEMA.md`가 이 프로젝트의 Single Source of Truth입니다.
> 어떤 AI(GPT, Gemini, Claude, Cursor 등)를 쓰든, 코드나 문서를 수정하기 전에 반드시 이 세 문서를 먼저 읽고 작업하세요.

---

## 1. 팀 협업 절차

AI에게 코드 작성 또는 문서 수정을 요청할 때 다음 순서를 따릅니다.

1. `BLUE_OCEAN_SCORE.md`와 `DATA_SCHEMA.md`를 먼저 읽는다
2. 기존 프로젝트 정의(변수명, 공식, 가중치)를 파악한다
3. 기존 변수명과 계산식을 유지한다
4. 사용자의 추가 요청만 반영한다
5. 기존 정의와 충돌하면 임의로 변경하지 않는다
6. 충돌 내용이 있으면 먼저 팀에 명시하고 협의한다
7. 변경이 확정되면 `BLUE_OCEAN_SCORE.md`의 CHANGELOG 섹션에 기록한다

---

## 2. AI Modification Rules

이 프로젝트 문서/코드를 다루는 AI는 다음 규칙을 따라야 합니다.

### MUST (반드시 지킬 것)
- 현재 문서의 프로젝트 목적을 유지할 것
- 기존 변수명을 유지할 것 (`DATA_SCHEMA.md` 기준)
- 기존 계산 공식을 기준으로 작업할 것 (`BLUE_OCEAN_SCORE.md` 기준)
- 기존 데이터 구조를 유지할 것
- 실제 데이터와 가상(예시) 데이터를 명확히 구분할 것
- 수정사항을 명확하게 표시할 것 (어디를, 왜 바꿨는지)

### MUST NOT (하지 말 것)
- 점수 공식을 이유 없이 변경하지 말 것
- 존재하지 않는 API나 데이터를 존재한다고 가정하지 말 것
- 가상의 데이터를 실제 데이터라고 표현하지 말 것
- 기존 변수명을 임의로 번역하거나 변경하지 말 것 (예: `korea_market_share` → `한국점유율`로 코드 내 변경 금지)
- 특정 AI만 이해할 수 있는 문법(플러그인 전용 태그 등)을 추가하지 말 것

---

## 3. 파일 소유권 (자기 파일만 수정)

| 담당 | 파일 | 비고 |
|---|---|---|
| A | `src/collect_data_A.py` | Comtrade/KOTRA 데이터 수집 |
| B | `src/preprocess_kpi_B.py` | 전처리, KPI, Export Gap 계산 |
| C | `src/score_engine_C.py` | Market/Penetration/Blue Ocean Score |
| D | `src/insight_D.py` | 경쟁국 분석, 인사이트 문장, 계절성 |
| E | `src/dashboard_E.py` | Streamlit 대시보드, 배포 |

다른 사람 파일을 고치고 싶으면 반드시 PR로 요청 후 본인 동의를 받아 병합합니다.

---

## 4. 개발 환경 (버전 고정)

- Python **3.11.x**
- 아래 버전 그대로 사용, 임의 최신 버전 설치 금지

```
streamlit==1.38.0
pandas==2.2.2
numpy==1.26.4
plotly==5.24.1
python-dotenv==1.0.1
requests==2.32.3
comtradeapicall==1.0.4
openpyxl==3.1.5
```

새 라이브러리가 필요하면 팀에 먼저 공유 후 버전과 함께 `requirements.txt`에 추가합니다.

---

## 5. 코딩 컨벤션

- 변수/함수명은 영문 snake_case만 사용 (한글 변수명 금지)
- 모든 함수는 **pandas DataFrame in → DataFrame out** (dict, list 반환 금지)
- 원본 DataFrame을 직접 수정하지 말고 `df.copy()` 후 작업
- 함수 상단에 docstring으로 입출력 형식 명시

---

## 6. Git 규칙

- 브랜치명: `feature/담당자명-기능명` (예: `feature/tony-collect-data`)
- 커밋 메시지: `[담당자] 내용` (예: `[tony] Export Gap 계산 함수 추가`)
- `main` 브랜치 직접 push 금지, PR로만 병합
- 하루 작업 끝나면 당일 커밋+push

---

## 7. AI에게 작업 요청 시 프롬프트 템플릿

```
너는 이 프로젝트의 BLUE_OCEAN_SCORE.md와 DATA_SCHEMA.md를 기준으로 작업해야 해.
아래 파일 내용을 먼저 읽고, 여기 정의된 변수명·공식·가중치를 절대 임의로 바꾸지 마.

[BLUE_OCEAN_SCORE.md 내용 붙여넣기]
[DATA_SCHEMA.md 내용 붙여넣기]

Python 3.11, pandas 2.2.2, streamlit 1.38.0 기준 문법으로 작성해줘.
모든 함수는 pandas DataFrame을 받아서 DataFrame을 반환해야 해.
변수명은 영문 snake_case만 쓰고, 위 문서의 컬럼명과 정확히 일치시켜줘.

내 담당 파일은 [파일명] 하나야. 다른 모듈 파일은 건드리지 마.
기존 정의와 충돌하는 부분이 있으면 마음대로 고치지 말고 먼저 나에게 알려줘.
```

---

## 8. 통합 전 체크리스트 (Day 7 통합 전 각자 확인)

- [ ] 내 코드가 `DATA_SCHEMA.md`의 컬럼명을 정확히 그대로 입출력하는지 확인
- [ ] 내 함수가 `BLUE_OCEAN_SCORE.md`의 공식·가중치와 일치하는지 확인
- [ ] `python src/내파일.py` 단독 실행 시 에러 없는지 확인
- [ ] 새로 추가한 라이브러리가 있으면 팀에 공유했는지 확인
- [ ] 가상 데이터로 만든 부분과 실제 API 연동 부분을 주석으로 구분했는지 확인

---

## 9. 충돌 발생 시 대응 원칙

- 컬럼명/공식이 서로 다르게 구현된 경우 → **`DATA_SCHEMA.md`와 `BLUE_OCEAN_SCORE.md`가 항상 기준.** 다른 쪽 코드를 문서에 맞게 고친다
- 두 사람이 같은 파일을 동시에 수정해 git 충돌(merge conflict)이 난 경우 → 임의로 아무거나 선택하지 말고 직접 협의해서 어느 로직을 살릴지 결정
- AI가 생성한 코드가 이 문서 규칙과 다르게 나왔다면 → 그대로 커밋하지 말고 "문서 기준에 맞게 다시 짜줘"라고 재요청
- 공식/가중치를 변경해야 할 필요가 생기면 → 임의로 바꾸지 말고 `BLUE_OCEAN_SCORE.md`의 개발원칙(13번)과 CHANGELOG(14번) 절차를 따를 것
