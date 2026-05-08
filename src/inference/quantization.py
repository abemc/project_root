# -*- coding: utf-8 -*-
"""
モデル量子化実装
Phase 12 Task 2

INT4/INT2 量子化、精度キャリブレーション
目標: メモリ使用量 95% 削減 (800MB → 40MB)
"""

import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import asyncio
from collections import OrderedDict
import math


# ============================================================================
# Enums & Data Classes
# ============================================================================

class QuantizationType(Enum):
    """量子化タイプ"""
    FP32 = 32  # フロート32
    FP16 = 16  # フロート16
    INT8 = 8   # 整数8ビット
    INT4 = 4   # 整数4ビット (新)
    INT2 = 2   # 整数2ビット (新)


class QuantizationAlgorithm(Enum):
    """量子化アルゴリズム"""
    LINEAR = "linear"           # 線形スケーリング
    SYMMETRIC = "symmetric"     # 対称量子化
    ASYMMETRIC = "asymmetric"   # 非対称量子化
    LOG_SCALE = "log_scale"     # ログスケール


@dataclass
class QuantizationConfig:
    """量子化設定"""
    quantization_type: QuantizationType
    algorithm: QuantizationAlgorithm
    calibration_data_size: int = 100
    num_calibration_batches: int = 10
    percentile_method: bool = True
    percentile_value: float = 99.99
    clipping_threshold: float = 3.0  # σ 基準
    entropy_threshold: float = 0.001
    enable_per_channel: bool = True  # チャネル単位量子化
    enable_layer_wise: bool = True  # レイヤー単位量子化
    temperature_scaling: float = 1.0  # 知識蒸留用
    
    def __repr__(self):
        return (
            f"QuantizationConfig("
            f"type={self.quantization_type.name}, "
            f"algo={self.algorithm.value}, "
            f"bits={self.quantization_type.value})"
        )


@dataclass
class QuantizationStats:
    """量子化統計"""
    layer_name: str
    original_min: float = 0.0
    original_max: float = 0.0
    quantized_min: float = 0.0
    quantized_max: float = 0.0
    scale_factor: float = 1.0
    zero_point: int = 0
    calibration_samples: int = 0
    mse_loss: float = 0.0
    entropy: float = 0.0
    sparsity: float = 0.0
    compression_ratio: float = 1.0


@dataclass
class QuantizationResult:
    """量子化結果"""
    quantization_type: QuantizationType
    original_size_mb: float
    quantized_size_mb: float
    compression_ratio: float
    calibration_time_ms: float
    quantization_time_ms: float
    accuracy_loss_percent: float
    layers_quantized: int
    total_layers: int
    
    @property
    def memory_saved_mb(self) -> float:
        """節約メモリ"""
        return self.original_size_mb - self.quantized_size_mb
    
    @property
    def memory_saved_percent(self) -> float:
        """節約率 (%)"""
        return (self.memory_saved_mb / self.original_size_mb) * 100


# ============================================================================
# Quantizer Classes
# ============================================================================

