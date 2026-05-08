"""テストスクリプト: 自立型LLM自己改善機能

このスクリプトで各モジュールの基本機能をテストできます。
"""

import sys
import json
from pathlib import Path

# モジュールをインポート
try:
    from src.self_improvement import (
        FeedbackManager,
        PromptOptimizer,
        ContinuousTrainer,
        MetricTracker,
    )
    print("✅ すべてのモジュールが正常にインポートされました")
except ImportError as e:
    print(f"❌ インポートエラー: {e}")
    sys.exit(1)


def test_feedback_manager():
    """FeedbackManager のテスト"""
    print("\n" + "="*60)
    print("🧪 FeedbackManager テスト")
    print("="*60)
    
    mgr = FeedbackManager()
    
    # テストフィードバックを記録
    test_cases = [
        {
            "query": "Pythonのデータ型について教えてください",
            "response": "Pythonには整数（int）、浮動小数点数（float）、文字列（str）などのデータ型があります...",
            "rating": 0.9,
            "tags": ["正確性", "わかりやすさ"],
            "suggestions": "例をもっと追加してください"
        },
        {
            "query": "機械学習と整数プログラミングの違いは？",
            "response": "機械学習は...",
            "rating": 0.6,
            "tags": ["不完全", "複雑すぎる"],
            "suggestions": "もっと簡潔に説明してください"
        },
        {
            "query": "Web開発の最新トレンドを教えてください",
            "response": "2024年のWeb開発では、AI統合、エッジコンピューティング、がトレンドです...",
            "rating": 0.85,
            "tags": ["正確性", "有用性"],
            "suggestions": None
        }
    ]
    
    for case in test_cases:
        feedback = mgr.record_feedback(
            user_query=case["query"],
            model_response=case["response"],
            rating=case["rating"],
            tags=case["tags"],
            suggestions=case["suggestions"]
        )
        print(f"✅ フィードバック記録: {feedback.id} (rating: {feedback.rating})")
    
    # 統計取得
    stats = mgr.get_summary_stats()
    print(f"\n📊 統計:")
    print(f"   総フィードバック数: {stats['total_count']}")
    print(f"   平均評価: {stats['average_rating']:.2%}")
    print(f"   中央値: {stats['median_rating']:.2%}")
    print(f"   標準偏差: {stats['std_rating']:.4f}")
    
    # 改善領域
    improvement_areas = mgr.get_improvement_areas()
    print(f"\n🎯 改善領域: {improvement_areas}")
    
    # 最近のフィードバック
    recent = mgr.get_recent_feedback(2)
    print(f"\n📝 最近のフィードバック: {len(recent)}件")
    
    return "✅ PASSED"


def test_prompt_optimizer():
    """PromptOptimizer のテスト"""
    print("\n" + "="*60)
    print("🧪 PromptOptimizer テスト")
    print("="*60)
    
    opt = PromptOptimizer()
    
    # テンプレートの登録
    print("\n1️⃣ テンプレート管理:")
    templates = opt.list_templates()
    print(f"✅ 登録テンプレート数: {len(templates)}")
    for t in templates[:2]:
        print(f"   - {t['name']}: {t['description']} (使用: {t['usage_count']})")
    
    # プロンプトのフォーマット処理
    print("\n2️⃣ プロンプトフォーマット処理:")
    query = "Pythonのリスト内包表記の使い方を教えてください"
    context = "Pythonの基本的なデータ構造"
    
    system_prompt, user_prompt = opt.format_prompt(
        query=query,
        template_name="best",
        context=context
    )
    
    print(f"✅ システムプロンプト: {system_prompt[:60]}...")
    print(f"✅ ユーザープロンプト: {user_prompt[:80]}...")
    
    #テンプレート性能更新
    print("\n3️⃣ テンプレート性能更新:")
    opt.update_template_performance("best", 0.85)
    best = opt.get_best_template()
    print(f"✅ 最高性能テンプレート: {best.name}")
    print(f"   平均評価: {best.average_rating:.2%}")
    print(f"   使用回数: {best.usage_count}")
    
    # カスタムテンプレート登録
    print("\n4️⃣ カスタムテンプレット登録:")
    custom = opt.register_template(
        name="test_template",
        template="Context: {context}\n\nQuestion: {query}\n\nPlease respond:",
        system_prompt="You are a helpful assistant.",
        description="Test template"
    )
    print(f"✅ 新テンプレット登録: {custom.name}")
    
    return "✅ PASSED"


