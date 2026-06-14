import os
from pathlib import Path
import pytest
from src.utils.path_utils import PROJECT_ROOT
from src.ui.code_interpreter_page import is_safe_path, read_interpreter_file, write_interpreter_file

def test_is_safe_path():
    # プロジェクトルート直下は安全
    safe_file = PROJECT_ROOT / "temp_test_safe.py"
    assert is_safe_path(str(safe_file)) == True
    
    # プロジェクトルート内サブフォルダも安全
    safe_sub_file = PROJECT_ROOT / "src" / "ui" / "temp_test_safe.py"
    assert is_safe_path(str(safe_sub_file)) == True
    
    # システム領域などは危険（ブロックされるべき）
    unsafe_file1 = "/etc/passwd"
    unsafe_file2 = "/tmp/outside_file.py"
    assert is_safe_path(unsafe_file1) == False
    assert is_safe_path(unsafe_file2) == False

def test_write_and_read_interpreter_file():
    test_file_path = PROJECT_ROOT / "temp_test_interpreter_io.py"
    test_content = "print('Hello from Code Interpreter File Ops Test!')\n"
    
    try:
        # 1. 正常な書き込み
        success, msg = write_interpreter_file(str(test_file_path), test_content)
        assert success == True
        assert "success" in msg.lower()
        
        # 2. 正常な読み込み
        success, content = read_interpreter_file(str(test_file_path))
        assert success == True
        assert content == test_content
        
        # 3. 範囲外への書き込みブロック
        unsafe_path = "/etc/test_danger.py"
        success_write, msg_write = write_interpreter_file(unsafe_path, test_content)
        assert success_write == False
        assert "access denied" in msg_write.lower()
        
        # 4. 範囲外からの読み込みブロック
        success_read, msg_read = read_interpreter_file("/etc/passwd")
        assert success_read == False
        assert "access denied" in msg_read.lower()
        
        # 5. 存在しないファイルのエラー
        success_nonexist, msg_nonexist = read_interpreter_file(str(PROJECT_ROOT / "non_existing_file_xyz.py"))
        assert success_nonexist == False
        assert "exist" in msg_nonexist.lower()
        
    finally:
        # クリーンアップ
        if test_file_path.exists():
            test_file_path.unlink()
