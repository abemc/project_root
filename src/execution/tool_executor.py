"""
Tool Executor: 実際のツール・コマンド実行

Permission Manager による権限チェック → Sandbox Executor で検証 →
本番環境での実行という一貫性のある実行パイプラインを提供。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Callable
from datetime import datetime, timedelta
import logging
import subprocess
import signal
import os

logger = logging.getLogger(__name__)


class ToolType(Enum):
    """ツールの種別"""
    SYSTEM_COMMAND = "system_command"  # OS コマンド (echo, ls など)
    PYTHON_FUNCTION = "python_function"  # Python 関数実行
    API_CALL = "api_call"  # 外部 API 呼び出し
    DATABASE_QUERY = "database_query"  # DB クエリ実行
    FILE_OPERATION = "file_operation"  # ファイル操作
    SHELL_SCRIPT = "shell_script"  # シェルスクリプト実行


class ExecutionPhase(Enum):
    """実行フェーズ"""
    PERMISSION_CHECK = "permission_check"  # 権限チェック
    SANDBOX_VALIDATION = "sandbox_validation"  # サンドボックス検証
    PRODUCTION_EXECUTION = "production_execution"  # 本番実行
    RESULT_VALIDATION = "result_validation"  # 結果検証
    COMPLETION = "completion"  # 完了


@dataclass
class ToolDefinition:
    """ツール定義"""
    name: str
    tool_type: ToolType
    description: str
    timeout_seconds: float = 30.0
    requires_approval: bool = False
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    custom_validator: Optional[Callable] = None
    environment_vars: Optional[Dict[str, str]] = None
    allowed_args: Optional[List[str]] = None  # 許可する引数パターン


@dataclass
class ExecutionContext:
    """実行コンテキスト"""
    tool_name: str
    command: str
    args: List[str]
    context_data: Dict[str, Any]
    execution_phases: List[ExecutionPhase]
    timestamp: datetime = None


@dataclass
class ExecutionResult:
    """実行結果"""
    execution_id: str
    tool_name: str
    status: str  # SUCCESS, FAILED, TIMEOUT, PERMISSION_DENIED など
    output: str
    error_output: str
    return_code: int
    execution_time: float
    phase_results: Dict[ExecutionPhase, bool]  # 各フェーズの成否
    safety_score: float
    retry_count: int
    timestamp: datetime = None
    context: Optional[ExecutionContext] = None


class ToolRegistry:
    """ツール定義のレジストリ"""
    
    def __init__(self):
        """初期化"""
        self.tools: Dict[str, ToolDefinition] = {}
        self._init_default_tools()
    
    def _init_default_tools(self):
        """デフォルトツールを登録"""
        default_tools = [
            ToolDefinition(
                name='web_search',
                tool_type=ToolType.PYTHON_FUNCTION,
                description='Search the web using DuckDuckGo',
                timeout_seconds=30.0,
                requires_approval=False,
                max_retries=3,
            ),
            ToolDefinition(
                name='file_create',
                tool_type=ToolType.FILE_OPERATION,
                description='Create a new file',
                timeout_seconds=10.0,
                requires_approval=True,
                max_retries=1,
            ),
            ToolDefinition(
                name='file_modify',
                tool_type=ToolType.FILE_OPERATION,
                description='Modify an existing file',
                timeout_seconds=10.0,
                requires_approval=True,
                max_retries=2,
            ),
            ToolDefinition(
                name='file_delete',
                tool_type=ToolType.FILE_OPERATION,
                description='Delete a file',
                timeout_seconds=5.0,
                requires_approval=True,
                max_retries=0,
            ),
            ToolDefinition(
                name='database_query',
                tool_type=ToolType.DATABASE_QUERY,
                description='Execute a database query',
                timeout_seconds=60.0,
                requires_approval=False,
                max_retries=2,
            ),
            ToolDefinition(
                name='api_call',
                tool_type=ToolType.API_CALL,
                description='Call an external API',
                timeout_seconds=30.0,
                requires_approval=False,
                max_retries=3,
            ),
        ]
        
        for tool in default_tools:
            self.register_tool(tool)
    
    def register_tool(self, tool_definition: ToolDefinition):
        """ツールを登録"""
        self.tools[tool_definition.name] = tool_definition
        logger.info(f"Tool registered: {tool_definition.name}")
    
    def get_tool(self, tool_name: str) -> Optional[ToolDefinition]:
        """ツール定義を取得"""
        return self.tools.get(tool_name)
    
    def get_all_tools(self) -> List[ToolDefinition]:
        """全ツール定義を取得"""
        return list(self.tools.values())


class ToolExecutor:
    """ツール実行エンジン"""
    
    def __init__(
        self,
        permission_manager=None,
        sandbox_executor=None,
        decision_explainer=None,
    ):
        """
        初期化
        
        Args:
            permission_manager: PermissionManager インスタンス
            sandbox_executor: SandboxExecutor インスタンス
            decision_explainer: DecisionExplainer インスタンス
        """
        self.tool_registry = ToolRegistry()
        self.permission_manager = permission_manager
        self.sandbox_executor = sandbox_executor
        self.decision_explainer = decision_explainer
        
        self.execution_history: List[ExecutionResult] = []
        self.approval_callbacks: List[Callable] = []
        
        logger.info("ToolExecutor initialized")
    
    def execute_tool(
        self,
        tool_name: str,
        args: Optional[List[str]] = None,
        autonomy_level: str = "SEMI_AUTONOMOUS",
        require_sandbox_validation: bool = True,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        ツールを実行
        
        Args:
            tool_name: ツール名
            args: ツール引数
            autonomy_level: 自律度レベル
            require_sandbox_validation: サンドボックス検証が必須か
            context_data: コンテキストデータ
        
        Returns:
            実行結果
        """
        execution_id = f"exec_{datetime.now().timestamp()}"
        args = args or []
        context_data = context_data or {}
        
        logger.info(f"Starting tool execution: {execution_id} ({tool_name})")
        
        # ツール定義を取得
        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            logger.error(f"Tool not found: {tool_name}")
            return ExecutionResult(
                execution_id=execution_id,
                tool_name=tool_name,
                status='TOOL_NOT_FOUND',
                output='',
                error_output=f'Tool "{tool_name}" not found in registry',
                return_code=-1,
                execution_time=0.0,
                phase_results={},
                safety_score=0.0,
                retry_count=0,
                timestamp=datetime.now(),
            )
        
        # 実行コンテキストを構築
        context = ExecutionContext(
            tool_name=tool_name,
            command=tool_name,
            args=args,
            context_data=context_data,
            execution_phases=[
                ExecutionPhase.PERMISSION_CHECK,
                ExecutionPhase.SANDBOX_VALIDATION if require_sandbox_validation else None,
                ExecutionPhase.PRODUCTION_EXECUTION,
                ExecutionPhase.RESULT_VALIDATION,
                ExecutionPhase.COMPLETION,
            ],
            timestamp=datetime.now(),
        )
        context.execution_phases = [p for p in context.execution_phases if p is not None]
        
        phase_results = {}
        start_time = datetime.now()
        
        try:
            # フェーズ 1: 権限チェック
            phase_results[ExecutionPhase.PERMISSION_CHECK] = (
                self._phase_permission_check(tool, autonomy_level)
            )
            
            if not phase_results[ExecutionPhase.PERMISSION_CHECK]:
                logger.warning(f"Permission denied for {tool_name}")
                return self._create_result(
                    execution_id, tool_name, 'PERMISSION_DENIED',
                    '', 'Permission denied', -1, start_time, phase_results, 0.0, 0
                )
            
            # フェーズ 2: サンドボックス検証
            if ExecutionPhase.SANDBOX_VALIDATION in context.execution_phases:
                phase_results[ExecutionPhase.SANDBOX_VALIDATION] = (
                    self._phase_sandbox_validation(tool, args)
                )
                
                if not phase_results[ExecutionPhase.SANDBOX_VALIDATION]:
                    logger.warning(f"Sandbox validation failed for {tool_name}")
                    return self._create_result(
                        execution_id, tool_name, 'SANDBOX_VALIDATION_FAILED',
                        '', 'Sandbox validation failed', -1, start_time, phase_results, 0.0, 0
                    )
            
            # フェーズ 3: 本番実行（リトライロジック付き）
            result = self._phase_production_execution(
                execution_id, tool, args, tool.max_retries
            )
            
            phase_results[ExecutionPhase.PRODUCTION_EXECUTION] = (
                result.return_code == 0
            )
            
            # フェーズ 4: 結果検証
            phase_results[ExecutionPhase.RESULT_VALIDATION] = (
                self._phase_result_validation(result, tool)
            )
            
            phase_results[ExecutionPhase.COMPLETION] = True
            
            # 最終結果を構築
            final_result = ExecutionResult(
                execution_id=execution_id,
                tool_name=tool_name,
                status=self._determine_status(phase_results),
                output=result.output,
                error_output=result.error_output,
                return_code=result.return_code,
                execution_time=(datetime.now() - start_time).total_seconds(),
                phase_results=phase_results,
                safety_score=self._calculate_safety_score(phase_results),
                retry_count=result.retry_count,
                timestamp=datetime.now(),
                context=context,
            )
            
            self.execution_history.append(final_result)
            logger.info(
                f"Tool execution completed: {tool_name} "
                f"(status: {final_result.status}, safety: {final_result.safety_score:.2f})"
            )
            
            return final_result
            
        except Exception as e:
            logger.error(f"Unexpected error during execution: {e}")
            return self._create_result(
                execution_id, tool_name, 'ERROR',
                '', str(e), -1, start_time, phase_results, 0.0, 0
            )
    
    def _phase_permission_check(
        self,
        tool: ToolDefinition,
        autonomy_level: str,
    ) -> bool:
        """フェーズ 1: 権限チェック"""
        if not self.permission_manager:
            logger.warning("PermissionManager not configured, allowing all tools")
            return True
        
        can_execute = self.permission_manager.can_execute(
            tool_name=tool.name,
            autonomy_level=autonomy_level,
        )
        
        if not can_execute:
            return False
        
        # 承認が必要か確認
        if self.permission_manager.requires_approval(
            tool_name=tool.name,
            autonomy_level=autonomy_level,
        ):
            # 承認コールバックを実行
            if self.approval_callbacks:
                approved = any(
                    callback(tool.name, tool.description)
                    for callback in self.approval_callbacks
                )
                return approved
        
        return True
    
    def _phase_sandbox_validation(
        self,
        tool: ToolDefinition,
        args: List[str],
    ) -> bool:
        """フェーズ 2: サンドボックス検証"""
        if not self.sandbox_executor:
            logger.warning("SandboxExecutor not configured, skipping validation")
            return True
        
        result = self.sandbox_executor.execute_in_sandbox(
            command=tool.name,
            args=args,
        )
        
        return result.validation_passed if result.validation_passed is not None else True
    
    def _phase_production_execution(
        self,
        execution_id: str,
        tool: ToolDefinition,
        args: List[str],
        max_retries: int,
    ) -> ExecutionResult:
        """フェーズ 3: 本番実行（リトライロジック付き）"""
        retry_count = 0
        last_error = None
        
        while retry_count <= max_retries:
            try:
                logger.info(f"Executing {tool.name} (attempt {retry_count + 1})")
                
                # 説明を生成
                if self.decision_explainer:
                    self.decision_explainer.explain_tool_selection(
                        task_description=f"Execute {tool.name}",
                        selected_tool=tool.name,
                        tool_candidates=[tool.name],
                        success_rates={tool.name: 0.8},
                        confidence=0.8,
                    )
                
                # ツール実行
                output, error_output, return_code = self._execute_tool_internal(
                    tool, args, tool.timeout_seconds
                )
                
                # 成功時は返却
                if return_code == 0:
                    return ExecutionResult(
                        execution_id=execution_id,
                        tool_name=tool.name,
                        status='SUCCESS',
                        output=output,
                        error_output=error_output,
                        return_code=return_code,
                        execution_time=0.0,
                        phase_results={},
                        safety_score=1.0,
                        retry_count=retry_count,
                    )
                
                # 失敗時は記録
                last_error = error_output
                
            except subprocess.TimeoutExpired:
                logger.warning(f"{tool.name} timed out")
                last_error = f"Timeout after {tool.timeout_seconds}s"
                
            except Exception as e:
                logger.error(f"Error executing {tool.name}: {e}")
                last_error = str(e)
            
            retry_count += 1
            
            # リトライ前に待機
            if retry_count <= max_retries:
                logger.info(f"Retrying {tool.name} in {tool.retry_delay_seconds}s")
                import time
                time.sleep(tool.retry_delay_seconds)
        
        # リトライ失敗
        return ExecutionResult(
            execution_id=execution_id,
            tool_name=tool.name,
            status='FAILED',
            output='',
            error_output=last_error or 'All retries exhausted',
            return_code=-1,
            execution_time=0.0,
            phase_results={},
            safety_score=0.0,
            retry_count=retry_count,
        )
    
    def _execute_tool_internal(
        self,
        tool: ToolDefinition,
        args: List[str],
        timeout_seconds: float,
    ) -> Tuple[str, str, int]:
        """実際のツール実行を行う（内部メソッド）"""
        
        if tool.tool_type == ToolType.SYSTEM_COMMAND:
            # システムコマンドを実行
            full_command = [tool.name] + args
            
            process = subprocess.Popen(
                full_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=tool.environment_vars,
                timeout=timeout_seconds,
            )
            
            stdout, stderr = process.communicate(timeout=timeout_seconds)
            return (
                stdout.decode('utf-8', errors='replace'),
                stderr.decode('utf-8', errors='replace'),
                process.returncode,
            )
        
        elif tool.tool_type == ToolType.PYTHON_FUNCTION:
            # Python 関数として実行（プレースホルダー）
            logger.info(f"Executing Python function: {tool.name}")
            return ('Function executed', '', 0)
        
        elif tool.tool_type == ToolType.FILE_OPERATION:
            # ファイル操作を実行
            if tool.name == 'file_create':
                return self._execute_file_create(args)
            elif tool.name == 'file_modify':
                return self._execute_file_modify(args)
            elif tool.name == 'file_delete':
                return self._execute_file_delete(args)
        
        elif tool.tool_type == ToolType.DATABASE_QUERY:
            # DB クエリを実行（プレースホルダー）
            logger.info(f"Executing database query: {args}")
            return ('Query executed', '', 0)
        
        elif tool.tool_type == ToolType.API_CALL:
            # API を呼び出し（プレースホルダー）
            logger.info(f"Making API call: {args}")
            return ('API call successful', '', 0)
        
        return ('Tool executed', '', 0)
    
    def _execute_file_create(self, args: List[str]) -> Tuple[str, str, int]:
        """ファイル作成実行"""
        if len(args) < 2:
            return ('', 'file_create requires: filepath, content', -1)
        
        filepath, content = args[0], args[1]
        
        try:
            with open(filepath, 'w') as f:
                f.write(content)
            return (f'File created: {filepath}', '', 0)
        except Exception as e:
            return ('', str(e), -1)
    
    def _execute_file_modify(self, args: List[str]) -> Tuple[str, str, int]:
        """ファイル修正実行"""
        if len(args) < 2:
            return ('', 'file_modify requires: filepath, content', -1)
        
        filepath, content = args[0], args[1]
        
        try:
            with open(filepath, 'a') as f:
                f.write(content)
            return (f'File modified: {filepath}', '', 0)
        except Exception as e:
            return ('', str(e), -1)
    
    def _execute_file_delete(self, args: List[str]) -> Tuple[str, str, int]:
        """ファイル削除実行"""
        if len(args) < 1:
            return ('', 'file_delete requires: filepath', -1)
        
        filepath = args[0]
        
        try:
            os.remove(filepath)
            return (f'File deleted: {filepath}', '', 0)
        except Exception as e:
            return ('', str(e), -1)
    
    def _phase_result_validation(
        self,
        result: ExecutionResult,
        tool: ToolDefinition,
    ) -> bool:
        """フェーズ 4: 結果検証"""
        # カスタムバリデータがあれば実行
        if tool.custom_validator:
            return tool.custom_validator(result)
        
        # デフォルト検証: リターンコードが 0 か確認
        return result.return_code == 0
    
    def _create_result(
        self,
        execution_id: str,
        tool_name: str,
        status: str,
        output: str,
        error_output: str,
        return_code: int,
        start_time: datetime,
        phase_results: Dict,
        safety_score: float,
        retry_count: int,
    ) -> ExecutionResult:
        """実行結果を生成"""
        return ExecutionResult(
            execution_id=execution_id,
            tool_name=tool_name,
            status=status,
            output=output,
            error_output=error_output,
            return_code=return_code,
            execution_time=(datetime.now() - start_time).total_seconds(),
            phase_results=phase_results,
            safety_score=safety_score,
            retry_count=retry_count,
            timestamp=datetime.now(),
        )
    
    def _determine_status(self, phase_results: Dict[ExecutionPhase, bool]) -> str:
        """フェーズ結果から最終ステータスを決定"""
        if not all(phase_results.values()):
            failed_phases = [p.value for p, r in phase_results.items() if not r]
            if ExecutionPhase.PERMISSION_CHECK in phase_results and not phase_results[ExecutionPhase.PERMISSION_CHECK]:
                return 'PERMISSION_DENIED'
            elif ExecutionPhase.SANDBOX_VALIDATION in phase_results and not phase_results[ExecutionPhase.SANDBOX_VALIDATION]:
                return 'SANDBOX_VALIDATION_FAILED'
            elif ExecutionPhase.PRODUCTION_EXECUTION in phase_results and not phase_results[ExecutionPhase.PRODUCTION_EXECUTION]:
                return 'EXECUTION_FAILED'
            else:
                return 'VALIDATION_FAILED'
        return 'SUCCESS'
    
    def _calculate_safety_score(self, phase_results: Dict[ExecutionPhase, bool]) -> float:
        """安全スコアを計算"""
        passed = sum(1 for r in phase_results.values() if r)
        total = len(phase_results)
        return passed / total if total > 0 else 0.0
    
    def register_approval_callback(self, callback: Callable):
        """承認コールバックを登録"""
        self.approval_callbacks.append(callback)
    
    def get_execution_report(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """実行レポートを取得"""
        for result in self.execution_history:
            if result.execution_id == execution_id:
                return {
                    'execution_id': result.execution_id,
                    'tool_name': result.tool_name,
                    'status': result.status,
                    'output': result.output[:500],
                    'error': result.error_output[:500],
                    'execution_time': result.execution_time,
                    'safety_score': result.safety_score,
                    'phase_results': {p.value: r for p, r in result.phase_results.items()},
                    'timestamp': result.timestamp.isoformat() if result.timestamp else None,
                }
        return None
    
    def get_tool_executor_statistics(self) -> Dict[str, Any]:
        """ツール実行統計を取得"""
        if not self.execution_history:
            return {'total_executions': 0}
        
        success_count = len([r for r in self.execution_history if r.status == 'SUCCESS'])
        failed_count = len([r for r in self.execution_history if 'FAILED' in r.status])
        
        return {
            'total_executions': len(self.execution_history),
            'success': success_count,
            'failed': failed_count,
            'success_rate': success_count / len(self.execution_history),
            'avg_safety_score': (
                sum(r.safety_score for r in self.execution_history) / len(self.execution_history)
            ),
            'total_retry_count': sum(r.retry_count for r in self.execution_history),
        }
