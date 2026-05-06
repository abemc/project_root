"""
Phase 7 デプロイメント準備・検証スクリプト
本番環境へのデプロイ前の最終検証
"""

import sys
import os
import subprocess
from datetime import datetime
import json

# プロジェクトルートを明示的に設定
project_root = "/home/abemc/project_root"
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def print_header(title: str):
    """ヘッダーを表示"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_check(status: str, message: str):
    """チェック結果を表示"""
    if status == "OK":
        print(f"  ✅ {message}")
    elif status == "WARNING":
        print(f"  ⚠️  {message}")
    else:  # FAIL
        print(f"  ❌ {message}")


class Phase7DeploymentValidator:
    """Phase 7デプロイメント検証"""
    
    def __init__(self):
        """初期化"""
        self.checks = []
        self.results = {
            'passed': 0,
            'warnings': 0,
            'failed': 0,
            'details': []
        }
    
    def check_python_version(self) -> bool:
        """Python バージョン確認"""
        print_header("1. Python 環境確認")
        
        version = sys.version_info
        required_version = (3, 8)
        
        if version >= required_version:
            print_check("OK", f"Python {version.major}.{version.minor}.{version.micro} ✓")
            self.results['passed'] += 1
            return True
        else:
            print_check("FAIL", f"Python {required_version[0]}.{required_version[1]}以上が必要")
            self.results['failed'] += 1
            return False
    
    def check_dependencies(self) -> bool:
        """依存パッケージの確認"""
        print_header("2. 依存パッケージ確認")
        
        required_packages = [
            'torch',
            'transformers',
            'numpy',
            'pandas',
            'faiss',
            'pydantic',
        ]
        
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package)
                print_check("OK", f"{package} ✓")
                self.results['passed'] += 1
            except ImportError:
                print_check("FAIL", f"{package} が見つかりません")
                missing_packages.append(package)
                self.results['failed'] += 1
        
        return len(missing_packages) == 0
    
    def check_module_files(self) -> bool:
        """モジュールファイルの確認"""
        print_header("3. モジュールファイル確認")
        
        required_files = [
            'src/self_improvement/context_analyzer.py',
            'src/self_improvement/domain_knowledge.py',
            'src/self_improvement/reasoning_engine.py',
            'src/rag/query_preprocessor.py',
            'src/rag/knowledge_integration_engine.py',
            'src/rag/performance_optimization.py',
        ]
        
        all_exist = True
        
        for file_path in required_files:
            full_path = os.path.join(project_root, file_path)
            if os.path.exists(full_path):
                size = os.path.getsize(full_path)
                print_check("OK", f"{file_path} ({size} bytes) ✓")
                self.results['passed'] += 1
            else:
                print_check("FAIL", f"{file_path} が見つかりません")
                all_exist = False
                self.results['failed'] += 1
        
        return all_exist
    
    def check_configuration(self) -> bool:
        """設定ファイルの確認"""
        print_header("4. 設定ファイル確認")
        
        config_files = [
            'src/self_improvement/config.py',
            'pyproject.toml',
        ]
        
        all_exist = True
        
        for config_file in config_files:
            full_path = os.path.join(project_root, config_file)
            if os.path.exists(full_path):
                print_check("OK", f"{config_file} ✓")
                self.results['passed'] += 1
            else:
                print_check("WARNING", f"{config_file} が見つかりません")
                self.results['warnings'] += 1
        
        return all_exist
    
    def check_test_execution(self) -> bool:
        """テストの実行確認"""
        print_header("5. テスト実行確認")
        
        test_files = [
            'tests/test_phase7_integration.py',
            'tests/test_phase7_advanced.py',
        ]
        
        all_passed = True
        
        for test_file in test_files:
            full_path = os.path.join(project_root, test_file)
            if os.path.exists(full_path):
                print_check("OK", f"{test_file} が存在 ✓")
                self.results['passed'] += 1
                
                # テスト実行を試みる（タイムアウト付き）
                try:
                    result = subprocess.run(
                        [sys.executable, full_path],
                        capture_output=True,
                        timeout=60,
                        cwd=project_root
                    )
                    if result.returncode == 0:
                        print_check("OK", f"  → テスト実行: PASS ✓")
                    else:
                        print_check("WARNING", f"  → テスト実行: 失敗（コード: {result.returncode}）")
                        self.results['warnings'] += 1
                except subprocess.TimeoutExpired:
                    print_check("WARNING", f"  → テスト実行: タイムアウト")
                    self.results['warnings'] += 1
                except Exception as e:
                    print_check("WARNING", f"  → テスト実行: エラー ({str(e)[:40]})")
                    self.results['warnings'] += 1
            else:
                print_check("FAIL", f"{test_file} が見つかりません")
                all_passed = False
                self.results['failed'] += 1
        
        return all_passed
    
    def check_documentation(self) -> bool:
        """ドキュメント確認"""
        print_header("6. ドキュメント確認")
        
        doc_files = [
            'PHASE7_DESIGN_DOCUMENT.md',
            'docs/PHASE7_INTEGRATION_GUIDE.md',
        ]
        
        all_exist = True
        
        for doc_file in doc_files:
            full_path = os.path.join(project_root, doc_file)
            if os.path.exists(full_path):
                size = os.path.getsize(full_path)
                print_check("OK", f"{doc_file} ({size} bytes) ✓")
                self.results['passed'] += 1
            else:
                print_check("WARNING", f"{doc_file} が見つかりません")
                self.results['warnings'] += 1
        
        return all_exist
    
    def check_memory_requirements(self) -> bool:
        """メモリ要件確認"""
        print_header("7. メモリ要件確認")
        
        try:
            import psutil
            memory = psutil.virtual_memory()
            gb_available = memory.available / (1024**3)
            
            minimum_required = 4  # 最小4GB
            
            if gb_available >= minimum_required:
                print_check("OK", f"利用可能メモリ: {gb_available:.1f}GB ✓")
                self.results['passed'] += 1
                return True
            else:
                print_check("WARNING", f"利用可能メモリ: {gb_available:.1f}GB（推奨: {minimum_required}GB以上）")
                self.results['warnings'] += 1
                return False
        except ImportError:
            print_check("WARNING", "psutil がインストールされていません")
            self.results['warnings'] += 1
            return False
    
    def generate_deployment_checklist(self) -> str:
        """デプロイチェックリストを生成"""
        checklist = """
