"""
Phase 4: Dashboard & Audit - Comprehensive Test Suite
=====================================================

Tests for audit logging and dashboard metrics:
  - AuditLogger: Event recording, queries, anomaly detection
  - DashboardMetrics: Metrics recording, trend analysis, health assessment
  - DashboardUI: Component rendering (placeholder tests)
"""

import unittest
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestAuditLogger(unittest.TestCase):
    """Test audit logging system"""

    def setUp(self):
        from src.self_improvement.audit_logger import (
            AuditLogger, EventType, AlertSeverity
        )
        self.EventType = EventType
        self.AlertSeverity = AlertSeverity
        
        # Create temporary directory for logs
        self.temp_dir = tempfile.mkdtemp()
        self.audit_logger = AuditLogger(log_dir=self.temp_dir)

    def tearDown(self):
        # Clean up temp directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_log_event(self):
        """Test event logging"""
        logger.info("TEST: Event logging")

        event = self.audit_logger.log_event(
            event_type=self.EventType.FEEDBACK_COLLECTED,
            component="phase_1",
            message="Feedback collected from 10 users",
            severity=self.AlertSeverity.INFO,
            detail={"count": 10, "avg_rating": 0.8},
        )

        self.assertIsNotNone(event.event_id)
        self.assertEqual(event.component, "phase_1")
        self.assertEqual(event.event_type, self.EventType.FEEDBACK_COLLECTED)
        logger.info(f"  ✓ Event logged: {event.event_id}")
        logger.info("✅ PASS: Event logging\n")

    def test_query_events(self):
        """Test event querying"""
        logger.info("TEST: Event querying")

        # Log multiple events
        for i in range(5):
            self.audit_logger.log_event(
                event_type=self.EventType.FEEDBACK_COLLECTED,
                component="phase_1",
                message=f"Feedback {i}",
                severity=self.AlertSeverity.INFO,
            )

        for i in range(3):
            self.audit_logger.log_event(
                event_type=self.EventType.PROMPT_OPTIMIZED,
                component="phase_1",
                message=f"Prompt optimized {i}",
                severity=self.AlertSeverity.INFO,
            )

        # Query by component
        phase1_events = self.audit_logger.get_events(component="phase_1")
        self.assertEqual(len(phase1_events), 8)
        logger.info(f"  ✓ Found {len(phase1_events)} phase_1 events")

        # Query by event type
        feedback_events = self.audit_logger.get_events(
            event_type=self.EventType.FEEDBACK_COLLECTED
        )
        self.assertEqual(len(feedback_events), 5)
        logger.info(f"  ✓ Found {len(feedback_events)} feedback events")

        # Query with limit
        recent = self.audit_logger.get_events(limit=3)
        self.assertEqual(len(recent), 3)
        logger.info(f"  ✓ Retrieved last 3 events")

        logger.info("✅ PASS: Event querying\n")

    def test_phase_summary(self):
        """Test phase summary generation"""
        logger.info("TEST: Phase summary")

        # Log events for multiple phases
        for i in range(3):
            self.audit_logger.log_event(
                event_type=self.EventType.FEEDBACK_COLLECTED,
                component="phase_1",
                message=f"Phase 1 event {i}",
            )

        for i in range(2):
            self.audit_logger.log_event(
                event_type=self.EventType.ROLLBACK_TRIGGERED,
                component="phase_2",
                message=f"Phase 2 event {i}",
            )

        # Get summaries
        summary1 = self.audit_logger.get_phase_summary("phase_1")
        summary2 = self.audit_logger.get_phase_summary("phase_2")

        self.assertEqual(summary1["total_events"], 3)
        self.assertEqual(summary2["total_events"], 2)
        logger.info(f"  ✓ Phase 1: {summary1['total_events']} events")
        logger.info(f"  ✓ Phase 2: {summary2['total_events']} events")

        logger.info("✅ PASS: Phase summary\n")

    def test_rollback_logging(self):
        """Test rollback event logging"""
        logger.info("TEST: Rollback event logging")

        event = self.audit_logger.log_rollback_event(
            reason="Rating drop detected",
            from_state="optimized_v2",
            to_state="stable_v1",
        )

        self.assertEqual(event.event_type, self.EventType.ROLLBACK_EXECUTED)
        self.assertEqual(event.severity, self.AlertSeverity.CRITICAL)
        self.assertEqual(event.component, "phase_2")
        logger.info(f"  ✓ Rollback logged: {event.message}")
        logger.info("✅ PASS: Rollback event logging\n")

    def test_ab_test_logging(self):
        """Test A/B test result logging"""
        logger.info("TEST: A/B test result logging")

        event = self.audit_logger.log_ab_test_result(
            test_id="abtest_001",
            best_candidate="combined_v2",
            recommendation="ADOPT",
            metrics={"p_value": 0.001, "cohens_d": 0.75},
        )

        self.assertEqual(event.event_type, self.EventType.AB_TEST_COMPLETED)
        self.assertEqual(event.component, "phase_3")
        logger.info(f"  ✓ A/B test logged: {event.detail['best_candidate']}")
        logger.info("✅ PASS: A/B test event logging\n")

    def test_summary_report(self):
        """Test summary report generation"""
        logger.info("TEST: Summary report generation")

        # Log various events
        for phase in ["phase_1", "phase_2", "phase_3"]:
            self.audit_logger.log_event(
                event_type=self.EventType.FEEDBACK_COLLECTED,
                component=phase,
                message=f"Test event for {phase}",
            )

        report = self.audit_logger.get_summary_report()

        self.assertIn("total_events", report)
        self.assertIn("phase_summaries", report)
        self.assertGreater(report["total_events"], 0)
        logger.info(f"  ✓ Total events: {report['total_events']}")
        logger.info(f"  ✓ Critical alerts: {report['active_alerts']}")
        logger.info("✅ PASS: Summary report generation\n")


