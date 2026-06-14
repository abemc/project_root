import pytest
import os
from pathlib import Path
from dotenv import load_dotenv

# テスト前に環境変数をロード
load_dotenv()

from src.sandbox.sandbox_executor import SandboxExecutor, SandboxType, ExecutionStatus
from src.utils.self_repair import request_code_repair

def test_execute_python_code_success():
    """正常なPythonコードの実行検証"""
    executor = SandboxExecutor(SandboxType.SUBPROCESS)
    code = (
        "a = 10\n"
        "b = 20\n"
        "print(a + b)\n"
    )
    result = executor.execute_python_code(code)
    
    assert result.status == ExecutionStatus.SUCCESS
    assert result.return_code == 0
    assert result.output.strip() == "30"
    assert result.error_output == ""
    assert result.validation_passed is True

def test_execute_python_code_failed():
    """エラーが発生するPythonコードの実行検証"""
    executor = SandboxExecutor(SandboxType.SUBPROCESS)
    code = (
        "def buggy_func():\n"
        "    return 1 / 0\n"
        "buggy_func()\n"
    )
    result = executor.execute_python_code(code)
    
    assert result.status == ExecutionStatus.FAILED
    assert result.return_code != 0
    assert "ZeroDivisionError" in result.error_output
    assert result.validation_passed is False

def test_execute_python_code_security_blocked():
    """セキュリティブロックされるPythonコードの実行検証"""
    executor = SandboxExecutor(SandboxType.SUBPROCESS)
    # 危険なキーワード 'eval(' が含まれているコード
    code = "eval('1 + 1')\n"
    result = executor.execute_python_code(code)
    
    assert result.status == ExecutionStatus.SECURITY_BLOCKED
    assert result.return_code == -1
    assert "Security Block" in result.error_output
    assert result.validation_passed is False

def test_request_code_repair_mock(monkeypatch):
    """AIコード修復のモックテスト"""
    # call_llmをモックしてLLM実行をテスト
    def mock_call_llm(prompt, model, system_prompt, chat_history, temperature, max_tokens):
        return (
            "分析：0除算によるZeroDivisionErrorが発生しています。分母が0にならないよう修正します。\n\n"
            "修正コード：\n"
            "```python\n"
            "def buggy_func():\n"
            "    denominator = 2 # 0から2に修正\n"
            "    return 1 / denominator\n"
            "buggy_func()\n"
            "```"
        )
    
    import src.utils.self_repair
    monkeypatch.setattr(src.utils.self_repair, "call_llm", mock_call_llm)
    monkeypatch.setattr(src.utils.self_repair, "llm_available", True)
    
    code = (
        "def buggy_func():\n"
        "    return 1 / 0\n"
        "buggy_func()\n"
    )
    error_log = "ZeroDivisionError: division by zero"
    
    repair_res = request_code_repair(code, error_log, model_name="dummy-model")
    
    assert repair_res["success"] is True
    assert "denominator = 2" in repair_res["repaired_code"]
    assert "ZeroDivisionError" in repair_res["explanation"]
