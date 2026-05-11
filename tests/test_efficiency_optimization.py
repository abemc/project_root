"""
効率性強化エンジン - テストスイート
"""

import pytest
from src.efficiency_optimization.efficiency_engine import (
    QuantizationType, QuantizationConfig,
    DistillationConfig, QuantizationEngine, KnowledgeDistillerEngine,
    FlashAttentionOptimizer, KVCacheOptimizer, EfficiencyOptimizationManager
)


# ==================== QuantizationEngine Tests ====================

class TestQuantizationEngine:
    """量子化エンジンのテスト"""
    
    def test_engine_initialization(self):
        """エンジン初期化テスト"""
        engine = QuantizationEngine()
        assert len(engine.configs) == 0
        assert len(engine.calibration_data) == 0
    
    def test_register_quantization(self):
        """量子化登録テスト"""
        engine = QuantizationEngine()
        config = QuantizationConfig(quantization_type=QuantizationType.INT8)
        success = engine.register_quantization("model_v1", config)
        
        assert success
        assert "model_v1" in engine.configs
    
    def test_add_calibration_data(self):
        """キャリブレーションデータ追加テスト"""
        engine = QuantizationEngine()
        data = [[0.1 * i for i in range(10)] for _ in range(150)]
        engine.add_calibration_data("model_v1", data)
        
        assert "model_v1" in engine.calibration_data
        assert len(engine.calibration_data["model_v1"]) == 100  # 最大100
    
    def test_compute_quantization_params(self):
        """量子化パラメータ計算テスト"""
        engine = QuantizationEngine()
        values = [0.0, 0.5, 1.0, 1.5, 2.0]
        scale, zero_point = engine.compute_quantization_params(values)
        
        assert scale > 0
        assert isinstance(zero_point, float)
    
    def test_quantize_tensor_int8(self):
        """INT8量子化テスト"""
        engine = QuantizationEngine()
        tensor = [0.0, 0.5, 1.0, 1.5, 2.0] * 20
        quantized, scale, zero_point = engine.quantize_tensor(tensor, QuantizationType.INT8)
        
        assert len(quantized) == len(tensor)
        assert all(isinstance(q, int) for q in quantized)
        assert scale > 0
    
    def test_quantize_tensor_int4(self):
        """INT4量子化テスト"""
        engine = QuantizationEngine()
        tensor = [0.0, 0.5, 1.0, 1.5, 2.0] * 20
        quantized, scale, zero_point = engine.quantize_tensor(tensor, QuantizationType.INT4)
        
        assert len(quantized) == len(tensor)
    
    @pytest.mark.asyncio
    async def test_apply_quantization(self):
        """量子化適用テスト"""
        engine = QuantizationEngine()
        config = QuantizationConfig()
        engine.register_quantization("model_v1", config)
        engine.add_calibration_data("model_v1", [[0.1 * i for i in range(10)] for _ in range(50)])
        
        result = await engine.apply_quantization("model_v1")
        
        assert "model" in result
        assert result["model"] == "model_v1"
        assert "statistics" in result
    
    def test_get_size_reduction_int4(self):
        """INT4サイズ削減率テスト"""
        engine = QuantizationEngine()
        original = 1000.0
        reduced = engine.get_size_reduction(original, QuantizationType.INT4)
        
        assert reduced == original / 8
    
    def test_get_size_reduction_int8(self):
        """INT8サイズ削減率テスト"""
        engine = QuantizationEngine()
        original = 1000.0
        reduced = engine.get_size_reduction(original, QuantizationType.INT8)
        
        assert reduced == original / 4


# ==================== KnowledgeDistillerEngine Tests ====================

