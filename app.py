import requests

BASE_URL = "https://api.db.nomics.world/v22/series"


def fetch_series_by_filter(provider_code, dataset_code, **dimension_filters):
    """
    정확한 series_code를 몰라도, 차원(dimension) 조건으로 필터링해서 시리즈를 찾는다.

    예)
        fetch_series_by_filter("WB", "WDI", country="VNM", indicator="NY.GDP.MKTP.CD")
    """
    url = f"{BASE_URL}/{provider_code}/{dataset_code}"
    params = {"observations": 1, "format": "json"}
    for key, value in dimension_filters.items():
        params[f"dimensions.{key}"] = value

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    raw_data = response.json()

    docs = raw_data.get("series", {}).get("docs", [])
    if not docs:
        raise ValueError(f"조건에 맞는 시리즈를 찾지 못함: {dimension_filters}")

    doc = docs[0]
    return {
        "series_code": doc.get("series_code"),
        "periods": doc["period"],
        "values": doc["value"],
    }


if __name__ == "__main__":
    # 베트남 GDP 조회 (국가코드는 ISO3 대문자: VNM, IDN, MEX)
    vn_gdp = fetch_series_by_filter("WB", "WDI", country="VNM", indicator="NY.GDP.MKTP.CD")

    print(f"찾은 시리즈 코드: {vn_gdp['series_code']}")
    print("베트남 GDP (최근 5개년):")
    for period, value in zip(vn_gdp["periods"][-5:], vn_gdp["values"][-5:]):
        print(f"  {period}: {value:,.0f} USD")

    # 여러 국가 비교
    countries = {"VNM": "베트남", "IDN": "인도네시아", "MEX": "멕시코"}

    print("\n국가별 최신 GDP 비교:")
    for code, name in countries.items():
        try:
            result = fetch_series_by_filter("WB", "WDI", country=code, indicator="NY.GDP.MKTP.CD")
            latest_period = result["periods"][-1]
            latest_value = result["values"][-1]
            print(f"  {name}({code}) [{latest_period}]: {latest_value:,.0f} USD")
        except Exception as e:
            print(f"  {name}({code}) 조회 실패: {e}")