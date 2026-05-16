# 🎯 GitHub Copilot プロジェクト指示書

**プロジェクト**: エンタープライズセキュリティプラットフォーム (Phase 7-10)  
**バージョン**: 1.0  
**最終更新**: 2026-04-17

---

## 📌 基本原則

### 1. **言語設定**
- すべてのコミュニケーション、コメント、ドキュメント、レポートを **日本語** で作成
- コード内のコメントも日本語
- エラーメッセージは適宜日本語化

### 2. **プロジェクト管理方式**
- **Phase ベース段階実装**: Phase 7-10 の段階的完成を管理
- **タスク追跡**: `manage_todo_list` で進捗を常に可視化
- **メモリ活用**: `/memories/repo/` に進捗・完了状況を記録

### 3. **テスト駆動開発**
- **目標**: 全テスト **100% PASS**
- **アプローチ**: テスト失敗 → 原因分析 → 実装修正 → 再テスト → PASS確認
- **失敗許容**: 一時的な失敗は許容するが、最終状態は全 PASS
- **レポート**: 各修正後にテスト結果を確認・報告

---

## 🔧 実装ガイドライン

### コード品質基準
- ✅ テストカバレッジ: **100%**
- ✅ 静的解析: 0 重大脆弱性
- ✅ コンプライアンス: GDPR/CCPA/APPI/PIPL 準拠
- ✅ パフォーマンス: SLA 達成

### ファイル管理
- 実装ファイル: `/src/phase*/` に配置
- テストファイル: `/tests/` に配置
- ドキュメント: `/docs/` に配置
- チェックポイント: `/checkpoints/` に配置

### コード命名規則
- 実装ファイル: `機能_実装.py` または `phase*.py`
- テストファイル: `test_phase*_*.py`
- ドキュメント: `Phase*_実装計画.md` または `*_完了レポート.md`

---

## 📊 ワークフロー

### Step 1: タスク開始
```python
1. manage_todo_list で新規タスク追加
2. 状態を "in-progress" に変更
3. メモリに作業内容を記録
```

### Step 2: 実装・テスト
```python
1. 実装コード作成
2. テスト実行: pytest tests/test_*.py -v
3. テスト失敗時:
   - 失敗原因を特定
   - 該当ファイルを修正
   - 再テスト実行
   - 全 PASS まで繰り返す
```

### Step 3: 完了・レポート
```python
1. manage_todo_list で状態を "completed" に変更
2. メモリに完了状況を記録
3. 完了レポート生成:
   - JSON 形式: PHASE10_DEPLOYMENT_REPORT.json
   - Markdown 形式: PHASE10_FINAL_COMPLETION_REPORT.md
```

### Step 4: プロジェクト整理
プロジェクト完了時に以下を実行：
```bash
1. chmod +x organize_project.sh
2. bash organize_project.sh
# 実装ファイル・テスト・ドキュメントが自動整理される
```

---

## 🎯 テスト修正フロー

### テスト失敗時の対応

**優先度順:**
1. **単体テスト失敗** (Unit Tests)
   - 該当コンポーネント調査
   - メソッド/属性の実装確認
   - デフォルト値・型チェック

2. **統合テスト失敗** (Integration Tests)
   - コンポーネント間のインターフェース確認
   - 非同期処理の整合性確認
   - Mock オブジェクトのシグネチャ確認

3. **ストレステスト失敗** (Stress Tests)
   - タイムアウト値の調整
   - リソース上限の確認
   - パフォーマンス最適化

### 修正手順

```
1. テスト実行結果を分析
   - 失敗箇所の特定
   - 失敗理由の分類 (AttributeError, TypeError, AssertionError等)

2. 該当ファイルを修正
   - 実装ファイルの修正
   - Mock/Fixture の修正
   - テストケース自体の修正（不適切な期待値の場合）

3. 再テスト実行
   - 単一テストで確認: pytest tests/test_*.py::TestClass::test_method
   - 全テストで確認: pytest tests/test_*.py -v

4. PASS 確認後に次へ
```

---

## 📝 レポート生成基準

### 本番デプロイメント完了時

**JSON レポート** (`PHASE10_DEPLOYMENT_REPORT.json`):
```json
{
  "deployment_status": "SUCCESS ✓",
  "start_time": "ISO format",
  "end_time": "ISO format",
  "phase_results": {
    "validation": {...},
    "canary": {...},
    "gradual_*": {...},
    "full": {...}
  },
  "sla_targets": {...},
  "deployment_artifacts": {...}
}
```

