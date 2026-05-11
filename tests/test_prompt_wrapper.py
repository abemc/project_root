from analyzer.prompt_wrapper import build_confirmation_prompt


def test_build_confirmation_prompt_basic():
    msg = "ファイルを削除してください"
    p = build_confirmation_prompt(msg)
    assert "復唱:" in p
    assert "確認:" in p
    assert "回答:" in p
    assert msg in p


def test_build_confirmation_with_context():
    ctx = [
        {"role": "user", "text": "先にログを出力して"},
        {"role": "assistant", "text": "ログ出力します。"},
    ]
    p = build_confirmation_prompt("最新のログを見せて", context=ctx)
    assert "（関連コンテキスト）" in p
    assert "先にログを出力して" in p
