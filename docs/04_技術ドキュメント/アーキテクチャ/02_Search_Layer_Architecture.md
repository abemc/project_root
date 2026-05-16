# 検索層の詳細構造

## 概要
マルチソース検索の内部メカニズムを詳細に表示します。

```mermaid
flowchart TD
    A["Query Input"] --> B["Embedding<br/>BGE-M3"]
    
    B --> C["FAISS Index<br/>Local Search"]
    B --> D["Web Search<br/>API"]
    
    C --> E["Top-K Results"]
    D --> F["Web Results"]
    
    E --> G["Merge Results"]
    F --> G
    
    G --> H["Re-ranker<br/>Score Norm"]
    H --> I["Deduplicate"]
    I --> J["Threshold Filter"]
    
    J --> K["Knowledge Fusion<br/>Multi-Domain"]
    K --> L["Final Results"]
    
    style B fill:#fff3e0
    style C fill:#f3e5f5
    style D fill:#c8e6c9
    style H fill:#ffe0b2
    style K fill:#e1bee7
```

## コンポーネント説明

### Local Retriever
- **FAISS Index**: ベクトル検索エンジン
- **Corpus Manager**: ドキュメント管理
- **Embedding Model**: BGE-M3で埋め込み生成

### Web Search
- **Online Query**: インターネット検索
- **Result Aggregation**: 結果の集約

### Re-ranking & Filtering
- **Score Normalization**: スコアを0-1に正規化
- **Duplicate Removal**: 重複を除去
- **Threshold Filtering**: 閾値以下は除外

### Knowledge Fusion
- **Multi-Domain Recognition**: ドメイン認識
- **Context Merging**: 文脈統合

## パフォーマンス指標

- ✅ FAISS検索: O(log N)
- ✅ Re-ranking: O(M log M) (M=候補数)
- ✅ 推奨Top-K: 5-10
