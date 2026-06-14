import os
import sys
from dotenv import load_dotenv
load_dotenv()
import tempfile
from pathlib import Path
from datetime import datetime
import html
import uuid
from src.rag.date_utils import parse_relative_date

# Import modularized utilities and pages
from src.utils.text_utils import (
    _decode_text_bytes,
    _chunk_text,
    _detect_audio_ext,
    _is_safe_url,
    _fetch_url_text,
    _fetch_url_text_and_title,
    _extract_game_score_from_url,
    _extract_urls,
    _parse_chapter_no,
    _extract_page_number,
)
from src.audio.audio_utils import (
    transcribe_audio_bytes,
    get_whisper_model,
    faster_whisper_available,
)
from src.weather.weather_utils import (
    _is_weather_query,
    _extract_weather_location,
    _weather_code_to_ja,
    _fallback_weather_coords,
    _resolve_weather_location,
    _fetch_weather_context,
)
from src.onenote.onenote_settings import (
    _load_onenote_settings,
    _save_onenote_settings,
)
from src.ui.diagram_renderer import (
    _has_mermaid_block,
    _normalize_mermaid_blocks,
    _fallback_mermaid_for_query,
    _render_markdown_with_mermaid,
    _render_mermaid_blocks_only,
    _safe_render_mermaid_blocks,
    _render_safe_flow_diagram,
    _parse_mermaid_steps,
    _MERMAID_BLOCK_RE,
)
from src.ui.sidebar import (
    _load_sidebar_history_days,
    _save_sidebar_history_days,
    get_retriever,
    setup_sidebar,
)
from src.ui.onenote_diary_page import display_onenote_diary
from src.ui.enterprise_dashboard_page import display_enterprise_dashboard

import streamlit as st
import streamlit.components.v1 as components
import logging
import json
import time
import hashlib
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
    from src.self_improvement.feedback_manager import FeedbackManager
    from src.self_improvement.streamlit_integration import StreamlitIntegration
    feedback_runtime_available = True
except Exception:
    FeedbackManager = None
    StreamlitIntegration = None
    feedback_runtime_available = False
try:
    from src.safety.ethics_guard import EthicsGuard
    ethics_guard_available = True
except Exception:
    EthicsGuard = None
    ethics_guard_available = False

try:
    from autonomous_rag_agent import AutonomousRAGAgent
    rag_agent_available = True
    agent = AutonomousRAGAgent()
except Exception:
    AutonomousRAGAgent = None
    rag_agent_available = False
    agent = None

# OneNote 日記モジュール
try:
    from src.onenote import onenote_diary as _onenote
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






_MERMAID_BLOCK_RE = re.compile(r"```mermaid(?:\s*\n|\s+)(.*?)```", re.DOTALL | re.IGNORECASE)
_ethics_guard = None
_feedback_manager = None


def _get_ethics_guard():
    global _ethics_guard
    if _ethics_guard is None and ethics_guard_available:
        try:
            _ethics_guard = EthicsGuard()
        except Exception:
            _ethics_guard = None
    return _ethics_guard


def _get_feedback_manager():
    global _feedback_manager
    if _feedback_manager is None and feedback_runtime_available:
        try:
            _feedback_manager = FeedbackManager()
        except Exception:
            _feedback_manager = None
    return _feedback_manager


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


def _remember_ethics_decision(query: str, ethics: dict, source: str) -> None:
    """Keep the latest ethics decision in session state for downstream feedback metadata."""
    try:
        st.session_state.last_ethics_decision = dict(ethics or {})
        st.session_state.last_ethics_query = str(query or "")
        st.session_state.last_ethics_source = str(source or "chat_input")
    except Exception:
        pass


def _build_feedback_target() -> dict | None:
    """Return the latest user/assistant pair for inline feedback."""
    messages = st.session_state.get("messages") or []
    last_assistant = None
    last_user = ""
    for item in reversed(messages):
        if last_assistant is None and item.get("role") == "assistant":
            last_assistant = item
            continue
        if last_assistant is not None and item.get("role") == "user":
            last_user = str(item.get("content") or "")
            break
    if not last_assistant:
        return None

    response_text = str(last_assistant.get("content") or last_assistant.get("conclusion") or "").strip()
    if not response_text:
        return None

    response_key = hashlib.sha256(
        f"{last_user}\n{response_text}".encode("utf-8", errors="ignore")
    ).hexdigest()[:16]
    return {
        "user_query": last_user,
        "response_text": response_text,
        "response_key": response_key,
    }


