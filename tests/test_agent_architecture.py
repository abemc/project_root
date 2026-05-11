"""
Phase 17 Task 3: Agent Architecture Tests

エージェント自律化システムの包括的テスト
- タスク計画・分解
- ツール実行・統合
- 自己改善・学習
- モニタリング・制御
"""

from src.agent_architecture.agent_engine import (
    TaskPlanner, ToolExecutor, SelfImprovement, MonitoringSystem, AgentEngine,
    Tool, ToolType, AutonomyLevel, ExecutionPlan, SubTask, ToolResult
)


class TestTaskPlanner:
    """タスク計画エンジンテスト"""
    
    def setup_method(self):
        self.planner = TaskPlanner()
        self.context = {
            "available_tools": ["web_search", "calculator", "file_writer"],
            "constraints": {"time_limit": 3600}
        }
    
    def test_planner_initialization(self):
        """計画エンジン初期化"""
        assert self.planner.max_depth == 5
        assert self.planner is not None
    
    def test_decompose_simple_task(self):
        """単純タスク分解"""
        goal = "Search for information"
        plan = self.planner.decompose_task(goal, self.context)
        
        assert isinstance(plan, ExecutionPlan)
        assert plan.main_goal == goal
        assert plan.status == "ready"
        assert len(plan.execution_order) > 0
    
    def test_decompose_moderate_task(self):
        """中程度複雑タスク分解"""
        goal = "Analyze and process data"
        plan = self.planner.decompose_task(goal, self.context)
        
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.subtasks) >= 3
        assert len(plan.execution_order) == len(plan.subtasks)
    
    def test_decompose_complex_task(self):
        """複雑タスク分解"""
        goal = "Design and optimize complete system"
        plan = self.planner.decompose_task(goal, self.context)
        
        assert isinstance(plan, ExecutionPlan)
        assert plan.estimated_steps > 0
        assert all(isinstance(st, SubTask) for st in plan.subtasks)
    
    def test_complexity_analysis(self):
        """複雑性分析"""
        simple_goal = "Search for data"
        moderate_goal = "Process and analyze data"
        complex_goal = "Design optimization strategy"
        
        assert self.planner._analyze_complexity(simple_goal) == "simple"
        assert self.planner._analyze_complexity(moderate_goal) == "moderate"
        assert self.planner._analyze_complexity(complex_goal) == "complex"
    
    def test_identify_required_tools(self):
        """必要ツール特定"""
        tools_search = self.planner._identify_required_tools("search for data", self.context)
        assert "web_search" in tools_search
        
        tools_calc = self.planner._identify_required_tools("calculate sum", self.context)
        assert "calculator" in tools_calc
        
        tools_write = self.planner._identify_required_tools("create new file", self.context)
        assert "file_writer" in tools_write
    
    def test_topological_sort(self):
        """トポロジカルソート"""
        subtasks = [
            SubTask(task_id="task_1", description="Step 1"),
            SubTask(task_id="task_2", description="Step 2", dependencies=["task_1"]),
            SubTask(task_id="task_3", description="Step 3", dependencies=["task_2"])
        ]
        
        sorted_order = self.planner._topological_sort(subtasks)
        assert sorted_order == ["task_1", "task_2", "task_3"]


