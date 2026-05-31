graph TD;
    A[README.md] --> B[ProjectStructure.md];
    A --> C[Code.md];
    B --> D[SourceCodeFolder];
    D --> E[src/main.py];
    D --> F[src/utils.py];
    C --> G[TestFilesFolder];
    G --> H[test_main.py];

---

## 🧪 テスト実行時の注意

テストが失敗した場合は、まず `docs/01_クイックスタート/AIベギナーガイド.md` の「よくあるトラブル・FAQ・対処法」セクションを参照してください。

- 依存パッケージ不足、パスの間違い、権限エラーなど、初心者がつまずきやすいポイントと解決策がまとまっています。
- FAQで解決しない場合は、エラーメッセージ全文と実行手順を添えて質問してください。

---

## Project Analyzer（実験機能）

このリポジトリにはワークスペースを解析する簡易ツール `Project Analyzer` を追加しています。主に開発者向けのプロジェクト要約・ファイルメタ情報収集を目的としたプロトタイプです。

主要ファイル:

クイックスタート（モック LLM を使う）:
```bash
python -c "from analyzer.cli import run_analyze; run_analyze(root='.', out='analysis.json')"
```

Streamlit で起動:

Prometheus エクスポーターの利用方法:

1. 依存パッケージをインストール:
```bash
pip install prometheus_client
```

2. サンプルコード:
```python
from analyzer.metrics_exporter import UsagePrometheusExporter
from analyzer.llm_client import OpenAIClient

client = OpenAIClient(api_key=None)
exporter = UsagePrometheusExporter()
exporter.start(port=8000)

# 何らかの処理で要約を行う
client.summarize('...')
client.summarize('...')

# exporter に集計を反映
exporter.update_from_client(client)

# ブラウザで http://localhost:8000/metrics を開くと Prometheus 形式でメトリクスが確認できます
```

注意: `UsagePrometheusExporter` は `prometheus_client` に依存します。複数インスタンス環境では exporter を中央集約（Pushgateway やローカル collector）することを検討してください。

### Collector 起動（CLI）と TLS 設定

簡易的に `CollectorServer` を起動する CLI を追加しました。TLS 設定（既存の証明書/鍵ファイル指定、または自己署名証明書の生成）に対応しています。

起動例（HTTP, shared secret 無し）:
```bash
python -m analyzer.collector_cli --path logs/central.log --host 0.0.0.0 --port 8001
```

起動例（HTTPS, 既存証明書を指定）:
```bash
python -m analyzer.collector_cli --path logs/central.log --host 0.0.0.0 --port 8443 --auth-secret mysecret --certfile /path/to/cert.pem --keyfile /path/to/key.pem
```

起動例（HTTPS, 自己署名証明書を自動生成）:
```bash
python -m analyzer.collector_cli --path logs/central.log --generate-cert --auth-secret mysecret
```

注意: `--generate-cert` はローカルテスト用途の自己署名証明書を `openssl` コマンドで生成します。実運用では適切な CA 発行証明書を使用してください。
```bash
pip install streamlit
streamlit run analyzer/ui_streamlit.py
```

OpenAI を用いて要約を行う場合:
1. 環境変数に API キーを設定します:
```bash
export OPENAI_API_KEY=your_key_here
export OPENAI_MODEL=gpt-4o-mini  # 任意
```
2. `OpenAIClient` を使う場合はスクリプトや対話から `analyzer.llm_client.OpenAIClient` を作成して `run_analyze(..., llm_client=client)` に渡してください。

注意点:
- シークレットや API キーなどの機密情報は自動送信されない設計です。検出したシークレットはログに警告します。
- 大きなファイルはデフォルトでスニペットのみを解析対象とするため、必要に応じて `analyzer.scanner.scan` の `size_threshold` を調整してください。

### RAG評価と自動ゲート

RAG の評価結果を保存し、そのまま回帰ゲートまで実行できます。

1. 評価入力を JSON で用意します。`evaluation_data` キー、またはルート配列のどちらでも読み込めます。
2. 評価と保存を実行します。

```bash
python -m src.evaluation.rag_evaluation \
    --input results/rag_inputs.json \
    --output results/benchmarks/rag_evaluation_20260601_120000.json
```

3. 保存と同時に直近 2 件を比較してゲートレポートも出す場合は `--auto-gate` を付けます。

```bash
python -m src.evaluation.rag_evaluation \
    --input results/rag_inputs.json \
    --output results/benchmarks/rag_evaluation_20260601_120000.json \
    --auto-gate
```

4. 保存済みの RAG 評価レポートと回帰ゲート履歴は、Streamlit の Learning Dashboard で確認できます。
    - 実画面では `🧠 Learning Dashboard` の `🎲 Reinforcement Learning` タブで、`🧪 ベンチマーク回帰ゲート`、`🧾 保存済み回帰ゲート履歴`、`📊 RAG評価履歴` が並んで表示されることを確認済みです。

補足:
- 回帰ゲートは `results/benchmarks/regression_gate_*.json` を保存します。
- RAG 評価レポートは `results/benchmarks/rag_evaluation_*.json` を保存します。
- ゲートは `factual_consistency` と `end_to_end_score` を含むベンチマーク互換 JSON を比較します。

### トークン使用量のロギングとファイル出力

`OpenAIClient` は API 呼び出し時にレスポンスの `usage` を内部 `usage_history` に蓄積します。ローカルに書き出すには `flush_usage_to(path, max_bytes, backup_count)` を使います。

例:
```python
from analyzer.llm_client import OpenAIClient

client = OpenAIClient(api_key=None)  # 環境変数 OPENAI_API_KEY を使用
client.summarize("...")
# ファイルに JSON-lines 形式で出力し、5MB を超えたら最大5世代でローテーション
client.flush_usage_to("logs/usage.log", max_bytes=5*1024*1024, backup_count=5)
```

仕様:
- 出力形式: JSON-lines（各行が1つの usage エントリ）
- ローテーション: ファイルサイズが `max_bytes` を超えると `usage.log` → `usage.log.1` → `usage.log.2` のように単純リネームでローテーション（`backup_count` 世代まで保持）
- 並列書き込みや高負荷環境には非推奨。堅牢化が必要な場合は外部ログ基盤を利用してください。

