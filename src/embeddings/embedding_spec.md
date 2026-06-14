# 仕様書: `embedding.py`

## 1. 概要
`embedding.py` は、RAG（Retrieval-Augmented Generation）システムにおいて、コーパスデータ（チャンク分割済みのテキスト）を多言語対応モデル `BAAI/bge-m3` を用いてベクトル化し、FAISSによる類似度検索のためのインデックスを構築・保存するスクリプトです。

## 2. 依存関係
- **標準ライブラリ**: `os`, `json`, `pathlib.Path`
- **機械学習・テンソル演算**: `torch`, `transformers` (Hugging Face), `numpy`
- **ベクトル検索**: `faiss`
- **内部モジュール**: `src.utils.path_utils` (`get_corpus_path`, `get_embeddings_path`)

## 3. グローバル設定・定数
- **`DEVICE`**: `"cuda"` （GPUを使用した高速推論を前提）
- **`BATCH_SIZE`**: `2` （VRAM消費を抑えるための小さなバッチサイズ。環境やGPUのVRAM容量に応じて調整可能）
- **入出力パス**:
  - `DATASET_PATH`: `${CORPUS_ROOT}/dataset.jsonl`（入力となるチャンクデータ）
  - `INDEX_PATH`: `${CORPUS_ROOT}/corpus.index`（出力されるFAISSインデックス）
  - `META_PATH`: `${CORPUS_ROOT}/corpus_meta.json`（出力されるメタデータ）

## 4. 関数仕様

### 4.1. `load_bge_m3()`
- **目的**: Hugging FaceのTransformersを利用して、埋め込みモデルとトークナイザーをロードします。
- **使用モデル**: `"BAAI/bge-m3"`
- **戻り値**: `(tokenizer, model)` のタプル。モデルは初期化時に指定されたデバイス(`cuda`)に転送されます。

### 4.2. `load_chunks()`
- **目的**: `dataset.jsonl` からテキストチャンクデータを読み込みます。
- **処理**: ファイルが存在しない場合はエラーメッセージを出力し、空のリストを返します。JSON Lines形式であることを前提とし、1行ずつパースします。
- **戻り値**: チャンクの辞書オブジェクトを格納したリスト (`list[dict]`)。

### 4.3. `encode_texts(tokenizer, model, texts, batch_size)`
- **目的**: 与えられたテキストのリストをベクトル（埋め込み）に変換します。
- **引数**:
  - `tokenizer`, `model`: `load_bge_m3()`で取得したオブジェクト
  - `texts`: ベクトル化対象の文字列リスト
  - `batch_size`: バッチサイズ（デフォルトは `BATCH_SIZE` の2）
- **処理**:
  1. トークナイズ処理 (`max_length=8192` を指定し、BGE-M3の長文入力に対応)。
  2. BGE-M3モデルによる推論処理（勾配計算を無効化する `torch.no_grad()` を使用）。
  3. **CLSプーリング**: 推論結果 `outputs.last_hidden_state[:, 0]` を取得し、テキスト全体の表現ベクトルとします。
  4. **L2正規化**: ベクトル長を1にするため `torch.nn.functional.normalize(..., p=2, dim=1)` を適用。これにより内積計算がコサイン類似度と等価になります。
- **戻り値**: 全テキストのベクトルをまとめた2次元Numpy配列 (`np.ndarray`)。

### 4.4. `generate_embeddings()`
- **目的**: メインとなるオーケストレーション関数。データ読み込み、エンコーディング、インデックス構築、メタデータ保存を一貫して実行します。
- **処理フロー**:
  1. 出力ディレクトリ（`EMB_DIR`）の作成とGPUメモリのキャッシュクリア。
  2. `load_bge_m3()` でモデルをロード。
  3. `load_chunks()` でチャンク情報を読み込み、エンコード対象のテキストリストを抽出。
  4. `encode_texts()` を呼び出し、テキストリスト全体をベクトル化。
  5. **FAISSインデックスの構築**:
     - `faiss.IndexFlatIP` (内積に基づくインデックス) を初期化。
     - 生成されたベクトル（`float32`に変換）をインデックスに追加。
     - インデックスを `corpus.index` としてディスクに保存。
  6. **メタデータの保存**:
     - 元のチャンクデータに `"id"` フィールドが無い場合、`"doc_{index}"` の形式で一意のIDを付与。
     - ID付与後のチャンクデータを `corpus_meta.json` としてディスクに保存。

## 5. 特記事項・エッジケース対応
- **互換性パッチ**: `torch` (バージョン2.4.x) と `torchao` (バージョン0.16.0以降) の間で発生する互換性の問題を解消するため、スクリプト冒頭で `torch.int1` 等のダミー属性を追加するモンキーパッチが適用されています。
- **長文対応とトークン制限**: トークナイザーで `max_length=8192` を設定しており、BGE-M3の特長である長文テキストの処理（最大8192トークン）に対応しています。
- **OOM対策**: メモリ（VRAM）不足によるエラー（Out of Memory）を防ぐため、バッチサイズは初期値 `2` と小さく設定されています。