class TestToolExecutor:
    """ツール実行エンジンテスト"""
    
    def setup_method(self):
        self.executor = ToolExecutor(AutonomyLevel.SEMI_AUTONOMOUS)
        
        # ツール登録
        def mock_search(query):
            return f"Search results for: {query}"
        
        def mock_calculate(expression):
            return eval(expression)
        
        tool_search = Tool(
            name="web_search",
            tool_type=ToolType.INFORMATION,
            description="Web search",
            execute_fn=mock_search,
            required_params=["query"]
        )
        
        tool_calc = Tool(
            name="calculator",
            tool_type=ToolType.REASONING,
            description="Calculate",
            execute_fn=mock_calculate,
            required_params=["expression"]
        )
        
        self.executor.register_tool(tool_search)
        self.executor.register_tool(tool_calc)
    
    def test_tool_registration(self):
        """ツール登録"""
        assert "web_search" in self.executor.tools
        assert "calculator" in self.executor.tools
    
    def test_execute_tool_success(self):
        """ツール実行成功"""
        result = self.executor.execute_tool("web_search", {"query": "test"})
        
        assert isinstance(result, ToolResult)
        assert result.status == "success"
        assert result.tool_name == "web_search"
    
    def test_execute_tool_missing_params(self):
        """パラメータ不足"""
        result = self.executor.execute_tool("web_search", {})
        
        assert result.status == "error"
        assert "Missing parameters" in result.error_message
    
    def test_execute_tool_not_found(self):
        """存在しないツール"""
        result = self.executor.execute_tool("nonexistent", {})
        
        assert result.status == "error"
        assert "not found" in result.error_message
    
    def test_get_tool_info(self):
        """ツール情報取得"""
        info = self.executor.get_tool_info("web_search")
        
        assert info is not None
        assert info["name"] == "web_search"
        assert info["type"] == "information"
        assert "query" in info["required_params"]
    
    def test_execution_history(self):
        """実行履歴記録"""
        self.executor.execute_tool("web_search", {"query": "test1"})
        self.executor.execute_tool("web_search", {"query": "test2"})
        
        assert len(self.executor.execution_history) == 2


class TestSelfImprovement:
    """自己改善・学習エンジンテスト"""
    
    def setup_method(self):
        self.improvement = SelfImprovement()
    
    def test_record_success_experience(self):
        """成功経験記録"""
        self.improvement.record_experience(
            task="search_data",
            action="web_search",
            result=True,
            execution_time=1.5,
            context={"source": "web"}
        )
        
        assert len(self.improvement.memory) == 1
        assert self.improvement.memory[0]["result"] is True
    
    def test_record_failure_experience(self):
        """失敗経験記録"""
        self.improvement.record_experience(
            task="search_data",
            action="web_search",
            result=False,
            execution_time=0.5,
            context={"source": "web"}
        )
        
        assert len(self.improvement.memory) == 1
        assert "search_data:web_search" in self.improvement.failure_patterns
    
    def test_success_rate_calculation(self):
        """成功率算出"""
        self.improvement.record_experience("task1", "action1", True, 1.0, {})
        self.improvement.record_experience("task1", "action1", True, 1.0, {})
        self.improvement.record_experience("task1", "action1", False, 1.0, {})
        
        success_rate = self.improvement.get_success_rate()
        assert 0.6 < success_rate < 0.7  # 2/3
    
    def test_recommend_strategy(self):
        """戦略推奨"""
        # 成功パターン記録
        for _ in range(5):
            self.improvement.record_experience(
                "task1", "strategy_A", True, 1.0, {}
            )
        
        for _ in range(2):
            self.improvement.record_experience(
                "task1", "strategy_B", True, 1.0, {}
            )
        
        recommended = self.improvement.recommend_strategy("task1")
        assert recommended == "strategy_A"
    
    def test_learning_efficiency(self):
        """学習効率"""
        # 初期状態
        efficiency = self.improvement.get_learning_efficiency()
        assert efficiency == 0.0
        
        # データ追加
        for _ in range(8):
            self.improvement.record_experience("task1", "action1", True, 1.0, {})
        for _ in range(2):
            self.improvement.record_experience("task1", "action1", False, 1.0, {})
        
        efficiency = self.improvement.get_learning_efficiency()
        assert 0.7 < efficiency < 0.9
    
    def test_memory_size_limit(self):
        """メモリサイズ制限"""
        improvement_small = SelfImprovement(memory_size=10)
        
        for i in range(20):
            improvement_small.record_experience(
                f"task_{i}", f"action_{i}", True, 1.0, {}
            )
        
        assert len(improvement_small.memory) <= 10


