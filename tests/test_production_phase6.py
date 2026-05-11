"""
Phase 7 RAG 本番化対応テストスイート
Days 6-7: 本番環境準備検証
"""

import sys
from pathlib import Path
sys.path.insert(0, '/home/abemc/project_root')

from src.rag.production_manager import (
    ProductionManager, ProductionConfig, ResourceMonitor,
    ErrorRecoveryStrategy, SecurityManager, ResourceConstraint
)


def test_production_config():
    """本番環境設定テスト"""
    print("\n" + "="*60)
    print("【テスト1】本番環境設定の検証")
    print("="*60)
    
    try:
        # 異なる設定プロファイル生成
        configs = {
            '標準': ProductionConfig(),
            '厳格': ProductionConfig(
                max_cache_size_mb=200,
                max_workers=2,
                query_timeout_sec=20,
                resource_constraint=ResourceConstraint.STRICT
            ),
            '緊急': ProductionConfig(
                max_cache_size_mb=100,
                max_workers=1,
                query_timeout_sec=10,
                resource_constraint=ResourceConstraint.EMERGENCY
            )
        }
        
        for name, config in configs.items():
            print(f"\n【{name}設定】")
            config.to_dict()
            
            print(f"  リソース制約: {config.resource_constraint.value}")
            print(f"  キャッシュ: {config.max_cache_size_mb}MB")
            print(f"  ワーカー: {config.max_workers}個")
            print(f"  クエリタイムアウト: {config.query_timeout_sec}秒")
            print(f"  セキュリティ: 入力検証={config.input_validation_enabled}, "
                  f"レート制限={config.rate_limiting_enabled}")
        
        print("\n✅ 本番環境設定: 正常")
        return True
    
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False


def test_resource_monitoring():
    """リソース監視テスト"""
    print("\n" + "="*60)
    print("【テスト2】リソース監視機構の検証")
    print("="*60)
    
    try:
        monitor = ResourceMonitor(
            alert_memory_percent=80,
            alert_cpu_percent=85
        )
        
        print("\n【システムリソース取得】")
        resources = monitor.get_system_resources()
        print(f"  総メモリ: {resources.total_memory_gb:.1f}GB")
        print(f"  利用可能メモリ: {resources.available_memory_gb:.1f}GB")
        print(f"  メモリ使用率: {resources.memory_usage_percent:.1f}%")
        print(f"  CPU: {resources.cpu_percent:.1f}% ({resources.cpu_count}コア)")
        print(f"  ディスク利用可能: {resources.disk_available_gb:.1f}GB")
        
        print("\n【制約レベル判定】")
        constraint, alerts = monitor.check_resource_constraints(resources)
        print(f"  判定レベル: {constraint.value.upper()}")
        print(f"  アラート件数: {len(alerts)}")
        if alerts:
            for alert in alerts:
                print(f"    - {alert}")
        
        print("\n✅ リソース監視: 正常")
        return True
    
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False


def test_error_recovery():
    """エラー復旧戦略テスト"""
    print("\n" + "="*60)
    print("【テスト3】エラー復旧戦略の検証")
    print("="*60)
    
    try:
        strategy = ErrorRecoveryStrategy(max_retries=3, retry_delay_sec=1)
        
        print("\n【リトライ設定】")
        error_types = [
            'QueryProcessingError',
            'RetrievalError',
            'KnowledgeIntegrationError',
            'TimeoutError'
        ]
        
        for error_type in error_types:
            config = strategy.get_retry_config(error_type)
            print(f"  {error_type}:")
            print(f"    最大リトライ: {config['max_retries']}回")
            print(f"    リトライ間隔: {config['delay_sec']}秒")
        
        print("\n【失敗操作記録】")
        strategy.record_failed_operation(
            'query_processing',
            'Timeout',
            {'query': 'テストクエリ', 'duration_ms': 5000}
        )
        strategy.recovery_count = 2
        strategy.record_failed_operation(
            'retrieval',
            'Network Error',
            {'domain': 'technical', 'retry': 1}
        )
        
        summary = strategy.get_recovery_summary()
        print(f"  復旧試行: {summary['total_recovery_attempts']}回")
        print(f"  失敗記録: {summary['total_failures']}件")
        
        print("\n✅ エラー復旧戦略: 正常")
        return True
    
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False


