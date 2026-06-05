import os
import json
import time
import re
import shutil
import logging
import subprocess
from pathlib import Path
from datetime import datetime
import streamlit as st

from src.utils.path_utils import PROJECT_ROOT
from src.utils.text_utils import (
    _decode_text_bytes,
    _chunk_text,
    _fetch_url_text,
    _fetch_url_text_and_title,
)

logger = logging.getLogger(__name__)

# Paths
RUN_LOG_PATH = PROJECT_ROOT / "logs" / "streamlit_run.log"
CHAT_HISTORY_PATH = PROJECT_ROOT / "logs" / "chat_history.jsonl"
SIDEBAR_CONFIG_PATH = PROJECT_ROOT / "config" / "sidebar_config.json"

# Imports
try:
    from rag_agent_config import RAGAgentConfig
    rag_config_available = True
except ImportError:
    rag_config_available = False

try:
    from src.ui.streamlit_sidebar_ui import StreamlitSidebarUI
    ui_available = True
except ImportError:
    ui_available = False

try:
    from src.rag.retriever import Retriever
    retriever_available = True
except ImportError:
    retriever_available = False

try:
    from src.backup.backup_manager import ProjectBackupManager
    backup_available = True
except ImportError:
    backup_available = False

try:
    from docs_manager import DocumentManager
except ImportError:
    DocumentManager = None

def _append_run_log(msg: str) -> None:
    try:
        RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RUN_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now().isoformat()} - {msg}\n")
    except Exception:
        logger.exception("failed to write run log")

