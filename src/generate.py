import torch
import tiktoken
from pathlib import Path
import sys

# プロジェクトルートから実行されることを想定して src.model をインポート
try:
    from src.model import GPT, GPTConfig, generate
except ImportError:
    # パスが解決できない場合のフォールバック
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from src.model import GPT, GPTConfig, generate

# ============================================================
# 設定 (学習スクリプト src/train_gpt.py と合わせる必要があります)
# ============================================================
n_embd = 384
n_head = 6
n_layer = 6
block_size = 512
device = 'cuda' if torch.cuda.is_available() else 'cpu'

# パス設定
ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_DIR = ROOT / "checkpoints"

def load_latest_checkpoint():
    """checkpointsディレクトリから最新の学習済みモデル(.pt)を探す"""
    if not CHECKPOINT_DIR.exists():
        return None
    
    # "ckpt_step_*.pt" パターンにマッチするファイルを取得
    checkpoints = list(CHECKPOINT_DIR.glob("ckpt_step_*.pt"))
    if not checkpoints:
        return None

    # ステップ数 (ファイル名の数値) でソートして最新を取得
    def get_step(p):
        try:
            return int(p.stem.split("_")[-1])
        except ValueError:
            return 0
            
    latest_ckpt = max(checkpoints, key=get_step)
    return latest_ckpt

def main():
    print(f"Device: {device}")

    # 1. チェックポイントの探索
    ckpt_path = load_latest_checkpoint()
    if not ckpt_path:
        print(f"[ERROR] Checkpoint not found in {CHECKPOINT_DIR}")
        print("Please run training first: python -m src.train_gpt")
        return

    print(f"Loading checkpoint: {ckpt_path.name}")

    # 2. トークナイザとモデル設定の準備
    enc = tiktoken.get_encoding("cl100k_base")
    vocab_size = enc.n_vocab

    config = GPTConfig(
        vocab_size=vocab_size,
        n_layer=n_layer,
        n_head=n_head,
        n_embd=n_embd,
        block_size=block_size
    )
    
    # 3. モデルの初期化とロード
    model = GPT(config)
    
    try:
        # map_locationでデバイスを適切に割り当て
        state_dict = torch.load(ckpt_path, map_location=device, weights_only=True)
        model.load_state_dict(state_dict)
        model.to(device)
        model.eval()  # 推論モード (Dropoutなどを無効化)
    except Exception as e:
        print(f"[ERROR] Failed to load model: {e}")
        return

    print("Model loaded successfully.")
    print("-" * 60)
    print("Interactive Generator (Ctrl+C or type 'exit' to quit)")
    print("-" * 60)

    # 4. 対話型生成ループ
    while True:
        try:
            prompt = input("\nYour prompt > ")
        except KeyboardInterrupt:
            print("\nExiting...")
            break

        if prompt.strip().lower() in ['exit', 'quit', 'q']:
            break
        
        if not prompt.strip():
            continue

        # 生成開始
        start_ids = enc.encode(prompt)
        x = torch.tensor(start_ids, dtype=torch.long, device=device)[None, ...]

        # 生成長
        max_new_tokens = 200
        
        with torch.no_grad():
            # src.model.generate 関数を利用
            y = generate(model, config, x, max_new_tokens)
            
        # デコードして表示
        generated_text = enc.decode(y[0].tolist())
        
        print("\n--- Generated Output ---")
        print(generated_text)
        print("------------------------")

if __name__ == "__main__":
    main()