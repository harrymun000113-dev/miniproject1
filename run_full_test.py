"""A(수집)+top3+구글트렌드(계절성 포함) → B(전처리) → C(점수) 전체 흐름을 한 번에 테스트."""
import pandas as pd
from src.collect_data_A import fetch_trade_data, fetch_top3_concentration, fetch_google_trend
from src.preprocess_kpi_B import preprocess_kpi_b
from src.score_engine_C import score_engine_c

query = pd.DataFrame({
    'hs_code': ['330499'] * 8,
    'year': [2020, 2021, 2022, 2023, 2020, 2021, 2022, 2023],
    'country_code': [842, 842, 842, 842, 704, 704, 704, 704],
})

print('1) 무역 데이터 수집 중...')
raw = fetch_trade_data(query)

print('2) 전처리 중...')
processed = preprocess_kpi_b(raw, exchange_rate=1350, full_country_coverage=True)

print('3) 상위3개국 점유율 수집 중...')
top3 = fetch_top3_concentration(query)

print('4) 구글트렌드+계절성 수집 중...')
trend = fetch_google_trend(query)
print(trend)

print('5) 보조지표 합치는 중...')
merged = processed.merge(top3, on=['country_code', 'hs_code', 'year'], how='left') \
                  .merge(trend, on=['country_code', 'hs_code', 'year'], how='left')
merged['hs_code'] = merged['hs_code'].astype(str)
merged['country_code'] = merged['country_code'].astype(str)
print(merged[['country_code', 'hs_code', 'year', 'top3_concentration', 'seasonality', 'google_trend']])

print('6) 점수 계산 중...')
result = score_engine_c(merged)
print(result[['country_code', 'hs_code', 'year',
             'market_opportunity_score', 'penetration_opportunity_score',
             'blue_ocean_score', 'rank']])