class TestKnowledgeDistillerEngine:
    """知識蒸留エンジンのテスト"""
    
    def test_engine_initialization(self):
        """エンジン初期化テスト"""
        engine = KnowledgeDistillerEngine()
        assert engine.teacher_model is None
        assert engine.student_model is None
    
    def test_set_teacher_model(self):
        """教師モデル設定テスト"""
        engine = KnowledgeDistillerEngine()
        teacher_config = {"name": "bert_large", "parameters": 340e6}
        success = engine.set_teacher_model(teacher_config)
        
        assert success
        assert engine.teacher_model is not None
    
    def test_set_student_model(self):
        """学生モデル設定テスト"""
        engine = KnowledgeDistillerEngine()
        student_config = {"name": "bert_small", "parameters": 110e6}
        success = engine.set_student_model(student_config)
        
        assert success
        assert engine.student_model is not None
    
    def test_set_distillation_config(self):
        """蒸留設定テスト"""
        engine = KnowledgeDistillerEngine()
        config = DistillationConfig(temperature=4.0, alpha=0.8)
        engine.set_distillation_config(config)
        
        assert engine.config.temperature == 4.0
        assert engine.config.alpha == 0.8
    
    def test_softmax_computation(self):
        """ソフトマックス計算テスト"""
        engine = KnowledgeDistillerEngine()
        values = [1.0, 2.0, 3.0]
        probs = engine._softmax(values, temperature=1.0)
        
        assert len(probs) == 3
        assert abs(sum(probs) - 1.0) < 1e-6
        assert all(0 <= p <= 1 for p in probs)
    
    def test_cross_entropy_computation(self):
        """クロスエントロピー計算テスト"""
        engine = KnowledgeDistillerEngine()
        output = [1.0, 2.0, 3.0]
        target = 2
        ce = engine._compute_cross_entropy(output, target)
        
        assert ce >= 0
    
    @pytest.mark.asyncio
    async def test_compute_distillation_loss(self):
        """蒸留損失計算テスト"""
        engine = KnowledgeDistillerEngine()
        config = DistillationConfig()
        engine.set_distillation_config(config)
        
        teacher_output = [1.0, 2.0, 3.0]
        student_output = [0.9, 1.9, 2.9]
        
        kl_loss, ce_loss, total_loss = await engine.compute_distillation_loss(
            teacher_output, student_output, 2
        )
        
        assert kl_loss >= 0
        assert ce_loss >= 0
        assert total_loss >= 0
    
    @pytest.mark.asyncio
    async def test_train_distillation(self):
        """蒸留訓練テスト"""
        engine = KnowledgeDistillerEngine()
        engine.set_teacher_model({"name": "teacher"})
        engine.set_student_model({"name": "student"})
        engine.set_distillation_config(DistillationConfig(num_epochs=2))
        
        training_data = [
            ([1.0, 2.0, 3.0], 1),
            ([0.5, 1.5, 2.5], 0),
        ] * 30
        
        history = await engine.train_distillation(training_data)
        
        assert "losses" in history
        assert "epoch" in history
        assert history["epoch"] == 2


# ==================== FlashAttentionOptimizer Tests ====================

class TestFlashAttentionOptimizer:
    """Flash Attentionオプティマイザーのテスト"""
    
    def test_optimizer_initialization(self):
        """オプティマイザー初期化テスト"""
        optimizer = FlashAttentionOptimizer()
        assert optimizer.block_size == 256
    
    @pytest.mark.asyncio
    async def test_compute_attention_standard(self):
        """標準Attention計算テスト"""
        optimizer = FlashAttentionOptimizer()
        
        Q = [[1.0, 0.0, 0.0] for _ in range(4)]
        K = [[1.0, 0.0, 0.0] for _ in range(4)]
        V = [[0.1, 0.2, 0.3] for _ in range(4)]
        
        output, memory = await optimizer.compute_attention_standard(Q, K, V)
        
        assert len(output) == 4
        assert memory > 0
    
    @pytest.mark.asyncio
    async def test_compute_attention_flash(self):
        """Flash Attention計算テスト"""
        optimizer = FlashAttentionOptimizer()
        
        Q = [[1.0, 0.0, 0.0] for _ in range(4)]
        K = [[1.0, 0.0, 0.0] for _ in range(4)]
        V = [[0.1, 0.2, 0.3] for _ in range(4)]
        
        output, memory = await optimizer.compute_attention_flash(Q, K, V)
        
        assert len(output) == 4
        assert memory > 0
    
    @pytest.mark.asyncio
    async def test_benchmark_attention(self):
        """Attentionベンチマークテスト"""
        optimizer = FlashAttentionOptimizer()
        result = await optimizer.benchmark_attention(seq_len=2048, hidden_dim=768)
        
        assert "seq_length" in result
        assert "memory_savings_percent" in result
        assert "speedup_estimate" in result
        assert result["memory_savings_percent"] >= 0


