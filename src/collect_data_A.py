"""A: .env 인증 및 UN Comtrade 연간 수입 수집. 실제 API 실패 시 가상 대체 금지."""
import os
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv


def fetch_trade_data(query_df: pd.DataFrame) -> pd.DataFrame:
    """Input: hs_code, year, country_code(Comtrade reporter 코드) DataFrame.

    Output: DATA_SCHEMA.md의 원본 7컬럼 DataFrame.
    국가×품목×연도당 세계발(0), 한국발(410)을 따로 조회한다.
    국가 목록은 실제 분석 대상국 전체를 호출자가 제공한다.
    """
    df = query_df.copy()
    required = ['hs_code', 'year', 'country_code']
    if not set(required).issubset(df.columns):
        raise ValueError(f'조회 DataFrame에 {required}가 필요합니다.')
    df = df[required].drop_duplicates().copy()
    if df.empty or df.isna().any().any():
        raise ValueError('조회 조건이 비어 있거나 결측입니다.')
    if not all(isinstance(value, str) for value in df['hs_code']):
        raise ValueError('hs_code를 문자열로 입력하세요.')
    if not df['hs_code'].str.fullmatch(r'\d{2}|\d{4}|\d{6}').all():
        raise ValueError('hs_code는 HS2/4/6 숫자 문자열이어야 합니다.')
    for column in ['year', 'country_code']:
        values = pd.to_numeric(df[column], errors='coerce')
        if values.isna().any() or not (values.gt(0) & values.lt(10000) & values.mod(1).eq(0)).all():
            raise ValueError(f'{column}는 유효한 양의 정수여야 합니다. 세계 합계 reporter=0은 금지합니다.')
        df[column] = values.astype('int64')
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / '.env', override=False)
    subscription_key = os.getenv('COMTRADE_API_KEY', '').strip()
    if not subscription_key:
        raise EnvironmentError('.env에 COMTRADE_API_KEY를 설정하세요.')
    rows = []
    empty_responses = 0
    with requests.Session() as session:
        session.headers.update({'Ocp-Apim-Subscription-Key': subscription_key})
        for query in df.itertuples(index=False):
            row = {'country': pd.NA, 'country_code': str(query.country_code),
                   'hs_code': query.hs_code, 'item_name': pd.NA, 'year': query.year,
                   'market_size': float('nan'), 'korea_export_usd': float('nan')}
            for partner_code, target in [(0, 'market_size'), (410, 'korea_export_usd')]:
                params = {'typeCode': 'C', 'freqCode': 'A', 'clCode': 'HS',
                          'period': str(query.year), 'reporterCode': str(query.country_code),
                          'cmdCode': query.hs_code, 'flowCode': 'M', 'partnerCode': str(partner_code),
                          'partner2Code': '0', 'customsCode': 'C00', 'motCode': '0',
                          'maxRecords': 500, 'includeDesc': 'true', 'breakdownMode': 'classic'}
                response = session.get('https://comtradeapi.un.org/data/v1/get/C/A/HS',
                                       params=params, timeout=(10, 60))
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
                    raise ValueError('Comtrade 응답에 유효한 data 배열이 없습니다.')
                records = payload['data']
                if payload.get('error') or payload.get('errorMessage'):
                    raise ValueError('Comtrade가 오류 응답을 반환했습니다.')
                if not records:
                    empty_responses += 1
                    continue
                if len(records) != 1:
                    raise ValueError('단일 집계 조회에서 여러 행이 반환되었습니다. 임의 합산하지 않습니다.')
                record = records[0]
                for field, expected in [('reporterCode', query.country_code), ('partnerCode', partner_code),
                                        ('refYear', query.year), ('partner2Code', 0), ('motCode', 0)]:
                    if int(record.get(field, -1)) != expected:
                        raise ValueError(f'응답 조회 조건 불일치: {field}')
                if str(record.get('cmdCode')) != query.hs_code or record.get('flowCode') != 'M':
                    raise ValueError('응답 HS/수입 흐름이 조회 조건과 다릅니다.')
                if record.get('customsCode') != 'C00':
                    raise ValueError('응답 통관 집계 조건 불일치')
                if 'primaryValue' not in record:
                    raise ValueError('Comtrade primaryValue가 없습니다.')
                row[target] = record['primaryValue']
                for source, destination in [('reporterDesc', 'country'), ('cmdDesc', 'item_name')]:
                    if record.get(source) is not None:
                        row[destination] = record[source]
            rows.append(row)
    result = pd.DataFrame(rows)
    for column in ['country', 'country_code', 'hs_code', 'item_name']:
        result[column] = result[column].astype('string')
    result['year'] = result['year'].astype('Int64')
    for column in ['market_size', 'korea_export_usd']:
        result[column] = pd.to_numeric(result[column], errors='coerce').astype('float64')
    result.attrs['collection_report'] = {'requests': 2 * len(df), 'empty_responses': empty_responses,
                                         'source': 'UN Comtrade API (actual responses)'}
    return result


if __name__ == '__main__':
    print('A 모듈 준비 완료. fetch_trade_data(query_df)로 실제 수집을 실행하세요.')
