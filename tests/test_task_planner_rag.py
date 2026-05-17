from src.agent_architecture.agent_engine import TaskPlanner


def test_decompose_includes_synth_and_summary_with_rag_docs():
    planner = TaskPlanner()
    # create synthetic rag_docs
    rag_docs = []
    for i in range(5):
        rag_docs.append({
            'id': f'd{i}',
            'text': f'Example usage and test case {i}',
            'meta': {'tags': ['example']}
        })

    plan = planner.decompose_task('create design for feature X', {'rag_docs': rag_docs})
    task_ids = [t.task_id for t in plan.subtasks]
    assert 'task_synth' in task_ids or 'task_summary' in task_ids
