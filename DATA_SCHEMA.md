# DATA_SCHEMA.md
### 데이터 컬럼 정의 및 API 명세 (Single Source of Truth)

> `BLUE_OCEAN_SCORE.md`의 변수명과 100% 일치해야 합니다. 컬럼명을 여기서 바꾸면 알고리즘 문서도 같이 수정하세요.

---

## 0. 데이터 흐름 (Funnel 단계별)

| 단계 | 사용하는 데이터 | 대상 국가 |
|---|---|---|
| Step 1 수집 | 원본 무역 데이터 (1번), 다년도 | 전 세계 보고국 |
| Step 2 컷 | `market_size` ≤ 5,000,000 USD 제외 | 전 세계 → U |
| Step 3 간이 점수 | 전처리 KPI (2번) → `proxy_score` (4번) | U |
| Step 4 후보 선별 | `proxy_score` 상위 50 → `is_candidate` | U → T (50개국) |
| Step 5 정밀 수집·점수 | 보조 지표 (3번) → 최종 점수 (4번) | T |
| Step 6 출력 | 랭킹 20개국 + 마켓 요약 (5번) + 박람회 (6번) | T 중 상위 20 |

- 성장률(`growth_1y`, `cagr_3y`) 계산을 위해 **연도 t, t-1, t-3 데이터가 모두 필요**합니다. 단일 연도만 조회하면 성장률이 전부 결측이 되므로 금지합니다.
- HS CODE는 **HS6 단위**로 통일합니다 (국가별 8~10단위는 일관성이 떨어짐).

---

## 1. 원본 무역 데이터 (수집 단계 출력)

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| `country` | str | 수입국명 (영문, Comtrade 표기 기준) |
| `country_code` | str | 국가코드 (Comtrade reporterCode) |
| `iso3` | str | ISO 3166-1 alpha-3 국가코드 |
| `hs_code` | str | HS코드 (앞자리 0 보존 위해 문자열) |
| `item_name` | str | 품목명 |
| `year` | int | 연도 |
| `market_size` | float | 해당국 전세계발 총수입액 (USD) |
| `korea_export_usd` | float | 해당국의 한국발 수입액 (USD) |

- 키: (`country_code`, `hs_code`, `year`). 중복 불가.
- 시장 데이터(`market_size`)가 있는데 한국발 응답만 빈 경우 `korea_export_usd = 0`으로 기록한다 (한국산 수입 없음). 시장 데이터 자체가 없으면 결측으로 둔다.

## 2. 전처리 후 추가 컬럼

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| `import_value_krw` | float | 환율 적용 원화환산액 |
| `korea_market_share` | float | korea_export_usd / market_size (0~1). 화면 표시 시 ×100 (한국기업 침투도 %) |
| `growth_1y` | float | 전년 대비 증가율 (%) |
| `cagr_3y` | float | 3년 연평균성장률 (%) |
| `global_korea_share` | float | 한국의 해당 품목 세계시장 평균 점유율 (**0~1 비율**, Step 1 수집 전체 국가 기준 계산값) |
| `export_gap` | float | MAX(global_korea_share - korea_market_share, 0). 점수 미사용, 상세 분석용 |
| `korea_export_growth` | float | 한국발 수입액 증가율 (%). 점수 미사용, 참고용 |
| `proxy_score` | float | 간이 점수 (0~100, U 기준, Step 3) |
| `is_candidate` | bool | 간이 점수 상위 50개국 여부 (Step 4) |
| `underpenetrated_flag` | bool | korea_market_share < global_korea_share |

## 3. 보조 지표 (Step 5, 후보 50개국에만 수집)