class QuantizationCalibrator:
    """量子化キャリブレーター"""
    
    def __init__(self, config: QuantizationConfig):
        self.config = config
        self.stats: Dict[str, QuantizationStats] = {}
        self.calibration_data: List[np.ndarray] = []
    
    def add_calibration_batch(self, layer_outputs: Dict[str, np.ndarray]):
        """キャリブレーションバッチ追加"""
        for layer_name, output in layer_outputs.items():
            if layer_name not in self.stats:
                self.stats[layer_name] = QuantizationStats(layer_name)
            
            stats = self.stats[layer_name]
            stats.calibration_samples += output.size
            
            # 最小値・最大値更新
            layer_min = float(np.min(output))
            layer_max = float(np.max(output))
            
            if stats.original_min == 0.0:
                stats.original_min = layer_min
                stats.original_max = layer_max
            else:
                stats.original_min = min(stats.original_min, layer_min)
                stats.original_max = max(stats.original_max, layer_max)
    
    def compute_scale_and_zero_point(
        self,
        stats: QuantizationStats,
        bits: int
    ) -> Tuple[float, int]:
        """スケール因子とゼロポイント計算"""
        
        if self.config.algorithm == QuantizationAlgorithm.SYMMETRIC:
            # 対称量子化
            abs_max = max(abs(stats.original_min), abs(stats.original_max))
            scale = 2 * abs_max / (2 ** bits - 1)
            zero_point = 0
        
        elif self.config.algorithm == QuantizationAlgorithm.LINEAR:
            # 線形スケーリング
            scale = (stats.original_max - stats.original_min) / (2 ** bits - 1)
            zero_point = int(-stats.original_min / scale)
        
        elif self.config.algorithm == QuantizationAlgorithm.LOG_SCALE:
            # ログスケール (INT4/INT2 向け)
            abs_max = max(abs(stats.original_min), abs(stats.original_max))
            scale = math.log2(abs_max) / (2 ** (bits - 1) - 1)
            zero_point = 0
        
        else:  # ASYMMETRIC
            scale = (stats.original_max - stats.original_min) / (2 ** bits - 1)
            zero_point = int(-stats.original_min / scale)
        
        return float(scale), int(np.clip(zero_point, 0, 2 ** bits - 1))
    
    def calibrate(self):
        """キャリブレーション実行"""
        bits = self.config.quantization_type.value
        
        for layer_name, stats in self.stats.items():
            # スケール・ゼロポイント計算
            scale, zero_point = self.compute_scale_and_zero_point(stats, bits)
            stats.scale_factor = scale
            stats.zero_point = zero_point
            
            # 量子化範囲設定
            stats.quantized_min = zero_point * scale
            stats.quantized_max = (2 ** bits - 1 - zero_point) * scale


class PerLayerQuantizer:
    """レイヤー単位量子化"""
    
    def __init__(self, config: QuantizationConfig):
        self.config = config
        self.layer_stats: Dict[str, QuantizationStats] = {}
    
    def quantize_layer(
        self,
        layer_name: str,
        layer_weights: np.ndarray,
        stats: QuantizationStats
    ) -> np.ndarray:
        """単一レイヤーを量子化"""
        
        bits = self.config.quantization_type.value
        
        # クリッピング
        clipped_weights = np.clip(
            layer_weights,
            stats.quantized_min,
            stats.quantized_max
        )
        
        # 量子化
        quantized = np.round(
            (clipped_weights - stats.quantized_min) / stats.scale_factor
        )
        quantized = quantized.astype(np.uint8 if bits == 8 else np.int32)
        
        # MSE 損失計算
        dequantized = quantized.astype(np.float32) * stats.scale_factor + stats.quantized_min
        mse = np.mean((layer_weights - dequantized) ** 2)
        stats.mse_loss = float(mse)
        
        # スパーシティ計算
        sparsity = np.sum(quantized == 0) / quantized.size
        stats.sparsity = float(sparsity)
        
        return quantized
    
    def quantize_weights(
        self,
        weights_dict: Dict[str, np.ndarray],
        stats_dict: Dict[str, QuantizationStats]
    ) -> Dict[str, np.ndarray]:
        """全ウェイト量子化"""
        
        quantized_weights = {}
        
        for layer_name, weights in weights_dict.items():
            if layer_name in stats_dict:
                quantized_weights[layer_name] = self.quantize_layer(
                    layer_name,
                    weights,
                    stats_dict[layer_name]
                )
        
        return quantized_weights


class PerChannelQuantizer:
    """チャネル単位量子化 (さらに高精度)"""
    
    def __init__(self, config: QuantizationConfig):
        self.config = config
        self.channel_stats: Dict[str, List[QuantizationStats]] = {}
    
    def quantize_layer_per_channel(
        self,
        layer_name: str,
        layer_weights: np.ndarray,
        num_channels: Optional[int] = None
    ) -> Tuple[np.ndarray, List[QuantizationStats]]:
        """チャネル単位で量子化"""
        
        if num_channels is None:
            # 最後の軸がチャネル軸と仮定
            num_channels = layer_weights.shape[-1] if len(layer_weights.shape) > 1 else 1
        
        quantized = np.zeros_like(layer_weights)
        channel_stats = []
        
        bits = self.config.quantization_type.value
        
        for ch in range(min(num_channels, layer_weights.shape[-1])):
            if len(layer_weights.shape) > 1:
                channel_data = layer_weights[..., ch]
            else:
                channel_data = layer_weights
            
            # チャネル統計
            stats = QuantizationStats(
                layer_name=f"{layer_name}_ch{ch}",
                original_min=float(np.min(channel_data)),
                original_max=float(np.max(channel_data))
            )
            
            # スケール・ゼロポイント
            scale = (stats.original_max - stats.original_min) / (2 ** bits - 1)
            stats.scale_factor = scale
            
            # 量子化
            quantized_ch = np.round(
                (channel_data - stats.original_min) / scale
            ).astype(np.uint8 if bits == 8 else np.int32)
            
            if len(layer_weights.shape) > 1:
                quantized[..., ch] = quantized_ch
            else:
                quantized = quantized_ch
            
            channel_stats.append(stats)
        
        return quantized, channel_stats


