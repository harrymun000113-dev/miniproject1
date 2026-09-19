"""A: .env 인증 및 UN Comtrade 연간 수입 수집. 실제 API 실패 시 가상 대체 금지."""
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

CACHE_DIR = Path(__file__).resolve().parents[1] / 'data' / 'cache'
REQUEST_DELAY_SECONDS = 1.5  # 같은 스레드 안에서 요청 사이 최소 간격 (초당 제한 회피)
MAX_RETRY_ATTEMPTS = 5
# 국가 단위 조회를 동시에 몇 개까지 병렬로 보낼지. 너무 높이면 Comtrade가 429를
# 더 자주 돌려줘서(어차피 재시도 로직이 있어 죽지는 않음) 오히려 손해일 수 있어 4로 둔다.
MAX_WORKERS = 4
COMTRADE_URL = 'https://comtradeapi.un.org/data/v1/get/C/A/HS'
SERPAPI_URL = 'https://serpapi.com/search.json'
COUNTRY_REF_URL = 'https://comtradeapi.un.org/files/v1/app/reference/Reporters.json'
WORLDBANK_LPI_URL = 'https://api.worldbank.org/v2/country/{iso3}/indicator/LP.LPI.OVRL.XQ'

# Comtrade reporterCode → ISO 3166-1 alpha-2 (Google Trends geo 파라미터)를 직접
# 하드코딩하면 국가마다 실수하기 쉬워서, ISO3 기준으로만 관리하고 실제 reporterCode는
# get_country_code_map()(UN 공식 참조파일)으로 매번 변환한다.
COUNTRY_ISO2_BY_ISO3 = {
    'USA': 'US', 'CHN': 'CN', 'DEU': 'DE', 'VNM': 'VN', 'IND': 'IN', 'JPN': 'JP',
    'GBR': 'GB', 'MEX': 'MX', 'KOR': 'KR', 'FRA': 'FR', 'ITA': 'IT', 'CAN': 'CA',
    'ESP': 'ES', 'NLD': 'NL', 'BRA': 'BR', 'RUS': 'RU', 'TUR': 'TR', 'IDN': 'ID',
    'SAU': 'SA', 'POL': 'PL',
}

# HS코드 → 검색 키워드를 팀에서 직접 정한 경우에만 여기 채운다. 없으면
# fetch_google_trend가 Comtrade의 공식 품목명(item_name/cmdDesc)에서 자동으로
# 키워드를 뽑아 쓴다(임의 추측 대신 UN 공식 설명 문구 사용).
HS_KEYWORD_MAP = {
    '330499': 'cosmetics',
}

_country_code_cache = None


def _cache_key(url: str, params: dict) -> Path:
    signature = hashlib.sha256(json.dumps({'url': url, 'params': params}, sort_keys=True).encode('utf-8')).hexdigest()
    return CACHE_DIR / f'{signature}.json'


def _payload_has_data(payload) -> bool:
    """실제 값이 있는 응답만 영구 캐시한다.

    data/results가 빈 배열인 응답을 그대로 캐시하면, 그게 '진짜 0건'인지
    '일시적 오류로 어쩌다 빈 응답이 온 것'인지 구분할 수 없는데도 영원히
    빈 값으로 고정돼버린다. 그래서 빈 응답은 저장하지 않고 다음 조회 때
    다시 확인한다. data/results 키 자체가 없는 응답(예: World Bank)은 그대로 캐시한다.
    """
    if not isinstance(payload, dict):
        return True
    for key in ('data', 'results'):
        if key in payload:
            return bool(payload[key])
    return True


