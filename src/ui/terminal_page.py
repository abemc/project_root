import streamlit as st
import time
from src.utils.terminal_executor import run_terminal_command, request_command_fix
from src.utils.path_utils import PROJECT_ROOT

def display_terminal():
    st.title("💻 ターミナル・コンソール")
    st.markdown(
        "プロジェクトのディレクトリ空間でコマンドを実行します。\n"
        "セッション中に実行された `cd` による移動状態は自動的に引き継がれます。"
    )
    st.markdown("---")

    # セッション状態の初期化
    if "terminal_cwd" not in st.session_state:
        st.session_state.terminal_cwd = str(PROJECT_ROOT)
    if "terminal_history" not in st.session_state:
        st.session_state.terminal_history = []
    if "last_cmd_failed" not in st.session_state:
        st.session_state.last_cmd_failed = False
    if "last_failed_command" not in st.session_state:
        st.session_state.last_failed_command = ""
    if "last_failed_error" not in st.session_state:
        st.session_state.last_failed_error = ""
    if "command_fix_result" not in st.session_state:
        st.session_state.command_fix_result = None

    # 1. ターミナルログ表示エリア
    st.subheader("🖥 コンソールログ")
    
    # ターミナル風表示用のHTML/CSS構築
    terminal_html = (
        '<div style="background-color: #1e1e1e; color: #f1f1f1; font-family: monospace; '
        'padding: 15px; border-radius: 8px; height: 350px; overflow-y: scroll; border: 1px solid #333; '
        'line-height: 1.4em; white-space: pre-wrap;">'
    )
    
    if not st.session_state.terminal_history:
        terminal_html += '<span style="color: #888;">Welcome to Web Terminal! コマンドを入力して実行してください。<br></span>'
    else:
        for idx, item in enumerate(st.session_state.terminal_history):
            cwd_disp = item.get("cwd", "")
            # プロジェクトルートからの相対表示
            try:
                rel_path = cwd_disp.replace(str(PROJECT_ROOT), "")
                rel_path = rel_path if rel_path else "/"
            except Exception:
                rel_path = cwd_disp
                
            terminal_html += f'<span style="color: #38bdf8;">[{rel_path}] $ {item["cmd"]}</span><br>'
            
            # 標準出力の出力
            if item.get("stdout"):
                terminal_html += f'{item["stdout"]}<br>'
                
            # 標準エラー出力の出力
            if item.get("stderr"):
                terminal_html += f'<span style="color: #f87171;">{item["stderr"]}</span><br>'
                
            # ステータスコード
            if item.get("exit_code") != 0:
                terminal_html += f'<span style="color: #f87171; font-size: 0.9em;">(exit code: {item["exit_code"]})</span><br>'
            terminal_html += '<hr style="border: 0; border-top: 1px dashed #444; margin: 8px 0;">'
            
    terminal_html += '</div>'
    st.markdown(terminal_html, unsafe_allow_html=True)

    # 2. プロンプト入力と実行
    # 表示用のプロンプトパス名
    try:
        current_rel = st.session_state.terminal_cwd.replace(str(PROJECT_ROOT), "")
        current_rel = current_rel if current_rel else "/"
    except Exception:
        current_rel = st.session_state.terminal_cwd

    # フォームを使って送信時の自動クリアと無限ループ防止を実現
    with st.form(key="terminal_command_form", clear_on_submit=True):
        col_prompt, col_run = st.columns([0.85, 0.15])
        with col_prompt:
            cmd_input = st.text_input(
                label="コマンド入力",
                value="",
                placeholder="例: ls -la, git status, cat requirements.txt",
                label_visibility="collapsed",
                key="terminal_command_input"
            )
        run_clicked = col_run.form_submit_button("▶ 送信", use_container_width=True)

    col_ctrl1, col_ctrl2 = st.columns([0.3, 0.7])
    if col_ctrl1.button("🧹 ログをクリア", key="clear_terminal_log_btn"):
        st.session_state.terminal_history = []
        st.session_state.last_cmd_failed = False
        st.session_state.command_fix_result = None
        st.rerun()

    # コマンド実行処理
    if run_clicked and cmd_input.strip():
        command_to_run = cmd_input.strip()
        with st.spinner("コマンドを実行中..."):
            res = run_terminal_command(command_to_run, st.session_state.terminal_cwd)
            
            # 履歴に追加
            st.session_state.terminal_history.append({
                "cmd": command_to_run,
                "cwd": st.session_state.terminal_cwd,
                "stdout": res["output"],
                "stderr": res["error_output"],
                "exit_code": res["exit_code"]
            })
            
            # カレントディレクトリの更新
            st.session_state.terminal_cwd = res["new_cwd"]
            
            # エラー検知の更新
            if res["exit_code"] != 0:
                st.session_state.last_cmd_failed = True
                st.session_state.last_failed_command = command_to_run
                st.session_state.last_failed_error = res["error_output"]
            else:
                st.session_state.last_cmd_failed = False
                st.session_state.command_fix_result = None
                
            st.rerun()

    # 3. AI修復アシスタントUI
    if st.session_state.last_cmd_failed:
        st.markdown("---")
        st.subheader("🤖 AIコマンド修復アシスト")
        st.warning(f"コマンド `{st.session_state.last_failed_command}` はエラーコードで終了しました。")
        
        model_name = st.session_state.get("llm_model", "gpt-4o-mini")
        
        col_fix1, col_fix2 = st.columns([0.4, 0.6])
        fix_btn = col_fix1.button(f"🔎 原因を分析して修正する", key="fix_command_ai_btn", use_container_width=True)
        dismiss_btn = col_fix2.button("❌ 警告を閉じる", key="dismiss_command_warning_btn")
        
        if dismiss_btn:
            st.session_state.last_cmd_failed = False
            st.session_state.command_fix_result = None
            st.rerun()
            
        if fix_btn:
            with st.spinner("AIがエラー原因と修復コマンドを生成中..."):
                fix_res = request_command_fix(
                    st.session_state.last_failed_command,
                    st.session_state.last_failed_error,
                    model_name=model_name
                )
                if fix_res["success"]:
                    st.session_state.command_fix_result = fix_res
                    st.rerun()
                else:
                    st.error(f"修正の生成に失敗しました: {fix_res['explanation']}")

    # 4. 修復結果の表示
    if st.session_state.command_fix_result:
        st.markdown("---")
        st.subheader("💡 AIによる修正提案")
        
        fix_data = st.session_state.command_fix_result
        st.markdown(fix_data["explanation"])
        
        if fix_data["suggested_command"]:
            st.markdown(f"**推奨される修正コマンド:**")
            st.code(fix_data["suggested_command"], language="bash")
            
            if st.button("💡 提案コマンドを今すぐ実行する", key="execute_suggested_cmd_btn", use_container_width=True):
                # 提案されたコマンドを実行
                suggested = fix_data["suggested_command"]
                with st.spinner("提案コマンドを実行中..."):
                    res = run_terminal_command(suggested, st.session_state.terminal_cwd)
                    st.session_state.terminal_history.append({
                        "cmd": suggested,
                        "cwd": st.session_state.terminal_cwd,
                        "stdout": res["output"],
                        "stderr": res["error_output"],
                        "exit_code": res["exit_code"]
                    })
                    st.session_state.terminal_cwd = res["new_cwd"]
                    
                    # 再びエラーか
                    if res["exit_code"] != 0:
                        st.session_state.last_cmd_failed = True
                        st.session_state.last_failed_command = suggested
                        st.session_state.last_failed_error = res["error_output"]
                    else:
                        st.session_state.last_cmd_failed = False
                        st.session_state.command_fix_result = None
                        
                    st.rerun()
