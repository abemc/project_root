import re
import logging
from typing import Dict, Any, Optional

try:
    from src.rag.llm import call_llm
    llm_available = True
except ImportError:
    call_llm = None
    llm_available = False

logger = logging.getLogger(__name__)

def request_code_repair(
    code_text: str,
    error_log: str,
    model_name: str = "qwen2.5-coder:7b",
) -> Dict[str, Any]:
    """
    LLMを利用して、エラーが発生したPythonコードのデバッグと自動修正を要求します。
    
    Args:
        code_text: エラーが発生した元のPythonコード
        error_log: 実行時の標準エラー出力（Tracebackなど）
        model_name: 使用するLLMモデル名
        
    Returns:
        Dict: {"success": bool, "repaired_code": str, "explanation": str, "error": Optional[str]}
    """
    if not llm_available or not call_llm:
        return {
            "success": False,
            "repaired_code": "",
            "explanation": "LLMモジュールが利用できないため、自動修復を実行できません。",
            "error": "LLM module not available"
        }
        
    system_prompt = (
        "あなたは優秀なPythonデバッグアシスタントです。\n"
        "提示されたプログラムのバグを分析し、修正した完全なプログラムと、原因の解説を日本語で提供してください。\n"
        "回答には必ず修正後のPythonコード全体を ```python ... ``` ブロックで囲んで含めてください。"
    )
    
    prompt = f"""
以下のPythonコードを実行したところ、エラーが発生しました。
エラーの原因を分析し、バグを修正した完全なプログラムコードを提案してください。

### エラーが発生したコード:
```python
{code_text}
```

### エラーログ (標準エラー出力):
```
{error_log}
```

### 期待する回答形式:
1. 原因の簡潔な解説 (日本語)
2. 修正した完全なPythonプログラムコード (```python ... ``` の中に全体を記述)
"""
    
    try:
        # call_llm の呼び出し
        response = call_llm(
            prompt=prompt,
            model=model_name,
            system_prompt=system_prompt,
            chat_history=None,
            temperature=0.2,
            max_tokens=2048
        )
        
        if not response or response.startswith("Error"):
            return {
                "success": False,
                "repaired_code": "",
                "explanation": f"LLMからの応答取得に失敗しました: {response}",
                "error": "LLM execution failed"
            }
            
        # レスポンスから ```python ... ``` 形式のコードブロックを抽出
        code_match = re.search(r"```python\s*\n(.*?)```", response, re.DOTALL | re.IGNORECASE)
        repaired_code = ""
        explanation = response
        
        if code_match:
            repaired_code = code_match.group(1).strip()
            # コードブロック部分を削って解説を綺麗に取り出す
            explanation = re.sub(r"```python\s*\n.*?```", "", response, flags=re.DOTALL | re.IGNORECASE).strip()
        else:
            # フォールバック: ``` で囲まれているだけのブロックを探す
            fallback_match = re.search(r"```\s*\n(.*?)```", response, re.DOTALL)
            if fallback_match:
                repaired_code = fallback_match.group(1).strip()
                explanation = re.sub(r"```\s*\n.*?```", "", response, flags=re.DOTALL).strip()
                
        # もしコードブロックが抽出できなかった場合は、元のコードをセット
        if not repaired_code:
            logger.warning("Failed to extract code block from LLM response")
            # 解説部分のみとする
            explanation = response
            
        return {
            "success": True,
            "repaired_code": repaired_code,
            "explanation": explanation,
            "error": None
        }
        
    except Exception as e:
        logger.exception("Exception during code repair request")
        return {
            "success": False,
            "repaired_code": "",
            "explanation": f"エラー修復の生成中に例外が発生しました: {e}",
            "error": str(e)
        }
