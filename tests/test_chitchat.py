import pytest
from src.utils.text_utils import _is_chitchat_query

def test_is_chitchat_query_true():
    """挨拶や自己紹介、感謝、名前の問いかけなどを正しく雑談クエリと判定するか検証"""
    chitchat_queries = [
        "こんにちは",
        "おはようございます！",
        "はじめまして、どうぞよろしく",
        "あなたのお名前は？",
        "自己紹介をしてください",
        "名前を教えて",
        "ありがとう！",
        "お疲れ様でした",
        "元気ですか？",
        "hello, who are you?",
        "what is your name?",
        "Good morning",
    ]
    for q in chitchat_queries:
        assert _is_chitchat_query(q) is True, f"Failed for query: {q}"

def test_is_chitchat_query_false():
    """RAGが必要な事実・語源などの質問は雑談クエリと判定されないことを検証"""
    factual_queries = [
        "RAGの仕組みについて教えてください",
        "挨拶の語源は何ですか？",
        "マンドラの定義を説明して",
        "名前の由来を調べる",
        "こんにちはという言葉の歴史",
    ]
    for q in factual_queries:
        assert _is_chitchat_query(q) is False, f"Failed for query: {q}"
