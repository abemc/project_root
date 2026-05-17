# ReAct（Reason + Act）ミニ例

概要:
ReAct パターンは「思考（Reason）→行動（Act）」を繰り返すループで、外部ツールを呼び出して観測を得て再計画します。

簡易ループ:
1. 観察: ユーザーの質問や現在の状態を取得
2. 思考: LLM が次の行動（ツール呼び出し／最終回答）を計画
3. 行動: 指定されたツールを実行（例: `search_doc`）
4. 反映: ツール結果を観測として取り込み、次のループへ

例（擬似JSONプラン）:
```
{
  "action": "search_doc",
  "thought": "まず関連文献を取得して要約の根拠を確保する",
  "tool_input": {"query": "Transformer モデルの日本語評価指標"}
}
```

このリポジトリでは `src/rag/agent.py` の `RAGAgent.run_step()` が同様のループを実装しています。簡易デモは `scripts/task_demo.py` を参照してください。
