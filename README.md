# Blue Ocean Finder
### 무역 기회 발굴 대시보드 — KITA AX 무역마스터 1차 프로젝트

---

## 프로젝트 개요

특정 HS CODE를 기준으로 전 세계 국가를 자동 분석하여, **"시장 수요와 성장성은 높지만 한국산 제품의 시장 침투율은 상대적으로 낮은 국가"** 를 찾아주는 서비스입니다.

기존의 단순한 "수출 유망국가 추천" 서비스와 달리, 한국이 아직 충분히 진출하지 못한 미개척 시장(Blue Ocean Market)을 찾는 것이 핵심입니다.

> "한국이 아직 놓치고 있는 시장을 찾습니다."

---

## 문서 구성 (읽는 순서)

이 프로젝트는 문서를 역할별로 분리해서 관리합니다. **코드를 짜기 전에 아래 순서로 먼저 읽으세요.**

1. **`README.md`** (이 문서) — 프로젝트 전체 개요
2. **`BLUE_OCEAN_SCORE.md`** — 알고리즘 명세서 (Market/Penetration/Export Gap/Blue Ocean Score 공식, 절대 임의 변경 금지)
3. **`DATA_SCHEMA.md`** — 데이터 컬럼 정의, API 소스 확정 정보
4. **`TEAM_RULES.md`** — 협업 규칙, Git 규칙, AI에게 작업 요청 시 프롬프트 템플릿

어떤 AI(GPT, Gemini, Claude, Cursor 등)로 코드를 짜든, 이 3개 문서(`BLUE_OCEAN_SCORE.md`, `DATA_SCHEMA.md`, `TEAM_RULES.md`)를 먼저 주고 작업을 시작해야 합니다.

---

## 핵심 서비스 흐름

```
[STEP 1] 상품/HS코드 입력
      ↓
[STEP 2] 전 세계 국가 자동 스캔 → Blue Ocean Map (버블차트)
      ↓
[STEP 3] Blue Ocean Score 랭킹 → "한국이 놓치고 있는 시장 TOP 10"
      ↓
[STEP 4] 선택 국가 상세 분석 → 왜 블루오션인가? (Export Gap, 경쟁국 변화, 계절성)
      ↓
[STEP 5] 진출 타이밍 + 관련 박람회 정보 연결
```

---

## 팀 역할 분담

| 담당 | 모듈 | 파일 |
|---|---|---|
| A | 데이터 수집 (Comtrade, KOTRA) | `src/collect_data_A.py` |
| B | 전처리·KPI·Export Gap 계산 | `src/preprocess_kpi_B.py` |
| C | Blue Ocean Score 산출 | `src/score_engine_C.py` |
| D | 경쟁국 분석·인사이트·계절성 | `src/insight_D.py` |
| E | 대시보드·배포 | `src/dashboard_E.py` |

---

## 개발 환경

- Python 3.11.x
- 설치: `pip install -r requirements.txt`
- 실행: `streamlit run src/dashboard_E.py`

버전 고정 목록은 `TEAM_RULES.md` 4번 섹션 참고.

---

## 데이터 출처

- UN Comtrade API (국가×품목별 수출입 데이터)
- 환율 API (한국수출입은행 or exchangerate-api.com)
- KOTRA 해외전시회 정보 (data.go.kr)

상세 확보 방법은 `DATA_SCHEMA.md` 6번 섹션 참고.

---

## 일정 (마감 2026-09-28)

| 일차 | 내용 |
|---|---|
| Day 1 | 문서 숙지, 데이터 스키마 재확인, API 키 발급 |
| Day 2~6 | A~D 병렬 개발 |
| Day 7~8 | E가 전체 통합, 실데이터 교체 |
| Day 9 | Streamlit Cloud 배포, 시연 영상 녹화 |
| Day 10~11 | README/PPT 정리, 발표 리허설 |

---

## 제출물

- [ ] GitHub 저장소 (README 포함)
- [ ] 시연 영상
- [ ] 발표 PPT (PDF)
- [ ] (가산점) Streamlit Cloud 배포 URL
- [ ] 데일리 스크럼 기록
