"""
Execution module: 実行環境管理

ツール実行、非同期イベントループ、エラー復帰を統合した実行フレームワーク。
"""

from .tool_executor import (
    ToolExecutor,
    ToolDefinition,
    ToolRegistry,
    ExecutionResult,
    ToolType,
    ExecutionPhase,
)
from .event_loop import (
    EventLoop,
    Task,
    TaskPriority,
    TaskStatus,
    EventBus,
    EventType,
    Event,
    TaskGraph,
)
from .fallback_chain import (
    FallbackChain,
    FallbackOption,
    FallbackAttempt,
    FallbackStrategy,
)

__all__ = [
    'ToolExecutor',
    'ToolDefinition',
    'ToolRegistry',
    'ExecutionResult',
    'ToolType',
    'ExecutionPhase',
    'EventLoop',
    'Task',
    'TaskPriority',
    'TaskStatus',
    'EventBus',
    'EventType',
    'Event',
    'TaskGraph',
    'FallbackChain',
    'FallbackOption',
    'FallbackAttempt',
    'FallbackStrategy',
]
