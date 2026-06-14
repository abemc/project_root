"""
Unit & Integration Test: 自律型エージェント能力拡張（第3フェーズ）
長期エピソード記憶の要約、圧縮、およびガベージコレクションの検証
"""

import os
import shutil
import json
import pytest
from pathlib import Path
from src.memory.episodic_memory import EpisodicMemory
from src.memory.memory_compressor import MemoryCompressor


@pytest.fixture
def temp_storage():
    """テスト用の一時記憶ディレクトリを提供するフィクスチャ"""
    temp_dir = Path("tests") / "temp_memory"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    yield temp_dir
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


def test_memory_compression_lifecycle(temp_storage):
    """長期記憶の圧縮、古い重複のGC、ルールの抽出のライフサイクル統合テスト"""
    memory = EpisodicMemory(storage_dir=temp_storage)

    # 1. 重複を含む多数のエピソード（生ログ）を登録する（閾値5件を超えるように8件登録）
    episodes = [
        {"trigger": "reverse string", "query": "reverse string", "action": "reverse_string", "result": "success", "resolution": "reversed correctly 1"},
        {"trigger": "reverse string", "query": "reverse string", "action": "reverse_string", "result": "success", "resolution": "reversed correctly 2"},
        {"trigger": "reverse string", "query": "reverse string", "action": "reverse_string", "result": "success", "resolution": "reversed correctly 3"},
        {"trigger": "reverse string", "query": "reverse string", "action": "reverse_string", "result": "success", "resolution": "reversed correctly 4"},
        {"trigger": "reverse string", "query": "reverse string", "action": "reverse_string", "result": "success", "resolution": "reversed correctly 5"},
        {"trigger": "unrelated task", "query": "unrelated task", "action": "unrelated_action", "result": "success", "resolution": "unrelated resolved"},
        {"trigger": "reverse string", "query": "reverse string", "action": "reverse_string", "result": "success", "resolution": "latest reversed correctly 1"},
        {"trigger": "reverse string", "query": "reverse string", "action": "reverse_string", "result": "success", "resolution": "latest reversed correctly 2"}
    ]

    for ep in episodes:
        memory.store_episode(ep)

    # ロード件数を確認 (計8件)
    assert len(memory.episodes) == 8

    # 2. 圧縮（GC ＆ 一般化ルールの抽出）を実行
    compressor = MemoryCompressor()
    stats = memory.compress_memory(compressor)

    # 3. 圧縮の統計情報をアサート
    assert stats["original_count"] == 8
    assert stats["pruned_count"] > 0
    assert stats["remaining_count"] < 8
    assert stats["extracted_rules_count"] >= 1
    assert stats["compression_ratio"] > 0.0

    # 4. ファイル上書き保存の検証（再ロードして確認）
    reloaded_memory = EpisodicMemory(storage_dir=temp_storage)
    assert len(reloaded_memory.episodes) == stats["remaining_count"]

    # 5. 一般化ルールファイル (rules.jsonl) が生成されているか検証
    rules_file_path = temp_storage / 'rules.jsonl'
    assert rules_file_path.exists() is True

    rules = []
    with open(rules_file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                rules.append(json.loads(line))

    assert len(rules) >= 1
    assert "reverse_string" in rules[0]["rule"] or "Consistently" in rules[0]["rule"]
    assert rules[0]["confidence"] >= 0.8


def test_empty_memory_compression(temp_storage):
    """メモリが空の場合の安全動作テスト"""
    memory = EpisodicMemory(storage_dir=temp_storage)
    stats = memory.compress_memory()

    assert stats["original_count"] == 0
    assert stats["pruned_count"] == 0
    assert stats["compression_ratio"] == 0.0
