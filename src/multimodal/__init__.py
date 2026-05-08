"""マルチモーダル統合パッケージ

自立型LLMに視覚情報（画像認識）と音声処理機能を追加します。
"""

from .vision_module import VisionAnalyzer, ImageAnalysis
from .audio_module import AudioProcessor, AudioTranscription, AudioSynthesis
from .multimodal_integration import MultimodalIntegrator, MultimodalInput, MultimodalOutput

__all__ = [
    "VisionAnalyzer",
    "AudioProcessor",
    "MultimodalIntegrator",
    "ImageAnalysis",
    "AudioTranscription",
    "AudioSynthesis",
    "MultimodalInput",
    "MultimodalOutput",
]
