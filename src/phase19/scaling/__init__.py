"""Scaling and Availability Module for Phase 19 Task 3."""

from .load_balancer import LoadBalancer, LoadBalancingStrategy
from .auto_scaler import AutoScaler, ScalingPolicy
from .cache_manager import CacheManager, CacheStrategy
from .fault_detector import FaultDetector, FaultType
from .scaling_manager import ScalingManager

__all__ = [
    'LoadBalancer',
    'LoadBalancingStrategy',
    'AutoScaler',
    'ScalingPolicy',
    'CacheManager',
    'CacheStrategy',
    'FaultDetector',
    'FaultType',
    'ScalingManager',
]
