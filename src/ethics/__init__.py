"""
Ethics module: 倫理的な価値の管理

複数の価値が衝突する場合の解決メカニズムを提供。
"""

from .value_conflict_resolver import (
    ValueConflictResolver,
    Value,
    ValuePriority,
    ConflictScenario,
)

__all__ = [
    'ValueConflictResolver',
    'Value',
    'ValuePriority',
    'ConflictScenario',
]