def test_metric_tracker():
    """MetricTracker のテスト"""
    print("\n" + "="*60)
    print("🧪 MetricTracker テスト")
    print("="*60)
    
    tracker = MetricTracker()
    
    # テストデータを記録
    print("\n1️⃣ メトリクススナップショット記録:")
    for i in range(3):
        snapshot = tracker.record_snapshot(
            feedback_count=20 + i*10,
            average_rating=0.65 + i*0.05,
            training_steps=i*100,
            model_loss=0.5 - i*0.05,
            improvement_percentage=5.0 + i*2
        )
        print(f"✅ スナップショット {i+1}: rating={snapshot.average_rating:.2%}")
    
    # ダッシュボード取得
    print("\n2️⃣ ダッシュボード生成:")
    dashboard = tracker.get_dashboard()
    print(f"✅ 現在の評価: {dashboard['current']['average_rating']:.2%}")
    print(f"✅ 品質傾向: {dashboard['current']['response_quality_trend']}")
    print(f"✅ 改善率: {dashboard['statistics']['rating_improvement_percent']:.1f}%")
    
    # 推奨アクション
    print("\n3️⃣ 推奨アクション:")
    for rec in dashboard['recommendations'][:3]:
        print(f"   💡 {rec}")
    
    # レポート生成
    print("\n4️⃣ Markdownレポート:")
    report = tracker.export_metrics()
    print("✅ レポート生成成功")
    print(f"   長さ: {len(report)}文字")
    
    return "✅ PASSED"


def test_archive_functionality():
    """アーカイブ機能のテスト"""
    print("\n" + "="*60)
    print("🧪 アーカイブ機能 テスト")
    print("="*60)
    
    tracker = MetricTracker()
    
    # テストデータを大量に記録
    print("\n1️⃣ テストデータ記録:")
    for i in range(30):
        tracker.record_snapshot(
            feedback_count=10 + i,
            average_rating=0.5 + (i * 0.01),
            training_steps=i * 10,
            model_loss=0.5 - (i * 0.01),
            improvement_percentage=i * 0.5
        )
    print(f"✅ {len(tracker.snapshots)}個のスナップショット記録")
    
    # アーカイブ情報取得
    print("\n2️⃣ アーカイブ情報:")
    info = tracker.get_archive_info()
    print(f"✅ メインファイル: {info['main_file_size_mb']:.2f}MB")
    print(f"✅ アーカイブ数: {info['archive_count']}")
    print(f"✅ 保持期間: {info['retention_days']}日")
    
    # 保持期間ベースのアーカイブテスト
    print("\n3️⃣ 保持期間ベースのアーカイブ:")
    initial_snapshots = len(tracker.snapshots)
    tracker._archive_by_retention()
    print(f"✅ アーカイブ後のスナップショット: {len(tracker.snapshots)}")
    print(f"✅ アーカイブ化: {initial_snapshots - len(tracker.snapshots)}個")
    
    # アーカイブ情報の再取得
    print("\n4️⃣ アーカイブ後の情報:")
    info_after = tracker.get_archive_info()
    print(f"✅ メインファイル: {info_after['main_file_size_mb']:.2f}MB")
    print(f"✅ アーカイブ合計: {info_after['total_archived_size_mb']:.2f}MB")
    print(f"✅ アーカイブ数: {info_after['archive_count']}")
    
    # クリーンアップテスト
    print("\n5️⃣ 古いアーカイブのクリーンアップ:")
    tracker._cleanup_old_archives()
    info_cleaned = tracker.get_archive_info()
    print(f"✅ クリーンアップ後のアーカイブ数: {info_cleaned['archive_count']}")
    
    return "✅ PASSED"


