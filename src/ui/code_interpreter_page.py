import os
import streamlit as st
import time
from pathlib import Path
from src.sandbox.sandbox_executor import SandboxExecutor, SandboxType, ExecutionStatus
from src.utils.self_repair import request_code_repair
from src.utils.path_utils import PROJECT_ROOT

def is_safe_path(target_path: str) -> bool:
    """与えられたパスが許可されたワークスペース配下にあるか検証します。"""
    try:
        resolved = Path(target_path).resolve()
        root_path = PROJECT_ROOT.resolve()
        
        # ワークスペース配下、またはコンテナ内の /app 配下なら安全とする
        is_under_project = (root_path in resolved.parents) or (resolved == root_path)
        is_under_app = (Path("/app").resolve() in resolved.parents) or (resolved == Path("/app").resolve())
        
        return is_under_project or is_under_app
    except Exception:
        return False

def read_interpreter_file(target_path: str) -> tuple[bool, str]:
    """安全にファイル内容を読み込みます。"""
    if not is_safe_path(target_path):
        return False, "Access Denied: Path is outside the authorized workspace."
    try:
        path = Path(target_path)
        if not path.exists() or not path.is_file():
            return False, "File does not exist or is not a file."
        content = path.read_text(encoding="utf-8")
        return True, content
    except Exception as e:
        return False, f"Error reading file: {e}"

