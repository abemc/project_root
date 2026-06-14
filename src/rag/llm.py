import os
import requests
import json
from typing import Optional, List, Dict, Any

# -----------------------------
# LLM 呼び出し
# -----------------------------
def call_llm(prompt: str, model: str = "qwen2.5-coder:7b", system_prompt: Optional[str] = None, chat_history: Optional[List[Dict[str, str]]] = None, stream: bool = False, **kwargs):
    """
    LLMを呼び出す統一インターフェース。
    """
    is_openai_model = model.lower().startswith(("gpt-", "o1-"))
    is_local_model = any(x in model.lower() for x in ["qwen", "llama", "gemma", "phi", "mistral"])
    force_openai = os.environ.get("USE_OPENAI_API", "").lower() == "true"
    
    if is_openai_model:
        return _call_openai_compatible(prompt, model, system_prompt, chat_history, stream=stream, **kwargs)
    elif is_local_model:
        return _call_ollama_chat(prompt, model, system_prompt, chat_history, stream=stream, **kwargs)
    elif force_openai:
        actual_model = "gpt-4o" if model == "qwen2.5-coder:7b" else model
        return _call_openai_compatible(prompt, actual_model, system_prompt, chat_history, stream=stream, **kwargs)
    else:
        return _call_ollama_chat(prompt, model, system_prompt, chat_history, stream=stream, **kwargs)


def _call_ollama_chat(prompt: str, model: str, system_prompt: Optional[str] = None, chat_history: Optional[List[Dict[str, str]]] = None, stream: bool = False, **kwargs):
    """
    Ollama Chat API (/api/chat) を呼び出す。
    """
    # ローカルのOllamaインスタンスに存在するモデルのみを許可し、すべて qwen2.5-coder:7b にマッピングする
    model = "qwen2.5-coder:7b"
    base_url = os.environ.get("OLLAMA_BASE_URL")
    if not base_url:
        # Dockerコンテナ内かどうかに関わらず、/proc/net/routeからデフォルトゲートウェイの取得を試みる
        gw_ip = None
        if os.path.exists("/proc/net/route"):
            try:
                with open("/proc/net/route", "r") as fh:
                    for line in fh:
                        fields = line.strip().split()
                        if len(fields) >= 3 and fields[1] == "00000000":
                            gw_hex = fields[2]
                            gw_ip = ".".join([str(int(gw_hex[i:i+2], 16)) for i in (6, 4, 2, 0)])
                            break
            except Exception:
                pass
        
        # ゲートウェイIPが検出できた場合、それはホストマシンを指している可能性が高い（コンテナ内実行時）
        # ホスト上の Ollama (11434) またはプロキシ (11435) への接続を試みる
        if gw_ip and gw_ip != "0.0.0.0":
            import socket
            # ゲートウェイの11435（プロキシ）または11434（Ollama）が生きているか確認
            for port in [11435, 11434]:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(1.5)
                        if s.connect_ex((gw_ip, port)) == 0:
                            base_url = f"http://{gw_ip}:{port}"
                            break
                except Exception:
                    pass

        # 上記で決定できなかった場合のフォールバック（ホスト上での直接実行時、またはゲートウェイ接続失敗時）
        if not base_url:
            base_url = "http://localhost:11435"  # デフォルトは直接11435に接続
            import socket
            # ホスト上での実行時、11435（プロキシ）または11434（Ollama）をチェック
            for port in [11435, 11434]:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(1.5)
                        if s.connect_ex(('127.0.0.1', port)) == 0:
                            base_url = f"http://localhost:{port}"
                            break
                except Exception:
                    pass
            
    url = f"{base_url}/api/chat"
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    
    if chat_history:
        messages.extend(chat_history)
    
    user_message = {"role": "user", "content": prompt}
    if "images" in kwargs:
        user_message["images"] = kwargs["images"]
    
    messages.append(user_message)

    # モデルサイズに応じてGPUレイヤー数を動的に決定する（OOM防止と安定動作の両立）
    # RTX 4060 Ti (8GB) のVRAM空き容量に合わせる
    num_gpu = None
    model_lower = model.lower()
    if "1.5b" in model_lower:
        num_gpu = 29  # 1.5Bモデルは軽量なので全レイヤーをGPUへ
    elif any(x in model_lower for x in ["7b", "8b"]):
        # 7B/8Bクラスのモデルは、WSL2上のVRAMメモリ制限（CUDA OOM）によるクラッシュを防ぐため、
        # 安全にCPUで動作させる（num_gpu: 0）
        num_gpu = 0
    else:
        # 30B以上の巨大モデルは安全のためCPUで動作させる
        num_gpu = 0

    options = {
        "temperature": kwargs.get("temperature", 0.7),
    }
    if num_gpu is not None:
        options["num_gpu"] = num_gpu
    max_tokens = kwargs.get("max_tokens", kwargs.get("max_new_tokens", 2048))
    if max_tokens:
        options["num_predict"] = max_tokens

    keep_alive_val = os.environ.get("OLLAMA_KEEP_ALIVE", "5m")
    try:
        keep_alive = int(keep_alive_val)
    except ValueError:
        keep_alive = keep_alive_val

    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "options": options,
        "keep_alive": keep_alive
    }

    try:
        # Increase read timeout to 300 seconds (5 minutes) for long/streaming generations
        # 接続タイムアウトを60秒に緩和し、初回モデルロード時のタイムアウト（GPU展開など）を防ぐ
        res = requests.post(url, json=payload, stream=stream, timeout=(60, 300))
        res.raise_for_status()
        
        if stream:
            def generator():
                try:
                    for line in res.iter_lines():
                        if line:
                            chunk = json.loads(line.decode('utf-8'))
                            content = chunk.get("message", {}).get("content", "")
                            if content:
                                yield content
                except Exception as e:
                    yield f"Error in stream: {e}"
            return generator()
        else:
            return res.json()["message"]["content"].strip()
            
    except requests.exceptions.RequestException as e:
        print(f"[Error] Request failed: {e}")
        return f"Error: {e}"


def _call_ollama(prompt: str, model: str, **kwargs):
    return _call_ollama_chat(prompt, model, **kwargs)


def _call_openai_compatible(prompt: str, model: str, system_prompt: Optional[str] = None, chat_history: Optional[List[Dict[str, str]]] = None, api_base: Optional[str] = None, stream: bool = False, **kwargs):
    """
    OpenAI Chat Completion API 互換のエンドポイントを呼び出す。
    """
    if model.lower() == "gpt-5.4-mini":
        model = "gpt-4o-mini"

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
        "stream": stream
    }
    
    max_tokens = kwargs.get("max_tokens", kwargs.get("max_new_tokens", 2048))
    if max_tokens:
        payload["max_tokens"] = max_tokens

    try:
        # Increase read timeout to 300 seconds (5 minutes) for long/streaming generations
        res = requests.post(url, headers=headers, json=payload, stream=stream, timeout=(5, 300))
        res.raise_for_status()
        
        if stream:
            def generator():
                try:
                    for line in res.iter_lines():
                        if line:
                            decoded = line.decode('utf-8').strip()
                            if decoded.startswith("data: "):
                                data_str = decoded[6:]
                                if data_str == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data_str)
                                    content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                    if content:
                                        yield content
                                except Exception:
                                    pass
                except Exception as e:
                    yield f"Error in stream: {e}"
            return generator()
        else:
            data = res.json()
            return data["choices"][0]["message"]["content"].strip()
            
    except Exception as e:
        error_msg = f"[Error] OpenAI API call failed: {e}"
        print(error_msg)
        return f"Error: {error_msg}"
