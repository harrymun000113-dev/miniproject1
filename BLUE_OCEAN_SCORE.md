# BLUE_OCEAN_SCORE.md
### Blue Ocean Score 알고리즘 명세서 (Single Source of Truth)

> 이 문서는 프로젝트의 핵심 알고리즘 기준 문서입니다.
> GPT, Gemini, Claude, Cursor 등 어떤 AI를 쓰더라도 이 문서를 먼저 읽고, 여기 정의된 변수명·공식·가중치를 그대로 따라야 합니다.
> 특정 AI 전용 문법, HTML, 플러그인 기능에 의존하지 않고 순수 Markdown으로만 작성되어 있습니다.

---

## 1. 프로젝트 목적

특정 HS CODE를 기준으로 전 세계 국가를 분석하여,

> "시장 수요와 성장성은 높지만 한국산 제품의 시장 침투율은 상대적으로 낮은 국가"

를 발굴하는 서비스입니다.

기존의 단순한 "수출 유망국가 추천"(예: TriBIG)과 달리, **한국이 아직 충분히 진출하지 못한 미개척 시장(Blue Ocean Market)** 을 찾는 것이 핵심입니다.

---

## 2. Core Concept

Blue Ocean Score는 두 개의 하위 점수로 구성됩니다.

1. **Market Opportunity Score** — 해당 국가의 시장 자체가 매력적인지 평가
2. **Korea Penetration Opportunity Score** — 한국 기업이 추가로 진출할 여지가 있는지 평가

두 점수를 결합해 최종 **Blue Ocean Score**를 산출합니다.

---

## 3. Market Opportunity Score

### 3-1. 사용 지표

| 변수명 | 지표 | 설명 | 방향 |
|---|---|---|---|
| `market_size` | 수입시장 규모 | 해당 국가의 해당 HS코드 총수입액 | 높을수록 좋음 |
| `cagr_3y` | 3년 CAGR | 최근 3년 수입시장 연평균 성장률 | 높을수록 좋음 |
| `growth_1y` | 최근 1년 성장률 | 전년 대비 수입시장 성장률 | 높을수록 좋음 |
| `google_trend` | Google Trends | 해당 상품/키워드 관심도 | 높을수록 좋음 |
| `seasonality` | 계절성 지수 | 현재/향후 수요 발생 가능성 | 높을수록 좋음 |

### 3-2. 가중치 공식

```
Market Opportunity Score
  = market_size_score        × 0.25
  + cagr_3y_score             × 0.30
  + growth_1y_score           × 0.25
  + google_trend_score        × 0.10
  + seasonality_score         × 0.10

(가중치 총합 = 1.00)
```

---

## 4. Korea Penetration Opportunity Score

### 4-1. 사용 지표

| 변수명 | 지표 | 설명 | 방향 |
|---|---|---|---|
| `low_korea_share` | 낮은 한국산 점유율 | 해당 국가 내 한국산 점유율이 얼마나 낮은지 | 낮을수록(=점수는) 높게 |
| `export_gap` | Export Gap | 한국 세계평균 점유율 대비 해당국 한국산 점유율 차이 | 높을수록 좋음 |
| `korea_export_growth` | 한국 수출 증가율 | 해당국으로의 한국산 수출 증가율 | 높을수록 좋음 |
| `competition_openness` | 경쟁시장 개방성 | 특정 경쟁국의 독점 정도가 낮은지 | 개방적일수록 좋음 |
| `logistics_accessibility` | 물류 접근성 | 한국→해당국 공급 용이성 | 물류부담 낮을수록 좋음 |

> `tariff_accessibility`(관세 접근성)는 2026-09-18부로 이 가중치 공식에서 제외되었습니다. 관세율은 변동성이 커서 점수화하지 않고, 11-1번의 뉴스 기반 AI Insight 텍스트로만 제공합니다.

### 4-2. 가중치 공식

```
Korea Penetration Opportunity Score
  = low_korea_share_score        × 0.29
  + export_gap_score              × 0.29
  + korea_export_growth_score     × 0.18
  + competition_openness_score    × 0.12
  + logistics_accessibility_score × 0.12

(가중치 총합 = 1.00)
```

---

## 5. Export Gap (핵심 독자 지표)

### 공식
```
Export Gap = MAX(한국의 해당 품목 세계시장 평균 점유율 - 해당 국가의 한국산 시장점유율, 0)
```

