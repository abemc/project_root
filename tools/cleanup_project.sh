#!/bin/bash
# Phase 7プロジェクト - フォルダー整理スクリプト
# 肥大化したプロジェクト構造を最適化

PROJECT_ROOT="/home/abemc/project_root"
BACKUP_DIR="$PROJECT_ROOT/backups"
ARCHIVE_DIR="$PROJECT_ROOT/.archive"
SCRIPT_LOG="$PROJECT_ROOT/cleanup_log.txt"

echo "=================================================="
echo "  Project Cleanup & Organization Script"
echo "=================================================="
echo "Start: $(date)" > "$SCRIPT_LOG"
echo "" >> "$SCRIPT_LOG"

# 色の定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SUCCESS_COUNT=0
FREED_SIZE=0

print_status() {
    echo -e "${GREEN}✅${NC} $1"
    echo "✅ $1" >> "$SCRIPT_LOG"
}

print_warning() {
    echo -e "${YELLOW}⚠️ ${NC} $1"
    echo "⚠️  $1" >> "$SCRIPT_LOG"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
    echo "❌ $1" >> "$SCRIPT_LOG"
}

# ================================================
# 1. 不要なフォルダー削除
# ================================================
echo ""
echo "【ステップ1】不要なフォルダー削除"
echo "【ステップ1】不要なフォルダー削除" >> "$SCRIPT_LOG"

# D: フォルダーの削除
if [ -d "$PROJECT_ROOT/D:" ]; then
    SIZE=$(du -sh "$PROJECT_ROOT/D:" | cut -f1)
    rm -rf "$PROJECT_ROOT/D:"
    print_status "D: フォルダー削除完了 (解放: $SIZE)"
    FREED_SIZE=$(echo "$FREED_SIZE + $(du -sh $PROJECT_ROOT/D: 2>/dev/null || echo 0B | cut -d'B' -f1)" | bc)
    ((SUCCESS_COUNT++))
fi

# D:\backups フォルダーの削除
if [ -d "$PROJECT_ROOT/D:\backups" ]; then
    SIZE=$(du -sh "$PROJECT_ROOT/D:\backups" | cut -f1)
    rm -rf "$PROJECT_ROOT/D:\backups"
    print_status "D:\\backups フォルダー削除完了 (解放: $SIZE)"
    ((SUCCESS_COUNT++))
fi

# __pycache__ の全削除
find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
print_status "__pycache__ ディレクトリをクリーンアップ"

# .pytest_cache の削除
find "$PROJECT_ROOT" -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null
print_status ".pytest_cache をクリーンアップ"

# *.pyc ファイルの削除
find "$PROJECT_ROOT" -type f -name "*.pyc" -delete 2>/dev/null
print_status "*.pyc ファイルをクリーンアップ"

((SUCCESS_COUNT++))

# ================================================
# 2. ルートレベルのテストスクリプト整理
# ================================================
echo ""
echo "【ステップ2】ルートレベルのスクリプト整理"
echo "【ステップ2】ルートレベルのスクリプト整理" >> "$SCRIPT_LOG"

TEST_SCRIPTS=(
    "test_phase1.py"
    "test_phase2.py"
    "test_phase3.py"
    "test_phase4.py"
    "test_phase5.py"
    "test_phase6.py"
    "test_phase7.py"
    "fix_all_memory.py"
    "fix_faiss.py"
    "fix_markdown.py"
    "fix_memories.py"
    "test_llm_fix.py"
    "deployment_check.py"
    "production_test_guide.py"
    "demo_reasoning_engine.py"
    "load_prompt.py"
    "build_knowledge.py"
)

for script in "${TEST_SCRIPTS[@]}"; do
    if [ -f "$PROJECT_ROOT/$script" ]; then
        # 移動先フォルダーを決定
        if [[ $script == test_* || $script == fix_* ]]; then
            mkdir -p "$PROJECT_ROOT/tools/test_scripts"
            mv "$PROJECT_ROOT/$script" "$PROJECT_ROOT/tools/test_scripts/"
            print_status "移動: $script → tools/test_scripts/"
        elif [[ $script == build_* ]]; then
            mkdir -p "$PROJECT_ROOT/tools/build"
            mv "$PROJECT_ROOT/$script" "$PROJECT_ROOT/tools/build/"
            print_status "移動: $script → tools/build/"
        elif [[ $script == demo_* ]]; then
            mkdir -p "$PROJECT_ROOT/tools/demos"
            mv "$PROJECT_ROOT/$script" "$PROJECT_ROOT/tools/demos/"
            print_status "移動: $script → tools/demos/"
        else
            mkdir -p "$PROJECT_ROOT/tools/misc"
            mv "$PROJECT_ROOT/$script" "$PROJECT_ROOT/tools/misc/"
            print_status "移動: $script → tools/misc/"
        fi
        ((SUCCESS_COUNT++))
    fi
done

# ================================================
# 3. ルートレベルのドキュメント整理
# ================================================
echo ""
echo "【ステップ3】ドキュメント整理"
echo "【ステップ3】ドキュメント整理" >> "$SCRIPT_LOG"

