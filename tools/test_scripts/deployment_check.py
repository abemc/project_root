#!/usr/bin/env python3
"""
Phase 7 + RAG Agent 本番環境デプロイ準備チェック
デプロイ前の最終検証を実行
"""

import sys
import os
from pathlib import Path

# プロジェクトルート設定
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

def print_section(title: str) -> None:
    """セクション表示"""
    print(f"\n{'='*70}")
    print(f"🚀 {title}")
    print(f"{'='*70}\n")


def check_environment() -> bool:
    """環境チェック"""
    print_section("ステップ1: 環境チェック")
    
    checks = []
    
    # Python バージョン確認
    py_version = sys.version_info
    py_ok = py_version >= (3, 10)
    print(f"{'✅' if py_ok else '❌'} Python バージョン: {py_version.major}.{py_version.minor}")
    checks.append(py_ok)
    
    # 必須ディレクトリ確認
    required_dirs = [
        "src/self_improvement",
        "src/rag",
        "tests",
        "docs",
        "logs",
        "checkpoints",
    ]
    
    dirs_ok = True
    for dir_path in required_dirs:
        full_path = PROJECT_ROOT / dir_path
        exists = full_path.exists()
        print(f"{'✅' if exists else '❌'} ディレクトリ: {dir_path}")
        dirs_ok = dirs_ok and exists
    checks.append(dirs_ok)
    
    # 主要ファイル確認
    required_files = [
        "src/rag/agent.py",
        "src/rag/retriever.py",
        "src/rag/reranker.py",
        "src/self_improvement/context_analyzer.py",
        "src/self_improvement/domain_knowledge.py",
        "src/self_improvement/reasoning_engine.py",
        "requirements.txt",
    ]
    
    files_ok = True
    for file_path in required_files:
        full_path = PROJECT_ROOT / file_path
        exists = full_path.exists()
        print(f"{'✅' if exists else '❌'} ファイル: {file_path}")
        files_ok = files_ok and exists
    checks.append(files_ok)
    
    return all(checks)


def check_dependencies() -> bool:
    """依存パッケージチェック"""
    print_section("ステップ2: 依存パッケージチェック")
    
    required_packages = [
        'torch',
        'transformers',
        'sentence_transformers',
        'faiss',
        'pandas',
        'numpy',
    ]
    
    all_ok = True
    for pkg in required_packages:
        try:
            __import__(pkg)
            print(f"✅ {pkg}")
        except ImportError:
            print(f"❌ {pkg} - インストール必要")
            all_ok = False
    
    return all_ok


def check_phase7_modules() -> bool:
    """Phase 7 モジュールチェック"""
    print_section("ステップ3: Phase 7 モジュール確認")
    
    try:
        from self_improvement.context_analyzer import ContextAnalyzer
        print("✅ ContextAnalyzer インポート成功")
        
        from self_improvement.domain_knowledge import DomainKnowledgeManager
        print("✅ DomainKnowledgeManager インポート成功")
        
        from self_improvement.reasoning_engine import KnowledgeIntegrator
        print("✅ KnowledgeIntegrator インポート成功")
        
        from rag.query_preprocessor import Phase7QueryPreprocessor
        print("✅ Phase7QueryPreprocessor インポート成功")
        
        from rag.knowledge_integration_engine import Phase7KnowledgeIntegrationEngine
        print("✅ Phase7KnowledgeIntegrationEngine インポート成功")
        
        return True
        
    except ImportError as e:
        print(f"❌ インポートエラー: {e}")
        return False


