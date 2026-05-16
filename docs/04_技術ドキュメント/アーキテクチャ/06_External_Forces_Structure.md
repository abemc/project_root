# 外力（External Forces）の全体構造

## 概要
RAGシステムへの全入力・依存性を表示します。

```mermaid
flowchart TD
    subgraph DS["Data Sources"]
        DS1["Local Corpus<br/>FAISS"]
        DS2["Web Search"]
        DS3["Memory Store"]
        DS4["Configuration"]
    end
    
    subgraph LB["LLM Backends"]
        LB1["Ollama<br/>Local"]
        LB2["OpenAI API"]
        LB3["BGE-M3<br/>Embeddings"]
    end
    
    subgraph PM["Processing"]
        PM1["Tokenizer"]
        PM2["Embedding"]
        PM3["FAISS Search"]
        PM4["Re-ranker"]
    end
    
    subgraph EA["External APIs"]
        EA1["Web API"]
        EA2["Document Parser"]
        EA3["Python Interp"]
    end
    
    subgraph FB["Feedback"]
        FB1["User Rating"]
        FB2["Metrics"]
        FB3["Improvement"]
    end
    
    RAG["RAG Core"]
    
    DS1 -.->|Data| RAG
    DS2 -.->|Data| RAG
    DS3 -.->|Data| RAG
    DS4 -.->|Config| RAG
    LB1 -.->|Compute| RAG
    LB2 -.->|Compute| RAG
    LB3 -.->|Compute| RAG
    PM1 -.->|Process| RAG
    PM2 -.->|Process| RAG
    PM3 -.->|Process| RAG
    PM4 -.->|Process| RAG
    EA1 -.->|Tool| RAG
    EA2 -.->|Tool| RAG
    EA3 -.->|Tool| RAG
    RAG -.->|Output| FB1
    FB1 -.->|Feedback| FB2
    FB2 -.->|Learn| FB3
    FB3 -.->|Improve| RAG
    
    style RAG fill:#e3f2fd,stroke:#1976d2
    style DS fill:#f3e5f5
    style LB fill:#fff3e0
    style PM fill:#f0f4c3
    style EA fill:#ffe0b2
    style FB fill:#c5cae9
```

## 外力の分類

### データ外力 (Data Forces)
- **Local Corpus**: ローカルコーパス (FAISS)
- **Web Search**: インターネット情報
- **Memory Store**: 会話履歴
- **Configuration**: システム設定

### 計算外力 (Computation Forces)
- **Ollama**: ローカルLLMモデル
- **OpenAI API**: クラウドLLMサービス
- **BGE-M3**: 埋め込みモデル

### 処理外力 (Functional Forces)
- **Tokenizer**: テキスト分割
- **Embedding**: ベクトル生成
- **FAISS**: ベクトル検索
- **Re-ranker**: スコア最適化

### API & Tool外力
- **Web API**: Web検索・取得
- **Document Parser**: PDF/画像処理
- **Python Interpreter**: データ分析実行

### フィードバック外力
- **User Feedback**: ユーザー評価
- **Metrics Tracking**: パフォーマンス計測
- **Self-Improvement**: 自動改善

## 依存関係マトリックス

| 外力 | 重要度 | 代替手段 | 冗長性 |
|-----|--------|--------|-------|
| LLM Backend | 🔴必須 | Ollama ↔ OpenAI | ✅ あり |
| Embedding Model | 🔴必須 | BGE-M3 固定 | ❌ なし |
| Local Corpus | 🟡重要 | Web Search | ✅ あり |
| FAISS Search | 🔴必須 | 線形検索 | ✅ あり |
| Web API | 🟡重要 | キャッシュ利用 | ✅ あり |
