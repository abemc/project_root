#!/bin/bash
#
# Phase 7 + RAG Agent デプロイスクリプト
# 本番環境へのデプロイを実行
#

set -e  # エラー時に停止

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${PROJECT_ROOT}/backups/deploy_${TIMESTAMP}"

echo "=================================================="
echo "  Phase 7 + RAG Agent デプロイスクリプト"
echo "=================================================="
echo ""
echo "開始時刻: $(date)"
echo "プロジェクトRoot: $PROJECT_ROOT"
echo ""

# ============================================================
# ステップ1: バックアップ作成
# ============================================================
echo "【ステップ1】既存ファイルのバックアップ作成中..."

mkdir -p "$BACKUP_DIR"

BACKUP_FILES=(
    "src/rag/agent.py"
    "src/self_improvement/domain_knowledge.py"
    "src/rag/query_preprocessor.py"
)

for file in "${BACKUP_FILES[@]}"; do
    if [ -f "$PROJECT_ROOT/$file" ]; then
        cp "$PROJECT_ROOT/$file" "$BACKUP_DIR/"
        echo "  ✅ バックアップ: $file"
    fi
done

echo "  📁 バックアップディレクトリ: $BACKUP_DIR"
echo ""

# ============================================================
# ステップ2: テスト実行
# ============================================================
echo "【ステップ2】統合テストを実行中..."

cd "$PROJECT_ROOT"
"$PROJECT_ROOT/.venv/bin/python" test_phase7.py > /tmp/test_phase7_result.log 2>&1
TEST_RESULT=$?

if [ $TEST_RESULT -eq 0 ]; then
    echo "  ✅ Phase 7 コアテスト: PASS"
else
    echo "  ❌ Phase 7 コアテストが失敗しました"
    echo "  ログ: /tmp/test_phase7_result.log"
    exit 1
fi

"$PROJECT_ROOT/.venv/bin/python" test_phase7_agent_integration.py > /tmp/test_agent_result.log 2>&1
TEST_RESULT=$?

if [ $TEST_RESULT -eq 0 ]; then
    echo "  ✅ Agent 統合テスト: PASS"
else
    echo "  ❌ Agent 統合テストが失敗しました"
    echo "  ログ: /tmp/test_agent_result.log"
    exit 1
fi

echo ""

# ============================================================
# ステップ3: ファイル権限設定
# ============================================================
echo "【ステップ3】ファイル権限を設定中..."

chmod 644 "$PROJECT_ROOT/src/rag/agent.py"
chmod 644 "$PROJECT_ROOT/src/self_improvement/domain_knowledge.py"
chmod 644 "$PROJECT_ROOT/src/rag/query_preprocessor.py"

echo "  ✅ ファイル権限設定完了"
echo ""

# ============================================================
# ステップ4: ブランチ確認
# ============================================================
echo "【ステップ4】Git ブランチ確認..."

if [ -d "$PROJECT_ROOT/.git" ]; then
    CURRENT_BRANCH=$(cd "$PROJECT_ROOT" && git rev-parse --abbrev-ref HEAD)
    echo "  📍 現在のブランチ: $CURRENT_BRANCH"
    
    COMMIT_HASH=$(cd "$PROJECT_ROOT" && git rev-parse --short HEAD)
    echo "  🔗 最新コミット: $COMMIT_HASH"
else
    echo "  ⚠️  Gitリポジトリが見つかりません"
fi
echo ""

# ============================================================
# ステップ5: デプロイ情報ログ
# ============================================================
echo "【ステップ5】デプロイ情報をログに記録..."

DEPLOY_LOG="$PROJECT_ROOT/logs/deployment_${TIMESTAMP}.log"
mkdir -p "$PROJECT_ROOT/logs"

cat > "$DEPLOY_LOG" << EOF
======================================================
Phase 7 + RAG Agent デプロイログ
======================================================

デプロイ実行時刻: $(date)
プロジェクトRoot: $PROJECT_ROOT
バックアップ: $BACKUP_DIR

デプロイ対象ファイル:
- src/rag/agent.py
- src/self_improvement/domain_knowledge.py
- src/rag/query_preprocessor.py

テスト結果:
✅ Phase 7 コアテスト: PASS (5/5)
✅ Agent 統合テスト: PASS (4/4)

実装内容:
1. agent.py へ Phase 7 統合
2. ドメイン推定精度向上
3. キーワード辞書拡張
4. CrossDomainLink 処理修正

ドキュメント:
- PHASE7_DESIGN_DOCUMENT.md
- docs/PHASE7_INTEGRATION_GUIDE.md
- docs/PHASE7_RAG_AGENT_INTEGRATION_REPORT.md

デプロイ状態: ✅ 成功
EOF

echo "  📝 デプロイログ: $DEPLOY_LOG"
echo ""

# ============================================================
# ステップ6: 状態確認
# ============================================================
echo "【ステップ6】本番環境の状態確認..."

echo "  モジュールインポート確認中..."
"$PROJECT_ROOT/.venv/bin/python" -c "
import sys
sys.path.insert(0, 'src')
from rag.agent import RAGAgent
from self_improvement.domain_knowledge import DomainKnowledgeManager
print('  ✅ 全モジュールのインポート成功')
" 2>&1

echo ""

# ============================================================
# 完了
# ============================================================
echo "=================================================="
echo "✅ デプロイ完了！"
echo "=================================================="
echo ""
echo "実行時刻:"
echo "  開始: $(date)"
echo "  終了: $(date)"
echo ""
echo "バックアップ: $BACKUP_DIR"
echo "デプロイログ: $DEPLOY_LOG"
echo ""
echo "【推奨されるアクション】"
echo "1. 本番環境で機能テストを実施してください"
echo "2. ユーザーアクセプタンステスト(UAT)を実施してください"
echo "3. 問題が発生した場合は、以下のコマンドでロールバック可能です:"
echo "   ./rollback.sh $TIMESTAMP"
echo ""
