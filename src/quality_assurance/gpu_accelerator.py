"""
GPU推論最適化エンジン

GPU推論の最適化、バッチ処理並列化、メモリ管理を実現するシステム
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any


class GPUDeviceType(Enum):
    """GPU デバイスタイプ"""
    CUDA = "cuda"
    ROCM = "rocm"
    METAL = "metal"
    TPU = "tpu"
    CPU = "cpu"


class OptimizationLevel(Enum):
    """最適化レベル"""
    MINIMAL = "minimal"
    STANDARD = "standard"
    AGGRESSIVE = "aggressive"
    MAXIMUM = "maximum"


@dataclass
class BatchConfig:
    """バッチ処理設定"""
    batch_size: int = 32
    max_tokens: int = 2048
    max_batch_time_ms: float = 1000.0
    priority_queue_size: int = 100


@dataclass
class MemoryAllocation:
    """メモリ割当"""
    total_mb: float = 0.0
    used_mb: float = 0.0
    reserved_mb: float = 0.0
    cache_mb: float = 0.0
    available_mb: float = 0.0


@dataclass
class InferenceMetrics:
    """推論メトリクス"""
    request_id: str
    
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    
    input_tokens: int = 0
    output_tokens: int = 0
    
    latency_ms: float = 0.0
    throughput_tokens_per_sec: float = 0.0
    
    batch_size: int = 1
    gpu_utilization_percent: float = 0.0
    memory_used_mb: float = 0.0


@dataclass
class OptimizationProfile:
    """最適化プロファイル"""
    profile_name: str
    optimization_level: OptimizationLevel
    
    batch_size: int = 32
    token_limit: int = 2048
    
    enable_quantization: bool = False
    quantization_bits: int = 8
    
    enable_pruning: bool = False
    pruning_sparsity: float = 0.0
    
    enable_distillation: bool = False
    distillation_temperature: float = 1.0


class GPUAccelerator:
    """GPU推論最適化エンジン"""
    
    def __init__(
        self,
        device_type: GPUDeviceType = GPUDeviceType.CUDA,
        device_id: int = 0,
        optimization_level: OptimizationLevel = OptimizationLevel.STANDARD
    ):
        """初期化"""
        self.device_type = device_type
        self.device_id = device_id
        self.optimization_level = optimization_level
        
        self.batch_config = BatchConfig()
        self.memory_allocation = MemoryAllocation()
        
        self.metrics_history: List[InferenceMetrics] = []
        self.optimization_profiles: Dict[str, OptimizationProfile] = {}
        
        self.is_initialized = False
        self.total_inferences = 0
    
    def initialize(self, total_memory_mb: float = 24000.0) -> bool:
        """GPU デバイスを初期化"""
        
        if self.is_initialized:
            return True
        
        self.memory_allocation.total_mb = total_memory_mb
        self.memory_allocation.available_mb = total_memory_mb
        self.memory_allocation.reserved_mb = total_memory_mb * 0.1  # 予約10%
        self.memory_allocation.available_mb -= self.memory_allocation.reserved_mb
        
        self.is_initialized = True
        return True
    
    def configure_batch(
        self,
        batch_size: int,
        max_tokens: int = 2048,
        max_batch_time_ms: float = 1000.0
    ) -> None:
        """バッチ処理を設定"""
        
        self.batch_config.batch_size = batch_size
        self.batch_config.max_tokens = max_tokens
        self.batch_config.max_batch_time_ms = max_batch_time_ms
    
    def optimize_batch(
        self,
        requests: List[Dict[str, Any]],
        profile_name: Optional[str] = None
    ) -> Tuple[List[List[Dict]], List[int]]:
        """バッチ処理を最適化"""
        
        if not requests:
            return [], []
        
        # プロファイルを取得
        profile = self.optimization_profiles.get(
            profile_name,
            self._get_default_profile()
        )
        
        # リクエストをソート（優先度 + トークン数）
        sorted_requests = sorted(
            requests,
            key=lambda r: (
                -r.get('priority', 0),  # 優先度が高い順
                -r.get('input_tokens', 0)  # トークン数が多い順
            )
        )
        
        # バッチを分割
        batches = []
        batch_indices = []
        current_batch = []
        current_tokens = 0
        current_batch_indices = []
        
        for idx, request in enumerate(sorted_requests):
            tokens = request.get('input_tokens', 100)
            
            # バッチサイズまたはトークン制限に達したか確認
            if (len(current_batch) >= profile.batch_size or
                current_tokens + tokens > profile.token_limit):
                
                if current_batch:
                    batches.append(current_batch)
                    batch_indices.append(current_batch_indices)
                    current_batch = []
                    current_tokens = 0
                    current_batch_indices = []
            
            current_batch.append(request)
            current_batch_indices.append(idx)
            current_tokens += tokens
        
        # 最後のバッチを追加
        if current_batch:
            batches.append(current_batch)
            batch_indices.append(current_batch_indices)
        
        return batches, batch_indices
    
    def allocate_memory(self, required_mb: float) -> bool:
        """メモリを割当"""
        
        if required_mb <= self.memory_allocation.available_mb:
            self.memory_allocation.used_mb += required_mb
            self.memory_allocation.cache_mb += required_mb * 0.2
            self.memory_allocation.available_mb -= required_mb
            return True
        
        return False
    
    def deallocate_memory(self, freed_mb: float) -> None:
        """メモリを解放"""
        
        self.memory_allocation.used_mb -= min(freed_mb, self.memory_allocation.used_mb)
        self.memory_allocation.available_mb += freed_mb
    
    def get_memory_status(self) -> Dict[str, float]:
        """メモリ状態を取得"""
        
        return {
            "total_mb": self.memory_allocation.total_mb,
            "used_mb": self.memory_allocation.used_mb,
            "cache_mb": self.memory_allocation.cache_mb,
            "available_mb": self.memory_allocation.available_mb,
            "utilization_percent": (
                (self.memory_allocation.used_mb / self.memory_allocation.total_mb) * 100
                if self.memory_allocation.total_mb > 0 else 0.0
            )
        }
    
    def record_inference(
        self,
        request_id: str,
        input_tokens: int,
        output_tokens: int,
        batch_size: int = 1,
        gpu_utilization: float = 0.0,
        memory_used_mb: float = 0.0
    ) -> InferenceMetrics:
        """推論メトリクスを記録"""
        
        metrics = InferenceMetrics(
            request_id=request_id,
            start_time=datetime.utcnow(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            batch_size=batch_size,
            gpu_utilization_percent=gpu_utilization,
            memory_used_mb=memory_used_mb
        )
        
        # レイテンシを計算（シミュレーション）
        base_latency = (input_tokens + output_tokens) / 100.0
        batch_latency = base_latency * (1 + (batch_size - 1) * 0.1)
        metrics.latency_ms = batch_latency * 1000.0
        
        # スループットを計算
        total_tokens = input_tokens + output_tokens
        metrics.throughput_tokens_per_sec = (
            total_tokens / (metrics.latency_ms / 1000.0)
            if metrics.latency_ms > 0 else 0.0
        )
        
        metrics.end_time = datetime.utcnow()
        
        self.metrics_history.append(metrics)
        self.total_inferences += 1
        
        return metrics
    
    def get_performance_statistics(self) -> Dict[str, float]:
        """パフォーマンス統計を取得"""
        
        if not self.metrics_history:
            return {
                "total_inferences": 0,
                "average_latency_ms": 0.0,
                "average_throughput_tokens_per_sec": 0.0,
                "average_gpu_utilization": 0.0,
                "average_batch_size": 0.0
            }
        
        avg_latency = sum(m.latency_ms for m in self.metrics_history) / len(self.metrics_history)
        avg_throughput = sum(m.throughput_tokens_per_sec for m in self.metrics_history) / len(self.metrics_history)
        avg_gpu = sum(m.gpu_utilization_percent for m in self.metrics_history) / len(self.metrics_history)
        avg_batch = sum(m.batch_size for m in self.metrics_history) / len(self.metrics_history)
        
        return {
            "total_inferences": len(self.metrics_history),
            "average_latency_ms": avg_latency,
            "average_throughput_tokens_per_sec": avg_throughput,
            "average_gpu_utilization": avg_gpu,
            "average_batch_size": avg_batch
        }
    
    def create_optimization_profile(
        self,
        profile_name: str,
        optimization_level: OptimizationLevel,
        batch_size: int = 32,
        token_limit: int = 2048,
        enable_quantization: bool = False,
        enable_pruning: bool = False
    ) -> OptimizationProfile:
        """最適化プロファイルを作成"""
        
        profile = OptimizationProfile(
            profile_name=profile_name,
            optimization_level=optimization_level,
            batch_size=batch_size,
            token_limit=token_limit,
            enable_quantization=enable_quantization,
            enable_pruning=enable_pruning
        )
        
        self.optimization_profiles[profile_name] = profile
        return profile
    
    def _get_default_profile(self) -> OptimizationProfile:
        """デフォルトプロファイルを取得"""
        
        return OptimizationProfile(
            profile_name="default",
            optimization_level=self.optimization_level,
            batch_size=self.batch_config.batch_size,
            token_limit=self.batch_config.max_tokens
        )
    
    def estimate_inference_time(
        self,
        input_tokens: int,
        output_tokens: int,
        batch_size: int = 1
    ) -> float:
        """推論時間を推定"""
        
        # 基本的なレイテンシモデル
        base_time_ms = (input_tokens + output_tokens) * 0.5
        batch_multiplier = 1.0 + (batch_size - 1) * 0.05
        
        return base_time_ms * batch_multiplier
    
    def get_optimization_recommendations(self) -> List[str]:
        """最適化推奨事項を取得"""
        
        recommendations = []
        
        if not self.metrics_history:
            return recommendations
        
        # メモリ使用率チェック
        memory_status = self.get_memory_status()
        if memory_status["utilization_percent"] > 80:
            recommendations.append("メモリ使用率が高い。バッチサイズを削減検討")
        
        # GPU使用率チェック
        avg_gpu = sum(m.gpu_utilization_percent for m in self.metrics_history[-10:]) / min(10, len(self.metrics_history))
        if avg_gpu < 30:
            recommendations.append("GPU使用率が低い。バッチサイズを増加検討")
        
        # 平均バッチサイズ
        avg_batch = sum(m.batch_size for m in self.metrics_history[-10:]) / min(10, len(self.metrics_history))
        if avg_batch < self.batch_config.batch_size * 0.5:
            recommendations.append("バッチサイズ未充分。並列性を向上検討")
        
        return recommendations
    
    def shutdown(self) -> None:
        """GPU デバイスをシャットダウン"""
        
        self.deallocate_memory(self.memory_allocation.used_mb)
        self.is_initialized = False