DOC_FILES=(
    "AI_BEGINNER_GUIDE_SUMMARY.md"
    "LLM_AND_REASONING_ENGINE_EXPLAINED.md"
    "LLM_LEARNING_ROADMAP.md"
    "QUICKSTART_FOR_BEGINNERS.md"
    "LEARNING_INDEX.md"
    "DEPLOYMENT_COMPLETE.md"
    "PHASE7_DESIGN_DOCUMENT.md"
    "OPERATIONAL_START_GUIDE.md"
)

mkdir -p "$PROJECT_ROOT/docs/guides"

for doc in "${DOC_FILES[@]}"; do
    if [ -f "$PROJECT_ROOT/$doc" ]; then
        mv "$PROJECT_ROOT/$doc" "$PROJECT_ROOT/docs/guides/"
        print_status "移動: $doc → docs/guides/"
        ((SUCCESS_COUNT++))
    fi
done

# ================================================
# 4. 学習ガイドの統合
# ================================================
echo ""
echo "【ステップ4】学習ガイドの統合"
echo "【ステップ4】学習ガイドの統合" >> "$SCRIPT_LOG"

if [ -d "$PROJECT_ROOT/📚_学習ガイド" ]; then
    mkdir -p "$PROJECT_ROOT/docs/learning_guide"
    cp -r "$PROJECT_ROOT/📚_学習ガイド"/* "$PROJECT_ROOT/docs/learning_guide/" 2>/dev/null
    print_status "📚_学習ガイド → docs/learning_guide へコピー"
    ((SUCCESS_COUNT++))
fi

# ================================================
# 5. 古いバックアップの圧縮・整理
# ================================================
echo ""
echo "【ステップ5】バックアップの整理"
echo "【ステップ5】バックアップの整理" >> "$SCRIPT_LOG"

if [ -d "$BACKUP_DIR" ]; then
    mkdir -p "$ARCHIVE_DIR"
    
    # 3月以前のバックアップをアーカイブへ移動
    OLD_BACKUPS=$(find "$BACKUP_DIR" -maxdepth 1 -type d -name "20260[12]*" -o -name "20260301*" -o -name "20260302*" 2>/dev/null)
    
    if [ ! -z "$OLD_BACKUPS" ]; then
        echo "$OLD_BACKUPS" | while read backup; do
            if [ -d "$backup" ]; then
                BACKUP_NAME=$(basename "$backup")
                mv "$backup" "$ARCHIVE_DIR/"
                print_status "移動: $BACKUP_NAME → .archive/"
                ((SUCCESS_COUNT++))
            fi
        done
    fi
    
    # 最新の4つのバックアップ以外をアーカイブ
    RECENT_BACKUPS=$(ls -td "$BACKUP_DIR"/20260* 2>/dev/null | head -4)
    for backup in "$BACKUP_DIR"/20260*; do
        if [ -d "$backup" ]; then
            if ! echo "$RECENT_BACKUPS" | grep -q "$(basename $backup)"; then
                BACKUP_NAME=$(basename "$backup")
                mv "$backup" "$ARCHIVE_DIR/" 2>/dev/null
                print_status "アーカイブへ移動: $BACKUP_NAME"
                ((SUCCESS_COUNT++))
            fi
        fi
    done
fi

# ================================================
# 6. 展開ファイルのクリーンアップ
# ================================================
echo ""
echo "【ステップ6】一時ファイル・キャッシュのクリーンアップ"
echo "【ステップ6】一時ファイル・キャッシュのクリーンアップ" >> "$SCRIPT_LOG"

# *.egg-info の削除
find "$PROJECT_ROOT" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null
print_status "*.egg-info をクリーンアップ"

# .egg ファイルの削除
find "$PROJECT_ROOT" -type d -name ".eggs" -exec rm -rf {} + 2>/dev/null
print_status ".eggs をクリーンアップ"

# 空のディレクトリを削除
find "$PROJECT_ROOT" -type d -empty -delete 2>/dev/null
print_status "空のディレクトリを削除"

((SUCCESS_COUNT++))

# ================================================
# 7. 最終的なストレージ状況を確認
# ================================================
echo ""
echo "【最終】ストレージ状況確認"
echo "【最終】ストレージ状況確認" >> "$SCRIPT_LOG"

TOTAL_SIZE=$(du -sh "$PROJECT_ROOT" | cut -f1)
TOP_DIRS=$(du -sh "$PROJECT_ROOT"/* 2>/dev/null | sort -rh | head -10)

echo "ストレージ使用量:"
echo "  合計: $TOTAL_SIZE"
echo ""
echo "大容量ディレクトリ (TOP10):"
echo "$TOP_DIRS" | while read line; do
    echo "  $line"
done

echo ""
echo "✅ クリーンアップ完了！"
echo "  実施タスク: $SUCCESS_COUNT個"
echo ""
echo "End: $(date)" >> "$SCRIPT_LOG"
echo "Successfully completed!" >> "$SCRIPT_LOG"

print_status "ログファイル: $SCRIPT_LOG"