**Markdown レポート** (`PHASE10_FINAL_COMPLETION_REPORT.md`):
- プロジェクト統計
- Phase 別実装内容
- テスト実行結果
- 本番デプロイメント結果
- セキュリティ監査結果
- 次のステップ

### レポート更新タイミング
- ✅ 全テスト PASS 達成時
- ✅ 本番デプロイメント完了時
- ✅ プロジェクト整理完了時

---

## 🔐 セキュリティ・コンプライアンスチェック

### 実装時の確認項目
- [ ] 暗号化処理の実装 (AES-256等)
- [ ] 認証・認可の実装
- [ ] インプット検証
- [ ] ログ・監査トレイル
- [ ] エラーハンドリング

### テスト時の確認項目
- [ ] セキュリティテスト: 脅威検出エンジンの動作確認
- [ ] コンプライアンステスト: GDPR/CCPA/APPI準拠確認
- [ ] パフォーマンステスト: SLA 目標達成確認

---

## 💾 メモリ・ドキュメント管理

### メモリ記録場所
- **ユーザーメモリ** (`/memories/`): 全プロジェクト共通パターン
- **リポジトリメモリ** (`/memories/repo/`): このプロジェクト固有情報
  - `/memories/repo/phase10_progress.md` - 進捗状況
  - `/memories/repo/phase*_completion.md` - 各 Phase 完了情報

### 記録する情報
1. **進捗状況**: 実装完成度、テスト成功率
2. **ファイル一覧**: 実装・テスト・ドキュメントファイル数
3. **失敗情報**: テスト失敗原因と修正内容
4. **デプロイ結果**: 本番展開の各フェーズ結果

---

## 📋 チェックリスト: プロジェクト完了

### 実装完了
- [ ] Phase 10 全 4 ステップ実装完了
- [ ] 実装行数: 15,000+ 行達成
- [ ] ファイル: 60+ ファイル作成

### テスト完了
- [ ] 全テスト 117/117 PASS
- [ ] テストカバレッジ: 100%
- [ ] 本番デプロイ前検証: 全項目 OK

### デプロイ完了
- [ ] 5 段階デプロイメント実行
- [ ] SLA 目標達成: 99.99% 稼働率確認
- [ ] セキュリティ監査: 合格

### プロジェクト整理完了
- [ ] `organize_project.sh` 実行完了
- [ ] ファイル整理: src/tests/docs 配下に整理
- [ ] レポート生成: JSON + Markdown 両方作成

---

## 🚀 実装例

### テスト失敗の修正例

**シナリオ**: `test_fido2_registration` が失敗

```
1. テスト実行結果を分析
   TypeError: register_fido2_credential() missing required argument 'device_name'

2. 実装ファイル修正
   src/phase10/next_gen_auth.py の register_fido2_credential()
   → device_name パラメータをデフォルト値と共に追加

3. 再テスト実行
   pytest tests/test_phase10_auth.py::TestFIDO2Registration -v
   → PASS 確認

4. メモリ記録
   /memories/repo/phase10_progress.md に修正内容を追記
```

---

## 📞 困ったときのガイド

### テスト失敗が多い場合
1. 実装ファイルの欠落メソッドをリストアップ
2. Mock/Fixture の定義を確認
3. テスト期待値が妥当か確認

### デプロイメント失敗時
1. 環境設定の確認 (Python, 依存関係等)
2. テストの事前実行確認
3. ロールバック計画の確認

### ファイル整理エラー時
```bash
# organize_project.sh の再実行
chmod +x organize_project.sh
bash organize_project.sh
```

---

## 🎊 サマリー

このプロジェクトでは以下を厳密に守ります：

1. ✅ **日本語**: 全コミュニケーション・出力
2. ✅ **テスト駆動**: 全テスト 100% PASS が目標
3. ✅ **自動整理**: 完了時にプロジェクト自動整理
4. ✅ **詳細レポート**: JSON + Markdown の両方生成
5. ✅ **進捗追跡**: メモリに記録して常に可視化

---

**このファイルは GitHub Copilot Agent のための指示書です。**  
**プロジェクト作業時はこれに従ってください。**

🎯 **目標**: Phase 10 エンタープライズセキュリティプラットフォーム 100% 完成
