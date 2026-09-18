import sys
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, render_template, request

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from collect_data_A import (
    fetch_google_trend,
    fetch_top3_concentration,
    fetch_trade_data,
    get_country_code_map,
)
from preprocess_kpi_B import preprocess_kpi_b
from score_engine_C import score_engine_c

app = Flask(__name__)

# score_engine_C는 같은 hs_code/연도 안에서 여러 국가를 상대 비교(최소-최대 정규화)해야
# 점수가 나온다. 국가를 1개만 조회하면 min=max가 되어 전부 NaN이 된다.
# 그래서 검색이 국가 1개뿐이면, 비교 기준이 되도록 이 벤치마크 국가들을 몰래 같이
# 조회해서 채점하고, 화면에는 사용자가 검색한 국가만 돌려준다.
# BLUE_OCEAN_SCORE.md 6-4가 권장하는 "가능한 많은 국가로 정규화"에 맞춰 주요
# 교역국 약 50개국으로 잡았다. 국가 수가 많을수록 첫 검색(캐시 없는 조합)은 오래 걸린다.
DEFAULT_BENCHMARK_COUNTRIES = [
    "USA", "CHN", "DEU", "VNM", "IND", "JPN", "GBR", "MEX", "KOR", "FRA",
    "ITA", "CAN", "ESP", "NLD", "BRA", "RUS", "TUR", "IDN", "SAU", "POL",
]


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/search")
def api_search():
    """국가(쉼표로 여러 개 가능) + HS코드로 실시간 조회."""
    countries_param = request.args.get("country", "").upper()
    requested = [c.strip() for c in countries_param.split(",") if c.strip()]
    hs_code = request.args.get("hs_code", "").strip()
    year = int(request.args.get("year", 2023))

    country_map = get_country_code_map()

    # 비교 상대가 부족하면(국가 1개) 벤치마크 국가를 몰래 추가한다.
    country_list = list(requested)
    if len(requested) < 2:
        for benchmark in DEFAULT_BENCHMARK_COUNTRIES:
            if benchmark not in country_list:
                country_list.append(benchmark)

    resolved = []
    unresolved = []
    for country in country_list:
        code = country_map.get(country)
        if code is None:
            if country in requested:
                unresolved.append(country)
        else:
            resolved.append((country, code))

    if not resolved or not hs_code:
        return jsonify({"error": f"지원하지 않는 국가 또는 HS코드입니다: {', '.join(unresolved) or '(국가 없음)'}"}), 400

    query = pd.DataFrame({
        "hs_code": [hs_code] * len(resolved),
        "year": [year] * len(resolved),
        "country_code": [code for _, code in resolved],
    })

    try:
        raw = fetch_trade_data(query)
        kpi = preprocess_kpi_b(raw, exchange_rate=1350, full_country_coverage=True)
        top3 = fetch_top3_concentration(query)
        trend = fetch_google_trend(query)
        merged = (kpi.merge(top3, on=["country_code", "hs_code", "year"], how="left")
                     .merge(trend, on=["country_code", "hs_code", "year"], how="left"))
        scored = score_engine_c(merged)
    except Exception as error:
        return jsonify({"error": f"데이터 수집 실패: {error}"}), 502

    def safe(value, digits=None):
        if value is None or pd.isna(value):
            return None
        return round(float(value), digits) if digits is not None else value

    code_to_iso3 = {code: iso3 for iso3, code in resolved}
    results = []
    for _, row in scored.iterrows():
        iso3 = code_to_iso3.get(int(row["country_code"]))
        if iso3 is None or iso3 not in requested:
            continue  # 벤치마크 국가는 채점에만 쓰고 화면에는 보여주지 않는다.
        market_size = row.get("market_size")
        results.append({
            "id": iso3,
            "hs_code": hs_code,
            "score": safe(row.get("blue_ocean_score"), 1),
            "potential": safe(row.get("market_opportunity_score"), 1),
            "penetration": safe(row.get("korea_market_share"), 1),
            "export_gap": safe(row.get("export_gap"), 2),
            "market_size_usd": safe(market_size / 1_000_000 if pd.notna(market_size) else None, 1),
            "tariff_rate": safe(row.get("tariff_rate")),
            "logistics_days": safe(row.get("logistics_days")),
        })

    return jsonify({"results": results, "unresolved": unresolved})


if __name__ == "__main__":
    app.run(debug=True, port=5000)