import re
import requests
import logging

logger = logging.getLogger(__name__)

def _is_weather_query(text: str) -> bool:
    """天気関連の質問かどうかを判定する。"""
    return bool(re.search(r"天気|天候|気温|降水|予報", text))

def _extract_weather_location(text: str) -> str:
    """質問文から地名を抽出する。抽出できない場合は恵庭市を既定値にする。"""
    candidates = [
        r"今日の(?P<loc>[^\s、。！？?]+?)の天気",
        r"(?P<loc>[^\s、。！？?]+?)の天気予報",
        r"(?P<loc>[^\s、。！？?]+?)の天気",
    ]
    for pat in candidates:
        m = re.search(pat, text)
        if m:
            loc = m.group("loc").strip(" 　")
            if loc:
                return loc
    return "恵庭市"

def _weather_code_to_ja(code: int) -> str:
    """Open-Meteoのweather codeを日本語へ変換する。"""
    mapping = {
        0: "快晴",
        1: "晴れ",
        2: "晴れ時々くもり",
        3: "くもり",
        45: "霧",
        48: "着氷性の霧",
        51: "弱い霧雨",
        53: "霧雨",
        55: "強い霧雨",
        56: "弱い着氷性霧雨",
        57: "強い着氷性霧雨",
        61: "弱い雨",
        63: "雨",
        65: "強い雨",
        66: "弱い着氷性の雨",
        67: "強い着氷性の雨",
        71: "弱い雪",
        73: "雪",
        75: "強い雪",
        77: "雪粒",
        80: "弱いにわか雨",
        81: "にわか雨",
        82: "激しいにわか雨",
        85: "弱いにわか雪",
        86: "強いにわか雪",
        95: "雷雨",
        96: "弱い雷雨とひょう",
        99: "強い雷雨とひょう",
    }
    return mapping.get(code, f"不明（コード: {code}）")

def _fallback_weather_coords(location: str):
    """既知地名の座標フォールバック。ジオコーディング失敗時に使用する。"""
    known = {
        "恵庭": (42.8826, 141.5759, "恵庭", "北海道", "日本"),
        "恵庭市": (42.8826, 141.5759, "恵庭", "北海道", "日本"),
        "札幌": (43.0618, 141.3545, "札幌", "北海道", "日本"),
        "札幌市": (43.0618, 141.3545, "札幌", "北海道", "日本"),
        "東京": (35.6762, 139.6503, "東京", "東京都", "日本"),
        "東京都": (35.6762, 139.6503, "東京", "東京都", "日本"),
    }
    return known.get(location)

def _resolve_weather_location(location: str):
    """地名を緯度経度へ解決する。失敗時は表記ゆれ・既知地名フォールバックを試す。"""
    candidates = [location]
    normalized = re.sub(r"(都|道|府|県|市|区|町|村)$", "", location)
    if normalized and normalized not in candidates:
        candidates.append(normalized)

    for name in candidates:
        try:
            geocode_resp = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={
                    "name": name,
                    "count": 5,
                    "language": "ja",
                    "format": "json",
                    "countryCode": "JP",
                },
                timeout=10,
            )
            geocode_resp.raise_for_status()
            geocode_data = geocode_resp.json()
            results = geocode_data.get("results") or []
            if results:
                jp_results = [r for r in results if (r.get("country_code") or "").upper() == "JP"]
                target = jp_results[0] if jp_results else results[0]
                return (
                    target.get("latitude"),
                    target.get("longitude"),
                    target.get("name", name),
                    target.get("admin1", ""),
                    target.get("country", ""),
                )
        except Exception as e:
            logger.warning(f"Geocoding API error for {name}: {e}")

    return _fallback_weather_coords(location)

def _fetch_weather_context(query: str) -> str:
    """天気質問に対して最新の天気情報を取得し、プロンプト用コンテキストを返す。"""
    if not _is_weather_query(query):
        return ""

    location = _extract_weather_location(query)
    try:
        resolved = _resolve_weather_location(location)
        if not resolved:
            return (
                "\n\n【天気データ取得結果】\n"
                f"- 指定地名「{location}」の位置情報が見つかりませんでした。"
            )

        lat, lon, resolved_name, admin1, country = resolved

        forecast_resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "Asia/Tokyo",
                "forecast_days": 2,
            },
            timeout=10,
        )
        forecast_resp.raise_for_status()
        forecast_data = forecast_resp.json()
        daily = forecast_data.get("daily", {})
        times = daily.get("time", [])
        codes = daily.get("weathercode", [])
        tmax = daily.get("temperature_2m_max", [])
        tmin = daily.get("temperature_2m_min", [])
        pop = daily.get("precipitation_probability_max", [])
        if not times:
            return "\n\n【天気データ取得結果】\n- 予報データが取得できませんでした。"

        today_idx = 0
        summary = (
            "\n\n【最新の天気データ（外部API取得）】\n"
            f"- 地点: {resolved_name} {admin1} {country}\n"
            f"- 日付: {times[today_idx]}\n"
            f"- 天気: {_weather_code_to_ja(int(codes[today_idx]))}\n"
            f"- 最高気温: {tmax[today_idx]}°C\n"
            f"- 最低気温: {tmin[today_idx]}°C\n"
            f"- 降水確率（最大）: {pop[today_idx]}%\n"
            "- 注意: 数値はOpen-Meteo의 予報値です。"
        )
        return summary
    except Exception as e:
        logger.warning(f"天気データ取得エラー: {e}")
        return f"\n\n【天気データ取得結果】\n- 外部APIからの取得に失敗しました: {e}"
