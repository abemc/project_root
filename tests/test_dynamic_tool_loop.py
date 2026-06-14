"""
Integration Test: 自律型エージェント能力拡張（第1フェーズ）
ツールの動的自己生成、ASTセキュリティ検証、サンドボックス内テスト、および動的登録の検証
"""

import os
import pytest
from src.agent_architecture.agent_engine import AgentEngine, AutonomyLevel
from src.self_improvement.tool_creator import ToolCreator


def test_dynamic_tool_creation_and_registration():
    """動的ツールの自動生成、テスト、登録、および実行の統合テスト"""
    # エージェントエンジンを完全自律モードで起動
    engine = AgentEngine(autonomy_level=AutonomyLevel.AUTONOMOUS)

    # 1. ツール生成リクエスト（スマートフォールバックで 'reverse' キーワードを含む要求を渡す）
    requirement = "与えられた文字列を逆順にする単純なツール (reverse)"
    success, result_msg = engine.create_and_register_dynamic_tool(requirement)

    assert success is True, f"Dynamic tool creation failed: {result_msg}"
    assert result_msg == "reverse_string"

    # 2. 登録されたツールが Executor に含まれているか確認
    assert "reverse_string" in engine.executor.tools

    # 3. 実際に登録されたツールを実行して動作確認
    params = {"text": "autonomous_agent"}
    execution_result = engine.executor.execute_tool("reverse_string", params)

    assert execution_result.status == "success"
    assert execution_result.result == "tnega_suomonotua"


def test_ast_security_validation():
    """ASTによる静的セキュリティバリデーションの動作確認"""
    creator = ToolCreator()

    # 安全なコードの検証
    safe_code = (
        "def safe_add(a: int, b: int) -> int:\n"
        "    return a + b\n"
    )
    is_safe, error_msg = creator.validate_code_safety(safe_code)
    assert is_safe is True
    assert error_msg == ""

    # 危険なインポートの検証 (os モジュール)
    unsafe_import_code = (
        "import os\n"
        "def unsafe_func(path: str):\n"
        "    return os.listdir(path)\n"
    )
    is_safe, error_msg = creator.validate_code_safety(unsafe_import_code)
    assert is_safe is False
    assert "インポートは禁止" in error_msg

    # 危険な関数呼び出しの検証 (eval)
    unsafe_eval_code = (
        "def dynamic_eval(expr: str):\n"
        "    return eval(expr)\n"
    )
    is_safe, error_msg = creator.validate_code_safety(unsafe_eval_code)
    assert is_safe is False
    assert "危険な関数 'eval' の呼び出しは禁止" in error_msg


def test_dynamic_tool_loader_unload():
    """動的ツールのクリーンアップ（アンロード）のテスト"""
    engine = AgentEngine(autonomy_level=AutonomyLevel.AUTONOMOUS)

    requirement = "文字列を逆順にする (reverse)"
    success, tool_name = engine.create_and_register_dynamic_tool(requirement)

    assert success is True
    assert tool_name in engine.executor.tools

    # アンロードを実行
    unload_success = engine.dynamic_tool_loader.unload_tool(tool_name)
    assert unload_success is True

    # sys.modules やキャッシュから消去されているか確認
    import sys
    assert f"dynamic_tool_{tool_name}" not in sys.modules
    assert tool_name not in engine.dynamic_tool_loader.loaded_modules
