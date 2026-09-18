"""C: MD 고정 가중치와 기하평균. 지표 부족 시 점수를 만들어내지 않는다."""
import numpy as np
import pandas as pd

market_weights = {'market_size': .25, 'cagr_3y': .30, 'growth_1y': .25,
                  'google_trend': .10, 'seasonality': .10}
penetration_weights = {'korea_market_share': .25, 'export_gap': .25,
                       'korea_export_growth': .15, 'top3_concentration': .10,
                       'tariff_rate': .15, 'logistics_days': .10}


def score_engine_c(input_df: pd.DataFrame) -> pd.DataFrame:
    """Input: B 출력 + 확보한 보조지표 DF. Output: MD 점수 3컬럼 및 후보 rank DF.

    HS×연도 전체 국가에서 정규화 후 후보 순위를 부여한다. 상수 지표(min=max)는
    MD 공식 분모가 0이므로 NaN. 가중치를 임의 재분배하지 않는다.
    """
    df = input_df.copy()
    for column in set(market_weights) | set(penetration_weights):
        if column not in df:
            df[column] = np.nan
        df[column] = pd.to_numeric(df[column], errors='coerce').astype(float)
        df[column] = df[column].where(np.isfinite(df[column]))
    for column in ['google_trend', 'seasonality', 'top3_concentration']:
        df[column] = df[column].where(df[column].between(0, 100))
    for column in ['tariff_rate', 'logistics_days']:
        df[column] = df[column].where(df[column].ge(0))
    for output in ['market_opportunity_score', 'penetration_opportunity_score', 'blue_ocean_score']:
        df[output] = np.nan
    df['rank'] = pd.Series(pd.NA, index=df.index, dtype='Int64')
    notes = []
    for (hs_code, year), group in df.groupby(['hs_code', 'year'], dropna=True):
        normalized = pd.DataFrame(index=group.index)
        for column in set(market_weights) | set(penetration_weights):
            values = group[column]
            if column == 'market_size':
                values = np.log(values.where(values.gt(0)))
            low, high = values.min(), values.max()
            if pd.isna(low) or high == low:
                normalized[column] = np.nan
                notes.append({'hs_code': str(hs_code), 'year': int(year), 'indicator': column,
                              'reason': 'missing_or_constant'})
            else:
                normalized[column] = (values - low) / (high - low) * 100
                if column in ('korea_market_share', 'top3_concentration', 'tariff_rate', 'logistics_days'):
                    normalized[column] = 100 - normalized[column]
        for weights, output in [(market_weights, 'market_opportunity_score'),
                                (penetration_weights, 'penetration_opportunity_score')]:
            contributions = normalized[list(weights)].mul(pd.Series(weights))
            df.loc[group.index, output] = contributions.sum(axis=1, min_count=len(weights))
        df.loc[group.index, 'blue_ocean_score'] = np.sqrt(
            df.loc[group.index, 'market_opportunity_score'] * df.loc[group.index, 'penetration_opportunity_score'])
        candidates = group['korea_market_share'].lt(group['global_korea_share'])
        indexes = group.index[candidates.fillna(False)]
        df.loc[indexes, 'rank'] = df.loc[indexes, 'blue_ocean_score'].rank(method='min', ascending=False).astype('Int64')
    df.attrs['score_report'] = {'mode': 'MD fixed weights; missing indicator => missing score', 'notes': notes}
    df['logistics_days'] = df['logistics_days'].where(df['logistics_days'].mod(1).eq(0)).astype('Int64')
    return df.sort_values(['hs_code', 'year', 'blue_ocean_score'], ascending=[True, False, False], na_position='last')


if __name__ == '__main__':
    print('C 모듈 준비 완료. 점수는 보조지표가 확보된 경우에 계산됩니다.')