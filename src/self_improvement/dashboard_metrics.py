"""
Phase 4: Dashboard Metrics
==========================

Real-time metrics collection and trend analysis for the dashboard.

Features:
  - Real-time metric aggregation
  - Trend detection (improving, stable, declining)
  - Performance snapshots
  - Historical data tracking
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
import statistics

logger = logging.getLogger(__name__)


@dataclass
class MetricSnapshot:
    """Point-in-time metrics snapshot"""
    timestamp: str
    average_rating: float
    rating_trend: str  # "improving", "stable", "declining"
    error_rate: float
    total_feedbacks: int
    feedback_count_24h: int
    avg_response_time_ms: float
    improvement_count: int
    rollback_count: int
    last_ab_test: Optional[str] = None


class DashboardMetrics:
    """Real-time metrics manager"""

    def __init__(self, storage_dir: str = None):
        """
        Args:
            storage_dir: Directory for metrics history (default: logs/metrics)
        """
        if storage_dir is None:
            storage_dir = Path("logs/metrics")
        else:
            storage_dir = Path(storage_dir)

        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.history_file = self.storage_dir / "metrics_history.jsonl"
        self.current_metrics: Optional[MetricSnapshot] = None
        self.metrics_history: List[MetricSnapshot] = []

        self._load_history()
        logger.info("DashboardMetrics initialized")

    def record_metrics(
        self,
        average_rating: float,
        error_rate: float,
        total_feedbacks: int,
        feedback_count_24h: int,
        avg_response_time_ms: float,
        improvement_count: int = 0,
        rollback_count: int = 0,
        last_ab_test: Optional[str] = None,
    ) -> MetricSnapshot:
        """
        Record current metrics snapshot.

        Args:
            average_rating: Average user rating (0-1)
            error_rate: Fraction of errors
            total_feedbacks: Total feedback count
            feedback_count_24h: Feedbacks in last 24h
            avg_response_time_ms: Average response time
            improvement_count: Number of improvements applied
            rollback_count: Number of rollbacks executed
            last_ab_test: ID of last A/B test

        Returns:
            Created MetricSnapshot
        """
        # Detect trend
        trend = self._detect_trend(average_rating)

        snapshot = MetricSnapshot(
            timestamp=datetime.now().isoformat(),
            average_rating=average_rating,
            rating_trend=trend,
            error_rate=error_rate,
            total_feedbacks=total_feedbacks,
            feedback_count_24h=feedback_count_24h,
            avg_response_time_ms=avg_response_time_ms,
            improvement_count=improvement_count,
            rollback_count=rollback_count,
            last_ab_test=last_ab_test,
        )

        self.current_metrics = snapshot
        self.metrics_history.append(snapshot)
        self._persist_snapshot(snapshot)

        logger.info(
            f"Metrics recorded: rating={average_rating:.3f}, "
            f"trend={trend}, errors={error_rate:.1%}"
        )

        return snapshot

    def get_current_metrics(self) -> Optional[MetricSnapshot]:
        """Get most recent metrics"""
        return self.current_metrics

    def get_metrics_range(
        self, hours: int = 24
    ) -> List[MetricSnapshot]:
        """Get metrics from last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        cutoff_iso = cutoff.isoformat()

        return [
            m for m in self.metrics_history
            if m.timestamp >= cutoff_iso
        ]

    def calculate_trend_stats(self, hours: int = 24) -> Dict:
        """Calculate trend statistics"""
        snapshots = self.get_metrics_range(hours)

        if not snapshots:
            return {
                "data_points": 0,
                "avg_rating": 0.0,
                "min_rating": 0.0,
                "max_rating": 0.0,
                "rating_volatility": 0.0,
                "trend": "unknown",
            }

        ratings = [s.average_rating for s in snapshots]
        error_rates = [s.error_rate for s in snapshots]

        avg_rating = statistics.mean(ratings) if len(ratings) > 0 else 0.0
        volatility = statistics.stdev(ratings) if len(ratings) > 1 else 0.0

        return {
            "data_points": len(snapshots),
            "avg_rating": avg_rating,
            "min_rating": min(ratings),
            "max_rating": max(ratings),
            "rating_volatility": volatility,
            "avg_error_rate": statistics.mean(error_rates) if error_rates else 0.0,
            "trend": snapshots[-1].rating_trend if snapshots else "unknown",
            "time_period_hours": hours,
        }

    def get_performance_index(self) -> float:
        """
        Calculate composite performance index (0-100).

        Index based on:
          - Average rating (weight: 50%)
          - Error rate (weight: 30%)
          - Response time (weight: 20%)
        """
        if not self.current_metrics:
            return 0.0

        metrics = self.current_metrics

        # Rating component (0-100): rating * 100
        rating_score = metrics.average_rating * 100

        # Error component (0-100): (1 - error_rate) * 100
        error_score = (1 - min(metrics.error_rate, 1.0)) * 100

        # Response time component (0-100)
        # Consider < 100ms as ideal (100), > 500ms as poor (0)
        if metrics.avg_response_time_ms <= 100:
            response_score = 100
        elif metrics.avg_response_time_ms >= 500:
            response_score = 0
        else:
            response_score = 100 * (1 - (metrics.avg_response_time_ms - 100) / 400)

        # Weighted composite
        index = (
            rating_score * 0.5 +
            error_score * 0.3 +
            response_score * 0.2
        )

        return max(0.0, min(100.0, index))

    def get_health_status(self) -> str:
        """Determine system health status"""
        if not self.current_metrics:
            return "UNKNOWN"

        index = self.get_performance_index()

        if index >= 80:
            return "EXCELLENT"
        elif index >= 60:
            return "GOOD"
        elif index >= 40:
            return "FAIR"
        elif index >= 20:
            return "POOR"
        else:
            return "CRITICAL"

    def get_health_details(self) -> Dict:
        """Get detailed health assessment"""
        if not self.current_metrics:
            return {"status": "UNKNOWN", "details": []}

        metrics = self.current_metrics
        status = self.get_health_status()
        index = self.get_performance_index()

        details = []

        # Rating assessment
        if metrics.average_rating >= 0.8:
            details.append({"component": "Rating", "status": "🟢 Excellent", "value": f"{metrics.average_rating:.1%}"})
        elif metrics.average_rating >= 0.6:
            details.append({"component": "Rating", "status": "🟡 Good", "value": f"{metrics.average_rating:.1%}"})
        else:
            details.append({"component": "Rating", "status": "🔴 Low", "value": f"{metrics.average_rating:.1%}"})

        # Error rate assessment
        if metrics.error_rate <= 0.02:
            details.append({"component": "Errors", "status": "🟢 Excellent", "value": f"{metrics.error_rate:.1%}"})
        elif metrics.error_rate <= 0.05:
            details.append({"component": "Errors", "status": "🟡 Acceptable", "value": f"{metrics.error_rate:.1%}"})
        else:
            details.append({"component": "Errors", "status": "🔴 High", "value": f"{metrics.error_rate:.1%}"})

        # Response time assessment
        if metrics.avg_response_time_ms <= 150:
            details.append({"component": "Response", "status": "🟢 Fast", "value": f"{metrics.avg_response_time_ms:.0f}ms"})
        elif metrics.avg_response_time_ms <= 300:
            details.append({"component": "Response", "status": "🟡 Normal", "value": f"{metrics.avg_response_time_ms:.0f}ms"})
        else:
            details.append({"component": "Response", "status": "🔴 Slow", "value": f"{metrics.avg_response_time_ms:.0f}ms"})

        # Trend assessment
        if metrics.rating_trend == "improving":
            details.append({"component": "Trend", "status": "📈 Improving", "value": metrics.rating_trend})
        elif metrics.rating_trend == "stable":
            details.append({"component": "Trend", "status": "➡️ Stable", "value": metrics.rating_trend})
        else:
            details.append({"component": "Trend", "status": "📉 Declining", "value": metrics.rating_trend})

        return {
            "status": status,
            "overall_index": index,
            "details": details,
            "timestamp": metrics.timestamp,
        }

    def _detect_trend(self, current_rating: float) -> str:
        """Detect rating trend (improving/stable/declining)"""
        if len(self.metrics_history) < 2:
            return "stable"

        # Compare current with previous
        prev_rating = self.metrics_history[-1].average_rating

        improvement = current_rating - prev_rating

        if improvement > 0.03:
            return "improving"
        elif improvement < -0.03:
            return "declining"
        else:
            return "stable"

    def _persist_snapshot(self, snapshot: MetricSnapshot):
        """Write snapshot to persistent storage"""
        data = {
            "timestamp": snapshot.timestamp,
            "average_rating": snapshot.average_rating,
            "rating_trend": snapshot.rating_trend,
            "error_rate": snapshot.error_rate,
            "total_feedbacks": snapshot.total_feedbacks,
            "feedback_count_24h": snapshot.feedback_count_24h,
            "avg_response_time_ms": snapshot.avg_response_time_ms,
            "improvement_count": snapshot.improvement_count,
            "rollback_count": snapshot.rollback_count,
            "last_ab_test": snapshot.last_ab_test,
        }

        with open(self.history_file, "a") as f:
            f.write(json.dumps(data) + "\n")

    def _load_history(self):
        """Load metrics history from persistent storage"""
        if not self.history_file.exists():
            return

        with open(self.history_file, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        snapshot = MetricSnapshot(
                            timestamp=data["timestamp"],
                            average_rating=data["average_rating"],
                            rating_trend=data["rating_trend"],
                            error_rate=data["error_rate"],
                            total_feedbacks=data["total_feedbacks"],
                            feedback_count_24h=data["feedback_count_24h"],
                            avg_response_time_ms=data["avg_response_time_ms"],
                            improvement_count=data.get("improvement_count", 0),
                            rollback_count=data.get("rollback_count", 0),
                            last_ab_test=data.get("last_ab_test"),
                        )
                        self.metrics_history.append(snapshot)
                    except Exception as e:
                        logger.warning(f"Failed to load metrics snapshot: {e}")

        if self.metrics_history:
            self.current_metrics = self.metrics_history[-1]
            logger.info(f"Loaded {len(self.metrics_history)} metrics snapshots")
