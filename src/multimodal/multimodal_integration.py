"""マルチモーダル統合モジュール

複数のモーダル（画像、テキスト、音声）を統合して処理します。
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json

from .vision_module import VisionAnalyzer, ImageAnalysis
from .audio_module import AudioProcessor, AudioTranscription, AudioSynthesis

logger = logging.getLogger(__name__)


@dataclass
class MultimodalInput:
    """マルチモーダル入力"""
    id: str
    timestamp: str
    text: Optional[str] = None
    images: List[ImageAnalysis] = None
    audio: Optional[AudioTranscription] = None


@dataclass
class MultimodalOutput:
    """マルチモーダル出力"""
    id: str
    timestamp: str
    response_text: str
    audio_output: Optional[AudioSynthesis] = None
    context: Dict[str, Any] = None


class MultimodalIntegrator:
    """マルチモーダル統合エンジン"""
    
    def __init__(
        self,
        vision_model: str = "clip",
        audio_model: str = "whisper-small",
        tts_engine: str = "edge-tts",
        cache_dir: str = None
    ):
        """
        Args:
            vision_model: ビジョンモデル
            audio_model: 音声認識モデル
            tts_engine: テキスト音声合成エンジン
            cache_dir: キャッシュディレクトリ
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path("models/multimodal")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 各モジュールの初期化
        self.vision = VisionAnalyzer(model_name=vision_model, cache_dir=str(self.cache_dir / "vision"))
        self.audio = AudioProcessor(
            model_name=audio_model,
            tts_engine=tts_engine,
            cache_dir=str(self.cache_dir / "audio")
        )
        
        self.input_history: List[MultimodalInput] = []
        self.output_history: List[MultimodalOutput] = []
    
    def process_multimodal_input(
        self,
        text: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
        audio_paths: Optional[List[str]] = None,
    ) -> MultimodalInput:
        """
        マルチモーダル入力を処理
        
        Args:
            text: テキスト入力
            image_paths: 画像ファイルパスのリスト
            audio_paths: 音声ファイルパスのリスト
        
        Returns:
            MultimodalInput オブジェクト
        """
        input_id = f"input_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        # 画像処理
        image_analyses = []
        if image_paths:
            for path in image_paths:
                try:
                    analysis = self.vision.analyze_image(path)
                    image_analyses.append(analysis)
                except Exception as e:
                    logger.error(f"Failed to analyze image {path}: {e}")
        
        # 音声処理
        audio_transcription = None
        if audio_paths and len(audio_paths) > 0:
            try:
                # 最初の音声ファイルを転記
                audio_transcription = self.audio.transcribe_audio(audio_paths[0])
            except Exception as e:
                logger.error(f"Failed to transcribe audio: {e}")
        
        # マルチモーダル入力を作成
        multimodal_input = MultimodalInput(
            id=input_id,
            timestamp=datetime.now().isoformat(),
            text=text,
            images=image_analyses if image_analyses else None,
            audio=audio_transcription
        )
        
        self.input_history.append(multimodal_input)
        logger.info(f"✅ Multimodal input processed: {input_id}")
        
        return multimodal_input
    
    def generate_context_prompt(self, multimodal_input: MultimodalInput) -> str:
        """
        マルチモーダル入力からコンテキストプロンプトを生成
        
        Args:
            multimodal_input: MultimodalInput オブジェクト
        
        Returns:
            LLMに提供するコンテキストプロンプト
        """
        context_parts = []
        
        # テキスト部分
        if multimodal_input.text:
            context_parts.append(f"ユーザー入力: {multimodal_input.text}")
        
        # 音声転記
        if multimodal_input.audio:
            context_parts.append(f"\n🎙️ 音声内容: {multimodal_input.audio.text}")
            context_parts.append(f"言語: {multimodal_input.audio.language}")
            context_parts.append(f"信頼度: {multimodal_input.audio.confidence:.0%}")
        
        # 画像分析
        if multimodal_input.images:
            context_parts.append(f"\n🖼️ 画像分析 ({len(multimodal_input.images)}個):")
            for i, image in enumerate(multimodal_input.images, 1):
                context_parts.append(f"\n  画像 {i}:")
                context_parts.append(f"    説明: {image.description}")
                if image.objects:
                    context_parts.append(f"    検出オブジェクト: {', '.join(image.objects)}")
                if image.text_content:
                    context_parts.append(f"    テキスト内容: {image.text_content}")
                if image.colors:
                    colors_str = ", ".join(f"{c['name']}({c['percentage']}%)" for c in image.colors[:2])
                    context_parts.append(f"    主な色: {colors_str}")
                context_parts.append(f"    サイズ: {image.size['width']}x{image.size['height']}px")
        
        prompt = "\n".join(context_parts)
        return prompt
    
    def create_response(
        self,
        response_text: str,
        multimodal_input: MultimodalInput,
        synthesize_speech: bool = False,
        speech_output_path: Optional[str] = None,
        language: str = "ja"
    ) -> MultimodalOutput:
        """
        レスポンスを作成（オプションで音声合成）
        
        Args:
            response_text: レスポンステキスト
            multimodal_input: 元の入力
            synthesize_speech: 音声合成するか
            speech_output_path: 音声出力パス
            language: 音声言語
        
        Returns:
            MultimodalOutput オブジェクト
        """
        output_id = f"output_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        # 音声合成
        audio_output = None
        if synthesize_speech:
            try:
                if speech_output_path is None:
                    speech_output_path = str(self.cache_dir / "outputs" / f"{output_id}.mp3")
                
                audio_output = self.audio.synthesize_speech(
                    text=response_text,
                    output_path=speech_output_path,
                    language=language
                )
            except Exception as e:
                logger.error(f"Failed to synthesize speech: {e}")
        
        # コンテキスト情報
        context = {
            "input_id": multimodal_input.id,
            "input_modalities": {
                "text": multimodal_input.text is not None,
                "images": multimodal_input.images is not None and len(multimodal_input.images) > 0,
                "audio": multimodal_input.audio is not None
            },
            "output_modalities": {
                "text": True,
                "speech": audio_output is not None
            }
        }
        
        multimodal_output = MultimodalOutput(
            id=output_id,
            timestamp=datetime.now().isoformat(),
            response_text=response_text,
            audio_output=audio_output,
            context=context
        )
        
        self.output_history.append(multimodal_output)
        logger.info(f"✅ Multimodal output created: {output_id}")
        
        return multimodal_output
    
    def get_interaction_summary(self) -> Dict[str, Any]:
        """
        インタラクション統計を取得
        
        Returns:
            統計情報
        """
        summary = {
            "timestamp": datetime.now().isoformat(),
            "input_count": len(self.input_history),
            "output_count": len(self.output_history),
            "modality_usage": {
                "text": 0,
                "images": 0,
                "audio": 0
            },
            "total_images_processed": 0,
            "total_audio_duration": 0.0,
        }
        
        # 入力モダリティの統計
        for inp in self.input_history:
            if inp.text:
                summary["modality_usage"]["text"] += 1
            if inp.images:
                summary["modality_usage"]["images"] += 1
                summary["total_images_processed"] += len(inp.images)
            if inp.audio:
                summary["modality_usage"]["audio"] += 1
                summary["total_audio_duration"] += inp.audio.duration
        
        return summary
    
    def get_input_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """入力履歴を取得"""
        history = []
        for inp in self.input_history[-limit:]:
            item = {
                "id": inp.id,
                "timestamp": inp.timestamp,
                "text": inp.text[:100] + "..." if inp.text and len(inp.text) > 100 else inp.text,
                "image_count": len(inp.images) if inp.images else 0,
                "has_audio": inp.audio is not None
            }
            history.append(item)
        return history
    
    def export_interaction_log(self, output_path: str = None) -> str:
        """
        インタラクションログをエクスポート
        
        Args:
            output_path: 出力ファイルパス
        
        Returns:
            ファイルパス
        """
        if output_path is None:
            output_path = str(self.cache_dir / f"interaction_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        log = {
            "timestamp": datetime.now().isoformat(),
            "total_inputs": len(self.input_history),
            "total_outputs": len(self.output_history),
            "inputs": [
                {
                    "id": inp.id,
                    "timestamp": inp.timestamp,
                    "text_length": len(inp.text) if inp.text else 0,
                    "image_count": len(inp.images) if inp.images else 0,
                    "audio_duration": inp.audio.duration if inp.audio else None
                }
                for inp in self.input_history
            ],
            "outputs": [
                {
                    "id": out.id,
                    "timestamp": out.timestamp,
                    "response_length": len(out.response_text),
                    "has_audio": out.audio_output is not None,
                    "context": out.context
                }
                for out in self.output_history
            ]
        }
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(log, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Interaction log exported: {output_path}")
        return output_path
