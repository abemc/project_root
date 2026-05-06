import time
import logging
from enum import Enum
from functools import wraps

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    """
    Phase 19 Task 1: SLA & 信頼性確保
    外部サービスの障害を検知し、連鎖的な障害を防ぐサーキットブレーカー。
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0

    def call(self, func, *args, **kwargs):
        """関数を実行し、サーキットブレーカーの状態を更新する。"""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                logger.info("CircuitBreaker: Recovery timeout reached. Transitioning to HALF_OPEN.")
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception("CircuitBreaker is OPEN. Call denied.")

        try:
            result = func(*args, **kwargs)
            
            # 成功時のリセット
            if self.state == CircuitState.HALF_OPEN:
                logger.info("CircuitBreaker: Success in HALF_OPEN. Transitioning to CLOSED.")
                self.reset()
            
            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            logger.warning(f"CircuitBreaker: Call failed ({self.failure_count}/{self.failure_threshold}): {e}")
            
            if self.failure_count >= self.failure_threshold:
                logger.error("CircuitBreaker: Failure threshold reached. Transitioning to OPEN.")
                self.state = CircuitState.OPEN
            
            raise e

    def reset(self):
        self.state = CircuitState.CLOSED
        self.failure_count = 0

def circuit_breaker(failure_threshold=5, recovery_timeout=60.0):
    """サーキットブレーカーのデコレータ。"""
    cb = CircuitBreaker(failure_threshold, recovery_timeout)
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return cb.call(func, *args, **kwargs)
        return wrapper
    return decorator
