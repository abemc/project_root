import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class GPTConfig:
    """GPTモデルのハイパーパラメータを保持する設定クラス"""
    def __init__(self, vocab_size, n_layer, n_head, n_embd, block_size):
        self.vocab_size = vocab_size    # 語彙サイズ
        self.n_layer = n_layer          # Transformerブロックの層数
        self.n_head = n_head            # Multi-Head Attentionのヘッド数
        self.n_embd = n_embd            # 埋め込みベクトルの次元数
        self.block_size = block_size    # コンテキスト長


class CausalSelfAttention(nn.Module):
    """因果関係的自己注意機構 (Causal Masked Multi-Head Self-Attention)"""
    def __init__(self, config):
        super().__init__()
        assert config.n_embd % config.n_head == 0

        # Query, Key, Value に変換するための全結合層
        self.key = nn.Linear(config.n_embd, config.n_embd)
        self.query = nn.Linear(config.n_embd, config.n_embd)
        self.value = nn.Linear(config.n_embd, config.n_embd)

        self.n_head = config.n_head
        self.dropout = nn.Dropout(0.1)

        # Attention出力後の最終的な射影層
        self.proj = nn.Linear(config.n_embd, config.n_embd)

        # 未来のトークンを参照しないための因果マスクを作成 (下三角行列)
        mask = torch.tril(torch.ones(config.block_size, config.block_size))
        self.register_buffer("mask", mask)

    def forward(self, x):
        B, T, C = x.size()
        H = self.n_head
        head_dim = C // H

        # Q, K, V を計算し、ヘッド数に合わせて形状を変換・転置
        k = self.key(x).view(B, T, H, head_dim).transpose(1, 2)
        q = self.query(x).view(B, T, H, head_dim).transpose(1, 2)
        v = self.value(x).view(B, T, H, head_dim).transpose(1, 2)

        # スケール化ドット積Attentionのスコア計算と因果マスクの適用
        att = (q @ k.transpose(-2, -1)) / math.sqrt(head_dim)
        att = att.masked_fill(self.mask[:T, :T] == 0, float("-inf"))
        
        # Softmaxによる正規化とDropout
        att = F.softmax(att, dim=-1)
        att = self.dropout(att)

        # Attentionスコアを用いてValueを重み付け加算し、元の次元に戻す
        y = att @ v
        y = y.transpose(1, 2).contiguous().view(B, T, C)

        return self.proj(y)


class Block(nn.Module):
    """1層分のTransformerデコーダーブロック"""
    def __init__(self, config):
        super().__init__()
        # Pre-LayerNormアーキテクチャ: AttentionとMLPの前にLayerNormを適用する
        self.ln1 = nn.LayerNorm(config.n_embd)
        self.attn = CausalSelfAttention(config)
        self.ln2 = nn.LayerNorm(config.n_embd)
        
        # Feed-Forward Network (MLP)
        # 次元を4倍に拡大し、GELU活性化を経て元の次元に戻す
        self.mlp = nn.Sequential(
            nn.Linear(config.n_embd, 4 * config.n_embd),
            nn.GELU(),
            nn.Linear(4 * config.n_embd, config.n_embd),
        )

    def forward(self, x):
        # LayerNorm -> Attention -> 残差接続
        x = x + self.attn(self.ln1(x))
        # LayerNorm -> MLP -> 残差接続
        x = x + self.mlp(self.ln2(x))
        return x


class GPT(nn.Module):
    """GPT (Generative Pre-trained Transformer) 本体"""
    def __init__(self, config):
        super().__init__()

        # トークン埋め込み層と、学習可能な位置埋め込みパラメータ
        self.token_emb = nn.Embedding(config.vocab_size, config.n_embd)
        self.pos_emb = nn.Parameter(torch.zeros(1, config.block_size, config.n_embd))

        # N個のTransformerブロックを直列に重ねる
        self.blocks = nn.Sequential(*[Block(config) for _ in range(config.n_layer)])
        
        # 最終出力前のレイヤー正規化と、語彙サイズへ射影する出力層
        self.ln_f = nn.LayerNorm(config.n_embd)
        self.head = nn.Linear(config.n_embd, config.vocab_size, bias=False)

        self.block_size = config.block_size

    def forward(self, idx):
        B, T = idx.size()
        
        assert T <= self.block_size

        # トークンIDのベクトル化と位置ベクトルの加算
        tok = self.token_emb(idx)
        pos = self.pos_emb[:, :T, :]
        x = tok + pos

        # Transformerブロック群を通過
        x = self.blocks(x)
        
        # 最終正規化を経てロジットを計算
        x = self.ln_f(x)
        logits = self.head(x)

        return logits


@torch.no_grad()
def generate(model, config, idx, max_new_tokens):
    """自己回帰的に新しいトークンを生成する関数"""
    for _ in range(max_new_tokens):
        # 入力コンテキストが block_size を超えないよう直近のトークンのみを切り出す
        idx_cond = idx[:, -config.block_size:]
        
        # モデルで推論し、最後のタイムステップのロジットを取得
        logits = model(idx_cond)
        logits = logits[:, -1, :]
        
        # 確率分布に変換して次のトークンをサンプリング
        probs = F.softmax(logits, dim=-1)
        next_id = torch.multinomial(probs, num_samples=1)
        
        # 生成されたトークンを入力シーケンスの末尾に追加
        idx = torch.cat((idx, next_id), dim=1)
        
    return idx