### 예시
- 한국의 HS 330499 세계시장 평균 점유율 = 8.1%
- 멕시코 내 한국산 HS 330499 점유율 = 1.0%
- Export Gap = 8.1% - 1.0% = **7.1%p**

### 의미
"한국이 해당 품목 자체에서 경쟁력이 없는 것이 아니라, 세계시장 평균과 비교했을 때 특정 국가에서 상대적으로 시장 침투가 부족하다"는 것을 나타냄.

Export Gap이 클수록 미개척 가능성이 높은 것으로 해석하되, **Export Gap이 크다는 이유만으로 Blue Ocean이라 판단하면 안 됨.** 시장규모·성장률·관세·경쟁국·물류를 함께 고려해야 함.

---

## 6. Normalization (정규화)

모든 지표는 단위가 다르므로 0~100점으로 정규화합니다.

### 6-1. Positive Indicator (높을수록 좋은 지표)
```
Score = ((x - min) / (max - min)) × 100
```
적용 대상: 시장성장률, CAGR, 한국 수출 증가율, Export Gap 등

### 6-2. Negative Indicator (낮을수록 좋은 지표)
```
Score = ((max - x) / (max - min)) × 100
```
적용 대상: 한국산 기존 점유율, 물류일수, 경쟁국 시장 집중도 등

### 6-3. Market Size Normalization (로그 변환)
시장규모는 초대형 시장(미국·중국 등) 때문에 다른 국가 값이 지나치게 왜곡될 수 있어, 일반 Min-Max 대신 로그 변환을 우선 적용합니다.
```
Market Size Score = ((log(x) - log(min)) / (log(max) - log(min))) × 100
```

### 6-4. 실제 개발 시 주의사항
5개국 정도의 소규모 min-max 대신, **UN Comtrade 조회 대상국 100~200개 전체를 기준으로 percentile 또는 winsorized normalization**을 적용하는 것을 권장합니다. 비교 국가가 하나 추가될 때마다 기존 점수가 급격히 변하는 문제를 줄일 수 있습니다.

---

## 7. Final Blue Ocean Score

단순 산술평균이 아닌 **기하평균**을 기본 방식으로 사용합니다.

```
Blue Ocean Score = SQRT(Market Opportunity Score × Korea Penetration Opportunity Score)
```

### 기하평균을 쓰는 이유
한쪽 점수만 지나치게 높은 국가가 최상위에 노출되는 것을 방지하기 위함.

**예시**
- Market Opportunity = 100, Korea Penetration = 20
- 산술평균: (100+20)/2 = 60
- 기하평균: SQRT(100×20) ≈ 44.72

→ 기하평균을 쓰면 양쪽 조건이 균형 있게 높은 국가만 상위에 올라옴.

---

## 8. Initial Filtering Rule

모든 국가를 바로 Blue Ocean 후보로 간주하지 않습니다.

### 기본 필터
```
해당 국가의 한국산 시장점유율 < 한국의 해당 상품 세계시장 평균점유율
```
이 조건을 만족하는 국가만 1차 Blue Ocean 후보로 분류합니다.

### 추가 필터 (향후 확장 시 고려)
- 최소 시장규모
- 최소 수입액
- 최소 CAGR
- 데이터 부족 국가 제외
- 무역제재 국가 제외
- 극단값(outlier) 제거
- 관세가 지나치게 높은 국가 제외

---

## 9. Example Dataset (테스트용 가상 데이터)

**품목**: HS CODE = 330499 (기타 화장품)
**한국의 세계시장 평균 점유율**: 8.1%

| 국가 | 시장규모($M) | CAGR(%) | 최근성장률(%) | Trend | 계절성 | 한국점유율(%) | 한국수출증가율(%) | Top3집중도(%) | 관세(%) | 물류일수 |
|---|---|---|---|---|---|---|---|---|---|---|
| Mexico | 900 | 16 | 14 | 82 | 85 | 1.0 | 20 | 64 | 10 | 18 |
| UAE | 650 | 21 | 24 | 90 | 75 | 1.5 | 18 | 70 | 5 | 12 |
| Poland | 800 | 18 | 15 | 75 | 80 | 3.0 | 15 | 58 | 0 | 20 |
| USA | 5200 | 12 | 10 | 68 | 70 | 12.5 | 8 | 42 | 0 | 14 |
| Japan | 2100 | 3 | 2 | 55 | 55 | 20.0 | -2 | 55 | 0 | 5 |

