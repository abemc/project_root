---

## ❓ よくある質問（FAQ）

### Q. APIの動作確認方法は？
**A.** サンプルコードや `tests/` 配下のAPIテストスクリプトを実行してください。

### Q. レスポンスが遅い場合は？
**A.** キャッシュ設定やタイムアウト、パラメータ設定を見直してください。

### Q. ImportErrorが出る場合は？
**A.** プロジェクトルートで実行し、src/配下が正しく参照されているか確認してください。

---

## ✅ 理解度チェックリスト

- [ ] 各APIエンドポイントの役割を説明できる
- [ ] サンプルコードを自分で動かせる
- [ ] エラー時の対処法を説明できる
- [ ] テスト・検証の手順を説明できる

すべてチェックできたら、次の実践・応用フェーズへ進みましょう！
# Phase 7 Pipeline API Documentation

## 概要

Phase 7 Complete Pipeline は、クエリ処理からレスポンス生成まで、
すべてのコンポーネントを統合したエンドツーエンドパイプラインです。

---

## クラスリファレンス

### Phase7CompletePipeline

メインパイプラインクラス。複数のコンポーネントを統合します。

#### 初期化

```python
from src.integrated_pipeline import Phase7CompletePipeline, PipelineConfig

# デフォルト設定で初期化
pipeline = Phase7CompletePipeline()

# カスタム設定で初期化
config = PipelineConfig(
    enable_caching=True,
    cache_size=1000,
    enable_logging=True,
    timeout_seconds=30,
    min_confidence_threshold=0.5
)
pipeline = Phase7CompletePipeline(config)
```

#### メソッド

##### process_query(query: str) -> ProcessingResult

単一のクエリを処理します。

**パラメータ:**
- `query` (str): 処理するクエリ

**戻り値:**
- `ProcessingResult`: 処理結果オブジェクト

**使用例:**
```python
result = pipeline.process_query("患者の症状について教えてください。")
print(f"ドメイン: {result.domain}")
print(f"信頼度: {result.confidence}")
print(f"処理時間: {result.processing_time_ms}ms")
```

##### process_batch(queries: List[str], batch_size: int = 10) -> List[ProcessingResult]

複数のクエリを一度に処理します。

**パラメータ:**
- `queries` (List[str]): 処理するクエリのリスト
- `batch_size` (int): バッチサイズ（デフォルト: 10）

**戻り値:**
- `List[ProcessingResult]`: 処理結果のリスト

**使用例:**
```python
queries = [
    "医学的な質問1",
    "医学的な質問2",
    "医学的な質問3"
]
results = pipeline.process_batch(queries, batch_size=10)

for result in results:
    print(f"Q: {result.query}")
    print(f"A: {result.answer}")
    print("---")
```

##### get_statistics() -> Dict[str, Any]

パイプラインの統計情報を取得します。

**戻り値:**
- `Dict[str, Any]`: 統計情報
  - `total_queries`: 総クエリ数
  - `successful_queries`: 成功したクエリ数
  - `failed_queries`: 失敗したクエリ数
  - `success_rate`: 成功率（%）
  - `average_processing_time_ms`: 平均処理時間
  - `total_processing_time_ms`: 総処理時間

**使用例:**
```python
# 複数のクエリを処理後
stats = pipeline.get_statistics()
print(f"成功率: {stats['success_rate']:.1f}%")
print(f"平均処理時間: {stats['average_processing_time_ms']:.1f}ms")
```

---

### ProcessingResult

処理結果を格納するデータクラス

**属性:**
- `query` (str): 入力クエリ
- `answer` (str): 生成された回答
- `domain` (str): 推定ドメイン
- `confidence` (float): 信頼度 (0.0-1.0)
- `sources` (List[str]): 参照ソース
- `processing_time_ms` (float): 処理時間（ミリ秒）
- `timestamp` (str): ISO形式のタイムスタンプ
- `reasoning_chain` (Optional[str]): 推論チェーン
- `error` (Optional[str]): エラーメッセージ

**メソッド:**

###### to_dict() -> Dict

結果を辞書形式に変換

###### to_json() -> str

結果をJSON文字列に変換

---

### PipelineConfig

パイプライン設定クラス

**属性:**
- `enable_caching` (bool): キャッシング有効化（デフォルト: True）
- `cache_size` (int): キャッシュサイズ（デフォルト: 1000）
- `enable_logging` (bool): ログ記録有効化（デフォルト: True）
- `timeout_seconds` (int): タイムアウト秒数（デフォルト: 30）
- `min_confidence_threshold` (float): 最小信頼度閾値（デフォルト: 0.5）

---

## 処理フロー

```
入力クエリ
    ↓
Step 1️⃣ : クエリ前処理
    ↓
Step 2️⃣ : ドメイン推定
    ↓
Step 3️⃣ : 知識統合
    ↓
Step 4️⃣ : 因果推論
    ↓
Step 5️⃣ : 不確実性評価
    ↓
Step 6️⃣ : 結果生成
    ↓
出力結果
```

---

## 実行例

### 基本的な使用方法

```python
from src.integrated_pipeline import Phase7CompletePipeline

# パイプラインの初期化
pipeline = Phase7CompletePipeline()

# クエリの処理
result = pipeline.process_query("医学的な問題について")

# 結果の表示
print(f"ドメイン: {result.domain}")
print(f"信頼度: {result.confidence:.2f}")
print(f"処理時間: {result.processing_time_ms:.1f}ms")

# 統計情報の表示
pipeline.print_statistics()
```

### バッチ処理

```python
from src.integrated_pipeline import Phase7CompletePipeline

pipeline = Phase7CompletePipeline()

queries = [
    "患者テスト1",
    "患者テスト2",
    "患者テスト3",
]

# バッチ処理実行
results = pipeline.process_batch(queries, batch_size=10)

# 結果の処理
for i, result in enumerate(results):
    print(f"{i+1}. {result.query[:50]}... → {result.domain}")
```

### JSON形式での出力

```python
from src.integrated_pipeline import Phase7CompletePipeline
import json

pipeline = Phase7CompletePipeline()
result = pipeline.process_query("テストクエリ")

# JSON文字列として出力
json_output = result.to_json()
print(json_output)

# ファイルに保存
with open("result.json", "w", encoding="utf-8") as f:
    f.write(json_output)
```

---

## トラブルシューティング

### 問題: 「ImportError: No module named 'src'」

**解決方法:**
```bash
cd /home/abemc/project_root
python your_script.py
```

### 問題: 処理時間が長い

**確認事項:**
- キャッシング設定が有効か
- バッチサイズは適切か
- システムリソースは十分か

**最適化方法:**
```python
config = PipelineConfig(
    enable_caching=True,
    cache_size=2000
)
pipeline = Phase7CompletePipeline(config)
```

---

## パフォーマンス目標

| 指標 | 目標値 | 実装状況 |
|------|-------|--------|
| 平均応答時間 | < 500ms | ✅ |
| スループット | > 200 queries/sec | ✅ |
| 成功率 | 100% | ✅ |
| キャッシュヒット率 | > 50% | ✅ |

---

## ライセンス

Phase 7 Pipeline は教育目的で提供されています。

---

## サポート

問題が発生した場合は、以下のファイルを確認してください：
- `/tmp/phase7_pipeline.log` - 詳細ログ
- `tests/test_integrated_pipeline.py` - テストコード例

最終更新: {timestamp}
