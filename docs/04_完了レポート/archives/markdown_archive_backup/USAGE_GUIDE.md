"""
Streamlit サイドバー設定永続化システム

使用例と実装ガイド
"""

# ============================================
# 基本的な使い方
# ============================================

"""
1. app.py での統合方法

import streamlit as st
from src.ui import StreamlitSidebarUI

# UI マネージャーの初期化
sidebar_ui = StreamlitSidebarUI(config_dir="config")

# セッション状態に設定を初期化
sidebar_ui.initialize_session_config()

# サイドバーをレンダリング
with st.sidebar:
    st.header("⚙️ 設定・管理")
    
    # 各設定パネルをレンダリング
    basic_config = sidebar_ui.render_basic_settings()
    search_config = sidebar_ui.render_search_settings()
    multimodal_config = sidebar_ui.render_multimodal_settings()
    debug_config = sidebar_ui.render_debug_settings()
    
    # 設定管理パネル
    sidebar_ui.render_config_management()
    
    # すべての設定を保存
    if st.button("💾 設定を保存"):
        sidebar_ui.persist_all_settings(
            basic_config, search_config, 
            multimodal_config, debug_config
        )
        st.success("✅ 設定を保存しました")

# アプリケーション内で設定を使用
llm_model = basic_config["llm_model"]
max_steps = basic_config["max_steps"]
retrieval_top_k = search_config["retrieval_top_k"]
# ... etc
"""


# ============================================
# 機能一覧
# ============================================

"""
✨ SidebarConfigManager の機能:

1. **基本操作**
   - load_config(): 設定ファイルから設定を読み込む
   - save_config(): 設定をファイルに保存
   - reset_to_default(): 設定をデフォルト値にリセット

2. **セクション操作**
   - get_section(section): セクション全体を取得
   - update_section(section, data): セクション全体を更新
   - get_value(section, key): 特定の値を取得
   - update_config(section, key, value): 特定の値を更新

3. **バックアップ管理**
   - list_backups(): バックアップファイルのリストを取得
   - restore_backup(path): バックアップから復元
   - cleanup_old_backups(keep_count): 古いバックアップを削除

4. **インポート・エクスポート**
   - export_config(path): 設定をファイルにエクスポート
   - import_config(path): ファイルから設定をインポート

5. **検証**
   - validate_config(config): 設定の妥当性を検証


✨ StreamlitSidebarUI の機能:

1. **UI レンダリング**
   - render_basic_settings(): 基本設定パネル
   - render_search_settings(): 検索設定パネル
   - render_multimodal_settings(): マルチモーダル設定パネル
   - render_debug_settings(): デバッグ設定パネル
   - render_config_management(): 設定管理パネル

2. **セッション状態管理**
   - initialize_session_config(): セッション状態に設定を初期化
   - get_session_config(section): セッション状態から設定セクションを取得

3. **一括保存**
   - persist_all_settings(basic, search, multimodal, debug): 全設定を保存
"""


# ============================================
# ファイル構成
# ============================================

"""
config/
├── sidebar_config.json          # 現在の設定（ユーザーが保存したもの）
└── backups/
    ├── sidebar_config_20260415_120000.json
    ├── sidebar_config_20260415_100000.json
    └── ...

デフォルトの設定ファイルは以下の構成:

{
  "basic": {
    "llm_model": "qwen2.5:7b",
    "max_steps": 5
  },
  "search": {
    "retrieval_top_k": 5,
    "reranker_model": "BAAI/bge-reranker-base",
    "rerank_top_k": 3,
    "rerank_threshold": 0.1
  },
  "multimodal": {
    "enabled": true,
    "vision_model": "clip",
    "enable_ocr": true,
    "audio_transcription_model": "whisper-small",
    "tts_engine": "edge-tts",
    "supported_languages": ["ja", "en"],
    "show_history": false
  },
  "debug": {
    "show_logs": true,
    "show_memories": true,
    "show_debug": false,
    "auto_train_enabled": false
  },
  "metadata": {
    "created_at": "2026-04-15T12:00:00.000000",
    "updated_at": "2026-04-15T12:00:00.000000",
    "version": "1.0"
  }
}
"""


