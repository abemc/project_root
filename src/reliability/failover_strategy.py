import logging
from typing import Any, List, Callable

logger = logging.getLogger(__name__)

class FailoverStrategy:
    """
    Phase 19 Task 1: SLA & 信頼性確保
    プライマリサービスが失敗した場合にバックアップサービスに切り替える戦略。
    """

    def __init__(self, services: List[Callable]):
        """
        services: 実行可能な関数のリスト。インデックス0がプライマリ。
        """
        self.services = services

    def execute(self, *args, **kwargs) -> Any:
        """順番にサービスを試行し、最初に成功した結果を返す。"""
        errors = []
        for i, service in enumerate(self.services):
            try:
                name = getattr(service, '__name__', f"service_{i}")
                logger.info(f"Attempting failover service {i}: {name}")
                return service(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Service {i} failed: {e}")
                errors.append(str(e))
        
        raise Exception(f"All failover services failed: {', '.join(errors)}")
