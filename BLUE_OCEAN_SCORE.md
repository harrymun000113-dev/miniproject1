# BLUE_OCEAN_SCORE.md
### Blue Ocean Score 알고리즘 명세서 (Single Source of Truth)

> 이 문서는 프로젝트의 핵심 알고리즘 기준 문서입니다.
> GPT, Gemini, Claude, Cursor 등 어떤 AI를 쓰더라도 이 문서를 먼저 읽고, 여기 정의된 변수명·공식·배점을 그대로 따라야 합니다.
> 특정 AI 전용 문법, HTML, 플러그인 기능에 의존하지 않고 순수 Markdown으로만 작성되어 있습니다.

---

## 1. 프로젝트 목적

특정 HS CODE를 기준으로 전 세계 국가를 분석하여,

> "시장 수요와 성장성은 높지만 한국산 제품의 시장 침투율은 상대적으로 낮은 국가"

를 발굴하는 서비스입니다.

기존의 단순한 "수출 유망국가 추천"과 달리, **한국이 아직 충분히 진출하지 못한 미개척 시장(Blue Ocean Market)** 을 찾는 것이 핵심입니다.

---

## 2. Core Concept

Blue Ocean Score는 100점 만점이며, 두 개의 하위 영역(각 50점)으로 구성됩니다.

1. **Market Opportunity (시장 매력, 50점)** — 해당 국가의 시장 자체가 매력적인지 평가. 화면에서는 **Potential**로 표시
2. **Korea Penetration Opportunity (한국 침투 여지, 50점)** — 한국 기업이 추가로 진출할 여지가 있는지 평가

두 영역의 점수를 합산해 최종 **Blue Ocean Score(100점)** 를 산출합니다.

---

## 3. 데이터 처리 깔때기 (Funnel)

랜덤 샘플링은 사용하지 않습니다. 비용이 들지 않는 계산으로 전 국가를 먼저 순위화하고, 비용이 드는 정밀 수집은 상위 50개국에만 적용합니다.

| 단계 | 내용 | API 비용 |
|---|---|---|
| Step 1 | HS CODE 입력 → 국가별 수입액(전 세계발, 한국발)을 다년도로 수집 | 발생 (1회성) |
| Step 2 | 하드 컷: 수입금액 **5,000,000 USD 이하** 국가 제외 (초과만 통과). 통과한 국가 집합을 **U**라 한다 | 0 |
| Step 3 | U 전체에 간이 점수(`proxy_score`) 계산 (3-1 참고) | 0 |
| Step 4 | `proxy_score` 상위 **50개국**을 후보 집합 **T**로 확정 (3-2 참고) | 0 |
| Step 5 | T(50개국)에만 추가 데이터 수집 후 100점 최종 점수 계산 (4번) | 발생 (50개국분) |
| Step 6 | 최종 상위 20개국과 전체 마켓 사이즈 출력 | 0 |

### 3-1. 간이 점수 (Proxy Score, Step 3)

Step 1 데이터만으로 계산 가능한 4개 지표를 사용하고, **최종 점수와 동일한 배점**을 재사용합니다 (별도 가중치를 만들지 않음).

| 지표 | 배점 | 방향 |
|---|---|---|
| `market_size` (로그) | 15 | 높을수록 좋음 |
| `cagr_3y` | 15 | 높을수록 좋음 |
| `growth_1y` | 10 | 높을수록 좋음 |
| `korea_market_share` | 25 | 낮을수록 좋음 |

```
proxy_score = ( 15×market_size_score + 15×cagr_3y_score + 10×growth_1y_score + 25×low_korea_share_score ) / 65
```

- 각 지표 점수는 **U 전체** 기준으로 정규화한다 (6번 참고).
- 결과는 0~100 범위이다.

### 3-2. 후보 선별 규칙 (Step 4)

