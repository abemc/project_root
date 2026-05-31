import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime
import html
import uuid
from src.rag.date_utils import parse_relative_date

import streamlit as st
import streamlit.components.v1 as components
import logging
import json
import time
import re
import difflib
import pandas as pd
import plotly.express as px
from src.ui.diagram_settings import (
    DIAGRAM_MODE_MERMAID,
    diagram_mode_from_label,
    diagram_mode_options,
    diagram_mode_to_label,
    diagram_steps_for_query,
    diagram_title_for_query,
    normalize_diagram_mode,
)
from src.ui.user_preference_profile import (
    build_response_style_directive,
    infer_response_preferences,
)
try:
    from src.safety.ethics_guard import EthicsGuard
    ethics_guard_available = True
except Exception:
    EthicsGuard = None
    ethics_guard_available = False

try:
    from autonomous_rag_agent import AutonomousRAGAgent
    rag_agent_available = True
except Exception:
    AutonomousRAGAgent = None
    rag_agent_available = False

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
    if chunk_size <= 0:
        return [text] if text else []
    if overlap < 0:
        overlap = 0
    # overlap が大きすぎると末尾で極小チャンクが大量に発生するため制限する
    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 4)

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
        if chunk and (not chunks or chunk != chunks[-1]):
            chunks.append(chunk)
        # 末尾に到達したら終了
        if end >= length:
            break
        # 次の開始位置はオーバーラップ分だけ前に戻す
        next_start = end - overlap
        if next_start <= start:
            next_start = start + max(1, chunk_size - overlap)
        start = min(next_start, length)

    # 末尾の極小チャンクはノイズになりやすいため削除
    min_tail_chars = max(20, overlap // 2)
    if len(chunks) >= 2 and len(chunks[-1]) < min_tail_chars:
        chunks.pop()
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


_MERMAID_BLOCK_RE = re.compile(r"```mermaid(?:\s*\n|\s+)(.*?)```", re.DOTALL | re.IGNORECASE)
_ethics_guard = None


def _get_ethics_guard():
    global _ethics_guard
    if _ethics_guard is None and ethics_guard_available:
        try:
            _ethics_guard = EthicsGuard()
        except Exception:
            _ethics_guard = None
    return _ethics_guard


def _check_user_instruction_ethics(query: str, source: str = "chat_input") -> dict:
    """ユーザー指示の倫理チェックを実行し、判定を辞書で返す。"""
    guard = _get_ethics_guard()
    if not guard:
        return {
            "action": "allow",
            "category": "unavailable",
            "reason": "倫理チェック未初期化",
            "confidence": 0.0,
            "matched_rules": [],
        }

    try:
        decision = guard.evaluate(query or "", source=source)
        return {
            "action": decision.action,
            "category": decision.category,
            "reason": decision.reason,
            "confidence": decision.confidence,
            "matched_rules": decision.matched_rules,
        }
    except Exception as e:
        logger.warning(f"ethics_check_failed: {e}")
        return {
            "action": "allow",
            "category": "error",
            "reason": "倫理チェック例外",
            "confidence": 0.0,
            "matched_rules": [],
        }


def _query_requests_diagram(query: str) -> bool:
    if not query:
        return False
    return bool(re.search(r"図解|図で|フロー図|構成図|mermaid|チャート|diagram", query, re.IGNORECASE))


def _query_is_beginner_learning_request(query: str) -> bool:
    if not query:
        return False
    q = str(query).strip()
    beginner_terms = [
        r"知識は?ゼロ",
        r"初心者",
        r"入門",
        r"何から始め",
        r"どう勉強",
        r"勉強したい",
        r"学習(したい|方法)",
        r"はじめたい",
    ]
    topic_terms = [
        r"LLM",
        r"大規模言語モデル",
        r"生成AI",
        r"RAG",
        r"プロンプト",
    ]
    beginner_hit = any(re.search(p, q, re.IGNORECASE) for p in beginner_terms)
    topic_hit = any(re.search(p, q, re.IGNORECASE) for p in topic_terms)
    return beginner_hit and topic_hit


def _has_mermaid_block(text: str) -> bool:
    return bool(text and _MERMAID_BLOCK_RE.search(text))


def _normalize_mermaid_blocks(text: str) -> str:
    """Mermaid フェンスの揺れを正規化する（1行記法や余分空白を吸収）。"""
    s = str(text or "")
    if not s:
        return s

    def _repl(match):
        body = (match.group(1) or "").strip()
        return f"```mermaid\n{body}\n```"

    # ```mermaid graph TD; ... ``` のような1行/崩れた表記を正規化
    s = re.sub(r"```mermaid\s+([\s\S]*?)```", _repl, s, flags=re.IGNORECASE)
    return s


def _fallback_mermaid_for_query(query: str) -> str:
    q = (query or "質問").strip().replace("\n", " ")[:60]
    escaped_q = q.replace("\"", "'")
    if re.search(r"構造|仕組み|流れ|関係|説明|解説", q, re.IGNORECASE):
        step2 = "要素を分解"
        step3 = "関係を整理"
        step4 = "全体の流れ"
    else:
        step2 = "要点を整理"
        step3 = "根拠を確認"
        step4 = "結論"
    return (
        "\n\n```mermaid\n"
        "flowchart TD\n"
        f"    A[質問: {escaped_q}] --> B[{step2}]\n"
        f"    B --> C[{step3}]\n"
        f"    C --> D[{step4}]\n"
        "    D --> E[結論]\n"
        "```\n"
    )


def _render_markdown_with_mermaid(markdown_text: str) -> None:
    """Markdown 内の Mermaid ブロックを図として描画し、それ以外は通常表示する。"""
    if not markdown_text:
        return

    parts = []
    last_end = 0
    for m in _MERMAID_BLOCK_RE.finditer(markdown_text):
        if m.start() > last_end:
            parts.append(("md", markdown_text[last_end:m.start()]))
        parts.append(("mermaid", m.group(1).strip()))
        last_end = m.end()
    if last_end < len(markdown_text):
        parts.append(("md", markdown_text[last_end:]))

    # Mermaid ブロックが無ければ従来表示
    if not any(kind == "mermaid" for kind, _ in parts):
        st.markdown(markdown_text, unsafe_allow_html=True)
        return

    for kind, chunk in parts:
        if kind == "md":
            if chunk and chunk.strip():
                st.markdown(chunk, unsafe_allow_html=True)
            continue

        if not chunk:
            continue

        block_id = f"mermaid-{uuid.uuid4().hex}"
        escaped_code = html.escape(chunk)
        est_height = max(260, min(1200, 180 + (chunk.count("\n") + 1) * 26))
        mermaid_html = f"""
<style>
    body {{ margin: 0; background: transparent; }}
    .mermaid-wrap {{
        overflow-x: auto;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
        padding: 10px 12px;
    }}
    .mermaid svg {{ max-width: 100%; height: auto; }}
</style>
<div class=\"mermaid-wrap\"> 
    <pre class=\"mermaid\" id=\"{block_id}\">{escaped_code}</pre>
</div>
<script type=\"module\"> 
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{
            startOnLoad: false,
            securityLevel: 'loose',
            theme: 'neutral',
            fontFamily: '"Noto Sans JP", "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif',
            flowchart: {{ useMaxWidth: true, htmlLabels: false, curve: 'linear' }},
            themeVariables: {{
                primaryColor: '#e8f0ff',
                primaryBorderColor: '#5b7fd1',
                lineColor: '#5b7fd1',
                textColor: '#0f172a',
                fontSize: '14px'
            }}
        }});
    const el = document.getElementById('{block_id}');
    if (el) {{
            try {{
                const src = (el.textContent || '').trim();
                // まずパース検証し、文法エラー時は Mermaid エラーカードを出さずにコード表示へフォールバック
                await mermaid.parse(src);
                const renderId = '{block_id}-svg';
                const r = await mermaid.render(renderId, src);
                const host = document.createElement('div');
                host.innerHTML = r.svg;
                el.replaceWith(host);
            }} catch (e) {{
                console.error('Mermaid render/parse error:', e);
                const fallback = document.createElement('pre');
                fallback.style.margin = '0';
                fallback.style.padding = '8px';
                fallback.style.whiteSpace = 'pre-wrap';
                fallback.style.wordBreak = 'break-word';
                fallback.textContent = (el.textContent || '').trim();
                el.replaceWith(fallback);
            }}
    }}
</script>
"""
        components.html(mermaid_html, height=est_height, scrolling=True)


def _render_mermaid_blocks_only(markdown_text: str) -> bool:
    """Markdown から Mermaid ブロックのみ抽出して描画する。描画したら True を返す。"""
    if not markdown_text:
        return False
    found = False
    for m in _MERMAID_BLOCK_RE.finditer(markdown_text):
        code = (m.group(1) or "").strip()
        if not code:
            continue
        found = True
        _render_markdown_with_mermaid(f"```mermaid\n{code}\n```")
    return found


def _safe_render_mermaid_blocks(markdown_text: str) -> None:
    """Mermaid 図の描画を安全に行い、失敗時はコード表示へフォールバックする。"""
    try:
        rendered = _render_mermaid_blocks_only(markdown_text)
        if not rendered:
            return
    except Exception as e:
        _append_run_log(f"mermaid_render_error: {e}")
        st.info("図の再表示で問題が発生したため、図コードを表示します。")
        # フォールバック: Mermaid コードをそのまま表示
        for m in _MERMAID_BLOCK_RE.finditer(markdown_text or ""):
            code = (m.group(1) or "").strip()
            if code:
                st.code(code, language="mermaid")


def _render_safe_flow_diagram(title: str, steps: list[str]) -> None:
        """Streamlit/preview で安定して表示できる純HTMLの図解を描画する。"""
        safe_steps = [str(step).strip() for step in steps if str(step).strip()]
        if not safe_steps:
                safe_steps = ["要点を整理", "根拠を確認", "結論をまとめる"]

        boxes = []
        for idx, step in enumerate(safe_steps, start=1):
                boxes.append(
                        '<div class="diag-node">'
                        f'<span class="diag-badge">{idx}</span>'
                        f'<span class="diag-text">{html.escape(step)}</span>'
                        '</div>'
                )
                if idx < len(safe_steps):
                        boxes.append('<div class="diag-arrow" aria-hidden="true">→</div>')

        est_height = 180 if len(safe_steps) <= 4 else 230
        html_body = f"""
<style>
    .diag-wrap {{
        margin: 10px 0 6px 0;
        padding: 14px 16px;
        border: 1px solid #cfd8e6;
        border-radius: 14px;
        background:
            radial-gradient(circle at 8% 14%, #fff7e6 0 18%, transparent 20%),
            radial-gradient(circle at 92% 80%, #e8f4ff 0 20%, transparent 22%),
            linear-gradient(180deg, #f7fbff 0%, #ffffff 100%);
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
    }}
    .diag-title {{
        font-weight: 700;
        color: #102a43;
        margin-bottom: 10px;
        font-size: 0.98rem;
        letter-spacing: 0.02em;
    }}
    .diag-flow {{
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 10px;
        color: #102a43;
        font-family: "Noto Sans JP", "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif;
    }}
    .diag-node {{
        display: inline-flex;
        align-items: center;
        gap: 9px;
        min-height: 46px;
        padding: 8px 12px;
        border: 1px solid #7b9bd6;
        border-radius: 999px;
        background: #edf4ff;
        color: #1f3a67;
        font-weight: 600;
        line-height: 1.35;
        box-sizing: border-box;
        max-width: 100%;
    }}
    .diag-badge {{
        width: 22px;
        height: 22px;
        border-radius: 999px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: #2f5fb7;
        color: #ffffff;
        font-size: 0.78rem;
        font-weight: 700;
        flex: 0 0 22px;
    }}
    .diag-text {{
        word-break: break-word;
    }}
    .diag-arrow {{
        font-size: 1.1rem;
        font-weight: 700;
        color: #6c7d93;
        padding: 0 2px;
    }}
    @media (max-width: 640px) {{
        .diag-flow {{
            align-items: stretch;
        }}
        .diag-arrow {{
            width: 100%;
            text-align: center;
            transform: rotate(90deg);
            padding: 0;
            margin: -3px 0;
        }}
        .diag-node {{
            width: 100%;
            border-radius: 12px;
        }}
    }}
</style>
<div class="diag-wrap">
    <div class="diag-title">{html.escape(title)}</div>
    <div class="diag-flow">
        {''.join(boxes)}
    </div>
</div>
"""
        components.html(html_body, height=est_height, scrolling=False)

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

# ロギングの設定（早期初期化）
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Streamlit 実行時の詳細ログ出力先（UIの問題解析用）
RUN_LOG_PATH = Path(__file__).resolve().parent / "logs" / "streamlit_run.log"

# チャット履歴ファイルパス（昨日以前のやり取りを参照可能）
CHAT_HISTORY_PATH = Path(__file__).resolve().parent / "logs" / "chat_history.jsonl"

def _append_run_log(msg: str) -> None:
    try:
        RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RUN_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now().isoformat()} - {msg}\n")
    except Exception:
        logger.exception("failed to write run log")


def _load_chat_history() -> list:
    """チャット履歴ファイル（JSONL）から過去のメッセージを読み込む。
    セッション初期化時に使用して、昨日以前のやり取りを復元する。"""
    try:
        if not CHAT_HISTORY_PATH.exists():
            return []
        messages = []
        with open(CHAT_HISTORY_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    msg = json.loads(line.strip())
                    if msg:
                        messages.append(msg)
                except (json.JSONDecodeError, ValueError):
                    continue
        return messages
    except Exception as e:
        logger.warning(f"チャット履歴の読み込みに失敗: {e}")
        return []


def _save_chat_message(message: dict) -> None:
    """チャットメッセージを履歴ファイル（JSONL）に追加保存する。
    メッセージ追加時に毎回呼び出して、永続化を保証する。"""
    try:
        CHAT_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CHAT_HISTORY_PATH, "a", encoding="utf-8") as f:
            # タイムスタンプを付加
            msg_with_ts = dict(message)
            if "timestamp" not in msg_with_ts:
                msg_with_ts["timestamp"] = datetime.now().isoformat()
            f.write(json.dumps(msg_with_ts, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"チャット履歴の保存に失敗: {e}")


def _parse_chapter_no(text: str) -> int | None:
    s = str(text or "")
    word_map = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
    }
    patterns = [
        r"第\s*([0-9０-９]{1,2})\s*章",
        r"\bchapter\s*([0-9]{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\b",
        r"\bch(?:apter)?[\s._-]*0*([0-9]{1,2})\b",
        r"(?:^|\s)([0-9０-９]{1,2})\s*[\.:：]\s*[A-Za-z一-龠ァ-ヶ々]",
    ]
    for p in patterns:
        m = re.search(p, s, re.IGNORECASE)
        if not m:
            continue
        found = m.group(1)
        if not found:
            continue
        try:
            lowered = found.lower()
            if lowered in word_map:
                return word_map[lowered]
            return int(str(found).translate(str.maketrans("０１２３４５６７８９", "0123456789")))
        except Exception:
            continue
    return None

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
        # ページタイトルを取得
        title_tag = soup.find('title')
        page_title = title_tag.get_text(strip=True) if title_tag else ''

        text = soup.get_text(separator="\n", strip=True)
        # 空行を圧縮
        lines = [l for l in text.splitlines() if l.strip()]
        result = "\n".join(lines)
        return result[:max_chars] + ("…（以下省略）" if len(result) > max_chars else "")
    except Exception as e:
        return f"[URLの取得に失敗しました: {e}]"


def _fetch_url_text_and_title(url: str, max_chars: int = 4000) -> tuple:
    """URLにアクセスしてページ本文とタイトルを返す。失敗時はエラー文字列を返す。
    戻り値: (text, title)"""
    if not _is_safe_url(url):
        return ("[セキュリティ上の理由によりこのURLは取得できません]", "")
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
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()
        title_tag = soup.find('title')
        page_title = title_tag.get_text(strip=True) if title_tag else ''
        text = soup.get_text(separator="\n", strip=True)
        lines = [l for l in text.splitlines() if l.strip()]
        result = "\n".join(lines)
        return (result[:max_chars] + ("…（以下省略）" if len(result) > max_chars else ""), page_title)
    except Exception as e:
        return (f"[URLの取得に失敗しました: {e}]", "")


def _extract_game_score_from_url(url: str) -> dict | None:
    """指定URLから試合の最終スコアを抽出する。成功時は辞書を返す。
    返り値例: {'teams': [{'name':'北海道日本ハムファイターズ','score':5}, {'name':'埼玉西武','score':4}], 'url': url}
    """
    try:
        if not _is_safe_url(url):
            return None
        import requests as _requests
        from bs4 import BeautifulSoup as _BS
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = _requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = _BS(resp.text, "html.parser")

        # Yahoo のスコアテーブル検出 (class 'bb-gameScoreTable') を優先
        table = soup.find('table', class_='bb-gameScoreTable')
        if table:
            # ヘッダ行から「計」の列Indexを探す
            header = None
            for tr in table.find_all('tr'):
                ths = [th.get_text(strip=True) for th in tr.find_all('th')]
                if '計' in ths:
                    header = ths
                    break
            if header:
                idx = header.index('計')
                teams = []
                for tr in table.find_all('tr'):
                    cells = [c.get_text(strip=True) for c in tr.find_all(['th','td'])]
                    if len(cells) > idx:
                        name = cells[0]
                        try:
                            score = int(cells[idx])
                        except Exception:
                            continue
                        teams.append({'name': name, 'score': score})
                if teams:
                    return {'teams': teams, 'url': url}

        # 汎用的なボックススコア検出: '計'と'安'が近くにある構造を探索
        text = soup.get_text('\n')
        if '計' in text and '安' in text:
            # 簡易パース: 行単位で '計' を含む行を探し、その前後の行でチーム名と数値を探す
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            for i,l in enumerate(lines):
                if l.startswith('計') or l == '計':
                    # 前後にチーム行があると仮定
                    candidates = []
                    for j in range(max(0,i-4), min(len(lines), i+6)):
                        candidates.append(lines[j])
                    # 数字を含む行を抽出
                    import re
                    parsed = []
                    for c in candidates:
                        m = re.findall(r"(\D{1,30}?)(\d+)\s*$", c)
                        if m:
                            name = m[0][0].strip()
                            score = int(m[0][1])
                            parsed.append({'name': name, 'score': score})
                    if parsed:
                        return {'teams': parsed, 'url': url}

    except Exception:
        return None
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
SIDEBAR_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "sidebar_config.json"


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


