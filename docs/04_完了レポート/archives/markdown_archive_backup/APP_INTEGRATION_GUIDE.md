"""
app.py への UI 永続化機能 統合ガイド

このファイルは、app.py に SidebarConfigManager を統合するための
ステップバイステップガイドです。
"""

# ============================================
# STEP 1: インポート文の追加
# ============================================

"""
app.py の最上部（他のインポートの後）に以下を追加:

# --- UI永続化機能のインポート ---
try:
    from src.ui import SidebarConfigManager, StreamlitSidebarUI
except ImportError:
    st.warning("⚠️ UI永続化モジュールが利用できません")
    SidebarConfigManager = None
    StreamlitSidebarUI = None
"""


# ============================================
# STEP 2: セッション初期化のコード追加
# ============================================

"""
st.set_page_config() の直後、サイドバー定義の前に以下を追加:

# --- UI永続化機能の初期化 ---
if SidebarConfigManager and "sidebar_config_manager" not in st.session_state:
    config_dir = BASE_DIR / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    st.session_state.sidebar_config_manager = SidebarConfigManager(str(config_dir))
    st.session_state.sidebar_ui = StreamlitSidebarUI(st.session_state.sidebar_config_manager)
    
    # 保存されている設定を読み込む
    try:
        saved_config = st.session_state.sidebar_config_manager.load_config()
        st.session_state.loaded_config = saved_config
    except Exception as e:
        st.session_state.loaded_config = None
"""


# ============================================
# STEP 3: 基本設定セクションの修正
# ============================================

"""
サイドバーの「基本設定」セクション (104-107行目) を以下のように修正:

    with st.expander("⚙️ 基本設定", expanded=True):
        # 保存された設定があれば読み込む
        if st.session_state.loaded_config and "basic" in st.session_state.loaded_config:
            default_model = st.session_state.loaded_config["basic"].get("llm_model", "qwen2.5:7b")
            default_steps = st.session_state.loaded_config["basic"].get("max_steps", 5)
        else:
            default_model = "qwen2.5:7b"
            default_steps = 5
        
        llm_model = st.text_input(
            "LLM Model Name", 
            value=default_model,
            help="利用可能なモデル名を指定してください（例: qwen2.5:7b）。軽量モデルを指定することで、推論速度が向上します。"
        )
        max_steps = st.number_input(
            "Max Steps", 
            min_value=1, 
            max_value=50, 
            value=default_steps,
            help="エージェントの最大思考ステップ数。値を小さくすると回答までの時間が短縮されます。"
        )
        
        # セッション状態に保存
        st.session_state.basic_config = {
            "llm_model": llm_model,
            "max_steps": max_steps
        }
"""


# ============================================
# STEP 4: 検索設定セクションの修正
# ============================================

"""
「検索・再ランク設定」セクション (109-116行目) を以下のように修正:

    with st.expander("🔍 検索・再ランク設定"):
        # 保存された設定があれば読み込む
        if st.session_state.loaded_config and "search" in st.session_state.loaded_config:
            cfg = st.session_state.loaded_config["search"]
            default_top_k = cfg.get("retrieval_top_k", 5)
            default_reranker = cfg.get("reranker_model", "BAAI/bge-reranker-base")
            default_rerank_k = cfg.get("rerank_top_k", 3)
            default_threshold = cfg.get("rerank_threshold", 0.1)
        else:
            default_top_k = 5
            default_reranker = "BAAI/bge-reranker-base"
            default_rerank_k = 3
            default_threshold = 0.1
        
        retrieval_top_k = st.number_input(
            "Retrieval Top-K", 
            min_value=1, 
            max_value=50, 
            value=default_top_k,
            help="Retrieverが検索してくるドキュメントの数。Rerankerはこの中からさらに絞り込みます。値を小さくすると高速化します。"
        )
        
        reranker_model = st.text_input(
            "Reranker Model", 
            value=default_reranker,
            help="HuggingFaceのCross-Encoderモデル名。largeよりbaseの方が高速です。変更するとモデルのダウンロードが始まります。"
        )
        rerank_top_k = st.number_input(
            "Rerank Top-K", 
            min_value=1, 
            max_value=20, 
            value=default_rerank_k,
            help="Rerank後にLLMに渡すドキュメント数。少ないほどLLMの処理が速くなります。"
        )
        rerank_threshold = st.slider(
            "Rerank Score Threshold", 
            min_value=0.0, 
            max_value=1.0, 
            value=default_threshold,
            step=0.05,
            help="このスコア未満のドキュメントをRerank後に除外します。"
        )
        
        # セッション状態に保存
        st.session_state.search_config = {
            "retrieval_top_k": retrieval_top_k,
            "reranker_model": reranker_model,
            "rerank_top_k": rerank_top_k,
            "rerank_threshold": rerank_threshold
        }
"""