- **`proxy_score` 상위 50개국을 T로 확정한다. 이것이 유일한 선별 규칙이다.** 랜덤·층화추출 등 보조 규칙은 쓰지 않는다.
- 동점이면 `market_size`가 큰 국가를 우선한다 (재현성 보장).
- U가 50개국 미만이면 U 전체를 T로 사용한다.
- 상위 50 밖으로 밀린 국가는 복구되지 않으므로, 간이 점수의 지표·배점 변경은 이 문서 절차(13번, 14번)를 반드시 따른다.

---

## 4. 최종 점수: 100점 스코어링 (Step 5)

### 4-1. 배점표

| 영역 | 변수명 | 지표 | 배점 | 방향 |
|---|---|---|---|---|
| Market (50) | `market_size` | 전체 시장 규모 (해당 국가의 해당 HS CODE 총수입액) | 15 | 높을수록 좋음 |
| | `cagr_3y` | 최근 3년 수입시장 연평균 성장률 | 15 | 높을수록 좋음 |
| | `growth_1y` | 전년 대비 수입시장 성장률 | 10 | 높을수록 좋음 |
| | `google_trend` | 해당 국가의 Google 트렌드 (검색 관심도) | 5 | 높을수록 좋음 |
| | `fx_change_3y` | 최근 3년 환율 추이 | 5 | 통화가치 하락폭이 작을수록 좋음 |
| Penetration (50) | `korea_market_share` | 시장 규모 대비 한국 수출 금액 (한국산 점유율) | 25 | 낮을수록 좋음 |
| | `top3_concentration` | 경쟁 개방성: 상위 3개 수출국이 차지하는 비중 | 15 | 낮을수록(=개방적일수록) 좋음 |
| | `tariff_rate` | 관세 | 10 | 낮을수록 좋음 |
| **합계** | | | **100** | |

### 4-2. 지표 정의

```
korea_market_share = korea_export_usd / market_size                   (0~1)
top3_concentration = 상위 3개 공급국 수입액 합 / 총 수입액 × 100      (0~100)
fx_change_3y       = (fx_t / fx_(t-3) - 1) × 100
                     fx = 해당 국가 통화의 USD 대비 환율 (1 USD당 현지통화). 양수 = 현지통화 약세
```

- `fx_change_3y` 정의는 **초안**이다 (15번 미확정 항목 참고).
- `tariff_rate`는 % 단위 관세율이다. 소스는 미확정이다 (15번 참고).

### 4-3. 점수 계산식

각 지표를 6번 방식으로 0~100점으로 정규화한 값을 `<변수명>_score`라 한다 (예: `cagr_3y_score`). 정규화는 **T(50개국)** 기준이다.

```
Market Opportunity Score (Potential, 0~100)
  = ( 15×market_size_score + 15×cagr_3y_score + 10×growth_1y_score
      + 5×google_trend_score + 5×fx_change_3y_score ) / 50

Korea Penetration Opportunity Score (0~100)
  = ( 25×low_korea_share_score + 15×competition_openness_score
      + 10×tariff_accessibility_score ) / 50

Blue Ocean Score (0~100)
  = ( Market Opportunity Score + Korea Penetration Opportunity Score ) / 2
```

- 위 식은 "지표 점수 × 배점의 합계"와 같다 (배점 합계 100점). 즉 `blue_ocean_score = Σ(지표점수 × 배점) / 100`.
- `low_korea_share_score`는 `korea_market_share`의 Negative 정규화 값, `competition_openness_score`는 `top3_concentration`의 Negative 정규화 값, `tariff_accessibility_score`는 `tariff_rate`의 Negative 정규화 값, `fx_change_3y_score`는 `fx_change_3y`의 Negative 정규화 값이다.

### 4-4. 계산 예시 (가상 데이터, 공식 이해용)

⚠️ **아래 숫자는 실제 데이터가 아니라 계산 방식을 설명하기 위한 가상 예시입니다.**

