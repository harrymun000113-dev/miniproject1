import sys
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, render_template, request

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from collect_data_A import (
    fetch_google_trend,
    fetch_logistics_days,
    fetch_top3_concentration,
    fetch_trade_data,
    get_country_code_map,
)
from preprocess_kpi_B import preprocess_kpi_b
from score_engine_C import score_engine_c

app = Flask(__name__)

# score_engine_C는 같은 hs_code/연도 안에서 여러 국가를 상대 비교(최소-최대 정규화)해야
# 점수가 나온다. 검색이 "HS코드만"으로 이루어지므로, 항상 아래 벤치마크 국가 전체를
# 조회해서 채점하고, 점수 순으로 정렬한 랭킹표를 그대로 돌려준다(국가 입력 자체가 없음).
# BLUE_OCEAN_SCORE.md 6-4가 권장하는 "가능한 많은 국가로 정규화"에 맞춰 주요
# 교역국 약 20개국으로 잡았다. 국가 수가 많을수록 첫 검색(캐시 없는 조합)은 오래 걸린다.
DEFAULT_BENCHMARK_COUNTRIES = [
    "USA", "CHN", "DEU", "VNM", "IND", "JPN", "GBR", "MEX", "KOR", "FRA",
    "ITA", "CAN", "ESP", "NLD", "BRA", "RUS", "TUR", "IDN", "SAU", "POL",
]

# growth_1y(전년 대비)와 cagr_3y(3개년 평균 성장률)는 preprocess_kpi_B가 같은 국가의
# t, t-1, t-3년 데이터를 직접 대조해서 계산한다. 검색 연도 1개만 조회하면 t-1/t-3
# 비교 대상 자체가 없어서 두 지표가 항상 NaN이 되고, market_opportunity_score(둘
# 합쳐 55% 가중치, min_count로 하나라도 NaN이면 전체 NaN)도 항상 NaN이 돼버린다.
# 그래서 조회 연도를 target, target-1, target-3 세 개로 넓힌다.
YEAR_OFFSETS = [0, 1, 3]


