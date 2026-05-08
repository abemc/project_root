"""
自動スケーリング

メトリクスベースのオートスケーリング、HPA（Horizontal Pod Autoscaler）対応
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, Any, List
import logging
import asyncio


logger = logging.getLogger(__name__)


class MetricType(Enum):
    """メトリクスタイプ"""
    CPU = "cpu"
    MEMORY = "memory"
    REQUESTS_PER_SECOND = "requests_per_second"
    CUSTOM = "custom"


class ScalingPolicy(Enum):
    """スケーリングポリシー"""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    MAINTAIN = "maintain"


@dataclass
class MetricThreshold:
    """メトリクスしきい値"""
    metric_type: MetricType
    target_value: float
    threshold_percent: float = 10.0  # 10%の余裕
    
    def should_scale_up(self, current_value: float) -> bool:
        """スケールアップ判定"""
        upper_threshold = self.target_value * (1 + self.threshold_percent / 100)
        return current_value > upper_threshold
    
    def should_scale_down(self, current_value: float) -> bool:
        """スケールダウン判定"""
        lower_threshold = self.target_value * (1 - self.threshold_percent / 100)
        return current_value < lower_threshold


@dataclass
class ScalingConfig:
    """スケーリング設定"""
    name: str
    namespace: str = "default"
    deployment_name: str = ""
    min_replicas: int = 1
    max_replicas: int = 10
    target_metrics: List[MetricThreshold] = field(default_factory=list)
    scale_up_cooldown_seconds: int = 60
    scale_down_cooldown_seconds: int = 300
    scale_up_step: int = 1
    scale_down_step: int = 1


@dataclass
class MetricSnapshot:
    """メトリクススナップショット"""
    timestamp: datetime
    metrics: Dict[str, float] = field(default_factory=dict)
    average_cpu_percent: float = 0.0
    average_memory_percent: float = 0.0
    requests_per_second: float = 0.0


class AutoScaler:
    """オートスケーラー"""
    
    def __init__(self, config: ScalingConfig):
        """初期化"""
        self.config = config
        self.current_replicas = config.min_replicas
        self.last_scale_action = datetime.utcnow()
        self.metric_history: List[MetricSnapshot] = []
        self.scaling_events: List[Dict[str, Any]] = []
    
    async def evaluate_scaling_decision(
        self,
        current_metrics: MetricSnapshot
    ) -> Optional[ScalingPolicy]:
        """スケーリング判定を評価"""
        
        # メトリクス履歴に追加
        self.metric_history.append(current_metrics)
        
        # 履歴を最新100件に制限
        if len(self.metric_history) > 100:
            self.metric_history = self.metric_history[-100:]
        
        # 各メトリクスをチェック
        scale_up_metrics = []
        scale_down_metrics = []
        
        for threshold in self.config.target_metrics:
            current_value = current_metrics.metrics.get(threshold.metric_type.value, 0)
            
            if threshold.should_scale_up(current_value):
                scale_up_metrics.append(threshold.metric_type)
            elif threshold.should_scale_down(current_value):
                scale_down_metrics.append(threshold.metric_type)
        
        # スケーリング判定
        if scale_up_metrics:
            logger.info(f"Scale-up needed for: {[m.value for m in scale_up_metrics]}")
            return ScalingPolicy.SCALE_UP
        
        elif scale_down_metrics:
            logger.info(f"Scale-down possible for: {[m.value for m in scale_down_metrics]}")
            return ScalingPolicy.SCALE_DOWN
        
        return ScalingPolicy.MAINTAIN
    
    async def calculate_new_replica_count(
        self,
        policy: ScalingPolicy
    ) -> int:
        """新しいレプリカ数を計算"""
        
        new_replicas = self.current_replicas
        
        if policy == ScalingPolicy.SCALE_UP:
            new_replicas = min(
                self.current_replicas + self.config.scale_up_step,
                self.config.max_replicas
            )
        
        elif policy == ScalingPolicy.SCALE_DOWN:
            new_replicas = max(
                self.current_replicas - self.config.scale_down_step,
                self.config.min_replicas
            )
        
        return new_replicas
    
    def is_cooldown_active(self, policy: ScalingPolicy) -> bool:
        """クールダウン期間がアクティブか確認"""
        
        elapsed = (datetime.utcnow() - self.last_scale_action).total_seconds()
        
        if policy == ScalingPolicy.SCALE_UP:
            return elapsed < self.config.scale_up_cooldown_seconds
        
        elif policy == ScalingPolicy.SCALE_DOWN:
            return elapsed < self.config.scale_down_cooldown_seconds
        
        return False
    
    async def apply_scaling(
        self,
        new_replicas: int,
        policy: ScalingPolicy
    ) -> bool:
        """スケーリングを適用"""
        
        # クールダウン確認
        if self.is_cooldown_active(policy):
            logger.info(f"Scaling cooldown active for {policy.value}")
            return False
        
        # 変更がないか確認
        if new_replicas == self.current_replicas:
            return False
        
        # スケーリング実行
        self.current_replicas = new_replicas
        self.last_scale_action = datetime.utcnow()
        
        # イベント記録
        self.scaling_events.append({
            "timestamp": self.last_scale_action.isoformat(),
            "policy": policy.value,
            "old_replicas": self.current_replicas - (
                self.config.scale_up_step if policy == ScalingPolicy.SCALE_UP
                else -self.config.scale_down_step
            ),
            "new_replicas": new_replicas
        })
        
        logger.info(
            f"Scaling applied: {self.config.name} "
            f"-> {new_replicas} replicas ({policy.value})"
        )
        
        return True
    
    async def get_scaling_metrics(self) -> Dict[str, Any]:
        """スケーリングメトリクスを取得"""
        
        if not self.metric_history:
            return {}
        
        recent_metrics = self.metric_history[-10:]
        
        avg_cpu = sum(m.average_cpu_percent for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.average_memory_percent for m in recent_metrics) / len(recent_metrics)
        avg_rps = sum(m.requests_per_second for m in recent_metrics) / len(recent_metrics)
        
        return {
            "current_replicas": self.current_replicas,
            "average_cpu_percent": f"{avg_cpu:.1f}",
            "average_memory_percent": f"{avg_memory:.1f}",
            "average_rps": f"{avg_rps:.1f}",
            "events_count": len(self.scaling_events),
            "last_scale_action": self.last_scale_action.isoformat()
        }


class HPA:
    """Horizontal Pod Autoscaler"""
    
    def __init__(self):
        """初期化"""
        self.scalers: Dict[str, AutoScaler] = {}
        self.monitoring_active = False
    
    async def create_hpa(self, config: ScalingConfig) -> bool:
        """HPAを作成"""
        
        key = f"{config.namespace}/{config.name}"
        
        if key in self.scalers:
            logger.warning(f"HPA {key} already exists")
            return False
        
        scaler = AutoScaler(config)
        self.scalers[key] = scaler
        
        logger.info(f"HPA created: {key}")
        
        return True
    
    async def delete_hpa(self, name: str, namespace: str = "default") -> bool:
        """HPAを削除"""
        
        key = f"{namespace}/{name}"
        
        if key not in self.scalers:
            logger.warning(f"HPA {key} not found")
            return False
        
        del self.scalers[key]
        
        logger.info(f"HPA deleted: {key}")
        
        return True
    
    async def update_metrics(
        self,
        name: str,
        metrics: MetricSnapshot,
        namespace: str = "default"
    ) -> Optional[ScalingPolicy]:
        """メトリクスを更新してスケーリング判定"""
        
        key = f"{namespace}/{name}"
        
        if key not in self.scalers:
            logger.warning(f"HPA {key} not found")
            return None
        
        scaler = self.scalers[key]
        
        # スケーリング判定
        policy = await scaler.evaluate_scaling_decision(metrics)
        
        if policy != ScalingPolicy.MAINTAIN:
            # 新しいレプリカ数を計算
            new_replicas = await scaler.calculate_new_replica_count(policy)
            
            # スケーリングを適用
            await scaler.apply_scaling(new_replicas, policy)
        
        return policy
    
    async def start_monitoring(self, interval_seconds: int = 30) -> None:
        """監視を開始（シミュレーション）"""
        
        self.monitoring_active = True
        
        logger.info("HPA monitoring started")
        
        while self.monitoring_active:
            # メトリクス更新（実装では定期的に収集）
            for key, scaler in self.scalers.items():
                # シミュレーション用のメトリクス
                metrics = MetricSnapshot(
                    timestamp=datetime.utcnow(),
                    metrics={
                        "cpu": 50.0,
                        "memory": 60.0,
                        "requests_per_second": 100.0
                    }
                )
                
                # 判定実行
                await self.update_metrics(
                    scaler.config.name,
                    metrics,
                    scaler.config.namespace
                )
            
            await asyncio.sleep(interval_seconds)
    
    async def stop_monitoring(self) -> None:
        """監視を停止"""
        
        self.monitoring_active = False
        logger.info("HPA monitoring stopped")
    
    async def get_hpa_status(self, name: str, namespace: str = "default") -> Dict[str, Any]:
        """HPA状態を取得"""
        
        key = f"{namespace}/{name}"
        
        if key not in self.scalers:
            return {}
        
        scaler = self.scalers[key]
        
        return {
            "name": scaler.config.name,
            "namespace": scaler.config.namespace,
            "current_replicas": scaler.current_replicas,
            "min_replicas": scaler.config.min_replicas,
            "max_replicas": scaler.config.max_replicas,
            "metrics": await scaler.get_scaling_metrics(),
            "recent_events": scaler.scaling_events[-5:]
        }


class VerticalPodAutoscaler:
    """Vertical Pod Autoscaler (リソースリクエスト最適化)"""
    
    def __init__(self):
        """初期化"""
        self.recommendations: Dict[str, Dict[str, Any]] = {}
    
    async def analyze_pod_resources(
        self,
        pod_name: str,
        usage_history: List[Dict[str, float]]
    ) -> Dict[str, str]:
        """ポッドリソース使用状況を分析してレコメンデーション提供"""
        
        if not usage_history:
            return {}
        
        # CPU平均
        avg_cpu = sum(u.get("cpu", 0) for u in usage_history) / len(usage_history)
        
        # メモリ平均
        avg_memory = sum(u.get("memory", 0) for u in usage_history) / len(usage_history)
        
        # ピーク
        peak_cpu = max(u.get("cpu", 0) for u in usage_history)
        peak_memory = max(u.get("memory", 0) for u in usage_history)
        
        # リコメンデーション
        recommendation = {
            "cpu_request": f"{int(peak_cpu * 1.2)}m",  # ピークの120%
            "cpu_limit": f"{int(peak_cpu * 1.5)}m",    # ピークの150%
            "memory_request": f"{int(peak_memory * 1.1)}Mi",  # ピークの110%
            "memory_limit": f"{int(peak_memory * 1.3)}Mi"     # ピークの130%
        }
        
        self.recommendations[pod_name] = recommendation
        
        logger.info(f"Resource recommendation for {pod_name}: {recommendation}")
        
        return recommendation
    
    async def get_recommendation(self, pod_name: str) -> Optional[Dict[str, str]]:
        """ポッドのリソースレコメンデーションを取得"""
        
        return self.recommendations.get(pod_name)
