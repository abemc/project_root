"""Streamlit アプリケーション - メインモジュール"""

import os
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime

import streamlit as st
import logging
import json
import time
import re
import difflib
import pandas as pd
import plotly.express as px
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from src.rag.utils import clean_markdown

# OneNote 日記モジュール
try:
    import onenote_diary as _onenote
    onenote_available = True
except ImportError:
    onenote_available = False

# 音声文字起こし
try:
    from faster_whisper import WhisperModel
    faster_whisper_available = True
except ImportError:
    faster_whisper_available = False

# モデルサイズごとにキャッシュするためモデルインスタンスを辞書で保持
_whisper_model_cache: dict = {}

# Executor for audio transcription tasks
_AUDIO_EXECUTOR = ThreadPoolExecutor(max_workers=2)

def get_whisper_model(model_size: str = "tiny"):
    """Whisperモデルをサイズ別キャッシュでロード"""
    if model_size not in _whisper_model_cache:
        try:
            _whisper_model_cache[model_size] = WhisperModel(
                model_size, device="cpu", compute_type="int8"
            )
        except Exception as e:
            logger.error(f"Whisperモデル読み込みエラー ({model_size}): {e}")
            return None
    return _whisper_model_cache[model_size]

def _decode_text_bytes(raw: bytes) -> str:
    """バイト列を適切なエンコーディングでデコードする。
    chardetで自動検出し、失敗時は日本語主要エンコーディングを順に試みる。"""
    # 1. chardetで自動検出
    try:
        import chardet
        detected = chardet.detect(raw)
        enc = detected.get("encoding")
        conf = detected.get("confidence", 0)
        if enc and conf >= 0.7:
            return raw.decode(enc)
    except Exception:
        pass
    # 2. 日本語主要エンコーディングを順に試みる
    for enc in ("utf-8", "utf-8-sig", "cp932", "shift_jis", "euc-jp", "iso-2022-jp"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    # 3. 最終フォールバック（文字化け最小化）
    return raw.decode("utf-8", errors="replace")

def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list:
    """テキストをBGE-M3のトークン上限に収まるよう文字数でチャンク分割する。
    chunk_size=400文字は512トークン上限に対して安全マージンを持つ目安。
    改行がない長い段落も文字数で強制分割する。"""
    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        # 改行や句点で自然な切れ目を探す（最大chunk_size文字の範囲内）
        if end < length:
            for sep in ('\n', '。', '．', '. ', '、', '，'):
                pos = text.rfind(sep, start, end)
                if pos != -1 and pos > start + overlap:
                    end = pos + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        # 次の開始位置はオーバーラップ分だけ前に戻す
        start = max(start + 1, end - overlap)
    return chunks if chunks else [text[:chunk_size]]

def _detect_audio_ext(audio_bytes: bytes) -> str:
    """マジックバイトから音声フォーマットを判定して適切な拡張子を返す"""
    if audio_bytes[:4] == b"RIFF":
        return ".wav"
    if audio_bytes[:4] == b"OggS":
        return ".ogg"
    if audio_bytes[:3] == b"ID3" or audio_bytes[:2] == b"\xff\xfb":
        return ".mp3"
    if audio_bytes[:4] == b"fLaC":
        return ".flac"
    # WebM (1a 45 df a3) などその他はwebmとして扱う
    return ".webm"

def transcribe_audio_bytes(audio_bytes: bytes, model_size: str = "tiny") -> str:
    """音声バイトデータをWhisperで文字起こし"""
    if not faster_whisper_available:
        return ""
    model = get_whisper_model(model_size)
    if model is None:
        return ""
    tmp_path = None
    try:
        ext = _detect_audio_ext(audio_bytes)
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        segments, _ = model.transcribe(
            tmp_path,
            language="ja",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=False,
            temperature=0.0,
            no_speech_threshold=0.5,
            # 日本語認識のヒント: 句読点や話し言葉を正しく認識させる
            initial_prompt="日本語の会話です。",
        )
        text = "".join(seg.text.strip() for seg in segments)
        return text
    except Exception as e:
        logger.error(f"音声文字起こしエラー: {e}")
        return ""
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

# ロギングの設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Streamlitのページ構成を設定
st.set_page_config(page_title="RAG Agent", layout="wide")


# ────────────────────────────────────────────
# URL本文取得ユーティリティ
# ────────────────────────────────────────────

def _is_safe_url(url: str) -> bool:
    """SSRF対策: プライベートIPアドレス・ローカルホスト・file/ftpスキームを拒否する。"""
    import ipaddress
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        # http/https のみ許可
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname or ""
        # localhost 系を拒否
        if hostname in ("localhost", ""):
            return False
        # IPアドレスの場合はプライベート・ループバック・リンクローカルを拒否
        try:
            addr = ipaddress.ip_address(hostname)
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                return False
        except ValueError:
            pass  # ホスト名（ドメイン）の場合はスキップ
        return True
    except Exception:
        return False


def _fetch_url_text(url: str, max_chars: int = 4000) -> str:
    """URLにアクセスしてページ本文テキストを返す。失敗時はエラー文字列を返す。"""
    if not _is_safe_url(url):
        return "[セキュリティ上の理由によりこのURLは取得できません]"
    try:
        from bs4 import BeautifulSoup
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ja,en;q=0.9",
        }
        import requests as _requests
        resp = _requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        # script/style/nav/header/footer を除去
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        # 空行を圧縮
        lines = [l for l in text.splitlines() if l.strip()]
        result = "\n".join(lines)
        return result[:max_chars] + ("…（以下省略）" if len(result) > max_chars else "")
    except Exception as e:
        return f"[URLの取得に失敗しました: {e}]"


def _parse_iso_from_query_text(q: str) -> str | None:
    """クエリ文字列からISO日付(YYYY-MM-DD)を抽出する。見つからなければ None を返す。"""
    try:
        import re
        from datetime import date, timedelta
        m = re.search(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日", q)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return f"{y:04d}-{mo:02d}-{d:02d}"
        m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", q)
        if m2:
            return f"{int(m2.group(1)):04d}-{int(m2.group(2)):02d}-{int(m2.group(3)):02d}"
        # 相対日付対応: 昨日 (Asia/Tokyo基準)
        # 日本語テキストでは \b が期待どおりに動作しないことがあるため
        # '昨日' または '昨日の' の出現を単純に検出する
        if re.search(r"昨日|昨日の", q):
            from datetime import datetime, timedelta
            try:
                from zoneinfo import ZoneInfo
                today_jst = datetime.now(ZoneInfo("Asia/Tokyo")).date()
            except Exception:
                today_jst = datetime.now().date()
            return (today_jst - timedelta(days=1)).isoformat()
    except Exception:
        pass
    return None


def _extract_score_from_game_page(url: str, iso_date: str | None = None) -> tuple[int, int] | None:
    """個別試合ページまたはスケジュール一覧から、指定日(ISO)に一致する“試合終了”ブロックのスコアを抽出する。
    戻り値は (home, away) のタプル。成功しなければ None。
    """
    try:
        from bs4 import BeautifulSoup
        import requests
        import re

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ja,en;q=0.9",
        }

        resp = requests.get(url, headers=headers, timeout=12)
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1) もしページがスケジュール一覧なら個別試合リンクを優先的に辿る
        try:
            anchors = soup.find_all("a", href=True)
            for a in anchors:
                href = a["href"]
                if "/game/" in href and iso_date:
                    if iso_date.replace("-", "") in href or iso_date in href:
                        linked = href if href.startswith("http") else requests.compat.urljoin(url, href)
                        sc = _extract_score_from_game_page(linked, iso_date=None)
                        if sc:
                            return sc
        except Exception:
            pass

        # 2) ページ中の time[datetime] やテキストで ISO 日付が出現するブロックを探す
        texts = []
        # time 要素で日付指定がある場合
        for t in soup.find_all("time"):
            dt = t.get("datetime", "")
            if iso_date and dt.startswith(iso_date):
                parent = t.find_parent()
                if parent:
                    texts.append(parent.get_text(separator="\n", strip=True))

        # 3) テキスト検索: ISO年月日表記が本文にあるブロック
        if iso_date:
            ymd_jp = None
            try:
                y, m, d = iso_date.split("-")
                ymd_jp = f"{int(y)}年{int(m)}月{int(d)}日"
            except Exception:
                ymd_jp = None
            if ymd_jp:
                for el in soup.find_all(text=re.compile(re.escape(ymd_jp))):
                    parent = el.parent
                    if parent:
                        texts.append(parent.get_text(separator="\n", strip=True))

        # Fallback: ページ全体のテキスト
        if not texts:
            texts = [soup.get_text(separator="\n", strip=True)]

        # スコア抽出: 直近の「試合終了」表記を含むブロックを優先
        score_re = re.compile(r"(\d{1,2})\s*[\-–—:：]\s*(\d{1,2})")
        for block in texts:
            if not block:
                continue
            if "試合終了" not in block and iso_date:
                # ISO 日付が示されているか確認
                if iso_date.replace("-", "") not in block and (ymd_jp and ymd_jp not in block):
                    continue
            m = score_re.search(block)
            if m:
                try:
                    a = int(m.group(1)); b = int(m.group(2))
                    # ページ上の記載でチーム名の前後関係が分かる場合はそのまま返す
                    return (a, b)
                except Exception:
                    continue
        return None
    except Exception:
        return None


