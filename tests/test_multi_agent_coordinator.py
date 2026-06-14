"""
Unit & Integration Test: 自律型エージェント能力拡張（第4フェーズ）
役割別マルチエージェントの協調ワークフロー、ディベート、および合意形成の検証
"""

import pytest
from src.agent_architecture.agent_engine import AgentEngine, AutonomyLevel
from src.agent_architecture.multi_agent_coordinator import MultiAgentCoordinator, MultiAgentRole


def test_multi_agent_coordinator_debate_flow():
    """MultiAgentCoordinator 単体でのエージェント間ディベートと合意形成プロセスのテスト"""
    coordinator = MultiAgentCoordinator()

    # 文字列反転タスクでコーディネートを実行（スマートフォールバック発動）
    goal = "与えられた文字列を逆順にする (reverse)"
    result = coordinator.coordinate_task(goal, context={})

    assert result["status"] == "consensus_reached"
    assert result["rounds"] == 1
    assert "agreed_plan" in result
    assert "planner_proposal" in result["agreed_plan"]
    assert "reviewer_verdict" in result["agreed_plan"]
    assert result["agreed_plan"]["reviewer_verdict"] == "APPROVED"

    # メッセージ履歴の検証
    history = coordinator.debate_history
    assert len(history) == 2
    
    # 最初の発信者は PLANNER で、受信者は REVIEWER
    assert history[0].sender == MultiAgentRole.PLANNER
    assert history[0].receiver == MultiAgentRole.REVIEWER
    assert "計画" in history[0].content

    # 2番目の発信者は REVIEWER で、受信者は PLANNER
    assert history[1].sender == MultiAgentRole.REVIEWER
    assert history[1].receiver == MultiAgentRole.PLANNER
    assert "レビュー" in history[1].content or "承認" in history[1].content


def test_agent_engine_multi_agent_delegation():
    """AgentEngine から MultiAgentCoordinator への安全な処理委譲と統合のテスト"""
    engine = AgentEngine(autonomy_level=AutonomyLevel.AUTONOMOUS)

    goal = "安全な手段で文字列を逆順にするタスク (reverse)"
    
    # execute_goal で use_multi_agent=True を指定
    result = engine.execute_goal(goal, context={}, use_multi_agent=True)

    # 協調結果が委譲されて正しく返ってくるかアサート
    assert result["status"] == "consensus_reached"
    assert "debate_history" in result
    assert result["rounds"] >= 1
    assert len(result["debate_history"]) >= 2