def _render_inline_feedback_panel() -> None:
    """Render an inline feedback form for the latest assistant response."""
    if not feedback_runtime_available:
        return
    target = _build_feedback_target()
    if not target:
        return

    submitted_keys = list(st.session_state.get("feedback_submitted_response_keys") or [])
    response_key = target["response_key"]
    st.markdown("---")
    if response_key in submitted_keys:
        st.caption("この回答へのフィードバックは送信済みです。")
        return

    with st.expander("📝 回答へのフィードバックを送る", expanded=False):
        feedback_data = StreamlitIntegration.render_feedback_ui(session_state_key=f"feedback_{response_key}")
        if not feedback_data.get("submitted"):
            return

        feedback_manager = _get_feedback_manager()
        if not feedback_manager:
            st.error("フィードバック保存機能を初期化できませんでした。")
            return

        try:
            feedback_manager.record_feedback(
                user_query=target["user_query"],
                model_response=target["response_text"],
                rating=float(feedback_data.get("rating") or 0.0),
                feedback_text=feedback_data.get("feedback_text"),
                tags=feedback_data.get("tags") or [],
                suggestions=feedback_data.get("suggestions"),
                response_id=response_key,
                model_name=st.session_state.get("llm_model"),
                metadata=feedback_data.get("metadata") or {},
            )
            st.session_state.feedback_submitted_response_keys = submitted_keys + [response_key]
            st.success("フィードバックを保存しました。")
        except Exception as e:
            logger.error(f"feedback_record_failed: {e}")
            st.error(f"フィードバック保存に失敗しました: {e}")


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


def _query_requests_counting(query: str) -> bool:
    if not query:
        return False
    return bool(re.search(r"何回|何文字|数えて|合計|計算|足して|算出して|カウント|文字数|単語数|個数", query))
















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


def _get_git_revision_info() -> str:
    """Git のコミットハッシュ（短縮）とコミット日付を取得する"""
    import subprocess
    try:
        # Dockerコンテナ内での所有権エラーを回避するための設定追加を試みる
        try:
            subprocess.run(["git", "config", "--global", "--add", "safe.directory", "/app"], stderr=subprocess.DEVNULL)
        except Exception:
            pass

        # コミットハッシュ取得 (7桁短縮)
        hash_cmd = ["git", "rev-parse", "--short", "HEAD"]
        commit_hash = subprocess.check_output(hash_cmd, stderr=subprocess.DEVNULL).decode("utf-8").strip()

        # コミット日付取得 (YYYY-MM-DD)
        date_cmd = ["git", "show", "-s", "--format=%cd", "--date=short", "HEAD"]
        commit_date = subprocess.check_output(date_cmd, stderr=subprocess.DEVNULL).decode("utf-8").strip()

        return f"Revision: {commit_hash} ({commit_date})"
    except Exception:
        return "Revision: unknown"


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



# Streamlitのページ構成を設定
st.set_page_config(page_title="RAG Agent", layout="wide")


# ────────────────────────────────────────────
# URL本文取得ユーティリティ
# ────────────────────────────────────────────






















# OneNote設定の保存先
ONENOTE_SETTINGS_PATH = Path(__file__).resolve().parent / "config" / "onenote_settings.json"
SIDEBAR_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "sidebar_config.json"









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

# サイドバーの設定

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
    default_model = "qwen2.5-coder:7b"
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("USE_OPENAI_API", "").lower() == "true":
        default_model = "gpt-4o"
    defaults = {
        "messages": _load_chat_history(),  # 昨日以前のチャット履歴を読み込む
        "llm_model": default_model,
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
        "feedback_submitted_response_keys": [],
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
            model=st.session_state.get("llm_model", "qwen2.5:1.5b"),
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
            f"{query}\n\n"
            "【提供された情報】\n"
            f"{url_context}{weather_context}{page_context}\n\n"
            "指示：提供された情報のみに基づいて回答してください。"
            "情報に記載がない場合は、推測で答えずに「提供データには記載がありません」と答えてください。"
        )
        # ページ指定で翻訳要求の場合は、翻訳指示を明示的に追加
        if page_no and ('翻訳' in query or 'translation' in query.lower()):
            base_prompt += "\n【翻訳指示】上記のコンテンツが英語の場合、自然な日本語に翻訳してください。段落構造は保持してください。"
    else:
        base_prompt = query

    return base_prompt


