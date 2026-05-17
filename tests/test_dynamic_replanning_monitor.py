from src.agent_architecture.dynamic_task_manager import DynamicTaskManager
from src.agent_architecture.agent_engine import ExecutionPlan, SubTask, ToolResult, MonitoringSystem


class DummyExecutor:
    def __init__(self, results):
        self.results = results
        self.call = 0

    def execute_tool(self, tool_name, params):
        # return the pre-defined ToolResult or dict
        res = self.results[self.call]
        self.call += 1
        return res


def make_plan():
    plan = ExecutionPlan(main_goal="g")
    plan.subtasks.append(SubTask(task_id="a", description="A", required_tools=["t"],))
    plan.subtasks.append(SubTask(task_id="b", description="B", required_tools=["t"],))
    plan.subtasks.append(SubTask(task_id="c", description="C", required_tools=["t"],))
    plan.execution_order = ["a", "b", "c"]
    return plan


def test_monitor_violation_triggers_replan_and_alert():
    monitor = MonitoringSystem()
    # set a low resource limit so the provided usage will violate
    monitor.constraints["resource_limit_percent"] = 10

    # first tool returns high cpu usage to trigger violation
    tr1 = ToolResult(tool_name="t", status="success", result={"resource_usage": {"cpu_percent": 80, "memory_percent": 20}})
    tr2 = ToolResult(tool_name="t", status="success", result={})
    tr3 = ToolResult(tool_name="t", status="success", result={})

    executor = DummyExecutor([tr1, tr2, tr3])
    dtm = DynamicTaskManager(executor=executor, monitor=monitor)
    plan = make_plan()

    summary = dtm.execute_plan(plan)

    # monitor should have recorded an alert
    assert len(monitor.alerts) >= 1
    # execution completed and summary exists
    assert "results" in summary
    assert summary["goal"] == plan.main_goal
