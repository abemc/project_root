"""
GPU推論・キャッシング最適化 テスト
"""

import pytest
from src.quality_assurance.gpu_accelerator import (
    GPUAccelerator,
    GPUDeviceType,
    OptimizationLevel
)
from src.quality_assurance.caching_layer import (
    CachingLayer,
    CachePolicy
)


class TestGPUAccelerator:
    """GPUAcceleratorテスト"""
    
    @pytest.fixture
    def gpu_accelerator(self):
        return GPUAccelerator(
            device_type=GPUDeviceType.CUDA,
            device_id=0,
            optimization_level=OptimizationLevel.STANDARD
        )
    
    def test_initialize(self, gpu_accelerator):
        """初期化テスト"""
        result = gpu_accelerator.initialize(total_memory_mb=8000)
        
        assert result is True
        assert gpu_accelerator.is_initialized is True
        assert gpu_accelerator.memory_allocation.total_mb == 8000
    
    def test_configure_batch(self, gpu_accelerator):
        """バッチ設定テスト"""
        gpu_accelerator.configure_batch(
            batch_size=64,
            max_tokens=4096,
            max_batch_time_ms=500.0
        )
        
        assert gpu_accelerator.batch_config.batch_size == 64
        assert gpu_accelerator.batch_config.max_tokens == 4096
    
    def test_optimize_batch(self, gpu_accelerator):
        """バッチ最適化テスト"""
        requests = [
            {"id": "req1", "input_tokens": 100, "priority": 1},
            {"id": "req2", "input_tokens": 200, "priority": 2},
            {"id": "req3", "input_tokens": 150, "priority": 1},
        ]
        
        batches, indices = gpu_accelerator.optimize_batch(requests)
        
        assert len(batches) > 0
        assert len(batches) == len(indices)
    
    def test_allocate_memory(self, gpu_accelerator):
        """メモリ割当テスト"""
        gpu_accelerator.initialize(total_memory_mb=1000)
        
        result = gpu_accelerator.allocate_memory(100)
        
        assert result is True
        assert gpu_accelerator.memory_allocation.used_mb == 100
    
    def test_memory_status(self, gpu_accelerator):
        """メモリ状態取得テスト"""
        gpu_accelerator.initialize(total_memory_mb=1000)
        gpu_accelerator.allocate_memory(500)
        
        status = gpu_accelerator.get_memory_status()
        
        assert status["total_mb"] == 1000
        assert status["used_mb"] == 500
        assert status["utilization_percent"] > 0
    
    def test_record_inference(self, gpu_accelerator):
        """推論メトリクス記録テスト"""
        metrics = gpu_accelerator.record_inference(
            request_id="test_req",
            input_tokens=100,
            output_tokens=50,
            batch_size=1,
            gpu_utilization=75.0
        )
        
        assert metrics.request_id == "test_req"
        assert metrics.input_tokens == 100
        assert metrics.latency_ms > 0
        assert metrics.throughput_tokens_per_sec > 0
    
    def test_optimization_profile(self, gpu_accelerator):
        """最適化プロファイルテスト"""
        profile = gpu_accelerator.create_optimization_profile(
            profile_name="test_profile",
            optimization_level=OptimizationLevel.AGGRESSIVE,
            batch_size=64,
            enable_quantization=True
        )
        
        assert profile.profile_name == "test_profile"
        assert profile.batch_size == 64
        assert profile.enable_quantization is True


class TestCachingLayer:
    """CachingLayerテスト"""
    
    @pytest.fixture
    def cache_layer(self):
        policy = CachePolicy(
            max_entries=100,
            max_size_mb=10.0,
            default_ttl_seconds=600
        )
        return CachingLayer(policy=policy)
    
    def test_put_and_get(self, cache_layer):
        """キャッシュ保存・取得テスト"""
        cache_layer.put("key1", "value1")
        
        result = cache_layer.get("key1")
        
        assert result == "value1"
        assert cache_layer.statistics.hit_count > 0
    
    def test_get_cache_miss(self, cache_layer):
        """キャッシュミステスト"""
        result = cache_layer.get("nonexistent")
        
        assert result is None
        assert cache_layer.statistics.miss_count > 0
    
    def test_delete(self, cache_layer):
        """キャッシュ削除テスト"""
        cache_layer.put("key1", "value1")
        result = cache_layer.delete("key1")
        
        assert result is True
        assert cache_layer.get("key1") is None
    
    def test_clear(self, cache_layer):
        """キャッシュクリアテスト"""
        cache_layer.put("key1", "value1")
        cache_layer.put("key2", "value2")
        
        cache_layer.clear()
        
        assert len(cache_layer.l1_cache) == 0
        assert len(cache_layer.l2_cache) == 0
    
    def test_invalidate_by_ttl(self, cache_layer):
        """TTL無効化テスト"""
        # TTL 1秒で期限切れエントリを作成
        cache_layer.put("key1", "value1", ttl_seconds=1)
        
        import time
        time.sleep(1.1)
        
        invalidated = cache_layer.invalidate_by_ttl()
        
        assert invalidated > 0
        assert cache_layer.get("key1") is None
    
    def test_invalidate_by_pattern(self, cache_layer):
        """パターン無効化テスト"""
        cache_layer.put("analysis:id1", "result1")
        cache_layer.put("analysis:id2", "result2")
        cache_layer.put("other:id1", "result3")
        
        invalidated = cache_layer.invalidate_by_pattern("analysis")
        
        assert invalidated == 2
        assert cache_layer.get("other:id1") is not None
    
    def test_cache_analysis_result(self, cache_layer):
        """分析結果キャッシュテスト"""
        result_data = {"score": 0.95, "status": "trusted"}
        
        cache_layer.cache_analysis_result("analysis_1", result_data)
        retrieved = cache_layer.get_analysis_result("analysis_1")
        
        assert retrieved == result_data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
