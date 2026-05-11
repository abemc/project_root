# -*- coding: utf-8 -*-
"""
モデル量子化テスト
Phase 12 Task 2

INT4/INT2 量子化、精度キャリブレーションテスト
"""

import pytest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from inference.quantization import (
    QuantizationType,
    QuantizationAlgorithm,
    QuantizationConfig,
    QuantizationStats,
    QuantizationResult,
    QuantizationCalibrator,
    PerLayerQuantizer,
    PerChannelQuantizer,
    QuantizationEngine,
    KnowledgeDistillationQuantizer,
    create_mock_model_weights,
    create_mock_calibration_batches,
    initialize_quantization_engine,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def quantization_config_int4():
    """INT4 量子化設定"""
    return QuantizationConfig(
        quantization_type=QuantizationType.INT4,
        algorithm=QuantizationAlgorithm.SYMMETRIC,
        calibration_data_size=100,
        num_calibration_batches=10,
    )


@pytest.fixture
def quantization_config_int2():
    """INT2 量子化設定"""
    return QuantizationConfig(
        quantization_type=QuantizationType.INT2,
        algorithm=QuantizationAlgorithm.LOG_SCALE,
        calibration_data_size=50,
        num_calibration_batches=5,
    )


@pytest.fixture
async def mock_weights():
    """モック ウェイト"""
    return await create_mock_model_weights()


@pytest.fixture
async def mock_calibration_batches():
    """モック キャリブレーションバッチ"""
    return await create_mock_calibration_batches()


# ============================================================================
# TestQuantizationConfig
# ============================================================================

class TestQuantizationConfig:
    """量子化設定テスト"""
    
    def test_config_creation_int4(self):
        """INT4 設定作成"""
        config = QuantizationConfig(
            quantization_type=QuantizationType.INT4,
            algorithm=QuantizationAlgorithm.SYMMETRIC,
        )
        
        assert config.quantization_type == QuantizationType.INT4
        assert config.algorithm == QuantizationAlgorithm.SYMMETRIC
        assert config.quantization_type.value == 4
    
    def test_config_creation_int2(self):
        """INT2 設定作成"""
        config = QuantizationConfig(
            quantization_type=QuantizationType.INT2,
            algorithm=QuantizationAlgorithm.LOG_SCALE,
        )
        
        assert config.quantization_type == QuantizationType.INT2
        assert config.algorithm == QuantizationAlgorithm.LOG_SCALE
        assert config.quantization_type.value == 2
    
    def test_config_repr(self):
        """設定の文字列表現"""
        config = QuantizationConfig(
            quantization_type=QuantizationType.INT4,
            algorithm=QuantizationAlgorithm.SYMMETRIC,
        )
        
        repr_str = repr(config)
        assert "INT4" in repr_str
        assert "symmetric" in repr_str


# ============================================================================
# TestQuantizationStats
# ============================================================================

class TestQuantizationStats:
    """量子化統計テスト"""
    
    def test_stats_creation(self):
        """統計作成"""
        stats = QuantizationStats(
            layer_name="layer1.weight",
            original_min=-2.0,
            original_max=2.0,
            scale_factor=0.1,
            mse_loss=0.001,
        )
        
        assert stats.layer_name == "layer1.weight"
        assert stats.original_min == -2.0
        assert stats.original_max == 2.0
        assert stats.scale_factor == 0.1
    
    def test_stats_compression_ratio(self):
        """圧縮率計算"""
        stats = QuantizationStats(
            layer_name="layer1.weight",
            original_min=-1.0,
            original_max=1.0,
            scale_factor=0.05,
            compression_ratio=8.0,  # 8倍圧縮
        )
        
        assert stats.compression_ratio == 8.0


# ============================================================================
# TestQuantizationResult
# ============================================================================

class TestQuantizationResult:
    """量子化結果テスト"""
    
    def test_result_creation(self):
        """結果作成"""
        result = QuantizationResult(
            quantization_type=QuantizationType.INT4,
            original_size_mb=800.0,
            quantized_size_mb=50.0,
            compression_ratio=16.0,
            calibration_time_ms=250.0,
            quantization_time_ms=150.0,
            accuracy_loss_percent=0.5,
            layers_quantized=6,
            total_layers=6,
        )
        
        assert result.quantization_type == QuantizationType.INT4
        assert result.original_size_mb == 800.0
        assert result.quantized_size_mb == 50.0
    
    def test_memory_saved_calculation(self):
        """メモリ節約計算"""
        result = QuantizationResult(
            quantization_type=QuantizationType.INT4,
            original_size_mb=800.0,
            quantized_size_mb=50.0,
            compression_ratio=16.0,
            calibration_time_ms=250.0,
            quantization_time_ms=150.0,
            accuracy_loss_percent=0.5,
            layers_quantized=6,
            total_layers=6,
        )
        
        assert result.memory_saved_mb == 750.0
        assert result.memory_saved_percent == 93.75
    
    def test_result_properties(self):
        """結果プロパティ"""
        result = QuantizationResult(
            quantization_type=QuantizationType.INT2,
            original_size_mb=800.0,
            quantized_size_mb=25.0,
            compression_ratio=32.0,
            calibration_time_ms=200.0,
            quantization_time_ms=100.0,
            accuracy_loss_percent=1.0,
            layers_quantized=6,
            total_layers=6,
        )
        
        saved_percent = result.memory_saved_percent
        assert saved_percent > 95.0  # INT2 目標


# ============================================================================
# TestQuantizationCalibrator
# ============================================================================

class TestQuantizationCalibrator:
    """キャリブレーターテスト"""
    
    def test_calibrator_creation(self, quantization_config_int4):
        """キャリブレーター作成"""
        cal = QuantizationCalibrator(quantization_config_int4)
        
        assert len(cal.stats) == 0
        assert cal.config == quantization_config_int4
    
    def test_add_calibration_batch(self, quantization_config_int4):
        """キャリブレーションバッチ追加"""
        cal = QuantizationCalibrator(quantization_config_int4)
        
        batch = {
            "layer1_output": np.random.randn(32, 128).astype(np.float32),
            "layer2_output": np.random.randn(32, 64).astype(np.float32),
        }
        
        cal.add_calibration_batch(batch)
        
        assert len(cal.stats) == 2
        assert "layer1_output" in cal.stats
        assert "layer2_output" in cal.stats
    
    def test_calibration_stats_update(self, quantization_config_int4):
        """キャリブレーション統計更新"""
        cal = QuantizationCalibrator(quantization_config_int4)
        
        # 最初のバッチ
        batch1 = {
            "layer1": np.array([1.0, 2.0, 3.0, 4.0, 5.0]).reshape(-1, 1).astype(np.float32),
        }
        cal.add_calibration_batch(batch1)
        
        assert cal.stats["layer1"].original_min == 1.0
        assert cal.stats["layer1"].original_max == 5.0
    
    def test_compute_scale_and_zero_point_symmetric(self, quantization_config_int4):
        """スケール・ゼロポイント計算 (対称)"""
        cal = QuantizationCalibrator(quantization_config_int4)
        
        stats = QuantizationStats(
            layer_name="layer1",
            original_min=-2.0,
            original_max=2.0,
        )
        
        scale, zero_point = cal.compute_scale_and_zero_point(stats, bits=4)
        
        assert scale > 0
        assert zero_point == 0


# ============================================================================
# TestPerLayerQuantizer
# ============================================================================

class TestPerLayerQuantizer:
    """レイヤー単位量子化テスト"""
    
    def test_quantizer_creation(self, quantization_config_int4):
        """量子化器作成"""
        quantizer = PerLayerQuantizer(quantization_config_int4)
        
        assert quantizer.config == quantization_config_int4
        assert len(quantizer.layer_stats) == 0
    
    def test_quantize_layer(self, quantization_config_int4):
        """単一レイヤー量子化"""
        quantizer = PerLayerQuantizer(quantization_config_int4)
        
        weights = np.random.randn(128, 512).astype(np.float32)
        stats = QuantizationStats(
            layer_name="layer1",
            original_min=float(np.min(weights)),
            original_max=float(np.max(weights)),
            scale_factor=0.1,
        )
        
        quantized = quantizer.quantize_layer("layer1", weights, stats)
        
        assert quantized.shape == weights.shape
        assert quantized.dtype in [np.uint8, np.int32]


# ============================================================================
# TestPerChannelQuantizer
# ============================================================================

class TestPerChannelQuantizer:
    """チャネル単位量子化テスト"""
    
    def test_per_channel_quantizer_creation(self, quantization_config_int4):
        """チャネル単位量子化器作成"""
        quantizer = PerChannelQuantizer(quantization_config_int4)
        
        assert quantizer.config == quantization_config_int4
    
    def test_quantize_layer_per_channel(self, quantization_config_int4):
        """チャネル単位量子化"""
        quantizer = PerChannelQuantizer(quantization_config_int4)
        
        weights = np.random.randn(128, 512).astype(np.float32)
        
        quantized, channel_stats = quantizer.quantize_layer_per_channel(
            "layer1", weights, num_channels=512
        )
        
        assert quantized.shape == weights.shape
        assert len(channel_stats) == 512


# ============================================================================
# TestQuantizationEngine
# ============================================================================

class TestQuantizationEngine:
    """量子化エンジンテスト"""
    
    def test_engine_creation_int4(self, quantization_config_int4):
        """INT4 エンジン作成"""
        engine = QuantizationEngine(quantization_config_int4)
        
        assert engine.config == quantization_config_int4
        assert len(engine.quantized_models) == 0
    
    def test_engine_creation_int2(self, quantization_config_int2):
        """INT2 エンジン作成"""
        engine = QuantizationEngine(quantization_config_int2)
        
        assert engine.config.quantization_type == QuantizationType.INT2
    
    @pytest.mark.asyncio
    async def test_calibrate_model(self, quantization_config_int4, mock_calibration_batches):
        """モデルキャリブレーション"""
        engine = QuantizationEngine(quantization_config_int4)
        
        stats_dict = await engine.calibrate_model("model1", mock_calibration_batches)
        
        assert len(stats_dict) > 0
    
    @pytest.mark.asyncio
    async def test_quantize_model_int4(
        self, quantization_config_int4, mock_weights, mock_calibration_batches
    ):
        """INT4 モデル量子化"""
        engine = QuantizationEngine(quantization_config_int4)
        
        result = await engine.quantize_model(
            "model1", mock_weights, mock_calibration_batches
        )
        
        assert result.quantization_type == QuantizationType.INT4
        assert result.compression_ratio > 1.0
        assert result.original_size_mb > 0
    
    @pytest.mark.asyncio
    async def test_quantize_model_int2(
        self, quantization_config_int2, mock_weights, mock_calibration_batches
    ):
        """INT2 モデル量子化"""
        engine = QuantizationEngine(quantization_config_int2)
        
        result = await engine.quantize_model(
            "model2", mock_weights, mock_calibration_batches
        )
        
        assert result.quantization_type == QuantizationType.INT2
        assert result.compression_ratio > 8.0  # INT2 は高い圧縮率
    
    def test_compute_compression_stats(self, quantization_config_int4):
        """圧縮統計計算"""
        engine = QuantizationEngine(quantization_config_int4)
        
        original = {
            "layer1": np.random.randn(128, 512).astype(np.float32),
            "layer2": np.random.randn(64, 128).astype(np.float32),
        }
        
        quantized = {
            "layer1": np.random.randint(0, 255, (128, 512), dtype=np.uint8),
            "layer2": np.random.randint(0, 255, (64, 128), dtype=np.uint8),
        }
        
        result = engine.compute_compression_stats(original, quantized, bits=4)
        
        assert result.original_size_mb > 0
        assert result.quantized_size_mb > 0
        assert result.compression_ratio > 1.0
    
    def test_get_model_sizes(self, quantization_config_int4):
        """モデルサイズ統計"""
        engine = QuantizationEngine(quantization_config_int4)
        
        # モデルを追加 (シミュレーション)
        result = QuantizationResult(
            quantization_type=QuantizationType.INT4,
            original_size_mb=800.0,
            quantized_size_mb=50.0,
            compression_ratio=16.0,
            calibration_time_ms=250.0,
            quantization_time_ms=150.0,
            accuracy_loss_percent=0.5,
            layers_quantized=6,
            total_layers=6,
        )
        
        engine.quantized_models["model1"] = {
            "weights": {},
            "stats": {},
            "result": result
        }
        
        sizes = engine.get_model_sizes()
        
        assert "model1" in sizes
        assert sizes["model1"]["compression_ratio"] == 16.0


# ============================================================================
# TestKnowledgeDistillationQuantizer
# ============================================================================

class TestKnowledgeDistillationQuantizer:
    """知識蒸留量子化テスト"""
    
    @pytest.mark.asyncio
    async def test_knowledge_distillation_quantizer(
        self, quantization_config_int4, mock_weights
    ):
        """知識蒸留 + 量子化"""
        engine = QuantizationEngine(quantization_config_int4)
        kd_quantizer = KnowledgeDistillationQuantizer(engine)
        
        teacher_outputs = np.random.randn(100, 10).astype(np.float32)
        calibration_batches = await create_mock_calibration_batches(5)
        
        quantized, kd_loss = await kd_quantizer.distill_and_quantize(
            mock_weights, teacher_outputs, calibration_batches
        )
        
        assert len(quantized) > 0
        assert kd_loss > 0


# ============================================================================
# TestIntegration
# ============================================================================

class TestIntegration:
    """統合テスト"""
    
    @pytest.mark.asyncio
    async def test_initialize_and_quantize(self):
        """初期化と量子化のフロー"""
        config = QuantizationConfig(
            quantization_type=QuantizationType.INT4,
            algorithm=QuantizationAlgorithm.SYMMETRIC,
        )
        
        engine = await initialize_quantization_engine(config)
        
        weights = await create_mock_model_weights()
        batches = await create_mock_calibration_batches()
        
        result = await engine.quantize_model("test_model", weights, batches)
        
        assert result.layers_quantized == result.total_layers


# ============================================================================
# Test実行
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
