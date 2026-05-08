"""
Phase 18: Monitoring & Observability Infrastructure

監視・可観測性システム
- リアルタイムメトリクス収集
- 分散トレーシング
- ログ集約
- パフォーマンスダッシュボード
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import json
import logging


class MetricType(Enum):
    """メトリクス種別"""
    COUNTER = "counter"  # 累積カウンタ
    GAUGE = "gauge"  # 現在値
    HISTOGRAM = "histogram"  # 分布
    TIMER = "timer"  # 実行時間


class LogLevel(Enum):
    """ログレベル"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class TraceStatus(Enum):
    """トレースステータス"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class Metric:
    """メトリクス定義"""
    name: str
    metric_type: MetricType
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    unit: str = ""


@dataclass
class LogEntry:
    """ログエントリ"""
    timestamp: datetime
    level: LogLevel
    logger: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    trace_id: Optional[str] = None
    span_id: Optional[str] = None


@dataclass
class Span:
    """分散トレーシングスパン"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: TraceStatus = TraceStatus.PENDING
    tags: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)


class MetricsCollector:
    """メトリクス収集エンジン"""
    
    def __init__(self):
        self.metrics: List[Metric] = []
        self.metric_registry: Dict[str, Metric] = {}
        self.logger = logging.getLogger(__name__)
    
    def record_metric(self, name: str, value: float, metric_type: MetricType,
                     labels: Optional[Dict[str, str]] = None,
                     unit: str = "") -> None:
        """
        メトリクス記録
        
        Args:
            name: メトリクス名
            value: 値
            metric_type: メトリクス種別
            labels: ラベル
            unit: 単位
        """
        metric = Metric(
            name=name,
            metric_type=metric_type,
            value=value,
            labels=labels or {},
            unit=unit
        )
        
        self.metrics.append(metric)
        self.metric_registry[name] = metric
    
    def counter_increment(self, name: str, value: float = 1.0,
                         labels: Optional[Dict[str, str]] = None) -> None:
        """カウンタ増加"""
        existing = self.metric_registry.get(name)
        
        if existing and existing.metric_type == MetricType.COUNTER:
            existing.value += value
        else:
            self.record_metric(name, value, MetricType.COUNTER, labels)
    
    def gauge_set(self, name: str, value: float,
                 labels: Optional[Dict[str, str]] = None) -> None:
        """ゲージ設定"""
        self.record_metric(name, value, MetricType.GAUGE, labels)
    
    def timer_observe(self, name: str, duration_ms: float,
                     labels: Optional[Dict[str, str]] = None) -> None:
        """タイマー観測"""
        self.record_metric(name, duration_ms, MetricType.TIMER, labels, "ms")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """メトリクスサマリー取得"""
        summary = {
            "total_metrics": len(self.metrics),
            "by_type": {},
            "latest": {}
        }
        
        for metric_type in MetricType:
            count = sum(1 for m in self.metrics if m.metric_type == metric_type)
            summary["by_type"][metric_type.value] = count
        
        # 最新メトリクス
        for name, metric in self.metric_registry.items():
            summary["latest"][name] = {
                "value": metric.value,
                "type": metric.metric_type.value,
                "timestamp": metric.timestamp.isoformat()
            }
        
        return summary


class DistributedTracer:
    """分散トレーシングエンジン"""
    
    def __init__(self):
        self.spans: Dict[str, Span] = {}
        self.active_traces: Dict[str, List[str]] = {}  # trace_id -> span_ids
        self.logger = logging.getLogger(__name__)
    
    def start_span(self, trace_id: str, operation_name: str,
                  parent_span_id: Optional[str] = None) -> Span:
        """
        スパン開始
        
        Args:
            trace_id: トレースID
            operation_name: 操作名
            parent_span_id: 親スパンID
        
        Returns:
            Span: 作成されたスパン
        """
        import uuid
        span_id = str(uuid.uuid4())[:8]
        
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            start_time=datetime.now()
        )
        
        self.spans[span_id] = span
        
        if trace_id not in self.active_traces:
            self.active_traces[trace_id] = []
        self.active_traces[trace_id].append(span_id)
        
        return span
    
    def end_span(self, span_id: str, status: TraceStatus = TraceStatus.SUCCESS) -> None:
        """
        スパン終了
        
        Args:
            span_id: スパンID
            status: ステータス
        """
        if span_id in self.spans:
            self.spans[span_id].end_time = datetime.now()
            self.spans[span_id].status = status
    
    def add_span_tag(self, span_id: str, key: str, value: Any) -> None:
        """スパンタグ追加"""
        if span_id in self.spans:
            self.spans[span_id].tags[key] = value
    
    def add_span_log(self, span_id: str, message: str) -> None:
        """スパンログ追加"""
        if span_id in self.spans:
            self.spans[span_id].logs.append(message)
    
    def get_trace(self, trace_id: str) -> Dict[str, Any]:
        """トレース情報取得"""
        span_ids = self.active_traces.get(trace_id, [])
        spans_data = []
        
        for span_id in span_ids:
            if span_id in self.spans:
                span = self.spans[span_id]
                duration = None
                if span.end_time:
                    duration = (span.end_time - span.start_time).total_seconds()
                
                spans_data.append({
                    "span_id": span.span_id,
                    "operation": span.operation_name,
                    "status": span.status.value,
                    "duration_seconds": duration,
                    "tags": span.tags,
                    "logs": span.logs
                })
        
        return {
            "trace_id": trace_id,
            "span_count": len(spans_data),
            "spans": spans_data
        }


