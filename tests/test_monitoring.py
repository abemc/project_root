"""
Phase 18: Monitoring & Observability Tests

監視・可観測性システムのテスト
- メトリクス収集
- 分散トレーシング
- ログ集約
- パフォーマンスダッシュボード
"""

from src.monitoring.monitoring_engine import (
    MetricsCollector, DistributedTracer, LogAggregator, PerformanceDashboard,
    MetricType, LogLevel, TraceStatus
)


class TestMetricsCollector:
    """メトリクス収集テスト"""
    
    def setup_method(self):
        self.collector = MetricsCollector()
    
    def test_collector_initialization(self):
        """コレクタ初期化"""
        assert self.collector is not None
        assert len(self.collector.metrics) == 0
    
    def test_record_counter_metric(self):
        """カウンタメトリクス記録"""
        self.collector.record_metric("requests", 42, MetricType.COUNTER)
        
        assert len(self.collector.metrics) == 1
        assert self.collector.metrics[0].value == 42
        assert self.collector.metrics[0].metric_type == MetricType.COUNTER
    
    def test_record_gauge_metric(self):
        """ゲージメトリクス記録"""
        self.collector.record_metric("memory_usage", 75.5, MetricType.GAUGE, unit="percent")
        
        assert self.collector.metrics[0].value == 75.5
        assert self.collector.metrics[0].unit == "percent"
    
    def test_record_histogram_metric(self):
        """ヒストグラムメトリクス記録"""
        self.collector.record_metric("response_times", 250, MetricType.HISTOGRAM)
        
        assert self.collector.metrics[0].metric_type == MetricType.HISTOGRAM
    
    def test_counter_increment(self):
        """カウンタ増加"""
        self.collector.counter_increment("api_calls", 5)
        self.collector.counter_increment("api_calls", 3)
        
        assert self.collector.metric_registry["api_calls"].value == 8
    
    def test_gauge_set(self):
        """ゲージ設定"""
        self.collector.gauge_set("cpu_usage", 45.0)
        self.collector.gauge_set("cpu_usage", 60.0)
        
        assert self.collector.metric_registry["cpu_usage"].value == 60.0
    
    def test_timer_observe(self):
        """タイマー観測"""
        self.collector.timer_observe("operation_time", 125.5)
        
        metric = self.collector.metrics[0]
        assert metric.value == 125.5
        assert metric.unit == "ms"
    
    def test_metrics_with_labels(self):
        """ラベル付きメトリクス"""
        labels = {"endpoint": "/api/users", "method": "GET"}
        self.collector.record_metric("requests", 100, MetricType.COUNTER, labels)
        
        assert self.collector.metrics[0].labels == labels
    
    def test_get_metrics_summary(self):
        """メトリクスサマリー取得"""
        self.collector.record_metric("m1", 10, MetricType.COUNTER)
        self.collector.record_metric("m2", 20, MetricType.GAUGE)
        self.collector.record_metric("m3", 30, MetricType.TIMER)
        
        summary = self.collector.get_metrics_summary()
        
        assert summary["total_metrics"] == 3
        assert summary["by_type"]["counter"] == 1
        assert summary["by_type"]["gauge"] == 1


