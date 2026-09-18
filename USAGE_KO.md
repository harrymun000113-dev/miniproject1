# 최종 Python 파일 사용 안내

## 범위와 역할

- `src/collect_data_A.py`: `.env`의 `UN_COMTRADE_API_KEY` 로드, 실제 Comtrade 연간 수입 수집 및 원본 7컬럼 구성.
- `src/preprocess_kpi_B.py`: 원본 보호, 타입/결측/중복 검증, KPI와 Export Gap 계산.
- `run_pipeline.py`: A→B 실행 및 CSV/품질 보고서 저장.
- `verify_pipeline.py`: 명시적으로 가상 데이터를 사용하는 오프라인 검증.

이번 요청은 기존 전처리 코드의 완성 범위입니다. C 점수 엔진, D 인사이트, E Streamlit 대시보드, KOTRA 수집은 구현 범위에 포함하지 않았습니다. B가 C의 점수 공식이나 가중치를 대신 정의하지 않습니다. 생성본은 적용용 파일이며 기존 팀 저장소 파일을 덮어쓰거나 병합하지 않았습니다.

## 실행

Python 3.11.x 환경에서 아래 순서로 실행합니다.

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# .env를 열고 실제 UN_COMTRADE_API_KEY 입력
python verify_pipeline.py
python run_pipeline.py --query query.csv --exchange-rate 1350
```

1350은 실행 형식을 보여주는 **예시 환율**입니다. 실제 사용할 때는 해당 분석 시점에 확인한 환율로 바꾸세요. 환율을 생략하면 `import_value_krw`는 NaN입니다. 환율 API가 연결되었다고 가정하지 않습니다.

`query.csv` 형식 예시(실제 무역 데이터가 아닌 조회 조건):

```csv
hs_code,year,country_code
010121,2020,484
010121,2021,484
010121,2022,484
010121,2023,484
```

실제 분석에는 전체 비교 대상국과 필요한 연도를 작성하세요. country_code는 Comtrade reporter 코드입니다. 세계 합계나 지역 합계를 개별 국가와 섞지 마세요. 한국발 수입은 partner=410, 전체 수입은 partner=0을 각각 조회합니다. HS 코드 앞자리 0을 보존해야 하므로 CSV를 Excel에서 숫자로 바꿔 저장하지 마세요.

전체 비교국 수집 범위를 확인한 경우에만 `--full-country-coverage`를 추가하세요. 이 옵션은 국가 목록을 자동 검증하거나 보충하지 않습니다. 생략하면 세계점유율과 Export Gap은 NaN입니다. 전체 범위 확인 후에도 동일 HS×연도에 금액/키 결측 또는 한국발 수입이 총수입보다 큰 오류가 있으면 세계점유율을 계산하지 않습니다. 미보고 국가가 있으므로 실제 세계시장 전체와 수집 가능한 국가 집합은 다를 수 있습니다. 발표에서 국가 범위·기준 연도·누락 건수를 함께 제시하세요.

각 국가×HS×연도당 API 2회입니다. 현재 계정 호출 한도를 확인한 뒤 조회 범위를 정하세요. HTTP 오류, 키 누락, 응답 형식 오류는 중단하며 가상 데이터로 바꾸지 않습니다. 빈 응답은 0이 아니라 NaN으로 보존합니다.

## 문서 준수와 구현 해석

- 원본 MD 4개는 변경하지 않았습니다. 함수는 DataFrame 입력 → DataFrame 반환이며 입력을 복사합니다. 품질 보고서는 `DataFrame.attrs`에 저장하므로 스키마 컬럼을 추가로 오염시키지 않습니다.
- 문자열 결측도 `Unknown`으로 채우지 않습니다. 공백은 결측 처리합니다. 잘못된 수치, 음수 금액, 무한대는 NaN으로 처리합니다. 연도는 결측 가능한 `Int64`, 문자열은 pandas `string`, 금액/KPI는 `float64`입니다.
- 완전히 같은 정제 행만 제거합니다. 동일 국가×HS×연도의 상충하는 행은 오류입니다. 결측 키를 임의 국가로 합치지 않습니다.
- `growth_1y=(market_size[t]/market_size[t-1]-1)*100`.
- `cagr_3y=((market_size[t]/market_size[t-3])**(1/3)-1)*100`. 실제 3년 간격이므로 양 끝 포함 4개 연도 조회를 권장합니다.
- `korea_export_growth=(korea_export_usd[t]/korea_export_usd[t-1]-1)*100`.
- 분모가 0/결측이면 성장률·점유율은 NaN입니다. 현재 금액 0, 과거 양수이면 성장률 -100%는 유효합니다.
- `global_korea_share=전체 비교국 korea_export_usd 합계/전체 비교국 market_size 합계`. 단순 국가별 비율의 산술평균이 아닌 전체 시장의 금액 기준 점유율입니다.
- DATA_SCHEMA 2번은 global_korea_share에 `%`라고 기재하지만, 7번은 비율을 0~1로 저장하도록 명시합니다. 계산 단위를 일치시키기 위해 점유율과 Export Gap은 7번 규칙을 적용합니다. 성장률은 컬럼 정의의 %를 유지합니다. 문서 자체는 수정하지 않았습니다.
- `export_gap=(global_korea_share-korea_market_share).clip(lower=0)`. 0.071은 7.1%p입니다. 8.1% 가상 기준값이나 고정 환율을 실제 값으로 넣지 않습니다.
- B는 후보 필터링을 하지 않고 전체 전처리 결과를 반환합니다. C에서 세계점유율 산출 후 `<` 조건을 적용해야 합니다.

## 검증 결과와 제한

`verify_pipeline.py` 통과: 모든 Python 파일의 Python 3.11 문법 호환 AST 검사 및 컴파일, 원본 보호, HS 앞자리 0, nullable 연도, 정확한 t-1/t-3 계산, 합계 기반 점유율, Export Gap, 결측, 0 분모, 음수/무한대, 중복 충돌, 빈 DataFrame, 부분 결측, API 응답 매핑, 키 누락 오류.

검증 실행 환경: Python 3.14.7 / pandas 3.0.5 / NumPy 2.5.3. 팀 지정 Python 3.11.x / pandas 2.2.2 / NumPy 1.26.4 실행 환경 검증은 하지 못했습니다. `requirements.txt`는 TEAM_RULES의 8개 버전을 그대로 고정했습니다. 설치 후 `python verify_pipeline.py`로 다시 확인하세요.

실제 API 키를 사용한 네트워크 수집은 수행하지 않았습니다. API 동작 검증은 모의 응답을 사용했습니다. 인증 권한·호출 한도·데이터 제공 여부에 따른 실수집 결과는 별도로 확인해야 합니다.

API 조회 조건 참고: UN Comtrade 공식 개발 도구와 예제
https://github.com/uncomtrade/comtradeapicall