class LogAggregator:
    """ログ集約エンジン"""
    
    def __init__(self, max_logs: int = 10000):
        self.logs: List[LogEntry] = []
        self.max_logs = max_logs
        self.level_counts: Dict[str, int] = {}
    
    def add_log(self, level: LogLevel, logger: str, message: str,
               context: Optional[Dict[str, Any]] = None,
               trace_id: Optional[str] = None,
               span_id: Optional[str] = None) -> None:
        """
        ログエントリ追加
        
        Args:
            level: ログレベル
            logger: ロガー名
            message: メッセージ
            context: コンテキスト
            trace_id: トレースID
            span_id: スパンID
        """
        log_entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            logger=logger,
            message=message,
            context=context or {},
            trace_id=trace_id,
            span_id=span_id
        )
        
        self.logs.append(log_entry)
        
        # レベル別カウント
        level_key = level.value
        self.level_counts[level_key] = self.level_counts.get(level_key, 0) + 1
        
        # サイズ制限
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]
    
    def get_logs(self, level: Optional[LogLevel] = None,
                logger: Optional[str] = None,
                limit: int = 100) -> List[LogEntry]:
        """
        ログ取得
        
        Args:
            level: フィルタ対象レベル
            logger: フィルタ対象ロガー
            limit: 返却上限
        
        Returns:
            ログエントリリスト
        """
        filtered = self.logs
        
        if level:
            filtered = [l for l in filtered if l.level == level]
        
        if logger:
            filtered = [l for l in filtered if l.logger == logger]
        
        return filtered[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報取得"""
        return {
            "total_logs": len(self.logs),
            "by_level": self.level_counts,
            "unique_loggers": len(set(l.logger for l in self.logs)),
            "with_trace": sum(1 for l in self.logs if l.trace_id)
        }


class PerformanceDashboard:
    """パフォーマンスダッシュボード"""
    
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.tracer = DistributedTracer()
        self.log_aggregator = LogAggregator()
    
    def record_operation(self, operation_name: str, duration_ms: float,
                        success: bool, labels: Optional[Dict[str, str]] = None) -> None:
        """
        オペレーション記録
        
        Args:
            operation_name: 操作名
            duration_ms: 実行時間（ms）
            success: 成功フラグ
            labels: ラベル
        """
        # メトリクス記録
        self.metrics_collector.timer_observe(f"{operation_name}_duration", duration_ms, labels)
        
        # カウンタ更新
        if success:
            self.metrics_collector.counter_increment(f"{operation_name}_success", labels=labels)
        else:
            self.metrics_collector.counter_increment(f"{operation_name}_failure", labels=labels)
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        ダッシュボード表示データ取得
        
        Returns:
            ダッシュボード用データ
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "metrics": self.metrics_collector.get_metrics_summary(),
            "logs": self.log_aggregator.get_statistics(),
            "traces": {
                "active_count": len(self.tracer.active_traces),
                "total_spans": len(self.tracer.spans)
            }
        }
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """パフォーマンスレポート生成"""
        metrics = self.metrics_collector.get_metrics_summary()
        logs = self.log_aggregator.get_statistics()
        
        # パフォーマンス指標の計算
        timers = [m for m in self.metrics_collector.metrics 
                 if m.metric_type == MetricType.TIMER]
        
        avg_duration = 0
        max_duration = 0
        min_duration = float('inf')
        
        if timers:
            durations = [m.value for m in timers]
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            min_duration = min(durations)
        
        # エラー率計算
        error_rate = 0
        if logs["by_level"].get("ERROR", 0) + logs["by_level"].get("CRITICAL", 0) > 0:
            total_errors = logs["by_level"].get("ERROR", 0) + logs["by_level"].get("CRITICAL", 0)
            error_rate = (total_errors / logs["total_logs"] * 100) if logs["total_logs"] > 0 else 0
        
        return {
            "summary": {
                "total_metrics": metrics["total_metrics"],
                "total_logs": logs["total_logs"],
                "error_rate_percent": round(error_rate, 2)
            },
            "performance": {
                "avg_duration_ms": round(avg_duration, 2),
                "max_duration_ms": round(max_duration, 2),
                "min_duration_ms": round(min_duration, 2) if min_duration != float('inf') else 0
            },
            "log_distribution": logs["by_level"],
            "timestamp": datetime.now().isoformat()
        }