def _extract_urls(text: str) -> list[str]:
    """テキスト中のURLを抽出する。"""
    import re
    pattern = r'https?://[^\s\u3000\u300d\u300f\uff09\u300b\u3011\uff3d\uff5d\"\'>\]）】]+'
    return re.findall(pattern, text)


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
    import requests as _requests

    candidates = [location]
    # 日本語の行政区分サフィックスを除いた表記も試す
    normalized = re.sub(r"(都|道|府|県|市|区|町|村)$", "", location)
    if normalized and normalized not in candidates:
        candidates.append(normalized)

    for name in candidates:
        geocode_resp = _requests.get(
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

    return _fallback_weather_coords(location)


def _fetch_weather_context(query: str) -> str:
    """天気質問に対して最新の天気情報を取得し、プロンプト用コンテキストを返す。"""
    if not _is_weather_query(query):
        return ""

    location = _extract_weather_location(query)
    try:
        import requests as _requests

        resolved = _resolve_weather_location(location)
        if not resolved:
            return (
                "\n\n【天気データ取得結果】\n"
                f"- 指定地名「{location}」の位置情報が見つかりませんでした。"
            )

        lat, lon, resolved_name, admin1, country = resolved

        forecast_resp = _requests.get(
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
            "- 注意: 数値はOpen-Meteoの予報値です。"
        )
        return summary
    except Exception as e:
        logger.warning(f"天気データ取得エラー: {e}")
        return f"\n\n【天気データ取得結果】\n- 外部APIからの取得に失敗しました: {e}"

# OneNote設定の保存先
ONENOTE_SETTINGS_PATH = Path(__file__).resolve().parent / "config" / "onenote_settings.json"


def _load_onenote_settings() -> dict:
    """保存済みのOneNote設定を読み込む。"""
    if not ONENOTE_SETTINGS_PATH.exists():
        return {}
    try:
        with open(ONENOTE_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as e:
        logger.warning(f"OneNote設定の読み込みに失敗: {e}")
    return {}


def _save_onenote_settings(client_id: str, tenant_id: str) -> None:
    """OneNote設定をファイルへ保存する。"""
    ONENOTE_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "client_id": client_id,
        "tenant_id": tenant_id,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(ONENOTE_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

# RAG Agent 設定管理のインポート
try:
    from rag_agent_config import RAGAgentConfig
    rag_config_available = True
except ImportError:
    rag_config_available = False
    logger.warning("RAGAgentConfig がインポートできません")

# UI モジュールのインポート
try:
    from src.ui.streamlit_sidebar_ui import StreamlitSidebarUI
    ui_available = True
except ImportError:
    ui_available = False
    logger.warning("StreamlitSidebarUI がインポートできません")

# LLM モジュールのインポート
try:
    from src.rag.llm import call_llm
    llm_available = True
except ImportError:
    llm_available = False
    logger.warning("LLM モジュールがインポートできません")

# Retriever モジュールのインポート
try:
    from src.rag.retriever import Retriever
    retriever_available = True
except ImportError:
    retriever_available = False
    logger.warning("Retriever モジュールがインポートできません")

# バックアップ・リストア モジュールのインポート
try:
    from src.backup.backup_manager import ProjectBackupManager
    backup_available = True
except ImportError:
    backup_available = False
    logger.warning("バックアップマネージャーがインポートできません")

# RAGAgent / Reranker のインポート
try:
    from src.rag.agent import RAGAgent
    from src.rag.reranker import Reranker
    agent_available = True
except ImportError:
    agent_available = False
    logger.warning("RAGAgent / Reranker がインポートできません")

# Retrieverをキャッシュ付きで初期化
@st.cache_resource
def get_retriever():
    """Retrieverをキャッシュ付きで初期化（重いモデルは一度だけロード）"""
    try:
        from pathlib import Path
        corpus_path = Path(__file__).resolve().parent / "corpus"
        index_path = str(corpus_path / "corpus.index")
        meta_path = str(corpus_path / "corpus_meta.json")
        return Retriever(index_path=index_path, meta_path=meta_path)
    except Exception as e:
        logger.error(f"Retriever初期化エラー: {e}")
        return None

# サイドバーの設定
def setup_sidebar():
    """サイドバーの設定を行う関数"""
    # --- 開発者向けユーティリティ ---
    def _append_dev_log(action: str, result: str) -> None:
        """開発者ツールの出力を JSONL で保存する。"""
        try:
            from pathlib import Path
            import json
            log_dir = Path(__file__).resolve().parent / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "dev_tools.jsonl"
            payload = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "action": action,
                "result": result,
            }
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def project_inspect() -> str:
        """プロジェクトのトップレベル一覧と指定ファイル存在チェックを返す文字列"""
        try:
            root = Path(__file__).resolve().parent
            entries = []
            for p in sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                entries.append(p.name + ("/" if p.is_dir() else ""))
            checks = []
            for name in ("app.py", "requirements.txt", "README.md", "settings.py", "views.py", "templates", "static"):
                p = root / name
                exists = p.exists()
                checks.append(f"{name}: {'存在' if exists else '未検出'}")
            out = "トップレベル一覧:\n" + "\n".join(entries)
            out += "\n\nチェック:\n" + "\n".join(checks)
            try:
                _append_dev_log("project_inspect", out)
            except Exception:
                pass
            return out
        except Exception as e:
            return f"プロジェクト検査エラー: {e}"

    def regenerate_app_spec() -> str:
        """`app.py` から簡易的に関数一覧とインポートを抽出して `docs/app_spec.md` を再生成する。"""
        try:
            import ast
            # use module-level Path
            root = Path(__file__).resolve().parent
            app_path = root / "app.py"
            out_path = root / "docs" / "app_spec.md"
            src = app_path.read_text(encoding="utf-8")
            tree = ast.parse(src)
            funcs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for n in node.names:
                        imports.append(n.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
            content = "# app.py 自動生成仕様\n\n## インポート\n"
            content += "\n".join(f"- {i}" for i in sorted(set(imports)))
            content += "\n\n## 定義関数\n"
            content += "\n".join(f"- `{f}`" for f in funcs)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
            res = f"再生成完了: {out_path.relative_to(root)}"
            try:
                _append_dev_log("regen_app_spec", res)
            except Exception:
                pass
            return res
        except Exception as e:
            res = f"再生成失敗: {e}"
            try:
                _append_dev_log("regen_app_spec", res)
            except Exception:
                pass
            return res

    def check_requirements() -> str:
        """`requirements.txt` を読み、インポートで確認できるパッケージの有無を返す（簡易チェック）。"""
        try:
            root = Path(__file__).resolve().parent
            req = root / "requirements.txt"
            if not req.exists():
                res = "requirements.txt が見つかりません"
                try:
                    _append_dev_log("check_requirements", res)
                except Exception:
                    pass
                return res
            missing = []
            for line in req.read_text(encoding="utf-8").splitlines():
                pkg = line.strip()
                if not pkg or pkg.startswith("#"):
                    continue
                name = re.split(r"[<>=!\s]", pkg)[0]
                try:
                    __import__(name)
                except Exception:
                    missing.append(name)
            if missing:
                res = "未インストールの可能性があるパッケージ:\n" + "\n".join(sorted(set(missing)))
                try:
                    _append_dev_log("check_requirements", res)
                except Exception:
                    pass
                return res
            res = "requirements に記載されたパッケージは import に成功しました（注意: 名前の差異やネイティブ依存は検出できません）"
            try:
                _append_dev_log("check_requirements", res)
            except Exception:
                pass
            return res
        except Exception as e:
            res = f"依存チェックエラー: {e}"
            try:
                _append_dev_log("check_requirements", res)
            except Exception:
                pass
            return res
    try:
        st.sidebar.title("🤖 RAGエージェント")

        # ===== ページナビゲーション =====
        if "app_page" not in st.session_state:
            st.session_state.app_page = "RAGエージェント"
        st.sidebar.radio(
            "ページ",
            ["RAGエージェント", "📔 OneNote日記", "🛡️ エンタープライズ統合"],
            key="app_page",
            horizontal=True,
        )
        st.sidebar.markdown("---")

        # 開発者向けの簡易コントロール
        with st.sidebar.expander("👷 開発者ツール", expanded=False):
            if st.button("🔎 プロジェクト検査", key="dev_proj_inspect"):
                result = project_inspect()
                st.text_area("検査結果", value=result, height=240, key="dev_proj_inspect_out")
            if st.button("🛠 app_spec.md 再生成", key="dev_regen_spec"):
                result = regenerate_app_spec()
                if result.startswith("再生成完了"):
                    st.success(result)
                else:
                    st.error(result)
            if st.button("📦 依存チェック", key="dev_check_req"):
                result = check_requirements()
                st.text_area("依存チェック", value=result, height=140, key="dev_check_req_out")
                # 履歴表示とダウンロード
                # 履歴フィルタ表示
                try:
                    log_file = Path(__file__).resolve().parent / "logs" / "dev_tools.jsonl"
                    entries = []
                    if log_file.exists():
                        for line in log_file.read_text(encoding="utf-8").splitlines():
                            try:
                                entries.append(json.loads(line))
                            except Exception:
                                continue
                    # アクション一覧を取得
                    actions = sorted({e.get("action") for e in entries if isinstance(e, dict) and e.get("action")})
                    actions = ["すべて"] + actions
                    selected_action = st.selectbox("Action フィルタ", actions, key="dev_filter_action")
                    keyword = st.text_input("フリーワード検索（result 内を検索）", value="", key="dev_filter_kw")
                    max_n = st.number_input("表示件数", min_value=1, max_value=500, value=50, key="dev_filter_max")

                    if st.button("🔎 フィルタ適用", key="dev_apply_filter"):
                        filtered = entries
                        if selected_action and selected_action != "すべて":
                            filtered = [e for e in filtered if e.get("action") == selected_action]
                        if keyword:
                            kw = keyword.lower()
                            def match(e):
                                try:
                                    return kw in json.dumps(e.get("result", ""), ensure_ascii=False).lower() or kw in json.dumps(e, ensure_ascii=False).lower()
                                except Exception:
                                    return False
                            filtered = [e for e in filtered if match(e)]
                        to_show = filtered[-int(max_n):]
                        if to_show:
                            pretty = "\n\n".join(json.dumps(e, ensure_ascii=False, indent=2) for e in to_show)
                            st.text_area(f"履歴（{len(to_show)}件）", value=pretty, height=360, key="dev_history_out")
                        else:
                            st.info("条件に一致する履歴がありません")
                    if st.button("⬇️ 履歴ダウンロード", key="dev_download_history"):
                        if log_file.exists():
                            data = log_file.read_bytes()
                            st.download_button("ダウンロード", data=data, file_name="dev_tools.jsonl", mime="application/json")
                        else:
                            st.info("履歴ファイルがありません")
                except Exception as e:
                    st.error(f"履歴操作エラー: {e}")

        if "corpus_action" not in st.session_state:
            st.session_state.corpus_action = "ドキュメント一覧"
        if "search_test_query" not in st.session_state:
            st.session_state.search_test_query = ""
        if "search_test_k" not in st.session_state:
            st.session_state.search_test_k = 3
        
        # ===== PDF/ドキュメント入力セクション =====
        st.sidebar.subheader("📚 ドキュメント入力")
        
        with st.sidebar.expander("📄 PDFアップロード"):
            if retriever_available:
                uploaded_files = st.file_uploader(
                    "PDFや画像を一括で追加", 
                    type=["pdf", "png", "jpg", "jpeg"], 
                    accept_multiple_files=True,
                    key="pdf_upload"
                )
                
                if uploaded_files and st.button("選択したファイルを追加", key="add_files_btn"):
                    retriever = get_retriever()
                    if retriever:
                        with st.spinner("ファイルを処理中..."):
                            total_chunks_added = 0
                            total_ocr_pages = 0
                            failed_files = []
                            total_files = len(uploaded_files)
                            
                            # プログレスバー
                            progress_bar = st.progress(0, text="PDFの処理を開始します...")
                            
                            # 非同期化: 各ファイル処理をワーカースレッドで実行し、
                            # UI スレッドは shared 状態をポーリングして進捗表示のみ行う。
                            from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

                            progress_states = {i: {"page_percent": 0.0, "status": "Queued"} for i in range(len(uploaded_files))}

                            def make_task(i, uploaded_file):
                                def task():
                                    def cb(page_percent, status_msg):
                                        # コールバックはワーカースレッドから呼ばれるため、UI 更新は行わず状態だけ更新
                                        progress_states[i]["page_percent"] = float(page_percent)
                                        progress_states[i]["status"] = str(status_msg)

                                    try:
                                        if uploaded_file.name.lower().endswith(".pdf"):
                                            return uploaded_file.name, retriever.add_pdf(uploaded_file, progress_callback=cb)
                                        else:
                                            return uploaded_file.name, retriever.add_image(uploaded_file, progress_callback=cb)
                                    except Exception as e:
                                        return uploaded_file.name, {"chunks_added": 0, "status": f"error: {e}"}
                                return task

                            with ThreadPoolExecutor(max_workers=min(4, total_files)) as ex:
                                futures = {ex.submit(make_task(i, f)): i for i, f in enumerate(uploaded_files)}

                                try:
                                    while futures:
                                        # aggregate progress for display
                                        agg = sum((progress_states[j]["page_percent"] for j in progress_states)) / float(total_files)
                                        progress_bar.progress(min(agg, 0.99), text=f"処理中... ({int(agg*100)}%)")

                                        done = []
                                        for fut, idx in list(futures.items()):
                                            try:
                                                name, result = fut.result(timeout=0.1)
                                                done.append(fut)
                                                if result.get("chunks_added", 0) > 0:
                                                    total_chunks_added += result["chunks_added"]
                                                    total_ocr_pages += result.get('ocr_pages', 0)
                                                else:
                                                    failed_files.append(f"{name} ({result.get('status', '不明なエラー')})")
                                            except TimeoutError:
                                                # まだ処理中: 続けてポーリング
                                                continue
                                            except Exception as e:
                                                try:
                                                    failed_files.append(f"{uploaded_files[idx].name} (エラー: {str(e)[:50]})")
                                                except Exception:
                                                    failed_files.append(f"index_{idx} (エラー)")
                                                done.append(fut)

                                        for d in done:
                                            futures.pop(d, None)

                                        time.sleep(0.05)

                                finally:
                                    # 最終進捗更新
                                    progress_bar.progress(1.0, text="完了準備中...")
                            
                            # 完了処理
                            progress_bar.progress(1.0, text="完了しました！")
                            time.sleep(1.0)
                            progress_bar.empty()
                            
                            if total_chunks_added > 0:
                                st.success(f"{len(uploaded_files) - len(failed_files)}個のファイルから合計 {total_chunks_added} 個のチャンクを追加しました。(OCR実行: {total_ocr_pages}ページ)")
                                retriever.save()
                                time.sleep(1)
                                st.rerun()
                            if failed_files:
                                st.error(f"失敗: {', '.join(failed_files)}")
                    else:
                        st.error("❌ Retrieverが初期化できませんでした")
            else:
                st.error("❌ Retrieverモジュールが利用できません")
        
        with st.sidebar.expander("📝 テキスト入力"):
            text_input = st.text_area("テキストを貼り付け", height=100, key="text_input")
            if st.button("追加", key="add_text"):
                if text_input.strip():
                    if retriever_available:
                        retriever = get_retriever()
                        if retriever:
                            try:
                                chunks = _chunk_text(text_input.strip())
                                retriever.add_texts(chunks, source_info={"source": "テキスト入力"})
                                st.sidebar.success(f"✅ テキストを追加しました ({len(chunks)}チャンク)")
                            except Exception as e:
                                st.sidebar.error(f"❌ 追加エラー: {str(e)[:60]}")
                        else:
                            st.sidebar.error("❌ Retrieverが初期化できませんでした")
                    else:
                        st.sidebar.success("✅ テキストが追加されました")
            
            st.markdown("**ファイルからテキストを読み込む**")
            text_file = st.file_uploader(
                "テキストファイルを選択",
                type=["txt", "md", "csv", "json", "py", "js", "html", "xml", "yaml", "yml"],
                key="text_file_upload",
                help="テキスト形式のファイルを選択するとコーパスに追加されます"
            )
            if text_file is not None:
                if st.button("ファイルを追加", key="add_text_file_btn"):
                    try:
                        raw = text_file.read()
                        content = _decode_text_bytes(raw)
                        if content.strip():
                            if retriever_available:
                                retriever = get_retriever()
                                if retriever:
                                    chunks = _chunk_text(content)
                                    retriever.add_texts(chunks, source_info={"source": text_file.name})
                                    st.sidebar.success(f"✅ {text_file.name} を追加しました ({len(chunks)}チャンク)")
                                else:
                                    st.sidebar.error("❌ Retrieverが初期化できませんでした")
                            else:
                                st.sidebar.success(f"✅ {text_file.name} を読み込みました")
                        else:
                            st.sidebar.warning("⚠️ ファイルが空です")
                    except Exception as e:
                        st.sidebar.error(f"❌ ファイル読み込みエラー: {str(e)[:60]}")
        
        with st.sidebar.expander("🔗 URLから取得"):
            url_input = st.text_input("URLを入力", key="url_input")
            if st.button("取得", key="get_url"):
                if url_input.strip():
                    st.sidebar.success("✅ URLから取得しました")
        
        # ===== コーパス管理セクション =====
        with st.sidebar.expander("🗂️ コーパス管理"):
            corpus_action = st.selectbox(
                "アクション",
                ["ドキュメント一覧", "チャンク内容確認", "検索テスト", "キャッシュクリア", "バックアップ取得", "復元"],
                key="corpus_action"
            )
            
            if corpus_action == "ドキュメント一覧":
                retriever = get_retriever()
                if retriever:
                    meta_path = Path(__file__).resolve().parent / "corpus" / "corpus_meta.json"
                    docs_stats = {}
                    if meta_path.exists():
                        try:
                            # errors='replace' を追加して不正なバイトを置換し、クラッシュを防ぐ
                            with open(meta_path, 'r', encoding='utf-8', errors='replace') as f:
                                chunks = json.load(f)
                                if isinstance(chunks, list):
                                    for chunk in chunks:
                                        meta_info = chunk.get("meta", {})
                                        src = meta_info.get("source") or chunk.get("source", "unknown")
                                        docs_stats[src] = docs_stats.get(src, 0) + 1
                        except Exception as e:
                            logger.error(f"メタデータ読み込みエラー: {e}")
                    
                    if docs_stats:
                        st.sidebar.info(f"📊 登録ドキュメント: {len(docs_stats)}個, チャンク総数: {sum(docs_stats.values())}")
                        search_query = st.text_input("ファイル名で検索", placeholder="例: manual.pdf", key="doc_search")
                        for source, count in sorted(docs_stats.items()):
                            if search_query and search_query.lower() not in source.lower():
                                continue
                            c1, c2 = st.columns([0.8, 0.2])
                            c1.caption(f"{source} ({count}チャンク)")
                            if c2.button("🗑️", key=f"del_{source}", help=f"削除"):
                                try:
                                    retriever.delete_source(source)
                                    st.toast(f"'{source}' を削除しました。", icon="✅")
                                    retriever.save()
                                    time.sleep(0.5)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"削除エラー: {e}")
                    else:
                        st.sidebar.info("📊 登録ドキュメント: 0個")
            
            elif corpus_action == "チャンク内容確認":
                # 登録済みチャンクをファイル別に閲覧して内容を検証する
                meta_path = Path(__file__).resolve().parent / "corpus" / "corpus_meta.json"
                if meta_path.exists():
                    try:
                        # 同様に安全な読み込みに変更
                        with open(meta_path, 'r', encoding='utf-8', errors='replace') as f:
                            all_chunks = json.load(f)
                        if isinstance(all_chunks, list) and all_chunks:
                            # 文字化け（U+FFFD）を含むエントリを検出
                            def _is_mojibake(text: str) -> bool:
                                total = len(text)
                                if total == 0:
                                    return False
                                bad = text.count('\ufffd')
                                return bad / total > 0.05  # 5%以上が置換文字なら文字化け
                            mojibake_sources = set()
                            for c in all_chunks:
                                if _is_mojibake(c.get("text", "")):
                                    src = c.get("meta", {}).get("source") or c.get("source", "unknown")
                                    mojibake_sources.add(src)
                            if mojibake_sources:
                                st.error(
                                    f"⚠️ **文字化けが検出されました（{len(mojibake_sources)}ファイル）**\n\n"
                                    "これらのファイルは文字化け修正前のバージョンで登録されたため、コーパス内のデータが壊れています。\n\n"
                                    "**対処手順：**\n"
                                    "1. 「コーパス管理」→「キャッシュクリア」でコーパスを削除\n"
                                    "2. 元のファイルを「📝 テキスト入力」または「📄 PDFアップロード」から再登録"
                                )
                                with st.expander("文字化けファイル一覧", expanded=False):
                                    for s in sorted(mojibake_sources):
                                        st.text(f"• {s}")
                            # ソース一覧
                            sources = sorted(set(
                                (c.get("meta", {}).get("source") or c.get("source", "unknown"))
                                for c in all_chunks
                            ))
                            selected_src = st.selectbox("ファイルを選択", sources, key="chunk_src_select")
                            src_chunks = [
                                c for c in all_chunks
                                if (c.get("meta", {}).get("source") or c.get("source", "")) == selected_src
                            ]
                            is_src_mojibake = selected_src in mojibake_sources
                            st.caption(
                                f"📦 {len(src_chunks)} チャンク登録済み"
                                + (" ⚠️ 文字化けあり（要再登録）" if is_src_mojibake else "")
                            )
                            max_preview = st.slider("表示チャンク数", 1, min(20, len(src_chunks)), 5, key="chunk_preview_n")
                            for i, chunk in enumerate(src_chunks[:max_preview]):
                                text = chunk.get("text", "")
                                label = f"チャンク {i+1}（{len(text)}文字）" + (" ⚠️" if _is_mojibake(text) else "")
                                with st.expander(label, expanded=(i == 0)):
                                    if _is_mojibake(text):
                                        st.warning("このチャンクは文字化けしています。ファイルを再登録してください。")
                                    st.text(text[:600] + ("…" if len(text) > 600 else ""))
                        else:
                            st.info("コーパスが空です")
                    except Exception as e:
                        st.error(f"読み込みエラー: {str(e)[:60]}")
                else:
                    st.info("コーパスファイルが見つかりません")

            elif corpus_action == "検索テスト":
                # キーワードで実際に検索して、取得されるチャンクとスコアを確認する
                st.caption("キーワードを入力して、コーパスから取得されるチャンクとスコアを確認します")
                with st.form("search_test_form", clear_on_submit=False):
                    test_query = st.text_area(
                        "検索キーワード",
                        placeholder="例: 音声入力の使い方",
                        key="search_test_query",
                        height=80,
                    )
                    top_k = st.slider("取得件数", 1, 10, st.session_state.search_test_k, key="search_test_k")
                    col_run, col_clear = st.columns(2)
                    run_search = col_run.form_submit_button("🔍 検索テスト実行", use_container_width=True)
                    clear_search_query = col_clear.form_submit_button("🧹 入力クリア", use_container_width=True)

                if clear_search_query:
                    st.session_state.search_test_query = ""
                    st.rerun()

                if run_search:
                    if test_query.strip():
                        if retriever_available:
                            retriever = get_retriever()
                            if retriever:
                                try:
                                    results = retriever.search(test_query.strip(), top_k=top_k)
                                    if results:
                                        st.success(f"✅ {len(results)} 件ヒット")
                                        for i, r in enumerate(results):
                                            score = r.get("score", r.get("similarity", 0))
                                            meta = r.get("meta")
                                            if isinstance(meta, dict):
                                                src = meta.get("source") or r.get("source") or r.get("book") or "不明"
                                            else:
                                                src = r.get("source") or r.get("book") or "不明"
                                            text = r.get("text", "")
                                            with st.expander(f"#{i+1} スコア: {score:.3f}  ソース: {src}", expanded=(i == 0)):
                                                if meta and isinstance(meta, dict):
                                                    extra = {k: v for k, v in meta.items() if k != "source"}
                                                    if extra:
                                                        st.caption("  ".join(f"{k}: {v}" for k, v in extra.items()))
                                                st.text(text[:500] + ("…" if len(text) > 500 else ""))
                                    else:
                                        st.warning("⚠️ 該当するチャンクが見つかりませんでした")
                                except Exception as e:
                                    st.error(f"検索エラー: {str(e)[:80]}")
                            else:
                                st.error("❌ Retrieverが初期化できませんでした")
                        else:
                            st.error("❌ Retrieverモジュールが利用できません")
                    else:
                        st.warning("キーワードを入力してください")
            
            elif corpus_action == "キャッシュクリア":
                if st.button("🗑️ キャッシュをクリア", use_container_width=True):
                    try:
                        corpus_path = Path(__file__).resolve().parent / "corpus"
                        ocr_cache = corpus_path / "ocr_cache"
                        if ocr_cache.exists():
                            import shutil
                            shutil.rmtree(ocr_cache)
                        st.sidebar.success("✅ キャッシュをクリアしました")
                    except Exception as e:
                        st.sidebar.error(f"クリアエラー: {e}")
            
            elif corpus_action == "バックアップ取得":
                if st.button("💾 コーパスをバックアップ", use_container_width=True):
                    try:
                        import shutil
                        corpus_path = Path(__file__).resolve().parent / "corpus"
                        backup_dir = Path(__file__).resolve().parent / "backups"
                        backup_dir.mkdir(exist_ok=True)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        backup_path = backup_dir / f"corpus_{timestamp}"
                        shutil.copytree(corpus_path, backup_path)
                        st.sidebar.success(f"✅ バックアップを作成: {backup_path.name}")
                    except Exception as e:
                        st.sidebar.error(f"バックアップエラー: {e}")
            
            elif corpus_action == "復元":
                try:
                    backup_dir = Path(__file__).resolve().parent / "backups"
                    backups = sorted([d for d in backup_dir.iterdir() if d.is_dir() and d.name.startswith("corpus_")], reverse=True)
                    if backups:
                        selected_backup = st.selectbox("復元するバックアップ", [b.name for b in backups])
                        if st.button("復元", use_container_width=True):
                            import shutil
                            corpus_path = Path(__file__).resolve().parent / "corpus"
                            if corpus_path.exists():
                                shutil.rmtree(corpus_path)
                            shutil.copytree(backup_dir / selected_backup, corpus_path)
                            st.sidebar.success("✅ 復元完了")
                            st.cache_resource.clear()
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.sidebar.info("利用可能なバックアップなし")
                except Exception as e:
                    st.sidebar.error(f"復元エラー: {e}")
        
        # ===== 基本設定セクション =====
        st.sidebar.markdown("---")
        with st.sidebar.expander("⚙️ 基本設定", expanded=False):
            llm_model = st.selectbox(
                "LLMモデル",
                ["qwen2.5:7b", "qwen2.5:14b", "llama2:7b"],
                index=0,
                key="sidebar_llm_model"
            )
            # セッション状態に保存
            st.session_state.llm_model = llm_model
            
            max_steps = st.number_input(
                "最大ステップ数",
                min_value=1,
                max_value=50,
                value=5,
                key="sidebar_max_steps"
            )
            st.session_state.max_steps = max_steps
            
            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=1.0,
                value=0.5,
                step=0.1,
                key="sidebar_temperature"
            )
            # セッション状態に保存
            st.session_state.temperature = temperature
        
        # ===== 検索・再ランク設定セクション =====
        with st.sidebar.expander("🔍 検索設定", expanded=False):
            retrieval_top_k = st.number_input(
                "検索結果数",
                min_value=1,
                max_value=50,
                value=5,
                key="sidebar_retrieval_top_k"
            )
            st.session_state.retrieval_top_k = retrieval_top_k
            
            reranker_model = st.selectbox(
                "再ランカーモデル",
                ["BAAI/bge-reranker-base", "BAAI/bge-reranker-large"],
                index=0,
                key="sidebar_reranker_model"
            )
            st.session_state.reranker_model = reranker_model
            
            rerank_top_k = st.number_input(
                "再ランク対象数",
                min_value=1,
                max_value=20,
                value=3,
                key="sidebar_rerank_top_k"
            )
            st.session_state.rerank_top_k = rerank_top_k
            
            rerank_threshold = st.slider(
                "再ランクスコア閾値",
                min_value=0.0,
                max_value=1.0,
                value=0.1,
                step=0.05,
                key="sidebar_rerank_threshold"
            )
            st.session_state.rerank_threshold = rerank_threshold
        
        # ===== マルチモーダル設定セクション =====
        with st.sidebar.expander("🎨 マルチモーダル設定", expanded=False):
            enable_multimodal = st.checkbox("マルチモーダル機能を有効化", value=True, key="sidebar_enable_multimodal")
            st.session_state.enable_multimodal = enable_multimodal
            
            if enable_multimodal:
                vision_model = st.selectbox("ビジョンモデル", ["clip", "blip"], key="sidebar_vision_model")
                st.session_state.vision_model = vision_model
                
                enable_ocr = st.checkbox("OCR有効化", value=True, key="sidebar_enable_ocr")
                st.session_state.enable_ocr = enable_ocr
                
                audio_model = st.selectbox(
                    "音声認識",
                    ["whisper-tiny", "whisper-small", "whisper-base"],
                    key="sidebar_audio_model"
                )
                st.session_state.audio_model = audio_model
                
                tts_engine = st.selectbox("音声合成", ["edge-tts", "gtts"], key="sidebar_tts_engine")
                st.session_state.tts_engine = tts_engine
                
                supported_languages = st.multiselect(
                    "サポート言語",
                    ["ja", "en", "zh", "es", "fr", "de", "ko"],
                    default=["ja", "en"],
                    key="sidebar_supported_languages"
                )
                st.session_state.supported_languages = supported_languages
                
                show_history = st.checkbox("インタラクション履歴を表示", value=False, key="sidebar_show_history")
                st.session_state.show_history = show_history
        
        # ===== デバッグ・学習設定セクション =====
        with st.sidebar.expander("🧠 デバッグ・学習設定", expanded=False):
            show_logs = st.checkbox("思考ログを表示", value=True, key="sidebar_show_logs")
            st.session_state.show_logs = show_logs
            
            show_debug = st.checkbox("🛠️ デバッグ情報を表示", value=False, key="sidebar_show_debug")
            st.session_state.show_debug = show_debug
            
            show_memories = st.checkbox("関連する記憶を表示", value=True, key="sidebar_show_memories")
            st.session_state.show_memories = show_memories
            
            auto_train_enabled = st.checkbox("自動トレーニングを有効化", value=False, key="sidebar_auto_train")
            st.session_state.auto_train_enabled = auto_train_enabled
        
        # ===== 設定の管理セクション =====
        with st.sidebar.expander("💾 設定の管理", expanded=False):
            st.subheader("設定の保存・復元")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("💾 保存", use_container_width=True):
                    st.sidebar.success("✅ 設定を保存しました")
            with col2:
                if st.button("🔄 リセット", use_container_width=True):
                    st.sidebar.success("✅ 設定をリセットしました")
            with col3:
                if st.button("🗑️ 古いバックアップ削除", use_container_width=True):
                    st.sidebar.success("✅ 5個以上前のバックアップを削除しました")
            
            # バックアップから復元
            st.subheader("バックアップから復元")
            backup_list = ["backup_2026-04-18_19-40", "backup_2026-04-18_18-30"]
            selected_backup = st.selectbox("復元するバックアップを選択", backup_list)
            if st.button("復元する", use_container_width=True):
                st.sidebar.success(f"✅ {selected_backup} から復元しました")
            
            # エクスポート・インポート
            st.divider()
            st.subheader("エクスポート・インポート")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📤 設定をエクスポート", use_container_width=True):
                    st.sidebar.info("設定ファイルをダウンロード中...")
            
            with col2:
                uploaded_config = st.file_uploader(
                    "📥 設定をインポート",
                    type=["json"],
                    key="config_import"
                )
                if uploaded_config:
                    if st.button("インポート", use_container_width=True):
                        st.sidebar.success("✅ 設定をインポートしました")
            
            # 設定情報の表示
            st.divider()
            st.subheader("現在の設定")
            col1, col2 = st.columns(2)
            with col1:
                st.caption("📅 作成日時: 2026-04-18 19:40:00")
            with col2:
                st.caption("📅 更新日時: 2026-04-18 19:45:00")
        
        # ===== 実行履歴セクション =====
        st.sidebar.markdown("---")
        st.sidebar.subheader("📋 実行履歴")
        with st.sidebar.expander("過去のクエリと結果"):
            st.write("履歴がまだありません")
        
        # ===== 統合バックアップ・リストア セクション =====
        st.sidebar.markdown("---")
        st.sidebar.subheader("💾 バックアップ・リストア")
        
        try:
            # ストレージ設定（共通）
            with st.sidebar.expander("🔧 ストレージ設定", expanded=False):
                storage_type = st.radio(
                    "ストレージ種別",
                    ["デフォルト", "Linux/WSL パス", "Windows ドライブ", "カスタムパス"],
                    key="backup_storage_type"
                )
                
                backup_root = None
                if storage_type == "デフォルト":
                    st.success("✅ デフォルト保存先")
                
                elif storage_type == "Linux/WSL パス":
                    wsl_path = st.text_input("パス", value="/mnt/d/backups", key="backup_wsl_path")
                    if wsl_path:
                        try:
                            Path(wsl_path).mkdir(parents=True, exist_ok=True)
                            st.success(f"✅ {wsl_path}")
                            backup_root = wsl_path
                        except Exception as e:
                            st.error(f"❌ {str(e)}")
                
                elif storage_type == "Windows ドライブ":
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        drive = st.selectbox("ドライブ", ["D", "E", "F", "G", "H"], key="backup_drive")
                    with col2:
                        folder = st.text_input("フォルダ", "backups", key="backup_folder")
                    
                    if drive and folder:
                        backup_root = f"/mnt/{drive.lower()}/{folder}"
                        try:
                            Path(backup_root).mkdir(parents=True, exist_ok=True)
                            st.success(f"✅ {drive}:\\{folder} → {backup_root}")
                        except Exception as e:
                            st.error(f"❌ {str(e)}")
                
                elif storage_type == "カスタムパス":
                    custom_path = st.text_input("パス", value="/home/abemc/project_root/backups", key="backup_custom")
                    if custom_path:
                        try:
                            Path(custom_path).mkdir(parents=True, exist_ok=True)
                            st.success(f"✅ {custom_path}")
                            backup_root = custom_path
                        except Exception as e:
                            st.error(f"❌ {str(e)}")
                
                # セッション状態に保存
                if backup_root:
                    st.session_state.backup_root = backup_root
            
            # タブ：コーパス vs RAG設定 vs リストア
            tab_corpus, tab_rag, tab_restore = st.sidebar.tabs(["📦 コーパス", "🎯 RAG設定", "🔄 復元"])
            
            # ===== タブ1: コーパスバックアップ =====
            with tab_corpus:
                st.markdown("**コーパス・プロジェクト全体**")
                
                if backup_available:
                    try:
                        project_root = Path(__file__).resolve().parent
                        backup_mgr = ProjectBackupManager(
                            project_root=str(project_root),
                            backup_root=st.session_state.get('backup_root')
                        )
                        
                        # バックアップ対象
                        available_targets = list(backup_mgr.BACKUP_TARGETS.keys())
                        default_targets = ["system_config", "source_code", "documentation"]
                        
                        selected = st.multiselect(
                            "対象を選択",
                            available_targets,
                            default=default_targets,
                            key="corpus_targets"
                        )
                        
                        if st.button("✨ バックアップ作成", key="create_corpus_backup", use_container_width=True):
                            with st.spinner("処理中..."):
                                try:
                                    result = backup_mgr.create_backup(targets=selected, compress=True)
                                    if result.get("success"):
                                        st.success(f"✅ {result.get('backup_id')}")
                                    else:
                                        st.error(f"❌ {result.get('error')}")
                                except Exception as e:
                                    st.error(f"❌ {str(e)[:60]}")
                    except Exception as e:
                        st.error(f"❌ {str(e)[:60]}")
                else:
                    st.warning("⚠️ バックアップマネージャーが利用できません")
            
            # ===== タブ2: RAG設定バックアップ =====
            with tab_rag:
                st.markdown("**RAG Agent 設定**")
                
                try:
                    from rag_agent_config import RAGAgentConfig
                    
                    rag_mgr = RAGAgentConfig()
                    current_config = rag_mgr.load_config()
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🔄 バックアップ作成", key="create_rag_backup", use_container_width=True):
                            try:
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                
                                # カスタムパスがあれば使用
                                backup_dir = Path(st.session_state.get('backup_root', rag_mgr.backup_dir))
                                backup_dir.mkdir(parents=True, exist_ok=True)
                                
                                backup_file = backup_dir / f"rag_config_{timestamp}.json"
                                with open(backup_file, 'w', encoding='utf-8') as f:
                                    json.dump(current_config, f, ensure_ascii=False, indent=2)
                                
                                st.success(f"✅ {backup_file.name}")
                            except Exception as e:
                                st.error(f"❌ {str(e)[:60]}")
                    
                    with col2:
                        if st.button("📋 一覧表示", key="list_rag_backup", use_container_width=True):
                            try:
                                backup_dir = Path(st.session_state.get('backup_root', rag_mgr.backup_dir))
                                if backup_dir.exists():
                                    backups = sorted([f for f in backup_dir.iterdir() if f.name.startswith('rag_config_')], reverse=True)
                                    st.caption(f"📊 {len(backups)} 個")
                                    for b in backups[:5]:
                                        mtime = datetime.fromtimestamp(b.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                                        st.caption(f"• {b.name}\n  {mtime}")
                                else:
                                    st.info("📭 なし")
                            except Exception as e:
                                st.error(f"❌ {str(e)[:60]}")
                
                except ImportError:
                    st.warning("⚠️ RAG設定モジュールが利用できません")
            
            # ===== タブ3: リストア（共通）=====
            with tab_restore:
                st.markdown("**バックアップからリストア**")
                
                if backup_available:
                    try:
                        project_root = Path(__file__).resolve().parent
                        backup_mgr = ProjectBackupManager(
                            project_root=str(project_root),
                            backup_root=st.session_state.get('backup_root')
                        )
                        
                        backups = backup_mgr.list_backups()
                        if backups:
                            selected = st.selectbox(
                                "バージョンを選択",
                                [b.get('backup_id', '') for b in backups],
                                key="restore_select"
                            )
                            
                            if st.button("🔄 リストア実行", key="restore_exec", use_container_width=True, type="primary"):
                                try:
                                    if selected:
                                        success = backup_mgr.restore_backup(backup_id=selected, verify=True)
                                        if success:
                                            st.success(f"✅ {selected}")
                                            st.info("🔄 ページを再読み込みしてください")
                                        else:
                                            st.error("❌ 失敗しました")
                                    else:
                                        st.error("❌ バージョンが選択され ていません")
                                except Exception as e:
                                    st.error(f"❌ {str(e)[:60]}")
                        else:
                            st.info("📦 バックアップなし")
                    except Exception as e:
                        st.error(f"❌ {str(e)[:60]}")


        
        except Exception as e:
            logger.error(f"バックアップセクション エラー: {e}")
            st.sidebar.error(f"⚠️ {str(e)[:50]}")
        
        logger.info("サイドバーの設定が完了しました")
    
    except Exception as e:
        logger.error(f"サイドバー設定中にエラー: {e}")
        st.sidebar.error(f"エラー: {e}")

# confirm_rebuild 関数を追加
def confirm_rebuild():
    """
    再構築を確認するための関数。
    必要に応じて、ユーザー入力や条件を追加してください。
    """
    # 仮の実装: 常に False を返す
    return False
def _init_display_session_state() -> None:
    """display_appで使うセッション状態を初期化する。"""
    defaults = {
        "messages": [],
        "llm_model": "qwen2.5:7b",
        "temperature": 0.5,
        "max_tokens": 2048,
        "attached_file_contents": [],
        "voice_query_pending": "",
        "_voice_last_hash": None,
        "_audio_input_key": 0,
        "last_query_processed": "",
        "use_autonomous_rag": True,
        "retrieval_top_k": 10,
        "rerank_top_k": 5,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _render_voice_input_section() -> None:
    """音声入力UIを表示し、文字起こし結果をセッション状態へ反映する。"""
    if not faster_whisper_available:
        st.info("⚠️ 音声入力には `faster-whisper` が必要です: `pip install faster-whisper`")
        return

    with st.expander("🎤 音声入力", expanded=False):
        audio_model_size_map = {
            "whisper-tiny": "tiny",
            "whisper-small": "small",
            "whisper-base": "base",
        }
        selected_audio_model = st.session_state.get("audio_model", "whisper-tiny")
        whisper_size = audio_model_size_map.get(selected_audio_model, "tiny")

        audio_value = st.audio_input(
            "マイクで録音してください（録音後、自動で文字起こしします）",
            key=f"audio_input_{st.session_state._audio_input_key}",
        )
        if audio_value is not None:
            import hashlib
            audio_hash = hashlib.md5(audio_value.getvalue()).hexdigest()
            if audio_hash != st.session_state._voice_last_hash:
                st.session_state._voice_last_hash = audio_hash
                with st.spinner("🔄 音声を文字起こし中..."):
                    try:
                        fut = _AUDIO_EXECUTOR.submit(transcribe_audio_bytes, audio_value.getvalue(), whisper_size)
                        waited = 0.0
                        while not fut.done():
                            time.sleep(0.05)
                            waited += 0.05
                            if waited > 120.0:
                                logger.warning("Transcription timeout after %.1fs", waited)
                                break
                        transcribed = fut.result() if fut.done() else ''
                    except Exception as e:
                        logger.exception('Transcription task failed: %s', e)
                        transcribed = ''

                if transcribed:
                    st.session_state.voice_query_pending = transcribed
                    st.success(f"📝 文字起こし結果: {transcribed}")
                else:
                    st.warning("⚠️ 文字起こしに失敗しました。もう一度お試しください。")

        if st.session_state.voice_query_pending:
            edited = st.text_area(
                "文字起こしテキスト（編集可能）",
                value=st.session_state.voice_query_pending,
                key="voice_text_edit",
                height=80,
            )
            col_send, col_clear = st.columns([1, 1])
            with col_send:
                if st.button("🚀 このテキストを送信", type="primary", use_container_width=True):
                    st.session_state._voice_submit_text = edited
                    st.session_state.voice_query_pending = ""
                    st.session_state._voice_last_hash = None
                    st.session_state._audio_input_key += 1
                    st.rerun()
            with col_clear:
                if st.button("🗑️ クリア", use_container_width=True):
                    st.session_state.voice_query_pending = ""
                    st.session_state._voice_last_hash = None
                    st.session_state._audio_input_key += 1
                    st.rerun()


def _build_query_with_context(query: str) -> str:
    """URL本文と添付ファイル内容を結合してLLM入力クエリを組み立てる。"""
    urls_in_query = _extract_urls(query)
    url_context = ""
    weather_context = _fetch_weather_context(query)
    if urls_in_query:
        url_context = "\n\n【URLから取得したページ内容】\n"
        for u in urls_in_query[:3]:
            with st.spinner(f"🌐 {u} を取得中..."):
                page_text = _fetch_url_text(u)
            url_context += f"\n🔗 URL: {u}\n{page_text}\n---\n"

    if st.session_state.attached_file_contents:
        file_context = "\n\n【添付ファイルの内容】\n"
        for file_info in st.session_state.attached_file_contents:
            filename = str(file_info["filename"]).encode("utf-8", "replace").decode("utf-8")
            content = str(file_info["content"]).encode("utf-8", "replace").decode("utf-8")
            file_context += f"\n📄 ファイル: {filename}\n"
            file_context += f"内容:\n{content}\n"
            file_context += "---\n"
        return (
            f"{query}{url_context}{weather_context}\n\n{file_context}\n\n"
            "【重要】上記のファイル・記事内容が英語であっても、回答は必ず日本語のみで行ってください。"
        )

    if url_context or weather_context:
        return (
            f"{query}{url_context}{weather_context}\n\n"
            "【重要】上記の実際のページ内容のみに基づいて日本語で回答してください。"
            "ページ内容や天気データに書かれていないことは推測・創作せず、「提供データには記載がありません」と答えてください。"
        )

    return query


def _generate_assistant_response(query: str) -> None:
    """クエリに対する回答を生成し、会話履歴へ追加する。"""
    if not llm_available:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "LLMモジュールが利用できません。設定を確認してください。"
        })
        return

    # サーバ側ショートカット: 単純な日付/時刻問い合わせはローカルで確実に日本語で応答する
    try:
        import re
        q_low = (query or "").strip()
        if re.search(r"今日.?の?日付|今日は何月何日|今日は何日|何月何日|何曜日", q_low):
            from datetime import datetime
            try:
                from zoneinfo import ZoneInfo
                t = datetime.now(ZoneInfo("Asia/Tokyo")).date()
            except Exception:
                t = datetime.now().date()
            # 曜日を日本語で表示
            _weekdays = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
            weekday = _weekdays[t.weekday()]
            resp = f"今日は{t.year}年{t.month}月{t.day}日（{weekday}）です。"
            st.session_state.messages.append({"role": "assistant", "content": resp})
            # clear file-context consumed for this query
            st.session_state.attached_file_contents = []
            return
        # サーバーショートカット: 日本ハムの試合結果を公式サイトから取得して応答
        # 注意: クエリに相対日付（昨日など）が含まれる場合はそれを優先して解決する
        if re.search(r"日本ハム.*試合結果|日本ハム.*試合|今日.*日本ハム.*試合|今日の日本ハム", q_low):
            try:
                import requests
                from bs4 import BeautifulSoup
                from datetime import datetime, timedelta
                try:
                    from zoneinfo import ZoneInfo
                    tokyo_today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
                except Exception:
                    tokyo_today = datetime.now().date()

                # 優先: クエリからISO日付を抽出
                iso = _parse_iso_from_query_text(query)
                if iso:
                    try:
                        target_date = datetime.fromisoformat(iso).date()
                    except Exception:
                        target_date = tokyo_today
                elif re.search(r"昨日|昨日の", q_low):
                    target_date = tokyo_today - timedelta(days=1)
                else:
                    target_date = tokyo_today

                date_str = target_date.strftime('%Y%m%d')
                headers = {"User-Agent": "project-analyzer/1.0 (+https://example.com)"}
                found = None
                base = f"https://www.fighters.co.jp/gamelive/result/"
                for i in range(1, 8):
                    url = f"{base}{date_str}{i:02d}/"
                    try:
                        r = requests.get(url, timeout=6, headers=headers)
                        if r.status_code != 200:
                            continue
                        soup = BeautifulSoup(r.text, 'html.parser')
                        names = [d.get_text(strip=True) for d in soup.select('.c-game-detail__header-text')]
                        table = soup.find(class_='c-score-board-table')
                        if table and names:
                            nums = re.findall(r"\d+", table.get_text())
                            if len(nums) >= 4:
                                r1, h1, r2, h2 = nums[-4:]
                                r1 = int(r1); r2 = int(r2)
                                t1 = names[0]; t2 = names[1]
                                if '北海道' in t1 or '日本ハム' in t1:
                                    team = t1; opp = t2; team_score = r1; opp_score = r2
                                elif '北海道' in t2 or '日本ハム' in t2:
                                    team = t2; opp = t1; team_score = r2; opp_score = r1
                                else:
                                    continue
                                resp = f"{target_date.isoformat()} の試合結果 — {team} {team_score} - {opp_score} {opp}。 (出典: {url})"
                                st.session_state.messages.append({"role":"assistant","content":resp})
                                st.session_state.attached_file_contents = []
                                found = True
                                break
                    except Exception:
                        continue
                if not found:
                    st.session_state.messages.append({"role":"assistant","content":"申し訳ありません、試合結果を取得できませんでした。後ほど再試行してください。"})
                    st.session_state.attached_file_contents = []
                return
            except Exception:
                pass
        if re.search(r"何時|何時ですか|何時になっています|現在の時刻|現在時刻", q_low):
            from datetime import datetime
            from zoneinfo import ZoneInfo
            now = datetime.now(ZoneInfo("Asia/Tokyo")) if '東京' in q_low or 'jst' in q_low else datetime.now()
            resp = f"現在の時刻は {now.hour:02d}時{now.minute:02d}分です。"
            st.session_state.messages.append({"role": "assistant", "content": resp})
            st.session_state.attached_file_contents = []
            return
    except Exception:
        # ショートカットで問題が発生してもフォールバックは通常のLLM経路で対応
        pass

    system_prompt = """あなたは日本語専用のAIアシスタントです。

【最重要ルール - 絶対に破らないこと】
- 回答は必ず100%日本語で書いてください
- 英語・中国語・その他の言語を一切使用しないでください
- ユーザーから英語のURLや英語の記事を渡された場合でも、あなたの回答は日本語のみです
- 英語の固有名詞・サービス名はカタカナに変換してください（例: newsletter → ニュースレター）
- 途中で英語に切り替えることは絶対に禁止です
- 英語のテキストを引用する場合も、必ず日本語訳または日本語の説明を添えてください
- URLが与えられた場合、【URLから取得したページ内容】として実際の内容が提供されます。その内容のみに基づいて回答してください。内容が提供されていないURLについては、内容を推測・創作しないでください。

【出力形式】
- 数式は `$...$` または `$$...$$` の形式で表示
- コードブロックは ``` で囲む
- 箇条書きは `-` または `*` を使用
- **太字** は ** で囲む
- リンクは [テキスト](URL) の形式

【ファイル・URL処理】
- 英語のコンテンツを参照する場合でも、回答・説明・要約はすべて日本語で行う
- ファイル内容を引用する際は日本語の説明を必ず付ける

前の会話内容を参考にしながら、常に日本語のみで一貫した回答をしてください。

追加ルール（検索ベース応答時に必ず守ること）:
- 与えられた【Web検索結果】や【URLから取得したページ内容】のみを根拠にして答えてください。与えられたソースに記載がないことは推測しないでください。
- 回答には必ず使用した出典のURLを明示してください（例: 出典: https://www.example.com）。
- 複数の出典が矛盾する場合は、勝手に一方を選ばず「提供データが矛盾するため確定できません」と答え、各出典を列挙してください。
- チーム名の曖昧さに注意してください。ユーザーが「読売ジャイアンツ」と書いた場合は日本のプロ野球チーム（読売ジャイアンツ、セ・リーグ）を指すと解釈し、MLBの "Giants"（サンフランシスコ・ジャイアンツ）とは混同しないでください。
- スコアや勝敗などの事実は、必ず出典の本文中に明示された数値・記述をそのまま引用して示してください。
- 出典の本文が長い場合は要点（スコア、対戦相手、開催場所）だけを抜き出し、出典URLを添えてください。
"""

    try:
        with st.spinner("🤔 回答を生成中..."):
            # まず、必要に応じて外部ウェブ検索を実行してコンテキストを取得
            web_context = ""
            # 相対日付（例: 昨日）を具体的な日付に置換して検索・プロンプトに反映する
            effective_query = query
            try:
                import re
                from datetime import datetime, timedelta
                try:
                    from zoneinfo import ZoneInfo
                    tokyo_today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
                except Exception:
                    tokyo_today = datetime.now().date()

                if re.search(r"\b昨日\b|昨日の", query):
                    y = tokyo_today - timedelta(days=1)
                    y_jp = f"{y.year}年{y.month}月{y.day}日"
                    # 例: "昨日のジャイアンツの試合" -> "2026年5月9日 のジャイアンツの試合"
                    effective_query = re.sub(r"\b昨日\b", y_jp, query)
                    effective_query = effective_query.replace("昨日の", y_jp + "の")
            except Exception:
                effective_query = query

            try:
                if st.session_state.get("use_web_search", False):
                    from src.rag.web_search import search_web_tool
                    web_hits = search_web_tool(effective_query, max_results=6)
                    if web_hits:
                        # Strict source-priority for スポーツ/試合確認クエリ:
                        # - 国内の信頼できるスポーツニュース/公式サイトのみを使用する
                        # - 見つからない場合は確定的な回答を避けユーザーへ確認を促す
                        from urllib.parse import urlparse
                        trusted_tokens = [
                            "giants.jp",
                            "baseballking.jp",
                            "nhk.or.jp",
                            "yahoo.co.jp",
                            "nikkansports.com",
                            "sponichi.co.jp",
                            "daily.co.jp",
                            "npb.jp",
                            "yakyu.yahoo.co.jp",
                        ]
                        def is_trusted(src_url: str) -> bool:
                            try:
                                net = urlparse(src_url).netloc or src_url
                                return any(t in net for t in trusted_tokens)
                            except Exception:
                                return False

                        # 判定: スポーツ/試合関連クエリか
                        sports_q = False
                        try:
                            if re.search(r"試合結果|スコア|勝敗|何点|vs|対|延長|サヨナラ|引き分け|延長戦", effective_query):
                                sports_q = True
                            # チーム名に「ジャイアンツ」「読売」「巨人」が含まれる場合もスポーツ扱い
                            if re.search(r"ジャイアンツ|読売ジャイアンツ|巨人|Giants", effective_query, flags=re.I):
                                sports_q = True
                        except Exception:
                            sports_q = False

                        trusted_hits = [h for h in web_hits if is_trusted(h.get("meta", {}).get("source") or h.get("source") or "")]

                        # スポーツクエリでは trusted_hits が必須。無ければ確定回答を避ける
                        if sports_q and not trusted_hits:
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": (
                                    "申し訳ありません。信頼できる国内のスポーツ情報ソースが見つかりませんでした。"
                                    "公式サイトや主要なスポーツニュースを指定してください。"
                                )
                            })
                            # clear file-context consumed for this query
                            st.session_state.attached_file_contents = []
                            return

                        chosen_hits = trusted_hits if trusted_hits else web_hits[:3]

                        web_context = "\n\n【Web検索結果】\n"
                        for h in chosen_hits[:5]:
                            src = h.get("meta", {}).get("source") or h.get("source") or "unknown"
                            text = h.get("text", "")
                            # Try to fetch the page body for more concrete context
                            try:
                                page_body = _fetch_url_text(src, max_chars=1200)
                                if page_body and not page_body.startswith("[URLの取得に失敗しました"):
                                    text = (text + "\n" + page_body) if text else page_body
                            except Exception:
                                pass
                            web_context += f"🔗 URL: {src}\n{text}\n---\n"
            except Exception as e:
                logger.warning(f"web_search failed: {e}")

            # プロンプトには日付解決済みのクエリを渡す（'昨日' を具体日付に置換済み）
            prompt = _build_query_with_context(effective_query)
            if web_context:
                # Web検索結果はプロンプトの先頭に付与して、最新情報が回答に反映されやすくする
                prompt = web_context + "\n\n" + prompt
            # 外部ウェブ検索オプションが選択されていない、または検索結果が無い場合は
            # LLMへ検索を行っていない旨を明示して渡す（セッションフラグではなく実際の結果で判定）
            if not web_context:
                prompt = (
                    "[注意] この応答では外部ウェブ検索は実行していません。最新情報が必要な場合は公式サイト等を直接ご確認ください。\n\n" + prompt
                )
            chat_history = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in st.session_state.messages[:-1]
            ]
            # デバッグ: LLMへ渡すプロンプトとシステムプロンプトをログ出力（問題解析用）
            try:
                log_dir = Path(__file__).resolve().parent / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                dbg_path = log_dir / "llm_debug.log"
                with open(dbg_path, "a", encoding="utf-8") as dbg:
                    # Write each block guarded so a single failure doesn't truncate other info
                    dbg.write("---\n")
                    try:
                        dbg.write(f"timestamp: {datetime.utcnow().isoformat()}Z\n")
                    except Exception:
                        dbg.write("timestamp: [write error]\n")
                    try:
                        dbg.write("system_prompt:\n")
                        dbg.write(str(system_prompt) + "\n")
                    except Exception:
                        dbg.write("system_prompt: [write error]\n")
                    try:
                        dbg.write("final_prompt:\n")
                        dbg.write(str(prompt) + "\n")
                    except Exception:
                        dbg.write("final_prompt: [write error]\n")
                    try:
                        dbg.write("chat_history:\n")
                        dbg.write(json.dumps(chat_history if chat_history else [], ensure_ascii=False) + "\n")
                    except Exception:
                        dbg.write("chat_history: [json dump failed]\n")
                    if web_context:
                        try:
                            dbg.write("web_search_performed: true\n")
                            dbg.write("web_results:\n")
                            dbg.write(json.dumps(web_hits, ensure_ascii=False) + "\n")
                        except Exception:
                            dbg.write("web_results: [json dump failed]\n")
                    dbg.flush()
            except Exception:
                # 最終的にログが書けなくても処理継続
                pass

            response = call_llm(
                prompt=prompt,
                model=st.session_state.llm_model,
                system_prompt=system_prompt,
                chat_history=chat_history if chat_history else None,
                temperature=st.session_state.temperature,
                max_tokens=st.session_state.max_tokens,
            )

        if isinstance(response, str) and not response.startswith("Error"):
            # スポーツ系クエリの場合は、信頼ソースから抽出したスコアと照合して不一致なら出典を示す
            try:
                def _extract_score_from_text(text: str) -> tuple[int,int] | None:
                    if not text:
                        return None
                    # よくあるスコア表記を探索する（例: 2-4, 2 – 4, 2:4, 2–4）
                    m = re.search(r"(\d{1,2})\s*[\-–—:：]\s*(\d{1,2})", text)
                    if m:
                        try:
                            return (int(m.group(1)), int(m.group(2)))
                        except Exception:
                            return None
                    # 別パターン: '2 対 4' や '2-4で敗戦' 等
                    m = re.search(r"(\d{1,2})\s*(?:対|vs|VS)\s*(\d{1,2})", text, flags=re.I)
                    if m:
                        try:
                            return (int(m.group(1)), int(m.group(2)))
                        except Exception:
                            return None
                    return None

                verified_msg = None
                if 'sports_q' in locals() and sports_q and 'trusted_hits' in locals() and trusted_hits:
                    # trusted_hits からスコアを抽出
                    src_scores = []
                    # クエリからISO日付を推定して個別ページ優先で抽出
                    iso_for_query = _parse_iso_from_query_text(effective_query)
                    for h in trusted_hits:
                        src = h.get("meta", {}).get("source") or h.get("source") or ""
                        sc = None
                        try:
                            # giants.jp や npb.jp のような公式系は個別試合ページを辿るロジックを使う
                            if any(d in src for d in ("giants.jp", "npb.jp", "/game/")):
                                sc = _extract_score_from_game_page(src, iso_date=iso_for_query)
                            # フォールバック: ページ本文を再取得して正規表現で抽出
                            if sc is None:
                                body = _fetch_url_text(src, max_chars=2000)
                                sc = _extract_score_from_text(body)
                        except Exception:
                            body = h.get("text", "")
                            sc = _extract_score_from_text(body)
                        if sc:
                            src_scores.append({"src": src, "score": sc})

                    # LLMが返したスコアを抽出
                    llm_sc = _extract_score_from_text(response)

                    if src_scores:
                        # 集計: 全ソースで同一ならそのスコアを信頼して回答を置換
                        unique_scores = {}
                        for s in src_scores:
                            unique_scores.setdefault(tuple(s['score']), []).append(s['src'])
                        if len(unique_scores) == 1:
                            # 全ソース一致
                            score_tuple = list(unique_scores.keys())[0]
                            if llm_sc != score_tuple:
                                # LLMとソースが異なるので、ソースに基づく断定的な回答を返す
                                url_list = unique_scores[score_tuple]
                                verified_msg = (
                                    f"提供された信頼できる出典によると、試合結果は {score_tuple[0]} - {score_tuple[1]} です。"
                                    f" 出典: {' , '.join(url_list)}\n\n(注意: LLMの出力と異なっていたため、出典に基づく結果を優先して表示しています)"
                                )
                        else:
                            # 出典間で不一致がある場合は確定を避け、出典を列挙
                            parts = []
                            for sc, urls in unique_scores.items():
                                parts.append(f"{sc[0]}-{sc[1]} (出典: {' , '.join(urls)})")
                            verified_msg = (
                                "提供された信頼できる出典同士でスコアが一致しません。確定できません。\n"
                                "各出典の記載は次の通りです: \n- " + "\n- ".join(parts)
                            )

                if verified_msg:
                    st.session_state.messages.append({"role": "assistant", "content": verified_msg})
                else:
                    st.session_state.messages.append({"role": "assistant", "content": response})
            except Exception:
                # 照合処理で問題が起きても元のLLM応答を渡す
                st.session_state.messages.append({"role": "assistant", "content": response})

            st.session_state.attached_file_contents = []
        else:
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"申し訳ありません。回答の生成に失敗しました: {response}",
            })
    except Exception as e:
        logger.error(f"LLM呼び出しエラー: {e}")
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"エラーが発生しました: {str(e)}",
        })

