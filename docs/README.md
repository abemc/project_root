C 📚 ドキュメンテーション

このフォルダには、自立型 LLM システムの設計、実装、ガイドが整理されています。

---

## 🎯 **すぐに始める - 3つの方法**

### ⚡ **方法1: 役割別ダッシュボード（最速・初心者向け）**
👉 **[ドキュメント管理ダッシュボード](DOCUMENTATION_DASHBOARD.md)**

自分の役割を選ぶだけで、必要な資料が一目でわかります。

- ✅ 初心者向けガイド
- ✅ ユーザー向けマニュアル  
- ✅ 運用者向けガイド
- ✅ 開発者向けドキュメント
- ✅ マネージャー向けレポート

**推奨時間**: 5分で必要な資料を発見 🚀

---

### 🔍 **方法2: Web検索（推奨・全員向け）**
👉 **[ドキュメント検索ページ（HTML版）](documents_index.html)**

ブラウザで開いて検索ボックスにキーワードを入力。リアルタイムで結果が絞り込まれます。

**検索例**: `デプロイ`、`セキュリティ`、`API`、`Phase15`

---

### ⌨️ **方法3: コマンドライン検索（技術者向け）**

```bash
# キーワードで検索
python ../../docs_manager.py --search "デプロイ"

# 特定フェーズの資料を表示
python ../../docs_manager.py --phase 15

# ダッシュボード表示
python ../../docs_manager.py --dashboard
```

---

## 📖 **検索ガイド**

さらに詳しい検索方法は **[ドキュメント検索ガイド](DOCUMENTATION_SEARCH_GUIDE.md)** をご覧ください。

---

## 📖 ガイド (Guides)

システムの使用方法と設計思想に関するドキュメント。

### [AUTONOMOUS_LLM_BLUEPRINT.md](guides/AUTONOMOUS_LLM_BLUEPRINT.md)
**自立型 LLM の綜合設計書**
- システムアーキテクチャ
- 自立性の定義と 9 つの判定基準
- 実装方針
- マチュアリティモデル

### [SYSTEM_INTEGRATION_GUIDE.md](guides/SYSTEM_INTEGRATION_GUIDE.md)
**システム統合ガイド**
- コンポーネント統合手順
- 配置戦略
- 設定方法

### [BACKUP_GUIDE.md](guides/BACKUP_GUIDE.md)
**バックアップと復旧ガイド**
- バックアップ戦略
- 復旧手順
- 災害対応

---

## 📊 実装レポート (Reports)

各フェーズの実装結果と検証報告。

### [PHASE1_IMPLEMENTATION_REPORT.md](reports/PHASE1_IMPLEMENTATION_REPORT.md)
**Phase 1: スケジューラー機構 実装レポート**
- ✅ 完了ステータス
- 実装内容:
  - AutomationScheduler（スケジューラー）
  - AutomationEngine（自動改善エンジン）
  - FeedbackTriggerSystem（トリガーシステム）
  - SafetyGate（安全性検証）
- テスト結果: 全項目パス ✅
- パフォーマンス指標

### [PHASE2_IMPLEMENTATION_REPORT.md](reports/PHASE2_IMPLEMENTATION_REPORT.md)
**Phase 2: ロールバック機構 実装レポート**
- ✅ 完了ステータス
- 実装内容:
  - CheckpointVersioning（チェックポイント版管理）
  - NegativeFeedbackDetector（異常検知）
  - ParameterRecovery（パラメータ復旧）
  - RollbackManager（統合管理）
- テスト結果: 全項目パス ✅
- 自動ロールバック動作フロー

### [AUTONOMOUS_LLM_VERIFICATION_REPORT.md](reports/AUTONOMOUS_LLM_VERIFICATION_REPORT.md)
**システム自立性検証レポート**
- 9 つの自立性基準に対する検証結果
- 実装状況の詳細分析
- 改善提案

### [MULTIMODAL_COMPLETION_REPORT.md](reports/MULTIMODAL_COMPLETION_REPORT.md)
**マルチモーダル機能 実装完了レポート**
- マルチモーダル処理の実装
- 機能検証結果
- パフォーマンス測定

---

---

## 🗂️ サイドドキュメント・ナビゲーション

初心者・自己学習者向けに、特に参照推奨のサイドドキュメントをまとめました。

