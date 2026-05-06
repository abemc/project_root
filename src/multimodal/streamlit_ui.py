"""マルチモーダルStreamlit統合"""

import streamlit as st
import os
from pathlib import Path
from typing import Optional
import tempfile
from datetime import datetime

from .multimodal_integration import MultimodalIntegrator
from .config import MultimodalConfig


def init_multimodal_session():
    """マルチモーダルセッションを初期化"""
    if "multimodal_integrator" not in st.session_state:
        config = MultimodalConfig()
        st.session_state.multimodal_integrator = MultimodalIntegrator(
            vision_model=config.vision.model_name,
            audio_model=config.audio.transcription_model,
            tts_engine=config.audio.tts_engine,
            cache_dir=config.vision.cache_dir
        )
        st.session_state.multimodal_config = config


def render_image_input_section():
    """画像入力セクションを表示"""
    st.subheader("🖼️ 画像入力")
    
    uploaded_files = st.file_uploader(
        "画像をアップロード（複数可）",
        type=["jpg", "jpeg", "png", "bmp", "gif"],
        accept_multiple_files=True
    )
    
    image_paths = []
    if uploaded_files:
        temp_dir = Path(tempfile.gettempdir()) / "multimodal_images"
        temp_dir.mkdir(exist_ok=True)
        
        for uploaded_file in uploaded_files:
            temp_path = temp_dir / uploaded_file.name
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            image_paths.append(str(temp_path))
            
            # 画像をプレビュー表示
            st.image(temp_path, caption=uploaded_file.name, use_column_width=True)
    
    return image_paths


def render_audio_input_section():
    """音声入力セクションを表示"""
    st.subheader("🎙️ 音声入力")
    
    audio_input_type = st.radio("音声入力方法", ["ファイルアップロード"])
    
    audio_paths = []
    if audio_input_type == "ファイルアップロード":
        uploaded_audio = st.file_uploader(
            "音声ファイルをアップロード",
            type=["mp3", "wav", "m4a", "ogg"]
        )
        
        if uploaded_audio:
            temp_dir = Path(tempfile.gettempdir()) / "multimodal_audio"
            temp_dir.mkdir(exist_ok=True)
            
            temp_path = temp_dir / uploaded_audio.name
            with open(temp_path, "wb") as f:
                f.write(uploaded_audio.getbuffer())
            audio_paths.append(str(temp_path))
            
            # 音声プレーヤーを表示
            st.audio(str(temp_path), format="audio/mp3")
    
    return audio_paths


def render_text_input_section():
    """テキスト入力セクションを表示"""
    st.subheader("📝 テキスト入力")
    
    text_input = st.text_area(
        "テキストを入力（オプション）",
        placeholder="ここにテキストを入力...",
        height=100
    )
    
    return text_input if text_input.strip() else None


