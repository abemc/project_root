"""
Unit & Integration Test: 自律型エージェント能力拡張（第2フェーズ）
能動的 HITL (Human-in-the-Loop) と曖昧さ解消プロセスの検証
"""

import pytest
from src.agent_architecture.agent_engine import AgentEngine, AutonomyLevel
from src.feedback.interactive_clarifier import InteractiveClarifier


def test_interactive_clarifier_logic():
    """InteractiveClarifier単体の判定および生成ロジックのテスト"""
    clarifier = InteractiveClarifier()

    # 1. 確信度が十分に高い場合は、ユーザー確認不要 (False)
    assert clarifier.should_clarify("単純な文字列反転", confidence_score=0.9) is False

    # 2. 確信度が低い（しきい値0.6未満）の場合は、確認必要 (True)
    assert clarifier.should_clarify("複雑なデータ変換タスク", confidence_score=0.4) is True

    # 3. 確信度は高くても、曖昧な指示を含む場合は確認必要 (True)
    assert clarifier.should_clarify("いい感じに文字列を逆順にしてください", confidence_score=0.95) is True

    # 4. 質問および選択肢の生成テスト
    clarification_data = clarifier.generate_clarification_options("文字列を逆順にする", context={})
    assert "question" in clarification_data
    assert "options" in clarification_data
    assert len(clarification_data["options"]) >= 2
    assert clarification_data["options"][0]["key"] == "A"


def test_agent_engine_hitl_suspension_and_resolution():
    """AgentEngine における曖昧タスクの一時サスペンドと、回答反映による実行再開テスト"""
    # 完全自律モードではなく、SEMI_AUTONOMOUS モードで起動
    engine = AgentEngine(autonomy_level=AutonomyLevel.SEMI_AUTONOMOUS)

    goal = "与えられた文字列を逆順にする (reverse)"
    # 確信度が低い (0.3) コンテキストを設定
    low_confidence_context = {"confidence": 0.3}

    # 1. 初回の実行開始 -> 確信度が低いため一時中断されるはず
    result = engine.execute_goal(goal, low_confidence_context)

    assert result["status"] == "pending_clarification"
    assert "clarification" in result
    clarification_data = result["clarification"]
    assert "question" in clarification_data
    
    question = clarification_data["question"]
    options = clarification_data["options"]

    # 2. ユーザーが「A案（すべての文字をそのまま逆順にする）」を選択したとシミュレート
    user_selection = options[0]
    additional_msg = "小文字で出力してください。"

    # コンテキストに回答を反映
    resolved_context = engine.clarifier.apply_user_response(
        context=result["context"],
        question=question,
        selected_key=user_selection["key"],
        selected_description=user_selection["description"],
        additional_text=additional_msg
    )

    # 解決済み情報が反映されているか確認
    assert "clarification_resolutions" in resolved_context
    assert resolved_context["clarification_resolutions"][0]["selected_key"] == "A"
    assert "user_instruction_addition" in resolved_context
    assert "小文字で出力してください" in resolved_context["user_instruction_addition"]

    # 3. 回答反映後のコンテキストを渡して再度実行 -> 今度はサスペンドせずにテストの実行まで進むはず
    # （第1フェーズで登録した 'reverse_string' ツールが正常に呼び出される）
    final_result = engine.execute_goal(goal, resolved_context)

    # テストが最後まで実行（完了または一部失敗）することを確認
    assert final_result["status"] in ("completed", "partial_failure")
    assert "results" in final_result
