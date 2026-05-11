"""Tests for Scaling and Availability Module - Phase 19 Task 3."""

import pytest
import time

from src.phase19.scaling.load_balancer import LoadBalancer, LoadBalancingStrategy, BackendStatus
from src.phase19.scaling.auto_scaler import AutoScaler, ScalingPolicy, ScalingRule, ScalingDirection
from src.phase19.scaling.cache_manager import CacheManager, CacheStrategy
from src.phase19.scaling.fault_detector import FaultDetector, FaultType
from src.phase19.scaling.scaling_manager import ScalingManager


# ==================== Load Balancer Tests ====================

class TestLoadBalancer:
    """Test load balancer functionality."""

    def test_initialization(self):
        """Test LoadBalancer initialization."""
        lb = LoadBalancer()
        assert lb.strategy == LoadBalancingStrategy.ROUND_ROBIN
        assert len(lb.backends) == 0

    def test_add_backend(self):
        """Test adding backend servers."""
        lb = LoadBalancer()
        backend = lb.add_backend("b1", "host1", 8080, weight=2)
        assert backend.id == "b1"
        assert backend.weight == 2
        assert len(lb.backends) == 1

    def test_remove_backend(self):
        """Test removing backend servers."""
        lb = LoadBalancer()
        lb.add_backend("b1", "host1", 8080)
        assert lb.remove_backend("b1") is True
        assert len(lb.backends) == 0
        assert lb.remove_backend("nonexistent") is False

    def test_round_robin_selection(self):
        """Test round robin backend selection."""
        lb = LoadBalancer(LoadBalancingStrategy.ROUND_ROBIN)
        lb.add_backend("b1", "host1", 8080)
        lb.add_backend("b2", "host2", 8081)

        selections = [lb.get_next_backend().id for _ in range(4)]
        # Should alternate
        assert "b1" in selections
        assert "b2" in selections

    def test_least_connections_selection(self):
        """Test least connections selection."""
        lb = LoadBalancer(LoadBalancingStrategy.LEAST_CONNECTIONS)
        lb.add_backend("b1", "host1", 8080)
        lb.add_backend("b2", "host2", 8081)

        lb.record_request_start("b1")
        lb.record_request_start("b1")
        # b2 should be selected (fewer connections)
        selected = lb.get_next_backend()
        assert selected.id == "b2"

    def test_health_update(self):
        """Test backend health update."""
        lb = LoadBalancer()
        lb.add_backend("b1", "host1", 8080)
        lb.update_health("b1", False)
        assert lb.backends["b1"].status == BackendStatus.UNHEALTHY

        # No healthy backends - returns None
        assert lb.get_next_backend() is None

    def test_request_tracking(self):
        """Test request start/end tracking."""
        lb = LoadBalancer()
        lb.add_backend("b1", "host1", 8080)

        lb.record_request_start("b1")
        assert lb.backends["b1"].active_connections == 1
        assert lb.backends["b1"].total_requests == 1

        lb.record_request_end("b1", response_time_ms=100.0)
        assert lb.backends["b1"].active_connections == 0

    def test_get_stats(self):
        """Test getting load balancer statistics."""
        lb = LoadBalancer()
        lb.add_backend("b1", "host1", 8080)
        lb.add_backend("b2", "host2", 8081)

        stats = lb.get_stats()
        assert stats["total_backends"] == 2
        assert stats["healthy_backends"] == 2
        assert stats["strategy"] == "round_robin"


# ==================== Auto Scaler Tests ====================