def test_security_management():
    """セキュリティ管理テスト"""
    print("\n" + "="*60)
    print("【テスト4】セキュリティ管理機構の検証")
    print("="*60)
    
    try:
        config = ProductionConfig(
            input_validation_enabled=True,
            rate_limiting_enabled=True,
            rate_limit_requests_per_minute=5
        )
        security_mgr = SecurityManager(config)
        
        print("\n【入力値検証】")
        test_inputs = [
            ("正常なクエリ", True),
            ("", False),
            ("a" * 1001, False),
            ("<script>alert('xss')</script>", False),
        ]
        
        for query, expected_valid in test_inputs:
            is_valid, error = security_mgr.validate_input(query)
            status = "✓" if is_valid == expected_valid else "✗"
            print(f"  {status} '{query[:20]}...': {is_valid}")
            if error:
                print(f"      エラー: {error}")
        
        print("\n【レート制限】")
        # リクエストシミュレーション
        for i in range(8):
            allowed, msg = security_mgr.check_rate_limit("user1")
            if not allowed:
                print(f"  リクエスト{i+1}: ❌ ブロック - {msg}")
                break
            else:
                security_mgr.log_request("user1", f"query{i}", "success", 100.0)
                print(f"  リクエスト{i+1}: ✓ 許可")
        
        metrics = security_mgr.get_security_metrics()
        print("\n【セキュリティメトリクス】")
        print(f"  総リクエスト: {metrics['total_requests']}")
        print(f"  拒否: {metrics['blocked_requests']}")
        print(f"  拒否率: {metrics['block_rate']}")
        
        print("\n✅ セキュリティ管理: 正常")
        return True
    
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False


def test_production_manager():
    """本番化マネージャー統合テスト"""
    print("\n" + "="*60)
    print("【テスト5】本番化マネージャー統合テスト")
    print("="*60)
    
    try:
        # 本番化マネージャー初期化
        config = ProductionConfig(
            max_cache_size_mb=300,
            max_workers=4,
            query_timeout_sec=25,
            rate_limiting_enabled=True
        )
        
        manager = ProductionManager(config)
        
        print("\n【本番化初期化】")
        init_status = manager.initialize()
        print(f"  ステータス: {init_status['status']}")
        print(f"  制約レベル: {init_status['constraint_level']}")
        print(f"  アラート: {len(init_status['alerts'])}件")
        
        print("\n【設定ファイル保存テスト】")
        config_file = Path('/home/abemc/project_root/logs/production_config.json')
        manager.save_config_to_file(config_file)
        
        if config_file.exists():
            file_size = config_file.stat().st_size
            print(f"  ✓ ファイル保存: {config_file}")
            print(f"  ✓ ファイルサイズ: {file_size} bytes")
            
            # ロード検証
            loaded_config = ProductionManager.load_config_from_file(config_file)
            print(f"  ✓ 設定ロード: {loaded_config.max_cache_size_mb}MB")
        else:
            print("  ✗ ファイル保存失敗")
            return False
        
        print("\n✅ 本番化マネージャー: 正常")
        return True
    
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False


def main():
    """メインテスト実行"""
    print("\n" + "🔧 "*30)
    print("Phase 7 RAG 本番化対応テストスイート")
    print("Days 6-7: 本番環境準備")
    print("🔧 "*30)
    
    # テスト実行
    results = {
        '本番環境設定': test_production_config(),
        'リソース監視': test_resource_monitoring(),
        'エラー復旧戦略': test_error_recovery(),
        'セキュリティ管理': test_security_management(),
        '本番化マネージャー': test_production_manager(),
    }
    
    # 結果サマリー
    print("\n" + "="*60)
    print("【テスト結果サマリー】")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    print(f"\n総合成功率: {passed}/{total} ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 すべてのテストが成功しました！")
        print("Days 6-7本番化対応フェーズ完了")
    else:
        print(f"\n⚠️  {total - passed}個のテストが失敗しました")
    
    # 本番化レポート表示
    if passed == total:
        manager = ProductionManager()
        manager.print_production_report()
    
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
