import os
import requests
import json
from typing import Optional, List, Dict, Any

# -----------------------------
# LLM 呼び出し
# -----------------------------
def call_llm(prompt: str, model: str = "qwen2.5:7b", system_prompt: Optional[str] = None, chat_history: Optional[List[Dict[str, str]]] = None, **kwargs):
    """
    LLMを呼び出す統一インターフェース。
    """
    is_openai_model = model.lower().startswith(("gpt-", "o1-"))
    force_openai = os.environ.get("USE_OPENAI_API", "").lower() == "true"
    
    if is_openai_model or force_openai:
        return _call_openai_compatible(prompt, model, system_prompt, chat_history, **kwargs)
    else:
        return _call_ollama_chat(prompt, model, system_prompt, chat_history, **kwargs)


def _call_ollama_chat(prompt: str, model: str, system_prompt: Optional[str] = None, chat_history: Optional[List[Dict[str, str]]] = None, **kwargs):
    """
    Ollama Chat API (/api/chat) を呼び出す。
    """
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    url = f"{base_url}/api/chat"
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    if chat_history:
        # すでにrole/contentの辞書形式であることを想定
        messages.extend(chat_history)
    
    user_message = {"role": "user", "content": prompt}
    
    # 画像データがkwargsにある場合は追加 (base64文字列のリストを想定)
    if "images" in kwargs:
        user_message["images"] = kwargs["images"]
    
    messages.append(user_message)

    options = {
        "temperature": kwargs.get("temperature", 0.7),
    }
    max_tokens = kwargs.get("max_tokens", kwargs.get("max_new_tokens", 2048))
    if max_tokens:
        options["num_predict"] = max_tokens

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": options
    }

    try:
        # タイムアウトを設定（接続に5秒、応答待ちに60秒）
        res = requests.post(url, json=payload, timeout=(5, 60))
    except requests.exceptions.RequestException as e:
        print(f"[Error] Request failed: {e}")
        return f"Error: {e}"

    try:
        res.raise_for_status()
        return res.json()["message"]["content"].strip()
    except Exception as e:
        error_msg = f"[Error] Ollama Chat failed: {e}"
        print(error_msg)
        return f"Error: {error_msg}"


def _call_ollama(prompt: str, model: str, **kwargs):
    # 下位互換用
    return _call_ollama_chat(prompt, model, **kwargs)


def _call_openai_compatible(prompt: str, model: str, system_prompt: Optional[str] = None, chat_history: Optional[List[Dict[str, str]]] = None, api_base: Optional[str] = None, **kwargs):
    """
    OpenAI Chat Completion API 互換のエンドポイントを呼び出す。
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = api_base if api_base else os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
    
    url = f"{base_url.rstrip('/')}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}" if api_key else ""
    }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    if chat_history:
        messages.extend(chat_history)
        
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": kwargs.get("temperature", 0.7),
    }
    
    max_tokens = kwargs.get("max_tokens", kwargs.get("max_new_tokens", 2048))
    if max_tokens:
        payload["max_tokens"] = max_tokens

    try:
        # タイムアウトを設定（接続に5秒、応答待ちに60秒）
        res = requests.post(url, headers=headers, json=payload, timeout=(5, 60))
        res.raise_for_status()
        data = res.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        error_msg = f"[Error] OpenAI API call failed: {e}"
        print(error_msg)
        return f"Error: {error_msg}"