| ドキュメント | 内容 | 図表・可視化 | 初心者向け要約 |
|---|---|---|---|
| [自律性スコアラー仕様書](../docs/01_仕様書/自律性スコアラー仕様書.md) | エージェント自律性の定量評価 | Mermaid/HTML図あり | あり |
| [RAG仕組み完全ガイド](04_技術ドキュメント/RAG仕組み完全ガイド.md) | RAGの全体像・仕組み | フローチャート/マインドマップ | あり |
| [LLM推論エンジン説明](04_技術ドキュメント/LLM推論エンジン説明.md) | 推論エンジンの設計・動作 | 図解あり | あり |
| [API仕様書](01_仕様書/API仕様書.md) | APIの使い方・仕様 | シーケンス図 | あり |
| [ベクトル化完全ガイド](04_技術ドキュメント/ベクトル化完全ガイド.md) | ベクトルDB・検索 | 構造図 | あり |
| [Phase7設計書](04_技術ドキュメント/Phase7設計書.md) | システム全体設計 | 構成図 | あり |
| [統合ガイド](04_技術ドキュメント/統合ガイド.md) | システム統合手順 | あり | あり |

---

### 📝 初心者向け要約テンプレート例

> **このドキュメントで分かること**
> - 目的・背景
> - 主要な仕組み・流れ（図解付き）
> - よくある質問・つまずきポイント
> - 参考リンク

> **図表例（Mermaid記法）**
> ```mermaid
> flowchart TD
>   A[ユーザー入力] --> B[推論エンジン]
>   B --> C[LLM]
>   C --> D[回答生成]
> ```

---

```
docs/
├── README.md (このファイル)
├── guides/
│   ├── AUTONOMOUS_LLM_BLUEPRINT.md         (システム設計書)
│   ├── SYSTEM_INTEGRATION_GUIDE.md        (統合ガイド)
│   └── BACKUP_GUIDE.md                    (バックアップガイド)
└── reports/
    ├── PHASE1_IMPLEMENTATION_REPORT.md    (Phase 1 レポート)
    ├── PHASE2_IMPLEMENTATION_REPORT.md    (Phase 2 レポート)
    ├── AUTONOMOUS_LLM_VERIFICATION_REPORT.md (検証レポート)
    └── MULTIMODAL_COMPLETION_REPORT.md    (マルチモーダルレポート)
```

---

## 🎯 クイックスタート

### 1. システムを理解したい
→ [AUTONOMOUS_LLM_BLUEPRINT.md](guides/AUTONOMOUS_LLM_BLUEPRINT.md) を読む

### 2. Phase 1 の詳細を知りたい
→ [PHASE1_IMPLEMENTATION_REPORT.md](reports/PHASE1_IMPLEMENTATION_REPORT.md) を読む

### 3. Phase 2 のロールバック機構を理解したい
→ [PHASE2_IMPLEMENTATION_REPORT.md](reports/PHASE2_IMPLEMENTATION_REPORT.md) を読む

### 4. システムを統合したい
→ [SYSTEM_INTEGRATION_GUIDE.md](guides/SYSTEM_INTEGRATION_GUIDE.md) を読む

### 5. バックアップを設定したい
→ [BACKUP_GUIDE.md](guides/BACKUP_GUIDE.md) を読む

---

## 📈 フェーズ進捗

| フェーズ | 内容 | ステータス | レポート |
|---------|------|-----------|---------|
| **Phase 1** | スケジューラー機構 | ✅ 完了 | [Link](reports/PHASE1_IMPLEMENTATION_REPORT.md) |
| **Phase 2** | ロールバック機構 | ✅ 完了 | [Link](reports/PHASE2_IMPLEMENTATION_REPORT.md) |
| **Phase 3** | 自動 A/B テスト | ⏳ 計画中 | - |
| **Phase 4** | ダッシュボード & 監査 | ⏳ 計画中 | - |

---

## 🔗 関連リソース

- **ベースシステム**: `/home/abemc/project_root/src/self_improvement/`
- **テストスイート**: `test_phase1.py`, `test_phase2.py`
- **実装スケジューラー**: `src/self_improvement/scheduler.py`
- **ロールバック機構**: `src/self_improvement/rollback_manager.py`

---

**最終更新**: 2026 年 4 月 11 日  
**システム自立性レベル**: 真の自立型 (完全自律) 🤖