def _request_with_cache_and_retry(session: requests.Session, url: str, params: dict) -> dict:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _cache_key(url, params)
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding='utf-8'))

    delay = REQUEST_DELAY_SECONDS
    for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            response = session.get(url, params=params, timeout=(10, 30))
        except requests.exceptions.RequestException as error:
            # 타임아웃/연결 끊김 등 네트워크 예외는 원래 재시도 없이 바로 죽었었다.
            # HTTP 429/5xx와 똑같이 재시도 대상으로 취급한다.
            if attempt == MAX_RETRY_ATTEMPTS:
                raise RuntimeError(f'{url} 요청이 반복 실패했습니다({error}). '
                                   '네트워크/방화벽/VPN을 확인하세요.') from error
            print(f'[재시도 {attempt}/{MAX_RETRY_ATTEMPTS}] 네트워크 오류({error}). '
                  f'{delay:.1f}초 대기 후 재시도합니다.')
            time.sleep(delay)
            delay *= 2
            continue
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
        if _payload_has_data(payload):
            cache_file.write_text(json.dumps(payload), encoding='utf-8')
        return payload
    raise RuntimeError('재시도 한도를 초과했습니다.')


def _get_api_key() -> str:
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / '.env', override=False)
    subscription_key = os.getenv('COMTRADE_API_KEY', '').strip()
    if not subscription_key:
        raise EnvironmentError('.env에 COMTRADE_API_KEY를 설정하세요.')
    return subscription_key


def get_country_code_map() -> dict:
    """ISO3 국가코드 -> Comtrade reporterCode 전체 매핑.

    UN Comtrade 공식 참조파일을 그대로 사용한다 (하드코딩/임의 매핑 금지).
    한 번 받아오면 data/cache에 저장해 재요청하지 않는다.
    """
    global _country_code_cache
    if _country_code_cache is not None:
        return _country_code_cache
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / 'reporters_reference.json'
    if cache_file.exists():
        payload = json.loads(cache_file.read_text(encoding='utf-8'))
    else:
        response = requests.get(COUNTRY_REF_URL, timeout=30)
        response.raise_for_status()
        payload = response.json()
        cache_file.write_text(json.dumps(payload), encoding='utf-8')
    mapping = {}
    for entry in payload.get('results', []):
        iso3 = entry.get('reporterCodeIsoAlpha3')
        code = entry.get('reporterCode')
        if iso3 and code is not None:
            mapping[iso3.upper()] = int(code)
    _country_code_cache = mapping
    return mapping


def _fetch_all_reporters(hs_code: str, year: int, partner_code: int, subscription_key: str) -> list:
    """reporterCode를 비워서 이 hs_code/year/partner 조합의 전세계 모든 reporter를
    한 번의 호출로 받아온다. 국가마다 따로 부르는 것보다 호출 수를 훨씬 줄여준다."""
    params = {'typeCode': 'C', 'freqCode': 'A', 'clCode': 'HS', 'period': str(year),
              'reporterCode': '', 'cmdCode': hs_code, 'flowCode': 'M',
              'partnerCode': str(partner_code), 'partner2Code': '0', 'customsCode': 'C00',
              'motCode': '0', 'maxRecords': 100000, 'includeDesc': 'true', 'breakdownMode': 'classic'}
    with requests.Session() as session:
        session.headers.update({'Ocp-Apim-Subscription-Key': subscription_key})
        payload = _request_with_cache_and_retry(session, COMTRADE_URL, params)
    if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
        raise ValueError('Comtrade 응답에 유효한 data 배열이 없습니다.')
    if payload.get('error') or payload.get('errorMessage'):
        raise ValueError('Comtrade가 오류 응답을 반환했습니다.')
    records = payload['data']
    count = payload.get('count')
    if len(records) >= 100000 or (count is not None and int(count) > len(records)):
        raise ValueError('응답이 잘렸을 가능성이 있어 전체 수집으로 처리하지 않습니다(maxRecords 확인 필요).')
    for record in records:
        if (int(record.get('partnerCode', -1)) != partner_code or int(record.get('refYear', -1)) != year
                or str(record.get('cmdCode')) != hs_code or record.get('flowCode') != 'M'
                or record.get('customsCode') != 'C00' or int(record.get('partner2Code', -1)) != 0
                or int(record.get('motCode', -1)) != 0):
            raise ValueError('응답 조회 조건 불일치(전체 reporter 조회).')
    return records


