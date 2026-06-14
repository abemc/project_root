import pytest
import os
from pathlib import Path
from dotenv import load_dotenv

# テスト前に環境変数をロード
load_dotenv()

from src.utils.terminal_executor import run_terminal_command, request_command_fix
from src.utils.path_utils import PROJECT_ROOT

def test_run_terminal_command_success():
    """通常コマンドの実行と出力の検証"""
    res = run_terminal_command("echo HelloTerminal", str(PROJECT_ROOT))
    assert res["status"] == "success"
    assert res["exit_code"] == 0
    assert "HelloTerminal" in res["output"]
    assert res["error_output"] == ""
    assert res["new_cwd"] == str(PROJECT_ROOT)

def test_run_terminal_command_cd_success():
    """cdコマンドによるCWD変更の検証"""
    res = run_terminal_command("cd src", str(PROJECT_ROOT))
    assert res["status"] == "success"
    assert res["exit_code"] == 0
    assert "Directory changed" in res["output"]
    
    target_path = Path(PROJECT_ROOT) / "src"
    assert res["new_cwd"] == str(target_path)

def test_run_terminal_command_cd_failed():
    """存在しないディレクトリへのcd時の挙動の検証"""
    res = run_terminal_command("cd non_existent_dir_123", str(PROJECT_ROOT))
    assert res["status"] == "failed"
    assert res["exit_code"] != 0
    assert "no such file or directory" in res["error_output"]
    assert res["new_cwd"] == str(PROJECT_ROOT)

def test_run_terminal_command_blocked():
    """危険コマンドのブロック検証"""
    res = run_terminal_command("rm -rf src", str(PROJECT_ROOT))
    assert res["status"] == "blocked"
    assert res["exit_code"] == -1
    assert "Prohibited" in res["error_output"] or "Security Block" in res["error_output"]
    assert res["new_cwd"] == str(PROJECT_ROOT)

def test_request_command_fix_mock(monkeypatch):
    """AIコマンド修正のモックテスト"""
    def mock_call_llm(prompt, model, system_prompt, chat_history, temperature, max_tokens):
        return (
            "分析：'gitt' は綴り間違いです。正しくは 'git' です。\n\n"
            "修正コマンド：\n"
            "`git status`"
        )
    
    import src.utils.terminal_executor
    monkeypatch.setattr(src.utils.terminal_executor, "call_llm", mock_call_llm)
    monkeypatch.setattr(src.utils.terminal_executor, "llm_available", True)
    
    res = request_command_fix("gitt status", "gitt: command not found", model_name="dummy-model")
    
    assert res["success"] is True
    assert res["suggested_command"] == "git status"
    assert "綴り間違い" in res["explanation"]