| 지표 | 정규화 점수 | 배점 | 획득 점수 |
|---|---|---|---|
| market_size | 60 | 15 | 9.00 |
| cagr_3y | 90 | 15 | 13.50 |
| growth_1y | 80 | 10 | 8.00 |
| google_trend | 70 | 5 | 3.50 |
| fx_change_3y | 50 | 5 | 2.50 |
| **Market 소계** | | **50** | **36.50 → Potential 73.0** |
| low_korea_share | 85 | 25 | 21.25 |
| competition_openness | 40 | 15 | 6.00 |
| tariff_accessibility | 100 | 10 | 10.00 |
| **Penetration 소계** | | **50** | **37.25 → 74.5** |
| **Blue Ocean Score** | | **100** | **73.75** |

---

## 5. 결측 처리 규칙

- **필수 지표**: `market_size`, `cagr_3y`, `growth_1y`, `korea_market_share`. 하나라도 결측이면 해당 국가의 점수는 계산하지 않고(NaN) 순위에서 제외한다.
- **선택 지표**: `top3_concentration`, `tariff_rate`, `google_trend`, `fx_change_3y`. 결측이면 해당 지표를 빼고 **남은 지표의 배점으로 재분배**한다.

```
score = Σ(사용 가능한 지표점수 × 배점) / Σ(사용 가능한 배점)         (각 영역 점수, 최종 점수 모두 동일)
score_coverage = Σ(사용 가능한 배점) / 100
```

- `score_coverage`를 결과에 함께 저장하고, 화면에서 낮은 국가는 "데이터 부족" 표시를 한다 (13번 7항).
- **결측과 0을 구분한다.** 단, 해당 국가의 시장 데이터(`market_size`)가 있는데 한국발 수입 응답만 빈 경우는 `korea_export_usd = 0`(한국산 수입 없음)으로 처리한다.
- 임의의 값을 생성해 채우지 않는다.

---

## 6. Normalization (정규화)

모든 지표는 단위가 다르므로 0~100점으로 정규화합니다.

### 6-1. Positive Indicator (높을수록 좋은 지표)
```
Score = ((x - min) / (max - min)) × 100
```
적용 대상: `cagr_3y`, `growth_1y`, `google_trend`

### 6-2. Negative Indicator (낮을수록 좋은 지표)
```
Score = ((max - x) / (max - min)) × 100
```
적용 대상: `korea_market_share`, `top3_concentration`, `tariff_rate`, `fx_change_3y`

### 6-3. Market Size Normalization (로그 변환)
```
Market Size Score = ((log(x) - log(min)) / (log(max) - log(min))) × 100
```

### 6-4. 정규화 기준 집합
- **간이 점수(Step 3)**: U 전체(하드 컷 통과 전 국가) 기준.
- **최종 점수(Step 5)**: T(상위 50개국) 기준.
- 어느 경우든 **함께 조회한 국가에 따라 점수가 달라지면 안 된다.** 기준 집합은 HS CODE 입력만으로 결정되어야 한다 (소수의 벤치마크 국가를 임의로 추가해 정규화하는 방식 금지).
- 상수 지표(min = max)는 분모가 0이므로 NaN 처리하고 5번 결측 규칙을 적용한다.
- 극단값 처리(`cagr_3y`, `growth_1y`의 상하위 5% winsorize 등)는 **초안**이며 15번 미확정 항목에서 확정한다.

---

## 7. Export Gap (참고 지표)

### 공식
```
Export Gap = MAX(한국의 해당 품목 세계시장 평균 점유율 - 해당 국가의 한국산 시장점유율, 0)
global_korea_share = Σ korea_export_usd / Σ market_size   (Step 1에서 수집한 전체 국가 기준)
```

### 의미
"한국이 해당 품목 자체에서 경쟁력이 없는 것이 아니라, 세계시장 평균과 비교했을 때 특정 국가에서 상대적으로 시장 침투가 부족하다"는 것을 나타냅니다.

- Export Gap은 **점수 계산에는 사용하지 않고**, 국가 상세 분석과 AI Insight 설명용으로 표시합니다 (한국산 점유율이 이미 25점 배점으로 반영되어 있음).
- Export Gap이 크다는 이유만으로 Blue Ocean이라 판단하면 안 됩니다.

### 예시 (가상)
- 한국의 HS 330499 세계시장 평균 점유율 = 8.1%
- 멕시코 내 한국산 HS 330499 점유율 = 1.0%
- Export Gap = 8.1% - 1.0% = **7.1%p**

