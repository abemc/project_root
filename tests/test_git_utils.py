import pytest
from pathlib import Path
import os

from src.utils.git_utils import (
    get_git_status,
    get_git_diff,
    git_restore,
    get_git_history
)
from src.utils.path_utils import PROJECT_ROOT

def test_git_status_and_history():
    # 履歴が取得できることを確認
    history = get_git_history(limit=3)
    assert isinstance(history, list)
    if history:
        assert "hash" in history[0]
        assert "subject" in history[0]

    # 現在のステータス一覧が取得できることを確認
    status = get_git_status()
    assert isinstance(status, list)


def test_git_untracked_file_flow():
    # 1. 一時的な未追跡ファイルを作成
    test_file_path = "temp_git_test_untracked.txt"
    full_path = PROJECT_ROOT / test_file_path
    
    try:
        full_path.write_text("Hello Git Test", encoding="utf-8")
        
        # 2. ステータスで検出されるか確認
        status = get_git_status()
        found = next((f for f in status if f["path"] == test_file_path), None)
        assert found is not None
        assert found["code"] == "??"

        # 3. Diff が新規ファイルとして取得できるか確認
        diff = get_git_diff(test_file_path)
        assert "+Hello Git Test" in diff

        # 4. リストア（削除）の実行
        res = git_restore(test_file_path)
        assert res["success"] is True
        assert not full_path.exists()

    finally:
        # クリーンアップ
        if full_path.exists():
            full_path.unlink()


def test_git_modified_file_flow():
    # 1. 既存ファイルを一時的に変更（副作用のない README.md を使う）
    target_file = "README.md"
    full_path = PROJECT_ROOT / target_file
    
    if not full_path.exists():
        pytest.skip("README.md does not exist, skipping modified file test")

    original_content = full_path.read_text(encoding="utf-8")
    
    try:
        # 内容を変更
        full_path.write_text(original_content + "\n# GIT_TEST_MODIFICATION\n", encoding="utf-8")
        
        # 2. ステータスで検出されるか確認
        status = get_git_status()
        found = next((f for f in status if f["path"] == target_file), None)
        assert found is not None
        assert "M" in found["code"]

        # 3. Diff で変更行が検出できるか確認
        diff = get_git_diff(target_file)
        assert "+# GIT_TEST_MODIFICATION" in diff

        # 4. リストアで元に戻るか確認
        res = git_restore(target_file)
        assert res["success"] is True
        
        # 内容が完全に戻っているか確認
        restored_content = full_path.read_text(encoding="utf-8")
        assert restored_content == original_content

    finally:
        # 万が一失敗した場合のロールバック
        if full_path.read_text(encoding="utf-8") != original_content:
            full_path.write_text(original_content, encoding="utf-8")