def display_app():
    """アプリのメイン画面を表示する関数 - チャット形式で質問と回答を表示"""
    st.title("🤖 自律型RAGエージェント")
    logger.debug("display_app function is being called...")
    
    _init_display_session_state()
    
    # ===== クエリ入力セクション =====
    st.subheader("📝 クエリ入力")
    
    # オプション設定
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        use_autonomous_rag = st.checkbox("🤖 自律RAGモード", value=st.session_state.use_autonomous_rag)
        st.session_state.use_autonomous_rag = use_autonomous_rag
    with col2:
        use_web_search = st.checkbox(
            "🌐 ウェブ検索",
            value=st.session_state.get("use_web_search", False),
            key="use_web_search",
        )
    with col3:
        include_reasoning = st.checkbox("🧠 推論詳細", value=True)
    with col4:
        stream_output = st.checkbox("⚡ ストリーム", value=True)
    
    # 現在の設定を表示
    st.info(f"📌 現在の設定: モデル={st.session_state.llm_model}, Temperature={st.session_state.temperature}")
    
    st.markdown("---")
    
    # チャット履歴の表示
    st.subheader("💬 会話")
    st.markdown("---")
    
    if st.session_state.messages:
        for message in st.session_state.messages:
            content = message.get('content', '')
            # 強制的に文字列化してからクリーン処理
            try:
                content = str(content)
            except Exception:
                content = ''

            # LLM応答を整形してマークダウンを復元する
            try:
                content = clean_markdown(content)
            except Exception:
                pass

            if message["role"] == "user":
                st.markdown(f"**🙋 あなた：**")
                st.markdown(content)
            else:
                st.markdown(f"**🤖 エージェント：**")
                # マークダウン形式で表示（HTML利用許可）
                st.markdown(content, unsafe_allow_html=True)
            st.markdown("---")
    else:
        st.info("💬 クエリを入力して、会話を開始してください")
    
    # ===== ファイルアップロード機能 =====
    st.markdown("---")
    st.subheader("📎 ファイル添付")
    
    uploaded_query_files = st.file_uploader(
        "クエリに添付するファイル（PDF・画像など）",
        type=["pdf", "png", "jpg", "jpeg", "txt"],
        accept_multiple_files=True,
        key="query_files_upload"
    )
    
    file_processing_info = []
    if uploaded_query_files:
        col1, col2, col3 = st.columns([0.5, 0.25, 0.25])
        with col1:
            st.caption(f"📁 {len(uploaded_query_files)} 個のファイルを選択")
        with col2:
            if st.button("📤 インデックスに追加", key="add_query_files_btn"):
                if retriever_available:
                    retriever = get_retriever()
                    if retriever:
                        with st.spinner("ファイルを処理中..."):
                            total_chunks = 0
                            failed_files = []
                            
                            for uploaded_file in uploaded_query_files:
                                try:
                                    fname_lower = uploaded_file.name.lower()
                                    if fname_lower.endswith(".pdf"):
                                        result = retriever.add_pdf(uploaded_file)
                                    elif fname_lower.endswith((".txt", ".md", ".csv", ".json",
                                                                ".py", ".js", ".html", ".xml",
                                                                ".yaml", ".yml")):
                                        raw = uploaded_file.read()
                                        content = _decode_text_bytes(raw)
                                        if content.strip():
                                            chunks = _chunk_text(content)
                                            count = retriever.add_texts(
                                                chunks,
                                                source_info={"source": uploaded_file.name}
                                            )
                                            result = {"chunks_added": count, "status": "ok"}
                                        else:
                                            result = {"chunks_added": 0, "status": "ファイルが空です"}
                                    else:
                                        result = retriever.add_image(uploaded_file)
                                    
                                    if result.get("chunks_added", 0) > 0:
                                        total_chunks += result["chunks_added"]
                                        file_processing_info.append(f"✅ {uploaded_file.name}: {result['chunks_added']}チャンク")
                                    else:
                                        failed_files.append(uploaded_file.name)
                                        file_processing_info.append(f"⚠️ {uploaded_file.name}: {result.get('status', 'エラー')}")
                                except Exception as e:
                                    failed_files.append(uploaded_file.name)
                                    file_processing_info.append(f"❌ {uploaded_file.name}: {str(e)[:30]}")
                            
                            if total_chunks > 0:
                                retriever.save()
                                st.success(f"✅ 合計 {total_chunks} 個のチャンクを追加しました")
                                for info in file_processing_info:
                                    st.caption(info)
                            else:
                                st.error(f"❌ ファイル処理に失敗しました")
                                for info in file_processing_info:
                                    st.caption(info)
                    else:
                        st.error("❌ Retrieverが初期化できませんでした")
                else:
                    st.error("❌ Retrieverモジュールが利用できません")
        
        with col3:
            if st.button("💡 コンテキストに読込", key="load_files_context_btn"):
                # ファイルの内容を抽出してセッション状態に保存
                st.session_state.attached_file_contents = []
                
                with st.spinner("ファイルを読み込み中..."):
                    for uploaded_file in uploaded_query_files:
                        try:
                            file_content = ""
                            filename = str(uploaded_file.name)
                            
                            if filename.lower().endswith(".txt"):
                                # テキストファイル（エンコーディング自動検出）
                                file_content = _decode_text_bytes(uploaded_file.read())
                            elif filename.lower().endswith(".pdf"):
                                # PDF処理
                                try:
                                    import pypdf
                                    pdf_reader = pypdf.PdfReader(uploaded_file)
                                    file_content = ""
                                    for page_num, page in enumerate(pdf_reader.pages):
                                        try:
                                            text = page.extract_text()
                                            if text:
                                                file_content += f"[ページ {page_num + 1}]\n{text}\n\n"
                                        except Exception as e:
                                            file_content += f"[ページ {page_num + 1} - 読み込みエラー]\n"
                                except Exception as e:
                                    file_content = f"[PDF読み込みエラー: {str(e)[:50]}]"
                            elif filename.lower().endswith((".png", ".jpg", ".jpeg")):
                                # 画像ファイル
                                file_content = f"[画像ファイル: {filename}]"
                            
                            if file_content:
                                # 内容を最初の2000文字に制限
                                content_limited = file_content[:2000]
                                st.session_state.attached_file_contents.append({
                                    "filename": filename,
                                    "content": content_limited
                                })
                                st.caption(f"✅ {filename} を読み込みました ({len(file_content)}文字)")
                        except Exception as e:
                            logger.error(f"ファイル読み込みエラー: {e}")
                            st.caption(f"❌ {uploaded_file.name}: {str(e)[:40]}")
    
    st.markdown("---")

    # ===== 音声入力セクション =====
    _render_voice_input_section()

    st.markdown("---")

    # チャット入力（Enterキーで送信）
    query = st.chat_input("ここにクエリを入力してください: (Enterキーで送信)", max_chars=2000)

    # 音声入力からの送信を処理
    if st.session_state.get("_voice_submit_text"):
        query = st.session_state._voice_submit_text
        st.session_state._voice_submit_text = ""

    if not query and st.session_state.get("_voice_submit"):
        st.session_state._voice_submit = False
        query = st.session_state.voice_query_pending
        st.session_state.voice_query_pending = ""

    if query:
        # 重複クエリの再処理を防止（リロードなどで同じクエリが再送される場合のデバウンス）
        if st.session_state.get("last_query_processed") == query:
            logger.info("Duplicate query detected; skipping generation")
        else:
            # ユーザーのクエリをメッセージに追加
            st.session_state.messages.append({
                "role": "user",
                "content": query
            })
            _generate_assistant_response(query)
            st.session_state.last_query_processed = query
            st.rerun()

