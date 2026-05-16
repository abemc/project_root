---
## Configurations
---
flowchart TB
    User["User"]
    Dashboard["Dashboard"]
    Admin["Admin"]
    API["API"]
    Agent["Agent"]
    RAG["RAG"]
    Scorer["Scorer"]
    FineTune["FineTune"]
    KB["KB"]
    Model["Model"]
    Feedback["Feedback"]
    Response["Response"]

    User -->|質問を投げかけ| Dashboard
    User -->|管理・設定| Admin
    Dashboard -->|推論リクエスト| API
    Admin -->|設定変更| API
    API -->|クエリ処理| Agent
    Agent -->|検索| RAG
    Agent -->|評価| Scorer
    Agent -->|改善| FineTune
    Agent -.->|RAG経由で利用| KB
    RAG -->|知識ベース検索| KB
    KB -->|関連コンテキスト返却| RAG
    FineTune -->|パラメータ調整| Model
    Agent -->|推論| Model
    Scorer -->|スコア計算| Feedback
    Feedback -->|学習データ| FineTune
    Model -->|出力| Response
    Response -->|表示| Dashboard

    style User fill:#ffffcc
    style Dashboard fill:#ccffff
    style Agent fill:#ffcccc
    style Model fill:#ccccff
    style RAG fill:#ccffcc
    style KB fill:#ccffcc