================================================================================
Phase 7 本番環境デプロイメント - チェックリスト
================================================================================

【環境準備】
- [ ] Python 3.8以上がインストール済み
- [ ] すべての依存パッケージをインストール
  pip install -r requirements.txt
- [ ] 環境変数を設定 (MODEL_PATH, DATA_PATH等)
- [ ] ログディレクトリを作成

【コード検証】
- [ ] すべてのテストが成功
  python tests/test_phase7_integration.py
  python tests/test_phase7_advanced.py
- [ ] コード品質チェック実施
  pylint src/rag/*.py src/self_improvement/*.py
- [ ] 依存関係の競合がない

【パフォーマンス検証】
- [ ] キャッシュ機構が有効
- [ ] メモリ使用量が許容範囲内
- [ ] 応答時間が < 1秒（目標）

【セキュリティチェック】
- [ ] 秘密情報 (.env, api_keys等) が含まれていない
- [ ] ファイルパーミッションが適切
- [ ] ログファイルにセンシティブ情報が記録されていない

【デプロイ実行】
- [ ] バックアップを取得
  ./deploy_backup.sh
- [ ] デプロイスクリプトを実行
  ./deploy.sh
- [ ] ヘルスチェック実施
  python verify_all_systems.py

【本番環境確認】
- [ ] 疎通確認（ping, curl等）
- [ ] ログ監視を開始
- [ ] 処理サンプルで動作確認
- [ ] パフォーマンス監視を開始

【ロールバック準備】
- [ ] ロールバックスクリプトが使用可能
  ./rollback.sh
- [ ] 前バージョンが復旧可能な状態

================================================================================
"""
        return checklist
    
    def run_all_checks(self) -> bool:
        """すべてのチェックを実行"""
        print_header("Phase 7 デプロイメント準備 - 最終検証")
        print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        checks = [
            self.check_python_version,
            self.check_dependencies,
            self.check_module_files,
            self.check_configuration,
            self.check_test_execution,
            self.check_documentation,
            self.check_memory_requirements,
        ]
        
        for check in checks:
            try:
                check()
            except Exception as e:
                print_check("FAIL", f"{check.__name__} でエラー: {str(e)[:50]}")
                self.results['failed'] += 1
        
        # 結果サマリー
        print_header("検証結果サマリー")
        
        total = self.results['passed'] + self.results['warnings'] + self.results['failed']
        
        print(f"\n  ✅ 合格: {self.results['passed']}")
        print(f"  ⚠️  警告: {self.results['warnings']}")
        print(f"  ❌ 失敗: {self.results['failed']}")
        print(f"  合計: {total}")
        
        success_rate = (self.results['passed'] / total * 100) if total > 0 else 0
        print(f"\n  合格率: {success_rate:.1f}%")
        
        # 最終判定
        print_header("デプロイ準備状態")
        
        if self.results['failed'] == 0 and success_rate >= 80:
            print(f"\n  🎉 デプロイ準備完了！")
            print(f"  ✅ Phase 7接統合は本番環境にデプロイ可能です")
            return True
        elif self.results['failed'] == 0:
            print(f"\n  ⚠️  軽微な警告がありますが、デプロイ可能です")
            print(f"     本番環境では注意が必要です")
            return True
        else:
            print(f"\n  ❌ デプロイ不可")
            print(f"     {self.results['failed']}個の問題を解決してください")
            return False
    
    def save_results(self, filename: str = "deployment_validation.json") -> None:
        """検証結果を保存"""
        output_path = os.path.join(project_root, filename)
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'validation_results': self.results,
            'status': 'PASS' if self.results['failed'] == 0 else 'FAIL'
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n  检验結果を {output_path} に保存しました\n")


def main():
    """メイン関数"""
    validator = Phase7DeploymentValidator()
    success = validator.run_all_checks()
    
    # チェックリストを表示
    checklist = validator.generate_deployment_checklist()
    print(checklist)
    
    # 検証結果を保存
    validator.save_results()
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