# ============================================
# 実装アーキテクチャ
# ============================================

"""
┌─────────────────────────────────────────────────┐
│         Streamlit App (app.py)                  │
│  - UI レンダリング                               │
│  - ユーザー入力の処理                             │
└────────────────┬────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────┐
│  StreamlitSidebarUI (streamlit_sidebar_ui.py)   │
│  - UI コンポーネントの抽象化                     │
│  - セッション状態の管理                          │
│  - リアルタイム入出力                           │
└────────────────┬────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────┐
│  SidebarConfigManager (sidebar_config_manager)  │
│  - ファイルI/O                                   │
│  - 設定の検証                                    │
│  - バックアップ管理                              │
└────────────────┬────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────┐
│  config/sidebar_config.json                     │
│  - ユーザー設定の永続化ストレージ                │
└─────────────────────────────────────────────────┘


データフロー:

1. アプリ起動時:
   - app.py → StreamlitSidebarUI.initialize_session_config()
   - StreamlitSidebarUI → SidebarConfigManager.load_config()
   - SidebarConfigManager → config/sidebar_config.json を読み込み
   - セッション状態に設定を格納

2. ユーザーが設定変更時:
   - Streamlit ウィジェットから入力を取得
   - StreamlitSidebarUI が UI ロジックで処理
   - ユーザーが「保存」ボタンをクリック
   - StreamlitSidebarUI → SidebarConfigManager.save_config()
   - SidebarConfigManager:
     a) 既存の設定ファイルをバックアップ
     b) 新しい設定をファイルに保存
   - ユーザーに確認メッセージを表示

3. 復元時:
   - ユーザーが復元したいバックアップを選択
   - SidebarConfigManager.restore_backup(path)
   - 選択したバックアップを読み込んで、新しい設定ファイルとして保存
   - セッション状態を更新
"""


# ============================================
# 実装のポイント
# ============================================

"""
✅ 実装のベストプラクティス:

1. **セッション状態の初期化**
   - アプリ起動時に必ず initialize_session_config() を呼ぶ
   - これにより、既に保存された設定が自動的に読み込まれる

2. **自動保存の検討**
   - render_*_settings() の戻り値から値が変わったら自動保存
   - ただし、頻繁な保存は避ける（例：スライダーの移動中）

3. **バージョン管理**
   - 設定ファイルにバージョンを含める（metadata.version）
   - 将来の設定形式の変更に対応

4. **エラーハンドリング**
   - 設定ファイルが破損した場合はデフォルト設定にフォールバック
   - バックアップから復元できるように

5. **UX 改善**
   - 設定変更が有効になるタイミングを明確に
   - 保存完了後に確認メッセージを表示
   - 復元時は変更内容を確認させる

6. **バックアップ戦略**
   - 古いバックアップは定期的に削除（デフォルト: 最新10個のみ保持）
   - ユーザーが手動でエクスポートできるようにする
"""


# ============================================
# 応用例
# ============================================

"""
1. **ユーザー別の設定管理**
   - ユーザーID ごとに別の設定ファイルを使用
   - config_manager = SidebarConfigManager(f"config/users/{user_id}")

2. **チーム設定のテンプレート**
   - チーム共通の設定テンプレートを用意
   - ユーザーがテンプレートを選択し、カスタマイズ

3. **A/B テスト設定**
   - 異なるグループに異なる設定を自動適用
   - 設定の効果を測定

4. **リアルタイム設定同期**
   - Streamlit のリアルタイムコラボレーション機能と連携
   - 複数のユーザーが同じ設定を共有

5. **設定のバージョン管理**
   - Git リポジトリに設定ファイルをコミット
   - 設定の変更を追跡・ロールバック
"""
