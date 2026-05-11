# CI テストとローカル検証手順

この文書は、CI上で安定してテストを回すための手順と、ローカルでの軽量テスト／フルテストの実行方法を示します。

## CI 方針

CI ではモデルの大きなダウンロードや GPU 必要処理を避けるため、環境変数 `USE_MOCK_VISION=1` を設定して軽量モードで実行します。

推奨ジョブ:

- ユニットジョブ: `USE_MOCK_VISION=1` をセットして高速に回す。
- インテグレーション/実機ジョブ: 別ジョブで `USE_MOCK_VISION` を外して実行（ネットワーク、ストレージ、場合によっては GPU を確保する）。

## ローカルでの実行

- 軽量（推奨, 早い）:

```bash
PYTHONPATH=. USE_MOCK_VISION=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  pytest -q -k "not integration and not e2e and not distributed"
```

- フル（モデルをダウンロードして実行）:

```bash
PYTHONPATH=. TRANSFORMERS_OFFLINE=0 HF_DATASETS_OFFLINE=0 \
  /home/abemc/project_root/.venv/bin/python -m pytest -q
```

注意: フル実行は時間がかかり、モデルのキャッシュのディスク使用が大きくなります。CIで実行する場合は専用ジョブを用意してください。

## トラブルシューティング

- `transformers` の安全チェックで `torch` のバージョン要件があるため、`torch>=2.6.0` を `requirements.txt` に指定してください。
- ダウンロードを避けたい場合は `TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1` を指定します。

## フルモデル検証ジョブ（CI）

フルモデル検証はコストがかかるため、CI では手動トリガー（`workflow_dispatch`）で実行することを推奨します。ワークフロー定義は [/.github/workflows/ci.yml](.github/workflows/ci.yml) にあり、`Full-model tests (manual)` ジョブを手動で起動できます。

