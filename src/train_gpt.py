import torch
from torch.nn import functional as F
import tiktoken
import json
from pathlib import Path
import time
from src.model import GPT, GPTConfig
from src.utils.path_utils import get_corpus_path, CHECKPOINT_DIR

# ============================================================
# ハイパーパラメータ設定
# ============================================================
batch_size = 12        # 一度に処理するバッチサイズ (VRAMに合わせて調整)
block_size = 512       # コンテキスト長 (モデルが一度に見るトークン数)
max_iters = 2500       # 学習ステップ数 (5000だと長いので短縮)
eval_interval = 200    # 評価ログを出力する間隔
learning_rate = 3e-4   # 学習率
device = 'cuda' if torch.cuda.is_available() else 'cpu'
eval_iters = 100       # 評価時に計算する平均ステップ数
n_embd = 384           # 埋め込み次元
n_head = 6             # Attentionヘッド数
n_layer = 6            # レイヤー数
dropout = 0.2          # ドロップアウト率

# パス設定
ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = get_corpus_path()
DATASET_PATH = CORPUS_ROOT / "dataset.jsonl"
CHECKPOINT_DIR = ROOT / "checkpoints"

# トークナイザ (chunk_text.py と合わせる)
enc = tiktoken.get_encoding("cl100k_base")
vocab_size = enc.n_vocab  # tiktokenの語彙サイズ (~100k)

print(f"Using device: {device}")

# ============================================================
# データローダー
# ============================================================
def load_data():
    """dataset.jsonl から全テキストを読み込み、トークン化して結合する"""
    print(f"Loading dataset from {DATASET_PATH} ...")
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATASET_PATH}")

    doc_ids = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            text = data["text"]
            # テキストをトークンID列に変換
            ids = enc.encode(text)
            doc_ids.extend(ids)
            # ドキュメントの区切りとして <|endoftext|> トークンなどを入れるのが一般的だが、
            # ここでは単純に結合する (tiktokenの特殊トークン扱いは簡易的に省略)
            doc_ids.append(enc.eot_token)

    print(f"Total tokens: {len(doc_ids)}")
    return torch.tensor(doc_ids, dtype=torch.long)

data = load_data()

# データを学習用と検証用に分割 (90% : 10%)
n = int(0.9 * len(data))
train_data = data[:n]
val_data = data[n:]

def get_batch(split):
    """バッチデータを生成する"""
    d = train_data if split == 'train' else val_data
    # データの終端を超えないランダムな開始位置を選択
    ix = torch.randint(len(d) - block_size, (batch_size,))
    
    # 入力(x)とターゲット(y)を作成 (yはxを1つずらしたもの)
    x = torch.stack([d[i:i+block_size] for i in ix])
    y = torch.stack([d[i+1:i+block_size+1] for i in ix])
    
    return x.to(device), y.to(device)

@torch.no_grad()
def estimate_loss(model):
    """学習中のモデルの性能を評価する"""
    out = {}
    model.eval()
    for split in ['train', 'val']:
        losses = torch.zeros(eval_iters)
        for k in range(eval_iters):
            X, Y = get_batch(split)
            logits = model(X)
            # 損失計算 (CrossEntropy)
            B, T, C = logits.shape
            logits = logits.view(B*T, C)
            targets = Y.view(B*T)
            loss = F.cross_entropy(logits, targets)
            losses[k] = loss.item()
        out[split] = losses.mean()
    model.train()
    return out

# ============================================================
# メイン学習ループ
# ============================================================
def train():
    # チェックポイントディレクトリから最新のステップ数を取得して再開する準備
    start_step = 0
    latest_ckpt = None
    if CHECKPOINT_DIR.exists():
        ckpts = list(CHECKPOINT_DIR.glob("ckpt_step_*.pt"))
        if ckpts:
            # ファイル名からステップ数を抽出してソート
            ckpts.sort(key=lambda p: int(p.stem.split("_")[-1]))
            latest_ckpt = ckpts[-1]
            start_step = int(latest_ckpt.stem.split("_")[-1])
            
    CHECKPOINT_DIR.mkdir(exist_ok=True)

    # モデルの初期化
    config = GPTConfig(
        vocab_size=vocab_size,
        n_layer=n_layer,
        n_head=n_head,
        n_embd=n_embd,
        block_size=block_size
    )
    model = GPT(config)
    model.to(device)
    
    # 続きから再開する場合
    if latest_ckpt:
        print(f"Resuming training from step {start_step} (checkpoint: {latest_ckpt.name})")
        state_dict = torch.load(latest_ckpt, map_location=device, weights_only=True)
        model.load_state_dict(state_dict)
    
    print(f"Model parameters: {sum(p.numel() for p in model.parameters())/1e6:.2f}M")

    # オプティマイザ (AdamW)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)

    start_time = time.time()

    for step in range(start_step, max_iters):

        # 定期的な評価と保存
        if step % eval_interval == 0 or step == max_iters - 1:
            losses = estimate_loss(model)
            print(f"step {step}: train loss {losses['train']:.4f}, val loss {losses['val']:.4f}")
            
            # チェックポイント保存
            if step > 0:
                ckpt_path = CHECKPOINT_DIR / f"ckpt_step_{step}.pt"
                torch.save(model.state_dict(), ckpt_path)

        # バッチ取得
        xb, yb = get_batch('train')

        # 順伝播
        logits = model(xb)
        B, T, C = logits.shape
        logits = logits.view(B*T, C)
        targets = yb.view(B*T)
        loss = F.cross_entropy(logits, targets)

        # 逆伝播
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()

    print(f"Training finished in {time.time() - start_time:.2f}s")

if __name__ == "__main__":
    train()