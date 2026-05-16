# app.py 仕様書

## 概要
`app.py` は、Streamlit を使用して構築されたアプリケーションのエントリーポイントです。このアプリケーションは、RAG（Retrieval-Augmented Generation）エージェントを中心に構成されており、以下の主要な機能を提供します。

- サイドバーの設定
- エージェントの初期化
- 知識ベースの管理
- デバッグ設定
- 再構築機能

## 構成

### インポート
- **標準ライブラリ**:
  - `os`, `sys`, `Path`
- **外部ライブラリ**:
  - `streamlit`
  - `logging`

### ロギング設定
- ログレベル: `INFO`
- フォーマット: `%(asctime)s - %(levelname)s - %(message)s`

### Streamlit ページ設定
- タイトル: `RAG Agent`
- レイアウト: `wide`

## 主な機能

### 1. サイドバーの設定
```python
try:
    setup_sidebar()
except Exception as e:
    logger.error(f"サイドバーの設定中にエラーが発生しました: {e}")
```
- サイドバーの UI を設定します。
- エラー発生時にはログに記録されます。

### 2. エージェントの初期化
```python
try:
    initialize_agent()
except Exception as e:
    logger.error(f"エージェントの初期化中にエラーが発生しました: {e}")
```
- RAG エージェントを初期化します。
- エラー発生時にはログに記録されます。

### 3. 知識ベースの管理
```python
try:
    manage_corpus()
except Exception as e:
    logger.error(f"知識ベースの管理中にエラーが発生しました: {e}")
```
- 知識ベース（コーパス）の管理を行います。
- エラー発生時にはログに記録されます。

### 4. デバッグ設定
```python
try:
    configure_debug()
except Exception as e:
    logger.error(f"デバッグ設定中にエラーが発生しました: {e}")
```
- デバッグ用の設定を行います。
- エラー発生時にはログに記録されます。

### 5. 再構築機能
#### UI
```python
def confirm_rebuild():
    """再構築の確認を行うUIを表示"""
    confirm = st.checkbox("再構築が必要な場合、ここにチェックを入れてください")
    if confirm:
        if st.button("再構築を実行"):
            return True
    return False
```
- 再構築が必要かどうかを確認するための UI を提供します。

#### 再構築の実行
```python
if confirm_rebuild():
    try:
        rebuild_project()
    except Exception as e:
        logger.error(f"プロジェクトの再構築中にエラーが発生しました: {e}")
else:
    try:
        display_app()
    except Exception as e:
        logger.error(f"アプリの表示中にエラーが発生しました: {e}")
```
- 再構築が必要な場合、`rebuild_project()` を実行します。
- 再構築が不要な場合、`display_app()` を実行します。

## エラー処理
- 各主要機能において、例外が発生した場合は `logger.error` を使用してエラーメッセージを記録します。

## 注意点
- `setup_sidebar`, `initialize_agent`, `manage_corpus`, `configure_debug`, `rebuild_project`, `display_app` は外部モジュールからインポートされる必要があります。
- 必要に応じて、これらの関数の実装を確認してください。