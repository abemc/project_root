"""Load Balancer - distributes requests across multiple backends."""

import random
import time
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class LoadBalancingStrategy(Enum):
    """Load balancing algorithms."""
    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"
    IP_HASH = "ip_hash"


class BackendStatus(Enum):
    """Backend server status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DRAINING = "draining"  # Graceful removal


@dataclass
class Backend:
    """Represents a backend server."""
    id: str
    host: str
    port: int
    weight: int = 1
    status: BackendStatus = BackendStatus.HEALTHY
    active_connections: int = 0
    total_requests: int = 0
    total_errors: int = 0
    last_health_check: Optional[str] = None
    response_times: List[float] = field(default_factory=list)

    @property
    def avg_response_time(self) -> float:
        """Average response time in ms."""
        if not self.response_times:
            return 0.0
        return sum(self.response_times[-100:]) / min(len(self.response_times), 100)

    @property
    def error_rate(self) -> float:
        """Error rate as a fraction."""
        if self.total_requests == 0:
            return 0.0
        return self.total_errors / self.total_requests

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "host": self.host,
            "port": self.port,
            "weight": self.weight,
            "status": self.status.value,
            "active_connections": self.active_connections,
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "avg_response_time_ms": round(self.avg_response_time, 2),
            "error_rate": round(self.error_rate, 4),
            "last_health_check": self.last_health_check
        }


class LoadBalancer:
    """Distributes requests across multiple backend servers.
    
    Supports:
    - Round Robin
    - Weighted Round Robin
    - Least Connections
    - Random
    - IP Hash (sticky sessions)
    
    Features:
    - Health checking
    - Automatic failover
    - Connection tracking
    - Performance metrics
    """

    def __init__(self, strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN):
        """Initialize load balancer.
        
        Args:
            strategy: Load balancing algorithm
        """
        self.strategy = strategy
        self.backends: Dict[str, Backend] = {}
        self._rr_index: int = 0
        self._lock = threading.RLock()

    def add_backend(
        self,
        backend_id: str,
        host: str,
        port: int,
        weight: int = 1
    ) -> Backend:
        """Add a backend server.
        
        Args:
            backend_id: Unique backend identifier
            host: Backend host
            port: Backend port
            weight: Weight for weighted round robin
            
        Returns:
            Added Backend
        """
        with self._lock:
            backend = Backend(id=backend_id, host=host, port=port, weight=weight)
            self.backends[backend_id] = backend
            return backend

    def remove_backend(self, backend_id: str) -> bool:
        """Remove a backend server.
        
        Args:
            backend_id: Backend to remove
            
        Returns:
            True if removed
        """
        with self._lock:
            if backend_id in self.backends:
                del self.backends[backend_id]
                return True
            return False

    def set_backend_status(self, backend_id: str, status: BackendStatus) -> bool:
        """Set backend status.
        
        Args:
            backend_id: Backend identifier
            status: New status
            
        Returns:
            True if status was set
        """
        with self._lock:
            if backend_id not in self.backends:
                return False
            self.backends[backend_id].status = status
            return True

    def get_next_backend(self, client_ip: Optional[str] = None) -> Optional[Backend]:
        """Get next backend based on load balancing strategy.
        
        Args:
            client_ip: Client IP for IP hash strategy
            
        Returns:
            Selected Backend or None if no healthy backends
        """
        with self._lock:
            healthy = self._get_healthy_backends()
            if not healthy:
                return None

            if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
                return self._round_robin(healthy)
            elif self.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
                return self._weighted_round_robin(healthy)
            elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
                return self._least_connections(healthy)
            elif self.strategy == LoadBalancingStrategy.RANDOM:
                return random.choice(healthy)
            elif self.strategy == LoadBalancingStrategy.IP_HASH:
                return self._ip_hash(healthy, client_ip)
            else:
                return self._round_robin(healthy)

    def record_request_start(self, backend_id: str) -> None:
        """Record start of request to backend.
        
        Args:
            backend_id: Backend identifier
        """
        with self._lock:
            if backend_id in self.backends:
                self.backends[backend_id].active_connections += 1
                self.backends[backend_id].total_requests += 1

    def record_request_end(
        self,
        backend_id: str,
        response_time_ms: float,
        success: bool = True
    ) -> None:
        """Record end of request to backend.
        
        Args:
            backend_id: Backend identifier
            response_time_ms: Response time in milliseconds
            success: Whether request succeeded
        """
        with self._lock:
            if backend_id not in self.backends:
                return
            backend = self.backends[backend_id]
            backend.active_connections = max(0, backend.active_connections - 1)
            backend.response_times.append(response_time_ms)
            if not success:
                backend.total_errors += 1

            # Limit response time history
            if len(backend.response_times) > 1000:
                backend.response_times = backend.response_times[-500:]

    def update_health(self, backend_id: str, is_healthy: bool) -> None:
        """Update backend health status.
        
        Args:
            backend_id: Backend identifier
            is_healthy: Whether backend is healthy
        """
        with self._lock:
            if backend_id not in self.backends:
                return
            backend = self.backends[backend_id]
            backend.status = BackendStatus.HEALTHY if is_healthy else BackendStatus.UNHEALTHY
            backend.last_health_check = datetime.utcnow().isoformat()

    def get_stats(self) -> Dict[str, Any]:
        """Get load balancer statistics.
        
        Returns:
            Statistics dictionary
        """
        with self._lock:
            healthy = len(self._get_healthy_backends())
            return {
                "strategy": self.strategy.value,
                "total_backends": len(self.backends),
                "healthy_backends": healthy,
                "unhealthy_backends": len(self.backends) - healthy,
                "backends": {bid: b.to_dict() for bid, b in self.backends.items()}
            }

    def _get_healthy_backends(self) -> List[Backend]:
        """Get list of healthy backends."""
        return [b for b in self.backends.values() if b.status == BackendStatus.HEALTHY]

    def _round_robin(self, backends: List[Backend]) -> Backend:
        """Round robin selection."""
        if not backends:
            return None
        backend = backends[self._rr_index % len(backends)]
        self._rr_index = (self._rr_index + 1) % len(backends)
        return backend

    def _weighted_round_robin(self, backends: List[Backend]) -> Backend:
        """Weighted round robin selection."""
        weighted = []
        for b in backends:
            weighted.extend([b] * b.weight)
        return random.choice(weighted) if weighted else None

    def _least_connections(self, backends: List[Backend]) -> Backend:
        """Least connections selection."""
        return min(backends, key=lambda b: b.active_connections)

    def _ip_hash(self, backends: List[Backend], client_ip: Optional[str]) -> Backend:
        """IP hash selection for sticky sessions."""
        if not client_ip:
            return random.choice(backends)
        index = hash(client_ip) % len(backends)
        return backends[index]