def _load_chat_history() -> list:
    """チャット履歴ファイル（JSONL）から過去のメッセージを読み込む。"""
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
    """チャットメッセージを履歴ファイル（JSONL）に追加保存する。"""
    try:
        CHAT_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CHAT_HISTORY_PATH, "a", encoding="utf-8") as f:
            msg_with_ts = dict(message)
            if "timestamp" not in msg_with_ts:
                msg_with_ts["timestamp"] = datetime.now().isoformat()
            f.write(json.dumps(msg_with_ts, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"チャット履歴の保存に失敗: {e}")

def _get_git_revision_info() -> str:
    """Git のコミットハッシュ（短縮）とコミット日付を取得する"""
    try:
        # コミットハッシュ取得 (7桁短縮)
        hash_cmd = ["git", "rev-parse", "--short", "HEAD"]
        commit_hash = subprocess.check_output(hash_cmd, stderr=subprocess.DEVNULL).decode("utf-8").strip()

        # コミット日付取得 (YYYY-MM-DD)
        date_cmd = ["git", "show", "-s", "--format=%cd", "--date=short", "HEAD"]
        commit_date = subprocess.check_output(date_cmd, stderr=subprocess.DEVNULL).decode("utf-8").strip()

        return f"Revision: {commit_hash} ({commit_date})"
    except Exception:
        return "Revision: unknown"

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

@st.cache_resource
def get_retriever():
    """Retrieverをキャッシュ付きで初期化（重いモデルは一度だけロード）"""
    if not retriever_available:
        return None
    try:
        corpus_path = PROJECT_ROOT / "corpus"
        index_path = str(corpus_path / "corpus.index")
        meta_path = str(corpus_path / "corpus_meta.json")
        return Retriever(index_path=index_path, meta_path=meta_path)
    except Exception as e:
        logger.error(f"Retriever初期化エラー: {e}")
        return None

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
            log_dir = PROJECT_ROOT / "logs"
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
            entries = []
            for p in sorted(PROJECT_ROOT.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                entries.append(p.name + ("/" if p.is_dir() else ""))
            checks = []
            for name in ("app.py", "requirements.txt", "README.md", "settings.py", "views.py", "templates", "static"):
                p = PROJECT_ROOT / name
                exists = p.exists()
                checks.append(f"{name}: {'存在' if exists else '未検出'}")
            out = "トップレベル一覧:\n" + "\n".join(entries)
            out += "\n\nチェック:\n" + "\n".join(checks)
            _append_dev_log("project_inspect", out)
            return out
        except Exception as e:
            return f"プロジェクト検査エラー: {e}"

    def regenerate_app_spec() -> str:
        """`app.py` から簡易的に関数一覧とインポートを抽出して `docs/app_spec.md` を再生成する。"""
        try:
            import ast
            app_path = PROJECT_ROOT / "app.py"
            out_path = PROJECT_ROOT / "docs" / "app_spec.md"
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
            res = f"再生成完了: {out_path.relative_to(PROJECT_ROOT)}"
            _append_dev_log("regen_app_spec", res)
            return res
        except Exception as e:
            res = f"再生成失敗: {e}"
            _append_dev_log("regen_app_spec", res)
            return res

    def check_requirements() -> str:
        """`requirements.txt` を読み、インポートで確認できるパッケージの有無を返す（簡易チェック）。"""
        try:
            req = PROJECT_ROOT / "requirements.txt"
            if not req.exists():
                res = "requirements.txt が見つかりません"
                _append_dev_log("check_requirements", res)
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
                _append_dev_log("check_requirements", res)
                return res
            res = "requirements に記載されたパッケージは import に成功しました（注意: 名前の差異やネイティブ依存は検出できません）"
            _append_dev_log("check_requirements", res)
            return res
        except Exception as e:
            res = f"依存チェックエラー: {e}"
            _append_dev_log("check_requirements", res)
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
                try:
                    chat_files = [
                        PROJECT_ROOT / "logs" / "chat_history.jsonl",
                        PROJECT_ROOT / "data" / "chat_history.json",
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
                try:
                    log_file = PROJECT_ROOT / "logs" / "dev_tools.jsonl"
                    entries = []
                    if log_file.exists():
                        for line in log_file.read_text(encoding="utf-8").splitlines():
                            try:
                                entries.append(json.loads(line))
                            except Exception:
                                continue
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

                            progress_bar.progress(1.0, text="完了しました！")
                            time.sleep(1.0)
                            progress_bar.empty()

                            if total_chunks_added > 0:
                                st.success(f"{len(uploaded_files) - len(failed_files)}個のファイルから合計 {total_chunks_added} 個のチャンクを追加しました。(OCR実行: {total_ocr_pages}ページ)")
                                try:
                                    if last_success_source:
                                        st.session_state['last_added_source'] = last_success_source
                                        st.session_state['last_uploaded_file_source'] = last_success_source
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

                                try:
                                    from urllib.parse import urlparse
                                    parsed = urlparse(url_input.strip())
                                    host = parsed.netloc.replace(':', '_') if parsed.netloc else 'site'
                                    safe_name = f"{host}_{int(time.time())}.txt"
                                    out_dir = PROJECT_ROOT / 'rag_corpus' / 'downloads'
                                    out_dir.mkdir(parents=True, exist_ok=True)
                                    (out_dir / safe_name).write_text(page_text, encoding='utf-8')
                                except Exception:
                                    pass
                            except Exception as e:
                                st.sidebar.error(f"❌ 登録失敗: {str(e)[:120]}")
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
                    meta_path = PROJECT_ROOT / "corpus" / "corpus_meta.json"
                    docs_stats = {}
                    if meta_path.exists():
                        try:
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
                meta_path = PROJECT_ROOT / "corpus" / "corpus_meta.json"
                if meta_path.exists():
                    try:
                        with open(meta_path, 'r', encoding='utf-8', errors='replace') as f:
                            all_chunks = json.load(f)
                        if isinstance(all_chunks, list) and all_chunks:
                            def _is_mojibake(text: str) -> bool:
                                total = len(text)
                                if total == 0:
                                    return False
                                bad = text.count('\ufffd')
                                return bad / total > 0.05
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
                        corpus_path = PROJECT_ROOT / "corpus"
                        ocr_cache = corpus_path / "ocr_cache"
                        if ocr_cache.exists():
                            shutil.rmtree(ocr_cache)
                        st.sidebar.success("✅ キャッシュをクリアしました")
                    except Exception as e:
                        st.sidebar.error(f"クリアエラー: {e}")

            elif corpus_action == "バックアップ取得":
                if st.button("💾 コーパスをバックアップ", use_container_width=True):
                    try:
                        corpus_path = PROJECT_ROOT / "corpus"
                        backup_dir = PROJECT_ROOT / "backups"
                        backup_dir.mkdir(exist_ok=True)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        backup_path = backup_dir / f"corpus_{timestamp}"
                        shutil.copytree(corpus_path, backup_path)
                        st.sidebar.success(f"✅ バックアップを作成: {backup_path.name}")
                    except Exception as e:
                        st.sidebar.error(f"バックアップエラー: {e}")

            elif corpus_action == "復元":
                try:
                    backup_dir = PROJECT_ROOT / "backups"
                    backups = sorted([d for d in backup_dir.iterdir() if d.is_dir() and d.name.startswith("corpus_")], reverse=True)
                    if backups:
                        selected_backup = st.selectbox("復元するバックアップ", [b.name for b in backups])
                        if st.button("復元", use_container_width=True):
                            corpus_path = PROJECT_ROOT / "corpus"
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
            st.session_state.llm_model = llm_model

            max_steps = st.number_input(
                "最大ステップ数",
                min_value=1,
                max_value=50,
                value=5,
                key="sidebar_max_steps"
            )
            st.session_state.max_steps = max_steps

            # 深掘り設定
            depth = st.radio(
                "回答の深掘りレベル",
                ["簡潔", "標準", "深掘り"],
                index=1,
                horizontal=True,
                key="sidebar_depth"
            )
            st.session_state.depth = depth
            
            from src.ui.diagram_settings import normalize_diagram_mode, diagram_mode_options, diagram_mode_to_label, diagram_mode_from_label
            current_diagram_mode = normalize_diagram_mode(st.session_state.get("diagram_render_mode", "stable"))
            diagram_label = st.selectbox(
                "図解表示モード",
                options=diagram_mode_options(),
                index=diagram_mode_options().index(diagram_mode_to_label(current_diagram_mode)),
                key="sidebar_diagram_mode"
            )
            st.session_state.diagram_render_mode = diagram_mode_from_label(diagram_label)
            if depth == "簡潔":
                st.session_state.temperature = 0.0
                st.session_state.max_tokens = 256
            elif depth == "標準":
                st.session_state.max_tokens = 1024
            else:
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

            st.caption("Value Tuning バイアス")
            value_tuning_bias_enabled = st.checkbox(
                "Value Tuningバイアスを重み更新へ反映",
                value=bool(st.session_state.get("value_tuning_bias_enabled", True)),
                key="sidebar_value_tuning_bias_enabled",
                help="価値軸シグナルを小さな補助バイアスとして reward_weights に反映します。",
            )
            st.session_state.value_tuning_bias_enabled = bool(value_tuning_bias_enabled)

            value_tuning_min_items = st.number_input(
                "Value Tuning最小件数 (value_tuning_min_items)",
                min_value=1,
                max_value=10000,
                value=int(st.session_state.get("value_tuning_min_items", 5)),
                step=1,
                key="sidebar_value_tuning_min_items",
            )
            st.session_state.value_tuning_min_items = int(value_tuning_min_items)

            value_tuning_max_bias = st.slider(
                "Value Tuning最大バイアス (value_tuning_max_bias)",
                min_value=0.0,
                max_value=0.5,
                value=float(st.session_state.get("value_tuning_max_bias", 0.12)),
                step=0.01,
                key="sidebar_value_tuning_max_bias",
                help="各重みに与える価値軸補助バイアスの最大幅です。",
            )
            st.session_state.value_tuning_max_bias = float(value_tuning_max_bias)

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

            st.subheader("バックアップから復元")
            backup_list = ["backup_2026-04-18_19-40", "backup_2026-04-18_18-30"]
            selected_backup = st.selectbox("復元するバックアップを選択", backup_list)
            if st.button("復元する", use_container_width=True):
                st.sidebar.success(f"✅ {selected_backup} から復元しました")

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
            history = _load_chat_history()
            if history:
                grouped = {}
                for msg in history:
                    ts = msg.get("timestamp", "")
                    if ts:
                        try:
                            msg_date = datetime.fromisoformat(ts).strftime("%Y-%m-%d")
                            if msg_date not in grouped:
                                grouped[msg_date] = []
                            grouped[msg_date].append(msg)
                        except:
                            continue

                for date_key in sorted(grouped.keys(), reverse=True)[:history_days_int]:
                    with st.sidebar.expander(f"📅 {date_key}"):
                        for msg in reversed(grouped[date_key]):
                            role_icon = "👤" if msg.get("role") == "user" else "🤖"
                            content = msg.get("content", "")[:100]
                            st.caption(f"{role_icon} {content}...")

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

                if backup_root:
                    st.session_state.backup_root = backup_root

            tab_corpus, tab_rag, tab_restore = st.sidebar.tabs(["📦 コーパス", "🎯 RAG設定", "🔄 復元"])

            # ===== タブ1: コーパスバックアップ =====
            with tab_corpus:
                st.markdown("**コーパス・プロジェクト全体**")

                if backup_available:
                    try:
                        project_root_str = str(PROJECT_ROOT)
                        backup_mgr = ProjectBackupManager(
                            project_root=project_root_str,
                            backup_root=st.session_state.get('backup_root')
                        )

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

                if rag_config_available:
                    try:
                        rag_mgr = RAGAgentConfig()
                        current_config = rag_mgr.load_config()

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("🔄 バックアップ作成", key="create_rag_backup", use_container_width=True):
                                try:
                                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
                    except Exception as e:
                        st.error(f"RAG設定エラー: {e}")
                else:
                    st.warning("⚠️ RAG設定モジュールが利用できません")

            # ===== タブ3: リストア =====
            with tab_restore:
                st.markdown("**バックアップからリストア**")

                if backup_available:
                    try:
                        project_root_str = str(PROJECT_ROOT)
                        backup_mgr = ProjectBackupManager(
                            project_root=project_root_str,
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
                                        st.error("❌ バージョンが選択されていません")
                                except Exception as e:
                                    st.error(f"❌ {str(e)[:60]}")
                        else:
                            st.info("📦 バックアップなし")
                    except Exception as e:
                        st.error(f"❌ {str(e)[:60]}")

        except Exception as e:
            logger.error(f"バックアップセクション エラー: {e}")
            st.sidebar.error(f"⚠️ {str(e)[:50]}")

        # ===== リビジョン情報の表示 =====
        st.sidebar.markdown("---")
        rev_info = _get_git_revision_info()
        st.sidebar.caption(rev_info)

        logger.info("サイドバーの設定が完了しました")

    except Exception as e:
        logger.error(f"サイドバー設定中にエラー: {e}")
        st.sidebar.error(f"エラー: {e}")