class TestMonitoringSystem:
    """モニタリング・制御テスト"""
    
    def setup_method(self):
        self.monitoring = MonitoringSystem()
    
    def test_constraint_check_pass(self):
        """制約チェック成功"""
        resource_usage = {
            "cpu_percent": 50,
            "memory_percent": 60
        }
        
        is_ok, violations = self.monitoring.check_constraints(resource_usage)
        assert is_ok is True
        assert len(violations) == 0
    
    def test_constraint_check_cpu_violation(self):
        """CPU制約違反"""
        resource_usage = {
            "cpu_percent": 80,
            "memory_percent": 60
        }
        
        is_ok, violations = self.monitoring.check_constraints(resource_usage)
        assert is_ok is False
        assert any("CPU" in v for v in violations)
    
    def test_constraint_check_memory_violation(self):
        """メモリ制約違反"""
        resource_usage = {
            "cpu_percent": 50,
            "memory_percent": 75
        }
        
        is_ok, violations = self.monitoring.check_constraints(resource_usage)
        assert is_ok is False
        assert any("Memory" in v for v in violations)
    
    def test_audit_log(self):
        """監査ログ記録"""
        self.monitoring.log_action(
            action_type="execute",
            description="Tool execution",
            actor="agent",
            resource_impact={"cpu": 30, "memory": 50}
        )
        
        assert len(self.monitoring.audit_log) == 1
        assert self.monitoring.audit_log[0]["actor"] == "agent"
    
    def test_alert_generation(self):
        """アラート生成"""
        self.monitoring.add_alert(
            severity="warning",
            message="High resource usage",
            recommended_action="Scale up resources"
        )
        
        assert len(self.monitoring.alerts) == 1
        assert self.monitoring.alerts[0]["severity"] == "warning"


class TestAgentEngine:
    """統合エージェントエンジンテスト"""
    
    def setup_method(self):
        self.agent = AgentEngine(AutonomyLevel.SEMI_AUTONOMOUS)
        
        # テストツール登録
        def mock_tool():
            return {"status": "success"}
        
        tool = Tool(
            name="test_tool",
            tool_type=ToolType.REASONING,
            description="Test tool",
            execute_fn=mock_tool
        )
        
        self.agent.executor.register_tool(tool)
    
    def test_agent_initialization(self):
        """エージェント初期化"""
        assert self.agent is not None
        assert self.agent.autonomy_level == AutonomyLevel.SEMI_AUTONOMOUS
    
    def test_execute_simple_goal(self):
        """単純ゴール実行"""
        result = self.agent.execute_goal(
            "search for information",
            {"available_tools": ["test_tool"]}
        )
        
        assert result["goal"] == "search for information"
        assert "status" in result
        assert "execution_plan" in result
    
    def test_execute_complex_goal(self):
        """複雑ゴール実行"""
        result = self.agent.execute_goal(
            "Design optimization plan for system",
            {"available_tools": ["test_tool"]}
        )
        
        assert result["estimated_steps"] > 0
        assert len(result["execution_plan"]["execution_order"]) > 0
    
    def test_agent_status(self):
        """エージェント状態取得"""
        status = self.agent.get_agent_status()
        
        assert "autonomy_level" in status
        assert "success_rate" in status
        assert "learning_efficiency" in status
        assert "memory_usage" in status


class TestAgentIntegration:
    """統合エージェント機能テスト"""
    
    def test_end_to_end_agent_workflow(self):
        """エンドツーエンドワークフロー"""
        agent = AgentEngine(AutonomyLevel.AUTONOMOUS)
        
        def mock_calculate(expr):
            return eval(expr)
        
        tool = Tool(
            name="calculator",
            tool_type=ToolType.REASONING,
            description="Calculate",
            execute_fn=mock_calculate,
            required_params=["expr"]
        )
        
        agent.executor.register_tool(tool)
        
        result = agent.execute_goal(
            "calculate result",
            {"available_tools": ["calculator"]}
        )
        
        assert result["status"] in ["completed", "partial"]
    
    def test_agent_self_improvement_integration(self):
        """自己改善統合"""
        agent = AgentEngine()
        
        # 複数のゴール実行
        for i in range(5):
            agent.execute_goal(
                "search task",
                {"available_tools": []}
            )
        
        status = agent.get_agent_status()
        assert status["total_experiences"] > 0
    
    def test_agent_monitoring_integration(self):
        """モニタリング統合"""
        agent = AgentEngine()
        
        # 制約チェック
        is_ok, violations = agent.monitoring.check_constraints({
            "cpu_percent": 40,
            "memory_percent": 50
        })
        
        assert is_ok is True
        assert len(violations) == 0
    
    def test_multi_subtask_execution(self):
        """複数サブタスク実行"""
        agent = AgentEngine()
        
        result = agent.execute_goal(
            "Perform complex analysis",
            {"available_tools": []}
        )
        
        assert result["estimated_steps"] >= 3
        assert "completed_steps" in result