def fetch_trade_data(query_df: pd.DataFrame) -> pd.DataFrame:
    """Input: hs_code, year, country_code(Comtrade reporter 코드) DataFrame.

    Output: DATA_SCHEMA.md의 원본 7컬럼 DataFrame.
    (hs_code, year)당 세계발(partner=0), 한국발(partner=410)을 각각 "전체 reporter
    한 번에" 조회한 뒤, 호출자가 요청한 country_code만 추려서 돌려준다. 국가마다
    따로 부르던 예전 방식(국가수×연도×2번)보다 호출 수가 훨씬 적다
    (연도×2번, reporterCode를 비워서 전세계를 한 번에 받으므로).
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

    hs_years = df[['hs_code', 'year']].drop_duplicates()
    tasks = [(hs, int(year), partner) for hs, year in hs_years.itertuples(index=False)
             for partner in (0, 410)]
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        fetched_list = list(executor.map(
            lambda t: _fetch_all_reporters(t[0], t[1], t[2], subscription_key), tasks))
    fetched = dict(zip(tasks, fetched_list))

    rows = []
    empty_responses = 0
    for (hs_code, year), group in df.groupby(['hs_code', 'year']):
        market_by_code = {int(r['reporterCode']): r for r in fetched[(hs_code, int(year), 0)]}
        korea_by_code = {int(r['reporterCode']): r for r in fetched[(hs_code, int(year), 410)]}
        for country_code in group['country_code']:
            row = {'country': pd.NA, 'country_code': str(country_code), 'hs_code': hs_code,
                   'item_name': pd.NA, 'year': year, 'market_size': float('nan'),
                   'korea_export_usd': float('nan')}
            market_record = market_by_code.get(int(country_code))
            if market_record is not None:
                row['market_size'] = market_record['primaryValue']
                if market_record.get('reporterDesc') is not None:
                    row['country'] = market_record['reporterDesc']
                if market_record.get('cmdDesc') is not None:
                    row['item_name'] = market_record['cmdDesc']
            else:
                empty_responses += 1
            korea_record = korea_by_code.get(int(country_code))
            if korea_record is not None:
                row['korea_export_usd'] = korea_record['primaryValue']
            elif pd.notna(row['market_size']):
                # 세계 수입(partner=0) 데이터는 있는데 한국발(partner=410) 레코드가 없다면
                # '데이터 없음'이 아니라 실제로 한국 수출이 0건이라는 뜻이다. NaN으로
                # 남기면 이후 global_korea_share/export_gap이 그룹 전체에서 깨진다.
                row['korea_export_usd'] = 0.0
            else:
                empty_responses += 1
            rows.append(row)

    result = pd.DataFrame(rows)
    for column in ['country', 'country_code', 'hs_code', 'item_name']:
        result[column] = result[column].astype('string')
    result['year'] = result['year'].astype('Int64')
    for column in ['market_size', 'korea_export_usd']:
        result[column] = pd.to_numeric(result[column], errors='coerce').astype('float64')
    result.attrs['collection_report'] = {
        'requests': len(tasks), 'empty_responses': empty_responses,
        'source': 'UN Comtrade API (actual responses, cached, batched by full-reporter query)'}
    return result


def _fetch_all_reporter_partner_pairs(hs_code: str, year: int, subscription_key: str) -> list:
    """reporterCode와 partnerCode를 둘 다 비워서 이 hs_code/year의 모든
    (수입국, 공급국) 조합을 한 번의 호출로 받아온다. top3_concentration은 국가마다
    따로 부를 필요 없이 여기서 로컬로 전부 계산할 수 있다."""
    params = {'typeCode': 'C', 'freqCode': 'A', 'clCode': 'HS', 'period': str(year),
              'reporterCode': '', 'cmdCode': hs_code, 'flowCode': 'M', 'partnerCode': '',
              'partner2Code': '0', 'customsCode': 'C00', 'motCode': '0',
              'maxRecords': 100000, 'includeDesc': 'false', 'breakdownMode': 'classic'}
    with requests.Session() as session:
        session.headers.update({'Ocp-Apim-Subscription-Key': subscription_key})
        payload = _request_with_cache_and_retry(session, COMTRADE_URL, params)
    records = payload.get('data', [])
    count = payload.get('count')
    if len(records) >= 100000 or (count is not None and int(count) > len(records)):
        raise ValueError('top3_concentration 응답이 잘렸을 가능성이 있습니다(maxRecords 확인 필요).')
    return records


def fetch_top3_concentration(query_df: pd.DataFrame) -> pd.DataFrame:
    """Input: hs_code, year, country_code DataFrame.
    Output: country_code, hs_code, year, top3_concentration(0~100).
    해당 국가의 해당 품목 수입 중 상위 3개 공급국이 차지하는 비중.
    (hs_code, year)당 딱 1번만 "전체 reporter×partner" 조합을 받아오고, 각 국가의
    top3 비중은 그 안에서 로컬로 계산한다(국가별로 API를 따로 부르지 않음).
    """
    df = query_df[['hs_code', 'year', 'country_code']].drop_duplicates().copy()
    subscription_key = _get_api_key()
    hs_years = df[['hs_code', 'year']].drop_duplicates()
    tasks = [(hs, int(year)) for hs, year in hs_years.itertuples(index=False)]
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        fetched_list = list(executor.map(
            lambda t: _fetch_all_reporter_partner_pairs(t[0], t[1], subscription_key), tasks))
    fetched = dict(zip(tasks, fetched_list))

    rows = []
    for (hs_code, year), group in df.groupby(['hs_code', 'year']):
        all_pairs = fetched[(hs_code, int(year))]
        by_reporter = {}
        for record in all_pairs:
            if int(record.get('partnerCode', -1)) == 0:
                continue
            by_reporter.setdefault(int(record['reporterCode']), []).append(record)
        for country_code in group['country_code']:
            records = by_reporter.get(int(country_code), [])
            total = sum((r.get('primaryValue') or 0) for r in records)
            top3 = sorted(records, key=lambda r: r.get('primaryValue') or 0, reverse=True)[:3]
            top3_sum = sum((r.get('primaryValue') or 0) for r in top3)
            concentration = (top3_sum / total * 100) if total > 0 else float('nan')
            rows.append({'country_code': str(country_code), 'hs_code': hs_code,
                        'year': year, 'top3_concentration': concentration})
    result = pd.DataFrame(rows)
    result['country_code'] = result['country_code'].astype('string')
    result['hs_code'] = result['hs_code'].astype('string')
    result['year'] = result['year'].astype('Int64')
    result['top3_concentration'] = pd.to_numeric(result['top3_concentration'], errors='coerce').astype('float64')
    return result


def _fetch_one_trend(query, has_item_name, serpapi_key, code_to_iso3) -> dict:
    keyword = HS_KEYWORD_MAP.get(query.hs_code)
    if keyword is None and has_item_name and pd.notna(getattr(query, 'item_name', None)):
        keyword = ' '.join(str(query.item_name).split()[:3])
    iso3 = code_to_iso3.get(int(query.country_code))
    geo = COUNTRY_ISO2_BY_ISO3.get(iso3) if iso3 else None
    if keyword is None or geo is None:
        return {'country_code': str(query.country_code), 'hs_code': query.hs_code,
                'year': query.year, 'google_trend': float('nan'), 'seasonality': float('nan')}
    params = {'engine': 'google_trends', 'q': keyword, 'geo': geo,
              'date': f'{query.year}-01-01 {query.year}-12-31',
              'data_type': 'TIMESERIES', 'api_key': serpapi_key}
    with requests.Session() as session:
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
    return {'country_code': str(query.country_code), 'hs_code': query.hs_code,
            'year': query.year, 'google_trend': trend_score, 'seasonality': seasonality_score}


def fetch_google_trend(query_df: pd.DataFrame) -> pd.DataFrame:
    """Input: hs_code, year, country_code(, item_name 있으면 활용) DataFrame.
    Output: country_code, hs_code, year, google_trend(0~100 연평균), seasonality(0~100 월별 변동계수).

    검색 키워드: HS_KEYWORD_MAP에 팀이 직접 등록한 게 있으면 그걸 쓰고, 없으면
    Comtrade가 응답에서 준 공식 품목명(item_name/cmdDesc)의 앞 3단어를 그대로 쓴다
    (임의로 지어내지 않고 UN 공식 설명 문구만 사용). 국가는 ISO3 → ISO2 매핑이
    있어야 하고, 키워드/국가 매핑이 둘 다 없으면 결측 처리한다. 국가 단위로 병렬 조회한다.
    """
    has_item_name = 'item_name' in query_df.columns
    columns = ['hs_code', 'year', 'country_code'] + (['item_name'] if has_item_name else [])
    df = query_df[columns].drop_duplicates(subset=['hs_code', 'year', 'country_code']).copy()
    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / '.env', override=False)
    serpapi_key = os.getenv('SERPAPI_API_KEY', '').strip()
    if not serpapi_key:
        raise EnvironmentError('.env에 SERPAPI_API_KEY를 설정하세요.')
    country_map = get_country_code_map()
    code_to_iso3 = {code: iso3 for iso3, code in country_map.items()}
    queries = list(df.itertuples(index=False))
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        rows = list(executor.map(
            lambda q: _fetch_one_trend(q, has_item_name, serpapi_key, code_to_iso3), queries))
    result = pd.DataFrame(rows)
    result['country_code'] = result['country_code'].astype('string')
    result['hs_code'] = result['hs_code'].astype('string')
    result['year'] = result['year'].astype('Int64')
    for column in ['google_trend', 'seasonality']:
        result[column] = pd.to_numeric(result[column], errors='coerce').astype('float64')
    return result


def _fetch_one_logistics(query, code_to_iso3) -> dict:
    code = int(query.country_code)
    iso3 = code_to_iso3.get(code)
    days = float('nan')
    if iso3:
        url = WORLDBANK_LPI_URL.format(iso3=iso3)
        params = {'format': 'json', 'date': '2007:2023', 'per_page': 100}
        with requests.Session() as session:
            payload = _request_with_cache_and_retry(session, url, params)
        lpi_value = None
        if isinstance(payload, list) and len(payload) > 1 and payload[1]:
            for entry in payload[1]:
                if entry.get('value') is not None:
                    lpi_value = float(entry['value'])
                    break
        if lpi_value is not None:
            days = round(30 - (lpi_value - 1) / 4 * 25)
    return {'country_code': str(query.country_code), 'hs_code': query.hs_code,
            'year': query.year, 'logistics_days': days}


def fetch_logistics_days(query_df: pd.DataFrame) -> pd.DataFrame:
    """Input: hs_code, year, country_code DataFrame.
    Output: country_code, hs_code, year, logistics_days(정수, 자체 근사치).

    World Bank는 물류 '일수'가 아니라 LPI(Logistics Performance Index, 1~5,
    높을수록 우수)만 제공한다. DATA_SCHEMA.md가 logistics_days를 '자체 근사치'로
    허용하므로, LPI를 근사 소요일로 환산한다(공식 통계 원본 그대로가 아님을 명시):
        days = round(30 - (LPI - 1) / 4 * 25)   → LPI 1(최저)=30일, LPI 5(최고)=5일
    LPI는 국가 단위 지표라 품목(hs_code)과는 무관하게 같은 값이 들어간다.
    해당 국가의 LPI 발표가 없으면 결측으로 둔다(임의 대체 금지). 국가 단위로 병렬 조회한다.
    (같은 국가를 여러 연도로 동시에 조회하면 첫 요청들이 서로의 캐시 생성을 못 보고
    중복 호출할 수 있지만, 결과는 같은 값이라 안전하며 두 번째 검색부터는 캐시로 즉시 처리된다.)
    """
    df = query_df[['hs_code', 'year', 'country_code']].drop_duplicates().copy()
    country_map = get_country_code_map()
    code_to_iso3 = {code: iso3 for iso3, code in country_map.items()}
    queries = list(df.itertuples(index=False))
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        rows = list(executor.map(lambda q: _fetch_one_logistics(q, code_to_iso3), queries))
    result = pd.DataFrame(rows)
    result['country_code'] = result['country_code'].astype('string')
    result['hs_code'] = result['hs_code'].astype('string')
    result['year'] = result['year'].astype('Int64')
    result['logistics_days'] = pd.to_numeric(result['logistics_days'], errors='coerce').astype('float64')
    return result


if __name__ == '__main__':
    print('A 모듈 준비 완료. fetch_trade_data(query_df)로 실제 수집을 실행하세요.')