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

def request_mermaid_modification(
    current_code: str,
    user_instruction: str,
    model_name: str = "qwen2.5-coder:7b",
) -> Dict[str, Any]:
    """
    ユーザーの日本語指示に基づいて、現在のMermaidコードを修正します。
    
    Args:
        current_code: 修正前のMermaidコード
        user_instruction: ユーザーの日本語修正指示（例：「DBの前にキャッシュを追加して」）
        model_name: 使用するLLMモデル名
        
    Returns:
        Dict: {"success": bool, "repaired_code": str, "explanation": str, "error": Optional[str]}
    """
    if not llm_available or not call_llm:
        return {
            "success": False,
            "repaired_code": "",
            "explanation": "LLMモジュールが利用できないため、ダイアグラムの自動編集を実行できません。",
            "error": "LLM module not available"
        }
        
    system_prompt = (
        "あなたは優秀なシステム設計およびMermaid図解のエキスパートです。\n"
        "提示されたMermaidコードを、ユーザーの日本語指示に従って適切に書き換え、修正後の完全なコードと解説を提供してください。\n"
        "回答には必ず修正後の完全なMermaidコードを ```mermaid ... ``` ブロックで囲んで含めてください。\n"
        "余計なコードブロック（例: html や python など）は含めず、純粋な mermaid ブロックのみを返してください。"
    )
    
    prompt = f"""
現在のMermaidダイアグラムコードを、以下の指示に従って適切に修正してください。

### 指示:
{user_instruction}

### 修正前のMermaidコード:
```mermaid
{current_code}
```

### 期待する回答形式:
1. どのような変更を行ったかの簡潔な解説 (日本語)
2. 修正後の完全なMermaidプログラムコード (```mermaid ... ``` の中に全体を記述)
"""
    
    return _call_llm_and_extract_mermaid(prompt, system_prompt, model_name)

def request_mermaid_repair(
    mermaid_code: str,
    error_msg: str,
    model_name: str = "qwen2.5-coder:7b",
) -> Dict[str, Any]:
    """
    構文エラーが発生しているMermaidコードの文法エラーを自動修正します。
    
    Args:
        mermaid_code: 構文エラーのあるMermaidコード
        error_msg: エラーメッセージ
        model_name: 使用するLLMモデル名
        
    Returns:
        Dict: {"success": bool, "repaired_code": str, "explanation": str, "error": Optional[str]}
    """
    if not llm_available or not call_llm:
        return {
            "success": False,
            "repaired_code": "",
            "explanation": "LLMモジュールが利用できないため、エラー修復を実行できません。",
            "error": "LLM module not available"
        }
        
    system_prompt = (
        "あなたはMermaid構文のエラーを修正するデバッグエキスパートです。\n"
        "提示されたMermaidコードのシンタックスエラー（矢印の不正な記法、括弧の不一致、未定義ノードの参照など）を特定し、文法エラーのない完全なMermaidコードを返してください。\n"
        "回答には必ず修正後の完全なMermaidコードを ```mermaid ... ``` ブロックで囲んで含めてください。"
    )
    
    prompt = f"""
以下のMermaidコードは構文エラー（Syntax Error）で描画に失敗しました。
エラーの原因を特定し、正しく描画できる完全なMermaidコードに修正してください。

### エラーの発生したMermaidコード:
```mermaid
{mermaid_code}
```

### エラー内容:
{error_msg}

### 期待する回答形式:
1. 修正箇所の簡潔な解説 (日本語)
2. 修正後の完全なMermaidプログラムコード (```mermaid ... ``` の中に全体を記述)
"""
    
    return _call_llm_and_extract_mermaid(prompt, system_prompt, model_name)

def _call_llm_and_extract_mermaid(
    prompt: str,
    system_prompt: str,
    model_name: str,
) -> Dict[str, Any]:
    """LLMを呼び出し、レスポンスからMermaidコードブロックを抽出する共通ヘルパー。"""
    try:
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
            
        # ```mermaid ... ``` ブロックを抽出
        code_match = re.search(r"```mermaid\s*\n(.*?)```", response, re.DOTALL | re.IGNORECASE)
        repaired_code = ""
        explanation = response
        
        if code_match:
            repaired_code = code_match.group(1).strip()
            # コードブロック部分を除去して解説テキストを取得
            explanation = re.sub(r"```mermaid\s*\n.*?```", "", response, flags=re.DOTALL | re.IGNORECASE).strip()
        else:
            # フォールバック: ``` で囲まれているだけのブロックを検索
            fallback_match = re.search(r"```\s*\n(.*?)```", response, re.DOTALL)
            if fallback_match:
                repaired_code = fallback_match.group(1).strip()
                explanation = re.sub(r"```\s*\n.*?```", "", response, flags=re.DOTALL).strip()
                
        if not repaired_code:
            logger.warning("Failed to extract Mermaid code block from LLM response")
            explanation = response
            
        return {
            "success": True,
            "repaired_code": repaired_code,
            "explanation": explanation,
            "error": None
        }
        
    except Exception as e:
        logger.exception("Exception during Mermaid repair/modification request")
        return {
            "success": False,
            "repaired_code": "",
            "explanation": f"図の生成中に例外が発生しました: {e}",
            "error": str(e)
        }