---

## 8. Blue Ocean 후보 표시

```
underpenetrated_flag = (korea_market_share < global_korea_share)
```

- 한국산 점유율이 한국의 세계 평균보다 낮은 국가에 "미개척 후보" 표시를 붙입니다.
- 이 조건을 순위 산정의 **필수 필터로 쓸지는 미확정**입니다 (15번). 확정 전에는 표시용으로만 사용하고 순위에서 제외하지 않습니다.

---

## 9. 출력 (Step 6)

### 9-1. 전체 마켓 사이즈
```
total_market_size_usd = Σ market_size   (Step 1에서 수집한 모든 보고국의 해당 HS CODE 총수입액)
```
- 하드 컷 이전 전체 국가 합계를 기본값으로 하고, U 합계(`eligible_market_size_usd`)도 함께 보관한다.
- 수입 통계를 보고하지 않은 국가는 빠지므로 화면에는 "보고국 기준 수입 규모"임을 함께 표기한다.

### 9-2. 1위 추천 타깃
- `blue_ocean_score` 1위 국가를 별도 카드로 보여주고, AI Insight(11번)로 추천 이유를 설명한다.

### 9-3. 랭킹 대시보드 (상위 20개국)

| field | 설명 |
|---|---|
| `rank` | 순위 (`blue_ocean_score` 내림차순) |
| `country` | 국가 |
| `blue_ocean_score` | 최종 점수 (0~100) |
| `market_opportunity_score` | Potential (0~100) |
| `korea_market_share` | 한국기업 침투도 (수입 규모 대비 한국산 비중, 화면 표시 시 ×100 %) |
| `competitor_1_country` ~ `competitor_3_country` (+ `_share`) | 경쟁국: 해당 국가 수입 시장의 상위 3개 공급국(한국 제외)과 점유율 |
| `market_size` | 해당 HS CODE 품목의 해당 국가 수입 규모 (기존 KOTRA 열을 대체하는 마지막 열) |

부가 필드: `hs_code`, `penetration_opportunity_score`, `global_korea_share`, `export_gap`, `cagr_3y`, `growth_1y`, `underpenetrated_flag`, `score_coverage`.

---

## 10. Example Dataset

이전 버전의 가상 예시 데이터(5개국)는 구 공식(기하평균, 물류·Export Gap 포함) 기준이므로 삭제했습니다. 새 공식의 계산 예시는 4-4번을 참고하세요. 실제 서비스에서는 반드시 API/공식 데이터를 사용합니다.

---

## 11. AI Insight Generation Rule

점수만 보여주지 말고, 사용자가 이유를 이해할 수 있도록 자연어로 설명해야 합니다.

**규칙**: AI 분석 문장은 반드시 실제 계산된 데이터에 근거해야 하며, 데이터에 없는 이유를 임의로 만들어내면 안 됩니다.

**예시 문장 (가상)**
> "UAE의 해당 품목 시장은 최근 3년간 연평균 21% 성장했습니다. 한국산 점유율은 1.5%로 한국의 세계 평균 점유율 8.1%보다 낮아 6.6%p의 Export Gap이 존재합니다. 상위 3개 수출국의 점유율 합이 낮아 신규 공급자에게 열려 있는 시장으로 분석됩니다."

### 11-1. 관세율 처리 방식

관세(`tariff_rate`)는 **10점 배점으로 점수에 반영**됩니다 (2026-09-19 변경, CHANGELOG 참고). 관세율은 국가·품목별 변동성이 크므로 아래 규칙을 지킵니다.

- 소스는 미확정이다 (15번). 점수에는 **출처가 확인된 수치**만 사용한다.
- 뉴스 크롤링 기반 AI 추정치는 근거 뉴스와 함께 AI Insight 서술에만 사용하고, 점수용 수치로 쓸지는 팀 확정 후 결정한다.
- 뉴스에 근거하지 않은 관세율 수치를 임의로 생성하지 않는다.
- 값이 없는 국가는 `tariff_rate`를 결측으로 두고 5번 규칙(배점 재분배)을 적용하며, 관세 관련 문장은 생성하지 않는다.

