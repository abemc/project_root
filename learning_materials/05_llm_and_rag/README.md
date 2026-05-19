# RAG デモ (学習用) — README

このディレクトリは小規模な RAG（Retrieval-Augmented Generation）学習教材です。目的は埋め込み→検索→生成の基本ワークフローを学ぶことです。

コンテンツ:

- `rag_demo.ipynb` : インタラクティブな Jupyter ノートブックのテンプレート。埋め込み作成と簡易検索、LLM 呼び出しのプレースホルダを含みます。
- `exercises.md` : 演習問題
- `solutions.md` : 演習の模範解答（簡潔）
- `../../scripts/rag_faiss_example.py` : 小さなコマンドライン例（Faiss を使ったインデックス作成と検索）

依存 (例):

```
pip install sentence-transformers faiss-cpu numpy
```

ノート:

- 実際に OpenAI / Hugging Face の LLM と連携する場合、APIキーを環境変数に設定してからノートブック内のプレースホルダを置き換えてください。
- 大規模データを扱うときは Faiss や動的なチャンク化が必要です。
# 05_llm_and_rag

目的: Transformer と注意機構の直感的理解、簡単な RAG（Retrieval-Augmented Generation）パイプラインの実装練習。

チェックポイント:
- 注意機構の Jupyter ノートを読み、各セルを実行して理解すること
- 小さな RAG デモ（ローカル埋め込み + 検索 + LLM 呼び出し）を作ること

既存ノート:
- `03_Jupyter_Notebook_Attention.ipynb`（attention_mechanism の既存ノートをここに移動）