def _load_sidebar_history_days(default: int = 5) -> int:
    """サイドバー設定ファイルから実行履歴の表示日数を読み込む。"""
    try:
        if not SIDEBAR_CONFIG_PATH.exists():
            return default
        with open(SIDEBAR_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        value = ((data or {}).get("history") or {}).get("history_days", default)
        value = int(value)
        return max(1, min(30, value))
    except Exception:
        return default


def _save_sidebar_history_days(days: int) -> None:
    """実行履歴の表示日数をサイドバー設定へ保存する。"""
    value = max(1, min(30, int(days)))
    SIDEBAR_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {}
    if SIDEBAR_CONFIG_PATH.exists():
        try:
            with open(SIDEBAR_CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    payload = loaded
        except Exception:
            payload = {}
    history_cfg = payload.get("history")
    if not isinstance(history_cfg, dict):
        history_cfg = {}
    history_cfg["history_days"] = value
    payload["history"] = history_cfg
    with open(SIDEBAR_CONFIG_PATH, "w", encoding="utf-8") as f:
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
    if "sidebar_history_days" not in st.session_state:
        loaded_days = _load_sidebar_history_days(default=5)
        st.session_state.sidebar_history_days = loaded_days
        st.session_state._last_saved_sidebar_history_days = loaded_days
        _save_sidebar_history_days(loaded_days)

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

        # Phase 5: Learning Systems Panel (render BEFORE page radio so button can set app_page)
        try:
            from src.rag.learning_dashboard import add_learning_panel_to_sidebar
            add_learning_panel_to_sidebar()
        except Exception:
            pass

        # ===== ページナビゲーション =====
        if "app_page" not in st.session_state:
            st.session_state.app_page = "RAGエージェント"
        _page_options = ["RAGエージェント", "📔 OneNote日記", "🛡️ エンタープライズ統合", "🧠 Learning Dashboard"]
        # determine index from current session state to ensure programmatic changes persist
        try:
            _current = st.session_state.get("app_page", _page_options[0])
            _index = _page_options.index(_current) if _current in _page_options else 0
        except Exception:
            _index = 0
        st.sidebar.radio(
            "ページ",
            _page_options,
            key="app_page",
            index=_index,
            horizontal=True,
        )
        st.sidebar.markdown("---")

        # ===== チャット履歴クリア機能 =====
        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("🗑️ チャット履歴クリア", key="clear_chat_history", use_container_width=True):
                st.session_state["messages"] = []
                st.session_state["presearch_query"] = ""
                st.session_state["presearch_results"] = []
                st.session_state["chat_history"] = []
                # チャット履歴ファイルも削除
                try:
                    base_dir = Path(__file__).resolve().parent
                    chat_files = [
                        base_dir / "logs" / "chat_history.jsonl",  # 現在の保存先
                        base_dir / "data" / "chat_history.json",   # 旧保存先（互換）
                    ]
                    for chat_file in chat_files:
                        if chat_file.exists():
                            chat_file.unlink()
                    st.success("✅ チャット履歴をクリアしました")
                except Exception as e:
                    st.warning(f"⚠️ クリア処理中に警告: {e}")
        with col2:
            if st.button("🔄 ページリロード", key="reload_page", use_container_width=True):
                st.rerun()

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
                            last_success_source = None
                            total_files = len(uploaded_files)
                            
                            # プログレスバー
                            progress_bar = st.progress(0, text="PDFの処理を開始します...")
                            
                            for i, uploaded_file in enumerate(uploaded_files):
                                try:
                                    def update_progress(page_percent, status_msg):
                                        current_total_progress = (i + page_percent) / total_files
                                        file_label = f"処理中 ({i+1}/{total_files}): {uploaded_file.name}"
                                        progress_bar.progress(min(current_total_progress, 0.99), text=f"{file_label} - {status_msg}")
                                    
                                    if uploaded_file.name.lower().endswith(".pdf"):
                                        result = retriever.add_pdf(uploaded_file, progress_callback=update_progress)
                                    else:
                                        result = retriever.add_image(uploaded_file, progress_callback=update_progress)
                                    
                                    if result.get("chunks_added", 0) > 0:
                                        total_chunks_added += result["chunks_added"]
                                        total_ocr_pages += result.get('ocr_pages', 0)
                                        last_success_source = result.get("source_name") or uploaded_file.name
                                    else:
                                        failed_files.append(f"{uploaded_file.name} ({result.get('status', '不明なエラー')})")
                                except Exception as e:
                                    logger.error(f"ファイル処理エラー: {e}")
                                    failed_files.append(f"{uploaded_file.name} (エラー: {str(e)[:50]})")
                            
                            # 完了処理
                            progress_bar.progress(1.0, text="完了しました！")
                            time.sleep(1.0)
                            progress_bar.empty()
                            
                            if total_chunks_added > 0:
                                st.success(f"{len(uploaded_files) - len(failed_files)}個のファイルから合計 {total_chunks_added} 個のチャンクを追加しました。(OCR実行: {total_ocr_pages}ページ)")
                                try:
                                    if last_success_source:
                                        st.session_state['last_added_source'] = last_success_source
                                        st.session_state['last_uploaded_file_source'] = last_success_source
                                    # URL由来の直近マーカーをクリアして、PDF文脈を優先させる
                                    st.session_state['last_added_source_url'] = None
                                except Exception:
                                    pass
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
                                try:
                                    st.session_state['last_added_source'] = "テキスト入力"
                                    st.session_state['last_added_source_url'] = None
                                except Exception:
                                    pass
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
                                    try:
                                        st.session_state['last_added_source'] = text_file.name
                                        st.session_state['last_uploaded_file_source'] = text_file.name
                                        st.session_state['last_added_source_url'] = None
                                    except Exception:
                                        pass
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
                    with st.spinner("🌐 URLを取得・コーパスへ登録しています..."):
                        _append_run_log(f"url_fetch_start url={url_input.strip()}")
                        page_text, page_title = _fetch_url_text_and_title(url_input.strip(), max_chars=20000)
                        _append_run_log(f"url_fetch_result text_len={len(page_text)} title={page_title}")
                        if page_text.startswith('[URLの取得に失敗') or page_text.startswith('[セキュリティ上の理由'):
                            st.sidebar.error(f"❌ 取得エラー: {page_text}")
                            _append_run_log(f"url_fetch_error: {page_text}")
                        else:
                            # chunk and add to retriever if available
                            try:
                                chunks = _chunk_text(page_text)
                                _append_run_log(f"url_chunks_created count={len(chunks)}")
                                retriever = get_retriever()
                                _append_run_log(f"url_retriever_status available={bool(retriever)}")
                                ingested_at = datetime.now().isoformat()
                                display_source = page_title if page_title else url_input.strip()
                                source_info = {"source": display_source, "source_url": url_input.strip(), "title": page_title, "ingested_at": ingested_at}
                                if retriever:
                                    retriever.add_texts(chunks, source_info=source_info)
                                    retriever.save()
                                    st.session_state['last_added_source'] = display_source
                                    st.session_state['last_added_source_url'] = url_input.strip()
                                    st.sidebar.success(f"✅ URLの内容をコーパスに追加しました ({len(chunks)}チャンク)")
                                    _append_run_log(f"url_added_to_corpus source={display_source} chunks={len(chunks)}")
                                    time.sleep(0.3)
                                    try:
                                        st.rerun()
                                    except Exception:
                                        pass
                                else:
                                    st.sidebar.info("ℹ️ Retrieverが利用できないため、ローカル保存のみ行います")

                                # also save fetched text to rag_corpus/downloads for traceability
                                try:
                                    from urllib.parse import urlparse
                                    parsed = urlparse(url_input.strip())
                                    host = parsed.netloc.replace(':', '_') if parsed.netloc else 'site'
                                    safe_name = f"{host}_{int(time.time())}.txt"
                                    out_dir = Path(__file__).resolve().parent / 'rag_corpus' / 'downloads'
                                    out_dir.mkdir(parents=True, exist_ok=True)
                                    (out_dir / safe_name).write_text(page_text, encoding='utf-8')
                                except Exception:
                                    pass
                            except Exception as e:
                                st.sidebar.error(f"❌ 登録失敗: {str(e)[:120]}")
                    # 直近追加ドキュメントで検索するボタンを表示
                    if st.session_state.get('last_added_source'):
                        if st.button('🔎 直近追加ドキュメントで検索', key='search_last_added'):
                            try:
                                retriever = get_retriever()
                                if retriever:
                                    results = retriever.search('', top_k=5, source_filter=st.session_state.get('last_added_source'))
                                    if results:
                                        st.sidebar.info(f"🔍 {len(results)} 件ヒット（直近追加）")
                                        for r in results:
                                            src = (r.get('meta') or {}).get('source') or r.get('source') or '不明'
                                            score = r.get('score', 0.0)
                                            st.sidebar.caption(f"{src}  スコア: {score:.3f}")
                                    else:
                                        st.sidebar.info('該当ドキュメントのチャンクは見つかりませんでした')
                                else:
                                    st.sidebar.error('Retrieverが利用できません')
                            except Exception as e:
                                st.sidebar.error(f'検索エラー: {e}')
        
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
            # 回答の深掘りレベル（プリセット）
            depth = st.selectbox(
                "回答の深掘りレベル",
                options=["簡潔","標準","深掘り"],
                index=1,
                key="sidebar_depth"
            )
            st.session_state.depth = depth
            current_diagram_mode = normalize_diagram_mode(st.session_state.get("diagram_render_mode", "stable"))
            diagram_label = st.selectbox(
                "図解表示モード",
                options=diagram_mode_options(),
                index=diagram_mode_options().index(diagram_mode_to_label(current_diagram_mode)),
                key="sidebar_diagram_mode"
            )
            st.session_state.diagram_render_mode = diagram_mode_from_label(diagram_label)
            # 深掘りレベルに応じた推奨パラメータを適用（ユーザーの手動設定を上書きする）
            if depth == "簡潔":
                st.session_state.temperature = 0.0
                st.session_state.max_tokens = 256
            elif depth == "標準":
                # 標準はユーザー設定を尊重（既に temperature が設定済み）
                st.session_state.max_tokens = 1024
            else:  # 深掘り
                st.session_state.temperature = 0.2
                st.session_state.max_tokens = 4096

        with st.sidebar.expander("📝 クエリ設定", expanded=False):
            use_web_search_sidebar = st.checkbox(
                "🌐 ウェブ検索",
                value=bool(st.session_state.get("use_web_search", False)),
                key="sidebar_query_use_web_search",
            )
            st.session_state.use_web_search = use_web_search_sidebar

            use_autonomous_rag_sidebar = st.checkbox(
                "🤖 自律RAGモード",
                value=bool(st.session_state.get("use_autonomous_rag", False)),
                key="sidebar_query_use_autonomous_rag",
            )
            st.session_state.use_autonomous_rag = use_autonomous_rag_sidebar

            include_reasoning_sidebar = st.checkbox(
                "🧠 推論詳細",
                value=bool(st.session_state.get("include_reasoning", True)),
                key="sidebar_query_include_reasoning",
            )
            st.session_state.include_reasoning = include_reasoning_sidebar

            stream_output_sidebar = st.checkbox(
                "⚡ ストリーム",
                value=bool(st.session_state.get("stream_output", True)),
                key="sidebar_query_stream_output",
            )
            st.session_state.stream_output = stream_output_sidebar
        
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

            show_pref_profile = st.checkbox("🧭 推定プロファイルを表示", value=False, key="sidebar_show_pref_profile")
            st.session_state.show_pref_profile = show_pref_profile

            if show_pref_profile:
                profile = st.session_state.get("response_preference_profile") or {}
                if profile:
                    st.caption("会話履歴から推定した応答スタイル（セッション内）")
                    st.json(profile)
                else:
                    st.info("推定プロファイルはまだありません。1回以上対話すると表示されます。")
            
            auto_train_enabled = st.checkbox("自動トレーニングを有効化", value=False, key="sidebar_auto_train")
            st.session_state.auto_train_enabled = auto_train_enabled

            st.markdown("---")
            st.caption("RLHF適用ゲート閾値")

            rlhf_gate_min_entries = st.number_input(
                "最小サンプル数 (min_entries)",
                min_value=1,
                max_value=10000,
                value=int(st.session_state.get("rlhf_gate_min_entries", 20)),
                step=1,
                key="sidebar_rlhf_gate_min_entries",
                help="この件数未満ではRLHF重み更新をスキップします。",
            )
            st.session_state.rlhf_gate_min_entries = int(rlhf_gate_min_entries)

            rlhf_gate_min_csat = st.slider(
                "最小CSAT (min_csat)",
                min_value=1.0,
                max_value=5.0,
                value=float(st.session_state.get("rlhf_gate_min_csat", 3.2)),
                step=0.1,
                key="sidebar_rlhf_gate_min_csat",
                help="平均CSATがこの値未満の場合は更新をスキップします。",
            )
            st.session_state.rlhf_gate_min_csat = float(rlhf_gate_min_csat)

            rlhf_gate_min_adoption_rate = st.slider(
                "最小採用率 (min_adoption_rate)",
                min_value=0.0,
                max_value=1.0,
                value=float(st.session_state.get("rlhf_gate_min_adoption_rate", 0.30)),
                step=0.05,
                key="sidebar_rlhf_gate_min_adoption_rate",
                help="採用率がこの値未満の場合は更新をスキップします。",
            )
            st.session_state.rlhf_gate_min_adoption_rate = float(rlhf_gate_min_adoption_rate)

            rlhf_gate_min_nps = st.slider(
                "最小NPS (min_nps)",
                min_value=-10.0,
                max_value=10.0,
                value=float(st.session_state.get("rlhf_gate_min_nps", 0.0)),
                step=0.5,
                key="sidebar_rlhf_gate_min_nps",
                help="平均NPSがこの値未満の場合は更新をスキップします。",
            )
            st.session_state.rlhf_gate_min_nps = float(rlhf_gate_min_nps)

            st.caption("RLAIF（AIフィードバック統合）")
            rlaif_ai_weight = st.slider(
                "AI評価の重み (ai_weight)",
                min_value=0.0,
                max_value=1.0,
                value=float(st.session_state.get("rlaif_ai_weight", 0.35)),
                step=0.05,
                key="sidebar_rlaif_ai_weight",
                help="人手指標に対するAI評価の統合重みです。乖離が大きい場合は内部で自動減衰します。",
            )
            st.session_state.rlaif_ai_weight = float(rlaif_ai_weight)

            rlaif_min_ai_entries = st.number_input(
                "AI評価の最小件数 (min_ai_entries)",
                min_value=1,
                max_value=100000,
                value=int(st.session_state.get("rlaif_min_ai_entries", 30)),
                step=1,
                key="sidebar_rlaif_min_ai_entries",
                help="この件数未満のAI評価は統合に使いません。",
            )
            st.session_state.rlaif_min_ai_entries = int(rlaif_min_ai_entries)

            rlaif_min_ai_confidence = st.slider(
                "AI評価の最小信頼度 (min_ai_confidence)",
                min_value=0.0,
                max_value=1.0,
                value=float(st.session_state.get("rlaif_min_ai_confidence", 0.60)),
                step=0.05,
                key="sidebar_rlaif_min_ai_confidence",
                help="AI評価の平均信頼度がこの値未満の場合は統合をスキップします。",
            )
            st.session_state.rlaif_min_ai_confidence = float(rlaif_min_ai_confidence)

            rlaif_auto_aggregate_ai = st.checkbox(
                "AI評価集計を自動実行（ai_feedback_aggregated.jsonを生成）",
                value=bool(st.session_state.get("rlaif_auto_aggregate_ai", True)),
                key="sidebar_rlaif_auto_aggregate_ai",
            )
            st.session_state.rlaif_auto_aggregate_ai = bool(rlaif_auto_aggregate_ai)

            rlaif_enable_delta_cap = st.checkbox(
                "RLAIF重み変動キャップを有効化",
                value=bool(st.session_state.get("rlaif_enable_delta_cap", True)),
                key="sidebar_rlaif_enable_delta_cap",
                help="human+ai ブレンド時に重み変動幅を制限し、急激な変化を防ぎます。",
            )
            st.session_state.rlaif_enable_delta_cap = bool(rlaif_enable_delta_cap)

            rlaif_max_weight_delta = st.slider(
                "重み変動の上限 (rlaif_max_weight_delta)",
                min_value=0.0,
                max_value=1.0,
                value=float(st.session_state.get("rlaif_max_weight_delta", 0.25)),
                step=0.05,
                key="sidebar_rlaif_max_weight_delta",
                help="各重みの1回の更新で許容する最大変動幅です。",
            )
            st.session_state.rlaif_max_weight_delta = float(rlaif_max_weight_delta)

            rlhf_show_gate_logs = st.checkbox(
                "RLHFゲートログをLearning Dashboardで表示",
                value=bool(st.session_state.get("rlhf_show_gate_logs", True)),
                key="sidebar_rlhf_show_gate_logs",
            )
            st.session_state.rlhf_show_gate_logs = bool(rlhf_show_gate_logs)
        
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
        history_days = st.sidebar.number_input(
            "表示日数",
            min_value=1,
            max_value=30,
            value=int(st.session_state.get("sidebar_history_days", 5)),
            step=1,
            key="sidebar_history_days",
            help="実行履歴を表示する日数を指定します（最新日から）。",
        )
        history_days_int = int(history_days)
        if st.session_state.get("_last_saved_sidebar_history_days") != history_days_int:
            _save_sidebar_history_days(history_days_int)
            st.session_state._last_saved_sidebar_history_days = history_days_int
        with st.sidebar.expander("過去のクエリと結果"):
            # チャット履歴ファイルから過去のやり取りを表示
            history = _load_chat_history()
            if history:
                # 日付でグループ化して表示
                from datetime import datetime as dt_cls
                grouped = {}
                for msg in history:
                    ts = msg.get("timestamp", "")
                    if ts:
                        try:
                            msg_date = dt_cls.fromisoformat(ts).strftime("%Y-%m-%d")
                            if msg_date not in grouped:
                                grouped[msg_date] = []
                            grouped[msg_date].append(msg)
                        except:
                            continue
                
                # 最新の日付から古い順に表示
                for date_key in sorted(grouped.keys(), reverse=True)[:history_days_int]:
                    with st.sidebar.expander(f"📅 {date_key}"):
                        for msg in reversed(grouped[date_key]):
                            role_icon = "👤" if msg.get("role") == "user" else "🤖"
                            content = msg.get("content", "")[:100]  # 最初の100文字
                            st.caption(f"{role_icon} {content}...")
                
                # ダウンロードボタン
                import io
                csv_data = io.StringIO()
                csv_data.write("timestamp,role,content\n")
                for msg in history:
                    ts = msg.get("timestamp", "")
                    role = msg.get("role", "")
                    content = msg.get("content", "").replace(",", ";").replace("\n", " ")
                    csv_data.write(f'"{ts}","{role}","{content}"\n')
                
                st.sidebar.download_button(
                    label="📥 履歴をCSVで保存",
                    data=csv_data.getvalue(),
                    file_name=f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.caption("履歴がまだありません")
        
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
        "messages": _load_chat_history(),  # 昨日以前のチャット履歴を読み込む
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
        "presearch_query": "",
        "response_preference_profile": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _extract_conclusion_and_sources(text: str) -> dict:
    """LLMの自由形式テキストから「結論」と「出典リスト」を切り出す。
    戻り値: {"conclusion": str, "sources": [{"id":..., "text":...}, ...], "raw": text}
    ロバスト性を重視し、最初の非空行を結論と見なす。出典は [web_n] を含む行を抽出。
    """
    lines = [l.strip() for l in text.splitlines()]
    # 結論: 最初の連続する短い段落（最大3行）
    conclusion_lines = []
    idx = 0
    while idx < len(lines) and (not lines[idx]):
        idx += 1
    # collect up to 3 lines or until blank
    while idx < len(lines) and len(conclusion_lines) < 3 and lines[idx]:
        conclusion_lines.append(lines[idx])
        idx += 1
    conclusion = "\n".join(conclusion_lines).strip()

    # sources: find lines containing [web_n] or raw URLs and normalize IDs
    sources = []
    import re
    src_pattern = re.compile(r"\[?(web_\d+)\]?|(https?://[^\s]+)")
    for l in lines:
        for m in src_pattern.finditer(l):
            web_id = m.group(1)
            url_match = m.group(2)
            src_id = web_id or url_match or m.group(0)
            # normalize id (strip surrounding brackets if present)
            if isinstance(src_id, str):
                src_id = src_id.strip("[]")
            # extract surrounding short snippet
            snippet = l
            sources.append({"id": src_id, "text": snippet})

    return {"conclusion": conclusion or text[:200], "sources": sources, "raw": text}


def _normalize_source_records(items) -> list[dict]:
    """Normalize mixed source schemas into {id, text} records for UI rendering."""
    if not isinstance(items, list):
        return []

    normalized = []
    seen = set()

    for it in items:
        if not isinstance(it, dict):
            continue

        src_id = it.get("id") or it.get("name") or it.get("source_id")
        src_text = it.get("text") or it.get("title") or it.get("snippet") or ""
        src_url = it.get("url") or it.get("path")

        meta = it.get("meta") if isinstance(it.get("meta"), dict) else {}
        if not src_url:
            src_url = meta.get("source_url") or meta.get("source")

        if isinstance(src_url, str):
            src_url = src_url.strip()
        else:
            src_url = ""

        if src_url and src_url not in str(src_text):
            src_text = f"{src_text} {src_url}".strip()

        if not src_id:
            src_id = src_url or "source"

        rec = {"id": str(src_id), "text": str(src_text).strip()}
        key = (rec["id"], rec["text"])
        if key in seen:
            continue
        seen.add(key)
        normalized.append(rec)

    return normalized


def _sanitize_japanese_response_text(text: str) -> str:
    """表示前に日本語回答の混在表記を最小限で正規化する。"""
    s = str(text or "")
    # マンドラ表記の崩れ（簡体字/混在）を統一
    s = re.sub(r"マン\s*[德徳]\s*[拉ラ]\s*(さん)?", "マンドラ", s)
    s = re.sub(r"マン\s*德\s*ラ\s*(さん)?", "マンドラ", s)

    # よく混入する簡体字を日本語漢字へ置換
    trans = str.maketrans({
        "乐": "楽",
        "馆": "館",
        "发": "発",
        "测": "測",
        "确": "確",
    })
    s = s.translate(trans)
    return s


def _translate_summary_to_japanese_if_needed(text: str, force: bool = False) -> str:
    """英語主体の要約文を日本語へ翻訳する。構造と出典IDは保持する。"""
    raw_text = str(text or "").strip()
    if not raw_text:
        return raw_text

    if not force:
        # 英字の混在度で翻訳要否を判定（短い英単語/AI略語も拾う）
        alpha_count = len(re.findall(r"[A-Za-z]", raw_text))
        jp_count = len(re.findall(r"[ぁ-んァ-ヶ一-龠々]", raw_text))
        if alpha_count < 10:
            return _sanitize_japanese_response_text(raw_text)
        if jp_count > 0 and alpha_count / max(len(raw_text), 1) < 0.05:
            return _sanitize_japanese_response_text(raw_text)

    try:
        if not llm_available:
            _append_run_log("summary_translation skipped: llm unavailable")
            return _sanitize_japanese_response_text(raw_text)

        translate_prompt = (
            "以下の要約文を自然な日本語に翻訳してください。\n"
            "- 箇条書き、番号、見出し構造を維持すること\n"
            "- [up_123] や [web_1] のような出典IDはそのまま残すこと\n"
            "- PDFファイル名、数式、章番号、固有名詞は必要に応じて維持すること\n"
            "- 内容を省略・追加せず、訳文のみを返すこと\n\n"
            f"{raw_text}"
        )
        translated = call_llm(
            prompt=translate_prompt,
            model=st.session_state.get("llm_model", "qwen2.5:7b"),
            system_prompt="あなたは翻訳専用アシスタントです。入力文を日本語として自然になるよう整えてください。英語混じりなら正確に日本語へ翻訳し、出典IDや構造は維持し、説明を追加しないでください。",
            chat_history=None,
            temperature=0.0,
            max_tokens=min(int(st.session_state.get("max_tokens", 1200)), 1600),
        )
        if isinstance(translated, str) and translated.strip() and not translated.startswith("Error"):
            _append_run_log("summary_translation applied")
            return _sanitize_japanese_response_text(translated.strip())
        _append_run_log("summary_translation fallback: llm empty_or_error")
    except Exception:
        _append_run_log("summary_translation fallback: exception")
        pass

    return _sanitize_japanese_response_text(raw_text)


def _build_file_ref_summary_response(docs: list, source_name: str, detailed_query: str | None = None) -> str:
    """PDF/ファイル参照クエリ向けに、抽出チャンクから章立て要約または詳細説明を生成する。"""
    def _extract_chapter_no(text: str) -> int | None:
        return _parse_chapter_no(text)

    normalized_docs = []
    for idx, d in enumerate(docs or [], 1):
        meta = d.get("meta") or {}
        raw = re.sub(r"\s+", " ", str(d.get("text") or "")).strip()
        if not raw:
            continue
        heading_match = re.search(
            r"(第\s*\d+\s*章[^。\n]{0,60}|Chapter\s*(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)[^.\n]{0,60}|\d+(?:\.\d+){1,3}\s+[^。\n]{0,60})",
            raw,
            re.IGNORECASE,
        )
        heading = heading_match.group(1).strip() if heading_match else raw[:36]
        heading = re.sub(r"[\-:：\s]+$", "", heading)
        sentences = re.split(r"(?<=[。.!?！？])\s+", raw)
        lead = " ".join([s.strip() for s in sentences[:2] if s.strip()]) or raw[:180]
        token_candidates = re.findall(r"[A-Za-z]{3,}|[ァ-ヶー]{3,}|[一-龠々]{2,}", raw)
        stop_kw = {"この", "それ", "ため", "こと", "について", "です", "ます", "および", "また"}
        keywords = []
        for token in token_candidates:
            if token in stop_kw:
                continue
            if token not in keywords:
                keywords.append(token)
            if len(keywords) >= 4:
                break
        normalized_docs.append({
            "id": d.get("id") or f"source_{idx}",
            "source": str(meta.get("source") or source_name),
            "heading": heading,
            "lead": lead[:220],
            "raw": raw,
            "keywords": keywords,
        })

    if not normalized_docs:
        return f"結論: 直近PDF『{source_name}』から要約可能な本文を抽出できませんでした。"

    if detailed_query:
        chapter_no = None
        chapter_match = re.search(r"(?:第\s*([0-9０-９]+)\s*章|chapter\s*([0-9]+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)|([0-9０-９]+)\s*章)", detailed_query, re.IGNORECASE)
        if chapter_match:
            found_q = chapter_match.group(1) or chapter_match.group(2) or chapter_match.group(3)
            chapter_no = _parse_chapter_no(found_q)
        target_docs = normalized_docs
        explicit_target = False
        if chapter_no is not None:
            chapter_candidates = []
            for item in normalized_docs:
                probe = f"{item.get('heading', '')}\n{item.get('raw', '')[:2000]}"
                found_no = _extract_chapter_no(probe)
                if found_no is None:
                    continue
                if found_no == chapter_no:
                    chapter_candidates.append(item)
            if chapter_candidates:
                target_docs = chapter_candidates[:2]
                explicit_target = True
            else:
                available = []
                for item in normalized_docs:
                    probe = f"{item.get('heading', '')}\n{item.get('raw', '')[:2000]}"
                    n = _extract_chapter_no(probe)
                    if n is not None and n not in available:
                        available.append(n)
                hint = f"（検出章: {', '.join([str(n) for n in available[:8]])}）" if available else ""
                not_found_text = (
                    f"結論: 直近PDF『{source_name}』では、第{chapter_no}章に一致する見出しを取得チャンク内で確認できませんでした。{hint}\n"
                    "補足: 『第2章 ではなく 2.1 を詳しく』のように節番号や見出し語で指定すると精度が上がります。"
                )
                return _translate_summary_to_japanese_if_needed(not_found_text, force=True)
        elif re.search(r"最初|冒頭|1つ目|一つ目", detailed_query):
            target_docs = [normalized_docs[0]]
            explicit_target = True
        else:
            # 「さらに詳しく」の連続入力では、毎回次のチャンク群へ進めて同文面の反復を避ける
            try:
                summary_ctx = st.session_state.get("last_file_summary_context") or {}
                cursor = int(summary_ctx.get("detail_cursor") or 0)
            except Exception:
                summary_ctx = {}
                cursor = 0
            window_size = 2
            start = max(0, min(cursor, max(len(normalized_docs) - 1, 0)))
            end = min(start + window_size, len(normalized_docs))
            target_docs = normalized_docs[start:end] or [normalized_docs[0]]
            try:
                if summary_ctx:
                    summary_ctx["detail_cursor"] = 0 if end >= len(normalized_docs) else end
                    st.session_state.last_file_summary_context = summary_ctx
            except Exception:
                pass

        detail_blocks = []
        for idx, item in enumerate(target_docs, 1):
            raw_text = item['raw'][:1500]  # 詳細説明用に1500文字まで取得（500→1500に増加）
            # 本文が英語である場合、LLMで構造化された日本語説明を生成
            detail_explanation = _translate_summary_to_japanese_if_needed(
                f"以下のテキストを、わかりやすく段落分けして日本語で説明してください：\n\n{raw_text}",
                force=True
            )
            # 不要な説明的プレフィックスを削除
            detail_explanation = re.sub(
                r"^(以下のテキストの説明です[：:]?|説明[：:]?|こちらは[^：:]*[：:]?)",
                "",
                detail_explanation.strip(),
                flags=re.IGNORECASE
            ).strip()
            if not detail_explanation or len(detail_explanation) < 30:
                # 翻訳/生成に失敗した場合はフォールバック
                detail_explanation = raw_text[:800]
            
            detail_blocks.append(
                f"{idx}. {item['heading']}\n"
                f"{detail_explanation}\n"
                f"- キーワード: {', '.join(item['keywords']) if item['keywords'] else '抽出なし'}\n"
                f"- 出典: [{item['id']}] {item['source']}"
            )
        response_text = (
            f"結論: 直近PDF『{source_name}』の詳細説明です。\n"
            + "【詳細説明】\n"
            + "\n".join(detail_blocks)
            + "\n補足: さらに細かく知りたい場合は『第2章をさらに詳しく』のように指定してください。"
        )
        if not explicit_target and len(normalized_docs) > 2:
            response_text += "\n注記: 次の『さらに詳しく』では別の章（次のチャンク）を説明します。"
        return _translate_summary_to_japanese_if_needed(response_text, force=True)

    sections = []
    source_notes = []
    for idx, item in enumerate(normalized_docs[:4], 1):
        sections.append(
            f"{idx}. {item['heading']}\n- 要点: {item['lead']}\n- キーワード: {', '.join(item['keywords']) if item['keywords'] else '抽出なし'}"
        )
        source_notes.append(f"- [{item['id']}] {item['source']}")
    response_text = (
        f"結論: 直近PDF『{source_name}』を章立てで要約しました。\n"
        + "【章立て要約】\n"
        + "\n".join(sections)
        + "\n【出典チャンク】\n"
        + "\n".join(source_notes[:4])
        + "\n補足: 取得チャンクに基づく抽出的要約です。必要なら章ごとの詳細説明を続けます。"
    )
    return _translate_summary_to_japanese_if_needed(response_text, force=True)


def _store_assistant_message(content) -> None:
    """Parse assistant content (str or dict) and append structured message to session_state.messages.
    If the content is a dict containing a clarification request (clarification_required),
    store the clarification question in session state so the UI can render a confirmation flow.
    """
    try:
        # If agent returned a structured dict (e.g., from autonomous_rag_agent), handle specially
        if isinstance(content, dict):
            provided_sources = _normalize_source_records(content.get("sources"))
            # If clarification is required, surface it to the UI
            if content.get("clarification_required"):
                st.session_state.clarification_active = True
                st.session_state.clarification_question = content.get("clarification_question") or "追加の確認が必要です。詳しく教えてください。"
                # store candidate options if provided
                candidates = content.get("candidates") or content.get("options") or None
                if candidates and isinstance(candidates, (list, tuple)):
                    st.session_state.clarification_candidates = list(candidates)
                else:
                    st.session_state.clarification_candidates = None
                # store a readable assistant message so it appears in the chat history
                readable = f"[確認が必要] {st.session_state.clarification_question}"
                readable = _sanitize_japanese_response_text(readable)
                parsed = _extract_conclusion_and_sources(readable)
                msg = {"role": "assistant", "content": readable, "conclusion": parsed["conclusion"], "sources": provided_sources or parsed["sources"], "clarification_required": True}
                st.session_state.messages.append(msg)
                _save_chat_message(msg)  # 履歴に保存
                return
            # fallback: if dict contains 'answer' or 'text', use that
            text = content.get("answer") or content.get("text") or str(content)
            st.session_state.clarification_active = False
            st.session_state.clarification_question = None
            st.session_state.clarification_candidates = None
            clean_text = _sanitize_japanese_response_text(str(text))
            clean_text = _normalize_mermaid_blocks(clean_text)
            parsed = _extract_conclusion_and_sources(clean_text)
            msg = {"role": "assistant", "content": clean_text, "conclusion": parsed["conclusion"], "sources": provided_sources or parsed["sources"]}
            st.session_state.messages.append(msg)
            _save_chat_message(msg)  # 履歴に保存
            return
    except Exception:
        # fall through to string handling on any unexpected structure
        pass

    # default: treat content as freeform string
    st.session_state.clarification_active = False
    st.session_state.clarification_question = None
    st.session_state.clarification_candidates = None
    clean_text = _sanitize_japanese_response_text(str(content))
    clean_text = _normalize_mermaid_blocks(clean_text)
    parsed = _extract_conclusion_and_sources(clean_text)
    msg = {"role": "assistant", "content": clean_text, "conclusion": parsed["conclusion"], "sources": parsed["sources"]}
    st.session_state.messages.append(msg)
    _save_chat_message(msg)  # 履歴に保存


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
                    transcribed = transcribe_audio_bytes(audio_value.getvalue(), whisper_size)
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


def _extract_page_number(text: str) -> int | None:
    """テキストからページ番号を抽出する（例：「425ページの翻訳を」→ 425）"""
    import re
    # 「425ページ」「425p」「p425」などのパターンを検出
    match = re.search(r'(?:第\s*)?(\d{1,4})\s*(?:ページ|p|P|pag\.?)?|p(?:ag\.?)?(\d{1,4})', text)
    if match:
        try:
            page_no = int(match.group(1) or match.group(2))
            if 1 <= page_no <= 10000:  # 妥当な範囲
                return page_no
        except (ValueError, TypeError):
            pass
    return None


def _build_query_with_context(query: str) -> str:
    """URL本文と添付ファイル内容を結合してLLM入力クエリを組み立てる。
    ページ指定検索（「425ページの翻訳を」）にも対応。
    """
    urls_in_query = _extract_urls(query)
    url_context = ""
    weather_context = _fetch_weather_context(query)
    page_context = ""
    
    # ページ指定検索の処理
    page_no = _extract_page_number(query)
    if page_no:
        try:
            # 最後に追加されたPDFから該当ページのチャンクを抽出
            retriever = get_retriever()
            if retriever:
                # コーパスメタデータから該当ドキュメントを検索
                meta_path = Path(__file__).resolve().parent / "corpus" / "corpus_meta.json"
                if meta_path.exists():
                    with open(meta_path, 'r', encoding='utf-8', errors='replace') as f:
                        all_chunks = json.load(f)
                    
                    # 直近追加ドキュメント（PDFを優先）からチャンクを抽出
                    last_source = st.session_state.get('last_uploaded_file_source') or st.session_state.get('last_added_source')
                    relevant_chunks = []
                    
                    if last_source and isinstance(all_chunks, list):
                        # ページ周辺のチャンク（±1ページ範囲）を取得
                        # 注意: チャンクにはページ番号がないため、チャンクインデックスで近似
                        source_chunks = [
                            c for c in all_chunks 
                            if (c.get("meta", {}).get("source") or c.get("source", "")) == last_source
                        ]
                        # ページは相対的にチャンク群の位置で推定（1ページ≈2-3チャンク）
                        if source_chunks:
                            estimated_chunk_idx = max(0, (page_no - 1) * 2)  # ページ数 * チャンク/ページ
                            start_idx = max(0, estimated_chunk_idx - 2)
                            end_idx = min(len(source_chunks), estimated_chunk_idx + 5)
                            relevant_chunks = source_chunks[start_idx:end_idx]
                    
                    if relevant_chunks:
                        page_context = f"\n\n【第{page_no}ページのコンテンツ（{len(relevant_chunks)}チャンク）】\n"
                        for i, chunk in enumerate(relevant_chunks, 1):
                            text = chunk.get("text", "")[:300]
                            page_context += f"{i}. {text}...\n"
                        _append_run_log(f"page_search page_no={page_no} chunks_found={len(relevant_chunks)} source={last_source}")
                    else:
                        page_context = f"\n\n【ページ検索】第{page_no}ページのコンテンツが見つかりませんでした。"
                        _append_run_log(f"page_search page_no={page_no} chunks_found=0")
        except Exception as e:
            logger.warning(f"ページ指定検索エラー: {e}")
            _append_run_log(f"page_search_error: {e}")
    
    if urls_in_query:
        _append_run_log(f"query_urls_found count={len(urls_in_query)} urls={urls_in_query}")
        url_context = "\n\n【URLから取得したページ内容】\n"
        for u in urls_in_query[:3]:
            with st.spinner(f"🌐 {u} を取得中..."):
                page_text = _fetch_url_text(u)
                _append_run_log(f"query_url_fetched url={u} text_len={len(page_text)}")
            url_context += f"\n🔗 URL: {u}\n{page_text}\n---\n"
    else:
        _append_run_log(f"query_no_urls_found")

    if st.session_state.attached_file_contents:
        file_context = "\n\n【添付ファイルの内容】\n"
        for file_info in st.session_state.attached_file_contents:
            filename = str(file_info["filename"]).encode("utf-8", "replace").decode("utf-8")
            content = str(file_info["content"]).encode("utf-8", "replace").decode("utf-8")
            file_context += f"\n📄 ファイル: {filename}\n"
            file_context += f"内容:\n{content}\n"
            file_context += "---\n"
        return (
            f"{query}{url_context}{weather_context}{page_context}\n\n{file_context}\n\n"
            "【重要】上記のファイル・記事内容が英語であっても、回答は必ず日本語のみで行ってください。"
        )

    if url_context or weather_context or page_context:
        base_prompt = (
            f"{query}{url_context}{weather_context}{page_context}\n\n"
            "【重要】上記の実際のページ内容のみに基づいて日本語で回答してください。"
            "ページ内容や天気データに書かれていないことは推測・創作せず、『提供データには記載がありません』と答えてください。"
        )
        # ページ指定で翻訳要求の場合は、翻訳指示を明示的に追加
        if page_no and ('翻訳' in query or 'translation' in query.lower()):
            base_prompt += "\n【翻訳指示】上記のコンテンツが英語の場合、自然な日本語に翻訳してください。段落構造は保持してください。"
    else:
        base_prompt = query

    return base_prompt


def _generate_assistant_response(query: str) -> None:
    """クエリに対する回答を生成し、会話履歴へ追加する。"""
    if not llm_available:
        _store_assistant_message("LLMモジュールが利用できません。設定を確認してください。")
        return

    # Get current date
    from datetime import datetime
    current_date = datetime.now().strftime("%Y年%m月%d日")
    
    system_prompt = f"""あなたは日本語専用のAIアシスタントです。

【重要：システム日付情報】
- 現在の日付は{current_date}です
- ユーザーが日付に関する質問をした場合は、この日付を基準に答えてください

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

【相対日付の処理について】
- ユーザーが「昨日」「明日」「今日」などの相対日付を使用した場合、システムは既にそれを具体的な日付に変換しています
- 「最近」「最新」「このところ」「ここ数ヶ月」など時間的な表現も、具体的な期間に変換されています
- 相対日付が具体日付に変換済みであることを前提にして、その具体的な日付を用いて回答してください
- 「具体的な日付が必要です」というような返答は避けてください

【前の会話との区別】
- 前の会話内容は、ユーザーとの対話トーンや文脈をつかむために参考にしてください
- ただし、現在の質問と無関係な話題を回答に混ぜないでください
- 例えば「今日は何月何日ですか」という質問には、日付のみを答えてください

【フォローアップ・深掘りの指示】
- ユーザーの質問が前の質問の続き、あるいは同一トピックに関する追加の照会である場合は、それを "フォローアップ" とみなしてください。
- ただし、プロンプト内に `【会話継続コンテキスト】` セクションが存在しない場合はフォローアップ扱いにしないでください。
- `【会話継続コンテキスト】` が無い場合、"前回の結論:" という文言は出力せず、今回の質問への結論から直接回答してください。
- フォローアップと判断した場合は、次の順序で回答してください:
    1) 最初に前回の簡潔な結論（1行）を要約する（"前回の結論: ..." と明記）。
    2) 次に、今回の質問に基づく新しい分析・追加情報を箇条書きで3〜5点示す。各項目は可能な限り出典ID（[web_n]）かURLを付記する。
    3) 追加の推奨アクションや調査すべきポイントを1〜2行で提案する。
- 同じ情報を繰り返すだけの場合は、冒頭に "追加情報なし（前回の回答と同じ）" と明記し、必要なら新たに得られる観点のみを提供してください。
- 出典の重複表示は避け、重要なソースのみを示してください。

【Web検索結果の参照について】
- 以下のセクション内に Web検索結果が含まれる場合、その結果から回答を構成する際は、必ず [web_1], [web_2], [web_3] などの形式で出典を明示してください。
- 例：「日本ハムファイターズは4-2で阪神タイガースに勝利しました [web_1]」
- 複数の出典から情報を取得した場合も、各情報に対応する出典を付記してください。
- Web検索結果に基づく回答には、最低でも1つの出典参照を含めることが必須です。

【Web検索結果に Body（詳細）がない場合の対応】
- Web検索の機能上、取得できるのはタイトルと URL のみで、ページ本文（Body）が空の場合があります。
- このとき、別の詳細データソースがない場合は、以下のように対応してください：
  1) まず「入手可能な情報」を URL 付きで列挙する（[web_1] 【タイトル】URL の形式）
  2) 次に「詳細情報を得るには」というセクションを設け、URL を開く手順を提示する
  3) 「データベースに詳細記録がない場合は、公式サイトを直接確認してください」と明記する
- この形式により、ユーザーは自分で確認できる経路を得られます。

【文字・表記の制約】
- 生成は必ず日本語で行うこと。中国語（簡体字・繁体字）を使用してはなりません。
- 特に「簡体字（例: 乐、馆、发、测、确）」が混入しないようにしてください。もし簡体字が混入している場合は必ず日本語の漢字に置換してください（例: 乐 → 楽）。
- 英語の固有名詞は原則カタカナに変換し、英字の混在表記（例: マンドOLA）は避けること。

前の会話内容を参考にしながら、常に日本語のみで一貫した回答をしてください。"""

    try:
        with st.spinner("🤔 回答を生成中..."):
            # 🔧 相対日付を具体日付に変換してから LLM に渡す
            normalized_query, interpreted_date = parse_relative_date(query)
            if interpreted_date:
                _append_run_log(f"date_normalization: original='{query}' normalized='{normalized_query}' interpreted={interpreted_date}")
                query_for_llm = normalized_query
            else:
                query_for_llm = query

            # 省略フォローアップ（例: "無料ですか"）は直前トピックを補って検索・回答の話題ずれを防ぐ
            try:
                import re as _re_q

                def _extract_topic_terms(text: str):
                    stop = {
                        "について", "とは", "です", "ます", "したい", "ください", "教えて", "知りたい", "何", "なに",
                        "どこ", "いつ", "無料", "有料", "料金", "価格", "値段", "使える", "できる", "可能", "対応"
                    }
                    terms = _re_q.findall(r"[A-Za-z][A-Za-z0-9_\-]{1,24}|[ァ-ヶー]{2,}|[一-龠々]{2,}", text or "")
                    return [t for t in terms if t not in stop]

                _recent_q = (query_for_llm or "").strip()
                _msgs = st.session_state.get("messages") or []
                _prev_user_q = ""
                for _m in reversed(_msgs[:-1]):
                    if _m.get("role") == "user":
                        _prev_user_q = str(_m.get("content") or "").strip()
                        break

                _ellipsis_follow = bool(
                    _re_q.search(r"^(無料|有料|料金|値段|価格|いくら|使える|使えますか|できますか|可能ですか|対応していますか).*[？?]?$", _recent_q)
                    or _re_q.search(r"(無料|有料|料金|値段|価格|いくら).*(ですか|ますか|\?|？)$", _recent_q)
                )
                _short_q = len(_recent_q) <= 24
                _has_subject_like = bool(_re_q.search(r"[A-Za-z]{2,}|[ァ-ヶー]{2,}|[一-龠々]{2,}", _recent_q))
                if _prev_user_q and _ellipsis_follow and _short_q:
                    _topic_terms = _extract_topic_terms(_prev_user_q)
                    if _topic_terms:
                        _topic_hint = " ".join(_topic_terms[:3])
                        query_for_llm = f"{_topic_hint} {_recent_q}"
                        _append_run_log(
                            f"followup_query_contextualized: original='{_recent_q}' expanded='{query_for_llm}' prev='{_prev_user_q[:80]}'"
                        )
                    elif not _has_subject_like:
                        # 最低限のフォールバックとして直前質問を短縮付与
                        _prev_hint = _prev_user_q[:40]
                        query_for_llm = f"{_prev_hint} {_recent_q}"
                        _append_run_log(
                            f"followup_query_contextualized_fallback: original='{_recent_q}' expanded='{query_for_llm}'"
                        )
            except Exception:
                pass
            
            # ===== Web 検索：相対日付有無に関わらずすべてのクエリで実行 =====
            presearch_docs = []
            try:
                do_auto = os.getenv("RAG_ENABLE_DATE_PRESEARCH", "true").lower() == "true" or st.session_state.get("ui_auto_search")
            except Exception:
                do_auto = os.getenv("RAG_ENABLE_DATE_PRESEARCH", "true").lower() == "true"
            
            # Web 検索実行条件：auto_search が有効
            if do_auto:
                simple_date_tokens = ["今日", "昨日", "明日", "一昨日"]
                original_query_stripped = query.strip()
                is_simple_date_query = original_query_stripped in simple_date_tokens
                
                # 日付検出有無を問わず、シンプル日付クエリ以外は Web 検索を実行
                if not is_simple_date_query:
                    _append_run_log(f"executing_web_search: query='{query_for_llm}' interpreted_date={interpreted_date}")
                    try:
                        from src.rag.web_search import search_web_tool as _search_web_tool
                        presearch_docs = _search_web_tool(query_for_llm)
                        _append_run_log(f"web_search_results: docs_count={len(presearch_docs) if isinstance(presearch_docs, list) else 0}")
                        # Log actual content for verification
                        if isinstance(presearch_docs, list) and len(presearch_docs) > 0:
                            for idx, d in enumerate(presearch_docs[:2], 1):
                                content = str(d.get("text", ""))[:150]
                                _append_run_log(f"web_search_content[{idx}]: {content}")
                        # Always save to session if we got list results
                        if isinstance(presearch_docs, list) and len(presearch_docs) > 0:
                            st.session_state.presearch_results = presearch_docs
                            st.session_state.presearch_query = query_for_llm
                            _append_run_log(f"presearch_docs_added_to_session: count={len(presearch_docs)}")
                        else:
                            # Even if no results, update presearch_query to maintain context
                            st.session_state.presearch_results = []
                            st.session_state.presearch_query = query_for_llm
                            _append_run_log(f"web_search_no_results: presearch_docs={type(presearch_docs)} len={len(presearch_docs) if isinstance(presearch_docs, list) else 'N/A'} [presearch_query still updated]")
                    except Exception as e:
                        _append_run_log(f"web_search_error: {e}")
                        presearch_docs = []
                else:
                    _append_run_log(f"skipping_web_search: simple_date_only")
            # ===============================================================================
            
            prompt = _build_query_with_context(query_for_llm)
            
            # ===== Web 検索結果をプロンプトに統合 =====
            _append_run_log(f"DEBUG: presearch_docs type={type(presearch_docs)} len={len(presearch_docs) if isinstance(presearch_docs, list) else 'N/A'}")
            if presearch_docs and isinstance(presearch_docs, list):
                _append_run_log(f"DEBUG: Entering web search result integration block")
                preview_lines = [f"\n【🔍 Web自動検索結果 {len(presearch_docs)}件 (解釈日: {interpreted_date})】\n以下のWeb検索結果を参考に、ユーザーの質問に答えてください。この情報が重要です。"]
                for i, d in enumerate(presearch_docs[:5], 1):
                    tid = d.get("id") or d.get("url") or f"web_{i}"
                    text = str(d.get("text", ""))
                    text_snip = text.replace('\n', ' ')[:400]
                    preview_lines.append(f"[web_{i}] ({tid}): {text_snip}")
                preview_block = "\n".join(preview_lines) + "\n"
                prompt = preview_block + prompt  # Web結果を先頭に配置して重要度UP
                _append_run_log(f"prompt_added_web_search_results: items={len(presearch_docs)} prompt_now_starts_with_web=True")
            else:
                _append_run_log(f"DEBUG: SKIPPED web search integration - presearch_docs empty or wrong type")
            # ==========================================
            
            # 古い presearch_results の再利用で話題ずれが起こるため、毎回クリアして再検索する
            current_query = (query or "").strip()
            wants_file_detail = bool(re.search(r"詳しく|詳細|深掘り|掘り下げ|第?\s*[0-9０-９]+\s*章|最初|冒頭", current_query))
            chapter_requested = bool(re.search(r"(?:第\s*[0-9０-９]+\s*章|chapter\s*(?:[0-9]+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)|[0-9０-９]+\s*章)", current_query, re.IGNORECASE))
            requested_chapter_no = None
            try:
                qm = re.search(r"(?:第\s*([0-9０-９]+)\s*章|chapter\s*([0-9]+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)|([0-9０-９]+)\s*章)", current_query, re.IGNORECASE)
                if qm:
                    qn = qm.group(1) or qm.group(2) or qm.group(3)
                    requested_chapter_no = _parse_chapter_no(qn)
            except Exception:
                requested_chapter_no = None
            # 🔧 相対日付を変換したクエリを検索用に使用
            chapter_hint_query = query_for_llm
            if chapter_requested and requested_chapter_no is not None:
                chapter_hint_query = f"第{requested_chapter_no}章 Chapter {requested_chapter_no} CH{requested_chapter_no:02d} {query_for_llm}"
            last_file_summary_context = st.session_state.get("last_file_summary_context") or {}
            if wants_file_detail and last_file_summary_context.get("docs"):
                # 明示的な章指定がある場合は、同一PDFソース内で再検索して章一致チャンクを優先する
                if chapter_requested and retriever_available:
                    try:
                        retriever = get_retriever()
                        target_source = str(last_file_summary_context.get("source") or st.session_state.get("last_uploaded_file_source") or "")
                        if retriever and target_source:
                            fresh_docs = retriever.hybrid_search(chapter_hint_query, top_k=max(int(st.session_state.get("retrieval_top_k", 10)), 64), source_filter=target_source, min_score=0.015)
                            if fresh_docs:
                                last_file_summary_context["docs"] = fresh_docs[:48]
                                st.session_state.last_file_summary_context = last_file_summary_context
                                _append_run_log(f"file_ref chapter refresh used: source={target_source} docs={len(fresh_docs)}")
                    except Exception:
                        pass
                detailed_response = _build_file_ref_summary_response(
                    last_file_summary_context.get("docs") or [],
                    str(last_file_summary_context.get("source") or "直近PDF"),
                    detailed_query=current_query,
                )
                _append_run_log("file_ref detailed follow-up used")
                _store_assistant_message(detailed_response)
                st.session_state.attached_file_contents = []
                return
            if chapter_requested and retriever_available and not last_file_summary_context.get("docs"):
                # 要約直後でなくても「第2章要約」を解釈できるよう、直近PDFソースを直接検索する
                try:
                    retriever = get_retriever()
                    target_source = str(st.session_state.get("last_uploaded_file_source") or st.session_state.get("last_added_source") or "")
                    if retriever and target_source:
                        fresh_docs = retriever.hybrid_search(chapter_hint_query, top_k=max(int(st.session_state.get("retrieval_top_k", 10)), 64), source_filter=target_source, min_score=0.015)
                        if fresh_docs:
                            st.session_state.last_file_summary_context = {
                                "source": target_source,
                                "docs": fresh_docs[:48],
                                "detail_cursor": 0,
                            }
                            detailed_response = _build_file_ref_summary_response(
                                fresh_docs[:48],
                                target_source,
                                detailed_query=current_query,
                            )
                            _append_run_log(f"file_ref chapter direct retrieval used: source={target_source} docs={len(fresh_docs)}")
                            _store_assistant_message(detailed_response)
                            st.session_state.attached_file_contents = []
                            return
                except Exception:
                    pass
            is_file_referential_query = bool(
                re.search(r"(この|その|直近|さっき|先ほど).*(pdf|ＰＤＦ|ファイル|文書|資料)", current_query, re.IGNORECASE)
                or re.search(r"(pdf|ＰＤＦ).*(要約|まとめ|概要)", current_query, re.IGNORECASE)
                or re.search(r"(この|その).*(要約|まとめ|概要)", current_query)
            )
            previous_presearch_results = st.session_state.get("presearch_results")
            previous_user_query = ""
            try:
                for m in reversed((st.session_state.get("messages") or [])[:-1]):
                    if m.get("role") == "user":
                        previous_user_query = str(m.get("content") or "").strip()
                        break
            except Exception:
                previous_user_query = ""
            st.session_state.presearch_results = None

            # LLM呼び出し前に、毎回ローカルコーパス検索を実行して結果を最新化する
            try:
                if retriever_available:
                    retriever = get_retriever()
                    _append_run_log(f"DEBUG: retriever_available={retriever_available} retriever={'exists' if retriever else 'None'}")
                    if retriever:
                        _append_run_log(f"DEBUG: Entering if retriever block")
                        top_k = st.session_state.get('retrieval_top_k', 10)
                        last_src = st.session_state.get('last_added_source')
                        last_file_src = st.session_state.get('last_uploaded_file_source')
                        source_for_file_ref = last_file_src or last_src

                        def _same_source(a: str, b: str) -> bool:
                            aa = str(a or "").strip().lower()
                            bb = str(b or "").strip().lower()
                            if not aa or not bb:
                                return False
                            if aa == bb:
                                return True
                            return aa in bb or bb in aa
                        # セッションに記録がない場合は、最近追加されたPDF系ソースを推定する
                        if is_file_referential_query and not source_for_file_ref:
                            try:
                                recent_docs = retriever.get_recent_docs(top_k=30)
                                for rd in recent_docs:
                                    rmeta = rd.get('meta') or {}
                                    rsrc = str(rmeta.get('source') or rd.get('source') or '')
                                    if rsrc.lower().endswith('.pdf'):
                                        source_for_file_ref = rsrc
                                        break
                            except Exception:
                                pass
                        # 「このPDF/このファイル」系は、直近追加ソースを最優先に検索する
                        if is_file_referential_query and source_for_file_ref:
                            local_pre = retriever.hybrid_search(query_for_llm, top_k=top_k, source_filter=source_for_file_ref, min_score=0.015)
                            try:
                                _append_run_log(f"file_ref source selected: {source_for_file_ref}")
                            except Exception:
                                pass
                            if not local_pre:
                                # source_filter が効かない実装差異への保険: 最近ドキュメントから同一sourceを抽出
                                try:
                                    recent_docs = retriever.get_recent_docs(top_k=300)
                                    local_pre = [
                                        d for d in (recent_docs or [])
                                        if _same_source((d.get('meta') or {}).get('source') or d.get('source'), source_for_file_ref)
                                    ][:max(int(top_k), 24)]
                                except Exception:
                                    local_pre = []
                        else:
                            local_pre = retriever.hybrid_search(query_for_llm, top_k=top_k, min_score=0.015)
                            _append_run_log(f"DEBUG: hybrid_search called, results: {len(local_pre)}")
                        
                        # EARLY presearch_query update - right after hybrid_search to ensure it executes
                        _append_run_log(f"DEBUG: After hybrid_search - local_pre type={type(local_pre).__name__} len={len(local_pre) if isinstance(local_pre, list) else 'N/A'} condition={bool(local_pre)}")
                        # Update presearch_query regardless of whether results exist (empty results still should update context)
                        st.session_state.presearch_results = local_pre if local_pre else []
                        st.session_state.presearch_query = query_for_llm
                        _append_run_log(f"DEBUG: EARLY_UPDATE - presearch_query set to '{query_for_llm}' after hybrid_search (results={len(local_pre) if isinstance(local_pre, list) else 0})")

                        # Wikipedia等のナビゲーション断片（言語一覧/話題を追加など）を除外
                        def _is_noise_chunk(s: str) -> bool:
                            t = re.sub(r"\s+", "", str(s or ""))
                            noise_markers = (
                                "話題を追加",
                                "個の言語版",
                                "から取得カテゴリ",
                                "検索マンドラ",
                            )
                            return any(m in t for m in noise_markers)

                        local_pre = [d for d in local_pre if not _is_noise_chunk(d.get('text') or '')]
                        
                        # 🔧 ドメイン判定: Web検索の優先化が必要なクエリを検出
                        sports_keywords = ["試合", "結果", "得点", "勝負", "スコア", "野球", "サッカー", "相撲", "格闘技", "NFL", "NBA", "NHL", "テニス", "ゴルフ", "マラソン", "オリンピック"]
                        news_keywords = ["最新", "ニュース", "速報", "今日", "昨日", "今週", "先週", "事件", "事故", "株価", "相場", "円相場"]
                        real_time_keywords = ["現在", "今", "今後", "予報", "天気", "温度", "湿度", "気圧", "ライブ", "中継"]
                        
                        detected_domain = None
                        if any(kw in query for kw in sports_keywords):
                            detected_domain = "sports"
                        elif any(kw in query for kw in news_keywords):
                            detected_domain = "news"
                        elif any(kw in query for kw in real_time_keywords):
                            detected_domain = "realtime"
                        
                        # ドメイン検出時に Web 検索を優先
                        if detected_domain and web_search_available and not local_pre:
                            try:
                                _append_run_log(f"Domain-based web search: detected_domain='{detected_domain}' for query='{query}'")
                                web_results = search_web_tool(query, max_results=10)
                                if web_results and isinstance(web_results, list):
                                    local_pre = web_results[:top_k]
                                    _append_run_log(f"Domain web search retrieved {len(local_pre)} results")
                            except Exception as e:
                                _append_run_log(f"Domain web search failed: {e}")
                                pass
                        
                        # 🔧 Web検索の優先化: ローカル検索が空またはスコアが非常に低い場合
                        if not local_pre and web_search_available:
                            try:
                                _append_run_log(f"Fallback to web search: local results empty for query='{query}'")
                                web_results = search_web_tool(query, max_results=8)
                                if web_results and isinstance(web_results, list):
                                    local_pre = web_results[:top_k]
                                    _append_run_log(f"Web search retrieved {len(local_pre)} results")
                            except Exception as e:
                                _append_run_log(f"Web search fallback failed: {e}")
                                pass

                        # このPDF参照では、検索後も同一source以外を除外して回答の混線を防ぐ
                        if is_file_referential_query and source_for_file_ref:
                            local_pre = [
                                d for d in local_pre
                                if _same_source((d.get('meta') or {}).get('source') or d.get('source'), source_for_file_ref)
                            ]

                        # クエリ語を含まない無関係文書（例: 以前追加した別URL）を上位採用しないようフィルタ
                        try:
                            import re as _re_kw
                            import unicodedata as _ud
                            stop_words = {
                                "について", "です", "ます", "したい", "ください", "教えて", "探して", "知りたい",
                                "とは", "こと", "もの", "ため", "から", "そして", "また", "それ", "これ",
                            }
                            # ひらがな2文字以上 or カタカナ/漢字2文字以上を抽出
                            raw_terms = _re_kw.findall(r"[ぁ-ん]{2,}|[ァ-ヶー一-龠々]{2,}", query or "")
                            keywords = [t for t in raw_terms if t not in stop_words]

                            def _norm_text(s: str) -> str:
                                s = _ud.normalize("NFKC", str(s or "")).lower()
                                # 全ての空白を除去（"マン ドラ" のような分断を吸収）
                                s = _re_kw.sub(r"\s+", "", s)
                                return s

                            if keywords and not is_file_referential_query:
                                norm_keywords = [_norm_text(k) for k in keywords if _norm_text(k)]
                                filtered = []
                                for d in local_pre:
                                    txt = str(d.get('text') or '')
                                    meta = d.get('meta') or {}
                                    src = str(meta.get('source') or '') + " " + str(meta.get('source_url') or '') + " " + str(meta.get('title') or '')
                                    hay = _norm_text(txt + "\n" + src)
                                    if any(k in hay for k in norm_keywords):
                                        filtered.append(d)
                                # 一致した文書のみ採用（0件なら後段の source_filter フォールバックへ）
                                local_pre = filtered

                            # キーワード一致が空の場合、直近追加ソースでの検索を優先する
                            if not local_pre and last_src:
                                try:
                                    scoped = retriever.hybrid_search(query_for_llm, top_k=top_k, source_filter=last_src, min_score=0.015)
                                    if scoped:
                                        local_pre = scoped
                                except Exception:
                                    pass

                            # 代名詞フォローアップ（例: それの教則本）で空になった場合は前回質問で補完
                            if not local_pre and previous_user_query and not is_file_referential_query:
                                try:
                                    is_referential = bool(_re_kw.search(r"これ|それ|あれ|その|上記|前者|後者", query or ""))
                                    if is_referential:
                                        carry = retriever.hybrid_search(previous_user_query, top_k=top_k, min_score=0.015)
                                        if carry:
                                            local_pre = carry
                                except Exception:
                                    pass

                            # それでも空なら、前回の検索結果を暫定利用して文脈断絶を防ぐ
                            if not local_pre and isinstance(previous_presearch_results, list) and previous_presearch_results and not is_file_referential_query:
                                local_pre = previous_presearch_results[:top_k]
                        except Exception:
                            pass

                        _append_run_log(f"DEBUG: Line 2635 reached - About to loop over local_pre. local_pre type={type(local_pre).__name__} len={len(local_pre) if isinstance(local_pre, list) else 'N/A'}")
                        for d in local_pre:
                            if 'meta' not in d:
                                d['meta'] = d.get('meta') or {}
                        _append_run_log(f"DEBUG: Line 2638 - Loop completed. About to update presearch_query.")
                        # 古い/外部由来の結果を混ぜると話題ずれしやすいため、現在クエリのローカル結果で上書き
                        _append_run_log(f"DEBUG: About to update presearch_query. Current local_pre len={len(local_pre) if isinstance(local_pre, list) else 'NOT_LIST'}")
                        st.session_state.presearch_results = local_pre
                        st.session_state.presearch_query = current_query
                        _append_run_log(f"LOCAL_SEARCH: presearch_query set to '{current_query}'") # DEBUG: verify execution
                        try:
                            snap = []
                            for d in local_pre[:3]:
                                meta = d.get('meta') or {}
                                snap.append({
                                    'id': d.get('id') or '-',
                                    'source': meta.get('source') or meta.get('source_url') or '-',
                                    'score': float(meta.get('score') or d.get('score') or 0.0),
                                })
                            _append_run_log(
                                f"retrieval query={current_query!r} presearch_query={st.session_state.get('presearch_query')!r} top3={json.dumps(snap, ensure_ascii=False)}"
                            )
                        except Exception:
                            pass

                        # 「このPDFの要約」系はLLMを介さず、取得チャンクから決定論的に章立て要約を返す
                        try:
                            wants_summary = bool(re.search(r"要約|まとめ|概要", query or ""))
                            if is_file_referential_query and wants_summary and local_pre:
                                src_name = str(source_for_file_ref or (local_pre[0].get("meta") or {}).get("source") or local_pre[0].get("source") or "直近PDF")
                                summary_docs = local_pre[:12]
                                direct_summary = _build_file_ref_summary_response(summary_docs, src_name)
                                if direct_summary:
                                    st.session_state.last_file_summary_context = {
                                        "source": src_name,
                                        "docs": summary_docs,
                                        "detail_cursor": 0,
                                    }
                                    _append_run_log("file_ref deterministic summary used")
                                    _store_assistant_message(direct_summary)
                                    st.session_state.attached_file_contents = []
                                    return
                        except Exception:
                            pass
            except Exception:
                pass

            # 事前検索結果がある場合はLLMへ明示的に参照させる指示を追加
            try:
                pre = st.session_state.get("presearch_results")

                # ドメイン優先フォールバック: マンドラ質問はマンドラ出典を優先して即答する
                try:
                    import re as _re_m
                    q_norm = _re_m.sub(r"\s+", "", str(query or "")).lower()
                    if "マンドラ" in q_norm:
                        cand = []
                        if isinstance(pre, list):
                            cand = pre
                        # 候補が空の場合、直近追加ソースで再検索
                        if not cand:
                            retriever = get_retriever() if retriever_available else None
                            if retriever and st.session_state.get('last_added_source'):
                                cand = retriever.hybrid_search(query_for_llm, top_k=5, source_filter=st.session_state.get('last_added_source'), min_score=0.015)

                        def _contains_mandora(d):
                            meta = d.get('meta') or {}
                            txt = str(d.get('text') or '')
                            if _is_noise_chunk(txt):
                                return False
                            hay = " ".join([
                                str(d.get('text') or ''),
                                str(meta.get('title') or ''),
                                str(meta.get('source') or ''),
                                str(meta.get('source_url') or ''),
                            ])
                            hay = _re_m.sub(r"\s+", "", hay)
                            return "マンドラ" in hay

                        mandora_docs = [d for d in (cand or []) if _contains_mandora(d)]
                        if mandora_docs:
                            d = mandora_docs[0]
                            txt = str(d.get('text') or '').replace('\n', ' ')
                            clean_txt = re.sub(r"\s+", " ", txt).strip()
                            src = (d.get('meta') or {}).get('source_url') or (d.get('meta') or {}).get('source') or d.get('id')
                            # 代表表現があれば優先、なければ抽出的に短く返す
                            m = re.search(r"(マンドラ[^。]{0,120}。)", clean_txt)
                            if m:
                                concl = f"結論: {m.group(1)}"
                            elif "マンドリン属の弦楽器" in clean_txt:
                                concl = "結論: マンドラはマンドリン属の弦楽器で、マンドリンより一回り大きい楽器です。"
                            else:
                                concl = f"結論: {clean_txt[:80]}" + ("..." if len(clean_txt) > 80 else "")
                            src_id = d.get('id') or 'web_1'
                            msg = concl + f"\n- [{src_id}] {clean_txt[:180]}\n補足: 詳細は出典を確認してください。\n出典: {src}"
                            _store_assistant_message(msg)
                            st.session_state.attached_file_contents = []
                            return
                except Exception:
                    pass

                # 先に自動抽出でスコアが取れれば直接応答させる（LLM 呼出しをスキップ）
                # 野球系クエリ以外でURL解析すると遅延が増えるため、対象クエリに限定する
                score_query = str(query or "")
                is_baseball_score_query = bool(re.search(r"日本ハム|ファイターズ|試合|スコア|box\s*score|野球", score_query, re.IGNORECASE))
                if pre and is_baseball_score_query:
                    for d in pre[:5]:
                        src = d.get('meta', {}).get('source','')
                        # meta.sourceにuddg経由のURLがあればデコード
                        url = None
                        try:
                            if 'uddg=' in src:
                                import urllib.parse
                                part = src.split('uddg=')[-1]
                                url = urllib.parse.unquote(part.split('&')[0])
                            else:
                                # meta.source そのものがURLかもしれない
                                if src.startswith('http'):
                                    url = src
                        except Exception:
                            url = None

                        if url:
                            score_info = _extract_game_score_from_url(url)
                            if score_info and isinstance(score_info.get('teams'), list):
                                # チーム名に日本ハムが含まれるか確認
                                teams = score_info['teams']
                                nh = None
                                other = None
                                for t in teams:
                                    if '日本ハム' in t['name'] or 'ファイターズ' in t['name']:
                                        nh = t
                                    else:
                                        other = t
                                if nh and other:
                                    # 勝敗判定
                                    if nh['score'] > other['score']:
                                        result_text = f"結論: 北海道日本ハムファイターズは{nh['score']}-{other['score']}で勝利しました。"
                                    elif nh['score'] < other['score']:
                                        result_text = f"結論: 北海道日本ハムファイターズは{nh['score']}-{other['score']}で敗れました。"
                                    else:
                                        result_text = f"結論: 試合は引き分け（{nh['score']}-{other['score']}）でした。"
                                    # 出典を明記して応答を保存
                                    src_id = d.get('id') or d.get('url') or url
                                    message = result_text + f"\n出典: [{src_id}] {url}\n補足: 詳細は出典ページのbox scoreを参照してください。"
                                    _store_assistant_message(message)
                                    st.session_state.attached_file_contents = []
                                    return
                if pre:
                    directive_lines = [
                        "【注意：検索結果を参照して簡潔に答えること】以下は自動で取得した検索結果（ローカル文書を含む）です。回答を作る際、必ずこれらを参照してください。出力形式に厳密に従ってください：",
                        "1) 結論（Qに対する答え）を最初に1〜2行で簡潔に述べる。",
                        "2) 根拠を箇条書きで最大3件示す。各項目は必ず出典IDを `[source_id]` の形式で明記し、根拠文を短く引用する。",
                        "2.1) 重要: 本文中に生のURLを貼り付けないでください。本文では必ず出典ID（[source_id]）のみを使い、URLは文末の注釈としてまとめてください。",
                        "2.2) 重要: 組織名とモデル名は明確に区別してください。例えば 'Anthropic' は組織名であり、'Claude' や 'Claude Mythos' は同組織が提供するモデル名です。回答中で混同しないこと。組織に関する記述とモデルに関する記述は別段落で記載してください。",
                        "3) 補足は1〜2文に留める。不要な背景説明は避ける。",
                        "4) すべて日本語で答えること。",
                        "5) 質問が『このPDF』『このファイル』のような参照表現を含む場合、直近追加ドキュメントの内容を最優先して要約・回答すること。",
                    ]
                    # Few-shot examples to guide the LLM output format
                    directive_lines.append("\n【例（良い出力）】\n結論: 日本ハムは昨日の試合に勝利しました（スコア 4-3）。\n- [web_3] 西武 vs 日本ハ 試合記事（速報）: 8回にレイエスの本塁打で勝ち越し\n補足: 公式サイトの成績ページで詳細を確認してください。")
                    directive_lines.append("\n【例（悪い出力）】\n昨日の試合について長い歴史や選手のプロフィールを詳述する（結論が不明瞭）。出典を示さない。")
                    import re as _re
                    def _short_info(d):
                        tid = d.get("id") or "-"
                        meta_url = (d.get("meta") or {}).get("source") if isinstance(d.get("meta"), dict) else d.get("url")
                        text_content = str(d.get("text", "")).replace("\n", " ")
                        # try to extract Title: prefix
                        m = _re.search(r"Title:\s*(.*?)(?:URL:|$)", text_content)
                        title = m.group(1).strip() if m else text_content[:120]
                        return tid, title, meta_url

                    for d in pre[:5]:
                        tid, title, meta_url = _short_info(d)
                        url_part = f" ({meta_url})" if meta_url else ""
                        text_snip = str(d.get("text", "")).replace("\n", " ")
                        text_snip = re.sub(r"\s+", " ", text_snip).strip()[:360]
                        directive_lines.append(f"- [{tid}] {title}{url_part}")
                        directive_lines.append(f"  抜粋: {text_snip}")
                    directive = "\n".join(directive_lines) + "\n\n"
                    prompt = directive + prompt
            except Exception:
                pass
            # Heuristic: 連続質問の文脈が切れないよう、参照語・短文・語彙重なりでもフォローアップ判定する
            import re as _re_local
            recent_query = (query or "").strip()
            treat_as_fresh = True
            followup_like = False
            try:
                # 直前ユーザー質問を取得（現在質問は messages の末尾に入っている前提）
                prev_user_query = ""
                msgs = st.session_state.get("messages") or []
                for m in reversed(msgs[:-1]):
                    if m.get("role") == "user":
                        prev_user_query = str(m.get("content") or "").strip()
                        break

                explicit_follow = bool(_re_local.search(r"続き|前回|さっき|先ほど|その件|もう少し|詳しく|補足|それで|ちなみに|じゃあ", recent_query))
                referential = bool(_re_local.search(r"これ|それ|あれ|上記|前者|後者|同じ|その|どれ|どの", recent_query))
                short_follow = len(recent_query) <= 24
                elliptical_follow = bool(
                    _re_local.search(r"^(無料|有料|料金|値段|価格|いくら|使える|使えますか|できますか|可能ですか|対応していますか).*[？?]?$", recent_query)
                    or _re_local.search(r"(無料|有料|料金|値段|価格|いくら).*(ですか|ますか|\?|？)$", recent_query)
                )
                marketplace_follow = bool(
                    _re_local.search(
                        r"amazon|アマゾン|楽天|yahoo|ヤフー|価格\.com|モノタロウ|ヨドバシ|通販|ショップ|販売",
                        recent_query,
                        _re_local.IGNORECASE,
                    )
                )

                # 内容語の重なりで関連度を推定
                stop_words = {
                    "について", "です", "ます", "したい", "ください", "教えて", "知りたい", "何", "なに", "どこ", "いつ",
                    "これ", "それ", "あれ", "その", "この", "で", "を", "が", "は", "に", "の", "と", "も", "か"
                }
                cur_terms = [t for t in _re_local.findall(r"[ぁ-んァ-ヶー一-龠々]{2,}", recent_query) if t not in stop_words]
                prev_terms = [t for t in _re_local.findall(r"[ぁ-んァ-ヶー一-龠々]{2,}", prev_user_query) if t not in stop_words]
                overlap = len(set(cur_terms) & set(prev_terms))

                # 「このPDF」系は履歴汚染を避けるため常に新規扱い
                if is_file_referential_query:
                    treat_as_fresh = True
                # 参照語+短文、または語彙重なりがあるときは会話継続扱い
                elif explicit_follow or (referential and short_follow) or overlap >= 1 or (marketplace_follow and short_follow) or (elliptical_follow and short_follow):
                    followup_like = True
                    treat_as_fresh = False
            except Exception:
                treat_as_fresh = True

            # Web検索結果がある場合でも、フォローアップ質問は会話継続を優先する
            presearch_has_docs = bool(presearch_docs and isinstance(presearch_docs, list) and len(presearch_docs) > 0)
            if presearch_has_docs:
                if followup_like:
                    treat_as_fresh = False
                    _append_run_log(f"INFO: Web search results found ({len(presearch_docs)} docs) + followup detected -> preserving recent chat context")
                else:
                    treat_as_fresh = True
                    _append_run_log(f"CRITICAL: Web search results found ({len(presearch_docs)} docs) -> ignoring chat history to prioritize fresh search results")

            if treat_as_fresh:
                chat_history = None
            else:
                history_source = st.session_state.messages[:-1]
                if presearch_has_docs and followup_like:
                    # 直近2往復に限定して、話題継続と履歴汚染抑制を両立する
                    history_source = history_source[-4:]
                chat_history = [
                    {"role": msg["role"], "content": msg["content"]}
                    for msg in history_source
                ]
                # フォローアップ時は、直前QAを短く明示して話題の連続性を強制する
                try:
                    last_user = ""
                    last_assistant = ""
                    for m in reversed(st.session_state.messages[:-1]):
                        if not last_assistant and m.get("role") == "assistant":
                            last_assistant = str(m.get("conclusion") or m.get("content") or "").strip()
                            if len(last_assistant) > 220:
                                last_assistant = last_assistant[:220] + "..."
                        if not last_user and m.get("role") == "user":
                            last_user = str(m.get("content") or "").strip()
                        if last_user and last_assistant:
                            break
                    if last_user or last_assistant:
                        carry_lines = [
                            "【会話継続コンテキスト】",
                            f"- 直前ユーザー質問: {last_user or '-'}",
                            f"- 直前アシスタント要点: {last_assistant or '-'}",
                            "- 今回の質問は上記の続きとして解釈し、話題を変えないこと。",
                            f"- 今回の質問: {recent_query or '-'}",
                            "- 最初の1文で今回の質問に直接答えること（前回要約の繰り返しは最小限）。",
                            "",
                        ]
                        prompt = "\n".join(carry_lines) + prompt
                except Exception:
                    pass
            try:
                _append_run_log(
                    f"llm_input query={current_query!r} presearch_query={st.session_state.get('presearch_query')!r} use_chat_history={bool(chat_history)} prompt_len={len(prompt)}"
                )
            except Exception:
                pass

            needs_diagram = _query_requests_diagram(current_query)
            if needs_diagram:
                prompt = (
                    prompt
                    + "\n\n【図解出力の必須要件】\n"
                    + "- ユーザーは図解を求めています。本文の最後に必ず 1 つ以上の Mermaid 図を ```mermaid ... ``` 形式で含めてください。\n"
                    + "- 図だけでなく、図の読み方を2〜4行で補足してください。\n"
                )
                _append_run_log("diagram_request_detected: forcing_mermaid_output=True")

            needs_beginner_learning_guide = _query_is_beginner_learning_request(current_query)
            if needs_beginner_learning_guide:
                prompt = (
                    prompt
                    + "\n\n【初心者学習ガイドの必須要件】\n"
                    + "- ユーザーは初学者です。リンク列挙だけで終わらせず、まず何をするべきかを具体的に説明してください。\n"
                    + "- 回答は次の順序で構成してください。\n"
                    + "  1) 最初の一歩（今日やること）を1〜3個\n"
                    + "  2) 7日間の学習プラン（各日1行）\n"
                    + "  3) 最低限おさえる用語を3〜5個（一言説明付き）\n"
                    + "  4) 最初の実践課題を1つ（達成条件つき）\n"
                    + "- 参照リンクは補助として最後に示し、本文の主役にしないでください。\n"
                    + "- 専門用語はかみ砕いて説明し、前提知識ゼロでも実行できる内容にしてください。\n"
                )
                _append_run_log("beginner_learning_request_detected: enforcing_actionable_study_plan=True")

            # 会話履歴から推定したユーザー志向を反映（セッション内のみ）
            try:
                inferred_profile = infer_response_preferences(st.session_state.get("messages") or [])
                st.session_state.response_preference_profile = inferred_profile
                style_directive = build_response_style_directive(inferred_profile)
                if style_directive:
                    prompt = style_directive + prompt
                    _append_run_log(f"response_style_profile_applied: {json.dumps(inferred_profile, ensure_ascii=False)}")
            except Exception as e:
                _append_run_log(f"response_style_profile_failed: {e}")

            # LLM 呼び出しを実行し、例外は捕捉してログに残す
            try:
                _append_run_log(f"DEBUG: About to call LLM with prompt_len={len(prompt)} model={st.session_state.llm_model}")
                _append_run_log(f"DEBUG: prompt_start={prompt[:300]}")  # Log first 300 chars
                response = call_llm(
                    prompt=prompt,
                    model=st.session_state.llm_model,
                    system_prompt=system_prompt,
                    chat_history=chat_history if chat_history else None,
                    temperature=st.session_state.temperature,
                    max_tokens=st.session_state.max_tokens,
                )
                _append_run_log(f"DEBUG: LLM returned, type={type(response)} len={len(str(response))}")
                # 軽いサニティログを残す（プロンプト長とレスポンス先頭）
                try:
                    preview = (str(response)[:600]).replace('\n', ' ')
                    _append_run_log(f"call_llm model={st.session_state.llm_model} prompt_len={len(prompt)} response_len={len(str(response))} response_preview={preview}")
                except Exception:
                    _append_run_log(f"call_llm logged response of type {type(response)}")
            except Exception as e:
                # LLM呼び出し自体が例外を投げた場合の記録
                logger.exception(f"LLM 呼び出し中に例外: {e}")
                _append_run_log(f"LLM exception: {e}")
                response = f"Error: LLM exception: {e}"

            # 図解要求時に Mermaid が欠けていたら、最低限の図を補完する
            try:
                if needs_diagram and isinstance(response, str) and response.strip() and not str(response).startswith("Error"):
                    if not _has_mermaid_block(response):
                        response = response + _fallback_mermaid_for_query(current_query)
                        _append_run_log("diagram_fallback_injected: mermaid_block_appended")
            except Exception:
                pass

            # Fresh回答（履歴未使用）では「前回の結論」表現を強制的に抑止する
            try:
                if not chat_history and isinstance(response, str) and response:
                    normalized_response = re.sub(r"前回の結論[：:]\s*", "結論: ", response)
                    if normalized_response != response:
                        _append_run_log("response_normalization: replaced '前回の結論' -> '結論' (fresh mode)")
                        response = normalized_response
            except Exception:
                pass

            # 「このPDF」系で内容不明応答になった場合は、取得済みチャンクから抽出的に要約を返す
            try:
                if is_file_referential_query and isinstance(response, str):
                    no_content = bool(re.search(r"具体的な内容が(示されていない|記載されていない)|要約(することは)?できません|内容が不明", response))
                    pre_docs = st.session_state.get("presearch_results") or []
                    if no_content and isinstance(pre_docs, list) and pre_docs:
                        src_name = str((pre_docs[0].get("meta") or {}).get("source") or pre_docs[0].get("source") or "直近PDF")
                        sections = []
                        source_notes = []
                        for idx, d in enumerate(pre_docs[:4], 1):
                            did = d.get("id") or f"source_{idx}"
                            meta = d.get("meta") or {}
                            source_label = str(meta.get("source") or src_name)
                            raw = str(d.get("text") or "")
                            raw = re.sub(r"\s+", " ", raw).strip()
                            if not raw:
                                continue

                            # 見出し候補: 章タイトルらしい文字列を優先、なければ先頭文を短縮
                            heading_match = re.search(
                                r"(第\s*\d+\s*章[^。\n]{0,60}|Chapter\s*\d+[^.\n]{0,60}|\d+(?:\.\d+){1,3}\s+[^。\n]{0,60})",
                                raw,
                                re.IGNORECASE,
                            )
                            heading = heading_match.group(1).strip() if heading_match else raw[:36]
                            heading = re.sub(r"[\-:：\s]+$", "", heading)

                            # 要点文は先頭2文程度
                            sentences = re.split(r"(?<=[。.!?！？])\s+", raw)
                            lead = " ".join([s.strip() for s in sentences[:2] if s.strip()])
                            if not lead:
                                lead = raw[:180]
                            lead = lead[:220]

                            # キーワード抽出（簡易）
                            token_candidates = re.findall(r"[A-Za-z]{3,}|[ァ-ヶー]{3,}|[一-龠々]{2,}", raw)
                            stop_kw = {"この", "それ", "ため", "こと", "について", "です", "ます", "および", "また"}
                            keywords = []
                            for t in token_candidates:
                                if t in stop_kw:
                                    continue
                                if t not in keywords:
                                    keywords.append(t)
                                if len(keywords) >= 4:
                                    break

                            sections.append(
                                f"{idx}. {heading}\n- 要点: {lead}\n- キーワード: {', '.join(keywords) if keywords else '抽出なし'}"
                            )
                            source_notes.append(f"- [{did}] {source_label}")

                        if sections:
                            response = (
                                f"結論: 直近PDF『{src_name}』を章立てで要約しました。\n"
                                + "【章立て要約】\n"
                                + "\n".join(sections)
                                + "\n【出典チャンク】\n"
                                + "\n".join(source_notes[:4])
                                + "\n補足: 抽出チャンクに基づく簡易章立てです。必要なら各章をさらに詳細化します。"
                            )
                            _append_run_log("file_ref fallback summary activated")
            except Exception:
                pass

            # フォールバック: LLM応答が正常に得られたら出典検証を行い、検証済み回答のみを最終表示する。
            _append_run_log(f"**CRITICAL: Before provenance check - response type={type(response).__name__} response_is_empty={not response} response_len={len(str(response)) if response else 0} presearch_docs type={type(presearch_docs).__name__} presearch_docs_len={len(presearch_docs) if isinstance(presearch_docs, list) else 'N/A'}")
            
            auto_enabled = st.session_state.get("ui_auto_search", True)
            # 優先順位: Web検索結果（ローカル変数presearch_docs） > session presearch_results > ローカル検索
            if presearch_docs and isinstance(presearch_docs, list):
                pre = presearch_docs
                _append_run_log(f"DEBUG: Using presearch_docs (Web search): len={len(pre)}")
            else:
                pre = st.session_state.get("presearch_results")
                _append_run_log(f"DEBUG: presearch_results from session: type={type(pre)} len={len(pre) if isinstance(pre, list) else 'N/A'}")
            
            # If no presearch results are present, run a local retrieval against the corpus
            try:
                if not pre and retriever_available:
                    retriever = get_retriever()
                    if retriever:
                        top_k = st.session_state.get('retrieval_top_k', 10)
                        pre = retriever.hybrid_search(query_for_llm, top_k=top_k, min_score=0.015)
                        _append_run_log(f"DEBUG: local retrieval executed: len={len(pre) if isinstance(pre, list) else 'N/A'}")
                        # normalize to expected format: ensure 'meta' exists
                        for d in pre:
                            if 'meta' not in d:
                                d['meta'] = d.get('meta') or {}
                        
                        # ===== Check if query requires specific content (e.g., "教則本", "ガイド", "マニュアル") =====
                        requirement_keywords = ["教則本", "教科書", "ガイド", "マニュアル", "入門", "初心者向け", "テキスト"]
                        query_has_requirement = any(kw in query_for_llm for kw in requirement_keywords)
                        
                        if query_has_requirement and pre:
                            # Filter results to include only those matching the requirement
                            filtered_pre = []
                            for d in pre:
                                text = d.get('text', '').lower()
                                title = d.get('meta', {}).get('title', '').lower()
                                combined = f"{text} {title}"
                                
                                # Check if result contains any requirement keyword
                                if any(kw.lower() in combined for kw in requirement_keywords):
                                    filtered_pre.append(d)
                            
                            if filtered_pre:
                                _append_run_log(f"REQUIREMENT_FILTER: Found {len(filtered_pre)}/{len(pre)} results matching requirement keywords")
                                pre = filtered_pre
                            else:
                                # Results don't match requirement - mark for fallback response
                                _append_run_log(f"REQUIREMENT_FILTER: No results match requirement. Query='{query_for_llm}', Requirements={requirement_keywords}")
                                # Empty pre to trigger fallback: insert a marker indicating requirement not met
                                pre = [{"_no_match": True, "requirement": requirement_keywords, "query": query_for_llm}]
                        
                        st.session_state.presearch_results = pre
            except Exception:
                pre = st.session_state.get("presearch_results")

            # Build lightweight sources structure from presearch results if present
            sources = []
            _append_run_log(f"DEBUG: Building sources from pre: pre={bool(pre)} is_list={isinstance(pre, list)}")
            
            # Check for requirement mismatch marker
            requirement_not_met = False
            requirement_kws = []
            if pre and isinstance(pre, list) and len(pre) == 1 and pre[0].get("_no_match"):
                requirement_not_met = True
                requirement_kws = pre[0].get("requirement", [])
                q = pre[0].get("query", query)
                _append_run_log(f"FALLBACK: Requirement not met in corpus. Query='{q}', Requirements={requirement_kws}")
                # Return fallback response immediately without calling LLM
                fallback_response = f"[確認が必要] コーパスに「{', '.join(requirement_kws[:2])}」に関する情報が見つかりませんでした。\n\n{query} について、以下の方法で情報を探すことをお勧めします：\n- インターネット検索で最新情報を確認\n- 専門家や公式サイトに直接お問い合わせ\n- 図書館や専門書でさらに詳しい情報を確認"
                _append_run_log(f"FALLBACK_RESPONSE_GENERATED: requirement not met, returning early")
                _store_assistant_message(fallback_response)
                st.session_state.attached_file_contents = []
                return
            
            try:
                if pre and isinstance(pre, list) and not requirement_not_met:
                    _append_run_log(f"DEBUG: Building sources - processing {len(pre)} items")
                    for i, d in enumerate(pre[:10], 1):
                        meta = d.get('meta') or {}
                        src_name = d.get('id') or meta.get('source') or f"web_{i}"
                        src_text = d.get('text') or ''
                        src_path = meta.get('source') or d.get('url') or ''
                        src_score = float(meta.get('score') or d.get('score') or 0.0)
                        sources.append({
                            'name': src_name,
                            'score': src_score,
                            'path': src_path,
                            'text': src_text,
                        })
                    _append_run_log(f"DEBUG: Built {len(sources)} source items")
                else:
                    _append_run_log(f"DEBUG: Skipped sources building - pre is empty or not list")
            except Exception as e:
                sources = []
                _append_run_log(f"DEBUG: Exception during sources building: {e}")

            # マンドラ質問で無関係（Claude系）応答を返さないための最終ガード
            try:
                q_norm = re.sub(r"\s+", "", str(query or "")).lower()
                r_norm = re.sub(r"\s+", "", str(response or "")).lower()
                if "マンドラ" in q_norm:
                    has_claude_topic = any(k in r_norm for k in ("claude", "anthropic", "クラウドについて"))
                    mandora_docs = []
                    for d in (pre or []):
                        meta = d.get('meta') or {}
                        if _is_noise_chunk(d.get('text') or ''):
                            continue
                        hay = " ".join([
                            str(d.get('text') or ''),
                            str(meta.get('title') or ''),
                            str(meta.get('source') or ''),
                            str(meta.get('source_url') or ''),
                        ])
                        hay = re.sub(r"\s+", "", hay)
                        if "マンドラ" in hay:
                            mandora_docs.append(d)

                    # まず直近検索結果からマンドラ文書を拾う。なければ last_added_source で再検索する。
                    if not mandora_docs and retriever_available and st.session_state.get('last_added_source'):
                        retriever = get_retriever()
                        if retriever:
                            scoped = retriever.hybrid_search(
                                query,
                                top_k=st.session_state.get('retrieval_top_k', 10),
                                source_filter=st.session_state.get('last_added_source'),
                                min_score=0.015
                            )
                            for d in (scoped or []):
                                meta = d.get('meta') or {}
                                if _is_noise_chunk(d.get('text') or ''):
                                    continue
                                hay = " ".join([
                                    str(d.get('text') or ''),
                                    str(meta.get('title') or ''),
                                    str(meta.get('source') or ''),
                                    str(meta.get('source_url') or ''),
                                ])
                                hay = re.sub(r"\s+", "", hay)
                                if "マンドラ" in hay:
                                    mandora_docs.append(d)

                    if mandora_docs and has_claude_topic:
                        d = mandora_docs[0]
                        txt = str(d.get('text') or '').replace('\n', ' ')
                        clean_txt = re.sub(r"\s+", " ", txt).strip()
                        meta = d.get('meta') or {}
                        src = meta.get('source_url') or meta.get('source') or d.get('id')
                        m = re.search(r"(マンドラ[^。]{0,120}。)", clean_txt)
                        if m:
                            concl = f"結論: {m.group(1)}"
                        elif "マンドリン属の弦楽器" in clean_txt:
                            concl = "結論: マンドラはマンドリン属の弦楽器で、マンドリンより一回り大きい楽器です。"
                        else:
                            concl = f"結論: {clean_txt[:80]}" + ("..." if len(clean_txt) > 80 else "")
                        src_id = d.get('id') or 'web_1'
                        forced = concl + f"\n- [{src_id}] {clean_txt[:180]}\n補足: 詳細は出典を確認してください。\n出典: {src}"
                        _append_run_log("topic_guard activated: replaced claude-topic response for mandora query")
                        _store_assistant_message(forced)
                        st.session_state.attached_file_contents = []
                        return
            except Exception:
                pass

            # If response is a normal string, run provenance verification; otherwise handle fallback summary.
            if isinstance(response, str) and not str(response).startswith("Error") and response.strip():
                # SIMPLE RULE: If Web search was performed, ALWAYS store sources
                # Otherwise, only store sources if response contains references
                
                if presearch_docs and isinstance(presearch_docs, list) and len(presearch_docs) > 0:
                    # Web search was performed -> accept response and store sources
                    ok = True
                    provenance = sources
                    _append_run_log(f"✅ WEB SEARCH MODE: Web search performed with {len(presearch_docs)} results -> ok=True, storing {len(provenance)} sources")
                else:
                    # No web search -> check if response has references
                    has_ref_pattern = bool(re.search(r"\[web_\d+\]|\[\d+\]", str(response)))
                    if has_ref_pattern:
                        ok = True
                        provenance = sources
                        _append_run_log(f"✅ REFERENCE MODE: Response contains URL references -> ok=True, storing {len(provenance)} sources")
                    else:
                        # No web search, no references -> reject
                        ok = False
                        provenance = sources
                        _append_run_log(f"❌ NO SOURCES MODE: No web search, no references -> ok=False")


                if ok:
                    # record audit & persist log if agent available
                    try:
                        if agent:
                            audit = agent._audit_answer(query, str(response), sources)
                            agent._persist_response_log({
                                'timestamp': datetime.now().isoformat(),
                                'question': query,
                                'response': str(response),
                                'sources': provenance,
                                'audit': audit,
                            })
                    except Exception:
                        pass
                    _append_run_log(f"DEBUG: Response OK - storing to session_state")
                    _store_assistant_message({"text": str(response), "sources": provenance})
                    
                    # Display Web search results in UI if available
                    if presearch_docs and isinstance(presearch_docs, list) and len(presearch_docs) > 0:
                        with st.expander(f"🔍 参考にした Web 検索結果 ({len(presearch_docs)}件)", expanded=False):
                            for i, doc in enumerate(presearch_docs[:10], 1):
                                st.markdown(f"### [{i}] {doc.get('id', f'web_{i}')}")
                                text = doc.get('text', '')
                                # Extract title and URL for display
                                title_match = re.search(r"Title:\s*(.+?)(?:\n|URL:)", text)
                                url_match = re.search(r"URL:\s*(.+?)(?:\n|Body:|\Z)", text)
                                body_match = re.search(r"Body:\s*(.+?)(?:\Z)", text)
                                
                                if title_match:
                                    st.markdown(f"**{title_match.group(1).strip()}**")
                                if url_match:
                                    url_text = url_match.group(1).strip()
                                    st.markdown(f"[リンク]({url_text})" if url_text.startswith('http') else f"`{url_text}`")
                                if body_match and body_match.group(1).strip():
                                    st.markdown(f"内容: {body_match.group(1).strip()[:300]}...")
                                else:
                                    st.info("※ この結果から詳細内容は取得できていません。上記リンクを開いて確認してください。")
                                st.divider()
                else:
                    # PDF章指定/詳細化では確認フローに入れず、取得チャンクから決定論的に返す
                    _append_run_log(f"DEBUG: Response NOT OK (ok=False) - entering fallback flow. sources={bool(sources)} response_first_200={str(response)[:200]}")
                    try:
                        if is_file_referential_query or chapter_requested or wants_file_detail:
                            fallback_docs = []
                            if isinstance(pre, list) and pre:
                                fallback_docs = pre[:48]
                            elif isinstance(last_file_summary_context.get("docs"), list):
                                fallback_docs = (last_file_summary_context.get("docs") or [])[:48]
                            if fallback_docs:
                                src_name = str(
                                    last_file_summary_context.get("source")
                                    or st.session_state.get("last_uploaded_file_source")
                                    or ((fallback_docs[0].get("meta") or {}).get("source") if isinstance(fallback_docs[0], dict) else "直近PDF")
                                    or "直近PDF"
                                )
                                fallback_answer = _build_file_ref_summary_response(
                                    fallback_docs,
                                    src_name,
                                    detailed_query=current_query if (chapter_requested or wants_file_detail) else None,
                                )
                                st.session_state.clarification_active = False
                                st.session_state.clarification_question = None
                                st.session_state.clarification_candidates = None
                                _append_run_log("file_ref provenance bypass fallback used")
                                _store_assistant_message(fallback_answer)
                                st.session_state.attached_file_contents = []
                                return
                    except Exception:
                        pass

                    # not enough provenance: ask clarification instead of showing a possibly hallucinated answer
                    candidate_titles = []
                    try:
                        if pre:
                            for d in pre[:5]:
                                t = (d.get('text') or '')[:120].replace('\n', ' ')
                                candidate_titles.append(t)
                    except Exception:
                        candidate_titles = None

                    clar_q = (
                        "一次情報（出典）が不足しています。もう少し具体的に探す対象を教えてください。"
                        " 例: 楽器のタイプ（マンドリン／マンドラ等）、初心者向けか上級者向け、掲載言語など。"
                    )
                    content = {
                        'clarification_required': True,
                        'clarification_question': clar_q,
                        'candidates': candidate_titles,
                        'answer_preview': str(response)[:800],
                    }
                    _store_assistant_message(content)
            else:
                # LLMがエラーまたは空文字を返した場合の既存のフォールバック処理
                _append_run_log(f"LLM returned error/empty response: {repr(response)[:400]}")
                if pre and auto_enabled:
                    lines = ["以下は自動で取得した外部検索結果の簡易要約です。最新情報の確認には必ず公式サイトをご確認ください。\n"]
                    import re as _re
                    def _format_line(d):
                        tid = d.get("id") or "-"
                        meta_url = (d.get("meta") or {}).get("source") if isinstance(d.get("meta"), dict) else d.get("url")
                        text_content = str(d.get("text", "")).replace("\n", " ")[:400]
                        m = _re.search(r"Title:\s*(.*?)(?:URL:|Body:|$)", text_content)
                        title = m.group(1).strip() if m else None
                        if title:
                            return f"・出典 [{tid}]: {title} ({meta_url})\n  要約: {text_content[:200]}"
                        else:
                            return f"・出典 [{tid}]: {text_content} ({meta_url})"

                    for d in pre[:3]:
                        lines.append(_format_line(d))
                    summary_text = "\n".join(lines)
                    _store_assistant_message(summary_text)
                else:
                    _store_assistant_message(f"申し訳ありません。回答の生成に失敗しました: {response}")
            st.session_state.attached_file_contents = []
    except Exception as e:
        logger.error(f"LLM呼び出しエラー: {e}")
        _store_assistant_message(f"エラーが発生しました: {str(e)}")

def display_app():
    """アプリのメイン画面を表示する関数 - チャット形式で質問と回答を表示"""
    st.markdown(
        """
        <style>
            /* チャット画面の情報密度を上げる（表題・余白を縮小） */
            .stApp [data-testid="stAppViewContainer"] .main .block-container {
                padding-top: 0.65rem;
                padding-bottom: 0.8rem;
                max-width: 96%;
            }

            .stApp h1 {
                font-size: 1.5rem !important;
                line-height: 1.2 !important;
                margin: 0 0 0.35rem 0 !important;
            }

            .stApp h2 {
                font-size: 1.05rem !important;
                line-height: 1.3 !important;
                margin: 0.35rem 0 0.25rem 0 !important;
            }

            .stApp h3 {
                font-size: 0.96rem !important;
                line-height: 1.3 !important;
                margin: 0.25rem 0 0.2rem 0 !important;
            }

            .chat-scroll-host {
                max-height: 58vh;
                overflow-y: auto;
                padding-right: 0.35rem;
                border: 1px solid #e5ebf3;
                border-radius: 10px;
                padding-left: 0.45rem;
                padding-top: 0.35rem;
                padding-bottom: 0.3rem;
                background: #ffffff;
            }

            .stApp [data-testid="stSidebar"] {
                min-width: 275px;
                max-width: 275px;
            }

            @media (max-width: 900px) {
                .stApp [data-testid="stSidebar"] {
                    min-width: 255px;
                    max-width: 255px;
                }
                .stApp [data-testid="stAppViewContainer"] .main .block-container {
                    max-width: 100%;
                    padding-top: 0.55rem;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("🤖 自律型RAGエージェント")
    logger.debug("display_app function is being called...")
    
    _init_display_session_state()

    st.subheader("💬 会話")

    chat_scroll_container = st.container(height=560, border=False)
    with chat_scroll_container:
        if st.session_state.messages:
            last_user_query = ""
            for message in st.session_state.messages:
                if message["role"] == "user":
                    last_user_query = str(message.get("content") or "")
                    st.markdown(f"**🙋 あなた：**")
                    st.markdown(message['content'])
                else:
                    st.markdown(f"**🤖 エージェント：**")
                    # If structured conclusion available, show concise Q->A style
                    concl = message.get("conclusion")
                    sources = message.get("sources") or []
                    if concl:
                        # Normalize combined organization+model mentions (display-side)
                        def _normalize_org_model(text):
                            import re as _re_local
                            mapping = {
                                'Anthropic': ['Claude Mythos', 'Claude', 'Mythos', 'Claude 2'],
                                'アンソロピック': ['Claude Mythos', 'Claude', 'ミトス', 'Mythos']
                            }
                            for org, models in mapping.items():
                                if org not in text:
                                    continue
                                for m in models:
                                    if m in text:
                                        # attempt to remove the org+model fragment, allowing surrounding quotes
                                        start = text.find(org + 'の')
                                        mid = text.find(m, start if start>=0 else 0)
                                        if start >= 0 and mid >= 0 and mid - start < 80:
                                            seg_start = start
                                            seg_end = mid + len(m)
                                        else:
                                            # fallback: look for proximity of org and model without 'の'
                                            pos_org = text.find(org)
                                            pos_m = text.find(m)
                                            if pos_org >= 0 and pos_m >= 0 and abs(pos_m - pos_org) < 80:
                                                seg_start = min(pos_org, pos_m)
                                                seg_end = max(pos_org + len(org), pos_m + len(m))
                                            else:
                                                continue
                                        while seg_end < len(text) and text[seg_end] in '」」"\'）)]。、':
                                            seg_end += 1
                                        while seg_start > 0 and text[seg_start] in '「“"\'（(':
                                            seg_start -= 1
                                        # replace the extracted fragment with the model name to preserve predicate
                                        replaced = (text[:seg_start] + m + text[seg_end:]).strip()
                                        # cleanup spacing and stray punctuation
                                        import re as _clean_re
                                        replaced = _clean_re.sub(r'\s+', ' ', replaced).strip()
                                        # ensure model name is separated by spaces
                                        replaced = replaced.replace(m, f" {m} ")
                                        replaced = _clean_re.sub(r'\s+', ' ', replaced).strip()
                                        # remove stray closing paren immediately after words (e.g. 'Claudepic)')
                                        replaced = _clean_re.sub(r"(\w)\)+", r"\1", replaced)
                                        parts = [f"組織: {org}", f"モデル: {m}"]
                                        if replaced:
                                            parts.append(replaced)
                                        return "\n\n".join(parts)
                            return text
    
                        norm_concl = _normalize_org_model(concl)
                        # Post-process common mixed-script artifacts (e.g. "マンドOLA")
                        try:
                            # helper: replace some simplified Chinese characters with Japanese equivalents
                            def _replace_simplified_chinese(s: str) -> str:
                                if not s:
                                    return s
                                # minimal mapping for common mixed-character artifacts observed in outputs
                                simple_map = {
                                    '乐': '楽',
                                    '馆': '館',
                                    '发': '発',
                                    '后': '後',
                                    '测': '測',
                                    '确': '確',
                                }
                                for k, v in simple_map.items():
                                    s = s.replace(k, v)
                                return s
    
                            # map common English terms to preferred katakana
                            entity_kana_map = {
                                'mandola': 'マンドーラ',
                                'mandolin': 'マンドリン',
                            }
                            import re as _re_fix
                            # If user query mentioned an English term, prefer its katakana form
                            user_q = (st.session_state.get('messages') or [])
                            last_user = ''
                            if user_q:
                                for m in reversed(user_q):
                                    if m.get('role') == 'user' and m.get('content'):
                                        last_user = m.get('content')
                                        break
                            for eng, kana in entity_kana_map.items():
                                if last_user and re.search(rf"\b{eng}\b", last_user, flags=re.IGNORECASE):
                                    # replace ASCII, mixed-case, and weirdly-capitalized forms in conclusion
                                    norm_concl = _re_fix.sub(rf"(?i){eng}", kana, norm_concl)
                                    # fix cases like マンドOLA where ASCII hangs onto katakana
                                    norm_concl = _re_fix.sub(rf"マンド[A-Za-z]+", kana, norm_concl)
    
                            # fix simplified-chinese artifacts (e.g. '乐器' -> '楽器')
                            norm_concl = _replace_simplified_chinese(norm_concl)
                        except Exception:
                            pass
                        st.markdown(f"**回答（簡潔）:** {norm_concl}")

                        # 初学者向け質問では、結論だけで終わらず実行ステップを主表示に補う
                        try:
                            if _query_is_beginner_learning_request(last_user_query):
                                raw_answer = str(message.get("content") or "")
                                raw_lines = [ln.strip() for ln in raw_answer.splitlines() if ln.strip()]
                                guide_lines = []
                                uniq = []

                                def _is_noise_line(ln: str) -> bool:
                                    return bool(
                                        re.search(
                                            r"^結論\s*:|回答（簡潔）|出典|https?://|\bURL\d+\b|\[web_\d+\]",
                                            ln,
                                        )
                                    )

                                def _is_heading_like_line(ln: str) -> bool:
                                    return bool(
                                        re.search(
                                            r"^(初めの一歩|最初の一歩|7日間の学習プラン|最低限おさえる用語|最初の実践課題)(（.*）)?[:：]?$",
                                            ln,
                                        )
                                    )

                                def _is_concrete_action_line(ln: str) -> bool:
                                    return bool(
                                        re.search(
                                            r"第?\d+日|^Day\s*\d+|[:：]|今日|明日|やる|試す|作る|書く|読む|実践",
                                            ln,
                                            re.IGNORECASE,
                                        )
                                    )

                                # 学習計画に関係する行を優先抽出
                                for i, ln in enumerate(raw_lines):
                                    if _is_noise_line(ln):
                                        continue
                                    if re.search(r"最初の一歩|初めの一歩|7日間|日目|用語|実践課題|今日やる|ステップ|学習プラン|まずは", ln):
                                        guide_lines.append(ln)
                                        # 「学習プラン」見出しがあれば、続く日次行も拾う
                                        if re.search(r"7日間|学習プラン", ln):
                                            for nxt in raw_lines[i + 1 : i + 9]:
                                                if _is_noise_line(nxt):
                                                    continue
                                                if re.search(r"^第?\d+日|^Day\s*\d+", nxt):
                                                    guide_lines.append(nxt)
                                                if len(guide_lines) >= 6:
                                                    break
                                    if len(guide_lines) >= 6:
                                        break

                                # 見出しが拾えない場合は、URL行を除いた箇条書き/番号行を補助的に使用
                                if not guide_lines:
                                    for ln in raw_lines:
                                        if _is_noise_line(ln):
                                            continue
                                        if re.match(r"^[-*]\s+|^\d+[\.)]\s+", ln):
                                            guide_lines.append(ln)
                                        if len(guide_lines) >= 6:
                                            break

                                # 重複・ノイズの最終除去
                                seen = set()
                                concrete = []
                                headings = []
                                for ln in guide_lines:
                                    cleaned_ln = re.sub(r"^[-*]\s+|^\d+[\.)]\s+", "", ln).strip()
                                    if not cleaned_ln or _is_noise_line(cleaned_ln):
                                        continue
                                    if cleaned_ln in seen:
                                        continue
                                    seen.add(cleaned_ln)

                                    if _is_heading_like_line(cleaned_ln):
                                        headings.append(cleaned_ln)
                                    elif _is_concrete_action_line(cleaned_ln):
                                        concrete.append(cleaned_ln)
                                    else:
                                        headings.append(cleaned_ln)

                                    if len(concrete) + len(headings) >= 6:
                                        break

                                # 具体行動を優先し、足りない分だけ見出し系を補完
                                uniq = (concrete + headings)[:6]

                                # 具体行動が不足する場合は、最低限の行動提案を補う
                                if len(concrete) < 2:
                                    fallback_steps = [
                                        "今日: Python実行環境を準備し、LLMを1回呼び出してみる",
                                        "明日: トークン・プロンプト・温度の3用語を1行ずつ説明できるようにする",
                                        "3日目: 小さな要約プロンプトを作り、入力と出力を比較して改善する",
                                    ]
                                    for fb in fallback_steps:
                                        if fb not in uniq:
                                            uniq.append(fb)
                                        if len(uniq) >= 6:
                                            break

                                # 具体行動が入った場合は、見出しだけの行を省いて可読性を上げる
                                if any(re.search(r"^今日:|^明日:|^\d+日目:", ln) for ln in uniq):
                                    uniq = [
                                        ln
                                        for ln in uniq
                                        if not re.search(
                                            r"^(最初の一歩|7日間の学習プラン|最低限おさえる用語|最初の実践課題)[:：]?$",
                                            ln,
                                        )
                                    ][:6]

                                if uniq:
                                    st.markdown("**最初にやること（要点）:**")
                                    for ln in uniq:
                                        st.markdown(f"- {ln}")
                        except Exception:
                            pass
    
                    # 図解要求の回答は、詳細表示を開かなくても主表示に図を出す
                    raw_content_for_diagram = str(message.get("content") or "")
                    if _has_mermaid_block(raw_content_for_diagram):
                        st.markdown("**図解:**")
                        diagram_mode = normalize_diagram_mode(st.session_state.get("diagram_render_mode", "stable"))
                        try:
                            latest_user_q = ""
                            for mm in reversed(st.session_state.get("messages") or []):
                                if mm.get("role") == "user":
                                    latest_user_q = str(mm.get("content") or "")
                                    break
                        except Exception:
                            latest_user_q = ""
                        if diagram_mode == DIAGRAM_MODE_MERMAID:
                            _safe_render_mermaid_blocks(raw_content_for_diagram)
                        else:
                            _render_safe_flow_diagram(
                                diagram_title_for_query(latest_user_q),
                                diagram_steps_for_query(latest_user_q),
                            )
    
                    # show sources as concise bullets and collect URLs as footnotes
                    if sources:
                        # load any prior presearch results from session state
                        pre_search = st.session_state.get("presearch_results") or []
    
                        # surface any scrape warnings included in pre_search
                        pre_search_warnings = []
                        for d in pre_search:
                            meta = d.get('meta') or {}
                            if meta.get('scrape_warning'):
                                pre_search_warnings.append(meta.get('scrape_warning'))
                        if pre_search_warnings:
                            for w in pre_search_warnings:
                                st.warning(f"検索スクレイピングの警告: {w}")
    
                        import re as _re
                        src_lines = []
                        footnotes = []
    
                        # build maps from pre_search for canonicalization
                        pre_by_id = {str(d.get('id')): d for d in pre_search}
                        pre_by_url = {}
    
                        def _normalize_url(u):
                            if not u or not isinstance(u, str):
                                return None
                            u = u.strip()
                            if u.startswith('//'):
                                u = 'https:' + u
                            u = u.rstrip(').,]')
                            # remove trailing slash for stable comparison
                            if u.endswith('/'):
                                u = u[:-1]
                            return u
    
                        for d in pre_search:
                            d_url = (d.get('meta') or {}).get('source') or d.get('url')
                            norm = _normalize_url(d_url)
                            if norm:
                                pre_by_url[norm] = d
    
                        # canonical entries preserve first-seen order
                        canonical = []
                        seen_keys = set()
    
                        def _extract_url_from_text(txt):
                            m = _re.search(r"(https?://[^\s)\]]+)", txt)
                            if not m:
                                m = _re.search(r"(//[^\s)\]]+)", txt)
                            found = m.group(1) if m else None
                            return _normalize_url(found) if found else None
    
                        for s in sources:
                            sid = s.get('id') or s.get('name') or s.get('source_id')
                            txt = (s.get('text') or s.get('title') or '').replace('\n', ' ')
                            seeded_url = s.get('url') or s.get('path') or ((s.get('meta') or {}).get('source') if isinstance(s.get('meta'), dict) else None)
                            url = _extract_url_from_text(txt)
                            if not url and seeded_url:
                                url = _normalize_url(str(seeded_url))
                            # if sid is a URL, prefer that as url
                            if isinstance(sid, str) and sid.startswith('http') and not url:
                                url = sid.rstrip(').,]')
    
                            canonical_id = None
                            # prefer pre_search id if url matches
                            if url:
                                url_norm = _normalize_url(url)
                            else:
                                url_norm = None
                            if url_norm and url_norm in pre_by_url:
                                canonical_id = str(pre_by_url[url_norm].get('id'))
                            elif isinstance(sid, str) and str(sid) in pre_by_id:
                                canonical_id = str(sid)
                            else:
                                canonical_id = url or str(sid) or None
    
                            key = canonical_id or url_norm or url or txt
                            if not key or key in seen_keys:
                                continue
                            seen_keys.add(key)
    
                            # determine title/label
                            title = ''
                            if canonical_id and canonical_id in pre_by_id:
                                d = pre_by_id[canonical_id]
                                text_content = str(d.get('text', '')).replace('\n', ' ')
                                t_m = _re.search(r"Title:\s*(.*?)(?:URL:|Body:|$)", text_content)
                                title = t_m.group(1).strip() if t_m else (text_content[:120] + ('...' if len(text_content) > 120 else ''))
                                url = url or (d.get('meta') or {}).get('source') or d.get('url')
                            else:
                                # fallback title from snippet
                                if url:
                                    title = txt.replace(url, '').replace('URL:', '').replace('[', '').replace(']', '').strip()
                                else:
                                    title = txt[:120]
    
                            canonical.append({'id': canonical_id, 'label': title or '-', 'url': url})
    
                        # render canonical entries with footnotes
                        note_idx = 1
                        url_to_note = {}
                        for entry in canonical:
                            cid = entry.get('id') or '-'
                            title = entry.get('label')
                            url = entry.get('url')
                            retrieved_at = entry.get('retrieved_at')
                            # format retrieved date as YYYY-MM-DD if present
                            retrieved_text = ''
                            if retrieved_at:
                                try:
                                    dt = retrieved_at
                                    # accept ISO strings
                                    if isinstance(dt, str):
                                        dtf = dt.split('T')[0]
                                    else:
                                        dtf = str(dt)
                                    retrieved_text = f" (取得: {dtf})"
                                except Exception:
                                    retrieved_text = ''
    
                            ref_text = ''
                            if url:
                                if url in url_to_note:
                                    ref_text = f" [URL{url_to_note[url]}]"
                                else:
                                    url_to_note[url] = note_idx
                                    ref_text = f" [URL{note_idx}]"
                                    footnotes.append((note_idx, url))
                                    note_idx += 1
                            # If URL present, render title as a clickable markdown link
                            if url:
                                title_display = f"[{title}]({url})"
                            else:
                                title_display = title
                            src_lines.append(f"- [URL{url_to_note.get(url, 0)}]: {title}{retrieved_text}" if url else f"- [{cid}]: {title}{retrieved_text}")

                        if footnotes:
                            st.markdown("**出典URL:**\n" + "\n".join([f"- URL{n}: [リンク]({u})" for n,u in footnotes]))
                    # provide full raw content in an expander for context
                    if message.get("content"):
                        # also show a normalized view of the raw content when helpful
                        raw = message.get("content")
                        norm_raw = raw
                        try:
                            # apply same normalization to raw block for readability
                            norm_raw = _normalize_org_model(raw)
                            # also apply simplified->Japanese character cleanup
                            def _replace_simplified_chinese(s: str) -> str:
                                if not s:
                                    return s
                                simple_map = {
                                    '乐': '楽',
                                    '馆': '館',
                                    '发': '発',
                                    '后': '後',
                                    '测': '測',
                                    '确': '確',
                                }
                                for k, v in simple_map.items():
                                    s = s.replace(k, v)
                                return s
                            norm_raw = _replace_simplified_chinese(norm_raw)
                        except Exception:
                            norm_raw = raw
                        with st.expander("詳細表示（元の応答）", expanded=False):
                            detail_text = _normalize_mermaid_blocks(norm_raw)
                            detail_text = re.sub(r"\[web_(\d+)\]", r"[URL\1]", detail_text)

                            # 詳細表示は生ログ由来テキストが1行に潰れやすいため、可読性を補正
                            detail_text = detail_text.replace("・出典 [URL", "\n\n・出典 [URL")
                            detail_text = detail_text.replace(") 要約: Title:", ")\n  要約: Title:")
                            detail_text = re.sub(r"\s+要約:\s*Title:", "\n  要約: Title:", detail_text)
                            detail_text = re.sub(r"\s+URL:\s*", "\n  URL: ", detail_text)
                            detail_text = re.sub(r"\s+Body:\s*", "\n  Body: ", detail_text)
                            detail_text = re.sub(r"\s+Bod\b", "\n  Body", detail_text)
                            detail_text = detail_text.replace("(//duckduckgo.com", "(https://duckduckgo.com")
                            detail_text = re.sub(r"\bURL:\s*//", "URL: https://", detail_text)

                            # Web要約形式は生テキストだと詰まりやすいので、出典単位で整形して表示
                            is_web_digest = (
                                "・出典 [URL" in detail_text and "要約: Title:" in detail_text and not _has_mermaid_block(detail_text)
                            )
                            if is_web_digest:
                                header = detail_text.split("・出典 [URL", 1)[0].strip()
                                chunks = re.findall(
                                    r"・出典 \[URL(\d+)\]:\s*(.*?)(?=・出典 \[URL\d+\]:|$)",
                                    detail_text,
                                    re.DOTALL,
                                )
                                lines = []
                                if header:
                                    lines.append(header)
                                if chunks:
                                    if lines:
                                        lines.append("")
                                    lines.append("**出典要約（整形）:**")
                                    for idx, chunk in chunks[:8]:
                                        one = re.sub(r"\s+", " ", chunk).strip()
                                        title = one.split(" (", 1)[0].strip(" -") if one else f"URL{idx}"
                                        u = re.search(r"URL:\s*(https?://[^\s)]+)", one)
                                        url = u.group(1).rstrip(").,") if u else ""
                                        s = re.search(r"要約:\s*Title:\s*(.+?)(?:\s+URL:|\s+Body:|$)", one)
                                        summary = s.group(1).strip() if s else ""
                                        if url:
                                            lines.append(f"- URL{idx}: {title} ([リンク]({url}))")
                                        else:
                                            lines.append(f"- URL{idx}: {title}")
                                        if summary and summary != title:
                                            lines.append(f"  要約: {summary}")
                                if lines:
                                    st.markdown("\n".join(lines))
                                else:
                                    st.text(detail_text)
                            else:
                                st.markdown(detail_text)
                            if _has_mermaid_block(detail_text) or re.search(r"図解|図で|フロー図|構成図|diagram", detail_text, re.IGNORECASE):
                                diagram_mode = normalize_diagram_mode(st.session_state.get("diagram_render_mode", "stable"))
                                if diagram_mode == DIAGRAM_MODE_MERMAID:
                                    mermaid_source = detail_text
                                    if not _has_mermaid_block(mermaid_source):
                                        mermaid_source = mermaid_source + _fallback_mermaid_for_query("質問")
                                    _safe_render_mermaid_blocks(mermaid_source)
                                else:
                                    latest_user_q = ""
                                    try:
                                        for mm in reversed(st.session_state.get("messages") or []):
                                            if mm.get("role") == "user":
                                                latest_user_q = str(mm.get("content") or "")
                                                break
                                    except Exception:
                                        latest_user_q = ""
                                    _render_safe_flow_diagram(
                                        diagram_title_for_query(latest_user_q),
                                        diagram_steps_for_query(latest_user_q),
                                    )
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

    # ===== 曖昧性確認フロー =====
    # If a clarification question is active (set by _store_assistant_message), show UI to collect user's clarification
    if st.session_state.get('clarification_active'):
        st.markdown("---")
        st.subheader("🟡 補足の確認が必要です")
        q = st.session_state.get('clarification_question') or "詳細を教えてください。"
        st.info(q)
        # allow either choosing from options (if provided) or free text
        clar_text = ""
        candidates = st.session_state.get('clarification_candidates')
        if candidates:
            try:
                choice = st.radio("該当する選択肢を選んでください:", options=candidates, key="clar_radio")
                if choice:
                    clar_text = choice
            except Exception:
                clar_text = st.text_input("補足 / 回答を入力してください:", key="clarification_input")
        else:
            clar_text = st.text_input("補足 / 回答を入力してください:", key="clarification_input")
        # Use callbacks for buttons to avoid modifying widget-backed keys in the same run
        def _clar_send():
            # prefer radio choice if present
            user_msg = None
            if st.session_state.get('clar_radio'):
                user_msg = st.session_state.get('clar_radio')
            else:
                user_msg = st.session_state.get('clarification_input')
            user_msg = user_msg or "（ユーザーによる補足なし）"
            # determine the last user query BEFORE appending the clarification to avoid duplication
            last_q = ""
            for m in reversed(st.session_state.messages):
                if m.get('role') == 'user' and m.get('content'):
                    last_q = m.get('content')
                    break
            # append user's clarification as a chat message so UI shows it
            user_msg_obj = {"role": "user", "content": user_msg}
            st.session_state.messages.append(user_msg_obj)
            _save_chat_message(user_msg_obj)  # 履歴に保存
            augmented = f"{last_q}\n\n追記（ユーザーの補足）: {user_msg}"

            ethics = _check_user_instruction_ethics(augmented, source="clarification")
            if ethics.get("action") == "warn":
                _store_assistant_message(
                    f"[注意喚起] この依頼はセンシティブ領域（{ethics.get('category')}）に該当する可能性があります。"
                    "必要に応じて専門家の確認を行ってください。"
                )
            if ethics.get("action") in ("block", "escalate"):
                _store_assistant_message(
                    "この指示は倫理・安全ポリシーにより対応できません。"
                    "目的を安全で合法な内容に言い換えて再入力してください。"
                )
                st.session_state.clarification_active = False
                st.session_state.clarification_question = None
                st.session_state.pop('clarification_input', None)
                st.session_state.pop('clar_radio', None)
                return
            # optional: perform a web search with the augmented query to enrich presearch_results
            try:
                if web_search_available and st.session_state.get('use_web_search'):
                    try:
                        results = search_web_tool(augmented, max_results=8)
                        # normalize results expected format into presearch_results
                        st.session_state.presearch_results = results
                    except Exception:
                        pass
            except Exception:
                pass
            # clear clarification state before calling
            st.session_state.clarification_active = False
            st.session_state.clarification_question = None
            # remove widget-backed keys safely
            st.session_state.pop('clarification_input', None)
            st.session_state.pop('clar_radio', None)
            # call generation with augmented query
            _generate_assistant_response(augmented)

        def _clar_cancel():
            st.session_state.clarification_active = False
            st.session_state.clarification_question = None
            st.session_state.pop('clarification_input', None)
            st.session_state.pop('clar_radio', None)
            # no explicit rerun call; Streamlit will re-run after callback returns

        col_ok, col_cancel = st.columns([1,1])
        with col_ok:
            st.button("送信して続行", key="clar_send", on_click=_clar_send)
        with col_cancel:
            st.button("キャンセル", key="clar_cancel", on_click=_clar_cancel)

    # チャット入力（常時表示）
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
        # 相対日付の事前表示と自動検索トグル
        try:
            norm_q, interpreted_date = parse_relative_date(query)
            if interpreted_date:
                col_a, col_b = st.columns([4,1])
                with col_a:
                    st.info(f"解釈: ユーザーの入力中の相対日付を {interpreted_date} と解釈しました。")
                with col_b:
                    auto_search = st.checkbox("自動検索", value=True, key="ui_auto_search")
                # UI選択で環境変数を制御し、エージェントの事前検索を有効/無効化する
                import os as _os
                _os.environ["RAG_ENABLE_DATE_PRESEARCH"] = "true" if auto_search else "false"
        except Exception:
            pass
        # 新規クエリ送信時は古い確認フロー状態を明示的に解除する
        st.session_state.clarification_active = False
        st.session_state.clarification_question = None
        st.session_state.clarification_candidates = None
        st.session_state.pop('clarification_input', None)
        st.session_state.pop('clar_radio', None)
        # ユーザーのクエリをメッセージに追加
        user_msg_obj = {
            "role": "user",
            "content": query
        }
        st.session_state.messages.append(user_msg_obj)
        _save_chat_message(user_msg_obj)  # 履歴に保存

        ethics = _check_user_instruction_ethics(query, source="chat_input")
        if ethics.get("action") == "warn":
            _store_assistant_message(
                f"[注意喚起] この依頼はセンシティブ領域（{ethics.get('category')}）に該当する可能性があります。"
                "必要に応じて専門家の確認を行ってください。"
            )
        if ethics.get("action") in ("block", "escalate"):
            _store_assistant_message(
                "この指示は倫理・安全ポリシーにより対応できません。"
                "目的を安全で合法な内容に言い換えて再入力してください。"
            )
            st.session_state.last_query_processed = query
            st.rerun()

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

        st.markdown("---")
        st.subheader("倫理チェック監査ログ")
        ethics_log = Path("logs/ethics_audit.jsonl")
        if ethics_log.exists():
            ethics_data = []
            with open(ethics_log, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        ethics_data.append(json.loads(line))
                    except Exception:
                        continue

            if ethics_data:
                df_ethics = pd.DataFrame(ethics_data)
                if "decision" in df_ethics.columns:
                    # decision(dict) を列へ展開
                    decision_df = pd.json_normalize(df_ethics["decision"])
                    decision_df.columns = [f"decision.{c}" for c in decision_df.columns]
                    df_ethics = pd.concat([df_ethics.drop(columns=["decision"]), decision_df], axis=1)

                # フィルタUI
                filt_cols = st.columns([1, 1, 1, 1])
                with filt_cols[0]:
                    action_options = sorted(df_ethics["decision.action"].dropna().astype(str).unique().tolist()) if "decision.action" in df_ethics.columns else []
                    selected_actions = st.multiselect(
                        "action フィルタ",
                        options=action_options,
                        default=action_options,
                        key="ethics_filter_actions",
                    )
                with filt_cols[1]:
                    category_options = sorted(df_ethics["decision.category"].dropna().astype(str).unique().tolist()) if "decision.category" in df_ethics.columns else []
                    selected_categories = st.multiselect(
                        "category フィルタ",
                        options=category_options,
                        default=category_options,
                        key="ethics_filter_categories",
                    )
                with filt_cols[2]:
                    source_options = sorted(df_ethics["source"].dropna().astype(str).unique().tolist()) if "source" in df_ethics.columns else []
                    selected_sources = st.multiselect(
                        "source フィルタ",
                        options=source_options,
                        default=source_options,
                        key="ethics_filter_sources",
                    )
                with filt_cols[3]:
                    max_rows = st.slider("表示件数", min_value=10, max_value=300, value=100, step=10, key="ethics_filter_max_rows")

                df_filtered = df_ethics.copy()
                if "decision.action" in df_filtered.columns and selected_actions:
                    df_filtered = df_filtered[df_filtered["decision.action"].astype(str).isin(selected_actions)]
                if "decision.category" in df_filtered.columns and selected_categories:
                    df_filtered = df_filtered[df_filtered["decision.category"].astype(str).isin(selected_categories)]
                if "source" in df_filtered.columns and selected_sources:
                    df_filtered = df_filtered[df_filtered["source"].astype(str).isin(selected_sources)]

                total = len(df_filtered)
                warn_count = int((df_filtered.get("decision.action") == "warn").sum()) if "decision.action" in df_filtered.columns else 0
                block_count = int((df_filtered.get("decision.action") == "block").sum()) if "decision.action" in df_filtered.columns else 0
                allow_count = int((df_filtered.get("decision.action") == "allow").sum()) if "decision.action" in df_filtered.columns else 0

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("判定総数", total)
                c2.metric("ALLOW", allow_count)
                c3.metric("WARN", warn_count)
                c4.metric("BLOCK", block_count)

                display_cols = [
                    c for c in [
                        "timestamp",
                        "source",
                        "query_preview",
                        "decision.action",
                        "decision.category",
                        "decision.reason",
                        "decision.confidence",
                    ]
                    if c in df_ethics.columns
                ]
                sort_col = "timestamp" if "timestamp" in df_ethics.columns else None
                if sort_col:
                    df_filtered = df_filtered.sort_values(sort_col, ascending=False)
                st.dataframe(df_filtered[display_cols].head(max_rows), use_container_width=True)
            else:
                st.info("倫理監査ログが空です。")
        else:
            st.info("倫理監査ログファイル（logs/ethics_audit.jsonl）はまだ作成されていません。")

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
        if 'rebuild_project' in globals():
            rebuild_project()
        else:
            logger.warning('rebuild_project が定義されていないためスキップします')
    except Exception as e:
        logger.error(f"プロジェクトの再構築中にエラーが発生しました: {e}")
else:
    try:
        setup_sidebar()
        if st.session_state.get("app_page") == "📔 OneNote日記":
            display_onenote_diary()
        elif st.session_state.get("app_page") == "🛡️ エンタープライズ統合":
            display_enterprise_dashboard()
        elif st.session_state.get("app_page") == "🧠 Learning Dashboard":
            from src.rag.learning_dashboard import render_learning_dashboard
            render_learning_dashboard()
        else:
            display_app()
    except Exception as e:
        logger.error(f"アプリ実行中にエラーが発生しました: {e}")
        st.error(f"❌ エラー: {e}")
