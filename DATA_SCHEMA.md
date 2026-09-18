# DATA_SCHEMA.md
### 데이터 컬럼 정의 및 API 명세 (Single Source of Truth)

> `BLUE_OCEAN_SCORE.md`의 변수명과 100% 일치해야 합니다. 컬럼명을 여기서 바꾸면 알고리즘 문서도 같이 수정하세요.

---

## 1. 원본 무역 데이터 (수집 단계 출력)

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| `country` | str | 수입국명 (영문, Comtrade 표기 기준) |
| `country_code` | str | 국가코드 |
| `hs_code` | str | HS코드 (앞자리 0 보존 위해 문자열) |
| `item_name` | str | 품목명 |
| `year` | int | 연도 |
| `market_size` | float | 해당국 전세계발 총수입액 (USD) |
| `korea_export_usd` | float | 해당국의 한국발 수입액 (USD) |

## 2. 전처리 후 추가 컬럼

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| `import_value_krw` | float | 환율 적용 원화환산액 |
| `korea_market_share` | float | korea_export_usd / market_size (0~1) |
| `growth_1y` | float | 전년 대비 증가율 (%) |
| `cagr_3y` | float | 3년 연평균성장률 (%) |
| `global_korea_share` | float | 한국의 해당 품목 세계시장 평균 점유율 (%, 전체 국가 기준 계산값) |
| `export_gap` | float | MAX(global_korea_share - korea_market_share, 0) |

## 3. 보조 지표 (확보 가능한 범위 내에서 사용, 없으면 NULL 허용)

| 컬럼명 | 타입 | 설명 | 데이터 소스 |
|---|---|---|---|
| `google_trend` | float | 0~100 검색관심도 지수 | Google Trends (pytrends) |
| `seasonality` | float | 0~100 계절성 지수 | Comtrade 월별 데이터 자체 계산 |
| `korea_export_growth` | float | 한국발 수출 증가율(%) | Comtrade |
| `top3_concentration` | float | 상위 3개 수출국 점유율 합(%) | Comtrade |
| `tariff_rate` | float | 실효관세율(%) — **점수 계산에는 사용하지 않음, AI Insight 서술 전용** | 뉴스 크롤링 기반 AI 추정치 (관세청 API 미사용, 상세는 `BLUE_OCEAN_SCORE.md` 11-1번 참고. 추정 불가 시 관련 문장 미생성) |
| `logistics_days` | int | 한국→해당국 물류 소요일수 | 자체 근사치 (확보 안 되면 NULL) |

**주의**: `logistics_days`, `google_trend`는 확보가 불확실한 지표입니다. 확보 안 될 경우 해당 세부점수는 가중치 재분배(나머지 지표로 총합 1.0 재조정) 하거나, 문서 개발원칙 3번에 따라 팀 협의 후 공식을 수정하고 CHANGELOG에 기록하세요. `tariff_rate`는 점수 공식에 포함되지 않으므로 재분배 대상이 아닙니다 (`BLUE_OCEAN_SCORE.md` CHANGELOG 2026-09-18 참고).

## 4. 스코어 계산 후 추가 컬럼

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| `market_opportunity_score` | float | 0~100 |
| `penetration_opportunity_score` | float | 0~100 |
| `blue_ocean_score` | float | 0~100 (기하평균) |
| `rank` | int | blue_ocean_score 기준 내림차순 순위 |

## 5. 전시회 데이터 (별도 DataFrame)

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| `fair_name` | str | 전시회명 |
| `country` | str | 개최국 (위 country와 표기 통일) |
| `city` | str | 개최도시 |
| `industry` | str | 산업분야 |
| `start_date` | str (YYYY-MM-DD) | 시작일 |
| `end_date` | str (YYYY-MM-DD) | 종료일 |
| `participant_count` | int | 참가기업 수 |

**출처**: KOTRA 해외전시회 정보 (data.go.kr, CSV 기본 제공)

---

## 6. API / 데이터 소스 확정 정보

| 소스 | 용도 | 확보 방법 | 비고 |
|---|---|---|---|
| UN Comtrade API | 국가×품목별 수출입 데이터 (메인) | comtrade.un.org 가입 → comtradedeveloper.un.org 키 발급 | 무료 티어: 일 500회 호출, 콜당 최대 10만 건 |
| 환율 API | USD→KRW 환산 | 한국수출입은행 API or exchangerate-api.com | 즉시 발급 가능 |
| KOTRA 해외전시회 정보 | 박람회명/개최지/기간/참가기업수 | data.go.kr 활용신청 | CSV 우선 사용, OpenAPI는 승인 지연 가능 |
| Google Trends | 검색 관심도 | `pytrends` (비공식 라이브러리) | 안정성 낮음 — 선택 사항 |
| 관세 뉴스 Open API | 실효관세율 (뉴스 기반 AI 추정, 점수 미반영) | 관세/무역 뉴스 크롤링 Open API → AI Insight가 최신 동향 반영 | 관세청 API 대비 변동성 대응 용이, 상세는 `BLUE_OCEAN_SCORE.md` 11-1번 참고 |

---

## 7. 데이터 타입/표기 규칙

- 국가명: 영문, Comtrade 표기 그대로 사용 (임의 번역 금지)
- 금액: 원본은 USD, 원화 컬럼은 반드시 `_krw` 접미사
- 비율: 0~1 소수로 저장 (`korea_market_share=0.05`), 퍼센트 텍스트 표시는 화면 출력 시에만 ×100
- 날짜: `YYYY-MM-DD` 문자열 통일
- 결측치: `NULL`/`NaN` 그대로 두고 임의로 0 채우지 않기 (0과 결측은 의미가 다름)