| 컬럼명 | 타입 | 설명 | 배점 | 데이터 소스 |
|---|---|---|---|---|
| `top3_concentration` | float | 상위 3개 공급국 점유율 합 (0~100, %) | 15 | Comtrade (수입 파트너 분해) |
| `tariff_rate` | float | 관세율 (%) | 10 | **미확정** (BLUE_OCEAN_SCORE.md 15번) |
| `google_trend` | float | 0~100 검색관심도 지수 (연평균) | 5 | Google Trends |
| `fx_change_3y` | float | 해당국 통화의 USD 대비 3년 변동률 (%) | 5 | 환율 API (정의는 초안) |
| `competitor_1_country` ~ `competitor_3_country` | str | 경쟁국: 상위 공급국 3개 (한국 제외) | 점수 미사용 | Comtrade (수입 파트너 분해) |
| `competitor_1_share` ~ `competitor_3_share` | float | 경쟁국 점유율 (0~1) | 점수 미사용 | Comtrade |
| `seasonality` | float | 0~100 계절성 지수 (월별 변동계수) | 점수 미사용 | Google Trends 또는 Comtrade 월별 데이터. 진출 타이밍 설명용 |

**주의**: 선택 지표(`top3_concentration`, `tariff_rate`, `google_trend`, `fx_change_3y`)가 확보되지 않으면 해당 배점을 나머지 지표로 재분배합니다 (`BLUE_OCEAN_SCORE.md` 5번). 필수 지표(`market_size`, `cagr_3y`, `growth_1y`, `korea_market_share`)가 결측이면 점수를 계산하지 않습니다. 결측을 0으로 채우지 않습니다.

## 4. 스코어 계산 후 추가 컬럼

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| `market_opportunity_score` | float | 0~100 (화면 표시명: Potential) |
| `penetration_opportunity_score` | float | 0~100 |
| `blue_ocean_score` | float | 0~100 (100점 배점 합산) |
| `score_coverage` | float | 사용된 배점 합 / 100 (0~1). 낮으면 "데이터 부족" 표시 |
| `rank` | int | blue_ocean_score 기준 내림차순 순위 |

## 5. 출력 데이터 (대시보드 입력)

### 5-1. 마켓 요약 (`market_summary`, 1행 DataFrame)

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| `hs_code` | str | 입력한 HS CODE |
| `item_name` | str | 품목명 |
| `year` | int | 기준 연도 |
| `total_market_size_usd` | float | 수집된 전체 보고국의 해당 HS CODE 총수입액 합계 (하드 컷 이전) |
| `eligible_market_size_usd` | float | 하드 컷 통과 국가(U)의 수입액 합계 |
| `reporting_countries` | int | 수입 데이터가 있는 보고국 수 |
| `eligible_countries` | int | U 국가 수 |

### 5-2. 랭킹 대시보드 (`ranking`, 최대 20행)

`rank`, `country`, `iso3`, `hs_code`, `blue_ocean_score`, `market_opportunity_score`, `penetration_opportunity_score`, `korea_market_share`, `competitor_1_country`~`competitor_3_country` (+ `_share`), `market_size`(마지막 열: 해당 HS CODE 수입 규모, 기존 KOTRA 열 대체), `export_gap`, `cagr_3y`, `growth_1y`, `underpenetrated_flag`, `score_coverage`

- 랭킹 표에는 KOTRA(박람회) 열을 넣지 않습니다.
- 1위 추천 타깃은 `rank == 1`인 행을 사용합니다.

## 6. 전시회 데이터 (별도 DataFrame, `fairs`)

| 컬럼명 | 타입 | 설명 |
|---|---|---|
| `fair_name` | str | 전시회명 |
| `country` | str | 개최국 (위 country와 표기 통일) |
| `city` | str | 개최도시 |
| `industry` | str | 산업분야 |
| `start_date` | str (YYYY-MM-DD) | 시작일 |
| `end_date` | str (YYYY-MM-DD) | 종료일 |
| `participant_count` | int | 참가기업 수 |
| `official_url` | str | 공식 사이트 (크롤링 시) |
| `source` | str | 출처 (KOTRA CSV / 크롤링 사이트명) |

