"""
Sandbox Executor: 隔離環境でのツール実行

Docker コンテナ内で未検証のツール・アクションを実行し、
結果を検証してから本番環境に適用。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import logging
import json
import subprocess

logger = logging.getLogger(__name__)


class SandboxType(Enum):
    """サンドボックス種別"""
    DOCKER_CONTAINER = "docker_container"  # Docker コンテナ
    VIRTUAL_ENV = "virtual_env"  # Python 仮想環境
    SUBPROCESS = "subprocess"  # サブプロセス (最小隔離)
    KUBERNETES_POD = "kubernetes_pod"  # Kubernetes Pod


class ExecutionStatus(Enum):
    """実行ステータス"""
    PENDING = "pending"  # 待機中
    RUNNING = "running"  # 実行中
    SUCCESS = "success"  # 成功
    FAILED = "failed"  # 失敗
    TIMEOUT = "timeout"  # タイムアウト
    SECURITY_BLOCKED = "security_blocked"  # セキュリティ理由で遮断


@dataclass
class SandboxResult:
    """サンドボックス実行結果"""
    execution_id: str
    status: ExecutionStatus
    output: str  # 実行出力
    error_output: str  # エラー出力
    return_code: int  # リターンコード
    execution_time: float  # 実行時間 (秒)
    resource_usage: Dict[str, float]  # CPU, メモリ使用率など
    timestamp: datetime = None
    validation_passed: Optional[bool] = None
    safety_score: Optional[float] = None  # 0-1


@dataclass
class ExecutionPolicy:
    """実行ポリシー"""
    timeout_seconds: float = 30.0
    max_memory_mb: int = 512
    max_cpu_percent: int = 50
    allow_network: bool = False
    allow_filesystem_write: bool = False
    max_file_size_mb: int = 10
    allowed_system_calls: Optional[List[str]] = None


class SandboxExecutor:
    """隔離環境実行管理"""
    
    def __init__(self, sandbox_type: SandboxType = SandboxType.DOCKER_CONTAINER):
        """
        初期化
        
        Args:
            sandbox_type: 使用するサンドボックスタイプ
        """
        self.sandbox_type = sandbox_type
        self.execution_history: List[SandboxResult] = []
        self.default_policy = ExecutionPolicy()
        self.validation_rules: List[Callable] = []
        
        logger.info(f"SandboxExecutor initialized with {sandbox_type.value}")
    
    def execute_in_sandbox(
        self,
        command: str,
        args: Optional[List[str]] = None,
        policy: Optional[ExecutionPolicy] = None,
        working_dir: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
    ) -> SandboxResult:
        """
        サンドボックス環境でコマンドを実行
        
        Args:
            command: 実行コマンド
            args: コマンド引数
            policy: 実行ポリシー
            working_dir: 作業ディレクトリ
            environment: 環境変数
        
        Returns:
            実行結果
        """
        execution_id = f"exec_{datetime.now().timestamp()}"
        policy = policy or self.default_policy
        
        logger.info(f"Starting sandbox execution: {execution_id}")
        logger.info(f"Command: {command} {' '.join(args or [])}")
        
        # 1. セキュリティチェック
        security_check = self._security_check(command, args, policy)
        if not security_check[0]:
            result = SandboxResult(
                execution_id=execution_id,
                status=ExecutionStatus.SECURITY_BLOCKED,
                output="",
                error_output=security_check[1],
                return_code=-1,
                execution_time=0.0,
                resource_usage={},
                timestamp=datetime.now(),
                safety_score=0.0,
            )
            self.execution_history.append(result)
            logger.warning(f"Execution blocked: {security_check[1]}")
            return result
        
        # 2. サンドボックスで実行
        try:
            start_time = datetime.now()
            
            result = self._execute_sandboxed(
                command,
                args,
                policy,
                working_dir,
                environment,
            )
            
            end_time = datetime.now()
            result.execution_time = (end_time - start_time).total_seconds()
            result.execution_id = execution_id
            result.timestamp = datetime.now()
            
        except Exception as e:
            logger.error(f"Sandbox execution error: {e}")
            result = SandboxResult(
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                output="",
                error_output=str(e),
                return_code=-1,
                execution_time=0.0,
                resource_usage={},
                timestamp=datetime.now(),
            )
        
        # 3. 結果を検証
        validation_result = self._validate_result(result, policy)
        result.validation_passed = validation_result['passed']
        result.safety_score = validation_result['safety_score']
        
        # 4. 履歴に記録
        self.execution_history.append(result)
        
        logger.info(
            f"Execution completed: {result.status.value} "
            f"(time: {result.execution_time:.2f}s, safety: {result.safety_score:.2f})"
        )
        
        return result
    
    def _security_check(
        self,
        command: str,
        args: Optional[List[str]],
        policy: ExecutionPolicy,
    ) -> Tuple[bool, str]:
        """
        セキュリティチェック
        
        Returns:
            (チェック結果, エラーメッセージ)
        """
        dangerous_commands = [
            'rm', 'mkfs', 'dd', 'chmod', 'chown', 'sudo',
            'reboot', 'shutdown', 'kill', 'pkill',
        ]
        
        # 危険なコマンドをチェック
        if command in dangerous_commands:
            return (False, f"Dangerous command blocked: {command}")
        
        # ネットワークアクセスをチェック
        if not policy.allow_network:
            network_commands = ['curl', 'wget', 'telnet', 'ssh', 'ftp']
            if command in network_commands:
                return (False, f"Network command blocked: {command}")
        
        # ファイルシステム書き込みをチェック
        if not policy.allow_filesystem_write:
            write_commands = ['rm', 'mv', 'cp', 'mkdir', 'touch', 'tee']
            if command in write_commands:
                return (False, f"Filesystem write blocked: {command}")
        
        return (True, "")
    
    def _execute_sandboxed(
        self,
        command: str,
        args: Optional[List[str]],
        policy: ExecutionPolicy,
        working_dir: Optional[str],
        environment: Optional[Dict[str, str]],
    ) -> SandboxResult:
        """
        実際の隔離実行を実行
        
        Returns:
            実行結果
        """
        # コマンドを構築
        full_command = [command] + (args or [])
        
        # 環境変数をマージ
        env = None
        if environment:
            import os
            env = os.environ.copy()
            env.update(environment)
        
        try:
            # subprocess で実行 (簡易版)
            # 本番では Docker や Kubernetes で隔離実行
            process = subprocess.Popen(
                full_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=working_dir,
                env=env,
                timeout=policy.timeout_seconds,
            )
            
            stdout, stderr = process.communicate(timeout=policy.timeout_seconds)
            
            return SandboxResult(
                execution_id="",
                status=ExecutionStatus.SUCCESS if process.returncode == 0 else ExecutionStatus.FAILED,
                output=stdout.decode('utf-8', errors='replace'),
                error_output=stderr.decode('utf-8', errors='replace'),
                return_code=process.returncode,
                execution_time=0.0,
                resource_usage={'estimated': 'low'},
            )
            
        except subprocess.TimeoutExpired:
            process.kill()
            return SandboxResult(
                execution_id="",
                status=ExecutionStatus.TIMEOUT,
                output="",
                error_output=f"Command timed out after {policy.timeout_seconds}s",
                return_code=-1,
                execution_time=policy.timeout_seconds,
                resource_usage={},
            )
        except Exception as e:
            return SandboxResult(
                execution_id="",
                status=ExecutionStatus.FAILED,
                output="",
                error_output=str(e),
                return_code=-1,
                execution_time=0.0,
                resource_usage={},
            )
    
    def _validate_result(
        self,
        result: SandboxResult,
        policy: ExecutionPolicy,
    ) -> Dict[str, Any]:
        """
        実行結果を検証
        
        Args:
            result: 実行結果
            policy: 実行ポリシー
        
        Returns:
            検証結果 {'passed': bool, 'safety_score': float}
        """
        checks = {
            'status_ok': result.status in [ExecutionStatus.SUCCESS],
            'return_code_ok': result.return_code == 0,
            'timeout_ok': result.status != ExecutionStatus.TIMEOUT,
            'security_ok': result.status != ExecutionStatus.SECURITY_BLOCKED,
            'output_size_ok': len(result.output) <= policy.max_file_size_mb * 1024 * 1024,
            'error_output_ok': len(result.error_output) == 0 or result.status != ExecutionStatus.SUCCESS,
        }
        
        # カスタム検証ルールを適用
        for rule in self.validation_rules:
            checks['custom_rule'] = rule(result)
        
        # 安全スコアを計算
        passed_checks = sum(1 for v in checks.values() if v)
        total_checks = len(checks)
        safety_score = passed_checks / total_checks
        
        passed = all(checks.values())
        
        return {
            'passed': passed,
            'safety_score': safety_score,
            'checks': checks,
        }
    
    def apply_to_production(
        self,
        execution_id: str,
        apply_command: str,
    ) -> bool:
        """
        サンドボックス実行結果を本番環境に適用
        
        Args:
            execution_id: サンドボックス実行ID
            apply_command: 適用コマンド
        
        Returns:
            適用成功
        """
        # 実行結果を検索
        result = None
        for r in self.execution_history:
            if r.execution_id == execution_id:
                result = r
                break
        
        if not result:
            logger.error(f"Execution not found: {execution_id}")
            return False
        
        # 検証が成功していることを確認
        if not result.validation_passed:
            logger.error(f"Validation failed for {execution_id}")
            return False
        
        # 本番環境に適用
        try:
            logger.info(f"Applying to production: {apply_command}")
            # 本番適用処理 (実装は環境に応じる)
            logger.info(f"Successfully applied execution {execution_id}")
            return True
        except Exception as e:
            logger.error(f"Application failed: {e}")
            return False
    
    def compare_results(
        self,
        execution_id1: str,
        execution_id2: str,
    ) -> Dict[str, Any]:
        """
        2つの実行結果を比較
        
        Args:
            execution_id1: 実行ID 1
            execution_id2: 実行ID 2
        
        Returns:
            比較結果
        """
        result1 = None
        result2 = None
        
        for r in self.execution_history:
            if r.execution_id == execution_id1:
                result1 = r
            if r.execution_id == execution_id2:
                result2 = r
        
        if not result1 or not result2:
            return {'error': 'One or both executions not found'}
        
        return {
            'execution1': execution_id1,
            'execution2': execution_id2,
            'status_same': result1.status == result2.status,
            'output_same': result1.output == result2.output,
            'time_diff': abs(result1.execution_time - result2.execution_time),
            'safety_score_diff': abs(result1.safety_score - result2.safety_score),
        }
    
    def get_execution_report(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """実行レポートを取得"""
        for result in self.execution_history:
            if result.execution_id == execution_id:
                return {
                    'execution_id': result.execution_id,
                    'status': result.status.value,
                    'output': result.output[:500],  # 最初の500文字
                    'error': result.error_output[:500],
                    'return_code': result.return_code,
                    'execution_time': result.execution_time,
                    'validation_passed': result.validation_passed,
                    'safety_score': result.safety_score,
                    'timestamp': result.timestamp.isoformat() if result.timestamp else None,
                }
        return None
    
    def get_sandbox_statistics(self) -> Dict[str, Any]:
        """サンドボックス統計を取得"""
        if not self.execution_history:
            return {'total_executions': 0}
        
        success_count = len([r for r in self.execution_history if r.status == ExecutionStatus.SUCCESS])
        failed_count = len([r for r in self.execution_history if r.status == ExecutionStatus.FAILED])
        blocked_count = len([r for r in self.execution_history if r.status == ExecutionStatus.SECURITY_BLOCKED])
        
        avg_time = sum(r.execution_time for r in self.execution_history) / len(self.execution_history)
        avg_safety = sum(r.safety_score for r in self.execution_history if r.safety_score) / len([r for r in self.execution_history if r.safety_score])
        
        return {
            'total_executions': len(self.execution_history),
            'success': success_count,
            'failed': failed_count,
            'blocked': blocked_count,
            'success_rate': success_count / len(self.execution_history),
            'average_execution_time': avg_time,
            'average_safety_score': avg_safety,
        }