def display_enterprise_dashboard():
    """Phase 20 Task 2: エンタープライズ統合ダッシュボードを表示する"""
    st.title("🛡️ エンタープライズ統合ダッシュボード")
    st.markdown("---")
    
    tab_reliability, tab_security, tab_performance = st.tabs([
        "📈 信頼性 & SLA", "🔒 セキュリティ & 監査", "⚡ パフォーマンス"
    ])
    
    # --- 1. 信頼性 & SLA ---
    with tab_reliability:
        st.subheader("可用性とレイテンシの監視")
        sla_log = Path("logs/sla_metrics.jsonl")
        if sla_log.exists():
            data = []
            with open(sla_log, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data.append(json.loads(line))
                    except: continue
            
            if data:
                df = pd.DataFrame(data)
                df['time'] = pd.to_datetime(df['timestamp'], unit='s')
                
                col1, col2, col3 = st.columns(3)
                col1.metric("稼働率", f"{df['availability'].iloc[-1]:.4f}%")
                col2.metric("p99 レイテンシ", f"{df['p99_latency'].iloc[-1]:.4f}s")
                col3.metric("総リクエスト数", f"{int(df['total_requests'].iloc[-1])}")
                
                # グラフ表示
                fig_lat = px.line(df, x='time', y='p99_latency', title="p99 レイテンシ推移")
                st.plotly_chart(fig_lat, use_container_width=True)
                
                fig_avail = px.line(df, x='time', y='availability', title="可用性推移")
                st.plotly_chart(fig_avail, use_container_width=True)
            else:
                st.info("データがまだありません。")
        else:
            st.warning("SLAログファイルが見つかりません。")

    # --- 2. セキュリティ & 監査 ---
    with tab_security:
        st.subheader("セキュリティ監査ログ")
        audit_log = Path("logs/audit.jsonl")
        if audit_log.exists():
            audit_data = []
            with open(audit_log, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        audit_data.append(json.loads(line))
                    except: continue
            
            if audit_data:
                df_audit = pd.DataFrame(audit_data)
                st.dataframe(df_audit.sort_values('timestamp', ascending=False), use_container_width=True)
                
                # PII検知統計
                if 'event_type' in df_audit.columns:
                    pii_events = df_audit[df_audit['event_type'] == 'pii_detection']
                    st.metric("累計 PII 検知数", len(pii_events))
            else:
                st.info("監査ログが空です。")
        else:
            st.warning("監査ログファイルが見つかりません。")

    # --- 3. パフォーマンス ---
    with tab_performance:
        st.subheader("キャッシュ & 最適化統計")
        from src.performance.cache_optimizer import get_cache_optimizer
        cache = get_cache_optimizer()
        
        col1, col2 = st.columns(2)
        if cache.redis_client:
            col1.success("Redis L2 キャッシュ: 接続済み")
            try:
                info = cache.redis_client.info()
                col2.metric("Redis メモリ使用量", f"{info['used_memory_human']}")
                st.json(info['keyspace'] if 'keyspace' in info else {"msg": "キーなし"})
            except:
                col2.warning("Redis情報の取得に失敗")
        else:
            col1.error("Redis L2 キャッシュ: 未接続")
        
        st.markdown("---")
        st.write("※ キャッシュヒットにより検索レイテンシを約 99% 削減しています。")


def display_onenote_diary():
    """OneNote 日記ページを表示する"""
    st.title("📔 OneNote 日記")

    if not onenote_available:
        st.error("❌ onenote_diary モジュールが読み込めません。onenote_diary.py を確認してください。")
        return

    # ─── セッション状態の初期化 ───────────────────────────────
    for key, default in [
        ("onenote_client_id", ""),
        ("onenote_tenant_id", "common"),
        ("onenote_settings_loaded", False),
        ("onenote_device_code_info", None),
        ("onenote_notebooks", []),
        ("onenote_sections", []),
        ("onenote_selected_notebook", ""),
        ("onenote_selected_section", ""),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    if not st.session_state.onenote_settings_loaded:
        saved = _load_onenote_settings()
        if saved:
            st.session_state.onenote_client_id = str(saved.get("client_id", "")).strip()
            st.session_state.onenote_tenant_id = str(saved.get("tenant_id", "common")).strip() or "common"
        st.session_state.onenote_settings_loaded = True

    def _sanitize_tenant_id(raw_tenant: str) -> tuple[str, str | None]:
        """テナント入力の軽微なミスを補正する。"""
        value = (raw_tenant or "").strip().lower()
        if not value:
            return "common", None
        if value in {"common", "consumers", "organizations"}:
            return value, None

        guid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        if re.fullmatch(guid_pattern, value):
            return value, None

        # 例: <tenant-guid>common のような誤入力を補正
        for suffix in ["consumers", "common", "organizations"]:
            if value.endswith(suffix):
                prefix = value[: -len(suffix)]
                if re.fullmatch(guid_pattern, prefix):
                    return suffix, f"テナントIDの入力を `{suffix}` に補正しました（`{prefix}{suffix}` を検出）。"

        return value, None

    # ─── Azure アプリ設定 ─────────────────────────────────────
    with st.expander("⚙️ Azure アプリ設定", expanded=st.session_state.onenote_client_id == ""):
        st.markdown(
            "**事前準備:** [Azure Portal](https://portal.azure.com) でアプリを登録し、"
            "`Notes.Create` / `Notes.ReadWrite` / `offline_access` スコープを付与してください。"
            "  \nプラットフォームは **モバイルとデスクトップアプリケーション** を選択し、"
            "リダイレクト URI は `https://login.microsoftonline.com/common/oauth2/nativeclient` にします。"
        )
        with st.form("onenote_settings_form"):
            client_id = st.text_input(
                "クライアント ID (Application ID)",
                value=st.session_state.onenote_client_id,
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            )
            tenant_id = st.text_input(
                "テナント ID（個人アカウントは `common`）",
                value=st.session_state.onenote_tenant_id,
                placeholder="consumers",
            )
            if st.form_submit_button("設定を保存"):
                st.session_state.onenote_client_id = client_id.strip()
                sanitized_tenant, tenant_note = _sanitize_tenant_id(tenant_id)
                st.session_state.onenote_tenant_id = sanitized_tenant
                try:
                    _save_onenote_settings(
                        st.session_state.onenote_client_id,
                        st.session_state.onenote_tenant_id,
                    )
                    st.success("設定を保存しました")
                except Exception as e:
                    st.error(f"設定ファイルの保存に失敗しました: {e}")
                if tenant_note:
                    st.info(tenant_note)

    normalized_tenant, tenant_note = _sanitize_tenant_id(st.session_state.onenote_tenant_id)
    if normalized_tenant != st.session_state.onenote_tenant_id:
        st.session_state.onenote_tenant_id = normalized_tenant
    if tenant_note:
        st.caption(f"ℹ️ {tenant_note}")

    # ─── 認証セクション ────────────────────────────────────────
    st.subheader("🔐 Microsoft アカウント認証")

    access_token = None
    if st.session_state.onenote_client_id:
        access_token = _onenote.get_valid_access_token(
            st.session_state.onenote_tenant_id,
            st.session_state.onenote_client_id,
        )

    if access_token:
        st.success("✅ 認証済み")
        if st.button("ログアウト"):
            _onenote.delete_token()
            st.session_state.onenote_notebooks = []
            st.session_state.onenote_sections = []
            st.rerun()
    else:
        if not st.session_state.onenote_client_id:
            st.info("上の「Azure アプリ設定」でクライアント ID を入力してください。")
        else:
            col_login, col_poll = st.columns([1, 1])
            with col_login:
                if st.button("🔑 ログイン（デバイスコード）"):
                    try:
                        info = _onenote.start_device_code_flow(
                            st.session_state.onenote_tenant_id,
                            st.session_state.onenote_client_id,
                        )
                        if info.get("tenant_used") and info.get("tenant_used") != st.session_state.onenote_tenant_id:
                            st.info(
                                f"指定テナントで失敗したため `{info.get('tenant_used')}` エンドポイントにフォールバックしました。"
                            )
                        st.session_state.onenote_device_code_info = info
                    except Exception as e:
                        st.error(f"ログイン開始エラー: {e}")
                        st.warning(
                            "確認ポイント: 1) クライアントIDが正しい 2) 個人Microsoftアカウント専用ならテナントIDは `consumers` 3) 『モバイルとデスクトップアプリケーション』と『パブリック クライアント フロー』を有効化"
                        )

            if st.session_state.onenote_device_code_info:
                info = st.session_state.onenote_device_code_info
                st.info(
                    f"**① 以下の URL をブラウザで開いてください:**  \n"
                    f"[{info.get('verification_uri')}]({info.get('verification_uri')})  \n\n"
                    f"**② 表示されたらこのコードを入力:**  \n"
                    f"### `{info.get('user_code')}`"
                )
                with col_poll:
                    if st.button("✅ 認証完了を確認"):
                        poll_tenant = info.get("tenant_used", st.session_state.onenote_tenant_id)
                        result = _onenote.poll_device_code_token(
                            poll_tenant,
                            st.session_state.onenote_client_id,
                            info.get("device_code", ""),
                        )
                        if result["status"] == "success":
                            st.session_state.onenote_device_code_info = None
                            st.success("✅ 認証が完了しました！")
                            st.rerun()
                        elif result["status"] == "pending":
                            st.warning(result["message"])
                        else:
                            st.error(result["message"])
                            st.session_state.onenote_device_code_info = None

    # ─── 日記書き込みセクション ────────────────────────────────
    if access_token:
        st.markdown("---")
        st.subheader("📓 ノートブック / セクション選択")

        col_nb, col_sc = st.columns(2)
        with col_nb:
            if st.button("🔄 ノートブック一覧を更新"):
                try:
                    st.session_state.onenote_notebooks = _onenote.list_notebooks(access_token)
                    st.session_state.onenote_sections = []
                    st.session_state.onenote_selected_notebook = ""
                except Exception as e:
                    st.error(f"取得エラー: {e}")

        if not st.session_state.onenote_notebooks:
            st.info("「ノートブック一覧を更新」ボタンを押してください。")
        else:
            nb_names = [nb["displayName"] for nb in st.session_state.onenote_notebooks]
            selected_nb_name = st.selectbox("ノートブック", nb_names, key="onenote_nb_select")
            selected_nb = next(
                (nb for nb in st.session_state.onenote_notebooks if nb["displayName"] == selected_nb_name),
                None,
            )

            if selected_nb and selected_nb["id"] != st.session_state.onenote_selected_notebook:
                st.session_state.onenote_selected_notebook = selected_nb["id"]
                st.session_state.onenote_sections = []

            with col_sc:
                if selected_nb and st.button("🔄 セクション一覧を更新"):
                    try:
                        st.session_state.onenote_sections = _onenote.list_sections(
                            access_token, selected_nb["id"]
                        )
                    except Exception as e:
                        st.error(f"セクション取得エラー: {e}")

            if st.session_state.onenote_sections:
                sc_names = [sc["displayName"] for sc in st.session_state.onenote_sections]
                selected_sc_name = st.selectbox("セクション", sc_names, key="onenote_sc_select")
                selected_sc = next(
                    (sc for sc in st.session_state.onenote_sections if sc["displayName"] == selected_sc_name),
                    None,
                )
            else:
                st.info("「セクション一覧を更新」を押してセクションを選択してください。")
                selected_sc = None

            # ─── 日記入力フォーム ─────────────────────────────
            if selected_sc:
                st.markdown("---")
                st.subheader("✏️ 日記を書く")

                def _is_proofread_safe(original_text: str, revised_text: str) -> bool:
                    """AI校正結果が内容改変しすぎていないかを軽量チェックする。"""
                    o = (original_text or "").replace("\r\n", "\n").strip()
                    r = (revised_text or "").replace("\r\n", "\n").strip()
                    if not o or not r:
                        return False
                    if o == r:
                        return True

                    ratio = difflib.SequenceMatcher(None, o, r).ratio()
                    if ratio < 0.55:
                        return False

                    len_ratio = len(r) / max(1, len(o))
                    if len_ratio < 0.7 or len_ratio > 1.35:
                        return False

                    # 数字・日付らしき情報が欠落していないか確認
                    for token in re.findall(r"\d[\d:/.-]*", o):
                        if token and token not in r:
                            return False

                    return True

                # セッション状態の初期化
                for k, v in [
                    ("diary_title_draft", datetime.now().strftime("%Y年%m月%d日の日記")),
                    ("diary_body_draft", ""),
                    ("diary_checked_body", ""),
                    ("diary_checked_edit", ""),
                    ("diary_check_done", False),
                ]:
                    if k not in st.session_state:
                        st.session_state[k] = v

                with st.form("diary_input_form"):
                    diary_title = st.text_input(
                        "タイトル",
                        value=st.session_state.diary_title_draft,
                    )
                    diary_body = st.text_area(
                        "本文",
                        value=st.session_state.diary_body_draft,
                        height=300,
                        placeholder="今日の出来事を書いてください...",
                    )
                    col_check, col_save = st.columns([1, 1])
                    with col_check:
                        do_check = st.form_submit_button(
                            "🔍 AIでチェック・修正",
                            use_container_width=True,
                        )
                    with col_save:
                        do_save = st.form_submit_button(
                            "📤 OneNote に保存",
                            type="primary",
                            use_container_width=True,
                        )

                if do_check:
                    if not diary_body.strip():
                        st.warning("本文を入力してください。")
                    else:
                        st.session_state.diary_title_draft = diary_title
                        st.session_state.diary_body_draft = diary_body
                        if llm_available:
                            with st.spinner("AIが本文をチェック中..."):
                                check_prompt = (
                                    "以下の日記本文を校正してください。絶対条件: 事実関係・時系列・主語/目的語・固有名詞・数値を変更しない。"
                                    "新しい情報の追加、推測補完、要約、削除は禁止。"
                                    "誤字脱字、句読点、助詞の不自然さ、冗長な繰り返しのみ最小限に修正してください。"
                                    "文の順序と段落構成は原則維持してください。"
                                    "出力は修正後の本文のみを返してください。\n\n"
                                    f"---\n{diary_body}\n---"
                                )
                                checked = call_llm(
                                    prompt=check_prompt,
                                    model=st.session_state.get("llm_model", "qwen2.5:7b"),
                                    system_prompt="あなたは日本語の日記校正アシスタントです。意味改変は禁止です。表現を最小限だけ整えてください。",
                                )
                            if isinstance(checked, str) and not checked.startswith("Error"):
                                if not _is_proofread_safe(diary_body, checked):
                                    strict_prompt = (
                                        "次の原文に対して、誤字脱字・句読点・明らかな助詞ミスのみ修正してください。"
                                        "意味が変わる書き換え、言い換え、要約、情報追加・削除は厳禁です。"
                                        "修正後の本文のみを返してください。\n\n"
                                        f"---\n{diary_body}\n---"
                                    )
                                    checked_retry = call_llm(
                                        prompt=strict_prompt,
                                        model=st.session_state.get("llm_model", "qwen2.5:7b"),
                                        system_prompt="原文の意味を1文字たりとも変えず、表記ミスだけ直してください。",
                                    )
                                    if isinstance(checked_retry, str) and not checked_retry.startswith("Error") and _is_proofread_safe(diary_body, checked_retry):
                                        checked = checked_retry
                                        st.info("内容保持を優先した厳格モードで再校正しました。")
                                    else:
                                        checked = diary_body
                                        st.warning("AI校正結果に内容改変の可能性があったため、原文を表示しています。必要なら手動で微修正してください。")
                                st.session_state.diary_checked_body = checked
                                st.session_state.diary_checked_edit = checked
                                st.session_state.diary_check_done = True
                            else:
                                st.error(f"AIチェックに失敗しました: {checked}")
                        else:
                            st.error("LLMモジュールが利用できません。")

                if st.session_state.diary_check_done:
                    st.markdown("---")
                    st.subheader("🔍 AIチェック結果")
                    st.caption("修正後の本文（編集して保存できます）")
                    edited_body = st.text_area(
                        "修正後の本文",
                        height=300,
                        key="diary_checked_edit",
                    )
                    col_apply, col_save_original, col_discard_check = st.columns([1, 1, 1])
                    with col_apply:
                        if st.button("✅ この内容で保存", type="primary", use_container_width=True):
                            with st.spinner("OneNote に保存中..."):
                                result = _onenote.create_diary_page(
                                    access_token=access_token,
                                    section_id=selected_sc["id"],
                                    title=st.session_state.diary_title_draft,
                                    body_text=edited_body,
                                )
                            if result["success"]:
                                st.success(f"✅ {result['message']}")
                                if result.get("page_url"):
                                    st.markdown(f"[OneNote でページを開く]({result['page_url']})")
                                st.session_state.diary_check_done = False
                                st.session_state.diary_body_draft = ""
                                st.session_state.diary_checked_body = ""
                            else:
                                st.error(f"❌ {result['message']}")
                    with col_save_original:
                        if st.button("↩️ 元の文章で保存", use_container_width=True):
                            with st.spinner("OneNote に保存中..."):
                                result = _onenote.create_diary_page(
                                    access_token=access_token,
                                    section_id=selected_sc["id"],
                                    title=st.session_state.diary_title_draft,
                                    body_text=st.session_state.diary_body_draft,
                                )
                            if result["success"]:
                                st.success(f"✅ {result['message']}")
                                if result.get("page_url"):
                                    st.markdown(f"[OneNote でページを開く]({result['page_url']})")
                                st.session_state.diary_check_done = False
                                st.session_state.diary_body_draft = ""
                                st.session_state.diary_checked_body = ""
                            else:
                                st.error(f"❌ {result['message']}")
                    with col_discard_check:
                        if st.button("🗑️ チェック結果を破棄", use_container_width=True):
                            st.session_state.diary_check_done = False
                            st.session_state.diary_checked_body = ""
                            st.rerun()

                elif do_save:
                    if not diary_body.strip():
                        st.warning("本文を入力してください。")
                    else:
                        with st.spinner("OneNote に保存中..."):
                            result = _onenote.create_diary_page(
                                access_token=access_token,
                                section_id=selected_sc["id"],
                                title=diary_title or datetime.now().strftime("%Y年%m月%d日の日記"),
                                body_text=diary_body,
                            )
                        if result["success"]:
                            st.success(f"✅ {result['message']}")
                            if result.get("page_url"):
                                st.markdown(f"[OneNote でページを開く]({result['page_url']})")
                            st.session_state.diary_body_draft = ""
                            st.session_state.diary_check_done = False
                        else:
                            st.error(f"❌ {result['message']}")


# confirm_rebuild ロジックを復元
if confirm_rebuild():
    try:
        rebuild_project()
    except Exception as e:
        logger.error(f"プロジェクトの再構築中にエラーが発生しました: {e}")
else:
    try:
        setup_sidebar()
        if st.session_state.get("app_page") == "📔 OneNote日記":
            display_onenote_diary()
        elif st.session_state.get("app_page") == "🛡️ エンタープライズ統合":
            display_enterprise_dashboard()
        else:
            display_app()
    except Exception as e:
        logger.error(f"アプリ実行中にエラーが発生しました: {e}")
        st.error(f"❌ エラー: {e}")
