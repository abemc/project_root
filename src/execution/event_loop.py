"""
Event Loop: 非同期実行管理

複数のツール実行を並行管理し、イベント駆動型の実行パイプラインを提供。
タスクのキューイング、スケジューリング、キャンセレーション、イベント通知を管理。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Coroutine
from datetime import datetime, timedelta
import logging
import asyncio
from queue import Queue, PriorityQueue
from threading import Thread, Lock, Event

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """タスク優先度"""
    CRITICAL = 1  # 最高優先度
    HIGH = 2
    NORMAL = 3
    LOW = 4
    DEFERRED = 5  # 最低優先度


class TaskStatus(Enum):
    """タスクステータス"""
    PENDING = "pending"  # 待機中
    QUEUED = "queued"  # キューに入った
    RUNNING = "running"  # 実行中
    PAUSED = "paused"  # 一時停止
    COMPLETED = "completed"  # 完了
    FAILED = "failed"  # 失敗
    CANCELLED = "cancelled"  # キャンセル


class EventType(Enum):
    """イベント種別"""
    TASK_CREATED = "task_created"
    TASK_QUEUED = "task_queued"
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"
    LOOP_STARTED = "loop_started"
    LOOP_STOPPED = "loop_stopped"
    LOOP_ERROR = "loop_error"


@dataclass
class Event:
    """イベント"""
    event_type: EventType
    task_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Task:
    """実行タスク"""
    task_id: str
    tool_name: str
    args: List[str]
    priority: TaskPriority
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    retries_remaining: int = 3
    timeout_seconds: float = 30.0
    dependencies: List[str] = field(default_factory=list)  # 依存タスク ID
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other):
        """優先度キューで使用（優先度が低いほど先）"""
        return self.priority.value < other.priority.value


class EventBus:
    """イベントバス"""
    
    def __init__(self):
        """初期化"""
        self.subscribers: Dict[EventType, List[Callable]] = {}
        self.event_history: List[Event] = []
        self.lock = Lock()
    
    def subscribe(self, event_type: EventType, callback: Callable):
        """イベントハンドラを登録"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: EventType, callback: Callable):
        """イベントハンドラを削除"""
        if event_type in self.subscribers:
            self.subscribers[event_type].remove(callback)
    
    def publish(self, event: Event):
        """イベントを発行"""
        with self.lock:
            self.event_history.append(event)
        
        # サブスクライバーに通知
        callbacks = self.subscribers.get(event.event_type, [])
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")
    
    def get_event_history(self, event_type: Optional[EventType] = None) -> List[Event]:
        """イベント履歴を取得"""
        if event_type:
            return [e for e in self.event_history if e.event_type == event_type]
        return self.event_history.copy()


class TaskGraph:
    """タスク依存グラフ"""
    
    def __init__(self):
        """初期化"""
        self.tasks: Dict[str, Task] = {}
        self.edges: Dict[str, List[str]] = {}  # task_id -> [dependent_ids]
    
    def add_task(self, task: Task):
        """タスクを追加"""
        self.tasks[task.task_id] = task
        if task.task_id not in self.edges:
            self.edges[task.task_id] = []
    
    def add_dependency(self, task_id: str, depends_on_id: str):
        """依存関係を追加"""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")
        if depends_on_id not in self.tasks:
            raise ValueError(f"Task {depends_on_id} not found")
        
        self.tasks[task_id].dependencies.append(depends_on_id)
    
    def get_executable_tasks(self) -> List[Task]:
        """実行可能なタスク（全依存完了済み）を取得"""
        executable = []
        
        for task in self.tasks.values():
            if task.status != TaskStatus.PENDING:
                continue
            
            # 全依存タスクが完了しているか確認
            all_deps_completed = all(
                self.tasks[dep_id].status == TaskStatus.COMPLETED
                for dep_id in task.dependencies
            )
            
            if all_deps_completed:
                executable.append(task)
        
        return executable
    
    def has_circular_dependency(self) -> bool:
        """循環依存をチェック"""
        visited = set()
        rec_stack = set()
        
        def dfs(task_id: str) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)
            
            task = self.tasks.get(task_id)
            if task:
                for dep_id in task.dependencies:
                    if dep_id not in visited:
                        if dfs(dep_id):
                            return True
                    elif dep_id in rec_stack:
                        return True
            
            rec_stack.remove(task_id)
            return False
        
        for task_id in self.tasks:
            if task_id not in visited:
                if dfs(task_id):
                    return True
        
        return False


