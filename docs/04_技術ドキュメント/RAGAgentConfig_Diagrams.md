# RAGAgentConfig - 構成図とフロー図

## 1. クラス構造図

```mermaid
classDiagram
    class RAGAgentConfig {
        - config_dir: Path
        - config_file: Path
        - backup_dir: Path
        
        + __init__(config_dir: str)
        + load_config() Dict
        + get_default_config() Dict
        + save_config(config: Dict) bool
        + backup_config() Optional[str]
        + restore_config(backup_file: Optional[str]) bool
        + get_backups_list() list
        + export_config(export_path: str) Optional[str]
        + import_config(import_file: str) bool
        + validate_config(config: Dict) tuple
        + get_config_summary() str
    }
    
    note for RAGAgentConfig "RAG Agent の設定を\n一元管理するクラス"
```

---

## 2. メソッドの依存関係図

```mermaid
graph TD
    __init__["__init__<br/>初期化"]
    
    load_config["load_config<br/>設定読み込み"]
    get_default_config["get_default_config<br/>デフォルト取得"]
    save_config["save_config<br/>設定保存"]
    
    backup_config["backup_config<br/>バックアップ作成"]
    restore_config["restore_config<br/>バックアップ復元"]
    get_backups_list["get_backups_list<br/>バックアップ一覧"]
    
    export_config["export_config<br/>エクスポート"]
    import_config["import_config<br/>インポート"]
    
    validate_config["validate_config<br/>設定検証"]
    get_config_summary["get_config_summary<br/>サマリー表示"]
    
    __init__ --> load_config
    load_config --> get_default_config
    
    backup_config --> load_config
    restore_config --> load_config
    restore_config --> save_config
    get_backups_list -.-> backup_config
    
    export_config --> load_config
    import_config --> save_config
    
    validate_config -.-> get_default_config
    get_config_summary --> load_config
    
    style __init__ fill:#e1f5ff
    style load_config fill:#fff9c4
    style get_default_config fill:#fff9c4
    style save_config fill:#fff9c4
    style backup_config fill:#f3e5f5
    style restore_config fill:#f3e5f5
    style get_backups_list fill:#f3e5f5
    style export_config fill:#e8f5e9
    style import_config fill:#e8f5e9
    style validate_config fill:#fce4ec
    style get_config_summary fill:#fce4ec
```

---

## 3. 設定管理のライフサイクル

```mermaid
graph TD
    A["🚀 アプリケーション起動"]
    B["RAGAgentConfig<br/>インスタンス作成"]
    C{"設定ファイル<br/>存在確認"}
    D["📂 load_config<br/>ファイルから読み込み"]
    E["⚙️ get_default_config<br/>デフォルト設定取得"]
    F["✅ 設定をメモリに<br/>ロード"]
    G["🔧 ユーザーが設定<br/>を変更"]
    H{{"検証<br/>必要？"}}
    I["🔍 validate_config<br/>設定検証"]
    J{{"検証<br/>OK？"}}
    K["💾 save_config<br/>ファイルに保存"]
    L{{"バックアップ<br/>作成？"}}
    M["🔐 backup_config<br/>バックアップ作成"]
    N["📊 get_config_summary<br/>サマリー表示"]
    O["✨ 処理完了"]
    
    A --> B
    B --> C
    C -->|Yes| D
    C -->|No| E
    D --> F
    E --> F
    F --> G
    G --> H
    H -->|Yes| I
    H -->|No| K
    I --> J
    J -->|OK| K
    J -->|Error| G
    K --> L
    L -->|Yes| M
    L -->|No| N
    M --> N
    N --> O
    
    style A fill:#e3f2fd
    style B fill:#e3f2fd
    style D fill:#fff9c4
    style E fill:#fff9c4
    style K fill:#fff9c4
    style I fill:#fce4ec
    style M fill:#f3e5f5
    style N fill:#e8f5e9
    style O fill:#c8e6c9
```

---

## 4. ファイルシステム構造

```mermaid
graph TD
    Root["/home/abemc/project_root"]
    RAGConfig["📄 rag_agent_config.py<br/>(RAGAgentConfigクラス)"]
    ConfigDir["📁 config/"]
    ConfigFile["📄 rag_agent_config.json<br/>(設定ファイル)"]
    BackupDir["📁 rag_backups/"]
    Backup1["📄 rag_config_backup_<br/>20260401_120000.json"]
    Backup2["📄 rag_config_backup_<br/>20260402_140500.json"]
    BackupN["📄 ..."]
    
    Root --> RAGConfig
    Root --> ConfigDir
    ConfigDir --> ConfigFile
    ConfigDir --> BackupDir
    BackupDir --> Backup1
    BackupDir --> Backup2
    BackupDir --> BackupN
    
    style Root fill:#e3f2fd,stroke:#1976d2,stroke-width:3px
    style RAGConfig fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    style ConfigDir fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style ConfigFile fill:#ffe0b2,stroke:#e65100,stroke-width:2px
    style BackupDir fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style Backup1 fill:#ffe0b2,stroke:#e65100,stroke-width:1px
    style Backup2 fill:#ffe0b2,stroke:#e65100,stroke-width:1px
    style BackupN fill:#ffe0b2,stroke:#e65100,stroke-width:1px
```

