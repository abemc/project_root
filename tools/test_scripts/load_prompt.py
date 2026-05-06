import os
import json
import sys
from pathlib import Path

# Patch for torchao compatibility (torchao 0.16.0+ requires torch 2.5+, but we have 2.4.1)
import torch
if not hasattr(torch, "int1"):
    for i in range(1, 8):
        for dtype in [f"int{i}", f"uint{i}"]:
            setattr(torch, dtype, type(dtype, (), {})())

# プロジェクトルートをsys.pathに追加してsrcモジュールをインポート可能にする
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

# src.rag.llm から call_llm をインポート
try:
    from src.rag.llm import call_llm
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

def load_prompt_template(file_path: str) -> str:
    """
    指定されたファイルパスからプロンプトテンプレートを読み込みます。

    Args:
        file_path (str): プロンプトテンプレートファイルのパス。

    Returns:
        str: ファイルの内容。

    Raises:
        FileNotFoundError: ファイルが見つからない場合に発生します。
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"エラー: ファイルが見つかりません: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"ファイルの読み込み中にエラーが発生しました: {e}")
        return ""

def validate_prompt_json_format(prompt_text: str):
    """
    プロンプトテキストからJSON形式の例を抽出し、パース可能か検証します。
    """
    print("\n--- JSON形式の検証 ---")
    try:
        # プロンプトテキストからJSONブロックを抽出
        start_index = prompt_text.find('{')
        end_index = prompt_text.rfind('}')
        
        if start_index == -1 or end_index == -1 or start_index > end_index:
            print("エラー: プロンプト内にJSON形式の例 '{...}' が見つかりません。")
            return

        json_string = prompt_text[start_index : end_index + 1]
        
        print("抽出されたJSON文字列のサンプル:")
        print(json_string)

        # JSONとしてパースしてみる
        parsed_json = json.loads(json_string)
        print("✅ 検証成功: JSON形式は有効です。")

        # キーの存在チェック
        required_keys = ["type", "reason", "query", "tool_name", "tool_input", "answer"]
        missing_keys = [key for key in required_keys if key not in parsed_json]
        
        if missing_keys:
            print(f"⚠️ 警告: 必須キーが不足しています: {', '.join(missing_keys)}")
        else:
            print("✅ 検証成功: 全ての必須キーが存在します。")

    except json.JSONDecodeError as e:
        print(f"❌ 検証失敗: JSONのパースに失敗しました。: {e}")
        print(f"  対象文字列: {json_string}")
    except Exception as e:
        print(f"❌ 検証中に予期せぬエラーが発生しました: {e}")

def test_with_llm(system_prompt: str, model_name: str = "qwen2.5:7b"):
    """
    読み込んだプロンプトを使用して実際にLLMにリクエストを送信します。
    """
    if not LLM_AVAILABLE:
        print("\n⚠️ src.rag.llm が見つからないため、LLMテストは実行できません。")
        return

    print(f"\n--- LLM接続テスト (Model: {model_name}) ---")
    print("システムプロンプトを適用して対話をテストします。")
    
    while True:
        try:
            user_input = input("\n質問を入力 ('q'で終了): ").strip()
            if not user_input or user_input.lower() == 'q':
                break
            
            # プロンプトの構築
            # ここでは単純にシステムプロンプトの後にユーザー入力を繋げます
            full_messages = f"{system_prompt}\n\n---\n\nユーザーの入力: {user_input}"
            
            print("⏳ 生成中...", end="", flush=True)
            response = call_llm(full_messages, model=model_name)
            print("\r✅ 生成完了   ")
            
            print("\n--- LLM Response ---")
            print(response)
            print("--------------------")
            
            # 応答がJSON形式であることを検証
            print("\n[応答の検証]")
            validate_prompt_json_format(response)
            
        except KeyboardInterrupt:
            print("\nテストを中断します。")
            break
        except Exception as e:
            print(f"\n❌ エラーが発生しました: {e}")

if __name__ == "__main__":
    prompt_file_path = os.path.join(project_root, "prompt.txt")

    # プロンプトを読み込む
    system_prompt = load_prompt_template(prompt_file_path)

    if system_prompt:
        print("--- プロンプトテンプレートの読み込みに成功しました ---")
        print(system_prompt)
        print("-------------------------------------------------")

        # JSON形式の検証を実行
        validate_prompt_json_format(system_prompt)

        if LLM_AVAILABLE:
            run_test = input("\nLLMを使用してプロンプトをテストしますか？ (y/n): ").lower().strip()
            if run_test == 'y':
                test_with_llm(system_prompt)