# ==================== KVCacheOptimizer Tests ====================

class TestKVCacheOptimizer:
    """KVキャッシュオプティマイザーのテスト"""
    
    def test_optimizer_initialization(self):
        """オプティマイザー初期化テスト"""
        optimizer = KVCacheOptimizer()
        assert optimizer.cache_strategy == "sliding_window"
    
    def test_compute_cache_size(self):
        """キャッシュサイズ計算テスト"""
        optimizer = KVCacheOptimizer()
        size = optimizer.compute_cache_size(
            batch_size=1,
            seq_length=128,
            hidden_dim=768,
            num_layers=12
        )
        
        assert size > 0
    
    def test_apply_sliding_window(self):
        """スライディングウィンドウ適用テスト"""
        optimizer = KVCacheOptimizer()
        cache = [[float(i)] for i in range(1000)]
        windowed = optimizer.apply_sliding_window(cache, window_size=256)
        
        assert len(windowed) == 256
    
    def test_sliding_window_smaller_than_cache(self):
        """キャッシュ < ウィンドウのテスト"""
        optimizer = KVCacheOptimizer()
        cache = [[float(i)] for i in range(100)]
        windowed = optimizer.apply_sliding_window(cache, window_size=256)
        
        assert len(windowed) == 100  # 変更なし
    
    @pytest.mark.asyncio
    async def test_optimize_cache(self):
        """キャッシュ最適化テスト"""
        optimizer = KVCacheOptimizer()
        result = await optimizer.optimize_cache(
            sequence_length=2048,
            hidden_dim=768,
            batch_size=1,
            num_layers=12
        )
        
        assert "original_cache_size_mb" in result
        assert "optimized_cache_size_mb" in result
        assert "cache_savings_percent" in result


# ==================== EfficiencyOptimizationManager Tests ====================

class TestEfficiencyOptimizationManager:
    """効率性最適化統合管理のテスト"""
    
    def test_manager_initialization(self):
        """管理器初期化テスト"""
        manager = EfficiencyOptimizationManager()
        
        assert manager.quantization_engine is not None
        assert manager.distillation_engine is not None
        assert manager.flash_attention_optimizer is not None
        assert manager.kv_cache_optimizer is not None
    
    @pytest.mark.asyncio
    async def test_generate_optimization_plan_large_reduction(self):
        """大規模削減計画生成テスト"""
        manager = EfficiencyOptimizationManager()
        plan = await manager.generate_optimization_plan(
            model_size_mb=1000,
            target_size_mb=100,  # 10倍削減必要
            target_latency_ms=10
        )
        
        assert "recommendations" in plan
        assert len(plan["recommendations"]) > 0
    
    @pytest.mark.asyncio
    async def test_generate_optimization_plan_small_reduction(self):
        """小規模削減計画生成テスト"""
        manager = EfficiencyOptimizationManager()
        plan = await manager.generate_optimization_plan(
            model_size_mb=1000,
            target_size_mb=500,
            target_latency_ms=50
        )
        
        assert "recommendations" in plan
    
    @pytest.mark.asyncio
    async def test_comprehensive_report(self):
        """包括的レポートテスト"""
        manager = EfficiencyOptimizationManager()
        report = await manager.get_comprehensive_report()
        
        assert "optimization_techniques" in report
        assert "timestamp" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
