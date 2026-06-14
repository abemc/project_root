import os
import re
import shlex
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

from src.sandbox.sandbox_executor import SandboxExecutor, SandboxType, SandboxResult, ExecutionStatus, ExecutionPolicy
from src.utils.path_utils import PROJECT_ROOT

try:
    from src.rag.llm import call_llm
    llm_available = True
except ImportError:
    call_llm = None
    llm_available = False

logger = logging.getLogger(__name__)

def run_terminal_command(
    command_str: str,
    current_cwd: str,
    timeout_seconds: float = 15.0,
) -> Dict[str, Any]:
    """
    ディレクトリの移動状態（CWD）を維持しながら、安全にコマンドを実行します。
    
    Args:
        command_str: 実行コマンド文字列 (例: 'ls -la', 'cd src')
        current_cwd: 現在の作業ディレクトリパス
        timeout_seconds: タイムアウト（秒）
        
    Returns:
        Dict: {
            "output": str,        # 標準出力
            "error_output": str,  # 標準エラー出力
            "exit_code": int,     # 終了コード
            "new_cwd": str,       # 移動後の新しい作業ディレクトリ
            "status": str,        # 実行ステータス (success, failed, blocked, timeout)
        }
    """
    cmd_stripped = command_str.strip()
    if not cmd_stripped:
        return {
            "output": "",
            "error_output": "",
            "exit_code": 0,
            "new_cwd": current_cwd,
            "status": "success"
        }
        
    # カレントディレクトリの絶対パス解決
    cwd_path = Path(current_cwd).resolve()
    if not cwd_path.exists() or not cwd_path.is_dir():
        cwd_path = PROJECT_ROOT
        
    # 1. cd コマンドの仮想的な処理
    if cmd_stripped.startswith("cd ") or cmd_stripped == "cd":
        parts = cmd_stripped.split(maxsplit=1)
        target_dir = parts[1].strip() if len(parts) > 1 else ""
        
        # cd 単体、または cd ~ はホームディレクトリ（またはプロジェクトルート）へ
        if not target_dir or target_dir == "~":
            new_path = PROJECT_ROOT
        else:
            # 相対パスまたは絶対パスの解決
            new_path = (cwd_path / target_dir).resolve()
            
        # パスが存在し、かつディレクトリかチェック
        if new_path.exists() and new_path.is_dir():
            # プロジェクトルート外への移動を制限するか？ (簡易保護)
            # 安全のため、PROJECT_ROOTの配下、あるいは環境制限に従う
            if PROJECT_ROOT in new_path.parents or new_path == PROJECT_ROOT or new_path.parts[1] == 'home' or new_path.parts[1] == 'app':
                return {
                    "output": f"Directory changed to: {new_path.relative_to(PROJECT_ROOT) if PROJECT_ROOT in new_path.parents else new_path}",
                    "error_output": "",
                    "exit_code": 0,
                    "new_cwd": str(new_path),
                    "status": "success"
                }
            else:
                return {
                    "output": "",
                    "error_output": f"Access Denied: Cannot navigate outside authorized workspace area: '{new_path}'",
                    "exit_code": 1,
                    "new_cwd": str(cwd_path),
                    "status": "failed"
                }
        else:
            return {
                "output": "",
                "error_output": f"cd: no such file or directory: {target_dir}",
                "exit_code": 1,
                "new_cwd": str(cwd_path),
                "status": "failed"
            }
            
    # 2. cd 以外の通常コマンドは SandboxExecutor で指定ディレクトリ実行
    executor = SandboxExecutor(SandboxType.SUBPROCESS)
    policy = ExecutionPolicy(timeout_seconds=timeout_seconds, allow_filesystem_write=True)
    
    # 危険なOSコマンドの事前拒否 (簡易セキュリティガード)
    try:
        parts = shlex.split(cmd_stripped)
    except ValueError:
        parts = cmd_stripped.split()
    primary_cmd = parts[0] if parts else ""
    dangerous_commands = ["rm", "dd", "mkfs", "chmod", "chown", "sudo", "reboot", "shutdown"]
    if primary_cmd in dangerous_commands:
        return {
            "output": "",
            "error_output": f"Security Block: Command '{primary_cmd}' is prohibited for safety reasons.",
            "exit_code": -1,
            "new_cwd": str(cwd_path),
            "status": "blocked"
        }
        
    try:
        # subprocess で実行
        # args は primary_cmd 以外の引数
        args = parts[1:] if len(parts) > 1 else None
        
        # 実際にコマンドを実行
        result = executor.execute_in_sandbox(
            command=primary_cmd,
            args=args,
            policy=policy,
            working_dir=str(cwd_path)
        )
        
        status_str = "success"
        if result.status == ExecutionStatus.TIMEOUT:
            status_str = "timeout"
        elif result.status == ExecutionStatus.SECURITY_BLOCKED:
            status_str = "blocked"
        elif result.status == ExecutionStatus.FAILED:
            status_str = "failed"
            
        return {
            "output": result.output,
            "error_output": result.error_output,
            "exit_code": result.return_code,
            "new_cwd": str(cwd_path),
            "status": status_str
        }
        
    except Exception as e:
        logger.exception(f"Command execution exception: {e}")
        return {
            "output": "",
            "error_output": str(e),
            "exit_code": -1,
            "new_cwd": str(cwd_path),
            "status": "failed"
        }