# ============================================
# STEP 5: マルチモーダル設定セクションの修正
# ============================================

"""
「マルチモーダル設定」セクション (171-215行目) を以下のように修正:

    with st.expander("🎨 マルチモーダル設定"):
        # 保存された設定があれば読み込む
        if st.session_state.loaded_config and "multimodal" in st.session_state.loaded_config:
            mm_cfg = st.session_state.loaded_config["multimodal"]
            default_enabled = mm_cfg.get("enabled", True)
            default_vision = mm_cfg.get("vision_model", "clip")
            default_ocr = mm_cfg.get("enable_ocr", True)
            default_transcription = mm_cfg.get("audio_transcription_model", "whisper-small")
            default_tts = mm_cfg.get("tts_engine", "edge-tts")
            default_langs = mm_cfg.get("supported_languages", ["ja", "en"])
            default_history = mm_cfg.get("show_history", False)
        else:
            default_enabled = True
            default_vision = "clip"
            default_ocr = True
            default_transcription = "whisper-small"
            default_tts = "edge-tts"
            default_langs = ["ja", "en"]
            default_history = False
        
        enable_multimodal = st.checkbox(
            "🖼️ マルチモーダル機能を有効にする", 
            value=default_enabled,
            help="画像・音声入力を処理できるようにします。"
        )
        
        vision_model = "clip"
        enable_ocr = True
        audio_transcription_model = "whisper-small"
        tts_engine = "edge-tts"
        supported_languages = ["ja", "en"]
        show_multimodal_history = False
        
        if enable_multimodal:
            col1, col2 = st.columns(2)
            with col1:
                vision_model = st.selectbox(
                    "ビジョンモデル",
                    ["clip", "blip"],
                    index=["clip", "blip"].index(default_vision) if default_vision in ["clip", "blip"] else 0,
                    help="CLIP: 軽量・高速 / BLIP: より正確な説明生成"
                )
            with col2:
                enable_ocr = st.checkbox("OCR有効", value=default_ocr, help="画像内のテキスト抽出")
            
            st.subheader("🎙️ 音声処理")
            col1, col2 = st.columns(2)
            with col1:
                audio_transcription_model = st.selectbox(
                    "音声認識",
                    ["whisper-tiny", "whisper-small", "whisper-base"],
                    index=["whisper-tiny", "whisper-small", "whisper-base"].index(default_transcription) if default_transcription in ["whisper-tiny", "whisper-small", "whisper-base"] else 1,
                    help="small/base: より正確、tiny: 高速"
                )
            with col2:
                tts_engine = st.selectbox(
                    "音声合成",
                    ["edge-tts", "gtts"],
                    index=["edge-tts", "gtts"].index(default_tts) if default_tts in ["edge-tts", "gtts"] else 0,
                    help="edge-tts: 自然（推奨）/ gtts: フォールバック"
                )
            
            supported_languages = st.multiselect(
                "サポート言語",
                ["ja", "en", "zh", "es", "fr", "de", "ko"],
                default=default_langs,
                help="複数選択可。音声認識・合成に対応"
            )
            
            show_multimodal_history = st.checkbox("インタラクション履歴を表示", value=default_history)
        
        st.session_state.multimodal_config = {
            "enabled": enable_multimodal,
            "vision_model": vision_model if enable_multimodal else None,
            "enable_ocr": enable_ocr if enable_multimodal else False,
            "audio_transcription_model": audio_transcription_model if enable_multimodal else None,
            "tts_engine": tts_engine if enable_multimodal else None,
            "supported_languages": supported_languages if enable_multimodal else [],
            "show_history": show_multimodal_history if enable_multimodal else False,
        }
"""


# ============================================
# STEP 6: デバッグ・学習設定セクションの修正
# ============================================

"""
「デバッグ・学習設定」セクション (217-240行目) を以下のように修正:

    with st.expander("🧠 デバッグ・学習設定"):
        # 保存された設定があれば読み込む
        if st.session_state.loaded_config and "debug" in st.session_state.loaded_config:
            db_cfg = st.session_state.loaded_config["debug"]
            default_show_logs = db_cfg.get("show_logs", True)
            default_show_mem = db_cfg.get("show_memories", True)
            default_show_debug = db_cfg.get("show_debug", False)
            default_auto_train = db_cfg.get("auto_train_enabled", False)
        else:
            default_show_logs = True
            default_show_mem = True
            default_show_debug = False
            default_auto_train = False
        
        show_logs = st.checkbox("エージェントの思考ログを表示", value=default_show_logs)
        show_memories = st.checkbox("関連する過去の記憶を表示", value=default_show_mem)
        show_debug = st.checkbox("🛠️ デバッグ情報を表示する", value=default_show_debug, help="LLMへのプロンプトや生レスポンス、ドキュメントのスコア詳細を表示します。")
        auto_train_enabled = st.checkbox("🤖 自動トレーニングを有効にする", value=default_auto_train, help="承認済みサンプルが一定数（例: 50件）に達した際に、バックグラウンドで学習を試みます。GPUリソースが必要です。")
        
        # セッション状態に保存
        st.session_state.debug_config = {
            "show_logs": show_logs,
            "show_memories": show_memories,
            "show_debug": show_debug,
            "auto_train_enabled": auto_train_enabled
        }
        
        # 以下は既存のコード...
        st.divider()
        # ... (他のセクション)
"""


