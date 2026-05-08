"""マルチモーダル設定"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class VisionConfig:
    """ビジョン処理設定"""
    # モデル設定
    model_name: str = "clip"
    clip_model: str = "openai/clip-vit-base-patch32"
    blip_model: str = "Salesforce/blip-image-captioning-base"
    detr_model: str = "facebook/detr-resnet50"
    tesseract_path: Optional[str] = None  # Tesseractインストールパス
    
    # 処理設定
    max_image_size: int = 1024
    batch_size: int = 4
    enable_detection: bool = True
    enable_ocr: bool = True
    enable_color_analysis: bool = True
    
    # キャッシュ設定
    cache_dir: str = "models/multimodal/vision"
    cache_embeddings: bool = True
    
    # 言語設定
    caption_language: str = "ja"


@dataclass
class AudioConfig:
    """音声処理設定"""
    # 音声認識設定
    transcription_model: str = "whisper-small"
    supported_languages: List[str] = field(default_factory=lambda: [
        "ja", "en", "zh", "es", "fr", "de", "ko"
    ])
    temperature: float = 0.0
    
    # テキスト音声合成設定
    tts_engine: str = "edge-tts"  # edge-tts または gtts
    default_language: str = "ja"
    default_speaker: str = "ja-JP-Nanami"  # edge-ttsの場合
    
    # 音声処理設定
    sample_rate: int = 16000
    chunk_duration: float = 30.0  # 秒
    
    # キャッシュ設定
    cache_dir: str = "models/multimodal/audio"
    cache_transcriptions: bool = True
    
    # 言語別ボイス設定
    voice_mappings: Dict[str, str] = field(default_factory=lambda: {
        "ja": "ja-JP-NanaMi",
        "en": "en-GB-LibbyRyan",
        "zh": "zh-CN-YunfengMale",
        "es": "es-MX-DaliaNeural",
        "fr": "fr-FR-AlainNeural",
        "de": "de-DE-ConradNeural",
        "ko": "ko-KR-InJoonNeural",
    })


@dataclass
class MultimodalConfig:
    """マルチモーダル統合設定"""
    # サブモジュール設定
    vision: VisionConfig = field(default_factory=VisionConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    
    # マルチモーダル設定
    enable_concurrent_processing: bool = True
    max_concurrent_tasks: int = 3
    
    # 履歴管理
    save_interaction_history: bool = True
    history_file: str = "logs/multimodal/interaction_history.jsonl"
    max_history_items: int = 1000
    
    # 出力設定
    output_dir: str = "data/multimodal_outputs"
    default_image_format: str = "png"
    default_audio_format: str = "mp3"
    
    # ロギング設定
    log_level: str = "INFO"
    log_file: str = "logs/multimodal/multimodal.log"
