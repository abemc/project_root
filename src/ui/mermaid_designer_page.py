import os
from pathlib import Path
import streamlit as st
import time
from src.utils.mermaid_repair import request_mermaid_modification, request_mermaid_repair
from src.ui.diagram_renderer import _render_markdown_with_mermaid
from src.ui.code_interpreter_page import is_safe_path, read_interpreter_file, write_interpreter_file
from src.utils.path_utils import PROJECT_ROOT

def display_mermaid_designer():
    st.title("🎨 AI Mermaidデザイナー")
    st.markdown(
        "システム構成図やフローチャートなどのダイアグラムを対話的に設計・編集します。\n"
        "左側でファイルの閲覧や選択、中央でMermaidコードの編集やAIへの修正指示を入力し、右側でリアルタイムプレビューを確認できます。"
    )
    st.markdown("---")

    # サンプルのMermaidダイアグラム
    default_mermaid = (
        "graph TD\n"
        "    A[クライアント] --> B(API ゲートウェイ)\n"
        "    B --> C{認証判定}\n"
        "    C -->|成功| D[Web アプリケーション]\n"
        "    C -->|失敗| E[エラーレスポンス]\n"
        "    D --> F[(データベース)]\n"
    )

    # セッション状態の初期化
    if "mermaid_code" not in st.session_state:
        st.session_state.mermaid_code = default_mermaid
    if "mermaid_error_log" not in st.session_state:
        st.session_state.mermaid_error_log = ""
    if "last_mermaid_explanation" not in st.session_state:
        st.session_state.last_mermaid_explanation = ""
    if "mermaid_open_file_path" not in st.session_state:
        st.session_state.mermaid_open_file_path = None
    if "mermaid_explorer_cwd" not in st.session_state:
        st.session_state.mermaid_explorer_cwd = str(PROJECT_ROOT)

    # 3カラムレイアウト（ファイルブラウザ、エディタ・指示、プレビュー）
    col_explorer, col_edit, col_preview = st.columns([0.23, 0.43, 0.34])

    # 1. 左側: ファイルブラウザ
    with col_explorer:
        st.markdown("### 📁 ワークスペース")
        
        cwd = Path(st.session_state.mermaid_explorer_cwd)
        if not cwd.exists() or not cwd.is_dir():
            cwd = PROJECT_ROOT
            st.session_state.mermaid_explorer_cwd = str(cwd)
            
        # 相対パス表示
        try:
            rel_cwd = cwd.relative_to(PROJECT_ROOT)
            st.caption(f"フォルダ: `./{rel_cwd}`" if str(rel_cwd) != "." else "フォルダ: `[root]`")
        except Exception:
            st.caption(f"フォルダ: `{cwd.name}`")
            
        # 上の階層へ
        if cwd != PROJECT_ROOT and cwd.parent and is_safe_path(str(cwd.parent)):
            if st.button("⬆️ 上の階層へ", key="mermaid_explorer_go_up", use_container_width=True):
                st.session_state.mermaid_explorer_cwd = str(cwd.parent)
                st.rerun()
                
        # フォルダとファイルのリスト
        try:
            items = sorted(cwd.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            
            # 除外リスト
            exclude_names = {".git", "__pycache__", ".pytest_cache", ".venv", ".streamlit"}
            folders = [i for i in items if i.is_dir() and i.name not in exclude_names and not i.name.startswith(".")]
            files = [i for i in items if i.is_file() and not i.name.startswith(".")]
            
            with st.container():
                for folder in folders:
                    if st.button(f"📁 {folder.name}", key=f"mermaid_dir_{folder.name}_{int(folder.stat().st_mtime)}", use_container_width=True):
                        st.session_state.mermaid_explorer_cwd = str(folder)
                        st.rerun()
                        
                for file in files:
                    # Mermaid関連およびテキストファイル
                    if file.suffix in [".mermaid", ".mmd", ".txt", ".md"]:
                        if st.button(f"📄 {file.name}", key=f"mermaid_file_{file.name}_{int(file.stat().st_mtime)}", use_container_width=True):
                            success, content = read_interpreter_file(str(file))
                            if success:
                                st.session_state.mermaid_code = content
                                st.session_state.mermaid_open_file_path = str(file)
                                # 実行エラーと解説もクリア
                                st.session_state.mermaid_error_log = ""
                                st.session_state.last_mermaid_explanation = ""
                                st.rerun()
                            else:
                                st.error(content)
        except Exception as e:
            st.error(f"読み込みエラー: {e}")

    # 2. 中央: 設計エディタ & 指示
    with col_edit:
        st.subheader("🛠 設計エディタ & 指示")
        
        # ファイル(F) 操作メニュー（互換性の高い st.expander を使用）
        with st.expander("📁 ファイル操作メニュー (開く・保存)", expanded=False):
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                # 新規作成
                if st.button("📄 新規ファイル", key="mermaid_menu_new_file", use_container_width=True):
                    st.session_state.mermaid_code = ""
                    st.session_state.mermaid_open_file_path = None
                    st.session_state.last_mermaid_explanation = ""
                    st.session_state.mermaid_error_log = ""
                    st.success("新規ファイルを作成しました。")
                    time.sleep(0.3)
                    st.rerun()
                
                # 上書き保存
                open_file = st.session_state.mermaid_open_file_path
                save_disabled = open_file is None
                if st.button("💾 上書き保存", key="mermaid_menu_save_file", disabled=save_disabled, use_container_width=True):
                    if open_file:
                        success, msg = write_interpreter_file(open_file, st.session_state.mermaid_code)
                        if success:
                            st.success(f"保存しました: {Path(open_file).name}")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(msg)
            
            with col_m2:
                # 名前を付けて保存
                st.markdown("**名前を付けて保存:**")
                save_name = st.text_input("ファイル名", value="", placeholder="diagram.mermaid", key="mermaid_menu_save_as_name", label_visibility="collapsed")
                if st.button("📝 保存実行", key="mermaid_menu_save_as_btn", use_container_width=True):
                    if not save_name.strip():
                        st.warning("ファイル名を入力してください。")
                    else:
                        target_path = Path(st.session_state.mermaid_explorer_cwd) / save_name.strip()
                        success, msg = write_interpreter_file(str(target_path), st.session_state.mermaid_code)
                        if success:
                            st.session_state.mermaid_open_file_path = str(target_path)
                            st.success(f"新規保存しました: {save_name}")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(msg)
                            
        # アクティブファイルのステータス表示
        if st.session_state.mermaid_open_file_path:
            file_name = Path(st.session_state.mermaid_open_file_path).name
            st.markdown(f"<div style='font-size: 0.85em; color: #888; margin-top: 5px; margin-bottom: 5px;'>開いているファイル: <strong>{file_name}</strong></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='font-size: 0.85em; color: #888; margin-top: 5px; margin-bottom: 5px;'>開いているファイル: <strong>新規ファイル (未保存)</strong></div>", unsafe_allow_html=True)

        # 直接編集用テキストエリア（同期バグ対策としてキーをセッション変数に直接紐付け）
        code_input = st.text_area(
            "Mermaidコードを直接編集できます",
            height=320,
            key="mermaid_code"
        )

        # AIへの日本語指示入力
        st.markdown("💡 **AIに図の追加・変更を指示する**")
        user_inst = st.text_input(
            "例: 「Webサーバーの前にキャッシュを追加して」「矢印を双方向にして」",
            value="",
            placeholder="AIに指示する内容を入力...",
            key="mermaid_inst_input"
        )

        model_name = st.session_state.get("llm_model", "gpt-4o-mini")

        col_btn1, col_btn2 = st.columns([0.4, 0.6])
        modify_btn = col_btn1.button("🎨 図を変更", key="apply_mermaid_inst_btn", use_container_width=True)
        clear_btn = col_btn2.button("🧹 エディタを初期状態に戻す", key="reset_mermaid_btn")

        if modify_btn:
            if not user_inst.strip():
                st.warning("⚠️ AIへの指示を入力してください。")
            else:
                with st.spinner("AIがダイアグラムを修正中..."):
                    res = request_mermaid_modification(code_input, user_inst, model_name=model_name)
                    if res["success"]:
                        st.session_state.mermaid_code = res["repaired_code"]
                        st.session_state.last_mermaid_explanation = res["explanation"]
                        st.success("図の修正に成功しました！")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"図の修正に失敗しました: {res['explanation']}")

        if clear_btn:
            st.session_state.mermaid_code = default_mermaid
            st.session_state.last_mermaid_explanation = ""
            st.session_state.mermaid_error_log = ""
            st.session_state.mermaid_open_file_path = None
            st.rerun()

        # 3. 構文エラーの自己修復セクション
        st.markdown("---")
        with st.expander("⚠️ 構文エラー（Syntax Error）の修復"):
            st.caption("レンダリングが壊れたり、構文に誤りがある場合はエラーを入力して修復を依頼できます。")
            err_msg = st.text_area(
                "エラー内容を入力（任意）",
                value=st.session_state.mermaid_error_log,
                placeholder="例: Parse error on line 4...",
                height=80,
                key="mermaid_error_textarea"
            )
            st.session_state.mermaid_error_log = err_msg

            repair_btn = st.button("🤖 AIに構文エラーの修復を依頼する", key="repair_mermaid_syntax_btn", use_container_width=True)
            if repair_btn:
                with st.spinner("AIが構文を修復中..."):
                    res = request_mermaid_repair(code_input, err_msg, model_name=model_name)
                    if res["success"]:
                        st.session_state.mermaid_code = res["repaired_code"]
                        st.session_state.last_mermaid_explanation = res["explanation"]
                        st.success("構文の修復に成功しました！")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"修復に失敗しました: {res['explanation']}")

    # 3. 右側: ダイアグラムプレビュー
    with col_preview:
        st.subheader("👁 ダイアグラムプレビュー")
        
        # 最新の解説文があれば表示
        if st.session_state.last_mermaid_explanation:
            with st.chat_message("assistant"):
                st.markdown(st.session_state.last_mermaid_explanation)
        
        # Mermaidコードのレンダリング
        if st.session_state.mermaid_code.strip():
            markdown_content = f"```mermaid\n{st.session_state.mermaid_code}\n```"
            try:
                # 既存のダイアグラムレンダラーを使用して描画
                _render_markdown_with_mermaid(markdown_content)
            except Exception as e:
                st.error(f"プレビュー描画中にエラーが発生しました: {e}")
                st.caption("Mermaidの構文が正しくない可能性があります。左側の「構文エラーの修復」をお試しください。")
        else:
            st.info("左側のエディタにMermaidコードを記述すると、リアルタイムでプレビューがここに描画されます。")
