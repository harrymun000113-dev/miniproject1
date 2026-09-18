"""B: DATA_SCHEMA 원본 → 결측 보존, 타입 정제, KPI DataFrame. Python 3.11."""
import numpy as np
import pandas as pd

raw_columns = ['country', 'country_code', 'hs_code', 'item_name', 'year',
               'market_size', 'korea_export_usd']
key_columns = ['country_code', 'hs_code', 'year']


def clean_trade_data(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Input: 수집 스키마 DataFrame. Output: 정제한 동일 스키마 DataFrame."""
    df = raw_df.copy()
    missing = set(raw_columns) - set(df.columns)
    if missing:
        raise ValueError(f'필수 컬럼 누락: {sorted(missing)}')
    df = df[raw_columns].copy()
    for column in ['country', 'country_code', 'hs_code', 'item_name']:
        df[column] = df[column].astype('string').str.strip().replace('', pd.NA)
    # HS2/4/6 혼용 가능: 임의 zero-padding이나 숫자 추측 복구 금지.
    invalid_hs = df['hs_code'].notna() & ~df['hs_code'].str.fullmatch(r'\d{2}|\d{4}|\d{6}', na=False)
    if invalid_hs.any():
        raise ValueError('hs_code는 앞자리 0을 보존한 HS2/4/6 문자열이어야 합니다.')
    year = pd.to_numeric(df['year'], errors='coerce')
    df['year'] = year.where(np.isfinite(year) & year.between(1, 9999) & year.mod(1).eq(0)).astype('Int64')
    for column in ['market_size', 'korea_export_usd']:
        values = pd.to_numeric(df[column], errors='coerce').astype('float64')
        df[column] = values.where(np.isfinite(values) & values.ge(0))
    exact_duplicates = int(df.duplicated().sum())
    df = df.drop_duplicates().reset_index(drop=True)
    valid_keys = df[key_columns].notna().all(axis=1)
    if df.loc[valid_keys].duplicated(key_columns).any():
        raise ValueError('국가×HS×연도 키에 서로 다른 중복 행이 있습니다. A 수집 조건을 확인하세요.')
    invalid_share = df['korea_export_usd'].gt(df['market_size'])
    # 오류 금액을 임의 수정하지 않고, 해당 점유율만 이후 NaN 처리.
    df.attrs['quality_report'] = {
        'rows_input': len(raw_df), 'rows_output': len(df),
        'exact_duplicates_removed': exact_duplicates,
        'missing_key_rows': int((~df[key_columns].notna().all(axis=1)).sum()),
        'korea_export_exceeds_market': int(invalid_share.sum()),
        'missing_by_column': df.isna().sum().astype(int).to_dict(),
    }
    return df


def preprocess_kpi_b(raw_df: pd.DataFrame, exchange_rate: float | None = None,
                     *, full_country_coverage: bool = False) -> pd.DataFrame:
    """Input: 전체 국가의 연도별 원본 DataFrame, 선택 USD/KRW 환율.

    Output: 원본 7컬럼 + 스키마의 KPI 6컬럼 + korea_export_growth.
    full_country_coverage=True는 호출자가 전체 비교국 수집을 확인한 경우에만 설정.
    누락 금액/키가 있는 HS×연도는 세계점유율을 NaN으로 유지한다.
    """
    df = clean_trade_data(raw_df)
    quality_report = df.attrs['quality_report'].copy()
    if exchange_rate is not None and (not np.isfinite(exchange_rate) or exchange_rate <= 0):
        raise ValueError('exchange_rate는 양의 유한한 USD/KRW 환율이어야 합니다.')
    df['import_value_krw'] = df['market_size'] * (exchange_rate if exchange_rate is not None else np.nan)
    valid_share = df['market_size'].gt(0) & df['korea_export_usd'].le(df['market_size'])
    df['korea_market_share'] = (df['korea_export_usd'] / df['market_size']).where(valid_share)
    # shift/pct_change는 연도 공백을 건너뛰므로 정확한 t-1, t-3 키로 결합한다.
    valid_keys = df[key_columns].notna().all(axis=1)
    for column, lag, output in [('market_size', 1, 'growth_1y'),
                                ('market_size', 3, 'cagr_3y'),
                                ('korea_export_usd', 1, 'korea_export_growth')]:
        history = df.loc[valid_keys, key_columns + [column]].copy()
        history['year'] = history['year'] + lag
        history = history.rename(columns={column: '_base'})
        df = df.merge(history, on=key_columns, how='left', validate='many_to_one', sort=False)
        ratio = df[column] / df['_base'].where(df['_base'].gt(0))
        df[output] = (ratio.pow(1 / lag) - 1) * 100
        df = df.drop(columns='_base')
    df['global_korea_share'] = np.nan
    if full_country_coverage:
        # 동일 국가 집합의 합계 비율. 부분 결측을 sum(skipna=True)로 숨기지 않는다.
        for _, group in df.groupby(['hs_code', 'year'], dropna=True):
            complete = group[key_columns + ['market_size', 'korea_export_usd']].notna().all().all()
            consistent = group['korea_export_usd'].le(group['market_size']).all()
            total_market = group['market_size'].sum(min_count=1)
            if complete and consistent and total_market > 0:
                df.loc[group.index, 'global_korea_share'] = group['korea_export_usd'].sum() / total_market
    df['export_gap'] = (df['global_korea_share'] - df['korea_market_share']).clip(lower=0)
    output_columns = raw_columns + ['import_value_krw', 'korea_market_share', 'growth_1y',
                                    'cagr_3y', 'global_korea_share', 'export_gap', 'korea_export_growth']
    df = df[output_columns].copy()
    for column in output_columns[5:]:
        df[column] = pd.to_numeric(df[column], errors='coerce').astype('float64')
        df[column] = df[column].where(np.isfinite(df[column]))
    quality_report['full_country_coverage_confirmed'] = full_country_coverage
    quality_report['missing_kpi_by_column'] = df[output_columns[7:]].isna().sum().astype(int).to_dict()
    df.attrs['quality_report'] = quality_report
    return df


if __name__ == '__main__':
    print('B 모듈 준비 완료. preprocess_kpi_b(DataFrame, exchange_rate=...)로 실행하세요.')
