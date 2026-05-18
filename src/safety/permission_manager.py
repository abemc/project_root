"""
Permission Manager: ツール実行の厳密なアクセス制御

読み取り専用 vs 書き込み許可の境界を明確化し、
自律レベル × ツール種別 のマトリックスで実行可否を判定。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Set, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ToolAccessLevel(Enum):
    """ツールのアクセスレベル"""
    READ_ONLY = "read_only"  # 読み取り専用（情報取得）
    WRITE_LIMITED = "write_limited"  # 書き込み制限（ファイル修正、パラメータ変更）
    WRITE_FULL = "write_full"  # 完全書き込み（ファイル作成・削除、重要操作）
    CRITICAL = "critical"  # 重大操作（システム設定、認証、セキュリティ）


class AutonomyLevel(Enum):
    """エージェント自律レベル"""
    SUPERVISED = "supervised"  # ユーザー監督下：すべての操作にユーザー承認要
    SEMI_AUTONOMOUS = "semi_autonomous"  # 半自律：重要操作のみ承認要
    AUTONOMOUS = "autonomous"  # 完全自律：読み取り/軽い書き込みは自由
    RESTRICTED = "restricted"  # 制限自律：特定操作のみ許可


@dataclass
class PermissionPolicy:
    """権限ポリシー"""
    tool_name: str
    access_level: ToolAccessLevel
    requires_approval: Dict[AutonomyLevel, bool]  # autonomy_level -> 承認必須か
    max_execution_per_hour: Optional[int] = None  # 時間当たり最大実行回数
    allowed_parameters: Optional[List[str]] = None  # 許可するパラメータ白リスト
    blocked_parameter_values: Optional[Dict[str, List[str]]] = None  # ブロック値


class PermissionManager:
    """ツール実行権限管理"""
    
    # デフォルト権限マトリックス: (tool_access_level, autonomy_level) -> 実行許可
    DEFAULT_PERMISSION_MATRIX = {
        (ToolAccessLevel.READ_ONLY, AutonomyLevel.SUPERVISED): True,
        (ToolAccessLevel.READ_ONLY, AutonomyLevel.SEMI_AUTONOMOUS): True,
        (ToolAccessLevel.READ_ONLY, AutonomyLevel.AUTONOMOUS): True,
        (ToolAccessLevel.READ_ONLY, AutonomyLevel.RESTRICTED): True,
        
        (ToolAccessLevel.WRITE_LIMITED, AutonomyLevel.SUPERVISED): False,  # 承認必須
        (ToolAccessLevel.WRITE_LIMITED, AutonomyLevel.SEMI_AUTONOMOUS): True,
        (ToolAccessLevel.WRITE_LIMITED, AutonomyLevel.AUTONOMOUS): True,
        (ToolAccessLevel.WRITE_LIMITED, AutonomyLevel.RESTRICTED): False,  # ブロック
        
        (ToolAccessLevel.WRITE_FULL, AutonomyLevel.SUPERVISED): False,
        (ToolAccessLevel.WRITE_FULL, AutonomyLevel.SEMI_AUTONOMOUS): False,  # 承認必須
        (ToolAccessLevel.WRITE_FULL, AutonomyLevel.AUTONOMOUS): True,
        (ToolAccessLevel.WRITE_FULL, AutonomyLevel.RESTRICTED): False,
        
        (ToolAccessLevel.CRITICAL, AutonomyLevel.SUPERVISED): False,
        (ToolAccessLevel.CRITICAL, AutonomyLevel.SEMI_AUTONOMOUS): False,
        (ToolAccessLevel.CRITICAL, AutonomyLevel.AUTONOMOUS): False,  # 常にブロック
        (ToolAccessLevel.CRITICAL, AutonomyLevel.RESTRICTED): False,
    }
    
    # デフォルト承認要件マトリックス
    DEFAULT_APPROVAL_MATRIX = {
        (ToolAccessLevel.READ_ONLY, AutonomyLevel.SUPERVISED): False,
        (ToolAccessLevel.READ_ONLY, AutonomyLevel.SEMI_AUTONOMOUS): False,
        (ToolAccessLevel.READ_ONLY, AutonomyLevel.AUTONOMOUS): False,
        (ToolAccessLevel.READ_ONLY, AutonomyLevel.RESTRICTED): False,
        
        (ToolAccessLevel.WRITE_LIMITED, AutonomyLevel.SUPERVISED): True,  # 要承認
        (ToolAccessLevel.WRITE_LIMITED, AutonomyLevel.SEMI_AUTONOMOUS): False,
        (ToolAccessLevel.WRITE_LIMITED, AutonomyLevel.AUTONOMOUS): False,
        (ToolAccessLevel.WRITE_LIMITED, AutonomyLevel.RESTRICTED): True,  # ブロック
        
        (ToolAccessLevel.WRITE_FULL, AutonomyLevel.SUPERVISED): True,
        (ToolAccessLevel.WRITE_FULL, AutonomyLevel.SEMI_AUTONOMOUS): True,
        (ToolAccessLevel.WRITE_FULL, AutonomyLevel.AUTONOMOUS): False,
        (ToolAccessLevel.WRITE_FULL, AutonomyLevel.RESTRICTED): True,
        
        (ToolAccessLevel.CRITICAL, AutonomyLevel.SUPERVISED): True,
        (ToolAccessLevel.CRITICAL, AutonomyLevel.SEMI_AUTONOMOUS): True,
        (ToolAccessLevel.CRITICAL, AutonomyLevel.AUTONOMOUS): True,  # 常に要承認
        (ToolAccessLevel.CRITICAL, AutonomyLevel.RESTRICTED): True,
    }
    
    def __init__(self):
        """初期化"""
        self.policies: Dict[str, PermissionPolicy] = {}
        self.execution_history: List[Dict] = []  # 実行記録
        self._init_default_policies()
    
    def _init_default_policies(self):
        """デフォルトツール権限ポリシーを初期化"""
        # 読み取り専用ツール
        self.register_policy(PermissionPolicy(
            tool_name="web_search",
            access_level=ToolAccessLevel.READ_ONLY,
            requires_approval={
                AutonomyLevel.SUPERVISED: False,
                AutonomyLevel.SEMI_AUTONOMOUS: False,
                AutonomyLevel.AUTONOMOUS: False,
                AutonomyLevel.RESTRICTED: False,
            },
            max_execution_per_hour=100,
        ))
        
        self.register_policy(PermissionPolicy(
            tool_name="database_query",
            access_level=ToolAccessLevel.READ_ONLY,
            requires_approval={
                AutonomyLevel.SUPERVISED: False,
                AutonomyLevel.SEMI_AUTONOMOUS: False,
                AutonomyLevel.AUTONOMOUS: False,
                AutonomyLevel.RESTRICTED: False,
            },
            max_execution_per_hour=50,
        ))
        
        # 書き込み制限ツール
        self.register_policy(PermissionPolicy(
            tool_name="file_modify",
            access_level=ToolAccessLevel.WRITE_LIMITED,
            requires_approval={
                AutonomyLevel.SUPERVISED: True,
                AutonomyLevel.SEMI_AUTONOMOUS: False,
                AutonomyLevel.AUTONOMOUS: False,
                AutonomyLevel.RESTRICTED: True,
            },
            max_execution_per_hour=20,
            allowed_parameters=["file_path", "content", "mode"],
        ))
        
        # 完全書き込みツール
        self.register_policy(PermissionPolicy(
            tool_name="file_create",
            access_level=ToolAccessLevel.WRITE_FULL,
            requires_approval={
                AutonomyLevel.SUPERVISED: True,
                AutonomyLevel.SEMI_AUTONOMOUS: True,
                AutonomyLevel.AUTONOMOUS: False,
                AutonomyLevel.RESTRICTED: True,
            },
            max_execution_per_hour=10,
        ))
        
        self.register_policy(PermissionPolicy(
            tool_name="file_delete",
            access_level=ToolAccessLevel.WRITE_FULL,
            requires_approval={
                AutonomyLevel.SUPERVISED: True,
                AutonomyLevel.SEMI_AUTONOMOUS: True,
                AutonomyLevel.AUTONOMOUS: False,
                AutonomyLevel.RESTRICTED: True,
            },
            max_execution_per_hour=5,
        ))
        
        # 重大操作ツール
        self.register_policy(PermissionPolicy(
            tool_name="system_config_change",
            access_level=ToolAccessLevel.CRITICAL,
            requires_approval={
                AutonomyLevel.SUPERVISED: True,
                AutonomyLevel.SEMI_AUTONOMOUS: True,
                AutonomyLevel.AUTONOMOUS: True,  # 常に要承認
                AutonomyLevel.RESTRICTED: True,
            },
            max_execution_per_hour=1,
        ))
        
        self.register_policy(PermissionPolicy(
            tool_name="authentication_change",
            access_level=ToolAccessLevel.CRITICAL,
            requires_approval={
                AutonomyLevel.SUPERVISED: True,
                AutonomyLevel.SEMI_AUTONOMOUS: True,
                AutonomyLevel.AUTONOMOUS: True,
                AutonomyLevel.RESTRICTED: True,
            },
            max_execution_per_hour=1,
        ))
    
    def register_policy(self, policy: PermissionPolicy):
        """カスタム権限ポリシーを登録"""
        self.policies[policy.tool_name] = policy
        logger.info(f"Policy registered for tool: {policy.tool_name}")
    
    def can_execute(
        self,
        tool_name: str,
        autonomy_level: AutonomyLevel,
        parameters: Optional[Dict] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        ツール実行が許可されているかチェック
        
        Args:
            tool_name: ツール名
            autonomy_level: 自律レベル
            parameters: 実行パラメータ
        
        Returns:
            (実行許可フラグ, エラーメッセージ)
        """
        # ポリシーを取得
        if tool_name not in self.policies:
            return False, f"Unknown tool: {tool_name}"
        
        policy = self.policies[tool_name]
        
        # マトリックスで実行可否を判定
        key = (policy.access_level, autonomy_level)
        permitted = self.DEFAULT_PERMISSION_MATRIX.get(key, False)
        
        if not permitted:
            reason = self._get_denial_reason(policy.access_level, autonomy_level)
            logger.warning(f"Execution denied for {tool_name}: {reason}")
            return False, reason
        
        # パラメータ検証
        if parameters:
            param_check, param_error = self._validate_parameters(policy, parameters)
            if not param_check:
                return False, param_error
        
        # 実行回数制限をチェック
        if policy.max_execution_per_hour:
            rate_check, rate_error = self._check_execution_rate(tool_name, policy)
            if not rate_check:
                return False, rate_error
        
        return True, None
    
    def requires_approval(
        self,
        tool_name: str,
        autonomy_level: AutonomyLevel,
    ) -> bool:
        """
        実行に承認が必要かチェック
        
        Args:
            tool_name: ツール名
            autonomy_level: 自律レベル
        
        Returns:
            承認必須かどうか
        """
        if tool_name not in self.policies:
            return True  # 未知のツールは要承認
        
        policy = self.policies[tool_name]
        key = (policy.access_level, autonomy_level)
        return self.DEFAULT_APPROVAL_MATRIX.get(key, True)
    
    def _get_denial_reason(
        self,
        access_level: ToolAccessLevel,
        autonomy_level: AutonomyLevel,
    ) -> str:
        """実行拒否理由を生成"""
        reasons = {
            (ToolAccessLevel.WRITE_LIMITED, AutonomyLevel.SUPERVISED): 
                "Write operations require user approval in SUPERVISED mode",
            (ToolAccessLevel.WRITE_LIMITED, AutonomyLevel.RESTRICTED):
                "Write operations are blocked in RESTRICTED mode",
            (ToolAccessLevel.WRITE_FULL, AutonomyLevel.SUPERVISED):
                "Full write operations require explicit user approval in SUPERVISED mode",
            (ToolAccessLevel.WRITE_FULL, AutonomyLevel.SEMI_AUTONOMOUS):
                "Full write operations require explicit user approval in SEMI_AUTONOMOUS mode",
            (ToolAccessLevel.WRITE_FULL, AutonomyLevel.RESTRICTED):
                "Full write operations are blocked in RESTRICTED mode",
            (ToolAccessLevel.CRITICAL, AutonomyLevel.SUPERVISED):
                "Critical operations are blocked without explicit authorization",
            (ToolAccessLevel.CRITICAL, AutonomyLevel.SEMI_AUTONOMOUS):
                "Critical operations are blocked without explicit authorization",
            (ToolAccessLevel.CRITICAL, AutonomyLevel.AUTONOMOUS):
                "Critical operations require explicit authorization in all modes",
            (ToolAccessLevel.CRITICAL, AutonomyLevel.RESTRICTED):
                "Critical operations are blocked in RESTRICTED mode",
        }
        
        key = (access_level, autonomy_level)
        return reasons.get(key, "Permission denied")
    
    def _validate_parameters(
        self,
        policy: PermissionPolicy,
        parameters: Dict,
    ) -> Tuple[bool, Optional[str]]:
        """パラメータを検証"""
        # 許可パラメータリストをチェック
        if policy.allowed_parameters:
            for param_name in parameters.keys():
                if param_name not in policy.allowed_parameters:
                    return False, f"Parameter '{param_name}' is not allowed"
        
        # ブロック値をチェック
        if policy.blocked_parameter_values:
            for param_name, blocked_values in policy.blocked_parameter_values.items():
                if param_name in parameters:
                    param_value = str(parameters[param_name])
                    if param_value in blocked_values:
                        return False, f"Parameter value '{param_value}' is blocked"
        
        return True, None
    
    def _check_execution_rate(
        self,
        tool_name: str,
        policy: PermissionPolicy,
    ) -> Tuple[bool, Optional[str]]:
        """実行回数制限をチェック"""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        # 過去1時間の実行回数をカウント
        recent_executions = [
            e for e in self.execution_history
            if e['tool_name'] == tool_name and e['timestamp'] > one_hour_ago
        ]
        
        if len(recent_executions) >= policy.max_execution_per_hour:
            return False, f"Rate limit exceeded for {tool_name} ({len(recent_executions)}/{policy.max_execution_per_hour})"
        
        return True, None
    
    def record_execution(
        self,
        tool_name: str,
        autonomy_level: AutonomyLevel,
        success: bool,
        parameters: Optional[Dict] = None,
        error: Optional[str] = None,
    ):
        """実行記録を保存"""
        from datetime import datetime
        
        record = {
            'tool_name': tool_name,
            'autonomy_level': autonomy_level.value,
            'success': success,
            'parameters': parameters,
            'error': error,
            'timestamp': datetime.now(),
        }
        
        self.execution_history.append(record)
        logger.info(f"Execution recorded: {tool_name} (success={success})")
    
    def get_allowed_tools(
        self,
        autonomy_level: AutonomyLevel,
        access_level_filter: Optional[ToolAccessLevel] = None,
    ) -> List[str]:
        """
        特定の自律レベルで実行可能なツール一覧を取得
        
        Args:
            autonomy_level: 自律レベル
            access_level_filter: アクセスレベルフィルタ
        
        Returns:
            実行可能なツール名リスト
        """
        allowed_tools = []
        
        for tool_name, policy in self.policies.items():
            if access_level_filter and policy.access_level != access_level_filter:
                continue
            
            key = (policy.access_level, autonomy_level)
            if self.DEFAULT_PERMISSION_MATRIX.get(key, False):
                allowed_tools.append(tool_name)
        
        return allowed_tools
    
    def get_blocked_tools(
        self,
        autonomy_level: AutonomyLevel,
    ) -> List[str]:
        """
        特定の自律レベルでブロックされているツール一覧を取得
        
        Args:
            autonomy_level: 自律レベル
        
        Returns:
            ブロックされているツール名リスト
        """
        blocked_tools = []
        
        for tool_name, policy in self.policies.items():
            key = (policy.access_level, autonomy_level)
            if not self.DEFAULT_PERMISSION_MATRIX.get(key, False):
                blocked_tools.append(tool_name)
        
        return blocked_tools
    
    def get_approval_required_tools(
        self,
        autonomy_level: AutonomyLevel,
    ) -> List[str]:
        """
        特定の自律レベルで承認が必要なツール一覧を取得
        
        Args:
            autonomy_level: 自律レベル
        
        Returns:
            承認必須のツール名リスト
        """
        approval_required = []
        
        for tool_name, policy in self.policies.items():
            key = (policy.access_level, autonomy_level)
            if self.DEFAULT_APPROVAL_MATRIX.get(key, False):
                approval_required.append(tool_name)
        
        return approval_required
    
    def get_permission_summary(self) -> Dict:
        """権限管理の統計サマリーを取得"""
        return {
            'total_policies': len(self.policies),
            'read_only_tools': len([
                p for p in self.policies.values()
                if p.access_level == ToolAccessLevel.READ_ONLY
            ]),
            'write_limited_tools': len([
                p for p in self.policies.values()
                if p.access_level == ToolAccessLevel.WRITE_LIMITED
            ]),
            'write_full_tools': len([
                p for p in self.policies.values()
                if p.access_level == ToolAccessLevel.WRITE_FULL
            ]),
            'critical_tools': len([
                p for p in self.policies.values()
                if p.access_level == ToolAccessLevel.CRITICAL
            ]),
            'total_executions': len(self.execution_history),
            'successful_executions': len([
                e for e in self.execution_history if e['success']
            ]),
        }
