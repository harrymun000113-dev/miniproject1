"""A: .env 인증 및 UN Comtrade 연간 수입 수집. 실제 API 실패 시 가상 대체 금지."""
import hashlib
import json
import os
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

CACHE_DIR = Path(__file__).resolve().parents[1] / 'data' / 'cache'
REQUEST_DELAY_SECONDS = 1.5  # 요청 사이 최소 간격 (초당 제한 회피)
MAX_RETRY_ATTEMPTS = 5
COMTRADE_URL = 'https://comtradeapi.un.org/data/v1/get/C/A/HS'
SERPAPI_URL = 'https://serpapi.com/search.json'

# Comtrade 리포터 코드 → ISO 3166-1 alpha-2 (Google Trends geo 파라미터). 필요한 국가 추가하세요.
COUNTRY_ISO2 = {
    842: 'US',  # USA
    704: 'VN',  # Vietnam
}

# HS코드 → 검색 키워드. 실제 담당 품목에 맞게 채우세요.
HS_KEYWORD_MAP = {
    '330499': 'cosmetics',
}


def _cache_key(url: str, params: dict) -> Path:
    signature = hashlib.sha256(json.dumps({'url': url, 'params': params}, sort_keys=True).encode('utf-8')).hexdigest()
    return CACHE_DIR / f'{signature}.json'


def _request_with_cache_and_retry(session: requests.Session, url: str, params: dict) -> dict:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _cache_key(url, params)
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding='utf-8'))

    delay = REQUEST_DELAY_SECONDS
    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        time.sleep(REQUEST_DELAY_SECONDS)
        response = session.get(url, params=params, timeout=(10, 60))
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            status = getattr(error.response, 'status_code', None)
            retryable = status == 429 or (isinstance(status, int) and status >= 500)
            if not retryable or attempt == MAX_RETRY_ATTEMPTS:
                raise
            wait = delay
            if error.response is not None:
                wait = float(error.response.headers.get('Retry-After', delay))
            print(f'[재시도 {attempt}/{MAX_RETRY_ATTEMPTS}] {status} 응답. {wait:.1f}초 대기 후 재시도합니다.')
            time.sleep(wait)
            delay *= 2
            continue
        payload = response.json()
        cache_file.write_text(json.dumps(payload), encoding='utf-8')
        return payload
    raise RuntimeError('재시도 한도를 초과했습니다.')


def _get_api_key() -> str:
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / '.env', override=False)
    subscription_key = os.getenv('COMTRADE_API_KEY', '').strip()
    if not subscription_key:
        raise EnvironmentError('.env에 COMTRADE_API_KEY를 설정하세요.')
    return subscription_key


