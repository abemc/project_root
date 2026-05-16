# RAG全体のマインドマップ

## 概要
RAGシステムを9層の階層構造として表示します。

```mermaid
mindmap
  root((RAG System<br/>全体構造))
    入力層
      ユーザークエリ
      会話履歴
      ドメイン情報
    前処理層
      QueryPreprocessor
        ドメイン検出
        意図分析
        隠れた意図発見
      ContextManager
        過去の記憶検索
        ドメイン文脈キャッシュ
    検索層
      Local Search
        FAISS Index検索
        埋め込みモデル
        コーパス管理
      Web Search
        オンラインクエリ
        結果集約
      Re-ranking
        スコア正規化
        重複除去
        閾値フィルタリング
    知識融合層
      KnowledgeIntegration
        マルチドメイン認識
        コンテキスト統合
        優先度付け
    プロンプト構築
      System Prompt
        テンプレート
        設定値
      Context Insertion
        ドキュメント挿入
        クエリ書き直し
    推論層
      LLM Engine
        Tool Selection
        Ollama/OpenAI
        パラメータ調整
    ツール実行
      search_doc
      search_web
      evaluate_docs
      rewrite_query
      python_interpreter
      answer
    出力層
      最終回答生成
      ユーザー出力
      フィードバック収集
    フィードバックループ
      履歴保存
      メモリ更新
      継続改善
```

## 9層の構造詳細

| 層 | 役割 | キーコンポーネント |
|---|----|------------------|
| 1. 入力層 | クエリとコンテキスト受け取り | User I/O |
| 2. 前処理層 | ドメイン・意図分析 | QueryPreprocessor |
| 3. 検索層 | マルチソース検索 | Retriever, Web API |
| 4. 知識融合層 | ドメイン統合 | KnowledgeIntegration |
| 5. プロンプト構築 | LLM用プロンプト生成 | PromptBuilder |
| 6. 推論層 | LLM実行 | LLM Engine |
| 7. ツール実行 | 動的ツール選択・実行 | 6種類のツール |
| 8. 出力層 | 回答生成・出力 | Formatter |
| 9. フィードバック | 学習と改善 | Memory Update |

## システムの特徴

- ✅ 9層の明確な責務分離
- ✅ 各層で異なる処理を実行
- ✅ 層間のデータ流通
- ✅ フィードバックループで継続改善