class EventLoop:
    """イベントループ（非同期実行管理）"""
    
    def __init__(self, max_concurrent_tasks: int = 4):
        """
        初期化
        
        Args:
            max_concurrent_tasks: 最大同時実行タスク数
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.task_queue: PriorityQueue = PriorityQueue()
        self.task_graph = TaskGraph()
        self.event_bus = EventBus()
        self.running_tasks: Dict[str, Task] = {}
        self.completed_tasks: Dict[str, Task] = {}
        
        self.is_running = False
        self.thread = None
        self.stop_event = asyncio.Event()
        
        self.tool_executor = None  # ToolExecutor インスタンス（遅延設定）
        
        logger.info(f"EventLoop initialized (max_concurrent: {max_concurrent_tasks})")
    
    def set_tool_executor(self, tool_executor):
        """ToolExecutor を設定"""
        self.tool_executor = tool_executor
    
    def schedule_task(
        self,
        tool_name: str,
        args: List[str],
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout_seconds: float = 30.0,
        depends_on: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        タスクをスケジュール
        
        Args:
            tool_name: ツール名
            args: 引数
            priority: 優先度
            timeout_seconds: タイムアウト時間
            depends_on: 依存タスク ID リスト
            metadata: メタデータ
        
        Returns:
            タスク ID
        """
        task_id = f"task_{datetime.now().timestamp()}"
        
        task = Task(
            task_id=task_id,
            tool_name=tool_name,
            args=args,
            priority=priority,
            timeout_seconds=timeout_seconds,
            dependencies=depends_on or [],
            metadata=metadata or {},
        )
        
        # グラフに追加
        self.task_graph.add_task(task)
        
        # 循環依存をチェック
        if self.task_graph.has_circular_dependency():
            logger.error(f"Circular dependency detected for task {task_id}")
            raise ValueError("Circular dependency in task graph")
        
        # キューに追加
        self.task_queue.put((priority.value, task))
        
        # イベントを発行
        self.event_bus.publish(Event(
            event_type=EventType.TASK_CREATED,
            task_id=task_id,
            data={'tool_name': tool_name, 'priority': priority.value},
        ))
        
        logger.info(f"Task scheduled: {task_id} ({tool_name})")
        
        return task_id
    
    def cancel_task(self, task_id: str) -> bool:
        """タスクをキャンセル"""
        if task_id in self.task_graph.tasks:
            task = self.task_graph.tasks[task_id]
            if task.status in [TaskStatus.PENDING, TaskStatus.QUEUED]:
                task.status = TaskStatus.CANCELLED
                
                self.event_bus.publish(Event(
                    event_type=EventType.TASK_CANCELLED,
                    task_id=task_id,
                ))
                
                logger.info(f"Task cancelled: {task_id}")
                return True
        
        return False
    
    def pause_task(self, task_id: str) -> bool:
        """タスクを一時停止"""
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            task.status = TaskStatus.PAUSED
            
            self.event_bus.publish(Event(
                event_type=EventType.TASK_PROGRESS,
                task_id=task_id,
                data={'status': 'paused'},
            ))
            
            logger.info(f"Task paused: {task_id}")
            return True
        
        return False
    
    def resume_task(self, task_id: str) -> bool:
        """一時停止されたタスクを再開"""
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            if task.status == TaskStatus.PAUSED:
                task.status = TaskStatus.RUNNING
                
                self.event_bus.publish(Event(
                    event_type=EventType.TASK_PROGRESS,
                    task_id=task_id,
                    data={'status': 'resumed'},
                ))
                
                logger.info(f"Task resumed: {task_id}")
                return True
        
        return False
    
    def start(self):
        """イベントループを開始"""
        if self.is_running:
            logger.warning("Event loop already running")
            return
        
        self.is_running = True
        self.thread = Thread(target=self._run_loop, daemon=False)
        self.thread.start()
        
        self.event_bus.publish(Event(event_type=EventType.LOOP_STARTED))
        logger.info("Event loop started")
    
    def stop(self):
        """イベントループを停止"""
        self.is_running = False
        
        if self.thread:
            self.thread.join(timeout=5.0)
        
        self.event_bus.publish(Event(event_type=EventType.LOOP_STOPPED))
        logger.info("Event loop stopped")
    
    def _run_loop(self):
        """メインループ（別スレッドで実行）"""
        import time
        
        while self.is_running:
            try:
                # 実行可能なタスクを取得
                executable = self.task_graph.get_executable_tasks()
                
                # 実行可能な数まで実行
                available_slots = self.max_concurrent_tasks - len(self.running_tasks)
                for task in executable[:available_slots]:
                    self._execute_task(task)
                
                # 短く待機
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in event loop: {e}")
                self.event_bus.publish(Event(
                    event_type=EventType.LOOP_ERROR,
                    data={'error': str(e)},
                ))
    
    def _execute_task(self, task: Task):
        """タスクを実行"""
        if not self.tool_executor:
            logger.error("ToolExecutor not configured")
            return
        
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self.running_tasks[task.task_id] = task
        
        self.event_bus.publish(Event(
            event_type=EventType.TASK_STARTED,
            task_id=task.task_id,
        ))
        
        # 別スレッドで実行
        def run_task():
            try:
                result = self.tool_executor.execute_tool(
                    tool_name=task.tool_name,
                    args=task.args,
                    context_data=task.metadata,
                )
                
                task.result = result
                task.status = TaskStatus.COMPLETED
                
                self.event_bus.publish(Event(
                    event_type=EventType.TASK_COMPLETED,
                    task_id=task.task_id,
                    data={
                        'status': result.status,
                        'safety_score': result.safety_score,
                    },
                ))
                
            except Exception as e:
                logger.error(f"Task execution error: {e}")
                task.error = str(e)
                task.status = TaskStatus.FAILED
                
                self.event_bus.publish(Event(
                    event_type=EventType.TASK_FAILED,
                    task_id=task.task_id,
                    data={'error': str(e)},
                ))
            
            finally:
                task.completed_at = datetime.now()
                del self.running_tasks[task.task_id]
                self.completed_tasks[task.task_id] = task
        
        thread = Thread(target=run_task, daemon=True)
        thread.start()
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """タスクステータスを取得"""
        if task_id in self.task_graph.tasks:
            return self.task_graph.tasks[task_id].status
        return None
    
    def get_task_result(self, task_id: str) -> Optional[Any]:
        """タスク結果を取得"""
        if task_id in self.completed_tasks:
            return self.completed_tasks[task_id].result
        if task_id in self.task_graph.tasks:
            return self.task_graph.tasks[task_id].result
        return None
    
    def get_running_tasks(self) -> List[Task]:
        """実行中のタスク一覧を取得"""
        return list(self.running_tasks.values())
    
    def get_pending_tasks(self) -> List[Task]:
        """待機中のタスク一覧を取得"""
        return [
            t for t in self.task_graph.tasks.values()
            if t.status in [TaskStatus.PENDING, TaskStatus.QUEUED]
        ]
    
    def get_loop_statistics(self) -> Dict[str, Any]:
        """ループ統計を取得"""
        all_tasks = list(self.task_graph.tasks.values())
        
        return {
            'total_tasks': len(all_tasks),
            'running': len(self.running_tasks),
            'completed': len(self.completed_tasks),
            'pending': len(self.get_pending_tasks()),
            'is_running': self.is_running,
            'max_concurrent': self.max_concurrent_tasks,
            'completed_rate': (
                len(self.completed_tasks) / len(all_tasks)
                if all_tasks else 0
            ),
            'event_count': len(self.event_bus.event_history),
        }