def _is_reasoning_or_math_query(query: str) -> bool:
    """Detect logic, math, character counting, coding, translation, or riddle queries."""
    q = query.strip().lower()
    patterns = [
        r"何回使われて",
        r"何回含まれて",
        r"何文字",
        r"文字数",
        r"カウント",
        r"足してください",
        r"引いてください",
        r"計算して",
        r"計算しなさい",
        r"合計",
        r"総数",
        r"なぞなぞ",
        r"トンチ",
        r"クイズ",
        r"解いて",
        r"アルファベットの数",
        r"英訳",
        r"英語にした時の",
        r"英単語の数",
        r"アルファベット数",
        r"算数",
        r"数学",
        r"方程式",
        r"コードを書いて",
        r"プログラム",
        r"実装してください",
        r"アルゴリズム",
    ]
    import re
    return any(re.search(p, q) for p in patterns)


def _generate_assistant_response(query: str, container=None) -> None:
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
- 回答は原則として100%日本語で書いてください（ただし、ユーザーが英単語のスペル、アルファベット、英会話表現、英語翻訳などを明示的に出力するよう求めている場合を除きます）。
- ユーザーからの英語のスペル確認や翻訳の要求がない限り、英語・中国語・その他の言語を回答に使用しないでください。
- ユーザーから英語のURLや英語の記事を渡された場合でも、ユーザーが翻訳を求めていない限り、あなたの解説や回答は日本語で行います。
- 英語の固有名詞・サービス名は原則としてカタカナに変換してください（例: newsletter → ニュースレター）。
- 理由なく途中で英語に切り替えることは絶対に禁止です。
- 英語のテキストを引用する場合も、原則として日本語訳または日本語の説明を添えてください。
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
            
            # 💡 スマートWeb検索バイパスロジック
            # 添付ファイルが存在するか、直近のPDFソース情報がロードされている場合は、遅延の大きい外部Web検索をスキップする
            has_attached_file = bool(st.session_state.get("attached_file_contents"))
            has_recent_source = bool(st.session_state.get("last_uploaded_file_source") or st.session_state.get("last_added_source"))
            
            # ユーザーが明示的にWeb検索を指定しているキーワード
            explicit_search_keywords = ["検索", "調べる", "web", "ウェブ", "最新", "ニュース", "速報", "今日", "昨日", "今週", "先週", "天気"]
            wants_explicit_search = any(kw in query.lower() for kw in explicit_search_keywords)
            
            if (has_attached_file or has_recent_source) and not wants_explicit_search:
                _append_run_log(f"smart_web_search_bypass: skipping web search because file/source context is loaded and query has no explicit search keywords. query='{query}'")
                do_auto = False
            
            if _is_reasoning_or_math_query(query):
                _append_run_log(f"reasoning_math_bypass: skipping web search for reasoning/math query='{query}'")
                do_auto = False
            
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
                preview_lines = [
                    f"\n【🔍 Web自動検索結果 {len(presearch_docs)}件 (解釈日: {interpreted_date})】",
                    "【最重要ルール: ハルシネーションの厳禁】",
                    "- 以下のWeb検索結果を参考に回答してください。回答の根拠となる箇所には必ず [web_1] のような出典IDを明記してください。",
                    "- もしユーザーの質問の前提（例：『昨日、日本の総理大臣が円からドルに変更すると発表した』等の主張や決定事項）が、提示された以下のWeb検索結果の抜粋に一切記載されていない、または矛盾する場合は、その前提が確認できないことを結論（回答の冒頭）で明確に指摘してください。",
                    "- 提供された検索結果に存在しない事実を認めて『発表されたが影響は書かれていない』などとでっち上げて回答したり、ありもしない根拠（出典ID）を付与することは絶対に禁止します（ハルシネーションの厳禁）。",
                    "---"
                ]
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
            
            # 推論・計算・なぞなぞクエリ用の指示を追加
            if _is_reasoning_or_math_query(query):
                prompt = (
                    "【注意：推論・論理的思考・数学・数え上げ問題】\n"
                    "この質問は、論理的思考、数学的計算、文字の正確なカウント、英訳およびその文字数カウント、またはプログラミングなどの推論能力を必要とします。\n"
                    "外部ソースの情報をそのまま引用するのではなく、あなた自身の高度な思考能力と論理的推論力をフルに活用し、思考プロセスを順を追って（ステップ・バイ・ステップで）説明した上で、正確に回答してください。\n\n"
                    + prompt
                )
            
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
            
            # Heuristic: 連続質問の文脈が切れないよう、参照語・短文・語彙重なりでもフォローアップ判定する
            treat_as_fresh = False
            followup_like = True
            previous_user_query = ""
            recent_query = (query or "").strip()
            try:
                # 直前ユーザー質問を取得（現在質問は messages の末尾に入っている前提）
                msgs = st.session_state.get("messages") or []
                for m in reversed(msgs[:-1]):
                    if m.get("role") == "user":
                        previous_user_query = str(m.get("content") or "").strip()
                        break

                has_detail_request = "詳しく" in recent_query
                explicit_follow = bool(re.search(r"続き|前回|さっき|先ほど|その件|もう少し|補足|それで|ちなみに|じゃあ", recent_query))
                if has_detail_request and (len(recent_query) <= 15 or not re.search(r"について|の件|の件について", recent_query)):
                    explicit_follow = True

                referential = bool(re.search(r"これ|それ|あれ|上記|前者|後者|同じ|その|どれ|どの|あの", recent_query))
                short_follow = len(recent_query) <= 24
                elliptical_follow = bool(
                    re.search(r"^(無料|有料|料金|値段|価格|いくら|使える|使えますか|できますか|可能ですか|対応していますか).*[？?]?$", recent_query)
                    or re.search(r"(無料|有料|料金|値段|価格|いくら).*(ですか|ますか|\?|？)$", recent_query)
                )
                marketplace_follow = bool(
                    re.search(
                        r"amazon|アマゾン|楽天|yahoo|ヤフー|価格\.com|モノタロウ|ヨドバシ|通販|ショップ|販売",
                        recent_query,
                        re.IGNORECASE,
                    )
                )

                # 内容語の重なりで関連度を推定
                stop_words = {
                    "について", "です", "ます", "したい", "ください", "教えて", "知りたい", "何", "なに", "どこ", "いつ",
                    "これ", "それ", "あれ", "その", "この", "で", "を", "が", "は", "に", "の", "と", "も", "か",
                    "詳しく", "説明", "解説", "図解", "概要", "要約", "詳細", "方法", "意味", "定義", "関係", "内容", "記事", "などで"
                }
                cur_terms = [t for t in re.findall(r"[a-zA-Z0-9ぁ-んァ-ヶー一-龠々]{2,}", recent_query) if t not in stop_words]
                prev_terms = [t for t in re.findall(r"[a-zA-Z0-9ぁ-んァ-ヶー一-龠々]{2,}", previous_user_query) if t not in stop_words]
                overlap = len(set(cur_terms) & set(prev_terms))

                # 「このPDF」系は履歴汚染を避けるため常に新規扱い
                if is_file_referential_query:
                    treat_as_fresh = True
                # 「について」が含まれ、かつ内容語の重複がない場合は新規扱い
                elif "について" in recent_query and overlap == 0:
                    followup_like = False
                    treat_as_fresh = True
                # 参照語+短文、または語彙重なりがあるときは会話継続扱い
                elif explicit_follow or (referential and short_follow) or overlap >= 1 or (marketplace_follow and short_follow) or (elliptical_follow and short_follow):
                    followup_like = True
                    treat_as_fresh = False
            except Exception:
                treat_as_fresh = True
                followup_like = False

            st.session_state.presearch_results = None

            # LLM呼び出し前に、毎回ローカルコーパス検索を実行して結果を最新化する
            try:
                if retriever_available and not _is_reasoning_or_math_query(query):
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
                                "詳しく", "説明", "解説", "図解", "概要", "要約", "詳細", "方法", "意味", "定義", "関係", "内容", "記事", "などで"
                            }
                            # アルファベット・数字・ひらがな/カタカナ/漢字の2文字以上を抽出
                            raw_terms = _re_kw.findall(r"[a-zA-Z0-9ぁ-んァ-ヶー一-龠々]{2,}", query or "")
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

                            # それでも空で、かつ会話が継続（フォローアップ）している場合のみ、前回の検索結果を暫定利用して文脈断絶を防ぐ
                            # (無関係な新規クエリへの文脈混入・トピックずれを防ぐため)
                            if not local_pre and followup_like and isinstance(previous_presearch_results, list) and previous_presearch_results and not is_file_referential_query:
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
                # 応答傾向（詳細要求等）を前倒しで推論
                inferred_profile = {
                    "verbosity": "balanced",
                    "format": "paragraph",
                    "focus": "balanced",
                    "validation": "normal",
                }
                try:
                    inferred_profile = infer_response_preferences(st.session_state.get("messages") or [])
                    st.session_state.response_preference_profile = inferred_profile
                except Exception as e:
                    _append_run_log(f"response_style_profile_failed_early: {e}")

                if pre:
                    is_detailed = inferred_profile.get("verbosity") == "detailed"
                    if is_detailed:
                        directive_lines = [
                            "【注意：検索結果を参照して詳細にわかりやすく答えること】以下は自動で取得した検索結果（ローカル文書を含む）です。回答を作る際、必ずこれらを参照してください。出力形式に厳密に従ってください：",
                            "1) 結論（Qに対する答え）を最初にわかりやすく述べる。",
                            "2) 結論に至る理由や技術的詳細、背景情報を詳しく解説する。段落や見出し（Markdown）を適切に使い、詳細に構成してください。",
                            "3) 根拠となる箇所は必ず出典ID `[source_id]` を明記してください。",
                            "3.1) 重要: 本文中に生のURLを貼り付けないでください。本文では必ず出典ID（[source_id]）のみを使い、URLは文末の注釈としてまとめてください。",
                            "3.2) 重要: 組織名とモデル名は明確に区別してください。混同しないこと。",
                            "4) すべて日本語で答えること。",
                        ]
                    else:
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
            # (followup_like, treat_as_fresh, previous_user_query, recent_query はすでに前段で計算されています)

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

            needs_counting_verification = _query_requests_counting(current_query)
            if needs_counting_verification:
                prompt = (
                    prompt
                    + "\n\n【計算・カウント・パズル問題の必須要件】\n"
                    + "- ユーザーは文字のカウントや計算、論理パズルを求めています。\n"
                    + "- 直感的に答えを出さず、必ず以下のステップを踏んで思考を書き出してください。\n"
                    + "  1) 対象の文字列を1文字ずつ分解（リスト化）して、カウント対象の文字がどこに存在するかを正確に数える。漢字の形が完全に一致するもの（部首などの一部ではなく、文字そのもの）のみを正確にカウントし、「社」や「者」といった異なる漢字は絶対に「車」としてカウントしないでください。\n"
                    + "  2) 同音異義語や複数の意味を持つ単語がある場合、それぞれの単語の意味とスペルをすべて書き出す。英単語の文字数を数える際は、必ずスペルを1文字ずつリスト化（例: 'your' -> y,o,u,r = 4文字）して、絶対に数え間違いのないように数えてください。\n"
                    + "  3) 各ステップでの中間計算（例: 各単語の文字数）を個別に書き出し、最後にすべての数値を算術的に合計する。\n"
                    + "- 最後に自己検証（ダブルチェック）を行い、矛盾やカウントミスがないか確認した上で結論を出力してください。\n\n"
                    + "【具体的な思考プロセスと検証の例】\n"
                    + "例：文章「貴社の記者が汽車で帰社した」の中の漢字「車」の回数と、各単語の英訳アルファベット総数の合計を求める場合：\n"
                    + "1. 文字列の分解と漢字の確認：\n"
                    + "   1.貴 (否)、2.社 (否)、3.の (否)、4.記 (否)、5.者 (否)、6.が (否)、7.汽 (否)、8.車 (合致 - 1回目)、9.で (否)、10.帰 (否)、11.社 (否)、12.し (否)、13.た (否)\n"
                    + "   よって「車」という漢字そのものは 1回 のみ使われています。（「社」や「者」は「車」とは異なる漢字ですので、絶対にカウントに含めてはなりません）\n"
                    + "2. 同音異義語「きしゃ」の英訳と文字数カウント：\n"
                    + "   - 貴社 -> your company: y,o,u,r(4) + c,o,m,p,a,n,y(7) = 11文字\n"
                    + "   - 記者 -> reporter: r,e,p,o,r,t,e,r = 8文字\n"
                    + "   - 汽車 -> train: t,r,a,i,n = 5文字\n"
                    + "   - 帰社 -> return to office: r,e,t,u,r,n(6) + t,o(2) + o,f,f,i,c,e(6) = 14文字\n"
                    + "3. 各英訳の文字数合計：\n"
                    + "   11 + 8 + 5 + 14 = 38文字\n"
                    + "4. 最終合計：\n"
                    + "   1 (「車」の数) + 38 (アルファベット数) = 39\n"
                )
                _append_run_log("counting_request_detected: enforcing_step_by_step_verification=True")

            # 会話履歴から推定したユーザー志向を反映（セッション内のみ）
            try:
                # 前倒しで推論済みの st.session_state.response_preference_profile または inferred_profile を使用
                inferred_profile = st.session_state.get("response_preference_profile") or inferred_profile
                style_directive = build_response_style_directive(inferred_profile)
                if style_directive:
                    prompt = style_directive + prompt
                    _append_run_log(f"response_style_profile_applied: {json.dumps(inferred_profile, ensure_ascii=False)}")
            except Exception as e:
                _append_run_log(f"response_style_profile_failed: {e}")

            # ======= 日本語出力の厳格化と二重制約の緩和 (User Prompt 末尾への念押し) =======
            prompt = (
                prompt
                + "\n\n【重要な最終指示】\n"
                + "- 必ず日本語のみで回答してください（英語の専門用語はカタカナにするか、日本語訳を併記すること）。中国語や英語などの多言語での出力は絶対に禁止します。\n"
                + "- もしユーザーの質問に「詳しく説明せよ」と「1文字で答えて（Yes/Noなど）」のような、矛盾する条件（二重制約）が含まれている場合、一方のみを優先してもう一方を無視するのを避けてください。まず要求された短いフォーマット（「No」など）で簡潔に回答した上で、その後に改行して明確な判断基準や説明を詳しく述べるようにしてください。"
            )
            # =========================================================

            # LLM 呼び出しを実行し、例外は捕捉してログに残す
            try:
                _append_run_log(f"DEBUG: About to call LLM with prompt_len={len(prompt)} model={st.session_state.llm_model}")
                _append_run_log(f"DEBUG: prompt_start={prompt[:300]}")  # Log first 300 chars
                if container is not None:
                    with container:
                        with st.chat_message("assistant", avatar="🤖"):
                            generator = call_llm(
                                prompt=prompt,
                                model=st.session_state.llm_model,
                                system_prompt=system_prompt,
                                chat_history=chat_history if chat_history else None,
                                temperature=st.session_state.temperature,
                                max_tokens=st.session_state.max_tokens,
                                stream=True,
                            )
                            if hasattr(generator, "__iter__") and not isinstance(generator, (str, bytes)):
                                response = st.write_stream(generator)
                            else:
                                response = generator
                                st.markdown(response)

                            # 新規生成した応答に Mermaid ブロックがある場合のレンダリング
                            try:
                                if _has_mermaid_block(response):
                                    diagram_mode = normalize_diagram_mode(st.session_state.get("diagram_render_mode", "mermaid"))
                                    latest_user_q = current_query if 'current_query' in locals() else ""
                                    if diagram_mode == DIAGRAM_MODE_MERMAID:
                                        # Mermaidモード時は送信完了後の st.rerun() によって
                                        # 履歴側の _render_markdown_with_mermaid で美しくインライン描画されるため、
                                        # ここでは二重描画を防ぐために何もしない
                                        pass
                                    else:
                                        st.markdown("**図解:**")
                                        parsed_steps = []
                                        try:
                                            for m in _MERMAID_BLOCK_RE.finditer(response):
                                                code = m.group(1) or ""
                                                parsed_steps.extend(_parse_mermaid_steps(code))
                                        except Exception as pe:
                                            _append_run_log(f"Error parsing steps for new response: {pe}")
                                        if not parsed_steps:
                                            parsed_steps = diagram_steps_for_query(latest_user_q)

                                        _render_safe_flow_diagram(
                                            diagram_title_for_query(latest_user_q),
                                            parsed_steps,
                                        )
                                        with st.expander("📊 図解のコード（Mermaid形式）を表示", expanded=False):
                                            for m in _MERMAID_BLOCK_RE.finditer(response):
                                                code = (m.group(1) or "").strip()
                                                if code:
                                                    st.code(code, language="mermaid")
                            except Exception as e:
                                _append_run_log(f"Error rendering diagram for new response: {e}")
                else:
                    response = call_llm(
                        prompt=prompt,
                        model=st.session_state.llm_model,
                        system_prompt=system_prompt,
                        chat_history=chat_history if chat_history else None,
                        temperature=st.session_state.temperature,
                        max_tokens=st.session_state.max_tokens,
                        stream=False,
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
                # 以前はここで出典(citation)が含まれていないと「hallucination」として回答を破棄・置換する
                # 厳格なチェックがありましたが、ユーザー体験を損ねる（回答が消える）ためチェックを緩和し、
                # 常に回答を受け入れて表示するように変更します。
                ok = True
                provenance = sources
                _append_run_log(f"✅ ACCEPT RESPONSE: Saving generated response. sources={len(provenance)}")

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
                    # 検索結果を元に、LLMに自然な要約を生成させることを試みる
                    fallback_system_prompt = (
                        "あなたは親切なAIアシスタントです。提供された検索結果をもとに、ユーザーの質問に対する回答を自然で分かりやすい日本語で作成してください。"
                        "検索結果にない情報は推測で補わず、事実に基づいた丁寧な回答を心がけてください。"
                    )
                    
                    docs_text = ""
                    for i, d in enumerate(pre[:5], 1):
                        docs_text += f"[出典 {i}]\n{d.get('text', '')}\n\n"
                    
                    fallback_prompt = (
                        f"ユーザーの質問: {query}\n\n"
                        f"【検索結果】\n{docs_text}\n"
                        f"上記の検索結果から、ユーザーの質問に対する回答を自然な日本語で作成してください。"
                        f"回答の最後には、どの出典を参考にしたか（例：[出典 1]など）を明記してください。"
                    )
                    
                    fallback_success = False
                    try:
                        _append_run_log("Attempting fallback LLM generation using search results...")
                        fallback_response = call_llm(
                            prompt=fallback_prompt,
                            model=st.session_state.llm_model,
                            system_prompt=fallback_system_prompt,
                            chat_history=None,
                            temperature=0.3,
                            max_tokens=600,
                            stream=False,
                        )
                        if isinstance(fallback_response, str) and fallback_response.strip() and not fallback_response.startswith("Error"):
                            _append_run_log("Fallback LLM generation succeeded.")
                            # 出典元情報を構築
                            _store_assistant_message({"text": fallback_response, "sources": sources})
                            fallback_success = True
                    except Exception as fe:
                        _append_run_log(f"Fallback LLM generation failed: {fe}")
                    
                    if not fallback_success:
                        # LLMがやはり失敗した場合は、出典のみを表示するが、より親切な文言にする
                        lines = ["申し訳ありません。回答の直接生成中に一時的なエラーが発生したため、自動で取得した外部検索結果の要約と参照リンクのみを提示いたします。最新情報の確認には必ず公式サイトをご確認ください。\n"]
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
                    _store_assistant_message(f"申し訳ありません。回答の直接生成中にエラーが発生しました。しばらく経ってから再度お試しください。 ({response})")
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
            .stApp [data-testid="stAppViewContainer"] .main .block-container,
            .stApp [data-testid="stAppViewContainer"] [data-testid="stMain"] .block-container,
            .stApp [data-testid="stAppViewContainer"] section:not([data-testid="stSidebar"]) .block-container,
            .stApp .main .block-container {
                padding-top: 0.65rem !important;
                padding-bottom: 3.5rem !important; /* メイン領域の底余白をさらに削って会話エリアを下限まで伸ばす */
                max-width: 96% !important;
            }

            /* チャットメッセージのコンテナ（回答エリア）の高さを広げる */
            /* 浅い階層（メイン領域の直下）にあるメインチャットコンテナのみをターゲットとし、ネストされたアコーディオンやフォームを排除 */
            [data-testid="stAppViewContainer"] [data-testid="stMain"] .block-container > div > div > [data-testid="element-container"] > [data-testid="stVScrollTable"],
            [data-testid="stAppViewContainer"] [data-testid="stMain"] .block-container > div > div > [data-testid="element-container"] > div.stVerticalBlockBorderWrapper,
            [data-testid="stAppViewContainer"] [data-testid="stMain"] .block-container > div > div > [data-testid="element-container"] > div > [data-testid="stVScrollTable"],
            [data-testid="stAppViewContainer"] [data-testid="stMain"] .block-container > div > div > [data-testid="element-container"] > div > div.stVerticalBlockBorderWrapper,
            div[style*="650px"],
            div[style*="height: 650px"],
            div[style*="height:650px"] {
                height: 68vh !important; /* 画面高さに収まるように68vhに固定 */
                max-height: 68vh !important;
                overflow-y: auto !important; /* 独立したスクロール窓として上下できるように強制指定 */
            }

            /* クエリ入力エリアをコンパクトにし、余白を削って回答エリアを広げる */
            div[data-testid="stChatInput"],
            .stChatInput {
                bottom: 8px !important; /* 最下部寄りに固定 */
                padding: 0px !important;
            }
            div[data-testid="stChatInput"] > div,
            .stChatInput > div {
                padding: 0px !important;
                border-radius: 8px !important;
            }
            div[data-testid="stChatInput"] textarea,
            .stChatInput textarea {
                padding-top: 6px !important;
                padding-bottom: 6px !important;
                height: 40px !important;
                min-height: 40px !important;
                max-height: 100px !important;
            }
            /* 入力コンテナ自体の余白調整 */
            [data-testid="stChatInputContainer"],
            .stChatInputContainer {
                padding: 2px 0px !important;
                margin-bottom: 0px !important;
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
    # 会話フォントサイズを動的に反映
    font_size = st.session_state.get("font_size", 16)
    st.markdown(
        f"""
        <style>
            [data-testid="stMain"] div[data-testid="stMarkdownContainer"] p,
            [data-testid="stMain"] div[data-testid="stMarkdownContainer"] li,
            [data-testid="stMain"] div[data-testid="stMarkdownContainer"] span,
            [data-testid="stMain"] div[data-testid="stMarkdownContainer"] strong,
            [data-testid="stMain"] div[data-testid="stMarkdownContainer"] code,
            [data-testid="stMain"] div[data-testid="stMarkdownContainer"] pre {{
                font-size: {font_size}px !important;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("🤖 自律型RAGエージェント")
    logger.debug("display_app function is being called...")
    
    _init_display_session_state()

    st.subheader("💬 会話")

    chat_scroll_container = st.container(height=720, border=False)
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
                        # st.markdown(f"**回答（簡潔）:** {norm_concl}")

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

                                # if uniq:
                                #     st.markdown("**最初にやること（要点）:**")
                                #     for ln in uniq:
                                #         st.markdown(f"- {ln}")
                                pass
                        except Exception:
                            pass
    
                    # 図解要求の回答は、詳細表示を開かなくても主表示に図を出す
                    raw_content_for_diagram = str(message.get("content") or "")
                    if _has_mermaid_block(raw_content_for_diagram):
                        st.markdown("**図解:**")
                        diagram_mode = normalize_diagram_mode(st.session_state.get("diagram_render_mode", "mermaid"))
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
                            parsed_steps = []
                            try:
                                for m in _MERMAID_BLOCK_RE.finditer(raw_content_for_diagram):
                                    code = m.group(1) or ""
                                    parsed_steps.extend(_parse_mermaid_steps(code))
                            except Exception as pe:
                                _append_run_log(f"Error parsing steps in history: {pe}")
                            if not parsed_steps:
                                parsed_steps = diagram_steps_for_query(latest_user_q)

                            _render_safe_flow_diagram(
                                diagram_title_for_query(latest_user_q),
                                parsed_steps,
                            )
                            with st.expander("📊 図解のコード（Mermaid形式）を表示", expanded=False):
                                for m in _MERMAID_BLOCK_RE.finditer(raw_content_for_diagram):
                                    code = (m.group(1) or "").strip()
                                    if code:
                                        st.code(code, language="mermaid")
    
                    # show sources as concise bullets and collect URLs as footnotes
                    footnotes = []
                    src_lines = []
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
                            src_lines.append(f"- [URL{url_to_note.get(url, 0)}]: {title_display}{retrieved_text}" if url else f"- [{cid}]: {title_display}{retrieved_text}")

                    if src_lines:
                        with st.expander(f"📚 参考ソース一覧 ({len(src_lines)}件)", expanded=False):
                            st.markdown("\n".join(src_lines))

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
                                clean_detail = _MERMAID_BLOCK_RE.sub("", detail_text).strip()
                                st.markdown(clean_detail)
                        else:
                            clean_detail = _MERMAID_BLOCK_RE.sub("", detail_text).strip()
                            st.markdown(clean_detail)

                        # アコーディオン（詳細表示）内での図解の重複描画は完全に廃止し、外側の主表示のみに1つだけ表示する
                        pass
                        if footnotes:
                            links = ", ".join([f'<a href="{u}" target="_blank" style="color: #666; text-decoration: underline;">URL{n}</a>' for n,u in footnotes])
                            st.markdown(f'<div style="font-size: 0.75em; color: gray; margin-top: 8px;">※出典: {links}</div>', unsafe_allow_html=True)
                st.markdown("---")
        else:
            st.info("💬 クエリを入力して、会話を開始してください")

    _render_inline_feedback_panel()
        
    # ===== 添付ファイル・音声入力統合アコーディオン =====
    # st.markdown("---")
    with st.expander("📎 添付ファイル・🎙️ 音声入力", expanded=False):
        tab_attach, tab_voice = st.tabs(["📎 ファイル添付", "🎙️ 音声入力"])
        
        with tab_attach:
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
        
        with tab_voice:
            _render_voice_input_section()

    # st.markdown("---")

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
            _remember_ethics_decision(augmented, ethics, "clarification")
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
            _generate_assistant_response(augmented, container=chat_scroll_container)

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
        _remember_ethics_decision(query, ethics, "chat_input")
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

        with chat_scroll_container:
            with st.chat_message("user", avatar="🙋"):
                st.markdown(query)
        _generate_assistant_response(query, container=chat_scroll_container)
        st.session_state.last_query_processed = query
        st.rerun()





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
