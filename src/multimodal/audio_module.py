"""オーディオ（音声処理）モジュール

音声認識、音声合成、音声分析などの機能を提供します。
"""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class AudioTranscription:
    """音声認識結果"""
    text: str
    timestamp: str
    duration: float
    language: str
    confidence: float
    segments: List[Dict[str, Any]] = None


@dataclass
class AudioSynthesis:
    """音声合成結果"""
    audio_path: str
    text: str
    timestamp: str
    duration: float
    language: str
    voice: str
    sample_rate: int


class AudioProcessor:
    """音声処理モジュール"""
    
    def __init__(
        self,
        model_name: str = "whisper-small",
        tts_engine: str = "edge-tts",
        cache_dir: str = None
    ):
        """
        Args:
            model_name: 音声認識モデル
            tts_engine: テキスト音声合成エンジン
            cache_dir: キャッシュディレクトリ
        """
        self.model_name = model_name
        self.tts_engine = tts_engine
        self.cache_dir = Path(cache_dir) if cache_dir else Path("models/audio")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.transcription_history: List[AudioTranscription] = []
        self.synthesis_history: List[AudioSynthesis] = []
        
        self._load_models()
    
    def _load_models(self):
        """音声モデルをロード"""
        try:
            import whisper
            logger.info(f"Loading {self.model_name}...")
            self.whisper_model = whisper.load_model(self.model_name)
            logger.info("✅ Whisper model loaded successfully")
        except ImportError:
            logger.warning("Whisper not installed. Speech recognition will not be available.")
            self.whisper_model = None
        except Exception as e:
            logger.error(f"Failed to load Whisper: {e}")
            self.whisper_model = None
        
        try:
            if self.tts_engine == "edge-tts":
                import edge_tts
                logger.info("✅ Edge TTS available")
            elif self.tts_engine == "gtts":
                from gtts import gTTS
                logger.info("✅ gTTS available")
        except ImportError:
            logger.warning(f"{self.tts_engine} not installed. Text-to-speech will not be available.")
    
    def transcribe_audio(
        self,
        audio_path: str,
        language: Optional[str] = None,
    ) -> AudioTranscription:
        """
        音声ファイルを転記
        
        Args:
            audio_path: 音声ファイルパス
            language: 言語コード（例: ja, en）
        
        Returns:
            AudioTranscription オブジェクト
        """
        if self.whisper_model is None:
            raise RuntimeError("Whisper model is not available")
        
        audio_path = Path(audio_path)
        
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        try:
            logger.info(f"Transcribing audio: {audio_path.name}")
            
            # 文字起こし
            result = self.whisper_model.transcribe(
                str(audio_path),
                language=language,
                verbose=False
            )
            
            text = result["text"].strip()
            duration = result.get("duration", 0)
            language = result.get("language", "en")
            
            # セグメント情報
            segments = result.get("segments", [])
            
            # 信頼度計算（セグメントの平均）
            if segments:
                confidence = sum(s.get("confidence", 0) for s in segments) / len(segments)
            else:
                confidence = 0.85
            
            transcription = AudioTranscription(
                text=text,
                timestamp=datetime.now().isoformat(),
                duration=duration,
                language=language,
                confidence=min(confidence, 1.0),
                segments=segments
            )
            
            self.transcription_history.append(transcription)
            logger.info(f"✅ Transcription complete: {len(text)} characters")
            
            return transcription
        
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            raise
    
    def synthesize_speech(
        self,
        text: str,
        output_path: str,
        language: str = "ja",
        voice: Optional[str] = None,
        rate: float = 1.0,
    ) -> AudioSynthesis:
        """
        テキストを音声に合成
        
        Args:
            text: 合成するテキスト
            output_path: 出力ファイルパス
            language: 言語コード（例: ja, en）
            voice: 音声（オプション）
            rate: 音声速度倍率
        
        Returns:
            AudioSynthesis オブジェクト
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            logger.info(f"Synthesizing speech: {len(text)} characters")
            
            if self.tts_engine == "edge-tts":
                return self._synthesize_edge_tts(text, output_path, language, voice, rate)
            elif self.tts_engine == "gtts":
                return self._synthesize_gtts(text, output_path, language)
            else:
                raise ValueError(f"Unknown TTS engine: {self.tts_engine}")
        
        except Exception as e:
            logger.error(f"Error synthesizing speech: {e}")
            raise
    
    def _synthesize_edge_tts(
        self,
        text: str,
        output_path: Path,
        language: str,
        voice: Optional[str],
        rate: float
    ) -> AudioSynthesis:
        """Edge TTS で合成"""
        import asyncio
        import edge_tts
        
        # 言語に応じた音声を選択
        if voice is None:
            voice = self._select_voice(language)
        
        rate_str = f"{rate:+.0%}".replace("+", "")
        
        async def _synthesize():
            communicate = edge_tts.Communicate(text, voice, rate=rate_str)
            await communicate.save(str(output_path))
        
        # イベントループを実行
        try:
            asyncio.run(_synthesize())
        except RuntimeError:
            # 既に実行中のループがある場合
            loop = asyncio.get_event_loop()
            loop.run_until_complete(_synthesize())
        
        # ファイルサイズから推定時間を計算
        file_size = output_path.stat().st_size
        # 一般的に 16bit 44.1kHz の場合、1秒あたり 176400 bytes
        estimated_duration = file_size / 176400 if file_size > 0 else len(text) / 100
        
        synthesis = AudioSynthesis(
            audio_path=str(output_path),
            text=text,
            timestamp=datetime.now().isoformat(),
            duration=estimated_duration,
            language=language,
            voice=voice,
            sample_rate=44100
        )
        
        self.synthesis_history.append(synthesis)
        logger.info(f"✅ Speech synthesis complete: {output_path.name}")
        
        return synthesis
    
    def _synthesize_gtts(
        self,
        text: str,
        output_path: Path,
        language: str
    ) -> AudioSynthesis:
        """gTTS で合成"""
        from gtts import gTTS
        
        tts = gTTS(text=text, lang=language, slow=False)
        tts.save(str(output_path))
        
        # ファイルサイズから推定時間を計算
        file_size = output_path.stat().st_size
        estimated_duration = file_size / 176400 if file_size > 0 else len(text) / 100
        
        synthesis = AudioSynthesis(
            audio_path=str(output_path),
            text=text,
            timestamp=datetime.now().isoformat(),
            duration=estimated_duration,
            language=language,
            voice="gtts",
            sample_rate=44100
        )
        
        self.synthesis_history.append(synthesis)
        logger.info(f"✅ Speech synthesis complete: {output_path.name}")
        
        return synthesis
    
    def _select_voice(self, language: str) -> str:
        """言語に応じた音声を選択"""
        voice_map = {
            "ja": "ja-JP-NanemiNeural",      # 日本語
            "en": "en-US-AriaNeural",        # 英語
            "zh": "zh-CN-XiaoxiaoNeural",    # 中国語
            "es": "es-ES-AlvaroNeural",      # スペイン語
            "fr": "fr-FR-DeniseNeural",      # フランス語
            "de": "de-DE-ConradNeural",      # ドイツ語
            "ko": "ko-KR-InJoonNeural",      # 韓国語
        }
        return voice_map.get(language, "en-US-AriaNeural")
    
    def get_transcription_as_text(self, transcription: AudioTranscription) -> str:
        """
        転記結果をテキスト形式で取得（LLMに提供用）
        
        Args:
            transcription: AudioTranscription オブジェクト
        
        Returns:
            フォーマットされたテキスト
        """
        text = f"""音声認識結果:

📝 内容: {transcription.text}

🌍 言語: {transcription.language}

⏱️ 時間: {transcription.duration:.1f}秒

🔍 信頼度: {transcription.confidence:.0%}

🎯 セグメント数: {len(transcription.segments) if transcription.segments else 0}
"""
        return text
    
    def batch_transcribe(self, audio_paths: List[str]) -> List[AudioTranscription]:
        """
        複数の音声ファイルを一括転記
        
        Args:
            audio_paths: 音声ファイルパスのリスト
        
        Returns:
            転記結果のリスト
        """
        results = []
        for path in audio_paths:
            try:
                result = self.transcribe_audio(path)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to transcribe {path}: {e}")
        
        return results
    
    def get_transcription_history(self, limit: int = 10) -> List[AudioTranscription]:
        """転記履歴を取得"""
        return self.transcription_history[-limit:]
    
    def get_synthesis_history(self, limit: int = 10) -> List[AudioSynthesis]:
        """合成履歴を取得"""
        return self.synthesis_history[-limit:]
