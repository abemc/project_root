from src.agent_architecture.agent_engine import AgentEngine, AutonomyLevel
from src.agent_architecture.agent_engine import Tool, ToolType


def test_agent_engine_execute_goal_with_dtm():
    agent = AgentEngine(AutonomyLevel.SEMI_AUTONOMOUS)

    # register a mock tool
    def mock_tool():
        return {"status": "success", "result": "ok"}

    tool = Tool(
        name="test_tool",
        tool_type=ToolType.REASONING,
        description="Test tool",
        execute_fn=mock_tool,
    )

    agent.executor.register_tool(tool)

    result = agent.execute_goal("search for information", {"available_tools": ["test_tool"]}, use_dynamic_manager=True)

    assert result["goal"] == "search for information"
    assert "execution_plan" in result
    assert "execution_order" in result["execution_plan"]
