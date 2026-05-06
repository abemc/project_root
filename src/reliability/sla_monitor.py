import time
import logging
import json
import os
from pathlib import Path
from collections import deque
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SLAMonitor:
    """
    Phase 19 Task 1: SLA & 信頼性確保
    可用性とレイテンシ（p99）を監視し、SLA違反を検知するクラス。
    """

    def __init__(self, window_size: int = 100, log_path: str = "logs/sla_metrics.jsonl"):
        self.window_size = window_size
        self.log_path = Path(log_path)
        self.latencies = deque(maxlen=window_size)
        self.success_count = 0
        self.failure_count = 0
        
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def record_request(self, duration: float, success: bool):
        """リクエストの結果を記録する。"""
        self.latencies.append(duration)
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        
        self._log_metrics()

    def get_metrics(self) -> Dict[str, Any]:
        """現在のメトリクスを取得する。"""
        total = self.success_count + self.failure_count
        availability = (self.success_count / total * 100) if total > 0 else 100.0
        
        sorted_latencies = sorted(list(self.latencies))
        p99 = 0.0
        if sorted_latencies:
            p99_idx = int(len(sorted_latencies) * 0.99)
            p99 = sorted_latencies[min(p99_idx, len(sorted_latencies) - 1)]
        
        return {
            "timestamp": time.time(),
            "availability": round(availability, 4),
            "p99_latency": round(p99, 4),
            "total_requests": total,
            "success_rate": round(self.success_count / total, 4) if total > 0 else 1.0
        }

    def _log_metrics(self):
        """メトリクスをJSONLファイルに保存する。"""
        metrics = self.get_metrics()
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(metrics) + "\n")
        except Exception as e:
            logger.error(f"Failed to log SLA metrics: {e}")

    def check_sla_violation(self, availability_threshold: float = 99.99, latency_threshold: float = 0.5) -> bool:
        """SLA違反が発生しているかチェックする。"""
        metrics = self.get_metrics()
        violated = False
        
        if metrics["availability"] < availability_threshold:
            logger.error(f"SLA Violation: Availability {metrics['availability']}% below threshold {availability_threshold}%")
            violated = True
        
        if metrics["p99_latency"] > latency_threshold:
            logger.error(f"SLA Violation: p99 Latency {metrics['p99_latency']}s above threshold {latency_threshold}s")
            violated = True
            
        return violated
