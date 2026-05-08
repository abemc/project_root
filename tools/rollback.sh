#!/bin/bash
#
# Phase 7 + RAG Agent ロールバックスクリプト
# デプロイを前の状態に戻す
#

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMESTAMP="${1:-}"

if [ -z "$TIMESTAMP" ]; then
    echo "使用方法: ./rollback.sh <TIMESTAMP>"
    echo ""
    echo "例: ./rollback.sh 20260412_152030"
    echo ""
    echo "利用可能なバックアップ:"
    ls -d "$PROJECT_ROOT/backups/deploy_"* 2>/dev/null | tail -5 | while read dir; do
        echo "  - $(basename $dir)"
    done
    exit 1
fi

BACKUP_DIR="$PROJECT_ROOT/backups/deploy_$TIMESTAMP"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ バックアップが見つかりません: $BACKUP_DIR"
    exit 1
fi

echo "=================================================="
echo "  Phase 7 + RAG Agent ロールバックスクリプト"
echo "=================================================="
echo ""
echo "バックアップから復元: $TIMESTAMP"
echo "バックアップディレクトリ: $BACKUP_DIR"
echo ""

# 確認
read -p "本当にロールバックしますか？ (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "キャンセルしました"
    exit 0
fi

echo ""
echo "【復元処理実行中】"

# 復元対象ファイル
RESTORE_FILES=(
    "agent.py"
    "domain_knowledge.py"
    "query_preprocessor.py"
)

for file in "${RESTORE_FILES[@]}"; do
    if [ -f "$BACKUP_DIR/$file" ]; then
        case "$file" in
            "agent.py")
                cp "$BACKUP_DIR/$file" "$PROJECT_ROOT/src/rag/agent.py"
                echo "  ✅ 復元: src/rag/agent.py"
                ;;
            "domain_knowledge.py")
                cp "$BACKUP_DIR/$file" "$PROJECT_ROOT/src/self_improvement/domain_knowledge.py"
                echo "  ✅ 復元: src/self_improvement/domain_knowledge.py"
                ;;
            "query_preprocessor.py")
                cp "$BACKUP_DIR/$file" "$PROJECT_ROOT/src/rag/query_preprocessor.py"
                echo "  ✅ 復元: src/rag/query_preprocessor.py"
                ;;
        esac
    fi
done

echo ""
echo "【ロールバックテスト実行】"

cd "$PROJECT_ROOT"

if "$PROJECT_ROOT/.venv/bin/python" test_phase7.py > /tmp/rollback_test.log 2>&1; then
    echo "  ✅ テスト通過"
else
    echo "  ❌ テスト失敗："
    tail -20 /tmp/rollback_test.log
    exit 1
fi

echo ""
echo "=================================================="
echo "✅ ロールバック完了！"
echo "=================================================="
echo ""
echo "復元されたファイル:"
echo "  - src/rag/agent.py"
echo "  - src/self_improvement/domain_knowledge.py"
echo "  - src/rag/query_preprocessor.py"
echo ""
echo "対応が必要な場合は、サポートにお問い合わせください"
echo ""