def request_command_fix(
    command: str,
    error_msg: str,
    model_name: str = "qwen2.5-coder:7b",
) -> Dict[str, Any]:
    """
    エラーが発生したOSコマンドのトラブルシューティングと正しい修正コマンドの提案をLLMに要求します。
    
    Args:
        command: 失敗したコマンド
        error_msg: エラー出力
        model_name: LLMモデル名
        
    Returns:
        Dict: {"success": bool, "suggested_command": str, "explanation": str, "error": Optional[str]}
    """
    if not llm_available or not call_llm:
        return {
            "success": False,
            "suggested_command": "",
            "explanation": "LLMモジュールが利用できないため、コマンドの自動修正を行えません。",
            "error": "LLM module not available"
        }
        
    system_prompt = (
        "あなたは優秀なLinuxシステム管理者兼AIアシスタントです。\n"
        "実行に失敗したOSコマンドとエラーメッセージを分析し、原因の解説と、実行すべき正しい修正コマンドを提案してください。\n"
        "回答には必ず修正コマンド自体を単一バッククォート（`command`）もしくはコードブロックで含めてください。"
    )
    
    prompt = f"""
以下のシェルコマンドを実行したところ、エラーが発生しました。
エラー原因を解説し、代わりに実行すべき正しいコマンドを提案してください。

### 実行に失敗したコマンド:
`{command}`

### エラーログ (標準エラー出力):
```
{error_msg}
```

### 期待する回答形式:
1. なぜエラーが起きたかの簡潔な解説 (日本語)
2. 代わりに実行すべき正しいコマンド例 (必ず `修正コマンド` のようにバッククォートまたはコードブロックで囲んで提示すること)
"""
    
    try:
        response = call_llm(
            prompt=prompt,
            model=model_name,
            system_prompt=system_prompt,
            chat_history=None,
            temperature=0.2,
            max_tokens=1024
        )
        
        if not response or response.startswith("Error"):
            return {
                "success": False,
                "suggested_command": "",
                "explanation": f"LLMからの応答取得に失敗しました: {response}",
                "error": "LLM execution failed"
            }
            
        # バッククォート `...` 内のコマンド、またはコードブロック内のコマンドを抽出
        cmd_match = re.search(r"`(.*?)`", response)
        suggested_command = ""
        explanation = response
        
        # 応答の中で、失敗した元のコマンドと異なるバッククォート内の文字列を探す
        if cmd_match:
            # 応答内のすべてのバッククォートペアを探して検証
            candidates = re.findall(r"`(.*?)`", response)
            for cand in candidates:
                cand_clean = cand.strip()
                # 失敗した元のコマンドと同一でなく、かつ短すぎない実用コマンド候補
                if cand_clean != command and len(cand_clean) > 2 and primary_cmd_in_str(cand_clean):
                    suggested_command = cand_clean
                    break
        
        # コードブロックからのフォールバック抽出
        if not suggested_command:
            block_match = re.search(r"```(?:bash|sh)?\s*\n(.*?)```", response, re.DOTALL | re.IGNORECASE)
            if block_match:
                suggested_command = block_match.group(1).strip()
                
        # 抽出したコマンドをクリーンアップ
        if suggested_command:
            # 改行が含まれる場合は最初の行だけを取り出す
            suggested_command = suggested_command.split("\n")[0].strip()
            
        return {
            "success": True,
            "suggested_command": suggested_command,
            "explanation": explanation,
            "error": None
        }
        
    except Exception as e:
        logger.exception("Exception during command fix request")
        return {
            "success": False,
            "suggested_command": "",
            "explanation": f"コマンド修正の生成中に例外が発生しました: {e}",
            "error": str(e)
        }

def primary_cmd_in_str(cmd_str: str) -> bool:
    """文字列が実行コマンド風であるかを簡易判定（単なる英単語除外用）"""
    common_cmds = ["ls", "pwd", "cd", "git", "python", "pip", "cat", "grep", "echo", "mkdir", "touch", "find", "curl", "wget"]
    parts = cmd_str.split()
    if not parts:
        return False
    primary = parts[0].lower()
    return primary in common_cmds or any(char in cmd_str for char in ["/", "-", ".", " "])