def _fetch_optional(label, fetch_fn, query_df, output_columns):
    """top3_concentration / google_trend / logistics_days는 DATA_SCHEMA.md 기준으로
    원래도 결측 허용되는 보조지표다. 외부 API(SerpApi, World Bank 등) 하나가
    타임아웃/장애로 죽었다고 해서 이미 정상적으로 확보된 핵심 무역 점수까지 통째로
    502로 날려버리면 안 되므로, 실패 시 해당 지표만 전부 NaN으로 채우고 계속 진행한다.
    """
    try:
        return fetch_fn(query_df)
    except Exception as error:
        print(f"[경고] {label} 수집 실패, 이 지표는 NaN으로 두고 계속 진행합니다: {error}")
        empty = query_df[["country_code", "hs_code", "year"]].drop_duplicates().copy()
        for column in output_columns:
            empty[column] = float("nan")
        return empty


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/search")
def api_search():
    """HS코드만으로 조회 — 벤치마크 국가 전체에 대해 점수를 매겨 랭킹으로 반환."""
    hs_code = request.args.get("hs_code", "").strip()
    target_year = int(request.args.get("year", 2023))

    if not hs_code:
        return jsonify({"error": "HS코드를 입력해주세요."}), 400

    country_map = get_country_code_map()

    resolved = []
    unresolved = []
    for country in DEFAULT_BENCHMARK_COUNTRIES:
        code = country_map.get(country)
        if code is None:
            unresolved.append(country)
        else:
            resolved.append((country, code))

    if not resolved:
        return jsonify({"error": "국가 코드 매핑에 실패했습니다."}), 400

    years = sorted({target_year - offset for offset in YEAR_OFFSETS})
    query = pd.DataFrame({
        "hs_code": [hs_code] * (len(resolved) * len(years)),
        "year": [year for year in years for _ in resolved],
        "country_code": [code for _ in years for _, code in resolved],
    })
    latest_query = query[query["year"] == target_year].drop_duplicates()

    try:
        raw = fetch_trade_data(query)
        kpi = preprocess_kpi_b(raw, exchange_rate=1350, full_country_coverage=True)

        # 구글트렌드 키워드는 Comtrade가 대상 연도에 실제로 돌려준 공식 품목명을 쓴다
        # (임의 추측 금지, HS_KEYWORD_MAP에 팀이 직접 등록한 게 있으면 그게 우선).
        item_name_map = (raw.loc[raw["item_name"].notna(), ["hs_code", "item_name"]]
                              .drop_duplicates(subset="hs_code", keep="first"))
        trend_query = latest_query.merge(item_name_map, on="hs_code", how="left")

        top3 = _fetch_optional("top3_concentration", fetch_top3_concentration,
                               latest_query, ["top3_concentration"])
        trend = _fetch_optional("google_trend/seasonality", fetch_google_trend,
                                trend_query, ["google_trend", "seasonality"])
        logistics = _fetch_optional("logistics_days(World Bank)", fetch_logistics_days,
                                    latest_query, ["logistics_days"])
        merged = (kpi.merge(top3, on=["country_code", "hs_code", "year"], how="left")
                     .merge(trend, on=["country_code", "hs_code", "year"], how="left")
                     .merge(logistics, on=["country_code", "hs_code", "year"], how="left"))
        scored = score_engine_c(merged)

        # 원인 확정용 진단 로그: 실행 중인 터미널(python app.py 콘솔)에 그대로 찍힌다.
        # 스코어/침투율이 이상하면 여기 값을 그대로 복사해서 알려주면 정확히 짚을 수 있다.
        debug_columns = ['country_code', 'year', 'market_size', 'korea_export_usd',
                          'growth_1y', 'cagr_3y', 'korea_market_share', 'global_korea_share',
                          'export_gap', 'top3_concentration', 'google_trend', 'seasonality',
                          'logistics_days', 'market_opportunity_score', 'penetration_opportunity_score']
        print(f"\n=== /api/search hs_code={hs_code} target_year={target_year} 진단 ===")
        print(scored[scored['year'] == target_year][debug_columns].to_string())
        print("collection_report:", raw.attrs.get('collection_report'))
        print("quality_report:", kpi.attrs.get('quality_report'))
        print("score_report notes:", scored.attrs.get('score_report', {}).get('notes'))

        scored = scored[scored["year"] == target_year]
    except Exception as error:
        return jsonify({"error": f"데이터 수집 실패: {error}"}), 502

    def safe(value, digits=None, scale=1):
        if value is None or pd.isna(value):
            return None
        value = float(value) * scale
        return round(value, digits) if digits is not None else value

    code_to_iso3 = {code: iso3 for iso3, code in resolved}
    results = []
    for _, row in scored.iterrows():
        iso3 = code_to_iso3.get(int(row["country_code"]))
        if iso3 is None:
            continue
        market_size = row.get("market_size")
        results.append({
            "id": iso3,
            "hs_code": hs_code,
            "score": safe(row.get("blue_ocean_score"), 1),
            "potential": safe(row.get("market_opportunity_score"), 1),
            # korea_market_share/export_gap은 score_engine_C에서 0~1 비율로 남아있다.
            # (정규화된 0~100 점수는 그룹 내부 계산에만 쓰이고 원본 컬럼엔 안 남는다.)
            # *100 없이 그대로 반올림하면 3.2%가 0.0으로 보인다.
            "penetration": safe(row.get("korea_market_share"), 1, scale=100),
            "export_gap": safe(row.get("export_gap"), 2, scale=100),
            "market_size_usd": safe(market_size / 1_000_000 if pd.notna(market_size) else None, 1),
            "tariff_rate": safe(row.get("tariff_rate")),
            "logistics_days": safe(row.get("logistics_days")),
        })

    # 점수 높은 순으로 정렬해서 랭킹표 형태로 반환.
    results.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    for rank, item in enumerate(results, start=1):
        item["rank"] = rank

    return jsonify({"results": results, "unresolved": unresolved})


if __name__ == "__main__":
    app.run(debug=True, port=5000)