---

## 12. Data Source Plan

실제 개발 단계에서 검토할 데이터 소스입니다. (확정 여부는 `DATA_SCHEMA.md` 참고)

| 카테고리 | 소스 후보 |
|---|---|
| 국가별 수입 (HS코드, 연도별) / 한국발 수입 / 공급국 구성 | UN Comtrade, K-Stat |
| 검색 트렌드 (`google_trend`) | Google Trends |
| 환율 추이 (`fx_change_3y`) | 환율 API |
| 관세 (`tariff_rate`) | 미확정 (공식 관세 데이터 vs 뉴스 기반 추정) |
| 박람회 일정 | KOTRA 해외전시회 정보, 크롤링 |

각 데이터 소스는 실제 API 사용 가능 여부와 라이선스, 호출 한도를 확인한 후 확정합니다. 확보되지 않은 선택 지표는 5번 규칙에 따라 배점 재분배로 처리합니다.

---

## 13. Development Principles

1. 기존 변수명을 임의로 변경하지 않는다.
2. 기존 점수 공식과 배점, 깔때기 규칙(상위 50 후보 → 상위 20 출력)을 임의로 변경하지 않는다.
3. 공식 변경이 필요한 경우 기존 공식과 변경안을 모두 제시하고 변경 이유를 설명한다.
4. 배점 총합은 반드시 100점(영역별 50점)이어야 한다.
5. 실제 데이터와 가상 데이터를 명확히 구분한다 (가상 데이터는 반드시 "예시/테스트용"이라고 표기).
6. 데이터가 없는 경우 임의의 값을 생성하지 않는다.
7. 통계적으로 불안정한 값(표본 부족, `score_coverage` 낮음 등)은 사용자에게 명시한다.
8. 모든 점수는 0~100 범위로 통일한다.
9. 코드 구현 시 변수명은 이 문서의 정의와 정확히 일치시킨다.
10. 특정 AI 서비스에 종속되는 문법을 사용하지 않는다 (순수 Markdown/Python만 사용).
11. 알고리즘 변경 시 반드시 하단 CHANGELOG에 기록한다.
12. 같은 HS CODE 입력에는 항상 같은 결과가 나와야 한다 (랜덤 요소 금지).

---

## 14. CHANGELOG

변경사항은 아래 형식으로 이 섹션 아래에 계속 추가합니다.

```
### YYYY-MM-DD
- Changed: 변경한 내용
- Reason: 변경 이유
- Impact: 기존 데이터 및 점수에 미치는 영향
```

<!-- 아래에 변경 이력 추가 -->

### 2026-09-18
- Changed: `tariff_rate`/`tariff_accessibility`의 데이터 소스를 관세청 Open API 직접 호출에서, 관세/무역 뉴스 Open API 크롤링 + AI Insight 기반 관세율 동향 추정 방식으로 변경.
- Reason: 관세율은 변동성이 크고 관세청 API는 승인 지연 등 실시간성 문제가 있어, 최신 뉴스 기반 추정 방식이 더 안정적으로 운영 가능하다고 판단.
- Impact: `tariff_rate` 컬럼 값은 공식 수치가 아닌 뉴스 기반 AI 추정치였으며, 근거 뉴스가 없는 경우 관련 문장을 생성하지 않음.

### 2026-09-18 (2)
- Changed: `tariff_accessibility`를 Korea Penetration Opportunity Score 가중치 공식에서 완전히 제외하고 나머지 5개 지표(`low_korea_share×0.29 + export_gap×0.29 + korea_export_growth×0.18 + competition_openness×0.12 + logistics_accessibility×0.12`)로 재분배.
- Reason: 관세율을 점수화하지 않고 뉴스 기반 AI Insight 서술형 텍스트로만 제공하기로 결정.
- Impact: 구 공식 기준 Penetration/Blue Ocean Score는 재계산 필요. (※ 아래 2026-09-19 항목에서 전면 대체됨)