class TestDistributedTracer:
    """分散トレーシングテスト"""
    
    def setup_method(self):
        self.tracer = DistributedTracer()
    
    def test_tracer_initialization(self):
        """トレーサー初期化"""
        assert self.tracer is not None
        assert len(self.tracer.spans) == 0
    
    def test_start_span(self):
        """スパン開始"""
        span = self.tracer.start_span("trace_1", "user_request")
        
        assert span.trace_id == "trace_1"
        assert span.operation_name == "user_request"
        assert span.status == TraceStatus.PENDING
    
    def test_end_span(self):
        """スパン終了"""
        span = self.tracer.start_span("trace_1", "operation")
        self.tracer.end_span(span.span_id, TraceStatus.SUCCESS)
        
        ended_span = self.tracer.spans[span.span_id]
        assert ended_span.status == TraceStatus.SUCCESS
        assert ended_span.end_time is not None
    
    def test_span_hierarchy(self):
        """スパン階層"""
        parent_span = self.tracer.start_span("trace_1", "parent_op")
        child_span = self.tracer.start_span("trace_1", "child_op", parent_span.span_id)
        
        assert child_span.parent_span_id == parent_span.span_id
    
    def test_add_span_tag(self):
        """スパンタグ追加"""
        span = self.tracer.start_span("trace_1", "operation")
        self.tracer.add_span_tag(span.span_id, "user_id", "user_123")
        self.tracer.add_span_tag(span.span_id, "status", "active")
        
        assert self.tracer.spans[span.span_id].tags["user_id"] == "user_123"
        assert self.tracer.spans[span.span_id].tags["status"] == "active"
    
    def test_add_span_log(self):
        """スパンログ追加"""
        span = self.tracer.start_span("trace_1", "operation")
        self.tracer.add_span_log(span.span_id, "Processing started")
        self.tracer.add_span_log(span.span_id, "Processing completed")
        
        logs = self.tracer.spans[span.span_id].logs
        assert len(logs) == 2
        assert "Processing started" in logs
    
    def test_get_trace(self):
        """トレース情報取得"""
        span1 = self.tracer.start_span("trace_1", "operation1")
        span2 = self.tracer.start_span("trace_1", "operation2")
        
        self.tracer.end_span(span1.span_id, TraceStatus.SUCCESS)
        self.tracer.end_span(span2.span_id, TraceStatus.SUCCESS)
        
        trace = self.tracer.get_trace("trace_1")
        
        assert trace["trace_id"] == "trace_1"
        assert trace["span_count"] == 2


class TestLogAggregator:
    """ログ集約テスト"""
    
    def setup_method(self):
        self.aggregator = LogAggregator()
    
    def test_aggregator_initialization(self):
        """ログアグリゲータ初期化"""
        assert self.aggregator is not None
        assert len(self.aggregator.logs) == 0
    
    def test_add_debug_log(self):
        """デバッグログ追加"""
        self.aggregator.add_log(LogLevel.DEBUG, "test_logger", "Debug message")
        
        assert len(self.aggregator.logs) == 1
        assert self.aggregator.logs[0].level == LogLevel.DEBUG
    
    def test_add_error_log(self):
        """エラーログ追加"""
        self.aggregator.add_log(LogLevel.ERROR, "test_logger", "Error message")
        
        assert self.aggregator.logs[0].level == LogLevel.ERROR
        assert self.aggregator.level_counts["ERROR"] == 1
    
    def test_add_log_with_context(self):
        """コンテキスト付きログ追加"""
        context = {"user_id": "123", "action": "login"}
        self.aggregator.add_log(LogLevel.INFO, "auth", "User login", context)
        
        assert self.aggregator.logs[0].context == context
    
    def test_add_log_with_trace(self):
        """トレース情報付きログ"""
        self.aggregator.add_log(
            LogLevel.INFO, "logger",
            "Message",
            trace_id="trace_123",
            span_id="span_456"
        )
        
        log = self.aggregator.logs[0]
        assert log.trace_id == "trace_123"
        assert log.span_id == "span_456"
    
    def test_get_logs_filter_by_level(self):
        """ログレベルでフィルタ"""
        self.aggregator.add_log(LogLevel.INFO, "logger", "Info")
        self.aggregator.add_log(LogLevel.ERROR, "logger", "Error")
        self.aggregator.add_log(LogLevel.WARNING, "logger", "Warning")
        
        errors = self.aggregator.get_logs(level=LogLevel.ERROR)
        assert len(errors) == 1
        assert errors[0].level == LogLevel.ERROR
    
    def test_get_logs_filter_by_logger(self):
        """ロガー名でフィルタ"""
        self.aggregator.add_log(LogLevel.INFO, "logger1", "Message1")
        self.aggregator.add_log(LogLevel.INFO, "logger2", "Message2")
        
        logger1_logs = self.aggregator.get_logs(logger="logger1")
        assert len(logger1_logs) == 1
        assert logger1_logs[0].logger == "logger1"
    
    def test_get_statistics(self):
        """統計情報取得"""
        self.aggregator.add_log(LogLevel.INFO, "logger1", "Message1")
        self.aggregator.add_log(LogLevel.ERROR, "logger2", "Message2")
        self.aggregator.add_log(LogLevel.WARNING, "logger1", "Message3", trace_id="trace_1")
        
        stats = self.aggregator.get_statistics()
        
        assert stats["total_logs"] == 3
        assert stats["by_level"]["INFO"] == 1
        assert stats["unique_loggers"] == 2
        assert stats["with_trace"] == 1


