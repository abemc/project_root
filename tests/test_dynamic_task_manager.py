import pytest

from src.agent_architecture.dynamic_task_manager import DynamicTaskManager
from src.agent_architecture.agent_engine import ExecutionPlan, SubTask


class MockExecutor:
    def __init__(self, behavior=None):
        self.behavior = behavior or {}

    def execute_tool(self, tool_name, params):
        # Return a simple dict as ToolResult-like
        if tool_name in self.behavior:
            return self.behavior[tool_name]
        return {"status": "success", "result": f"executed:{tool_name}"}


def make_plan_with_tasks(ids):
    plan = ExecutionPlan(main_goal="test_goal")
    for i, tid in enumerate(ids, start=1):
        st = SubTask(task_id=tid, description=f"task {i}", required_tools=["tool_a"])
        plan.subtasks.append(st)
        plan.execution_order.append(tid)
    plan.status = "ready"
    return plan


def test_evaluate_priorities_simple():
    dtm = DynamicTaskManager()
    plan = make_plan_with_tasks(["task_1", "task_2", "task_3"])
    scores = dtm.evaluate_priorities(plan)
    assert isinstance(scores, dict)
    assert set(scores.keys()) == set(["task_1", "task_2", "task_3"]) 
    # Expect non-increasing scores for increasing index
    vals = [scores[k] for k in ["task_1", "task_2", "task_3"]]
    assert vals[0] >= vals[1] >= vals[2]


def test_execute_plan_with_mock_executor():
    dtm = DynamicTaskManager()
    plan = make_plan_with_tasks(["task_1", "task_2"])
    mock = MockExecutor(behavior={"tool_a": {"status": "success", "result": "ok"}})
    dtm.executor = mock
    summary = dtm.execute_plan(plan)
    assert summary["goal"] == "test_goal"
    assert "results" in summary
    assert summary["results"]["task_1"]["status"] == "success"


def test_execute_plan_skips_when_no_executor_or_tool():
    dtm = DynamicTaskManager()
    # create a plan with a subtask that has no required_tools -> should be skipped
    plan = ExecutionPlan(main_goal="test_goal2")
    st = SubTask(task_id="t1", description="no tool", required_tools=[])
    plan.subtasks.append(st)
    plan.execution_order.append("t1")
    plan.status = "ready"
    summary = dtm.execute_plan(plan)
    assert summary["results"]["t1"]["status"] == "skipped"


def test_priority_with_context():
    dtm = DynamicTaskManager()
    plan = make_plan_with_tasks(["a", "b", "c"])
    # provide context where 'c' is urgent and fast, 'a' is slow/low success
    ctx = {
        "a": {"historical_success_rate": 0.3, "estimated_time": 120.0, "urgency": 0.1},
        "b": {"historical_success_rate": 0.8, "estimated_time": 30.0, "urgency": 0.4},
        "c": {"historical_success_rate": 0.6, "estimated_time": 5.0, "urgency": 0.9},
    }
    scores = dtm.evaluate_priorities(plan, task_context=ctx)
    # c should get the highest normalized score due to high urgency and efficiency
    sorted_tasks = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    assert sorted_tasks[0][0] == "c"
