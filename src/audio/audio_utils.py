import os
import tempfile
import logging
from src.utils.text_utils import _detect_audio_ext

logger = logging.getLogger(__name__)

# 音声文字起こし
try:
    from faster_whisper import WhisperModel
    faster_whisper_available = True
except ImportError:
    WhisperModel = None
    faster_whisper_available = False

# モデルサイズごとにキャッシュするためモデルインスタンスを辞書で保持
_whisper_model_cache: dict = {}

def get_whisper_model(model_size: str = "tiny"):
    """Whisperモデルをサイズ別キャッシュでロード"""
    if not faster_whisper_available:
        return None
    if model_size not in _whisper_model_cache:
        try:
            _whisper_model_cache[model_size] = WhisperModel(
                model_size, device="cpu", compute_type="int8"
            )
        except Exception as e:
            logger.error(f"Whisperモデル読み込みエラー ({model_size}): {e}")
            return None
    return _whisper_model_cache[model_size]

def transcribe_audio_bytes(audio_bytes: bytes, model_size: str = "tiny") -> str:
    """音声バイトデータをWhisperで文字起こし"""
    if not faster_whisper_available:
        return ""
    model = get_whisper_model(model_size)
    if model is None:
        return ""
    tmp_path = None
    try:
        ext = _detect_audio_ext(audio_bytes)
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        segments, _ = model.transcribe(
            tmp_path,
            language="ja",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=False,
            temperature=0.0,
            no_speech_threshold=0.5,
            # 日本語認識のヒント: 句読点や話し言葉を正しく認識させる
            initial_prompt="日本語の会話です。",
        )
        text = "".join(seg.text.strip() for seg in segments)
        return text
    except Exception as e:
        logger.error(f"音声文字起こしエラー: {e}")
        return ""
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