def fetch_trade_data(query_df: pd.DataFrame) -> pd.DataFrame:
    """Input: hs_code, year, country_code(Comtrade reporter 코드) DataFrame.

    Output: DATA_SCHEMA.md의 원본 7컬럼 DataFrame.
    국가×품목×연도당 세계발(0), 한국발(410)을 따로 조회한다.
    국가 목록은 실제 분석 대상국 전체를 호출자가 제공한다.
    성공한 응답은 data/cache에 저장되어 같은 조건 재조회 시 API를 다시 부르지 않는다.
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
    subscription_key = _get_api_key()
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
                payload = _request_with_cache_and_retry(session, COMTRADE_URL, params)
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
                                         'source': 'UN Comtrade API (actual responses, cached)'}
    return result


def fetch_top3_concentration(query_df: pd.DataFrame) -> pd.DataFrame:
    """Input: hs_code, year, country_code DataFrame.
    Output: country_code, hs_code, year, top3_concentration(0~100).
    해당 국가의 해당 품목 수입 중 상위 3개 공급국이 차지하는 비중.
    """
    df = query_df[['hs_code', 'year', 'country_code']].drop_duplicates().copy()
    subscription_key = _get_api_key()
    rows = []
    with requests.Session() as session:
        session.headers.update({'Ocp-Apim-Subscription-Key': subscription_key})
        for query in df.itertuples(index=False):
            params = {'typeCode': 'C', 'freqCode': 'A', 'clCode': 'HS',
                      'period': str(query.year), 'reporterCode': str(query.country_code),
                      'cmdCode': query.hs_code, 'flowCode': 'M', 'partnerCode': '',
                      'partner2Code': '0', 'customsCode': 'C00', 'motCode': '0',
                      'maxRecords': 500, 'includeDesc': 'false', 'breakdownMode': 'classic'}
            payload = _request_with_cache_and_retry(session, COMTRADE_URL, params)
            records = [r for r in payload.get('data', []) if int(r.get('partnerCode', -1)) != 0]
            total = sum((r.get('primaryValue') or 0) for r in records)
            top3 = sorted(records, key=lambda r: r.get('primaryValue') or 0, reverse=True)[:3]
            top3_sum = sum((r.get('primaryValue') or 0) for r in top3)
            concentration = (top3_sum / total * 100) if total > 0 else float('nan')
            rows.append({'country_code': str(query.country_code), 'hs_code': query.hs_code,
                        'year': query.year, 'top3_concentration': concentration})
    result = pd.DataFrame(rows)
    result['country_code'] = result['country_code'].astype('string')
    result['hs_code'] = result['hs_code'].astype('string')
    result['year'] = result['year'].astype('Int64')
    result['top3_concentration'] = pd.to_numeric(result['top3_concentration'], errors='coerce').astype('float64')
    return result


def fetch_google_trend(query_df: pd.DataFrame) -> pd.DataFrame:
    """Input: hs_code, year, country_code DataFrame.
    Output: country_code, hs_code, year, google_trend(0~100 연평균), seasonality(0~100 월별 변동계수).
    HS_KEYWORD_MAP/COUNTRY_ISO2에 매핑이 없으면 둘 다 결측 처리.
    """
    df = query_df[['hs_code', 'year', 'country_code']].drop_duplicates().copy()
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / '.env', override=False)
    serpapi_key = os.getenv('SERPAPI_API_KEY', '').strip()
    if not serpapi_key:
        raise EnvironmentError('.env에 SERPAPI_API_KEY를 설정하세요.')
    rows = []
    with requests.Session() as session:
        for query in df.itertuples(index=False):
            keyword = HS_KEYWORD_MAP.get(query.hs_code)
            geo = COUNTRY_ISO2.get(int(query.country_code))
            if keyword is None or geo is None:
                rows.append({'country_code': str(query.country_code), 'hs_code': query.hs_code,
                            'year': query.year, 'google_trend': float('nan'), 'seasonality': float('nan')})
                continue
            params = {'engine': 'google_trends', 'q': keyword, 'geo': geo,
                      'date': f'{query.year}-01-01 {query.year}-12-31',
                      'data_type': 'TIMESERIES', 'api_key': serpapi_key}
            payload = _request_with_cache_and_retry(session, SERPAPI_URL, params)
            timeline = payload.get('interest_over_time', {}).get('timeline_data', [])
            values = [entry.get('extracted_value') for point in timeline
                     for entry in point.get('values', []) if entry.get('extracted_value') is not None]
            series = pd.Series(values, dtype='float64')
            trend_score = float(series.mean()) if len(series) else float('nan')
            if len(series) >= 6 and series.mean() > 0:
                seasonality_score = min(float(series.std() / series.mean() * 100), 100.0)
            else:
                seasonality_score = float('nan')
            rows.append({'country_code': str(query.country_code), 'hs_code': query.hs_code,
                        'year': query.year, 'google_trend': trend_score, 'seasonality': seasonality_score})
    result = pd.DataFrame(rows)
    result['country_code'] = result['country_code'].astype('string')
    result['hs_code'] = result['hs_code'].astype('string')
    result['year'] = result['year'].astype('Int64')
    for column in ['google_trend', 'seasonality']:
        result[column] = pd.to_numeric(result[column], errors='coerce').astype('float64')
    return result


if __name__ == '__main__':
    print('A 모듈 준비 완료. fetch_trade_data(query_df)로 실제 수집을 실행하세요.')