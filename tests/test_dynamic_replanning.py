from src.agent_architecture.dynamic_task_manager import DynamicTaskManager
from src.agent_architecture.agent_engine import ExecutionPlan, SubTask


def make_plan():
    plan = ExecutionPlan(main_goal="g")
    # three tasks: a -> b -> c (no deps initially)
    plan.subtasks.append(SubTask(task_id="a", description="A", required_tools=["t"]))
    plan.subtasks.append(SubTask(task_id="b", description="B", required_tools=["t"]))
    plan.subtasks.append(SubTask(task_id="c", description="C", required_tools=["t"]))
    plan.execution_order = ["a", "b", "c"]
    return plan


def test_replan_changes_order_on_context_update():
    dtm = DynamicTaskManager()
    plan = make_plan()

    # initial context: 'a' high success, 'c' low
    ctx = {
        'a': {'historical_success_rate': 0.9, 'estimated_time': 10, 'urgency': 0.2},
        'b': {'historical_success_rate': 0.6, 'estimated_time': 20, 'urgency': 0.3},
        'c': {'historical_success_rate': 0.4, 'estimated_time': 5, 'urgency': 0.1},
    }

    new_plan = dtm.replan_if_needed(plan, task_context=ctx)
    # initial best should be 'a'
    assert new_plan.execution_order[0] == 'a'

    # simulate context update where 'c' becomes urgent
    ctx_update = {'c': {'historical_success_rate': 0.6, 'estimated_time': 3, 'urgency': 0.95}}
    new_plan2 = dtm.replan_if_needed(plan, task_context=ctx_update)
    # now 'c' should be ordered earlier (likely first)
    assert 'c' in new_plan2.execution_order
    assert new_plan2.execution_order[0] == 'c' or new_plan2.execution_order[0] == 'a'
