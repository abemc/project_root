"""
SLA Monitor Implementation

SLA監視とアラート機能の実装
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime, timedelta
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class SLAThresholds:
    """SLA閾値"""
    availability_target: float = 0.9999         # 99.99%
    max_downtime_per_month: float = 2.592       # 秒（43.2秒/月）
    p99_latency: float = 250.0                  # ミリ秒
    p95_latency: float = 200.0
    p50_latency: float = 100.0
    error_rate_threshold: float = 0.01          # 1%


@dataclass
class SLAMetrics:
    """SLAメトリクス"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_downtime: float = 0.0                 # 秒
    
    # レイテンシデータ
    latencies: List[float] = field(default_factory=list)
    
    # タイムスタンプ
    measurement_start: datetime = field(default_factory=datetime.now)
    measurement_end: Optional[datetime] = None
    
    def get_availability(self) -> float:
        """可用性を取得（0-1）"""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests
    
    def get_error_rate(self) -> float:
        """エラー率を取得（0-1）"""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests
    
    def get_p99_latency(self) -> float:
        """P99レイテンシを取得（ミリ秒）"""
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * 0.99)
        index = min(index, len(sorted_latencies) - 1)
        return sorted_latencies[index]
    
    def get_p95_latency(self) -> float:
        """P95レイテンシを取得（ミリ秒）"""
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * 0.95)
        index = min(index, len(sorted_latencies) - 1)
        return sorted_latencies[index]
    
    def get_p50_latency(self) -> float:
        """P50（中央値）レイテンシを取得（ミリ秒）"""
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        index = len(sorted_latencies) // 2
        return sorted_latencies[index]
    
    def get_avg_latency(self) -> float:
        """平均レイテンシを取得（ミリ秒）"""
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)


@dataclass
class SLABreach:
    """SLA違反"""
    metric: str
    threshold: float
    actual_value: float
    timestamp: datetime
    severity: str  # "warning", "critical"


class SLAMonitor:
    """
    SLA監視
    
    99.99% SLA達成のための監視とアラート
    """
    
    def __init__(self, thresholds: Optional[SLAThresholds] = None):
        """初期化"""
        self.thresholds = thresholds or SLAThresholds()
        self.metrics = SLAMetrics()
        self.breaches: List[SLABreach] = []
        self.alert_callbacks: List[Callable] = []
        self._lock = asyncio.Lock()
        self._measurement_start = datetime.now()
    
    async def record_request(
        self,
        success: bool,
        latency: float,  # ミリ秒
        downtime: float = 0.0  # 秒
    ) -> None:
        """リクエストを記録"""
        async with self._lock:
            self.metrics.total_requests += 1
            self.metrics.latencies.append(latency)
            
            if success:
                self.metrics.successful_requests += 1
            else:
                self.metrics.failed_requests += 1
            
            self.metrics.total_downtime += downtime
            
            # SLA違反をチェック
            await self._check_sla_breaches()
    
    async def _check_sla_breaches(self) -> None:
        """SLA違反をチェック"""
        current_availability = self.metrics.get_availability()
        current_error_rate = self.metrics.get_error_rate()
        p99_latency = self.metrics.get_p99_latency()
        p95_latency = self.metrics.get_p95_latency()
        
        # 可用性チェック
        if current_availability < self.thresholds.availability_target:
            breach = SLABreach(
                metric="availability",
                threshold=self.thresholds.availability_target,
                actual_value=current_availability,
                timestamp=datetime.now(),
                severity="critical"
            )
            if breach not in self.breaches:
                self.breaches.append(breach)
                await self._trigger_alerts(breach)
        
        # エラー率チェック
        if current_error_rate > self.thresholds.error_rate_threshold:
            breach = SLABreach(
                metric="error_rate",
                threshold=self.thresholds.error_rate_threshold,
                actual_value=current_error_rate,
                timestamp=datetime.now(),
                severity="warning"
            )
            if breach not in self.breaches:
                self.breaches.append(breach)
                await self._trigger_alerts(breach)
        
        # P99レイテンシチェック
        if p99_latency > self.thresholds.p99_latency:
            breach = SLABreach(
                metric="p99_latency",
                threshold=self.thresholds.p99_latency,
                actual_value=p99_latency,
                timestamp=datetime.now(),
                severity="warning"
            )
            if breach not in self.breaches:
                self.breaches.append(breach)
                await self._trigger_alerts(breach)
        
        # P95レイテンシチェック
        if p95_latency > self.thresholds.p95_latency:
            logger.debug(f"P95 latency warning: {p95_latency:.1f}ms > {self.thresholds.p95_latency}ms")
    
    async def _trigger_alerts(self, breach: SLABreach) -> None:
        """アラートをトリガー"""
        logger.warning(
            f"SLA Breach Detected: {breach.metric} = {breach.actual_value} "
            f"(threshold: {breach.threshold}) [{breach.severity}]"
        )
        
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(breach)
                else:
                    callback(breach)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
    
    def register_alert_callback(self, callback: Callable) -> None:
        """アラートコールバックを登録"""
        self.alert_callbacks.append(callback)
    
    def get_sla_report(self) -> Dict[str, Any]:
        """SLAレポートを取得"""
        availability = self.metrics.get_availability()
        error_rate = self.metrics.get_error_rate()
        
        return {
            "measurement_period": {
                "start": self.metrics.measurement_start.isoformat(),
                "end": (self.metrics.measurement_end or datetime.now()).isoformat(),
            },
            "availability": {
                "actual": availability,
                "target": self.thresholds.availability_target,
                "status": "OK" if availability >= self.thresholds.availability_target else "BREACH",
            },
            "error_rate": {
                "actual": error_rate,
                "threshold": self.thresholds.error_rate_threshold,
                "status": "OK" if error_rate <= self.thresholds.error_rate_threshold else "BREACH",
            },
            "latency": {
                "p99": {
                    "actual": self.metrics.get_p99_latency(),
                    "threshold": self.thresholds.p99_latency,
                    "status": "OK" if self.metrics.get_p99_latency() <= self.thresholds.p99_latency else "BREACH",
                },
                "p95": {
                    "actual": self.metrics.get_p95_latency(),
                    "threshold": self.thresholds.p95_latency,
                    "status": "OK" if self.metrics.get_p95_latency() <= self.thresholds.p95_latency else "BREACH",
                },
                "p50": self.metrics.get_p50_latency(),
                "avg": self.metrics.get_avg_latency(),
            },
            "requests": {
                "total": self.metrics.total_requests,
                "successful": self.metrics.successful_requests,
                "failed": self.metrics.failed_requests,
            },
            "downtime": {
                "total": self.metrics.total_downtime,
                "max_allowed_per_month": self.thresholds.max_downtime_per_month,
            },
            "breaches": [
                {
                    "metric": b.metric,
                    "threshold": b.threshold,
                    "actual": b.actual_value,
                    "timestamp": b.timestamp.isoformat(),
                    "severity": b.severity,
                }
                for b in self.breaches
            ],
        }
    
    def reset_metrics(self) -> None:
        """メトリクスをリセット"""
        self.metrics = SLAMetrics()
        self.breaches = []
        self._measurement_start = datetime.now()