def write_interpreter_file(target_path: str, content: str) -> tuple[bool, str]:
    """安全にファイル内容を書き込み・保存します。"""
    if not is_safe_path(target_path):
        return False, "Access Denied: Path is outside the authorized workspace."
    try:
        path = Path(target_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return True, "File saved successfully."
    except Exception as e:
        return False, f"Error writing file: {e}"

def display_code_interpreter():
    # ページヘッダー
    st.title("💻 AIコード・インタープリタ")
    st.markdown(
        "隔離されたサンドボックス環境（セキュリティ制限付きのプロセス空間）で、安全にPythonコードを実行し結果をキャプチャします。\n"
        "エラーが発生した場合は、AI（自己修復機能）が自動的に原因分析と修正コードを提案します。"
    )
    st.markdown("---")

    # サンプルのPythonコード
    default_code = (
        "# サンドボックス実行のサンプルコード\n"
        "import math\n\n"
        "def calculate_circle_area(radius):\n"
        "    return math.pi * (radius ** 2)\n\n"
        "r = 5.0\n"
        "area = calculate_circle_area(r)\n"
        "print(f\"半径 {r} の円の面積: {area:.4f}\")\n"
    )

    # セッション状態の初期化
    if "interpreter_code" not in st.session_state:
        st.session_state.interpreter_code = default_code
    if "interpreter_result" not in st.session_state:
        st.session_state.interpreter_result = None
    if "interpreter_open_file_path" not in st.session_state:
        st.session_state.interpreter_open_file_path = None
    if "explorer_cwd" not in st.session_state:
        st.session_state.explorer_cwd = str(PROJECT_ROOT)

    # 3カラムレイアウト（ファイルブラウザ、エディタ、実行結果）
    col_explorer, col_edit, col_output = st.columns([0.23, 0.43, 0.34])

    # 1. 左側: ファイルブラウザ
    with col_explorer:
        st.markdown("### 📁 ワークスペース")
        
        cwd = Path(st.session_state.explorer_cwd)
        if not cwd.exists() or not cwd.is_dir():
            cwd = PROJECT_ROOT
            st.session_state.explorer_cwd = str(cwd)
            
        # 相対パス表示
        try:
            rel_cwd = cwd.relative_to(PROJECT_ROOT)
            st.caption(f"フォルダ: `./{rel_cwd}`" if str(rel_cwd) != "." else "フォルダ: `[root]`")
        except Exception:
            st.caption(f"フォルダ: `{cwd.name}`")
            
        # 上の階層へ
        if cwd != PROJECT_ROOT and cwd.parent and is_safe_path(str(cwd.parent)):
            if st.button("⬆️ 上の階層へ", key="explorer_go_up", use_container_width=True):
                st.session_state.explorer_cwd = str(cwd.parent)
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
                    if st.button(f"📁 {folder.name}", key=f"dir_{folder.name}_{int(folder.stat().st_mtime)}", use_container_width=True):
                        st.session_state.explorer_cwd = str(folder)
                        st.rerun()
                        
                for file in files:
                    # テキスト編集対象の拡張子に絞り込み
                    if file.suffix in [".py", ".txt", ".md", ".json", ".requirements", ".cfg", ".ini", ".yaml", ".yml"]:
                        if st.button(f"📄 {file.name}", key=f"file_{file.name}_{int(file.stat().st_mtime)}", use_container_width=True):
                            success, content = read_interpreter_file(str(file))
                            if success:
                                st.session_state.interpreter_code = content
                                st.session_state.interpreter_open_file_path = str(file)
                                # 実行結果と修復提案もクリア
                                st.session_state.interpreter_result = None
                                if "last_repair_result" in st.session_state:
                                    del st.session_state.last_repair_result
                                st.rerun()
                            else:
                                st.error(content)
        except Exception as e:
            st.error(f"読み込みエラー: {e}")

    # 2. 中央: エディタとファイルメニュー
    with col_edit:
        st.markdown("### 📝 エディタ")
        
        # ファイル(F) 操作メニュー（互換性の高い st.expander を使用）
        with st.expander("📁 ファイル操作メニュー (開く・保存)", expanded=False):
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                # 新規作成
                if st.button("📄 新規ファイル", key="menu_new_file", use_container_width=True):
                    st.session_state.interpreter_code = ""
                    st.session_state.interpreter_open_file_path = None
                    st.session_state.interpreter_result = None
                    if "last_repair_result" in st.session_state:
                        del st.session_state.last_repair_result
                    st.success("新規ファイルを作成しました。")
                    time.sleep(0.3)
                    st.rerun()
                
                # 上書き保存
                open_file = st.session_state.interpreter_open_file_path
                save_disabled = open_file is None
                if st.button("💾 上書き保存", key="menu_save_file", disabled=save_disabled, use_container_width=True):
                    if open_file:
                        success, msg = write_interpreter_file(open_file, st.session_state.interpreter_code)
                        if success:
                            st.success(f"保存しました: {Path(open_file).name}")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(msg)
            
            with col_m2:
                # 名前を付けて保存
                st.markdown("**名前を付けて保存:**")
                save_name = st.text_input("ファイル名", value="", placeholder="script.py", key="menu_save_as_name", label_visibility="collapsed")
                if st.button("📝 保存実行", key="menu_save_as_btn", use_container_width=True):
                    if not save_name.strip():
                        st.warning("ファイル名を入力してください。")
                    else:
                        target_path = Path(st.session_state.explorer_cwd) / save_name.strip()
                        success, msg = write_interpreter_file(str(target_path), st.session_state.interpreter_code)
                        if success:
                            st.session_state.interpreter_open_file_path = str(target_path)
                            st.success(f"新規保存しました: {save_name}")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(msg)
                            
        # アクティブファイルのステータス表示
        if st.session_state.interpreter_open_file_path:
            file_name = Path(st.session_state.interpreter_open_file_path).name
            st.markdown(f"<div style='font-size: 0.85em; color: #888; margin-top: 5px; margin-bottom: 5px;'>開いているファイル: <strong>{file_name}</strong></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='font-size: 0.85em; color: #888; margin-top: 5px; margin-bottom: 5px;'>開いているファイル: <strong>新規ファイル (未保存)</strong></div>", unsafe_allow_html=True)

        tab_edit, tab_preview = st.tabs(["📝 編集", "📖 Markdownプレビュー"])
        with tab_edit:
            code_input = st.text_area(
                "実行するPythonプログラムを入力してください" if not st.session_state.interpreter_open_file_path or not st.session_state.interpreter_open_file_path.endswith(".md") else "Markdownを編集してください",
                height=300,
                key="interpreter_code"
            )
        with tab_preview:
            if st.session_state.interpreter_code:
                st.markdown(st.session_state.interpreter_code)
            else:
                st.caption("表示するコンテンツがありません。")

        st.caption("※ セキュリティ制限により、一部の危険なコマンドやネットワークアクセスは遮断されます。")

        col_btn1, col_btn2 = st.columns([0.45, 0.55])
        run_btn = col_btn1.button("▶ コードを実行", key="run_interpreter_btn", use_container_width=True)
        clear_btn = col_btn2.button("🧹 エディタをクリア", key="clear_interpreter_btn", use_container_width=True)

        if clear_btn:
            st.session_state.interpreter_code = ""
            st.session_state.interpreter_open_file_path = None
            st.session_state.interpreter_result = None
            if "last_repair_result" in st.session_state:
                del st.session_state.last_repair_result
            st.rerun()

    # 3. 右側: 実行結果
    with col_output:
        st.subheader("🖥 実行結果")
        
        # 実行ボタン押下時の処理
        if run_btn:
            if not code_input.strip():
                st.warning("⚠️ 実行するコードを入力してください。")
            else:
                with st.spinner("サンドボックス環境でコードを実行中..."):
                    executor = SandboxExecutor(SandboxType.SUBPROCESS)
                    result = executor.execute_python_code(code_input)
                    st.session_state.interpreter_result = {
                        "status": result.status,
                        "output": result.output,
                        "error_output": result.error_output,
                        "return_code": result.return_code,
                        "execution_time": result.execution_time,
                        "safety_score": result.safety_score,
                    }

        # 結果の描画
        res = st.session_state.interpreter_result
        if res:
            status = res["status"]
            
            # メタ情報の表示
            col_meta1, col_meta2 = st.columns(2)
            col_meta1.caption(f"ステータス: **{status.value.upper()}** (終了コード: {res['return_code']})")
            col_meta2.caption(f"実行時間: {res['execution_time']:.3f} 秒 / 安全性スコア: {res['safety_score']:.2f}")

            # 正常終了
            if status == ExecutionStatus.SUCCESS:
                st.success("✅ 正常終了")
                if res["output"].strip():
                    st.text_area("標準出力 (Stdout)", value=res["output"], height=200, disabled=True)
                else:
                    st.info("出力はありません（print文などが実行されなかったか、標準出力が空です）。")
            
            # セキュリティブロック
            elif status == ExecutionStatus.SECURITY_BLOCKED:
                st.error("🛡️ セキュリティブロック（ポリシー違反）")
                st.warning(res["error_output"])
                
            # タイムアウト
            elif status == ExecutionStatus.TIMEOUT:
                st.error("⌛ 実行タイムアウト")
                st.warning(res["error_output"])
                
            # エラー終了 (ExecutionStatus.FAILED)
            else:
                st.error("❌ 実行エラー（例外発生）")
                
                # 標準出力があれば表示
                if res["output"].strip():
                    with st.expander("エラー発生前の標準出力 (Stdout)", expanded=False):
                        st.code(res["output"])
                        
                # トレースバック（Stderr）の表示
                st.code(res["error_output"], language="python")

                # AI修復セクション
                st.markdown("---")
                st.markdown("💡 **エラー修復アシスト**")
                
                model_name = st.session_state.get("llm_model", "gpt-4o-mini")
                
                repair_btn = st.button(
                    f"🤖 AIにコードの修復を依頼する (使用モデル: {model_name})",
                    key="repair_code_btn",
                    use_container_width=True
                )
                
                if repair_btn:
                    with st.spinner("AIがエラーを解析して修正コードを生成中..."):
                        repair_res = request_code_repair(
                            code_input,
                            res["error_output"],
                            model_name=model_name
                        )
                        
                        if repair_res["success"]:
                            st.session_state.last_repair_result = repair_res
                            st.rerun()
                        else:
                            st.error(f"修復コードの生成に失敗しました: {repair_res['explanation']}")

        else:
            st.info("コードを入力して「▶ コードを実行」をクリックすると、結果がここに表示されます。")

    # 修復結果の表示 (セッションに残っている場合)
    if "last_repair_result" in st.session_state:
        st.markdown("---")
        st.subheader("🤖 AIによる修正提案")
        
        repair_res = st.session_state.last_repair_result
        
        st.markdown(repair_res["explanation"])
        
        if repair_res["repaired_code"]:
            st.markdown("**提案された修正コード:**")
            st.code(repair_res["repaired_code"], language="python")
            
            col_apply1, col_apply2 = st.columns([0.4, 0.6])
            if col_apply1.button("💡 修正コードをエディタに適用する", key="apply_repaired_code_btn", use_container_width=True):
                st.session_state.interpreter_code = repair_res["repaired_code"]
                # 古い実行結果と修復結果をクリア
                st.session_state.interpreter_result = None
                del st.session_state.last_repair_result
                st.success("エディタの内容を更新しました。再実行してください！")
                time.sleep(1)
                st.rerun()
            
            if col_apply2.button("❌ 提案を却下して閉じる", key="dismiss_proposal_btn"):
                del st.session_state.last_repair_result
                st.rerun()
