import re
import requests
import logging
import pytz
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def _is_weather_query(text: str) -> bool:
    """天気関連の質問かどうかを判定する。"""
    return bool(re.search(r"天気|天候|気温|降水|予報", text))

def _extract_weather_location(text: str) -> str:
    """質問文から地名を抽出する。抽出できない場合は恵庭市を既定値にする。"""
    # 日付や相対日付表現を除去してクリーンにする
    clean_text = re.sub(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?\s*(の)?", "", text)
    clean_text = re.sub(r"\d{4}-\d{2}-\d{2}\s*(の)?", "", clean_text)
    clean_text = re.sub(r"(今日|昨日|明日|一昨日|最近|最新)\s*(の)?", "", clean_text)
    
    candidates = [
        r"今日の(?P<loc>[^\s、。！？?]+?)の天気",
        r"(?P<loc>[^\s、。！？?]+?)の天気予報",
        r"(?P<loc>[^\s、。！？?]+?)の天気",
    ]
    for pat in candidates:
        m = re.search(pat, clean_text)
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

        # JSTの現在日付を取得
        tz = pytz.timezone('Asia/Tokyo')
        today = datetime.now(tz).date()
        target_date = None

        # クエリから日付表現を抽出
        if "一昨日" in query or "おととい" in query:
            target_date = today - timedelta(days=2)
        elif "昨日" in query or "きのう" in query:
            target_date = today - timedelta(days=1)
        elif "明日" in query or "あした" in query:
            target_date = today + timedelta(days=1)
        elif "今日" in query or "きょう" in query:
            target_date = today
        else:
            # クエリから日付を抽出 (YYYY-MM-DD 形式)
            date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", query)
            if date_match:
                try:
                    target_date = datetime.strptime(date_match.group(0), "%Y-%m-%d").date()
                except ValueError:
                    pass
            else:
                # YYYY年MM月DD日 形式
                date_match_ja = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", query)
                if date_match_ja:
                    try:
                        year, month, day = map(int, date_match_ja.groups())
                        target_date = datetime(year, month, day).date()
                    except ValueError:
                        pass

        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "Asia/Tokyo",
        }
        
        if target_date:
            date_str = target_date.strftime("%Y-%m-%d")
            params["start_date"] = date_str
            params["end_date"] = date_str
        else:
            params["forecast_days"] = 2

        forecast_resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params=params,
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

        idx = 0
        p_prob = pop[idx] if idx < len(pop) and pop[idx] is not None else "不明"
        
        date_label = times[idx]
        if target_date:
            date_str = target_date.strftime("%Y-%m-%d")
            if target_date == today - timedelta(days=1):
                date_label = f"昨日（{date_str}）"
            elif target_date == today - timedelta(days=2):
                date_label = f"一昨日（{date_str}）"
            elif target_date == today + timedelta(days=1):
                date_label = f"明日（{date_str}）"
            elif target_date == today:
                date_label = f"今日（{date_str}）"

        summary = (
            "\n\n【最新の天気データ（外部API取得）】\n"
            f"- 地点: {resolved_name} {admin1} {country}\n"
            f"- 日付: {date_label}\n"
            f"- 天気: {_weather_code_to_ja(int(codes[idx]))}\n"
            f"- 最高気温: {tmax[idx]}°C\n"
            f"- 最低気温: {tmin[idx]}°C\n"
            f"- 降水確率（最大）: {p_prob}%\n"
            "- 注意: 数値はOpen-Meteo ofデータです。"
        )
        return summary
    except Exception as e:
        logger.warning(f"天気データ取得エラー: {e}")
        return f"\n\n【天気データ取得結果】\n- 外部APIからの取得に失敗しました: {e}"