⚠️ **이 데이터는 실제 데이터가 아니라 알고리즘 테스트 및 UI 개발용 가상 데이터입니다.** 실제 서비스에서는 API/공식 데이터로 반드시 교체해야 합니다.

### 계산 결과 예시 (가상 데이터 기준)

| 순위 | 국가 | Market Opportunity | Penetration Opportunity | Blue Ocean Score |
|---|---|---|---|---|
| 1 | UAE | 71.7 | 74.1 | 72.8 |
| 2 | Poland | 56.3 | 71.2 | 63.3 |
| 3 | Mexico | 56.9 | 68.5 | 62.4 |
| - | USA | 57.8 | 45.7 | 51.4 (필터 제외 대상) |
| - | Japan | 14.1 | 30.4 | 20.7 (필터 제외 대상) |

> ⚠️ 위 Penetration Opportunity 수치는 2026-09-18 가중치 변경(관세 항목 제외, 4-2번 참고) 이전 예시로, 참고용 가상 데이터입니다. 실제 값은 현재 공식으로 재계산해야 합니다.

USA·Japan은 한국산 점유율(12.5%, 20.0%)이 한국 세계평균(8.1%)보다 이미 높으므로 8번 필터링 규칙에 따라 최종 후보에서 제외됩니다.

**중요한 해석 포인트**: Export Gap만 보면 Mexico가 1위지만, 물류 등 진입 가능성까지 반영하면 UAE가 최종 1위가 됩니다. 이 차이가 단순 무역통계와 이 서비스의 차별점입니다. (표의 관세(%) 열은 점수에는 반영되지 않으며, 11-1번 방식의 AI Insight 문장 참고용 예시입니다.)

---

## 10. Expected Output (최종 결과 필드)

| field | 설명 |
|---|---|
| `country` | 국가 |
| `hs_code` | HS CODE |
| `market_opportunity_score` | 시장 매력도 |
| `penetration_opportunity_score` | 한국 침투 기회 |
| `blue_ocean_score` | 최종 점수 |
| `korea_market_share` | 한국산 시장점유율 |
| `global_korea_share` | 한국 세계시장 평균점유율 |
| `export_gap` | Export Gap |
| `market_size` | 시장규모 |
| `cagr_3y` | 3년 CAGR |
| `korea_export_growth` | 한국 수출 증가율 |

최종 결과는 `blue_ocean_score` 기준 내림차순 정렬합니다.

---

## 11. AI Insight Generation Rule

점수만 보여주지 말고, 사용자가 이유를 이해할 수 있도록 자연어로 설명해야 합니다.

**규칙**: AI 분석 문장은 반드시 실제 계산된 데이터에 근거해야 하며, 데이터에 없는 이유를 임의로 만들어내면 안 됩니다.

**예시 문장**
> "UAE의 해당 품목 시장은 최근 3년간 연평균 21% 성장했습니다. 한국산 점유율은 1.5%로 한국의 세계 평균 점유율 8.1%보다 낮아 6.6%p의 Export Gap이 존재합니다. 또한 한국산 수입이 최근 18% 증가하고 있어 초기 시장 침투 신호가 나타나고 있습니다. 따라서 시장 성장성과 한국산 추가 침투 가능성이 동시에 높은 시장으로 분석됩니다."

### 11-1. 관세율 처리 방식 (뉴스 기반 AI 추정)

관세율은 국가·품목별로 변동성이 매우 크고, 관세청 Open API는 승인 지연 등 실시간성이 떨어지는 문제가 있습니다. 이에 따라 `tariff_accessibility`는 **4-2번 가중치 공식에서 완전히 제외**되었고, `tariff_rate`는 점수 계산에 쓰이지 않는 AI Insight 전용 텍스트 지표로만 남습니다. 관세청 API는 이 프로젝트에서 호출하지 않습니다.

1. Open API로 관세·무역 관련 최신 뉴스를 크롤링한다 (관세 인상/인하, FTA 협상, 무역분쟁 등).
2. AI가 크롤링된 뉴스를 바탕으로 해당 HS코드·국가의 최신 관세율 동향을 추정하고, 이를 AI Insight 문장에 서술형으로만 반영한다 (Blue Ocean Score 계산에는 포함하지 않음).

