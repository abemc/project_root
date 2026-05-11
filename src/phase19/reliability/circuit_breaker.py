"""
Circuit Breaker Pattern Implementation

99.99% SLA達成のための信頼性メカニズム
"""

from enum import Enum
from dataclasses import dataclass
from typing import Callable, Any, Optional, Dict
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit Breaker状態"""
    CLOSED = "closed"          # 正常状態
    OPEN = "open"              # 障害状態
    HALF_OPEN = "half_open"    # 回復テスト中


@dataclass
class CircuitBreakerConfig:
    """Circuit Breaker設定"""
    failure_threshold: int = 5          # 失敗カウント閾値
    success_threshold: int = 2          # 成功カウント閾値（HALF_OPEN時）
    timeout: int = 60                   # OPEN状態の継続時間（秒）
    name: str = "default"               # Circuit名


@dataclass
class CircuitBreakerMetrics:
    """Circuit Breakerメトリクス"""
    total_calls: int = 0                # 総呼び出し数
    successful_calls: int = 0           # 成功数
    failed_calls: int = 0               # 失敗数
    rejected_calls: int = 0             # 拒否数
    state_changes: int = 0              # 状態遷移回数
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    
    def get_success_rate(self) -> float:
        """成功率を取得"""
        if self.total_calls == 0:
            return 100.0
        return (self.successful_calls / self.total_calls) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "state_changes": self.state_changes,
            "success_rate": self.get_success_rate(),
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success_time": self.last_success_time.isoformat() if self.last_success_time else None,
        }


class CircuitBreaker:
    """
    Circuit Breaker パターンの実装
    
    外部呼び出しの信頼性を向上させるデザインパターン。
    - CLOSED: 正常に動作
    - OPEN: 障害を検出、呼び出しを拒否
    - HALF_OPEN: 回復テスト中
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        """初期化"""
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.metrics = CircuitBreakerMetrics()
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Circuit Breaker経由で関数を呼び出し
        
        Args:
            func: 実行する関数
            *args: 位置引数
            **kwargs: キーワード引数
            
        Returns:
            関数の実行結果
            
        Raises:
            CircuitBreakerOpen: Circuit Breakerが開いている場合
        """
        async with self._lock:
            if self.state == CircuitState.OPEN:
                # タイムアウト確認
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    logger.info(f"[{self.config.name}] State: OPEN → HALF_OPEN")
                else:
                    self.metrics.rejected_calls += 1
                    raise CircuitBreakerOpen(
                        f"Circuit breaker '{self.config.name}' is OPEN"
                    )
        
        try:
            # 関数を実行
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # 成功時の処理
            await self._on_success()
            return result
            
        except Exception:
            # 失敗時の処理
            await self._on_failure()
            raise
    
    async def _on_success(self) -> None:
        """成功時の処理"""
        async with self._lock:
            self.failure_count = 0
            self.metrics.successful_calls += 1
            self.metrics.total_calls += 1
            self.metrics.last_success_time = datetime.now()
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.success_count = 0
                    self.metrics.state_changes += 1
                    logger.info(
                        f"[{self.config.name}] State: HALF_OPEN → CLOSED "
                        f"(success_rate: {self.metrics.get_success_rate():.1f}%)"
                    )
    
    async def _on_failure(self) -> None:
        """失敗時の処理"""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            self.metrics.failed_calls += 1
            self.metrics.total_calls += 1
            self.metrics.last_failure_time = datetime.now()
            
            if self.state == CircuitState.HALF_OPEN:
                # HALF_OPEN中の失敗でOPENに戻す
                self.state = CircuitState.OPEN
                self.success_count = 0
                self.metrics.state_changes += 1
                logger.warning(
                    f"[{self.config.name}] State: HALF_OPEN → OPEN "
                    f"(failed during recovery test)"
                )
            
            elif self.state == CircuitState.CLOSED:
                # 失敗カウントが閾値を超えたらOPENに
                if self.failure_count >= self.config.failure_threshold:
                    self.state = CircuitState.OPEN
                    self.metrics.state_changes += 1
                    logger.error(
                        f"[{self.config.name}] State: CLOSED → OPEN "
                        f"(failure_count: {self.failure_count}/{self.config.failure_threshold})"
                    )
    
    def _should_attempt_reset(self) -> bool:
        """リセットを試みるべきかを判定"""
        if self.last_failure_time is None:
            return True
        
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.config.timeout
    
    def get_state(self) -> CircuitState:
        """現在の状態を取得"""
        return self.state
    
    def get_metrics(self) -> CircuitBreakerMetrics:
        """メトリクスを取得"""
        return self.metrics
    
    async def reset(self) -> None:
        """手動でリセット"""
        async with self._lock:
            old_state = self.state
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self.metrics.state_changes += 1
            logger.info(
                f"[{self.config.name}] Manual reset: {old_state.value} → CLOSED"
            )
    
    def __repr__(self) -> str:
        """文字列表現"""
        return (
            f"CircuitBreaker("
            f"name='{self.config.name}', "
            f"state={self.state.value}, "
            f"success_rate={self.metrics.get_success_rate():.1f}%)"
        )


class CircuitBreakerRegistry:
    """複数のCircuit Breakerを管理"""
    
    def __init__(self):
        """初期化"""
        self.breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    async def register(
        self, 
        name: str, 
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Circuit Breakerを登録"""
        async with self._lock:
            if name in self.breakers:
                return self.breakers[name]
            
            cfg = config or CircuitBreakerConfig(name=name)
            breaker = CircuitBreaker(cfg)
            self.breakers[name] = breaker
            logger.info(f"Registered Circuit Breaker: {name}")
            return breaker
    
    async def get(self, name: str) -> Optional[CircuitBreaker]:
        """Circuit Breakerを取得"""
        return self.breakers.get(name)
    
    async def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """全Circuit Breakerのメトリクスを取得"""
        metrics = {}
        for name, breaker in self.breakers.items():
            metrics[name] = {
                "state": breaker.get_state().value,
                **breaker.get_metrics().to_dict()
            }
        return metrics
    
    async def reset_all(self) -> None:
        """全Circuit Breakerをリセット"""
        for breaker in self.breakers.values():
            await breaker.reset()


class CircuitBreakerOpen(Exception):
    """Circuit Breakerがopen状態の例外"""
    pass


# グローバルレジストリ
_global_registry = CircuitBreakerRegistry()


def get_circuit_breaker(name: str) -> Optional["CircuitBreaker"]:
    """グローバルレジストリからCircuit Breakerを取得"""
    return _global_registry.breakers.get(name)


def register_circuit_breaker(
    name: str,
    breaker_or_config: "CircuitBreaker | CircuitBreakerConfig | None" = None
) -> "CircuitBreaker":
    """グローバルレジストリにCircuit Breakerを登録"""
    if isinstance(breaker_or_config, CircuitBreaker):
        _global_registry.breakers[name] = breaker_or_config
        return breaker_or_config
    cfg = breaker_or_config if isinstance(breaker_or_config, CircuitBreakerConfig) else CircuitBreakerConfig(name=name)
    new_breaker = CircuitBreaker(cfg)
    _global_registry.breakers[name] = new_breaker
    return new_breaker


async def get_all_circuit_breakers() -> Dict[str, Dict[str, Any]]:
    """全Circuit Breakerのメトリクスを取得"""
    return await _global_registry.get_all_metrics()
