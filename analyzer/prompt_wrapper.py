from typing import List, Dict, Optional

def build_confirmation_prompt(user_message: str, context: Optional[List[Dict]] = None) -> str:
    """Build a wrapped prompt that repeats the user's request, asks for confirmation, then asks the model to answer.

    Format:
    復唱: <user_message>
    確認: 上の内容で間違いありませんか？（はい/いいえ）
    回答: <ここに回答を記載してください>
    """
    ctx_summary = ""
    if context:
        # Keep context short: join last few user turns if present
        last_user_turns = [m.get("text", "") for m in context if m.get("role") == "user"]
        if last_user_turns:
            ctx_summary = "\n（関連コンテキスト）" + " | ".join(last_user_turns[-3:])

    prompt = (
        f"復唱: {user_message}{ctx_summary}\n"
        "確認: 上の内容で間違いありませんか？（はい/いいえ）\n"
        "回答:"
    )
    return prompt

def wrap_and_call(llm_func, user_message: str, context: Optional[List[Dict]] = None, **kwargs):
    """Helper to wrap a call to an LLM function.

    llm_func should accept a single `prompt` string argument (or `message`) and return text.
    This helper builds the confirmation prompt and returns the LLM output.
    """
    prompt = build_confirmation_prompt(user_message, context=context)
    return llm_func(prompt, **kwargs)

__all__ = ["build_confirmation_prompt", "wrap_and_call"]
