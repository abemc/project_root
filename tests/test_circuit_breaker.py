from src.agent_architecture.dynamic_task_manager import DynamicTaskManager
from src.agent_architecture.agent_engine import ExecutionPlan, SubTask, ToolResult


class FailingExecutor:
    def __init__(self, fail_times=5):
        self.calls = 0
        self.fail_times = fail_times

    def execute_tool(self, tool_name, params):
        self.calls += 1
        if self.calls <= self.fail_times:
            return ToolResult(tool_name=tool_name, status="error", error_message="boom")
        return ToolResult(tool_name=tool_name, status="success", result={})


def make_plan():
    plan = ExecutionPlan(main_goal="g")
    plan.subtasks.append(SubTask(task_id="t1", description="T1", required_tools=["toolA"]))
    plan.subtasks.append(SubTask(task_id="t2", description="T2", required_tools=["toolA"]))
    plan.subtasks.append(SubTask(task_id="t3", description="T3", required_tools=["toolA"]))
    plan.execution_order = ["t1", "t2", "t3"]
    return plan


def test_circuit_trips_and_skips():
    exec = FailingExecutor(fail_times=4)
    dtm = DynamicTaskManager(executor=exec)
    # set low threshold/cooldown to exercise quickly
    dtm.circuit_threshold = 2
    dtm.circuit_cooldown = 1

    plan = make_plan()
    summary = dtm.execute_plan(plan)

    # After failures, circuit should have tripped and later tasks skipped
    # At least one task should be skipped due to circuit_tripped
    skipped = [k for k, v in summary["results"].items() if v.get("reason") == "circuit_tripped"]
    assert len(skipped) >= 1
    # failure count recorded
    circ = dtm.tool_circuit.get("toolA")
    assert circ is not None
    assert circ.get("fail_count", 0) >= 1
 