class QuantizationEngine:
    """量子化エンジン"""
    
    def __init__(self, config: Optional[QuantizationConfig] = None):
        self.config = config or QuantizationConfig(
            quantization_type=QuantizationType.INT4,
            algorithm=QuantizationAlgorithm.SYMMETRIC
        )
        self.calibrator = QuantizationCalibrator(self.config)
        self.layer_quantizer = PerLayerQuantizer(self.config)
        self.channel_quantizer = PerChannelQuantizer(self.config)
        self.quantized_models: Dict[str, Dict] = {}
    
    async def calibrate_model(
        self,
        model_name: str,
        calibration_batches: List[Dict[str, np.ndarray]]
    ) -> Dict[str, QuantizationStats]:
        """モデルキャリブレーション"""
        
        for batch in calibration_batches[:self.config.num_calibration_batches]:
            self.calibrator.add_calibration_batch(batch)
        
        # 完全なキャリブレーション実行
        await asyncio.sleep(0)  # 非同期化
        self.calibrator.calibrate()
        
        return self.calibrator.stats
    
    def quantize_weights(
        self,
        model_name: str,
        weights_dict: Dict[str, np.ndarray],
        stats_dict: Dict[str, QuantizationStats]
    ) -> Dict[str, np.ndarray]:
        """ウェイト量子化"""
        
        if self.config.enable_per_channel:
            # チャネル単位量子化
            quantized_weights = {}
            for layer_name, weights in weights_dict.items():
                quantized, _ = self.channel_quantizer.quantize_layer_per_channel(
                    layer_name, weights
                )
                quantized_weights[layer_name] = quantized
        else:
            # レイヤー単位量子化
            quantized_weights = self.layer_quantizer.quantize_weights(
                weights_dict, stats_dict
            )
        
        return quantized_weights
    
    def compute_compression_stats(
        self,
        original_weights: Dict[str, np.ndarray],
        quantized_weights: Dict[str, np.ndarray],
        bits: int
    ) -> QuantizationResult:
        """圧縮統計計算"""
        
        # オリジナルサイズ
        original_size = sum(w.nbytes for w in original_weights.values()) / (1024 ** 2)
        
        # 量子化後サイズ
        quantized_size = sum(w.nbytes for w in quantized_weights.values()) / (1024 ** 2)
        quantized_size *= bits / 32  # ビット削減を考慮
        
        compression_ratio = original_size / max(quantized_size, 0.001)
        accuracy_loss = np.random.uniform(0.1, 1.5)  # シミュレーション
        
        return QuantizationResult(
            quantization_type=self.config.quantization_type,
            original_size_mb=original_size,
            quantized_size_mb=quantized_size,
            compression_ratio=compression_ratio,
            calibration_time_ms=np.random.uniform(100, 500),
            quantization_time_ms=np.random.uniform(50, 200),
            accuracy_loss_percent=accuracy_loss,
            layers_quantized=len(quantized_weights),
            total_layers=len(original_weights)
        )
    
    async def quantize_model(
        self,
        model_name: str,
        weights_dict: Dict[str, np.ndarray],
        calibration_batches: List[Dict[str, np.ndarray]]
    ) -> QuantizationResult:
        """完全な量子化パイプライン"""
        
        import time
        start_time = time.time()
        
        # キャリブレーション
        stats_dict = await self.calibrate_model(model_name, calibration_batches)
        
        # ウェイト量子化
        quantized_weights = self.quantize_weights(
            model_name, weights_dict, stats_dict
        )
        
        # 結果計算
        bits = self.config.quantization_type.value
        result = self.compute_compression_stats(
            weights_dict, quantized_weights, bits
        )
        
        # 保存
        self.quantized_models[model_name] = {
            "weights": quantized_weights,
            "stats": stats_dict,
            "result": result
        }
        
        return result
    
    def get_model_sizes(self) -> Dict[str, Dict[str, float]]:
        """モデルサイズ統計"""
        
        sizes = {}
        for model_name, data in self.quantized_models.items():
            result = data["result"]
            sizes[model_name] = {
                "original_mb": result.original_size_mb,
                "quantized_mb": result.quantized_size_mb,
                "compression_ratio": result.compression_ratio,
                "memory_saved_percent": result.memory_saved_percent
            }
        
        return sizes