def test_continuous_trainer():
    """ContinuousTrainer のテスト（基本機能のみ）"""
    print("\n" + "="*60)
    print("🧪 ContinuousTrainer テスト")
    print("="*60)
    
    print("\n⚠️ 注意: このテストはモデルが利用可能な場合のみ実行可能です")
    print("   完全なテストには torch.nn.Module が必要です")
    
    # テスト用のダミーモデル
    import torch
    import torch.nn as nn
    
    class DummyModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = nn.Embedding(100, 10)
            self.linear = nn.Linear(10, 100)
        
        def forward(self, x):
            x = self.embedding(x)
            return self.linear(x)
    
    model = DummyModel()
    trainer = ContinuousTrainer(model=model)
    
    print("\n1️⃣ トレーナー初期化:")
    print(f"✅ 現在のステップ: {trainer.current_step}")
    print(f"✅ 保存ディレクトリ: {trainer.storage_dir}")
    
    # 訓練統計取得
    print("\n2️⃣ 訓練統計:")
    stats = trainer.get_training_stats()
    print(f"✅ 総ステップ: {stats['total_steps']}")
    print(f"✅ チェックポイント数: {stats['checkpoints_count']}")
    
    # 訓練トリガー判定
    print("\n3️⃣ 訓練トリガー判定:")
    test_feedback = [
        {"rating": 0.8},
        {"rating": 0.75},
        {"rating": 0.9},
    ]
    should_train = trainer.should_trigger_training(test_feedback, threshold=2)
    print(f"✅ 訓練実行: {should_train}")
    
    return "✅ PASSED"


def test_integration():
    """統合テスト"""
    print("\n" + "="*60)
    print("🧪 統合テスト")
    print("="*60)
    
    print("\n1️⃣ 全モジュール相互作用:")
    
    feedback_mgr = FeedbackManager()
    prompt_opt = PromptOptimizer()
    metrics = MetricTracker()
    
    query = "質問テスト"
    response = "回答テスト"
    
    # フィードバック記録
    feedback = feedback_mgr.record_feedback(
        user_query=query,
        model_response=response,
        rating=0.8,
        tags=["テスト"],
        suggestions="改善案"
    )
    print(f"✅ フィードバック記録")
    
    # テンプレート性能更新
    prompt_opt.update_template_performance("default", 0.8)
    print(f"✅ プロンプト性能更新")
    
    # メトリクス記録
    stats = feedback_mgr.get_summary_stats()
    metrics.record_snapshot(
        feedback_count=stats["total_count"],
        average_rating=stats["average_rating"],
        training_steps=0,
        model_loss=0.2,
        improvement_percentage=5.0
    )
    print(f"✅ メトリクス記録")
    
    # ダッシュボード確認
    dashboard = metrics.get_dashboard()
    assert dashboard["current"]["average_rating"] > 0
    print(f"✅ ダッシュボード生成")
    
    return "✅ PASSED"


def main():
    """メインテスト関数"""
    print("\n")
    print("🚀 自立型LLM自己改善システム テスト")
    print("="*60)
    
    tests = [
        ("FeedbackManager", test_feedback_manager),
        ("PromptOptimizer", test_prompt_optimizer),
        ("MetricTracker", test_metric_tracker),
        ("アーカイブ機能", test_archive_functionality),
        ("ContinuousTrainer", test_continuous_trainer),
        ("統合テスト", test_integration),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ エラー: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, f"❌ FAILED: {e}"))
    
    # テスト結果サマリー
    print("\n" + "="*60)
    print("📋 テスト結果サマリー")
    print("="*60)
    
    passed = sum(1 for _, r in results if "PASSED" in r)
    total = len(results)
    
    for name, result in results:
        status = "✅" if "PASSED" in result else "❌"
        print(f"{status} {name}: {result}")
    
    print(f"\n📊 合計: {passed}/{total} テスト成功")
    
    if passed == total:
        print("\n🎉 すべてのテストが成功しました！")
        return 0
    else:
        print(f"\n⚠️ {total - passed} 件のテストが失敗しました")
        return 1


if __name__ == "__main__":
    sys.exit(main())
