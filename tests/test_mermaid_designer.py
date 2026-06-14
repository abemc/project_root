import pytest
from dotenv import load_dotenv

# テスト前に環境変数をロード
load_dotenv()

from src.utils.mermaid_repair import request_mermaid_modification, request_mermaid_repair

def test_request_mermaid_modification_mock(monkeypatch):
    """日本語指示によるMermaid図面変更のモックテスト"""
    def mock_call_llm(prompt, model, system_prompt, chat_history, temperature, max_tokens):
        return (
            "分析：データベースの前にRedisキャッシュサーバーを追加します。\n\n"
            "修正コード：\n"
            "```mermaid\n"
            "graph TD\n"
            "    A[クライアント] --> B[Webサーバー]\n"
            "    B --> C[Redisキャッシュ]\n"
            "    C --> D[(データベース)]\n"
            "```"
        )
    
    import src.utils.mermaid_repair
    monkeypatch.setattr(src.utils.mermaid_repair, "call_llm", mock_call_llm)
    monkeypatch.setattr(src.utils.mermaid_repair, "llm_available", True)
    
    current_code = (
        "graph TD\n"
        "    A[クライアント] --> B[Webサーバー]\n"
        "    B --> D[(データベース)]\n"
    )
    instruction = "データベースの前にRedisキャッシュを追加して"
    
    res = request_mermaid_modification(current_code, instruction, model_name="dummy-model")
    
    assert res["success"] is True
    assert "Redisキャッシュ" in res["repaired_code"]
    assert "データベース" in res["repaired_code"]
    assert "ZeroDivisionError" not in res["explanation"] # 無関係なものが含まれていないこと

def test_request_mermaid_repair_mock(monkeypatch):
    """Mermaid構文エラー修復のモックテスト"""
    def mock_call_llm(prompt, model, system_prompt, chat_history, temperature, max_tokens):
        return (
            "分析：矢印記法が不正な '->' になっているため、正しい '-->' に修正します。\n\n"
            "修正コード：\n"
            "```mermaid\n"
            "graph TD\n"
            "    A --> B\n"
            "```"
        )
    
    import src.utils.mermaid_repair
    monkeypatch.setattr(src.utils.mermaid_repair, "call_llm", mock_call_llm)
    monkeypatch.setattr(src.utils.mermaid_repair, "llm_available", True)
    
    mermaid_code = "graph TD\n    A -> B\n"
    error_msg = "Parse error on line 2: A -> B"
    
    res = request_mermaid_repair(mermaid_code, error_msg, model_name="dummy-model")
    
    assert res["success"] is True
    assert "A --> B" in res["repaired_code"]
    assert "矢印記法" in res["explanation"]
