import subprocess
import os
from pathlib import Path
from typing import List, Dict, Any

from src.utils.path_utils import PROJECT_ROOT

def _run_git_command(args: List[str]) -> subprocess.CompletedProcess:
    """Gitコマンドを実行する共通ヘルパー。"""
    # Dockerコンテナ内の安全なディレクトリ設定を念のため行う
    try:
        subprocess.run(
            ["git", "config", "--global", "--add", "safe.directory", "/app"],
            capture_output=True,
            text=True,
            timeout=5
        )
    except Exception:
        pass

    return subprocess.run(
        args,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=10
    )

def get_git_status() -> List[Dict[str, str]]:
    """
    リポジトリ内の変更状態を取得する。
    戻り値: [{"path": "app.py", "status": "Modified", "code": "M"}, ...]
    """
    res = _run_git_command(["git", "status", "--porcelain"])
    if res.returncode != 0:
        return []

    status_map = {
        "M": "Modified (変更)",
        "A": "Added (追加)",
        "D": "Deleted (削除)",
        "R": "Renamed (改名)",
        "??": "Untracked (未追跡)",
        "C": "Copied (コピー)",
        "U": "Updated but unmerged (未マージ)",
    }

    results = []
    for line in res.stdout.splitlines():
        if len(line) < 4:
            continue
        # インデックス状態とワークツリー状態
        code = line[:2].strip()
        file_path = line[3:].strip()
        
        # リネームやコピー時のファイル名処理 (例: old -> new)
        if " -> " in file_path:
            file_path = file_path.split(" -> ")[-1].strip()

        # クォートされている場合のクォート解除 (例: "logs/test.log")
        if file_path.startswith('"') and file_path.endswith('"'):
            file_path = file_path[1:-1]

        status_name = status_map.get(code, f"Unknown ({code})")
        results.append({
            "path": file_path,
            "status": status_name,
            "code": code
        })
    return results

def get_git_diff(file_path: str) -> str:
    """
    指定ファイルのHEADからの差分（Diff）を取得する。
    """
    # ファイルの状態をチェック
    status_list = get_git_status()
    file_status = next((f for f in status_list if f["path"] == file_path), None)
    
    if not file_status:
        return "変更はありません。"

    # 未追跡ファイルの場合は、新規ファイルとして全体を表示
    if file_status["code"] == "??":
        full_path = PROJECT_ROOT / file_path
        if not full_path.exists():
            return "ファイルが見つかりません。"
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            # 全行に '+' を付与してDiff風にする
            diff_lines = [f"+{line}" for line in content.splitlines()]
            return f"--- /dev/null\n+++ b/{file_path}\n@@ -0,0 +1,{len(diff_lines)} @@\n" + "\n".join(diff_lines)
        except Exception as e:
            return f"新規ファイルの読み込みに失敗しました: {e}"

    # 削除されたファイルの場合
    if "D" in file_status["code"]:
        return f"ファイル '{file_path}' は削除されています。"

    # 通常の変更ファイルの場合は git diff を実行
    res = _run_git_command(["git", "--no-pager", "diff", "HEAD", "--", file_path])
    if res.returncode != 0:
        return f"Diffの取得に失敗しました: {res.stderr}"
    
    return res.stdout

def git_add_and_commit(file_paths: List[str], message: str) -> Dict[str, Any]:
    """
    指定されたファイルをステージングし、コミットを実行する。
    """
    if not file_paths:
        return {"success": False, "error": "コミット対象のファイルが選択されていません。"}
    if not message.strip():
        return {"success": False, "error": "コミットメッセージを入力してください。"}

    # 1. 各ファイルをステージング (git add)
    for path in file_paths:
        # 削除されたファイルの場合は git rm
        full_path = PROJECT_ROOT / path
        if not full_path.exists():
            res_add = _run_git_command(["git", "rm", "--cached", path])
        else:
            res_add = _run_git_command(["git", "add", path])
            
        if res_add.returncode != 0:
            return {"success": False, "error": f"ファイルの追加に失敗しました ({path}): {res_add.stderr}"}

    # 2. コミットを実行
    res_commit = _run_git_command(["git", "commit", "-m", message])
    if res_commit.returncode != 0:
        # コミット競合やエラー
        return {"success": False, "error": f"コミットに失敗しました: {res_commit.stderr}"}

    # 3. 最新のコミットハッシュを取得
    res_hash = _run_git_command(["git", "rev-parse", "--short", "HEAD"])
    commit_hash = res_hash.stdout.strip() if res_hash.returncode == 0 else "unknown"

    return {
        "success": True,
        "commit_hash": commit_hash,
        "stdout": res_commit.stdout
    }

def git_restore(file_path: str) -> Dict[str, Any]:
    """
    ファイルの変更を破棄して元に戻す。
    """
    status_list = get_git_status()
    file_status = next((f for f in status_list if f["path"] == file_path), None)
    
    if not file_status:
        return {"success": False, "error": "変更されていないファイルです。"}

    # 未追跡ファイルの場合は物理削除
    if file_status["code"] == "??":
        full_path = PROJECT_ROOT / file_path
        try:
            if full_path.is_dir():
                import shutil
                shutil.rmtree(full_path)
            elif full_path.exists():
                full_path.unlink()
            return {"success": True, "info": f"未追跡ファイル '{file_path}' を削除しました。"}
        except Exception as e:
            return {"success": False, "error": f"ファイルの削除に失敗しました: {e}"}

    # 既存ファイルの変更の場合は git restore を実行
    res = _run_git_command(["git", "checkout", "HEAD", "--", file_path])
    if res.returncode != 0:
        # git restore にフォールバック
        res = _run_git_command(["git", "restore", file_path])
        
    if res.returncode != 0:
        return {"success": False, "error": f"変更の破棄に失敗しました: {res.stderr}"}
        
    return {"success": True}

def get_git_history(limit: int = 5) -> List[Dict[str, str]]:
    """
    直近のコミット履歴を取得する。
    """
    res = _run_git_command([
        "git", "log", f"-n{limit}", 
        "--pretty=format:%h|%an|%ad|%s", 
        "--date=short"
    ])
    if res.returncode != 0:
        return []

    history = []
    for line in res.stdout.splitlines():
        parts = line.split("|", 3)
        if len(parts) < 4:
            continue
        history.append({
            "hash": parts[0],
            "author": parts[1],
            "date": parts[2],
            "subject": parts[3]
        })
    return history
