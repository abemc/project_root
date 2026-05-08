"""
Streamlit アプリケーション用のサイドバー設定UI統合モジュール

SidebarConfigManager を Streamlit UI に統合し、
ユーザーが簡単に設定を管理できるようにするユーティリティ関数を提供します。
"""

# Streamlit が利用可能な場合のみインポート
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False
    st = None

from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import json
import logging

from .sidebar_config_manager import SidebarConfigManager

logger = logging.getLogger(__name__)


class StreamlitSidebarUI:
    """Streamlit サイドバーUI統合クラス"""
    
    def __init__(self, config_dir: str = "config"):
        """初期化"""
        self.config_manager = SidebarConfigManager(config_dir)
        
        # セッション状態の初期化 (Streamlit 利用可能な場合のみ)
        if STREAMLIT_AVAILABLE and st is not None:
            if "sidebar_config_loaded" not in st.session_state:
                st.session_state.sidebar_config_loaded = False
                st.session_state.sidebar_config = None
    
    def initialize_session_config(self) -> Dict[str, Any]:
        """
        セッション状態に設定を初期化
        
        Returns:
            現在の設定
        """
        if not STREAMLIT_AVAILABLE or st is None:
            raise RuntimeError("Streamlit が利用可能ではありません")
        
        if not st.session_state.sidebar_config_loaded:
            st.session_state.sidebar_config = self.config_manager.load_config()
            st.session_state.sidebar_config_loaded = True
        
        return st.session_state.sidebar_config
    
    def get_session_config(self, section: str) -> Dict[str, Any]:
        """
        セッション状態から設定セクションを取得
        
        Args:
            section: セクション名
        
        Returns:
            セクションのデータ
        """
        self.initialize_session_config()
        return st.session_state.sidebar_config.get(section, {})
    
    def render_basic_settings(self) -> Dict[str, Any]:
        """
        基本設定パネルをレンダリング
        
        Returns:
            基本設定の辞書
        """
        with st.expander("⚙️ 基本設定", expanded=True):
            basic_config = self.get_session_config("basic")
            
            col1, col2 = st.columns(2)
            
            with col1:
                llm_model = st.text_input(
                    "LLM Model Name",
                    value=basic_config.get("llm_model", "qwen2.5:7b"),
                    help="利用可能なモデル名を指定してください（例: qwen2.5:7b）。軽量モデルを指定することで、推論速度が向上します。"
                )
            
            with col2:
                max_steps = st.number_input(
                    "Max Steps",
                    min_value=1,
                    max_value=50,
                    value=basic_config.get("max_steps", 5),
                    help="エージェントの最大思考ステップ数。値を小さくすると回答までの時間が短縮されます。"
                )
            
            return {
                "llm_model": llm_model,
                "max_steps": max_steps
            }
    
    def render_search_settings(self) -> Dict[str, Any]:
        """
        検索・再ランク設定パネルをレンダリング
        
        Returns:
            検索設定の辞書
        """
        with st.expander("🔍 検索・再ランク設定"):
            search_config = self.get_session_config("search")
            
            col1, col2 = st.columns(2)
            
            with col1:
                retrieval_top_k = st.number_input(
                    "Retrieval Top-K",
                    min_value=1,
                    max_value=50,
                    value=search_config.get("retrieval_top_k", 5),
                    help="Retrieverが検索してくるドキュメントの数"
                )
                reranker_model = st.text_input(
                    "Reranker Model",
                    value=search_config.get("reranker_model", "BAAI/bge-reranker-base"),
                    help="HuggingFaceのCross-Encoderモデル名"
                )
            
            with col2:
                rerank_top_k = st.number_input(
                    "Rerank Top-K",
                    min_value=1,
                    max_value=20,
                    value=search_config.get("rerank_top_k", 3),
                    help="Rerank後にLLMに渡すドキュメント数"
                )
                rerank_threshold = st.slider(
                    "Rerank Score Threshold",
                    min_value=0.0,
                    max_value=1.0,
                    value=search_config.get("rerank_threshold", 0.1),
                    step=0.05,
                    help="このスコア未満のドキュメントをRerank後に除外します"
                )
            
            return {
                "retrieval_top_k": retrieval_top_k,
                "reranker_model": reranker_model,
                "rerank_top_k": rerank_top_k,
                "rerank_threshold": rerank_threshold
            }
    
    def render_multimodal_settings(self) -> Dict[str, Any]:
        """
        マルチモーダル設定パネルをレンダリング
        
        Returns:
            マルチモーダル設定の辞書
        """
        with st.expander("🎨 マルチモーダル設定"):
            multimodal_config = self.get_session_config("multimodal")
            
            enable_multimodal = st.checkbox(
                "🖼️ マルチモーダル機能を有効にする",
                value=multimodal_config.get("enabled", True),
                help="画像・音声入力を処理できるようにします"
            )
            
            settings = {"enabled": enable_multimodal}
            
            if enable_multimodal:
                col1, col2 = st.columns(2)
                with col1:
                    settings["vision_model"] = st.selectbox(
                        "ビジョンモデル",
                        ["clip", "blip"],
                        index=["clip", "blip"].index(multimodal_config.get("vision_model", "clip")),
                        help="CLIP: 軽量・高速 / BLIP: より正確な説明生成"
                    )
                    settings["enable_ocr"] = st.checkbox(
                        "OCR有効",
                        value=multimodal_config.get("enable_ocr", True),
                        help="画像内のテキスト抽出"
                    )
                
                with col2:
                    settings["audio_transcription_model"] = st.selectbox(
                        "音声認識",
                        ["whisper-tiny", "whisper-small", "whisper-base"],
                        index=["whisper-tiny", "whisper-small", "whisper-base"].index(
                            multimodal_config.get("audio_transcription_model", "whisper-small")
                        ),
                        help="small/base: より正確、tiny: 高速"
                    )
                
                col3, col4 = st.columns(2)
                with col3:
                    settings["tts_engine"] = st.selectbox(
                        "音声合成",
                        ["edge-tts", "gtts"],
                        index=["edge-tts", "gtts"].index(multimodal_config.get("tts_engine", "edge-tts")),
                        help="edge-tts: 自然（推奨）/ gtts: フォールバック"
                    )
                
                with col4:
                    settings["supported_languages"] = st.multiselect(
                        "サポート言語",
                        ["ja", "en", "zh", "es", "fr", "de", "ko"],
                        default=multimodal_config.get("supported_languages", ["ja", "en"]),
                        help="複数選択可。音声認識・合成に対応"
                    )
                
                settings["show_history"] = st.checkbox(
                    "インタラクション履歴を表示",
                    value=multimodal_config.get("show_history", False)
                )
            else:
                settings.update({
                    "vision_model": None,
                    "enable_ocr": False,
                    "audio_transcription_model": None,
                    "tts_engine": None,
                    "supported_languages": [],
                    "show_history": False
                })
            
            return settings
    
    def render_debug_settings(self) -> Dict[str, Any]:
        """
        デバッグ・学習設定パネルをレンダリング
        
        Returns:
            デバッグ設定の辞書
        """
        with st.expander("🧠 デバッグ・学習設定"):
            debug_config = self.get_session_config("debug")
            
            col1, col2 = st.columns(2)
            
            with col1:
                show_logs = st.checkbox(
                    "エージェントの思考ログを表示",
                    value=debug_config.get("show_logs", True)
                )
                show_debug = st.checkbox(
                    "🛠️ デバッグ情報を表示する",
                    value=debug_config.get("show_debug", False),
                    help="LLMへのプロンプトや生レスポンスを表示します"
                )
            
            with col2:
                show_memories = st.checkbox(
                    "関連する過去の記憶を表示",
                    value=debug_config.get("show_memories", True)
                )
                auto_train_enabled = st.checkbox(
                    "🤖 自動トレーニングを有効にする",
                    value=debug_config.get("auto_train_enabled", False),
                    help="承認済みサンプルが一定数に達した際に、バックグラウンドで学習を試みます"
                )
            
            return {
                "show_logs": show_logs,
                "show_memories": show_memories,
                "show_debug": show_debug,
                "auto_train_enabled": auto_train_enabled
            }
    
    def render_config_management(self) -> None:
        """
        設定管理パネルをレンダリング（保存・復元・エクスポート等）
        """
        with st.expander("💾 設定の管理"):
            st.subheader("設定の保存・復元")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("💾 現在の設定を保存する", use_container_width=True):
                    config = st.session_state.get("sidebar_config", {})
                    if self.config_manager.save_config(config):
                        st.success("✅ 設定を保存しました")
                    else:
                        st.error("❌ 設定の保存に失敗しました")
            
            with col2:
                if st.button("🔄 リセットする", use_container_width=True):
                    if self.config_manager.reset_to_default():
                        st.session_state.sidebar_config = self.config_manager.load_config()
                        st.success("✅ 設定をデフォルト値にリセットしました")
                    else:
                        st.error("❌ リセットに失敗しました")
            
            with col3:
                if st.button("🗑️ バックアップを削除", use_container_width=True):
                    deleted = self.config_manager.cleanup_old_backups(keep_count=5)
                    st.info(f"📦 {deleted}個の古いバックアップを削除しました")
            
            # バックアップから復元
            backups = self.config_manager.list_backups()
            if backups:
                st.subheader("バックアップから復元")
                selected_backup = st.selectbox(
                    "復元するバックアップを選択",
                    backups,
                    format_func=lambda x: Path(x).name
                )
                if st.button("復元する", use_container_width=True):
                    if self.config_manager.restore_backup(selected_backup):
                        st.session_state.sidebar_config = self.config_manager.load_config()
                        st.success("✅ バックアップから復元しました")
                    else:
                        st.error("❌ 復元に失敗しました")
            
            # エクスポート・インポート
            st.divider()
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📤 設定をエクスポート", use_container_width=True):
                    config = st.session_state.get("sidebar_config", {})
                    json_str = json.dumps(config, ensure_ascii=False, indent=2)
                    st.download_button(
                        "JSON をダウンロード",
                        json_str,
                        file_name="sidebar_config.json",
                        mime="application/json"
                    )
            
            with col2:
                uploaded_file = st.file_uploader(
                    "📥 設定をインポート",
                    type=["json"],
                    label_visibility="collapsed"
                )
                if uploaded_file is not None:
                    try:
                        import_config = json.load(uploaded_file)
                        is_valid, errors = self.config_manager.validate_config(import_config)
                        
                        if is_valid:
                            if st.button("インポート", use_container_width=True):
                                if self.config_manager.save_config(import_config):
                                    st.session_state.sidebar_config = import_config
                                    st.success("✅ 設定をインポートしました")
                                else:
                                    st.error("❌ インポートに失敗しました")
                        else:
                            st.error("❌ 設定ファイルが無効です:")
                            for error in errors:
                                st.error(f"  - {error}")
                    except json.JSONDecodeError:
                        st.error("❌ JSON ファイルが無効です")
            
            # 設定情報の表示
            st.subheader("現在の設定")
            current_config = st.session_state.get("sidebar_config", {})
            metadata = current_config.get("metadata", {})
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("作成日時", metadata.get("created_at", "N/A")[:19])
            with col2:
                st.metric("更新日時", metadata.get("updated_at", "N/A")[:19])
    
    def persist_all_settings(self, basic: Dict, search: Dict, 
                            multimodal: Dict, debug: Dict) -> bool:
        """
        すべての設定を一度に保存
        
        Args:
            basic: 基本設定
            search: 検索設定
            multimodal: マルチモーダル設定
            debug: デバッグ設定
        
        Returns:
            成功した場合 True
        """
        config = {
            "basic": basic,
            "search": search,
            "multimodal": multimodal,
            "debug": debug
        }
        
        # セッション状態も更新
        st.session_state.sidebar_config = config
        
        return self.config_manager.save_config(config)
