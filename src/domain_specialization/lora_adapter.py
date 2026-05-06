"""
ドメイン特化アダプター (LoRA)

低ランク適応 (Low-Rank Adaptation) による効率的なドメイン特化学習
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import math
import logging
from enum import Enum


logger = logging.getLogger(__name__)


class LoRAConfig:
    """LoRA設定"""
    
    def __init__(
        self,
        rank: int = 16,
        alpha: int = 32,
        dropout: float = 0.05,
        target_modules: Optional[List[str]] = None
    ):
        """初期化"""
        self.rank = rank
        self.alpha = alpha
        self.dropout = dropout
        self.target_modules = target_modules or ["q_proj", "v_proj"]
        self.scaling = alpha / rank


@dataclass
class LoRAWeights:
    """LoRA重み"""
    A: List[List[float]] = field(default_factory=list)  # (in_features, rank)
    B: List[List[float]] = field(default_factory=list)  # (rank, out_features)
    layer_name: str = ""
    domain: str = ""


class LoRAAdapterModule:
    """LoRAアダプターモジュール"""
    
    def __init__(
        self,
        in_features: int,
        out_features: int,
        config: LoRAConfig,
        layer_name: str
    ):
        """初期化"""
        self.in_features = in_features
        self.out_features = out_features
        self.config = config
        self.layer_name = layer_name
        
        # LoRA行列の初期化
        self.lora_a = self._init_matrix(in_features, config.rank)
        self.lora_b = self._init_matrix(config.rank, out_features, zero_init=True)
        
        self.total_params = (in_features * config.rank) + (config.rank * out_features)
    
    def _init_matrix(
        self,
        rows: int,
        cols: int,
        zero_init: bool = False
    ) -> List[List[float]]:
        """行列を初期化"""
        
        if zero_init:
            return [[0.0 for _ in range(cols)] for _ in range(rows)]
        
        # Kaiming uniform初期化
        bound = math.sqrt(6.0 / (rows + cols))
        return [[
            (2.0 * i * j - 1.0) / (rows * cols) * bound
            for j in range(cols)
        ] for i in range(rows)]
    
    def forward(
        self,
        x: List[List[float]],
        base_output: Optional[List[List[float]]] = None
    ) -> List[List[float]]:
        """フォワードパス"""
        
        # LoRA計算: output = base_output + (x @ A @ B) * scaling
        batch_size = len(x)
        
        # x @ A
        intermediate = self._matrix_multiply(x, self.lora_a)
        
        # intermediate @ B
        lora_output = self._matrix_multiply(intermediate, self.lora_b)
        
        # スケーリング
        scaling_factor = self.config.scaling
        
        if base_output is None:
            return [[
                lora_output[i][j] * scaling_factor
                for j in range(len(lora_output[i]))
            ] for i in range(batch_size)]
        
        # 基礎出力 + LoRA出力
        return [[
            base_output[i][j] + lora_output[i][j] * scaling_factor
            for j in range(len(base_output[i]))
        ] for i in range(batch_size)]
    
    def _matrix_multiply(
        self,
        a: List[List[float]],
        b: List[List[float]]
    ) -> List[List[float]]:
        """行列乗算"""
        
        rows_a = len(a)
        cols_a = len(a[0]) if a else 0
        cols_b = len(b[0]) if b else 0
        
        result = [[0.0 for _ in range(cols_b)] for _ in range(rows_a)]
        
        for i in range(rows_a):
            for k in range(cols_a):
                for j in range(cols_b):
                    result[i][j] += a[i][k] * b[k][j]
        
        return result
    
    def save_weights(self) -> LoRAWeights:
        """重みを保存"""
        return LoRAWeights(
            A=self.lora_a,
            B=self.lora_b,
            layer_name=self.layer_name,
            domain=""
        )


class DomainSpecificLoRA:
    """ド���イン特化LoRA"""
    
    def __init__(
        self,
        model_hidden_size: int = 768,
        num_attention_heads: int = 12,
        num_layers: int = 12
    ):
        """初期化"""
        self.model_hidden_size = model_hidden_size
        self.num_attention_heads = num_attention_heads
        self.num_layers = num_layers
        
        self.adapters: Dict[str, Dict[str, LoRAAdapterModule]] = {}
    
    def create_lora_adapter(
        self,
        domain: str,
        config: LoRAConfig
    ) -> Dict[str, LoRAAdapterModule]:
        """ドメイン用LoRAアダプターを作成"""
        
        adapter_modules = {}
        
        for layer_idx in range(self.num_layers):
            for target_module in config.target_modules:
                layer_name = f"layer_{layer_idx}.{target_module}"
                
                module = LoRAAdapterModule(
                    in_features=self.model_hidden_size,
                    out_features=self.model_hidden_size,
                    config=config,
                    layer_name=layer_name
                )
                
                adapter_modules[layer_name] = module
        
        self.adapters[domain] = adapter_modules
        
        total_params = sum(m.total_params for m in adapter_modules.values())
        logger.info(
            f"Created LoRA adapter for {domain}: "
            f"{len(adapter_modules)} modules, {total_params} parameters"
        )
        
        return adapter_modules
    
    def get_total_lora_params(self, domain: str) -> int:
        """ドメインのLoRAパラメータ総数を取得"""
        
        if domain not in self.adapters:
            return 0
        
        return sum(
            module.total_params
            for module in self.adapters[domain].values()
        )
    
    def apply_lora(
        self,
        domain: str,
        layer_name: str,
        base_output: List[List[float]]
    ) -> List[List[float]]:
        """LoRAを適用"""
        
        if domain not in self.adapters:
            logger.warning(f"Adapter for domain '{domain}' not found")
            return base_output
        
        adapter_modules = self.adapters[domain]
        
        if layer_name not in adapter_modules:
            return base_output
        
        module = adapter_modules[layer_name]
        return module.forward(base_output)
    
    def merge_lora_weights(
        self,
        domain: str,
        base_weights: Dict[str, List[List[float]]]
    ) -> Dict[str, List[List[float]]]:
        """LoRA重みを基礎重みにマージ"""
        
        if domain not in self.adapters:
            return base_weights
        
        merged_weights = base_weights.copy()
        adapter_modules = self.adapters[domain]
        
        for layer_name, module in adapter_modules.items():
            if layer_name in base_weights:
                # A @ B を計算してスケーリング
                lora_contribution = module._matrix_multiply(
                    module.lora_a,
                    module.lora_b
                )
                
                # 基礎重みに追加
                merged_weights[layer_name] = [[
                    base_weights[layer_name][i][j] + lora_contribution[i][j] * module.config.scaling
                    for j in range(len(base_weights[layer_name][i]))
                ] for i in range(len(base_weights[layer_name]))]
        
        return merged_weights
    
    def get_adapter_statistics(self, domain: str) -> Dict[str, Any]:
        """アダプター統計を取得"""
        
        if domain not in self.adapters:
            return {"error": f"Adapter for domain '{domain}' not found"}
        
        modules = self.adapters[domain]
        
        total_params = sum(m.total_params for m in modules.values())
        avg_rank = sum(m.config.rank for m in modules.values()) / len(modules)
        
        return {
            "domain": domain,
            "total_modules": len(modules),
            "total_parameters": total_params,
            "average_rank": avg_rank,
            "parameter_reduction_ratio": (
                (self.model_hidden_size ** 2 * len(modules)) / total_params
            )
        }


class MultiDomainLoRAManager:
    """マルチドメインLoRA管理"""
    
    def __init__(
        self,
        model_config: Dict[str, int]
    ):
        """初期化"""
        self.model_config = model_config
        self.lora_system = DomainSpecificLoRA(
            model_hidden_size=model_config.get("hidden_size", 768),
            num_attention_heads=model_config.get("num_attention_heads", 12),
            num_layers=model_config.get("num_layers", 12)
        )
        
        self.domain_configs: Dict[str, LoRAConfig] = {}
        self.active_domain: Optional[str] = None
    
    def register_domain(
        self,
        domain: str,
        lora_rank: int = 16,
        lora_alpha: int = 32,
        target_modules: Optional[List[str]] = None
    ) -> bool:
        """ドメインを登録"""
        
        try:
            config = LoRAConfig(
                rank=lora_rank,
                alpha=lora_alpha,
                target_modules=target_modules
            )
            
            self.domain_configs[domain] = config
            self.lora_system.create_lora_adapter(domain, config)
            
            logger.info(f"Registered domain: {domain} with rank={lora_rank}")
            return True
        except Exception as e:
            logger.error(f"Failed to register domain {domain}: {e}")
            return False
    
    def activate_domain(self, domain: str) -> bool:
        """ドメインを有効化"""
        
        if domain not in self.domain_configs:
            logger.error(f"Domain '{domain}' not registered")
            return False
        
        self.active_domain = domain
        logger.info(f"Activated domain: {domain}")
        return True
    
    def deactivate_domain(self) -> None:
        """ドメインを無効化"""
        self.active_domain = None
    
    def get_adapter_info(self) -> Dict[str, Any]:
        """アダプター情報を取得"""
        
        info = {
            "registered_domains": list(self.domain_configs.keys()),
            "active_domain": self.active_domain,
            "adapters": {}
        }
        
        for domain in self.domain_configs.keys():
            stats = self.lora_system.get_adapter_statistics(domain)
            info["adapters"][domain] = stats
        
        return info
    
    def calculate_total_params_per_domain(self) -> Dict[str, int]:
        """ドメイン別パラメータ数を計算"""
        
        return {
            domain: self.lora_system.get_total_lora_params(domain)
            for domain in self.domain_configs.keys()
        }
    
    def get_efficiency_report(self) -> Dict[str, Any]:
        """効率性レポートを取得"""
        
        base_model_params = (
            self.model_config.get("hidden_size", 768) ** 2 *
            self.model_config.get("num_layers", 12) * 2  # q, v projections
        )
        
        domain_params = self.calculate_total_params_per_domain()
        
        total_lora_params = sum(domain_params.values())
        
        return {
            "base_model_parameters": base_model_params,
            "total_lora_parameters": total_lora_params,
            "parameter_overhead_percent": (
                (total_lora_params / base_model_params * 100)
                if base_model_params > 0 else 0
            ),
            "domain_breakdown": domain_params,
            "efficiency_improvement": (
                f"{(base_model_params / (base_model_params + total_lora_params) * 100):.1f}% "
                f"memory saved vs full fine-tuning"
            )
        }