---

## 5. 設定値の流れ

```mermaid
graph LR
    User["👤 ユーザー"]
    UI["🖥️ UI/ダッシュボード"]
    App["📱 アプリケーション"]
    RAGConfig["⚙️ RAGAgentConfig"]
    FileSystem["💾 ファイルシステム"]
    JSON["📄 JSON設定ファイル"]
    
    User -->|設定を入力| UI
    UI -->|設定値をリクエスト| App
    App -->|save_config| RAGConfig
    RAGConfig -->|JSON形式で保存| FileSystem
    FileSystem -->|rag_agent_config.json| JSON
    
    JSON -->|JSON読み込み| FileSystem
    FileSystem -->|ファイル内容| RAGConfig
    RAGConfig -->|load_config| App
    App -->|設定値を表示| UI
    UI -->|設定を表示| User
    
    style User fill:#e1f5fe
    style UI fill:#f3e5f5
    style App fill:#fff9c4
    style RAGConfig fill:#c8e6c9
    style FileSystem fill:#ffccbc
    style JSON fill:#ffe0b2
```

---

## 6. バックアップ・リストア フロー

```mermaid
sequenceDiagram
    participant User as ユーザー
    participant App as アプリケーション
    participant Config as RAGAgentConfig
    participant FS as ファイルシステム
    
    User->>App: バックアップ作成リクエスト
    App->>Config: backup_config()
    Config->>Config: load_config()
    Config->>Config: タイムスタンプ生成
    Config->>FS: バックアップファイル作成
    FS-->>Config: 成功（パス返却）
    Config-->>App: バックアップパス
    App-->>User: ✅ バックアップ完了
    
    User->>App: リストア実行リクエスト
    App->>Config: restore_config(backup_file)
    Config->>FS: バックアップファイル読み込み
    FS-->>Config: JSON内容
    Config->>Config: save_config()
    Config->>FS: 設定ファイル上書き
    FS-->>Config: 成功
    Config-->>App: True
    App-->>User: ✅ リストア完了
```

---

## 7. エラーハンドリング フロー

```mermaid
graph TD
    Start["メソッド実行開始"]
    
    LoadCheck{"ファイル存在確認"}
    LoadOK["ファイル読み込み"]
    LoadError["エラー発生"]
    
    ParseCheck{"JSON解析確認"}
    ParseOK["解析成功"]
    ParseError["パースエラー"]
    
    ValidateCheck{"検証実行"}
    ValidateOK["検証成功"]
    ValidateError["検証エラー"]
    
    Success["✅ 成功"]
    Failure["❌ 失敗"]
    
    Start --> LoadCheck
    LoadCheck -->|Yes| LoadOK
    LoadCheck -->|No| LoadError
    LoadOK --> ParseCheck
    LoadError --> Failure
    ParseCheck -->|OK| ParseOK
    ParseCheck -->|Error| ParseError
    ParseOK --> ValidateCheck
    ParseError --> Failure
    ValidateCheck -->|OK| ValidateOK
    ValidateCheck -->|Error| ValidateError
    ValidateOK --> Success
    ValidateError --> Failure
    
    style Start fill:#e3f2fd
    style LoadOK fill:#c8e6c9
    style ParseOK fill:#c8e6c9
    style ValidateOK fill:#c8e6c9
    style Success fill:#81c784,stroke:#2e7d32,stroke-width:2px
    style LoadError fill:#ffcdd2
    style ParseError fill:#ffcdd2
    style ValidateError fill:#ffcdd2
    style Failure fill:#e53935,stroke:#b71c1c,stroke-width:2px
```

---

## 8. app.py との連携図

```mermaid
graph TD
    App["📱 app.py<br/>Streamlit Application"]
    Sidebar["🎨 Sidebar UI<br/>サイドバー設定"]
    Display["📊 Display App<br/>メイン画面"]
    
    RAGConfig["⚙️ RAGAgentConfig<br/>設定管理"]
    Retriever["🔍 Retriever<br/>ドキュメント検索"]
    LLM["🤖 LLM Module<br/>言語モデル"]
    BackupManager["💾 ProjectBackupManager<br/>プロジェクト全体バックアップ"]
    
    App --> Sidebar
    App --> Display
    
    Sidebar -->|基本設定| RAGConfig
    Sidebar -->|検索設定| RAGConfig
    Sidebar -->|マルチモーダル設定| RAGConfig
    Sidebar -->|バックアップ作成| RAGConfig
    Sidebar -->|バックアップリストア| RAGConfig
    
    Sidebar -->|コーパス管理| Retriever
    Sidebar -->|バックアップ/リストア| BackupManager
    
    Display -->|設定読み込み| RAGConfig
    Display -->|クエリ処理| LLM
    Display -->|ドキュメント検索| Retriever
    
    LLM -->|設定参照| RAGConfig
    Retriever -->|設定参照| RAGConfig
    
    style App fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style Sidebar fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style Display fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    style RAGConfig fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    style Retriever fill:#ffe0b2,stroke:#e65100,stroke-width:2px
    style LLM fill:#ffccbc,stroke:#bf360c,stroke-width:2px
    style BackupManager fill:#f8bbd0,stroke:#c2185b,stroke-width:2px
```