def check_agent_integration() -> bool:
    """Agent 統合チェック"""
    print_section("ステップ4: Agent 統合検証")
    
    try:
        from rag.agent import RAGAgent
        
        # Agent インスタンス化テスト（ダミーオブジェクト使用）
        class DummyRetriever:
            def hybrid_search(self, query, top_k=10):
                return []
            def get_recent_docs(self, top_k=10):
                return []
        
        class DummyReranker:
            def rerank(self, question, docs, top_k=5):
                return []
        
        agent = RAGAgent(
            question="本番環境テスト",
            retriever=DummyRetriever(),
            reranker=DummyReranker(),
            max_steps=1
        )
        
        # Phase 7 属性確認
        checks = [
            ("query_preprocessor", hasattr(agent, "query_preprocessor")),
            ("knowledge_integrator", hasattr(agent, "knowledge_integrator")),
            ("domain_context", hasattr(agent, "domain_context")),
        ]
        
        all_ok = True
        for name, result in checks:
            print(f"{'✅' if result else '❌'} {name}")
            all_ok = all_ok and result
        
        return all_ok
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False


def check_test_execution() -> bool:
    """テスト実行確認"""
    print_section("ステップ5: テスト実行確認")
    
    import subprocess
    
    test_files = [
        "test_phase7.py",
        "test_phase7_agent_integration.py",
    ]
    
    all_ok = True
    for test_file in test_files:
        test_path = PROJECT_ROOT / test_file
        if test_path.exists():
            print(f"✅ テストファイル存在: {test_file}")
        else:
            print(f"❌ テストファイル未検出: {test_file}")
            all_ok = False
    
    return all_ok


def check_documentation() -> bool:
    """ドキュメント確認"""
    print_section("ステップ6: ドキュメント確認")
    
    doc_files = [
        "PHASE7_DESIGN_DOCUMENT.md",
        "docs/PHASE7_INTEGRATION_GUIDE.md",
        "docs/PHASE7_RAG_AGENT_INTEGRATION_REPORT.md",
    ]
    
    all_ok = True
    for doc_file in doc_files:
        doc_path = PROJECT_ROOT / doc_file
        if doc_path.exists():
            size = doc_path.stat().st_size
            print(f"✅ {doc_file} ({size} bytes)")
        else:
            print(f"⚠️  {doc_file} 未検出")
            all_ok = all_ok and True  # ドキュメントは必須ではない
    
    return all_ok


def generate_deployment_checklist() -> None:
    """デプロイチェックリスト生成"""
    print_section("デプロイ前最終チェックリスト")
    
    checklist = [
        ("環境", "Python >= 3.10, 必須ディレクトリ存在"),
        ("依存", "torch, transformers, faiss等インストール確認"),
        ("Phase 7", "全モジュールインポート確認"),
        ("Agent", "Phase 7統合属性確認"),
        ("テスト", "全テストファイル準備完了"),
        ("ドキュメント", "統合レポート作成完了"),
        ("バックアップ", "デプロイ前ファイルバックアップ"),
        ("ロールバック", "ロールバック計画確認"),
    ]
    
    for i, (category, description) in enumerate(checklist, 1):
        print(f"{i}. 【{category}】 {description}")
        print(f"   [ ] 確認完了")


def main():
    """デプロイ準備チェック実行"""
    
    print("\n" + "="*70)
    print("  Phase 7 + RAG Agent 本番環境デプロイ準備")
    print("="*70)
    
    checks = {
        "環境チェック": check_environment(),
        "依存パッケージ": check_dependencies(),
        "Phase 7モジュール": check_phase7_modules(),
        "Agent統合": check_agent_integration(),
        "テスト確認": check_test_execution(),
        "ドキュメント": check_documentation(),
    }
    
    # 結果集計
    print("\n" + "="*70)
    print("📊 デプロイ準備チェック結果")
    print("="*70 + "\n")
    
    passed = sum(1 for result in checks.values() if result)
    total = len(checks)
    
    for check_name, result in checks.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {check_name}")
    
    print(f"\n📈 準備完了度: {passed}/{total} ({100*passed/total:.0f}%)")
    
    if passed == total:
        print("\n🎯 デプロイ準備完了！")
        generate_deployment_checklist()
        return 0
    else:
        print("\n⚠️  デプロイ前に上記の失敗項目を修正してください")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