class TestPerformanceDashboard:
    """パフォーマンスダッシュボードテスト"""
    
    def setup_method(self):
        self.dashboard = PerformanceDashboard()
    
    def test_dashboard_initialization(self):
        """ダッシュボード初期化"""
        assert self.dashboard is not None
        assert self.dashboard.metrics_collector is not None
        assert self.dashboard.tracer is not None
        assert self.dashboard.log_aggregator is not None
    
    def test_record_operation_success(self):
        """成功オペレーション記録"""
        self.dashboard.record_operation("database_query", 125.5, True)
        
        metrics = self.dashboard.metrics_collector.get_metrics_summary()
        assert metrics["total_metrics"] == 2  # duration + success
    
    def test_record_operation_failure(self):
        """失敗オペレーション記録"""
        self.dashboard.record_operation("api_call", 500, False)
        
        metrics = self.dashboard.metrics_collector.get_metrics_summary()
        assert metrics["total_metrics"] == 2  # duration + failure
    
    def test_record_multiple_operations(self):
        """複数オペレーション記録"""
        self.dashboard.record_operation("op1", 100, True)
        self.dashboard.record_operation("op2", 200, True)
        self.dashboard.record_operation("op1", 150, True)
        
        metrics = self.dashboard.metrics_collector.get_metrics_summary()
        # op1が2回なので、op1_successは増加、uniqueなメトリクス数は5
        assert metrics["total_metrics"] >= 5
    
    def test_get_dashboard_data(self):
        """ダッシュボードデータ取得"""
        self.dashboard.record_operation("operation", 100, True)
        
        data = self.dashboard.get_dashboard_data()
        
        assert "timestamp" in data
        assert "metrics" in data
        assert "logs" in data
        assert "traces" in data
    
    def test_generate_performance_report(self):
        """パフォーマンスレポート生成"""
        self.dashboard.record_operation("op1", 100, True)
        self.dashboard.record_operation("op2", 200, True)
        self.dashboard.record_operation("op3", 150, True)
        
        report = self.dashboard.generate_performance_report()
        
        assert "summary" in report
        assert "performance" in report
        assert "log_distribution" in report
        
        # 平均値確認
        assert report["performance"]["avg_duration_ms"] == 150.0
        assert report["performance"]["max_duration_ms"] == 200.0
        assert report["performance"]["min_duration_ms"] == 100.0


class TestMonitoringIntegration:
    """統合監視テスト"""
    
    def test_end_to_end_monitoring(self):
        """エンドツーエンド監視"""
        dashboard = PerformanceDashboard()
        
        # オペレーション記録
        dashboard.record_operation("request_processing", 250, True, 
                                  {"endpoint": "/api/data"})
        
        # トレース記録
        span = dashboard.tracer.start_span("trace_1", "request_processing")
        dashboard.tracer.add_span_tag(span.span_id, "status", "success")
        dashboard.tracer.end_span(span.span_id, TraceStatus.SUCCESS)
        
        # ログ記録
        dashboard.log_aggregator.add_log(
            LogLevel.INFO, "request_handler",
            "Request processed", trace_id="trace_1"
        )
        
        # ダッシュボード確認
        data = dashboard.get_dashboard_data()
        assert data["metrics"]["total_metrics"] > 0
        assert data["logs"]["total_logs"] == 1
        assert data["traces"]["active_count"] == 1
    
    def test_performance_report_with_errors(self):
        """エラーを含むパフォーマンスレポート"""
        dashboard = PerformanceDashboard()
        
        # 複数のオペレーション
        dashboard.record_operation("operation", 100, True)
        dashboard.record_operation("operation", 200, False)
        
        # ログにエラー追加
        dashboard.log_aggregator.add_log(LogLevel.ERROR, "system", "Operation failed")
        
        report = dashboard.generate_performance_report()
        
        assert report["summary"]["error_rate_percent"] > 0
        assert report["log_distribution"].get("ERROR", 0) > 0
    
    def test_metrics_with_custom_labels(self):
        """カスタムラベル付きメトリクス"""
        dashboard = PerformanceDashboard()
        
        labels = {"service": "auth", "region": "us-east-1"}
        dashboard.record_operation("user_login", 150, True, labels)
        
        metrics = dashboard.metrics_collector.get_metrics_summary()
        assert metrics["total_metrics"] > 0