def render_multimodal_processing_section():
    """マルチモーダル処理セクション"""
    init_multimodal_session()
    
    with st.container():
        st.header("🚀 マルチモーダル処理")
        
        # 入力セクション
        with st.expander("📥 入力", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                image_paths = render_image_input_section()
            
            with col2:
                audio_paths = render_audio_input_section()
            
            text_input = render_text_input_section()
        
        # 処理実行
        if st.button("🔄 処理実行", use_container_width=True):
            with st.spinner("処理中..."):
                try:
                    integrator = st.session_state.multimodal_integrator
                    
                    # マルチモーダル入力を処理
                    multimodal_input = integrator.process_multimodal_input(
                        text=text_input,
                        image_paths=image_paths if image_paths else None,
                        audio_paths=audio_paths if audio_paths else None
                    )
                    
                    st.session_state.last_multimodal_input = multimodal_input
                    st.success("✅ 入力処理完了")
                    
                except Exception as e:
                    st.error(f"❌ エラー: {str(e)}")
        
        # 処理結果の表示
        if "last_multimodal_input" in st.session_state:
            input_obj = st.session_state.last_multimodal_input
            
            st.divider()
            st.subheader("📊 処理結果")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if input_obj.text:
                    st.info(f"📝 テキスト: {input_obj.text[:50]}...")
            with col2:
                if input_obj.images:
                    st.info(f"🖼️ 画像: {len(input_obj.images)}個")
            with col3:
                if input_obj.audio:
                    st.info(f"🎙️ 音声: {input_obj.audio.language}")
            
            # 詳細表示
            with st.expander("📋 詳細", expanded=False):
                if input_obj.text:
                    st.write("**テキスト入力:**")
                    st.write(input_obj.text)
                
                if input_obj.audio:
                    st.write("**音声転記:**")
                    st.write(input_obj.audio.text)
                    st.write(f"言語: {input_obj.audio.language}")
                    st.write(f"信頼度: {input_obj.audio.confidence:.0%}")
                
                if input_obj.images:
                    st.write("**画像分析:**")
                    for i, img in enumerate(input_obj.images, 1):
                        st.write(f"##### 画像 {i}")
                        st.write(f"説明: {img.description}")
                        if img.objects:
                            st.write(f"検出オブジェクト: {', '.join(img.objects)}")
                        if img.text_content:
                            st.write(f"テキスト内容: {img.text_content}")
                        if img.colors:
                            colors_display = ", ".join(f"{c['name']}({c['percentage']}%)" for c in img.colors[:3])
                            st.write(f"主な色: {colors_display}")


def render_response_generation_section():
    """レスポンス生成セクション"""
    if "last_multimodal_input" not in st.session_state:
        st.info("📥 先にマルチモーダル入力を処理してください")
        return
    
    st.header("💬 レスポンス生成")
    
    input_obj = st.session_state.last_multimodal_input
    
    # コンテキストプロンプト表示
    integrator = st.session_state.multimodal_integrator
    context_prompt = integrator.generate_context_prompt(input_obj)
    
    with st.expander("📖 コンテキストプロンプト", expanded=False):
        st.code(context_prompt, language="markdown")
    
    # レスポンス入力
    st.subheader("レスポンステキスト")
    response_text = st.text_area(
        "LLMのレスポンスを入力またはペースト",
        placeholder="ここにレスポンスを入力...",
        height=150
    )
    
    # 音声合成設定
    col1, col2, col3 = st.columns(3)
    with col1:
        synthesize_speech = st.checkbox("🔊 音声合成", value=False)
    with col2:
        speech_language = st.selectbox(
            "言語",
            ["ja", "en", "zh", "es", "fr", "de", "ko"],
            disabled=not synthesize_speech
        )
    with col3:
        st.write("")  # スペーサー
    
    # レスポンス作成
    if st.button("✨ レスポンス作成", use_container_width=True):
        if not response_text.strip():
            st.error("❌ レスポンステキストを入力してください")
            return
        
        with st.spinner("処理中..."):
            try:
                multimodal_output = integrator.create_response(
                    response_text=response_text,
                    multimodal_input=input_obj,
                    synthesize_speech=synthesize_speech,
                    language=speech_language
                )
                
                st.session_state.last_multimodal_output = multimodal_output
                st.success("✅ レスポンス作成完了")
                
            except Exception as e:
                st.error(f"❌ エラー: {str(e)}")
    
    # 出力表示
    if "last_multimodal_output" in st.session_state:
        output_obj = st.session_state.last_multimodal_output
        
        st.divider()
        st.subheader("📤 出力")
        
        # テキスト出力
        st.write("**レスポンステキスト:**")
        st.write(output_obj.response_text)
        
        # 音声出力
        if output_obj.audio_output:
            st.write("**音声出力:**")
            st.audio(output_obj.audio_output.output_path, format="audio/mp3")
            st.write(f"期間: {output_obj.audio_output.duration:.1f}秒")


def render_history_section():
    """履歴セクション"""
    st.header("📜 インタラクション履歴")
    
    integrator = st.session_state.multimodal_integrator
    
    # 統計情報
    summary = integrator.get_interaction_summary()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("入力", summary["input_count"])
    with col2:
        st.metric("出力", summary["output_count"])
    with col3:
        st.metric("処理画像", summary["total_images_processed"])
    with col4:
        st.metric("音声合計", f"{summary['total_audio_duration']:.0f}秒")
    
    # 入力履歴
    st.subheader("最近の入力")
    history = integrator.get_input_history(limit=5)
    
    if history:
        for item in reversed(history):
            with st.expander(f"📥 {item['timestamp']} - ID: {item['id'][:8]}..."):
                if item['text']:
                    st.write(f"📝 テキスト: {item['text']}")
                st.write(f"🖼️ 画像: {item['image_count']}個")
                st.write(f"🎙️ 音声: {'あり' if item['has_audio'] else 'なし'}")
    
    # ログエクスポート
    if st.button("💾 ログをエクスポート"):
        try:
            log_path = integrator.export_interaction_log()
            st.success(f"✅ ログをエクスポート: {log_path}")
        except Exception as e:
            st.error(f"❌ エラー: {str(e)}")


def render_multimodal_dashboard():
    """マルチモーダルダッシュボード"""
    st.set_page_config(
        page_title="🚀 マルチモーダル処理",
        page_icon="🎨",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    init_multimodal_session()
    
    st.title("🎨 マルチモーダル処理ダッシュボード")
    st.write("画像、音声、テキストを統合してLLMで処理します")
    
    # タブで区分
    tab1, tab2, tab3 = st.tabs(["📥 入力と処理", "💬 出力生成", "📜 履歴"])
    
    with tab1:
        render_multimodal_processing_section()
    
    with tab2:
        render_response_generation_section()
    
    with tab3:
        render_history_section()