# ============================================
# STEP 7: サイドバー下部に保存ボタンを追加
# ============================================

"""
チャット履歴クリア後（608行目）に以下を追加:

        st.divider()
        
        # --- 設定保存セクション ---
        if SidebarConfigManager and st.session_state.sidebar_config_manager:
            st.subheader("💾 設定管理")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("💾 設定を保存", use_container_width=True):
                    try:
                        # 全ての設定をまとめて保存
                        all_config = {
                            "basic": st.session_state.get("basic_config", {}),
                            "search": st.session_state.get("search_config", {}),
                            "multimodal": st.session_state.get("multimodal_config", {}),
                            "debug": st.session_state.get("debug_config", {})
                        }
                        st.session_state.sidebar_config_manager.save_config(all_config)
                        st.success("✅ 設定を保存しました")
                    except Exception as e:
                        st.error(f"❌ 設定保存エラー: {e}")
            
            with col2:
                if st.button("🔄 デフォルトに戻す", use_container_width=True):
                    try:
                        st.session_state.sidebar_config_manager.reset_to_default()
                        st.success("✅ デフォルト設定に戻しました")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ リセットエラー: {e}")
            
            with col3:
                if st.button("📋 詳細表示", use_container_width=True):
                    try:
                        current_config = st.session_state.sidebar_config_manager.load_config()
                        with st.expander("現在の設定"):
                            st.json(current_config)
                    except Exception as e:
                        st.error(f"❌ 設定読込エラー: {e}")
"""


# ============================================
# STEP 8: オプション - バージョン情報
# ============================================

"""
Status セクションの下に以下を追加（オプション）:

    st.divider()
    
    # バージョン・設定情報
    with st.expander("ℹ️ 設定情報", expanded=False):
        if st.session_state.loaded_config:
            st.caption("✅ 設定ファイルは正常に読み込まれています")
            st.json(st.session_state.loaded_config)
        else:
            st.caption("⚠️ 設定ファイルがまだ保存されていません")
"""


# ============================================
# 修正一覧（クイックリファレンス）
# ============================================

"""
修正ファイル: /home/abemc/project_root/app.py

修正内容:
1. Line ~1-25: インポート追加
2. Line ~30-40: セッション初期化追加
3. Line 104-107: 基本設定セクション修正（default値読込）
4. Line 109-116: 検索設定セクション修正（default値読込）
5. Line 171-215: マルチモーダル設定セクション修正（default値読込）
6. Line 217-240: デバッグ設定セクション修正（default値読込）
7. Line 608+: 保存ボタンセクション追加
8. Line 612+: オプション - バージョン情報追加

合計変更行数: 約80行（新規追加60行 + 修正20行）
"""


# ============================================
# テストキューリスト
# ============================================

"""
統合後のテストチェックリスト:

✅ アプリ起動
   - [] app.py を起動して、エラーが出ないか確認
   - [] サイドバーが正常に表示されるか確認

✅ 初期ロード
   - [] 初回起動時はデフォルト値が表示されるか
   - [] config/sidebar_config.json が作成されるか

✅ 設定保存
   - [] 基本設定を変更して「設定を保存」をクリック
   - [] config/sidebar_config.json に変更が保存されているか
   - [] ブラウザをリロード
   - [] 変更が保存されているか確認

✅ 各セクション
   - [] 基本設定: llm_model, max_steps が保存/復元される
   - [] 検索設定: retrieval_top_k など全項目が保存/復元される
   - [] マルチモーダル: enable のON/OFFが保存/復元される
   - [] デバッグ設定: フラグが保存/復元される

✅ デフォルト復元
   - [] 「デフォルトに戻す」をクリック
   - [] config/sidebar_config.json が初期化されるか
   - [] アプリをリロード
   - [] デフォルト値に戻っているか確認

✅ 詳細表示
   - [] 「詳細表示」をクリック
   - [] 設定が JSON 形式で表示されるか
"""
