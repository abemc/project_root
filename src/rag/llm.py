import os
import requests
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor, Future

# Module-level executor for async LLM calls
_LLM_EXECUTOR = ThreadPoolExecutor(max_workers=4)

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


def call_llm_async(prompt: str, model: str = "qwen2.5:7b", system_prompt: Optional[str] = None, chat_history: Optional[List[Dict[str, str]]] = None, **kwargs) -> Future:
    """Submit a call_llm request to the background executor and return a Future."""
    # Use a wrapper to call the synchronous call_llm inside the thread
    def _worker():
        return call_llm(prompt=prompt, model=model, system_prompt=system_prompt, chat_history=chat_history, **kwargs)

    return _LLM_EXECUTOR.submit(_worker)


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
        # タイムアウトを設定（接続に10秒、応答待ちに300秒 = 5分）
        res = requests.post(url, json=payload, timeout=(10, 300))
    except requests.exceptions.RequestException as e:
        err = f"[Error] Request failed: {e}"
        print(err)
        return f"Error: {err}"

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
        # タイムアウトを設定（接続に10秒、応答待ちに300秒 = 5分）
        res = requests.post(url, headers=headers, json=payload, timeout=(10, 300))
        res.raise_for_status()
        data = res.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        error_msg = f"[Error] OpenAI API call failed: {e}"
        print(error_msg)
        # フォールバック: OpenAI互換エンドポイントが使えない場合はローカルのOllamaにフォールバックしてみる
        try:
            print("[Info] Attempting fallback to Ollama chat...")
            fallback = _call_ollama_chat(prompt, model, system_prompt=system_prompt, chat_history=chat_history, **kwargs)
            if isinstance(fallback, str) and not fallback.startswith("Error:"):
                return fallback
            else:
                print(f"[Info] Ollama fallback also failed: {fallback}")
        except Exception as ex2:
            print(f"[Error] Ollama fallback exception: {ex2}")

        # 追加フォールバック: ローカルの Hugging Face モデルを試す
        try:
            print("[Info] Attempting fallback to local Hugging Face model...")
            try:
                from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
            except Exception as imp_e:
                raise RuntimeError(f"transformers import failed: {imp_e}")

            model_id = os.environ.get("LOCAL_FALLBACK_MODEL", "gpt2")
            max_new = int(kwargs.get("max_new_tokens", kwargs.get("max_tokens", 128)))

            # ロードは遅いので慎重に行う
            tokenizer = AutoTokenizer.from_pretrained(model_id)
            model_hf = AutoModelForCausalLM.from_pretrained(model_id)

            import torch as _torch
            device = 0 if _torch.cuda.is_available() else -1
            gen = pipeline("text-generation", model=model_hf, tokenizer=tokenizer, device=device)
            out = gen(prompt, max_new_tokens=max_new, do_sample=False)
            if out and isinstance(out, list):
                text = out[0].get("generated_text") or out[0].get("text") or ""
                return text.strip()
        except Exception as hf_e:
            print(f"[Error] Local HF fallback failed: {hf_e}")

        return f"Error: {error_msg}"