class TestAutoScaler:
    """Test auto scaler functionality."""

    def test_initialization(self):
        """Test AutoScaler initialization."""
        scaler = AutoScaler(min_instances=1, max_instances=10)
        assert scaler.current_instances == 1
        assert scaler.min_instances == 1
        assert scaler.max_instances == 10

    def test_manual_scale_out(self):
        """Test manual scale out."""
        scaler = AutoScaler(min_instances=1, max_instances=10)
        event = scaler.scale_out(count=2)
        assert scaler.current_instances == 3
        assert event.direction == ScalingDirection.SCALE_OUT
        assert event.instances_after == 3

    def test_manual_scale_in(self):
        """Test manual scale in."""
        scaler = AutoScaler(min_instances=1, max_instances=10, initial_instances=5)
        event = scaler.scale_in(count=2)
        assert scaler.current_instances == 3
        assert event.direction == ScalingDirection.SCALE_IN

    def test_max_instances_cap(self):
        """Test that scale out respects max_instances."""
        scaler = AutoScaler(min_instances=1, max_instances=3, initial_instances=3)
        scaler.scale_out(count=5)
        assert scaler.current_instances == 3  # Capped at max

    def test_min_instances_floor(self):
        """Test that scale in respects min_instances."""
        scaler = AutoScaler(min_instances=2, max_instances=10, initial_instances=2)
        scaler.scale_in(count=5)
        assert scaler.current_instances == 2  # Floored at min

    def test_auto_scale_rule(self):
        """Test automatic scaling with rule evaluation."""
        scaler = AutoScaler(min_instances=1, max_instances=10, initial_instances=2)
        rule = ScalingRule(
            rule_id="cpu_rule",
            policy=ScalingPolicy.CPU_BASED,
            scale_out_threshold=80.0,
            scale_in_threshold=30.0,
            cooldown_seconds=0  # No cooldown for testing
        )
        scaler.add_rule(rule)

        events = scaler.evaluate_metrics({"cpu_percent": 85.0})
        assert len(events) == 1
        assert events[0].direction == ScalingDirection.SCALE_OUT

    def test_scaling_history(self):
        """Test scaling event history tracking."""
        scaler = AutoScaler()
        scaler.scale_out(count=1)
        scaler.scale_in(count=1)

        history = scaler.get_scaling_history()
        assert len(history) == 2

    def test_scaling_callback(self):
        """Test scale out/in callbacks."""
        scaler = AutoScaler()
        callback_calls = []

        scaler.set_scale_out_callback(lambda n: callback_calls.append(("out", n)))
        scaler.set_scale_in_callback(lambda n: callback_calls.append(("in", n)))

        scaler.scale_out()
        scaler.scale_in()

        assert ("out", 2) in callback_calls
        assert ("in", 1) in callback_calls


# ==================== Cache Manager Tests ====================

class TestCacheManager:
    """Test cache manager functionality."""

    def test_initialization(self):
        """Test CacheManager initialization."""
        cache = CacheManager(max_size=100)
        assert cache.max_size == 100
        assert cache.strategy == CacheStrategy.LRU

    def test_set_and_get(self):
        """Test basic set and get operations."""
        cache = CacheManager()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_miss(self):
        """Test cache miss returns None."""
        cache = CacheManager()
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self):
        """Test TTL expiry."""
        cache = CacheManager(default_ttl=0.01)  # 10ms TTL
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        time.sleep(0.02)
        assert cache.get("key1") is None

    def test_delete(self):
        """Test deleting cache entries."""
        cache = CacheManager()
        cache.set("key1", "value1")
        assert cache.delete("key1") is True
        assert cache.get("key1") is None

    def test_get_or_set(self):
        """Test get-or-set pattern."""
        cache = CacheManager()
        factory_calls = []

        def factory():
            factory_calls.append(1)
            return "computed_value"

        result1 = cache.get_or_set("key1", factory)
        result2 = cache.get_or_set("key1", factory)

        assert result1 == "computed_value"
        assert result2 == "computed_value"
        assert len(factory_calls) == 1  # Factory called only once

    def test_invalidate_pattern(self):
        """Test pattern-based cache invalidation."""
        cache = CacheManager()
        cache.set("user:1:name", "Alice")
        cache.set("user:1:email", "alice@example.com")
        cache.set("product:1:name", "Widget")

        removed = cache.invalidate_pattern("user:")
        assert removed == 2
        assert cache.get("product:1:name") == "Widget"

    def test_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = CacheManager(max_size=2, strategy=CacheStrategy.LRU)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get("a")  # Access 'a' to make 'b' the LRU
        cache.set("c", 3)  # Should evict 'b'
        assert cache.get("a") == 1
        assert cache.get("c") == 3

    def test_stats(self):
        """Test cache statistics."""
        cache = CacheManager()
        cache.set("k1", "v1")
        cache.get("k1")   # hit
        cache.get("miss") # miss

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_warm_up(self):
        """Test cache warming."""
        cache = CacheManager()
        added = cache.warm_up({"k1": "v1", "k2": "v2", "k3": "v3"})
        assert added == 3
        assert cache.get("k1") == "v1"


# ==================== Fault Detector Tests ====================

