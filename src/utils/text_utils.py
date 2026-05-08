def _decode_text_bytes(raw: bytes) -> str:
    """バイト列を適切なエンコーディングでデコードする。"""
    # ...existing code...

def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list:
    """テキストをチャンク分割する。"""
    # ...existing code...

def _detect_audio_ext(audio_bytes: bytes) -> str:
    """音声フォーマットを判定する。"""
    # ...existing code...

def _extract_urls(text: str) -> list[str]:
    """テキスト中のURLを抽出する。"""
    # ...existing code...

def _is_safe_url(url: str) -> bool:
    """SSRF対策: URLの安全性を確認する。"""
    # ...existing code...

def _fetch_url_text(url: str, max_chars: int = 4000) -> str:
    """URLにアクセスして本文を取得する。"""
    # ...existing code...