class TestDashboardMetrics(unittest.TestCase):
    """Test dashboard metrics system"""

    def setUp(self):
        from src.self_improvement.dashboard_metrics import DashboardMetrics
        self.DashboardMetrics = DashboardMetrics

        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()
        self.metrics = DashboardMetrics(storage_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_metrics(self):
        """Test metrics recording"""
        logger.info("TEST: Metrics recording")

        snapshot = self.metrics.record_metrics(
            average_rating=0.85,
            error_rate=0.02,
            total_feedbacks=150,
            feedback_count_24h=45,
            avg_response_time_ms=120,
            improvement_count=3,
            rollback_count=0,
        )

        self.assertIsNotNone(snapshot.timestamp)
        self.assertEqual(snapshot.average_rating, 0.85)
        self.assertEqual(snapshot.error_rate, 0.02)
        logger.info(f"  ✓ Metrics recorded: rating={snapshot.average_rating:.1%}")
        logger.info("✅ PASS: Metrics recording\n")

    def test_get_current_metrics(self):
        """Test retrieving current metrics"""
        logger.info("TEST: Get current metrics")

        self.metrics.record_metrics(
            average_rating=0.80,
            error_rate=0.05,
            total_feedbacks=100,
            feedback_count_24h=30,
            avg_response_time_ms=150,
        )

        current = self.metrics.get_current_metrics()
        self.assertIsNotNone(current)
        self.assertEqual(current.average_rating, 0.80)
        logger.info(f"  ✓ Current rating: {current.average_rating:.1%}")
        logger.info("✅ PASS: Get current metrics\n")

    def test_trend_detection(self):
        """Test trend detection"""
        logger.info("TEST: Trend detection")

        # Record improving trend
        self.metrics.record_metrics(0.70, 0.05, 100, 30, 150)
        self.metrics.record_metrics(0.75, 0.04, 110, 35, 140)
        self.metrics.record_metrics(0.82, 0.03, 120, 40, 130)

        snapshot = self.metrics.get_current_metrics()
        self.assertEqual(snapshot.rating_trend, "improving")
        logger.info(f"  ✓ Detected trend: {snapshot.rating_trend}")
        logger.info("✅ PASS: Trend detection\n")

    def test_performance_index(self):
        """Test performance index calculation"""
        logger.info("TEST: Performance index calculation")

        self.metrics.record_metrics(
            average_rating=0.85,
            error_rate=0.02,
            total_feedbacks=150,
            feedback_count_24h=45,
            avg_response_time_ms=100,
        )

        index = self.metrics.get_performance_index()
        self.assertGreater(index, 0)
        self.assertLessEqual(index, 100)
        logger.info(f"  ✓ Performance index: {index:.1f}/100")
        logger.info("✅ PASS: Performance index calculation\n")

    def test_health_status(self):
        """Test health status assessment"""
        logger.info("TEST: Health status assessment")

        # Good health
        self.metrics.record_metrics(0.85, 0.02, 150, 45, 100)
        status = self.metrics.get_health_status()
        self.assertIn(status, ["EXCELLENT", "GOOD", "FAIR", "POOR", "CRITICAL"])
        logger.info(f"  ✓ Health status: {status}")

        health_details = self.metrics.get_health_details()
        self.assertIn("status", health_details)
        self.assertIn("details", health_details)
        logger.info(f"  ✓ Details retrieved: {len(health_details['details'])} components")
        logger.info("✅ PASS: Health status assessment\n")

    def test_trend_statistics(self):
        """Test trend statistics"""
        logger.info("TEST: Trend statistics")

        # Record multiple metrics
        for i in range(5):
            self.metrics.record_metrics(
                average_rating=0.70 + i * 0.05,
                error_rate=0.05 - i * 0.01,
                total_feedbacks=100 + i * 10,
                feedback_count_24h=30 + i * 5,
                avg_response_time_ms=150 - i * 10,
            )

        stats = self.metrics.calculate_trend_stats(hours=24)

        self.assertGreater(stats["data_points"], 0)
        self.assertGreater(stats["avg_rating"], 0)
        logger.info(f"  ✓ Data points: {stats['data_points']}")
        logger.info(f"  ✓ Avg rating: {stats['avg_rating']:.2f}")
        logger.info(f"  ✓ Volatility: {stats['rating_volatility']:.3f}")
        logger.info("✅ PASS: Trend statistics\n")


class TestDashboardUI(unittest.TestCase):
    """Test dashboard UI components"""

    def setUp(self):
        from src.self_improvement.dashboard_ui import DashboardUI, DashboardPageBuilder
        self.DashboardUI = DashboardUI
        self.DashboardPageBuilder = DashboardPageBuilder

    def test_dashboard_ui_init(self):
        """Test dashboard UI initialization"""
        logger.info("TEST: Dashboard UI initialization")

        ui = self.DashboardUI()
        self.assertIsNotNone(ui)
        logger.info("  ✓ Dashboard UI initialized")
        logger.info("✅ PASS: Dashboard UI initialization\n")

    def test_page_builder_init(self):
        """Test page builder initialization"""
        logger.info("TEST: Page builder initialization")

        builder = self.DashboardPageBuilder()
        self.assertIsNotNone(builder)
        self.assertIn("page_title", builder.page_config)
        logger.info(f"  ✓ Page config: {builder.page_config['page_title']}")
        logger.info("✅ PASS: Page builder initialization\n")


class Phase4IntegrationTest(unittest.TestCase):
    """Integration tests for Phase 4"""

    def test_audit_and_metrics_integration(self):
        """Test integration of audit logger and metrics"""
        logger.info("TEST: Audit and metrics integration")

        from src.self_improvement.audit_logger import AuditLogger, EventType, AlertSeverity
        from src.self_improvement.dashboard_metrics import DashboardMetrics

        temp_dir = tempfile.mkdtemp()

        try:
            audit = AuditLogger(log_dir=f"{temp_dir}/audit")
            metrics = DashboardMetrics(storage_dir=f"{temp_dir}/metrics")

            # Record metrics
            snapshot = metrics.record_metrics(0.80, 0.03, 120, 40, 130)

            # Log event with metrics
            audit.log_event(
                event_type=EventType.METRIC_VERIFIED,
                component="phase_1",
                message="Metrics verified",
                metrics_snapshot={
                    "average_rating": snapshot.average_rating,
                    "error_rate": snapshot.error_rate,
                },
            )

            # Verify integration
            events = audit.get_events(event_type=EventType.METRIC_VERIFIED)
            self.assertEqual(len(events), 1)
            self.assertIsNotNone(events[0].metrics_snapshot)
            logger.info("  ✓ Metrics captured in audit log")
            logger.info("✅ PASS: Integration working\n")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


def run_test_suite():
    """Run all Phase 4 tests"""
    logger.info("=" * 80)
    logger.info("PHASE 4: DASHBOARD & AUDIT - TEST SUITE")
    logger.info("=" * 80 + "\n")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test suites
    suite.addTests(loader.loadTestsFromTestCase(TestAuditLogger))
    suite.addTests(loader.loadTestsFromTestCase(TestDashboardMetrics))
    suite.addTests(loader.loadTestsFromTestCase(TestDashboardUI))
    suite.addTests(loader.loadTestsFromTestCase(Phase4IntegrationTest))

    # Run with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 4 TEST SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Tests run: {result.testsRun}")
    logger.info(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    logger.info(f"Failed: {len(result.failures)}")
    logger.info(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        logger.info("\n✅ ALL PHASE 4 TESTS PASSED!")
    else:
        logger.info("\n❌ SOME TESTS FAILED")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_test_suite()
    exit(0 if success else 1)
