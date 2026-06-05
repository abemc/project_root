import re
import difflib
import logging
from datetime import datetime
import streamlit as st

logger = logging.getLogger(__name__)

# OneNote 日記モジュール
try:
    import onenote_diary as _onenote
    onenote_available = True
except ImportError:
    onenote_available = False

# LLM モジュールのインポート
try:
    from src.rag.llm import call_llm
    llm_available = True
except ImportError:
    call_llm = None
    llm_available = False

from src.onenote.onenote_settings import _load_onenote_settings, _save_onenote_settings

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
                        if llm_available and call_llm is not None:
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