class TestFaultDetector:
    """Test fault detector functionality."""

    def test_initialization(self):
        """Test FaultDetector initialization."""
        fd = FaultDetector()
        assert len(fd.service_thresholds) == 0
        assert len(fd.active_faults) == 0

    def test_register_service(self):
        """Test service registration."""
        fd = FaultDetector()
        fd.register_service("svc1", thresholds={"error_rate": 0.1})
        assert "svc1" in fd.service_thresholds
        assert fd.service_thresholds["svc1"]["error_rate"] == 0.1

    def test_detect_high_error_rate(self):
        """Test detecting high error rate."""
        fd = FaultDetector()
        fd.register_service("svc1")

        faults = fd.update_metrics("svc1", {"error_rate": 0.5})
        assert len(faults) == 1
        assert faults[0].fault_type == FaultType.HIGH_ERROR_RATE

    def test_detect_high_latency(self):
        """Test detecting high latency."""
        fd = FaultDetector()
        fd.register_service("svc1")

        faults = fd.update_metrics("svc1", {"latency_ms": 5000.0})
        assert len(faults) == 1
        assert faults[0].fault_type == FaultType.HIGH_LATENCY

    def test_no_fault_below_threshold(self):
        """Test that no fault is detected below threshold."""
        fd = FaultDetector()
        fd.register_service("svc1")

        faults = fd.update_metrics("svc1", {"error_rate": 0.01, "latency_ms": 100.0})
        assert len(faults) == 0

    def test_fault_resolution(self):
        """Test resolving a fault."""
        fd = FaultDetector()
        fd.register_service("svc1")

        faults = fd.update_metrics("svc1", {"error_rate": 0.5})
        assert len(faults) == 1
        fault_id = faults[0].fault_id

        result = fd.resolve_fault(fault_id)
        assert result is True
        assert len(fd.get_active_faults("svc1")) == 0

    def test_alert_callback(self):
        """Test fault alert callback."""
        fd = FaultDetector()
        alerts = []
        fd.set_alert_callback(lambda f: alerts.append(f))

        fd.register_service("svc1")
        fd.update_metrics("svc1", {"error_rate": 0.9})

        assert len(alerts) == 1
        assert alerts[0].fault_type == FaultType.HIGH_ERROR_RATE

    def test_service_health(self):
        """Test getting service health status."""
        fd = FaultDetector()
        fd.register_service("svc1")

        health = fd.get_service_health("svc1")
        assert health["status"] == "healthy"

        fd.update_metrics("svc1", {"error_rate": 0.9})
        health = fd.get_service_health("svc1")
        assert health["status"] in ("degraded", "critical")


# ==================== Scaling Manager Integration Tests ====================

class TestScalingManager:
    """Test unified scaling manager."""

    def test_initialization(self):
        """Test ScalingManager initialization."""
        sm = ScalingManager()
        assert sm.load_balancer is not None
        assert sm.auto_scaler is not None
        assert sm.cache_manager is not None
        assert sm.fault_detector is not None

    def test_add_and_remove_backend(self):
        """Test adding and removing backends."""
        sm = ScalingManager()
        bid = sm.add_backend("host1", 8080)
        assert bid is not None
        assert len(sm.load_balancer.backends) == 1

        result = sm.remove_backend(bid)
        assert result is True
        assert len(sm.load_balancer.backends) == 0

    def test_get_next_backend(self):
        """Test backend selection."""
        sm = ScalingManager()
        sm.add_backend("host1", 8080)
        sm.add_backend("host2", 8081)

        backend = sm.get_next_backend()
        assert backend is not None

    def test_cache_operations(self):
        """Test cache get/set/invalidate."""
        sm = ScalingManager()
        sm.cache_set("key1", "value1")
        assert sm.cache_get("key1") == "value1"

        sm.cache_invalidate("key")
        assert sm.cache_get("key1") is None

    def test_update_metrics_with_scaling(self):
        """Test metrics update triggers scaling."""
        sm = ScalingManager()
        sm.add_scaling_rule(
            rule_id="cpu_rule",
            policy=ScalingPolicy.CPU_BASED,
            scale_out_threshold=80.0,
            scale_in_threshold=20.0,
            cooldown_seconds=0
        )

        result = sm.update_metrics("service1", {"cpu_percent": 90.0})
        assert "scaling_events" in result
        assert "faults_detected" in result

    def test_get_system_health(self):
        """Test system health report."""
        sm = ScalingManager()
        sm.add_backend("host1", 8080)

        health = sm.get_system_health()
        assert "status" in health
        assert "load_balancer" in health
        assert "auto_scaler" in health
        assert "cache" in health
        assert "fault_detection" in health

    def test_get_compliance_report(self):
        """Test compliance report."""
        sm = ScalingManager()
        report = sm.get_compliance_report()
        assert "generated_at" in report
        assert "system_health" in report
        assert "cache_hit_rate" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
