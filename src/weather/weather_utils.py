def _is_weather_query(text: str) -> bool:
    """天気関連の質問かどうかを判定する。"""
    # ...existing code...

def _extract_weather_location(text: str) -> str:
    """質問文から地名を抽出する。"""
    # ...existing code...

def _weather_code_to_ja(code: int) -> str:
    """天気コードを日本語に変換する。"""
    # ...existing code...

def _fallback_weather_coords(location: str):
    """既知地名の座標フォールバック。"""
    # ...existing code...

def _resolve_weather_location(location: str):
    """地名を緯度経度に解決する。"""
    # ...existing code...

def _fetch_weather_context(query: str) -> str:
    """天気情報を取得する。"""
    # ...existing code...