### 2026-09-18 (3)
- Changed: `src/score_engine_C.py`에서 결측 지표를 제외하고 남은 지표의 가중치 합이 1.0이 되도록 비례 재분배하는 방식으로 변경.
- Reason: `logistics_days` 수집 로직 부재로 점수가 항상 NaN이 되는 문제.
- Impact: 결측 지표가 있는 국가도 0~100 점수를 받음. (※ 2026-09-19 항목에서 필수/선택 지표 구분으로 정교화됨)

### 2026-09-19
- Changed: 스코어링 체계를 전면 개편. (1) 데이터 처리를 깔때기 방식으로 확정: 수입 500만 달러 이하 컷 → 간이 점수로 전체 국가 순위화 → **상위 50개국만** 후보 선별(랜덤/층화추출 없음) → 후보에 정밀 수집 → 상위 20개국 출력. (2) 가중치 방식(합계 1.0, Market×Penetration 기하평균)을 **100점 배점 합산 방식**으로 교체: 시장 규모 15, CAGR 15, 전년 성장률 10, 한국 수출 비중 25, 경쟁 개방성(top3 집중도) 15, 관세 10, Google 트렌드 5, 최근 3년 환율 추이 5. (3) `tariff_rate`를 점수(10점)에 다시 반영. (4) `fx_change_3y` 신규 추가. (5) `export_gap`, `korea_export_growth`, `logistics_days`, `seasonality`를 점수에서 제외하고 참고/설명용으로만 사용(`export_gap`은 상세 분석, `seasonality`는 진출 타이밍 설명). (6) 필수/선택 지표를 구분하는 결측 규칙과 `score_coverage` 추가. (7) 정규화 기준 집합 명시(간이 점수=U, 최종=T). (8) 출력에 전체 마켓 사이즈, 1위 추천 타깃, 경쟁국, 수입 규모 추가 (랭킹 마지막 열의 KOTRA 표시는 수입 규모로 대체). (9) Top 랭킹 노출을 10개에서 20개로 변경.
- Reason: 팀 기획 변경. 최종 결과를 직관적인 100점제로 설명 가능하게 하고, API 호출량을 줄이면서(상위 50개국만 정밀 수집) 랜덤 샘플링의 부정확성과 비재현성을 없애기 위함.
- Impact: 모든 점수 수치가 기존과 달라지므로 전체 재계산이 필요. `score_engine_C.py`의 `market_weights`/`penetration_weights`는 4-1번 배점표로 교체 필요. 기하평균에 있던 "한쪽만 높은 국가 억제" 효과가 사라지므로 두 영역 점수의 편차가 큰 국가는 상세 화면에서 함께 보여준다. `DATA_SCHEMA.md`의 `global_korea_share` 단위 표기를 0~1 비율로 통일.

---

## 15. 미확정 항목 (팀 확정 후 이 섹션에서 삭제하고 본문에 반영)

| 항목 | 현재 초안 | 확정 필요 사유 |
|---|---|---|
| `fx_change_3y` 정의 | 현지통화의 USD 대비 3년 변동률, 약세일수록 감점 | 환율 기준 통화쌍(현지통화/USD vs 원화 등)과 방향성이 요구사항에 명시되지 않음 |
| `tariff_rate` 소스 | 미정 | 점수에 쓰려면 검증 가능한 수치가 필요. 뉴스 기반 AI 추정치는 점수용으로 부적합할 수 있음 |
| `underpenetrated_flag`의 필터 여부 | 표시용, 순위 제외 안 함 | 구 공식에서는 필수 필터였음 |
| 극단값 처리 | 상하위 5% winsorize 검토 | `cagr_3y`, `growth_1y`의 소규모 시장 급등 왜곡 방지 |
| 간이 점수 검증 기준 | 상위 20 재현율(recall@20) ≥ 0.9 | HS CODE 10~20개로 "전체 국가 정밀 점수 상위 20"과 "깔때기 상위 20"의 겹침 비율을 비교 후 미달 시 후보 수(50) 재협의 |
