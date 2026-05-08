"""マルチモーダル統合テスト"""

import unittest
import tempfile
from pathlib import Path
from datetime import datetime
import json
import os

# テスト用のモック画像とオーディオデータを作成
try:
    from PIL import Image, ImageDraw
    PIMAGE_AVAILABLE = True
except ImportError:
    PIMAGE_AVAILABLE = False

try:
    import soundfile as sf
    import numpy as np
    AUDIO_TOOLS_AVAILABLE = True
except ImportError:
    AUDIO_TOOLS_AVAILABLE = False


class TestMultimodalIntegrator(unittest.TestCase):
    """マルチモーダルインテグレーターテスト"""
    
    @classmethod
    def setUpClass(cls):
        """テストクラスの初期化"""
        from src.multimodal import MultimodalIntegrator
        cls.integrator = MultimodalIntegrator(cache_dir=tempfile.mkdtemp())
        cls.test_temp_dir = Path(tempfile.mkdtemp())
    
    def test_init_integrator(self):
        """インテグレーター初期化テスト"""
        from src.multimodal import MultimodalIntegrator
        
        integrator = MultimodalIntegrator()
        self.assertIsNotNone(integrator.vision)
        self.assertIsNotNone(integrator.audio)
        self.assertEqual(len(integrator.input_history), 0)
        self.assertEqual(len(integrator.output_history), 0)
    
    def test_process_text_only_input(self):
        """テキストのみ入力処理テスト"""
        text = "これはテストテキストです"
        initial_count = len(self.integrator.input_history)
        
        multimodal_input = self.integrator.process_multimodal_input(
            text=text,
            image_paths=None,
            audio_paths=None
        )
        
        self.assertIsNotNone(multimodal_input)
        self.assertEqual(multimodal_input.text, text)
        self.assertIsNone(multimodal_input.images)
        self.assertIsNone(multimodal_input.audio)
        self.assertEqual(len(self.integrator.input_history), initial_count + 1)
    
    @unittest.skipIf(not PIMAGE_AVAILABLE, "PIL not available")
    def test_process_with_image(self):
        """画像付き入力処理テスト"""
        # テスト用画像を作成
        img = Image.new('RGB', (100, 100), color='red')
        test_image_path = self.test_temp_dir / "test_image.png"
        img.save(test_image_path)
        
        text = "テスト画像"
        multimodal_input = self.integrator.process_multimodal_input(
            text=text,
            image_paths=[str(test_image_path)],
            audio_paths=None
        )
        
        self.assertIsNotNone(multimodal_input)
        self.assertEqual(multimodal_input.text, text)
        # 画像の処理結果（モデルが利用可能な場合）
        if multimodal_input.images:
            self.assertGreater(len(multimodal_input.images), 0)
    
    def test_generate_context_prompt_text_only(self):
        """コンテキストプロンプト生成テスト（テキストのみ）"""
        text = "テストテキスト"
        multimodal_input = self.integrator.process_multimodal_input(text=text)
        
        prompt = self.integrator.generate_context_prompt(multimodal_input)
        
        self.assertIsNotNone(prompt)
        self.assertIn(text, prompt)
        self.assertIn("ユーザー入力:", prompt)
    
    def test_create_response_text_only(self):
        """レスポンス作成テスト（テキストのみ）"""
        text = "テスト"
        multimodal_input = self.integrator.process_multimodal_input(text=text)
        
        response_text = "これはテストレスポンスです"
        multimodal_output = self.integrator.create_response(
            response_text=response_text,
            multimodal_input=multimodal_input,
            synthesize_speech=False
        )
        
        self.assertIsNotNone(multimodal_output)
        self.assertEqual(multimodal_output.response_text, response_text)
        self.assertIsNone(multimodal_output.audio_output)
        self.assertEqual(len(self.integrator.output_history), 1)
    
    def test_get_interaction_summary(self):
        """インタラクション統計テスト"""
        # 複数の入力を処理
        self.integrator.process_multimodal_input(text="テスト1")
        self.integrator.process_multimodal_input(text="テスト2")
        
        summary = self.integrator.get_interaction_summary()
        
        self.assertIsNotNone(summary)
        self.assertGreater(summary["input_count"], 0)
        self.assertIn("modality_usage", summary)
        self.assertIn("timestamp", summary)
    
    def test_get_input_history(self):
        """入力履歴取得テスト"""
        initial_count = len(self.integrator.input_history)
        self.integrator.process_multimodal_input(text="履歴テスト")
        
        history = self.integrator.get_input_history(limit=10)
        
        self.assertIsNotNone(history)
        self.assertGreater(len(history), 0)
        # 履歴項目の構造確認
        if history:
            item = history[0]
            self.assertIn("id", item)
            self.assertIn("timestamp", item)
            self.assertIn("image_count", item)
            self.assertIn("has_audio", item)
    
    def test_export_interaction_log(self):
        """インタラクションログエクスポートテスト"""
        # 入出力データを作成
        inp = self.integrator.process_multimodal_input(text="エクスポートテスト")
        self.integrator.create_response("テストレスポンス", inp)
        
        output_path = self.integrator.export_interaction_log()
        
        self.assertTrue(Path(output_path).exists())
        
        # ファイル内容を確認
        with open(output_path, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
        
        self.assertIn("timestamp", log_data)
        self.assertIn("total_inputs", log_data)
        self.assertIn("total_outputs", log_data)
        self.assertIn("inputs", log_data)
        self.assertIn("outputs", log_data)
    
    def test_multimodal_input_dataclass(self):
        """MultimodalInputデータクラステスト"""
        from src.multimodal import MultimodalInput
        
        inp = MultimodalInput(
            id="test_id",
            timestamp=datetime.now().isoformat(),
            text="テスト",
            images=None,
            audio=None
        )
        
        self.assertEqual(inp.id, "test_id")
        self.assertEqual(inp.text, "テスト")
        self.assertIsNone(inp.images)
        self.assertIsNone(inp.audio)
    
    def test_multimodal_output_dataclass(self):
        """MultimodalOutputデータクラステスト"""
        from src.multimodal import MultimodalOutput
        
        out = MultimodalOutput(
            id="output_id",
            timestamp=datetime.now().isoformat(),
            response_text="レスポンス",
            audio_output=None,
            context={"test": "value"}
        )
        
        self.assertEqual(out.id, "output_id")
        self.assertEqual(out.response_text, "レスポンス")
        self.assertIsNotNone(out.context)


class TestMultimodalConfig(unittest.TestCase):
    """マルチモーダル設定テスト"""
    
    def test_vision_config(self):
        """ビジョン設定テスト"""
        from src.multimodal.config import VisionConfig
        
        config = VisionConfig()
        
        self.assertEqual(config.model_name, "clip")
        self.assertTrue(config.enable_detection)
        self.assertTrue(config.enable_ocr)
        self.assertTrue(config.enable_color_analysis)
        self.assertEqual(config.max_image_size, 1024)
    
    def test_audio_config(self):
        """オーディオ設定テスト"""
        from src.multimodal.config import AudioConfig
        
        config = AudioConfig()
        
        self.assertEqual(config.tts_engine, "edge-tts")
        self.assertEqual(config.default_language, "ja")
        self.assertIn("ja", config.supported_languages)
        self.assertIn("en", config.supported_languages)
    
    def test_multimodal_config(self):
        """マルチモーダル統合設定テスト"""
        from src.multimodal.config import MultimodalConfig
        
        config = MultimodalConfig()
        
        self.assertIsNotNone(config.vision)
        self.assertIsNotNone(config.audio)
        self.assertTrue(config.enable_concurrent_processing)
        self.assertEqual(config.max_concurrent_tasks, 3)
        self.assertTrue(config.save_interaction_history)


class TestVisionModule(unittest.TestCase):
    """ビジョンモジュールテスト"""
    
    def test_vision_analyzer_init(self):
        """VisionAnalyzer初期化テスト"""
        from src.multimodal import VisionAnalyzer
        
        analyzer = VisionAnalyzer(cache_dir=tempfile.mkdtemp())
        
        self.assertIsNotNone(analyzer)
        self.assertEqual(len(analyzer.analysis_history), 0)
    
    @unittest.skipIf(not PIMAGE_AVAILABLE, "PIL not available")
    def test_vision_image_analysis(self):
        """画像分析テスト"""
        from src.multimodal import VisionAnalyzer
        
        # テスト用画像を作成
        img = Image.new('RGB', (100, 100), color='blue')
        test_path = Path(tempfile.mktemp(suffix=".png"))
        img.save(test_path)
        
        try:
            analyzer = VisionAnalyzer(cache_dir=tempfile.mkdtemp())
            analysis = analyzer.analyze_image(str(test_path))
            
            self.assertIsNotNone(analysis)
            # ImageAnalysisの属性確認
            self.assertIsNotNone(analysis.image_path)
            self.assertIsNotNone(analysis.timestamp)
        finally:
            test_path.unlink(missing_ok=True)


class TestAudioModule(unittest.TestCase):
    """オーディオモジュールテスト"""
    
    def test_audio_processor_init(self):
        """AudioProcessor初期化テスト"""
        from src.multimodal import AudioProcessor
        
        processor = AudioProcessor(cache_dir=tempfile.mkdtemp())
        
        self.assertIsNotNone(processor)
        self.assertEqual(len(processor.transcription_history), 0)


def run_tests():
    """テスト実行"""
    # テストスイート作成
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # テストクラスを追加
    suite.addTests(loader.loadTestsFromTestCase(TestMultimodalIntegrator))
    suite.addTests(loader.loadTestsFromTestCase(TestMultimodalConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestVisionModule))
    suite.addTests(loader.loadTestsFromTestCase(TestAudioModule))
    
    # テスト実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 結果サマリー
    print("\n" + "="*70)
    print("テスト結果サマリー")
    print("="*70)
    print(f"実行: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失敗: {len(result.failures)}")
    print(f"エラー: {len(result.errors)}")
    print(f"スキップ: {len(result.skipped)}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