---

## 9. データフォーマット - デフォルト設定構造

```mermaid
graph TD
    Config["rag_agent_config.json"]
    
    Version["version: string<br/>1.0"]
    Created["created: datetime<br/>ISO形式"]
    
    LLM["llm_model: string<br/>GPT-4o"]
    SearchMethod["search_method: string<br/>ハイブリッド"]
    Language["language: string<br/>ja"]
    
    TopK["top_k: integer<br/>5"]
    Confidence["confidence_threshold: float<br/>0.7"]
    Categories["document_categories: list<br/>root, reports, guides"]
    
    Cache["enable_cache: boolean<br/>true"]
    CacheTTL["cache_ttl: integer<br/>3600"]
    MaxTokens["max_tokens: integer<br/>2000"]
    Temperature["temperature: float<br/>0.7"]
    
    SystemPrompt["system_prompt: string<br/>プロンプト定義"]
    Attribution["enable_source_attribution: boolean<br/>true"]
    FollowUp["enable_follow_up_questions: boolean<br/>true"]
    
    BackupLoc["backup_location: string<br/>/mnt/d/backups"]
    LastModified["last_modified: datetime<br/>ISO形式"]
    
    Config --> Version
    Config --> Created
    Config --> LLM
    Config --> SearchMethod
    Config --> Language
    Config --> TopK
    Config --> Confidence
    Config --> Categories
    Config --> Cache
    Config --> CacheTTL
    Config --> MaxTokens
    Config --> Temperature
    Config --> SystemPrompt
    Config --> Attribution
    Config --> FollowUp
    Config --> BackupLoc
    Config --> LastModified
    
    style Config fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    style Version fill:#fff9c4
    style Created fill:#fff9c4
    style LLM fill:#ffe0b2
    style SearchMethod fill:#ffe0b2
    style Language fill:#ffe0b2
    style TopK fill:#ffccbc
    style Confidence fill:#ffccbc
    style Categories fill:#ffccbc
    style Cache fill:#f3e5f5
    style CacheTTL fill:#f3e5f5
    style MaxTokens fill:#f3e5f5
    style Temperature fill:#f3e5f5
    style SystemPrompt fill:#bbdefb
    style Attribution fill:#bbdefb
    style FollowUp fill:#bbdefb
    style BackupLoc fill:#c8e6c9
    style LastModified fill:#c8e6c9
```

---

## 10. 検証ロジック フロー

```mermaid
graph TD
    Start["validate_config実行"]
    
    SubCheck1["必須フィールド確認"]
    Field1{"llm_model?"}
    Field2{"search_method?"}
    Field3{"top_k?"}
    Field4{"confidence_threshold?"}
    Field5{"temperature?"}
    
    RangeCheck["値の範囲チェック"]
    Range1{"top_k<br/>1-50範囲？"}
    Range2{"confidence<br/>0-1範囲？"}
    Range3{"temperature<br/>0-2範囲？"}
    
    Result["結果判定"]
    ErrorsExist{"エラー<br/>あり？"}
    
    ReturnOK["return True, []"]
    ReturnError["return False,<br/>error_list"]
    
    Start --> SubCheck1
    SubCheck1 --> Field1
    Field1 -->|No| ReturnError
    Field1 -->|Yes| Field2
    Field2 -->|No| ReturnError
    Field2 -->|Yes| Field3
    Field3 -->|No| ReturnError
    Field3 -->|Yes| Field4
    Field4 -->|No| ReturnError
    Field4 -->|Yes| Field5
    Field5 -->|No| ReturnError
    Field5 -->|Yes| RangeCheck
    
    RangeCheck --> Range1
    Range1 -->|No| ReturnError
    Range1 -->|Yes| Range2
    Range2 -->|No| ReturnError
    Range2 -->|Yes| Range3
    Range3 -->|No| ReturnError
    Range3 -->|Yes| Result
    
    Result --> ErrorsExist
    ErrorsExist -->|No| ReturnOK
    ErrorsExist -->|Yes| ReturnError
    
    style Start fill:#e3f2fd
    style SubCheck1 fill:#fff9c4
    style RangeCheck fill:#fff9c4
    style Result fill:#f3e5f5
    style ReturnOK fill:#81c784,stroke:#2e7d32,stroke-width:2px
    style ReturnError fill:#e53935,stroke:#b71c1c,stroke-width:2px
```

---

**図作成日**: 2026-04-26  
**バージョン**: 1.0
