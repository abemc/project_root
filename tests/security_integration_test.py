"""
Phase 7 セキュリティ統合テスト
RAGAgentにセキュリティ層を統合

機能:
- 入力検証の統合
- アクセス制御の統合
- 監査ログの統合
- エラーハンドリングの統合
"""

import sys
from datetime import datetime
from typing import Dict, Any, Optional

sys.path.insert(0, '/home/abemc/project_root')

from security_hardening import (
    InputValidator,
    AccessController,
    AuditLogger,
    SecureErrorHandler,
    AccessLevel
)


class SecureRAGAgent:
    """セキュリティ統合RAGエージェント"""
    
    def __init__(self):
        self.validator = InputValidator()
        self.access_controller = AccessController()
        self.audit_logger = AuditLogger()
        self.error_handler = SecureErrorHandler()
        
        # テスト用APIキー登録
        self.access_controller.register_api_key(
            api_key="demo_key_12345",
            access_level=AccessLevel.AUTHENTICATED,
            rate_limit=100
        )
    
    def handle_query(
        self,
        query: str,
        domain: str = "general",
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """セキュアなクエリ処理"""
        
        try:
            # ステップ1: 認証
            auth_result = self.access_controller.authenticate(api_key)
            if not auth_result.get("authenticated") and api_key:
                self.audit_logger.log_access(
                    user_id=api_key[:8] if api_key else None,
                    action="query",
                    resource=domain,
                    result="failure",
                    details={"reason": "auth_failed"}
                )
                return {
                    "success": False,
                    "error": "認証に失敗しました"
                }
            
            # ステップ2: レート制限チェック
            if api_key:
                rate_check = self.access_controller.check_rate_limit(
                    api_key=api_key,
                    limit=auth_result.get("rate_limit", 60)
                )
                
                if not rate_check["allowed"]:
                    self.audit_logger.log_access(
                        user_id=api_key[:8],
                        action="query",
                        resource=domain,
                        result="failure",
                        details={"reason": "rate_limit_exceeded"}
                    )
                    return {
                        "success": False,
                        "error": "レート制限を超過しました",
                        "retry_after": rate_check["retry_after"]
                    }
            
            # ステップ3: 入力検証
            validation_result = self.validator.validate_query(query, max_length=1000)
            
            if not validation_result["valid"]:
                self.audit_logger.log_access(
                    user_id=api_key[:8] if api_key else None,
                    action="query",
                    resource=domain,
                    result="failure",
                    details={"reason": "invalid_input", "errors": validation_result["errors"]}
                )
                return {
                    "success": False,
                    "error": "無効なクエリです",
                    "details": validation_result["errors"]
                }
            
            # ステップ4: ドメイン検証
            valid_domains = ["medical", "legal", "general", "technical"]
            if not self.validator.validate_domain(domain, valid_domains):
                self.audit_logger.log_access(
                    user_id=api_key[:8] if api_key else None,
                    action="query",
                    resource=domain,
                    result="failure",
                    details={"reason": "invalid_domain"}
                )
                return {
                    "success": False,
                    "error": "無効なドメインです"
                }
            
            # ステップ5: 成功ログと結果返却
            self.audit_logger.log_access(
                user_id=api_key[:8] if api_key else "anonymous",
                action="query",
                resource=domain,
                result="success",
                details={
                    "query_length": len(query),
                    "sanitized": validation_result["sanitized_query"]
                }
            )
            
            return {
                "success": True,
                "query": validation_result["sanitized_query"],
                "domain": domain,
                "processed_at": datetime.now().isoformat()
            }
        
        except Exception as e:
            return self.error_handler.handle_error(
                e,
                user_facing=True,
                audit_logger=self.audit_logger
            )


def run_integration_tests():
    """セキュリティ統合テストを実行"""
    
    print("\n" + "="*70)
    print("  Phase 7 セキュリティ統合テスト")
    print("="*70 + "\n")
    
    agent = SecureRAGAgent()
    
    # テストケース
    test_cases = [
        {
            "name": "Test 1: 正常なクエリ (認証あり)",
            "query": "医療について教えてください",
            "domain": "medical",
            "api_key": "demo_key_12345",
            "expected": "success"
        },
        {
            "name": "Test 2: SQLインジェクション試行",
            "query": "'; DROP TABLE users; --",
            "domain": "medical",
            "api_key": "demo_key_12345",
            "expected": "failure"
        },
        {
            "name": "Test 3: XSS試行",
            "query": "<script>alert('xss')</script>",
            "domain": "medical",
            "api_key": "demo_key_12345",
            "expected": "failure"
        },
        {
            "name": "Test 4: 無効なAPIキー",
            "query": "医療について",
            "domain": "medical",
            "api_key": "invalid_key_xyz",
            "expected": "failure"
        },
        {
            "name": "Test 5: 無効なドメイン",
            "query": "医療について",
            "domain": "invalid_domain",
            "api_key": "demo_key_12345",
            "expected": "failure"
        },
        {
            "name": "Test 6: 空のクエリ",
            "query": "",
            "domain": "medical",
            "api_key": "demo_key_12345",
            "expected": "failure"
        },
        {
            "name": "Test 7: 認証なしアクセス",
            "query": "一般的な質問です",
            "domain": "general",
            "api_key": None,
            "expected": "success"
        },
    ]
    
    results = []
    passed_count = 0
    
    for i, test in enumerate(test_cases, 1):
        result = agent.handle_query(
            query=test["query"],
            domain=test["domain"],
            api_key=test["api_key"]
        )
        
        test_passed = (result["success"] and test["expected"] == "success") or \
                     (not result["success"] and test["expected"] == "failure")
        
        results.append({
            "test_num": i,
            "name": test["name"],
            "passed": test_passed,
            "success": result["success"]
        })
        
        if test_passed:
            passed_count += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
        
        print(f"{status} {test['name']}")
        if result.get("error"):
            print(f"    → {result['error']}")
    
    # 監査ログを表示
    print("\n【監査ログ (最新5件)】")
    recent_logs = agent.audit_logger.get_recent_logs(limit=5)
    for log in recent_logs[-5:]:
        action_result = "✅" if log.get("result") == "success" else "❌"
        print(f"{action_result} {log['user_id']} | {log['action']} on {log['resource']}")
    
    # 結果サマリー
    print("\n" + "="*70)
    print(f"テスト結果: {passed_count}/{len(test_cases)} PASS ({100*passed_count//len(test_cases)}%)")
    
    if passed_count == len(test_cases):
        print("✅ すべてのセキュリティ統合テストに合格しました")
        print("   本番環境デプロイメント準備完了 🚀")
    else:
        print(f"⚠️  {len(test_cases) - passed_count}件のテストが失敗しました")
    
    print("="*70 + "\n")
    
    return {
        "total_tests": len(test_cases),
        "passed": passed_count,
        "success_rate": f"{100*passed_count//len(test_cases)}%"
    }


if __name__ == "__main__":
    run_integration_tests()