- **HS CODE 연결**: 전시회 데이터에는 HS CODE가 없으므로, `hs_industry_map`(HS CODE → 산업분야/키워드) 매핑 테이블을 별도로 관리합니다. (미구축)
- 이미 종료된 일정은 제외하고, 다가오는 일정 순으로 정렬합니다.
- 크롤링 대상 사이트는 이용약관/robots.txt 확인 후 확정합니다.

---

## 7. API / 데이터 소스 확정 정보

| 소스 | 용도 | 확보 방법 | 비고 |
|---|---|---|---|
| UN Comtrade API | 국가×품목별 수입, 한국발 수입, 공급국 구성 (메인 후보) | comtrade.un.org 가입 → comtradedeveloper.un.org 키 발급 | 무료 티어: 일 500회 호출, 콜당 최대 10만 건 (팀 확인값, 개발 전 재확인) |
| K-Stat API (한국무역협회) | Comtrade 대체/보완 후보 | 별도 확인 필요 | **주 소스 미확정.** 확정되면 이 표를 갱신 |
| 환율 API | 환율 추이(`fx_change_3y`), USD→KRW 환산(`import_value_krw`) | 한국수출입은행 API or exchangerate-api.com | 과거 3년 환율 조회 가능 여부 확인 필요 |
| Google Trends | 검색 관심도(`google_trend`) | `pytrends`(비공식) 또는 SerpAPI | 안정성 낮음, 어느 쪽을 쓸지 확정 필요 (새 라이브러리는 팀 공유) |
| 관세 데이터 | `tariff_rate` | 미확정 | 공식 관세 데이터 vs 뉴스 기반 추정 (`BLUE_OCEAN_SCORE.md` 11-1, 15번) |
| KOTRA 해외전시회 정보 | 박람회명/개최지/기간/참가기업수 | data.go.kr 활용신청 | CSV 우선 사용, OpenAPI는 승인 지연 가능 |
| 박람회 크롤링 | KOTRA에 없는 일정 보완 | 대상 사이트 미정 | 약관/robots.txt 확인 필수 |

### 호출량 관리 원칙

- 무료 티어 한도(일 500회)를 감안해 **성공한 응답은 캐시**한다 (키: HS CODE, 국가, 연도, 파라미터). TTL은 1~4주.
- **빈 응답(`data`가 비어 있음)은 영구 캐시하지 않는다.** 일시적 빈 응답이 계속 재사용되는 문제를 막기 위함.
- Step 1에서 국가별로 개별 호출하지 않고, 한 번에 여러 국가(또는 전체 보고국)를 조회할 수 있는지 먼저 확인한다 (미확인).
- Step 5의 추가 호출(공급국 분해, 트렌드)은 **후보 50개국에만** 수행한다.
- 일일 한도 초과 오류는 재시도하지 않고 사용자에게 명확히 알린다.
- API 실패 시 가상 데이터로 대체하지 않는다.

---

## 8. 데이터 타입/표기 규칙

- 국가명: 영문, Comtrade 표기 그대로 사용 (임의 번역 금지)
- 금액: 원본은 USD, 원화 컬럼은 반드시 `_krw` 접미사
- 비율: 0~1 소수로 저장 (`korea_market_share=0.05`, `global_korea_share=0.081`), 퍼센트 텍스트 표시는 화면 출력 시에만 ×100. 단, `growth_1y`, `cagr_3y`, `fx_change_3y`, `tariff_rate`, `top3_concentration`은 % 단위(예: 21.0)로 저장
- 화면 표시 시 작은 비율이 0으로 보이지 않도록 반올림 전 값으로 계산하고 소수 1~2자리로 표시
- 날짜: `YYYY-MM-DD` 문자열 통일
- 결측치: `NULL`/`NaN` 그대로 두고 임의로 0 채우지 않기 (0과 결측은 의미가 다름). 화면에서도 결측을 0으로 표시하지 않는다.