**규칙**
- 뉴스에 근거하지 않은 관세율 수치를 임의로 생성하지 않는다.
- 관세율 추정은 "뉴스 기반 추정치"이며 점수에 반영되지 않는다는 점을 AI Insight 문장에 명시한다 (예: "최근 뉴스에 따르면 관세율이 인상될 가능성이 있습니다" 등 근거를 함께 제시).
- 관련 뉴스가 확보되지 않는 국가/품목은 관세 관련 문장을 생성하지 않는다 (단정하지 않음).

---

## 12. Data Source Plan

실제 개발 단계에서 검토할 데이터 소스입니다. (확정 여부는 `DATA_SCHEMA.md` 참고)

| 카테고리 | 소스 후보 |
|---|---|
| 국가별 수출입 (HS코드, 연도별/월별) | UN Comtrade |
| 한국 수출입 데이터 | 한국무역협회(KITA), 공공데이터포털 |
| 상품 관심도/검색 트렌드 | Google Trends (pytrends) |
| 관세 데이터 (관세율, FTA 여부) | 관세청 API 대신 관세/무역 뉴스 Open API 크롤링 → AI Insight가 최신 관세율 동향을 추정 반영 (11-1번 참고) |
| 물류 데이터 (운송거리/기간) | 자체 계산 또는 근사치 사용 |

각 데이터 소스는 실제 API 사용 가능 여부와 라이선스를 확인한 후 확정합니다. 확보되지 않은 지표(물류·Google Trends 등)는 소수 국가만 하드코딩하거나, 1차 버전에서는 제외하고 향후 확장 항목으로 명시해도 됩니다.

---

## 13. Development Principles

1. 기존 변수명을 임의로 변경하지 않는다.
2. 기존 점수 공식과 가중치를 임의로 변경하지 않는다.
3. 공식 변경이 필요한 경우 기존 공식과 변경안을 모두 제시하고 변경 이유를 설명한다.
4. 가중치 총합은 반드시 1.0이 되어야 한다.
5. 실제 데이터와 가상 데이터를 명확히 구분한다 (가상 데이터는 반드시 "예시/테스트용"이라고 표기).
6. 데이터가 없는 경우 임의의 값을 생성하지 않는다.
7. 통계적으로 불안정한 값(표본 부족 등)은 사용자에게 명시한다.
8. 모든 점수는 가능한 한 0~100 범위로 통일한다.
9. 코드 구현 시 변수명은 이 문서의 정의와 정확히 일치시킨다.
10. 특정 AI 서비스에 종속되는 문법을 사용하지 않는다 (순수 Markdown/Python만 사용).
11. 알고리즘 변경 시 반드시 하단 CHANGELOG에 기록한다.

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
- Changed: `tariff_rate`/`tariff_accessibility`의 데이터 소스를 관세청 Open API 직접 호출에서, 관세/무역 뉴스 Open API 크롤링 + AI Insight 기반 관세율 동향 추정 방식으로 변경 (11-1번 참고).
- Reason: 관세율은 변동성이 크고 관세청 API는 승인 지연 등 실시간성 문제가 있어, 최신 뉴스 기반 추정 방식이 더 안정적으로 운영 가능하다고 판단.
- Impact: `tariff_rate` 컬럼 값은 이제 공식 수치가 아닌 뉴스 기반 AI 추정치이며, 근거 뉴스가 없는 경우 관련 문장을 생성하지 않음.

### 2026-09-18 (2)
- Changed: `tariff_accessibility`를 Korea Penetration Opportunity Score 가중치 공식(4-2번)에서 완전히 제외. 기존 공식: `low_korea_share×0.25 + export_gap×0.25 + korea_export_growth×0.15 + competition_openness×0.10 + tariff_accessibility×0.15 + logistics_accessibility×0.10`. 변경 후 공식: `low_korea_share×0.29 + export_gap×0.29 + korea_export_growth×0.18 + competition_openness×0.12 + logistics_accessibility×0.12` (제외된 0.15를 나머지 5개 지표에 비례 재분배). `src/score_engine_C.py`의 `penetration_weights`도 동일하게 수정.
- Reason: 관세율을 더 이상 점수화하지 않고 뉴스 기반 AI Insight 서술형 텍스트로만 제공하기로 결정 (위 항목 참고). 점수화하지 않는 지표를 가중치 공식에 남겨두면 혼선이 생기므로 공식에서도 제거.
- Impact: Korea Penetration/Blue Ocean Score 수치가 기존 대비 달라짐 (재계산 필요). 9번 예시 표의 Penetration Opportunity 수치는 구 공식 기준이므로 참고용으로만 사용.