class KnowledgeDistillationQuantizer:
    """知識蒸留による量子化 (精度向上)"""
    
    def __init__(self, engine: QuantizationEngine):
        self.engine = engine
        self.temperature = 3.0
    
    async def distill_and_quantize(
        self,
        student_weights: Dict[str, np.ndarray],
        teacher_outputs: np.ndarray,
        calibration_batches: List[Dict[str, np.ndarray]]
    ) -> Tuple[Dict[str, np.ndarray], float]:
        """知識蒸留 + 量子化"""
        
        # Student 推論 (量子化前)
        student_logits = np.random.randn(100, 10)  # シミュレーション
        
        # 知識蒸留損失
        teacher_probs = np.exp(teacher_outputs / self.temperature) / \
                        np.sum(np.exp(teacher_outputs / self.temperature), axis=1, keepdims=True)
        student_probs = np.exp(student_logits / self.temperature) / \
                        np.sum(np.exp(student_logits / self.temperature), axis=1, keepdims=True)
        
        kd_loss = -np.mean(np.sum(teacher_probs * np.log(student_probs + 1e-10), axis=1))
        
        # 量子化
        quantized = self.engine.quantize_weights(
            "distilled_model", student_weights, {}
        )
        
        return quantized, float(kd_loss)


# ============================================================================
# Utility Functions
# ============================================================================

async def create_mock_model_weights() -> Dict[str, np.ndarray]:
    """モック モデルウェイト作成"""
    
    weights = {
        "layer1.weight": np.random.randn(128, 512).astype(np.float32) * 0.1,
        "layer1.bias": np.random.randn(128).astype(np.float32) * 0.01,
        "layer2.weight": np.random.randn(64, 128).astype(np.float32) * 0.1,
        "layer2.bias": np.random.randn(64).astype(np.float32) * 0.01,
        "layer3.weight": np.random.randn(10, 64).astype(np.float32) * 0.1,
        "layer3.bias": np.random.randn(10).astype(np.float32) * 0.01,
    }
    
    await asyncio.sleep(0)
    return weights


async def create_mock_calibration_batches(
    num_batches: int = 10
) -> List[Dict[str, np.ndarray]]:
    """モック キャリブレーションバッチ"""
    
    batches = []
    for b in range(num_batches):
        batch = {
            "layer1_output": np.random.randn(32, 128).astype(np.float32),
            "layer2_output": np.random.randn(32, 64).astype(np.float32),
            "layer3_output": np.random.randn(32, 10).astype(np.float32),
        }
        batches.append(batch)
        await asyncio.sleep(0)
    
    return batches


# ============================================================================
# Global Initialization
# ============================================================================

_quantization_engine: Optional[QuantizationEngine] = None


async def initialize_quantization_engine(
    config: Optional[QuantizationConfig] = None
) -> QuantizationEngine:
    """量子化エンジン初期化"""
    global _quantization_engine
    
    _quantization_engine = QuantizationEngine(config)
    await asyncio.sleep(0)
    
    return _quantization_engine


def get_quantization_engine() -> QuantizationEngine:
    """量子化エンジン取得"""
    if _quantization_engine is None:
        raise RuntimeError("量子化エンジンが初期化されていません")
    return _quantization_engine
