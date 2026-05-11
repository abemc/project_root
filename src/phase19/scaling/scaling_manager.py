"""Scaling Manager - unified availability and scaling system."""

from typing import Dict, List, Optional, Any
from datetime import datetime

from .load_balancer import LoadBalancer, LoadBalancingStrategy, BackendStatus
from .auto_scaler import AutoScaler, ScalingPolicy, ScalingRule
from .cache_manager import CacheManager
from .fault_detector import FaultDetector, FaultType, FaultEvent


class ScalingManager:
    """Unified availability and scaling management system.
    
    Integrates:
    - Load balancing across backends
    - Auto-scaling based on metrics
    - Multi-level caching
    - Fault detection and recovery
    
    Provides a single interface for all availability operations.
    """

    def __init__(
        self,
        lb_strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
        min_instances: int = 1,
        max_instances: int = 10,
        cache_size: int = 1000,
        cache_ttl: Optional[float] = 300.0
    ):
        """Initialize Scaling Manager.
        
        Args:
            lb_strategy: Load balancing strategy
            min_instances: Min instances for auto-scaler
            max_instances: Max instances for auto-scaler
            cache_size: Max cache entries
            cache_ttl: Default cache TTL in seconds
        """
        self.load_balancer = LoadBalancer(lb_strategy)
        self.auto_scaler = AutoScaler(min_instances, max_instances)
        self.cache_manager = CacheManager(cache_size, cache_ttl)
        self.fault_detector = FaultDetector()
        self._initialized_at = datetime.utcnow().isoformat()

        # Wire up auto-scaler callbacks to load balancer
        self.auto_scaler.set_scale_out_callback(self._on_scale_out)
        self.auto_scaler.set_scale_in_callback(self._on_scale_in)

        # Track managed backends
        self._managed_backend_ids: List[str] = []
        self._backend_counter = 0

    def add_backend(
        self,
        host: str,
        port: int,
        weight: int = 1,
        backend_id: Optional[str] = None
    ) -> str:
        """Add a backend server.
        
        Args:
            host: Backend host
            port: Backend port
            weight: Load balancing weight
            backend_id: Optional custom ID
            
        Returns:
            Backend ID
        """
        if not backend_id:
            self._backend_counter += 1
            backend_id = f"backend_{self._backend_counter}"

        self.load_balancer.add_backend(backend_id, host, port, weight)
        self.fault_detector.register_service(backend_id)
        self._managed_backend_ids.append(backend_id)
        return backend_id

    def remove_backend(self, backend_id: str) -> bool:
        """Remove a backend server gracefully.
        
        Args:
            backend_id: Backend to remove
            
        Returns:
            True if removed
        """
        # Set to draining first
        self.load_balancer.set_backend_status(backend_id, BackendStatus.DRAINING)
        result = self.load_balancer.remove_backend(backend_id)
        if result and backend_id in self._managed_backend_ids:
            self._managed_backend_ids.remove(backend_id)
        return result

    def get_next_backend(self, client_ip: Optional[str] = None):
        """Get next backend for request routing.
        
        Args:
            client_ip: Client IP for sticky sessions
            
        Returns:
            Selected Backend or None
        """
        return self.load_balancer.get_next_backend(client_ip)

    def add_scaling_rule(
        self,
        rule_id: str,
        policy: ScalingPolicy,
        scale_out_threshold: float,
        scale_in_threshold: float,
        min_instances: int = 1,
        max_instances: int = 10,
        cooldown_seconds: int = 60
    ) -> ScalingRule:
        """Add an auto-scaling rule.
        
        Args:
            rule_id: Rule identifier
            policy: Scaling policy
            scale_out_threshold: Metric value to trigger scale out
            scale_in_threshold: Metric value to trigger scale in
            min_instances: Minimum instances
            max_instances: Maximum instances
            cooldown_seconds: Cooldown between scaling actions
            
        Returns:
            Created ScalingRule
        """
        rule = ScalingRule(
            rule_id=rule_id,
            policy=policy,
            scale_out_threshold=scale_out_threshold,
            scale_in_threshold=scale_in_threshold,
            min_instances=min_instances,
            max_instances=max_instances,
            cooldown_seconds=cooldown_seconds
        )
        self.auto_scaler.add_rule(rule)
        return rule

    def update_metrics(
        self,
        service_id: str,
        metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """Update metrics for auto-scaling and fault detection.
        
        Args:
            service_id: Service identifier
            metrics: Current metrics dict
            
        Returns:
            Dict with scaling events and faults
        """
        # Update auto-scaler
        scaling_events = self.auto_scaler.evaluate_metrics(metrics)

        # Update fault detector
        faults = self.fault_detector.update_metrics(service_id, metrics)

        # Sync backend health based on faults
        if faults:
            critical_faults = [f for f in faults if f.fault_type == FaultType.SERVICE_UNAVAILABLE]
            if critical_faults and service_id in self._managed_backend_ids:
                self.load_balancer.update_health(service_id, False)

        return {
            "scaling_events": [e.to_dict() for e in scaling_events],
            "faults_detected": [f.to_dict() for f in faults],
            "current_instances": self.auto_scaler.current_instances
        }

    def cache_get(self, key: str) -> Optional[Any]:
        """Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        return self.cache_manager.get(key)

    def cache_set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds
        """
        self.cache_manager.set(key, value, ttl)

    def cache_invalidate(self, pattern: str) -> int:
        """Invalidate cache entries by pattern.
        
        Args:
            pattern: Key prefix pattern
            
        Returns:
            Number of entries invalidated
        """
        return self.cache_manager.invalidate_pattern(pattern)

    def get_active_faults(self, service_id: Optional[str] = None) -> List[FaultEvent]:
        """Get active faults.
        
        Args:
            service_id: Filter by service
            
        Returns:
            List of active faults
        """
        return self.fault_detector.get_active_faults(service_id)

    def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status.
        
        Returns:
            Health status dictionary
        """
        lb_stats = self.load_balancer.get_stats()
        as_stats = self.auto_scaler.get_stats()
        cache_stats = self.cache_manager.get_stats()
        fault_stats = self.fault_detector.get_stats()

        active_faults = fault_stats["active_faults"]
        critical_faults = fault_stats["critical_faults"]

        if critical_faults > 0:
            overall_status = "critical"
        elif active_faults > 0:
            overall_status = "degraded"
        elif lb_stats["healthy_backends"] == 0:
            overall_status = "unavailable"
        else:
            overall_status = "healthy"

        return {
            "status": overall_status,
            "initialized_at": self._initialized_at,
            "timestamp": datetime.utcnow().isoformat(),
            "load_balancer": lb_stats,
            "auto_scaler": as_stats,
            "cache": cache_stats,
            "fault_detection": fault_stats
        }

    def get_compliance_report(self) -> Dict[str, Any]:
        """Get availability and scaling report.
        
        Returns:
            Report dictionary
        """
        health = self.get_system_health()
        scaling_history = self.auto_scaler.get_scaling_history()

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "system_health": health,
            "scaling_events_count": len(scaling_history),
            "fault_history_count": len(self.fault_detector.fault_history),
            "cache_hit_rate": self.cache_manager.get_stats()["hit_rate"]
        }

    def _on_scale_out(self, new_count: int) -> None:
        """Callback when scale out occurs."""
        pass  # Hook for future: provision new backend instances

    def _on_scale_in(self, new_count: int) -> None:
        """Callback when scale in occurs."""
        pass  # Hook for future: gracefully terminate instances
