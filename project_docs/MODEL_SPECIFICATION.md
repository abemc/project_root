# GPT モデル仕様書 (`src/model.py`)

本書は、本プロジェクトにおいてスクラッチで実装されている自己回帰型Transformerモデル（GPTアーキテクチャ）の仕様を定義・説明するドキュメントです。

## 概要

`src/model.py` は、PyTorch (`torch.nn`) を用いてゼロから構築された、デコーダーのみのTransformerモデル (GPT: Generative Pre-trained Transformer) のコアモジュールです。主に言語モデリング（次のトークンの予測）タスクに使用されます。

## 依存ライブラリ
- `math`: スケール化ドット積Attentionの計算（平方根）に使用
- `torch`: テンソル演算全般
- `torch.nn`: ニューラルネットワーク層の構成要素
- `torch.nn.functional`: 活性化関数やSoftmaxなどの関数

---

## クラス・関数定義

### 1. `GPTConfig` クラス
モデルの構造・ハイパーパラメータを保持するための設定データクラスです。

| パラメータ名 | 型 | 説明 |
| :--- | :--- | :--- |
| `vocab_size` | int | 語彙数 (トークンの種類数)。出力層のサイズにもなります。 |
| `n_layer` | int | Transformerブロック (層) の数。 |
| `n_head` | int | マルチヘッドアテンションにおけるヘッドの数。 |
| `n_embd` | int | トークンおよび位置の埋め込みベクトル次元数 (隠れ層の次元数)。 |
| `block_size` | int | コンテキスト長 (モデルが一度に処理できる最大シーケンス長)。 |

### 2. `CausalSelfAttention` クラス
因果関係的自己注意機構 (Causal Masked Multi-Head Self-Attention) の実装です。未来のトークンを先読みして情報が漏洩しないようにマスク処理を行います。

**処理フローと仕様:**
1. **Q, K, V の射影:**
   入力ベクトルに対して、それぞれ独立した全結合層 (`self.query`, `self.key`, `self.value`) を適用し、Query, Key, Value を計算します。
2. **ヘッドの分割:**
   `n_embd` 次元を `n_head` 個のヘッドに分割し (`head_dim = n_embd // n_head`)、並列でAttentionを計算できるように形状を変換・転置します。
3. **スケール化ドット積Attention:**
   `Q` と転置した `K` の内積を取り、`sqrt(head_dim)` でスケーリングします。
4. **因果マスク (Causal Mask):**
   下三角行列 (`torch.tril`) を用いて作成したマスクを適用し、未来のトークンに対応するAttentionスコアを `-inf` に置き換えます（Softmax後に0になります）。
5. **Softmax & Dropout:**
   Softmax関数を適用してAttentionの重みを正規化し、Dropout (`p=0.1`) を適用します。
6. **Vへの重み付けと出力:**
   計算されたAttention重みを `V` に掛け合わせ、分割していたヘッドを再結合した後、出力用の全結合層 (`self.proj`) に通します。

### 3. `Block` クラス
1層分のTransformerデコーダーブロックです。

**構造:**
1. **LayerNorm 1:** 入力に対するレイヤー正規化。
2. **Attention:** 上記の `CausalSelfAttention` を適用。
3. **残差接続 1:** `x = x + Attention(LayerNorm(x))`
4. **LayerNorm 2:** 次の層の入力に対するレイヤー正規化。
5. **MLP (Feed Forward):** 隠れ層を4倍 (`4 * n_embd`) に拡大し、GELU活性化関数を挟んで元の次元 (`n_embd`) に戻す2層の全結合ネットワーク。
6. **残差接続 2:** `x = x + MLP(LayerNorm(x))`

*注意: 元の論文(Attention Is All You Need)のPre-LayerNorm方式（各サブレイヤーの前にLayerNormを適用する方式）が採用されています。*

### 4. `GPT` クラス
Transformerモデルの全体構造（本体）を定義します。

**構造:**
1. **埋め込み層:**
   - `token_emb`: トークンIDをベクトルに変換するEmbedding層 (`vocab_size` → `n_embd`)。
   - `pos_emb`: 絶対位置を学習するPosition Embeddingパラメーター (サイズ: `[1, block_size, n_embd]`)。
2. **Transformerブロック:**
   `n_layer` 個の `Block` クラスを直列に繋げたシーケンシャルモデル。
3. **最終出力層:**
   - `ln_f`: 最後のレイヤー正規化。
   - `head`: `n_embd` 次元の出力を元の語彙サイズ `vocab_size` に射影する全結合層（バイアスなし）。ここから各トークンのロジット（確率の対数前）が出力されます。

**フォワードパス (`forward`):**
- トークンID配列 (`B, T`) を受け取り、最大シーケンス長が `block_size` 以下であることをアサート。
- トークン埋め込みと位置埋め込みを加算し、Transformerブロック群に入力。
- 最終層を通して、語彙サイズ分の次元を持つロジット (`[B, T, vocab_size]`) を出力。

### 5. `generate` 関数
学習済みモデルを使用して、与えられた入力トークンから新しいトークンを自己回帰的に生成する推論用のユーティリティ関数です。

**仕様:**
- `@torch.no_grad()` デコレータが付与されており、推論時のメモリ消費と計算コストを抑えます。
- 指定された `max_new_tokens` の数だけループを回します。
- **コンテキストの切り詰め:** 入力シーケンスの長さが `block_size` を超えないよう、直近の `block_size` 個のトークンのみを切り出してモデルに入力します。
- **サンプリング:** 出力されたロジットの最後の時間ステップ (`-1`) に対してSoftmaxを適用して確率分布を求め、`torch.multinomial` で次の1トークンを確率的にサンプリングします。
- 生成されたトークンを入力シーケンスの末尾に結合し、次の予測に使用します。

---

## アーキテクチャの特長
- **Pre-LayerNorm**: 学習の安定性を高めるため、GPT-2などで採用されている層事前正規化を採用。
- **学習可能な位置埋め込み**: 正弦波による固定の位置エンコーディングではなく、データから学習する絶対位置埋め込み(`nn.Parameter`)を採用。
- **GELU 活性化関数**: ReLUの代わりに、より自然言語処理に適したGELU (Gaussian Error Linear Unit) をMLP層で使用。
