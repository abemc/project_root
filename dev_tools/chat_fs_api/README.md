# Chat FS API

軽量のファイル操作API（ローカルワークスペース）です。差分パッチのチェックと適用をサポートします。

起動例:

```bash
python -m uvicorn dev_tools.chat_fs_api.server:APP --host 127.0.0.1 --port 8001 --reload
```

主なエンドポイント:
- `GET /api/list?path=.`: ディレクトリ一覧
- `GET /api/read?path=path/to/file`: ファイル内容取得（2MB上限）
- `POST /api/patch/check`: パッチ（unified diff）検証
- `POST /api/patch/apply`: 新しいブランチを作ってパッチを適用しコミットします

注意:
- 本ツールはローカル開発向けです。公開環境での利用は認証・許可・監査の実装が必要です。
