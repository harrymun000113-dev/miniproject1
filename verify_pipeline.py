"""오프라인 검증. 모든 데이터는 테스트용 가상 데이터이며 네트워크 호출 없음."""
import ast
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from src.collect_data_A import fetch_trade_data
from src.preprocess_kpi_B import preprocess_kpi_b, raw_columns


if __name__ == '__main__':
    for path in Path(__file__).parent.rglob('*.py'):
        source = path.read_text(encoding='utf-8-sig')
        ast.parse(source, filename=str(path), feature_version=(3, 11))
        compile(source, str(path), 'exec')
    df = pd.DataFrame([
        ['Alpha', '1', '010121', 'Test', '2020', '100', '10'],
        ['Alpha', '1', '010121', 'Test', '2022', '125', '10'],
        ['Alpha', '1', '010121', 'Test', '2023', '200', '20'],
        ['Beta', '2', '010121', 'Test', '2023', '300', '90'],
    ], columns=raw_columns)
    original = df.copy(deep=True)
    result = preprocess_kpi_b(df, exchange_rate=1300, full_country_coverage=True)
    assert_frame_equal(df, original)
    current = result.loc[result['country_code'].eq('1') & result['year'].eq(2023)].iloc[0]
    assert np.isclose(current['growth_1y'], 60)
    assert np.isclose(current['cagr_3y'], (2 ** (1 / 3) - 1) * 100)
    assert np.isclose(current['korea_export_growth'], 100)
    assert np.isclose(current['global_korea_share'], .22)
    assert np.isclose(current['export_gap'], .12)
    assert current['import_value_krw'] == 260000
    assert result.loc[result['year'].eq(2022), 'growth_1y'].isna().all()
    assert preprocess_kpi_b(df)['global_korea_share'].isna().all()
    assert preprocess_kpi_b(df)['import_value_krw'].isna().all()
    assert result['hs_code'].eq('010121').all()
    assert str(result['year'].dtype) == 'Int64'
    duplicate = preprocess_kpi_b(pd.concat([df, df.iloc[[0]]], ignore_index=True))
    assert len(duplicate) == len(df)
    assert duplicate.attrs['quality_report']['exact_duplicates_removed'] == 1
    conflict = df.iloc[[0]].copy()
    conflict['market_size'] = '999'
    try:
        preprocess_kpi_b(pd.concat([df, conflict], ignore_index=True))
    except ValueError:
        pass
    else:
        raise AssertionError('충돌 중복을 거부해야 합니다.')
    bad = pd.DataFrame([
        [None, '3', '010121', None, '2023.5', 'invalid', None],
        ['Zero', '4', '010121', 'Test', '2023', '0', '0'],
        ['Negative', '5', '010121', 'Test', '2023', '-1', 'inf'],
    ], columns=raw_columns)
    cleaned = preprocess_kpi_b(bad, full_country_coverage=True)
    assert pd.isna(cleaned.loc[0, 'country']) and pd.isna(cleaned.loc[0, 'year'])
    assert cleaned['korea_market_share'].isna().all()
    assert pd.isna(cleaned.loc[2, 'market_size'])
    assert pd.isna(cleaned.loc[2, 'korea_export_usd'])
    partial = df.copy()
    partial.loc[3, 'korea_export_usd'] = None
    partial_result = preprocess_kpi_b(partial, full_country_coverage=True)
    assert partial_result.loc[partial_result['year'].eq(2023), 'global_korea_share'].isna().all()
    assert preprocess_kpi_b(pd.DataFrame(columns=raw_columns)).empty
    query = pd.DataFrame({'hs_code': ['010121'], 'year': [2023], 'country_code': ['1']})
    responses = []
    for partner, amount in [(0, 200), (410, 20)]:
        response = MagicMock()
        response.json.return_value = {'data': [{
            'reporterCode': 1, 'partnerCode': partner, 'refYear': 2023,
            'partner2Code': 0, 'motCode': 0, 'customsCode': 'C00', 'flowCode': 'M',
            'cmdCode': '010121', 'reporterDesc': 'Alpha', 'cmdDesc': 'Test', 'primaryValue': amount,
        }]}
        responses.append(response)

    with patch.dict(os.environ, {'COMTRADE_API_KEY': 'test_only'}), patch('src.collect_data_A.load_dotenv'), patch('src.collect_data_A.requests.Session') as mocked:

    with patch.dict(os.environ, {'UN_COMTRADE_API_KEY': 'test_only'}), patch('src.collect_data_A.load_dotenv'), patch('src.collect_data_A.requests.Session') as mocked:

        session = mocked.return_value.__enter__.return_value
        session.get.side_effect = responses
        collected = fetch_trade_data(query)
        assert collected.loc[0, 'market_size'] == 200
        assert collected.loc[0, 'korea_export_usd'] == 20
        assert session.get.call_count == 2
        assert session.get.call_args.kwargs['params']['partnerCode'] == '410'

    with patch.dict(os.environ, {'COMTRADE_API_KEY': ''}), patch('src.collect_data_A.load_dotenv'):

    with patch.dict(os.environ, {'UN_COMTRADE_API_KEY': ''}), patch('src.collect_data_A.load_dotenv'):

        try:
            fetch_trade_data(query)
        except EnvironmentError:
            pass
        else:
            raise AssertionError('키 누락은 오류여야 합니다.')
    print('PASS: Python 3.11 문법 호환, KPI/결측/타입/연도/중복/원본 보호/API 매핑 검증')
