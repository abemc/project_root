**VectorStore 強化まとめ**

- **目的**: 正規化改善、埋め込み高速化（バッチ/GPU）、監視（Prometheus）、CI 品質ゲート、開発者向けドキュメント整備を順次導入。

- **追加ファイル**:
  - `scripts/normalize_enhanced.py`: 正規化ルール強化（注記除去、ルビ処理、外字フック）
  - `scripts/async_embed.py`: バッチ埋め込み（device auto, 出力は .npy）
  - `src/monitoring/prometheus_exporter.py`: 軽量 Prometheus エクスポーター
  - `scripts/ci_check_results.py`: 閾値チェックを追加（`results/search_quality_metrics.json` の `avg_overlap` を確認）

- **実行例**:

  - 正規化のドライラン (最初の 10 ファイル): 

    ```bash
    python scripts/normalize_enhanced.py --input-dir corpus/normalized --dry-run --limit 10
    ```

  - 小規模で埋め込み（CPU）:

    ```bash
    python scripts/async_embed.py --source corpus/dataset.jsonl --batch-size 32 --device cpu --limit 200 --out-dir corpus/emb_tmp
    ```

  - Prometheus エクスポーター起動:

    ```bash
    python -m src.monitoring.prometheus_exporter --port 9000
    ```

  - CI チェック実行 (閾値 0.3):

    ```bash
    python scripts/ci_check_results.py --smoke-file results/ci_smoke_after.json --overlap-threshold 0.3
    ```

- **次の推奨作業**:
  - `GAIJI_MAP` を現実の外字マッピングで拡充
  - `scripts/async_embed.py` を asyncio + multiprocessing に置き換え、メモリマップ出力を追加
  - Prometheus メトリクスを埋め込みパイプライン／ingest に組み込み
  - CI ワークフローに `scripts/ci_check_results.py` を組み込み（しきい値は環境変数で管理）

- **注意**: 追加したスクリプトは最小限の実装です。本番での利用前に負荷試験・例外処理・ログを強化してください。
