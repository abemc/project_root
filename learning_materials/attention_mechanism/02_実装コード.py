"""
Attentionメカニズム - 実装例とユーティリティ

このモジュールは、様々なAttentionメカニズムの実装と検証用ツールを提供します。
"""

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional
import matplotlib.pyplot as plt
import seaborn as sns


# ============================================================================
# 1. 基本的な Attention 計算
# ============================================================================

def scaled_dot_product_attention(
    query: torch.Tensor,
    key: torch.Tensor,
    value: torch.Tensor,
    mask: Optional[torch.Tensor] = None,
    dropout_p: float = 0.0
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Scaled Dot-Product Attention を計算
    
    Args:
        query: Query テンソル (batch_size, seq_len, d_k)
        key: Key テンソル (batch_size, seq_len, d_k)
        value: Value テンソル (batch_size, seq_len, d_v)
        mask: Optional attention mask
        dropout_p: Dropout 確率
    
    Returns:
        output: Attention 出力 (batch_size, seq_len, d_v)
        attention_weights: Attention ウェイト (batch_size, seq_len, seq_len)
    
    公式:
        Attention(Q, K, V) = softmax(Q·K^T / √d_k) · V
    """
    d_k = query.size(-1)
    
    # Step 1: QK^T を計算
    scores = torch.matmul(query, key.transpose(-2, -1))
    
    # Step 2: スケーリング
    scores = scores / np.sqrt(d_k)
    
    # Step 3: マスク適用（オプション）
    if mask is not None:
        scores = scores.masked_fill(mask == 0, float('-inf'))
    
    # Step 4: softmax
    attention_weights = torch.softmax(scores, dim=-1)
    
    # Step 5: Dropout
    if dropout_p > 0:
        attention_weights = F.dropout(attention_weights, p=dropout_p, training=True)
    
    # Step 6: Value との乗算
    output = torch.matmul(attention_weights, value)
    
    return output, attention_weights


# ============================================================================
# 2. Multi-Head Attention の実装
# ============================================================================

class MultiHeadAttention(nn.Module):
    """
    Multi-Head Attention レイヤー
    
    複数のアテンションヘッドを並列に実行し、結果を連結します。
    
    公式:
        MultiHead(Q, K, V) = Concat(head_1, ..., head_h) W^O
        where head_i = Attention(Q W_i^Q, K W_i^K, V W_i^V)
    """
    
    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        """
        Args:
            d_model: モデルの次元
            num_heads: アテンションヘッド数
            dropout: Dropout 確率
        """
        super().__init__()
        assert d_model % num_heads == 0, "d_model は num_heads で割り切れる必要があります"
        
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads
        
        # 線形変換層
        self.linear_Q = nn.Linear(d_model, d_model)
        self.linear_K = nn.Linear(d_model, d_model)
        self.linear_V = nn.Linear(d_model, d_model)
        self.linear_out = nn.Linear(d_model, d_model)
        
        self.dropout = nn.Dropout(dropout)
    
    def forward(
        self,
        query: torch.Tensor,
        key: torch.Tensor,
        value: torch.Tensor,
        mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            query: Query (batch_size, seq_len, d_model)
            key: Key (batch_size, seq_len, d_model)
            value: Value (batch_size, seq_len, d_model)
            mask: Optional mask
        
        Returns:
            output: (batch_size, seq_len, d_model)
            attention_weights: (batch_size, num_heads, seq_len, seq_len)
        """
        batch_size = query.size(0)
        
        # Step 1: 線形変換
        Q = self.linear_Q(query)  # (batch, seq, d_model)
        K = self.linear_K(key)
        V = self.linear_V(value)
        
        # Step 2: マルチヘッドに分割
        Q = Q.view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        # (batch, num_heads, seq, d_k)
        K = K.view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        V = V.view(batch_size, -1, self.num_heads, self.d_k).transpose(1, 2)
        
        # Step 3: 各ヘッドで Attention を計算
        output, attention_weights = scaled_dot_product_attention(
            Q, K, V, mask, dropout_p=self.dropout.p
        )
        
        # Step 4: ヘッドを連結
        output = output.transpose(1, 2).contiguous()  # (batch, seq, num_heads, d_k)
        output = output.view(batch_size, -1, self.d_model)  # (batch, seq, d_model)
        
        # Step 5: 出力層
        output = self.linear_out(output)
        
        return output, attention_weights


# ============================================================================
# 3. Self-Attention と Cross-Attention
# ============================================================================

class SelfAttention(MultiHeadAttention):
    """Self-Attention: 同じシーケンス内での関係を学習"""
    
    def forward(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: 入力シーケンス (batch_size, seq_len, d_model)
            mask: Optional mask
        
        Returns:
            output: Self-Attention 出力
            attention_weights: Attention ウェイト
        """
        return super().forward(x, x, x, mask)


class CrossAttention(MultiHeadAttention):
    """Cross-Attention: 異なるシーケンス間の関係を学習"""
    
    def forward(
        self,
        query: torch.Tensor,
        encoder_output: torch.Tensor,
        mask: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            query: Query (decoder) (batch_size, seq_len, d_model)
            encoder_output: Key, Value (encoder) (batch_size, seq_len, d_model)
            mask: Optional mask
        
        Returns:
            output: Cross-Attention 出力
            attention_weights: Attention ウェイト
        """
        return super().forward(query, encoder_output, encoder_output, mask)


# ============================================================================
# 4. Causal Attention (因果注意) の実装
# ============================================================================

def create_causal_mask(seq_len: int) -> torch.Tensor:
    """
    因果マスク（Causal Mask）を生成
    
    将来の位置を見ないようにマスク
    
    Args:
        seq_len: シーケンス長
    
    Returns:
        マスク (1, seq_len, seq_len)
    
    例:
        seq_len = 3 の場合:
        [[1, 0, 0],
         [1, 1, 0],
         [1, 1, 1]]
    """
    mask = torch.tril(torch.ones(seq_len, seq_len))
    return mask.unsqueeze(0)


class CausalAttention(SelfAttention):
    """Causal Self-Attention: 将来の単語を見ない"""
    
    def forward(
        self,
        x: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: 入力シーケンス (batch_size, seq_len, d_model)
        
        Returns:
            output: Causal Attention 出力
            attention_weights: Attention ウェイト
        """
        seq_len = x.size(1)
        mask = create_causal_mask(seq_len).to(x.device)
        return super().forward(x, mask)


# ============================================================================
# 5. Position-wise Feed-Forward Network
# ============================================================================

class PositionwiseFeedForward(nn.Module):
    """Position-wise Feed-Forward Network
    
    FFN(x) = max(0, xW_1 + b_1)W_2 + b_2
    """
    
    def __init__(self, d_model: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        self.linear1 = nn.Linear(d_model, d_ff)
        self.linear2 = nn.Linear(d_ff, d_model)
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear2(self.dropout(F.relu(self.linear1(x))))


# ============================================================================
# 6. Transformer ブロック
# ============================================================================

class TransformerBlock(nn.Module):
    """Transformer ブロック
    
    構成:
    1. Multi-Head Self-Attention
    2. Add & Norm (残差接続 + 層正規化)
    3. Position-wise Feed-Forward
    4. Add & Norm (残差接続 + 層正規化)
    """
    
    def __init__(self, d_model: int, num_heads: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        
        self.attention = MultiHeadAttention(d_model, num_heads, dropout)
        self.ffn = PositionwiseFeedForward(d_model, d_ff, dropout)
        
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        
        self.dropout = nn.Dropout(dropout)
    
    def forward(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Args:
            x: 入力 (batch_size, seq_len, d_model)
            mask: Optional attention mask
        
        Returns:
            出力 (batch_size, seq_len, d_model)
        """
        # Multi-Head Attention + 残差接続 + 層正規化
        attn_output, _ = self.attention(x, x, x, mask)
        x = self.norm1(x + self.dropout(attn_output))
        
        # Feed-Forward + 残差接続 + 層正規化
        ffn_output = self.ffn(x)
        x = self.norm2(x + self.dropout(ffn_output))
        
        return x


# ============================================================================
# 7. Attention の可視化
# ============================================================================

def visualize_attention_weights(
    attention_weights: torch.Tensor,
    tokens: list,
    head_idx: int = 0,
    figsize: Tuple[int, int] = (8, 8)
):
    """
    Attention ウェイトを可視化（ヒートマップ）
    
    Args:
        attention_weights: (batch, num_heads, seq_len, seq_len)
        tokens: トークンリスト
        head_idx: 表示するヘッドのインデックス
        figsize: 図のサイズ
    """
    # バッチサイズが1と仮定
    weights = attention_weights[0, head_idx].detach().cpu().numpy()
    
    plt.figure(figsize=figsize)
    sns.heatmap(
        weights,
        xticklabels=tokens,
        yticklabels=tokens,
        cmap='Blues',
        cbar=True
    )
    plt.title(f"Attention Weights (Head {head_idx})")
    plt.tight_layout()
    plt.show()


def plot_attention_pattern(
    query: torch.Tensor,
    key: torch.Tensor,
    title: str = "Attention Pattern"
):
    """
    Attention パターンを可視化
    
    Args:
        query: Query (1, seq_len, d_k)
        key: Key (1, seq_len, d_k)
        title: 図のタイトル
    """
    # スコア計算
    scores = torch.matmul(query, key.transpose(-2, -1))
    scores = scores.squeeze(0).detach().cpu().numpy()
    
    plt.figure(figsize=(8, 6))
    plt.imshow(scores, cmap='coolwarm', aspect='auto')
    plt.colorbar(label='Attention Score')
    plt.xlabel('Key Position')
    plt.ylabel('Query Position')
    plt.title(title)
    plt.tight_layout()
    plt.show()


# ============================================================================
# 8. デモ用ユーティリティ
# ============================================================================

def create_sample_tokens(text: str, tokenizer=None) -> list:
    """
    サンプルテキストをトークン化
    
    Args:
        text: 入力テキスト
        tokenizer: Optional トークナイザー
    
    Returns:
        トークンリスト
    """
    if tokenizer is None:
        # 簡易的な分かち書き
        return text.split()
    else:
        return tokenizer.tokenize(text)


def create_token_embeddings(tokens: list, d_model: int = 64) -> torch.Tensor:
    """
    トークンの埋め込みを生成（デモ用）
    
    Args:
        tokens: トークンリスト
        d_model: 埋め込み次元
    
    Returns:
        埋め込みテンソル (1, seq_len, d_model)
    """
    seq_len = len(tokens)
    # ランダムな埋め込み（実際にはWord2Vec, GloVe等を使用）
    embeddings = torch.randn(1, seq_len, d_model)
    return embeddings


def create_positional_encoding(seq_len: int, d_model: int) -> torch.Tensor:
    """
    位置エンコーディングを生成（Sinusoidal）
    
    Args:
        seq_len: シーケンス長
        d_model: モデルの次元
    
    Returns:
        位置エンコーディング (1, seq_len, d_model)
    """
    position = torch.arange(seq_len).unsqueeze(1)
    div_term = torch.exp(torch.arange(0, d_model, 2) * 
                        -(np.log(10000.0) / d_model))
    
    pe = torch.zeros(seq_len, d_model)
    pe[:, 0::2] = torch.sin(position * div_term)
    pe[:, 1::2] = torch.cos(position * div_term)
    
    return pe.unsqueeze(0)


# ============================================================================
# 9. パフォーマンス比較
# ============================================================================

def benchmark_attention(
    seq_len: int,
    d_model: int = 512,
    num_heads: int = 8,
    num_iterations: int = 100
) -> dict:
    """
    異なるアテンションメカニズムのパフォーマンスを比較
    
    Args:
        seq_len: シーケンス長
        d_model: モデルの次元
        num_heads: ヘッド数
        num_iterations: 反復回数
    
    Returns:
        パフォーマンスメトリクス辞書
    """
    import time
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # ダミーデータ生成
    x = torch.randn(1, seq_len, d_model).to(device)
    
    results = {}
    
    # 1. Basic Attention
    def basic_attention():
        Q = torch.randn(1, seq_len, d_model).to(device)
        K = torch.randn(1, seq_len, d_model).to(device)
        V = torch.randn(1, seq_len, d_model).to(device)
        scores = torch.matmul(Q, K.transpose(-2, -1)) / np.sqrt(d_model)
        weights = torch.softmax(scores, dim=-1)
        output = torch.matmul(weights, V)
        return output
    
    # 2. Multi-Head Attention
    mha = MultiHeadAttention(d_model, num_heads).to(device)
    
    # ベンチマーク
    start = time.time()
    for _ in range(num_iterations):
        basic_attention()
    results['basic_attention'] = time.time() - start
    
    start = time.time()
    for _ in range(num_iterations):
        mha(x, x, x)
    results['multi_head_attention'] = time.time() - start
    
    return results


# ============================================================================
# 10. 検証・テスト用ユーティリティ
# ============================================================================

def verify_attention_properties():
    """
    Attention メカニズムの性質を検証
    """
    print("=" * 60)
    print("Attention メカニズムの性質検証")
    print("=" * 60)
    
    # テストデータ
    seq_len = 4
    d_model = 64
    batch_size = 2
    
    Q = torch.randn(batch_size, seq_len, d_model)
    K = torch.randn(batch_size, seq_len, d_model)
    V = torch.randn(batch_size, seq_len, d_model)
    
    output, weights = scaled_dot_product_attention(Q, K, V)
    
    print(f"\n✓ Query 形状: {Q.shape}")
    print(f"✓ Key 形状: {K.shape}")
    print(f"✓ Value 形状: {V.shape}")
    print(f"✓ Output 形状: {output.shape}")
    print(f"✓ Attention Weights 形状: {weights.shape}")
    
    # 性質1: ウェイトの合計が1
    weight_sums = weights.sum(dim=-1)
    is_valid = torch.allclose(weight_sums, torch.ones_like(weight_sums), atol=1e-6)
    print(f"\n✓ Attention weights の合計 = 1: {is_valid}")
    
    # 性質2: ウェイトが非負
    is_non_negative = (weights >= 0).all()
    print(f"✓ Attention weights >= 0: {is_non_negative}")
    
    # 性質3: Output が Value と同じ形状
    is_shape_correct = output.shape == V.shape
    print(f"✓ Output 形状 = Value 形状: {is_shape_correct}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    # 検証実行
    verify_attention_properties()
    
    # デモ実行
    print("\nデモ: Simple Attention Calculation")
    print("-" * 60)
    
    text = "The cat sat on the mat"
    tokens = create_sample_tokens(text)
    print(f"テキスト: {text}")
    print(f"トークン: {tokens}")
    
    embeddings = create_token_embeddings(tokens, d_model=64)
    print(f"埋め込み形状: {embeddings.shape}")
    
    output, weights = scaled_dot_product_attention(embeddings, embeddings, embeddings)
    print(f"出力形状: {output.shape}")
    print(f"Attention weights 形状: {weights.shape}")
    
    print("\n✓ 基本的な Attention 計算完了！")
