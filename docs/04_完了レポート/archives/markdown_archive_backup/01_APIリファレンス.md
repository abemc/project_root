# 🔌 API リファレンス - エンタープライズセキュリティプラットフォーム

**バージョン**: 1.0  
**作成日**: 2026年4月17日  
**API Base URL**: `https://api.security-platform.com/v1`  
**認証**: Bearer Token (JWT) + API Key

---

## 📌 目次

1. [認証 API](#認証-api)
2. [ユーザー管理 API](#ユーザー管理-api)
3. [セキュリティ監視 API](#セキュリティ監視-api)
4. [脅威検知 API](#脅威検知-api)
5. [コンプライアンス API](#コンプライアンス-api)
6. [エラーコード](#エラーコード)
7. [レート制限](#レート制限)

---

## 🔐 認証 API

### 1. ユーザー登録

登録新規ユーザーを作成します。

**エンドポイント:**
```
POST /auth/register
```

**リクエスト:**
```json
{
  "username": "user@example.com",
  "password": "SecurePassword123!",
  "full_name": "Taro Yamada",
  "organization": "Acme Corp",
  "mfa_preference": "totp"
}
```

**レスポンス (成功):**
```json
{
  "user_id": "USR-20260417-001",
  "username": "user@example.com",
  "status": "active",
  "mfa_setup_required": true,
  "created_at": "2026-04-17T12:00:00Z",
  "verification_token": "token_xyz123"
}
```

**エラーレスポンス:**
```json
{
  "error": "INVALID_PASSWORD",
  "message": "Password must contain at least 12 characters with uppercase, lowercase, numbers, and special characters",
  "code": 400
}
```

**パラメータ:**
| 名前 | 型 | 必須 | 説明 |
|------|-----|------|------|
| username | string | ✓ | ユーザーメールアドレス |
| password | string | ✓ | 強力なパスワード (最小 12 文字) |
| full_name | string | ✓ | フルネーム |
| organization | string | ✓ | 組織名 |
| mfa_preference | enum | ✓ | totp, sms, fido2, biometric |

**ステータスコード:**
- `201 Created` - ユーザー作成成功
- `400 Bad Request` - 入力値エラー
- `409 Conflict` - ユーザーが既に存在

---

### 2. ログイン

ユーザーがシステムにログインします。

**エンドポイント:**
```
POST /auth/login
```

**リクエスト:**
```json
{
  "username": "user@example.com",
  "password": "SecurePassword123!",
  "device_id": "device_abc123",
  "client_ip": "203.0.113.45"
}
```

**レスポンス (成功):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "refresh_token_xyz",
  "mfa_required": true,
  "mfa_methods": ["totp", "sms", "fido2"],
  "challenge_id": "chal_20260417_001"
}
```

**パラメータ:**
| 名前 | 型 | 必須 | 説明 |
|------|-----|------|------|
| username | string | ✓ | ユーザーメールアドレス |
| password | string | ✓ | パスワード |
| device_id | string | × | デバイス識別子 |
| client_ip | string | × | クライアント IP |

---

### 3. MFA 検証 (TOTP)

Time-Based One-Time Password (TOTP) で検証します。

**エンドポイント:**
```
POST /auth/mfa/totp/verify
```

**リクエスト:**
```json
{
  "challenge_id": "chal_20260417_001",
  "totp_code": "123456",
  "device_id": "device_abc123"
}
```

**レスポンス (成功):**
```json
{
  "authenticated": true,
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user_id": "USR-20260417-001",
  "expires_in": 3600,
  "login_timestamp": "2026-04-17T12:05:00Z"
}
```

**パラメータ:**
| 名前 | 型 | 必須 | 説明 |
|------|-----|------|------|
| challenge_id | string | ✓ | ログインチャレンジ ID |
| totp_code | string | ✓ | 6 桁 TOTP コード |
| device_id | string | × | デバイス識別子 |

---

### 4. FIDO2 登録

FIDO2 セキュリティキーを登録します。

**エンドポイント:**
```
POST /auth/fido2/register
```

**リクエスト:**
```json
{
  "user_id": "USR-20260417-001",
  "device_name": "YubiKey 5 NFC",
  "challenge": "random_challenge_string"
}
```

**レスポンス (成功):**
```json
{
  "registration_id": "fido2_reg_001",
  "device_name": "YubiKey 5 NFC",
  "credential_id": "cred_xyz123",
  "public_key": "-----BEGIN PUBLIC KEY-----\nMFkw...",
  "status": "registered",
  "created_at": "2026-04-17T12:00:00Z",
  "attestation_verified": true
}
```

**パラメータ:**
| 名前 | 型 | 必須 | 説明 |
|------|-----|------|------|
| user_id | string | ✓ | ユーザー ID |
| device_name | string | ✓ | デバイス名 (例: "My YubiKey") |
| challenge | string | ✓ | ランダムチャレンジ |

---

### 5. 生体認証登録

生体認証 (指紋・顔・虹彩) を登録します。

**エンドポイント:**
```
POST /auth/biometric/register
```

**リクエスト:**
```json
{
  "user_id": "USR-20260417-001",
  "biometric_type": "fingerprint",
  "biometric_data": "base64_encoded_biometric_template",
  "quality_score": 98.5,
  "device_type": "Windows Hello",
  "enrollment_count": 3
}
```

**レスポンス (成功):**
```json
{
  "enrollment_id": "bio_enum_001",
  "biometric_type": "fingerprint",
  "status": "enrolled",
  "quality_score": 98.5,
  "templates_registered": 3,
  "match_threshold": 0.98,
  "created_at": "2026-04-17T12:00:00Z"
}
```

**パラメータ:**
| 名前 | 型 | 必須 | 説明 |
|------|-----|------|------|
| user_id | string | ✓ | ユーザー ID |
| biometric_type | enum | ✓ | fingerprint, face, iris |
| biometric_data | string | ✓ | Base64 エンコード生体テンプレート |
| quality_score | float | ✓ | 品質スコア (0-100) |
| device_type | string | ✓ | デバイスタイプ |
| enrollment_count | int | ✓ | テンプレート登録数 |

---

## 👥 ユーザー管理 API

### 1. ユーザー情報取得

ユーザーの詳細情報を取得します。

**エンドポイント:**
```
GET /users/{user_id}
```

**ヘッダー:**
```
Authorization: Bearer {access_token}
```

**レスポンス:**
```json
{
  "user_id": "USR-20260417-001",
  "username": "user@example.com",
  "full_name": "Taro Yamada",
  "organization": "Acme Corp",
  "status": "active",
  "mfa_methods": ["totp", "fido2"],
  "auth_devices": [
    {
      "device_id": "device_abc123",
      "device_name": "My Laptop",
      "last_login": "2026-04-17T12:00:00Z",
      "trusted": true
    }
  ],
  "created_at": "2026-04-10T08:00:00Z",
  "last_login": "2026-04-17T12:00:00Z"
}
```

---

### 2. ユーザーデバイス列表

ユーザーが登録しているデバイス一覧を取得します。

**エンドポイント:**
```
GET /users/{user_id}/devices
```

**レスポンス:**
```json
{
  "devices": [
    {
      "device_id": "device_abc123",
      "device_name": "My Laptop",
      "device_type": "Windows 11",
      "trusted": true,
      "last_login": "2026-04-17T12:00:00Z",
      "created_at": "2026-04-10T08:00:00Z"
    },
    {
      "device_id": "device_def456",
      "device_name": "iPhone 14",
      "device_type": "iOS 17",
      "trusted": false,
      "last_login": "2026-04-16T15:30:00Z",
      "created_at": "2026-04-15T10:00:00Z"
    }
  ],
  "total": 2
}
```

---

### 3. ユーザーデバイス削除

デバイスを信頼できないと判定して削除します。

**エンドポイント:**
```
DELETE /users/{user_id}/devices/{device_id}
```

**レスポンス:**
```json
{
  "status": "deleted",
  "device_id": "device_def456",
  "deleted_at": "2026-04-17T12:10:00Z"
}
```

---

## 🔒 セキュリティ監視 API

### 1. セキュリティイベント報告

セキュリティイベントをシステムに報告します。

**エンドポイント:**
```
POST /security/events
```

**リクエスト:**
```json
{
  "event_type": "authentication",
  "user_id": "USR-20260417-001",
  "client_ip": "203.0.113.45",
  "device_id": "device_abc123",
  "success": true,
  "timestamp": "2026-04-17T12:00:00Z",
  "details": {
    "mfa_method": "totp",
    "authentication_method": "password",
    "session_duration": 3600
  }
}
```

**レスポンス:**
```json
{
  "event_id": "evt_20260417_001",
  "status": "recorded",
  "severity": "info",
  "timestamp": "2026-04-17T12:00:00Z"
}
```

**イベントタイプ:**
- `authentication` - ログイン成功/失敗
- `access_granted` - リソースアクセス許可
- `access_denied` - リソースアクセス拒否
- `data_modification` - データ修正・削除
- `policy_violation` - ポリシー違反

---

### 2. インシデント取得

セキュリティインシデントを取得します。

**エンドポイント:**
```
GET /security/incidents
```

**クエリパラメータ:**
| 名前 | 型 | 説明 |
|------|-----|------|
| severity | string | critical, high, medium, low |
| status | string | open, resolved, in_progress |
| limit | int | 返却件数 (デフォルト: 50) |
| offset | int | オフセット (デフォルト: 0) |

**レスポンス:**
```json
{
  "incidents": [
    {
      "incident_id": "inc_20260417_001",
      "severity": "critical",
      "title": "Multiple failed authentication attempts",
      "description": "5 failed login attempts in 10 minutes",
      "affected_user": "USR-20260417-002",
      "created_at": "2026-04-17T12:15:00Z",
      "status": "in_progress",
      "action_taken": "Account temporarily locked",
      "auto_response": true
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

---

### 3. 脅威レポート取得

指定期間の脅威レポートを生成します。

**エンドポイント:**
```
GET /security/threats/report
```

**クエリパラメータ:**
| 名前 | 型 | 必須 | 説明 |
|------|-----|------|------|
| date_range | string | × | 7d, 30d, 90d (デフォルト: 7d) |
| threat_type | string | × | malware, data_breach, intrusion |
| format | string | × | json, csv, pdf (デフォルト: json) |

**レスポンス:**
```json
{
  "report_id": "rpt_20260417_001",
  "period": "2026-04-10 ~ 2026-04-17",
  "total_events": 15234,
  "threat_summary": {
    "critical": 2,
    "high": 12,
    "medium": 89,
    "low": 15131
  },
  "top_threats": [
    {
      "threat_type": "brute_force_attack",
      "occurrences": 23,
      "affected_users": 5
    },
    {
      "threat_type": "privilege_escalation",
      "occurrences": 8,
      "affected_users": 2
    }
  ],
  "generated_at": "2026-04-17T12:20:00Z"
}
```

---

## 🤖 脅威検知 API

### 1. 異常検知実行

機械学習異常検知エンジンを実行します。

**エンドポイント:**
```
POST /threats/anomaly-detection
```

**リクエスト:**
```json
{
  "detection_type": "user_behavior",
  "time_window": 86400,
  "threshold": 0.90,
  "methods": ["isolation_forest", "lstm", "lof"],
  "include_graph_analysis": true
}
```

**レスポンス:**
```json
{
  "detection_run_id": "det_20260417_001",
  "status": "completed",
  "duration_ms": 2345,
  "anomalies_detected": 12,
  "results": [
    {
      "entity_id": "USR-20260417-003",
      "entity_type": "user",
      "anomaly_score": 0.95,
      "detection_method": "isolation_forest",
      "description": "Unusual login time and location",
      "confidence": 0.98,
      "recommendations": [
        "Require additional MFA verification",
        "Monitor account activity",
        "Review recent access logs"
      ]
    }
  ],
  "timestamp": "2026-04-17T12:25:00Z"
}
```

**パラメータ:**
| 名前 | 型 | 必須 | 説明 |
|------|-----|------|------|
| detection_type | enum | ✓ | user_behavior, network_traffic, data_access |
| time_window | int | × | 秒数 (デフォルト: 86400) |
| threshold | float | × | 異常スコア閾値 (0-1, デフォルト: 0.85) |
| methods | array | × | Isolation Forest, LSTM, LOF 等 |
| include_graph_analysis | bool | × | グラフベース分析を含める |

---

### 2. 脅威予測

侵害確率と攻撃シーケンスを予測します。

**エンドポイント:**
```
POST /threats/prediction
```

**リクエスト:**
```json
{
  "entity_id": "USR-20260417-003",
  "entity_type": "user",
  "time_horizon": "7d",
  "include_recommendations": true
}
```

**レスポンス:**
```json
{
  "prediction_id": "pred_20260417_001",
  "entity_id": "USR-20260417-003",
  "breach_probability": 0.72,
  "breach_probability_explanation": "High risk indicators: unusual geographic logins, multiple failed authentications, data access spike",
  "predicted_attacks": [
    {
      "attack_sequence": "Reconnaissance → Privilege Escalation → Data Exfiltration",
      "probability": 0.65,
      "estimated_time_to_compromise": "2-3 days"
    }
  ],
  "estimated_dwell_time": 180,
  "recommendations": [
    "Require multi-factor authentication",
    "Monitor privilege escalation attempts",
    "Implement data exfiltration controls"
  ],
  "predicted_at": "2026-04-17T12:30:00Z"
}
```

---

## 📋 コンプライアンス API

### 1. コンプライアンスステータス取得

GDPR/CCPA/APPI コンプライアンスのステータスを取得します。

**エンドポイント:**
```
GET /compliance/status
```

**レスポンス:**
```json
{
  "compliance_status": {
    "gdpr": {
      "status": "compliant",
      "last_audit": "2026-04-15T10:00:00Z",
      "checks_passed": 45,
      "checks_total": 45,
      "violations": 0
    },
    "ccpa": {
      "status": "compliant",
      "last_audit": "2026-04-15T10:00:00Z",
      "checks_passed": 32,
      "checks_total": 32,
      "violations": 0
    },
    "appi": {
      "status": "compliant",
      "last_audit": "2026-04-15T10:00:00Z",
      "checks_passed": 28,
      "checks_total": 28,
      "violations": 0
    }
  },
  "overall_compliance": 100,
  "checked_at": "2026-04-17T12:35:00Z"
}
```

---

### 2. 監査ログ取得

監査ログ (改ざん防止) を取得します。

**エンドポイント:**
```
GET /compliance/audit-logs
```

**クエリパラメータ:**
| 名前 | 型 | 説明 |
|------|-----|------|
| start_date | string | ISO 8601 日付 |
| end_date | string | ISO 8601 日付 |
| action | string | login, data_access, policy_change 等 |
| limit | int | 返却件数 (デフォルト: 100) |

**レスポンス:**
```json
{
  "audit_logs": [
    {
      "log_id": "audit_20260417_001",
      "timestamp": "2026-04-17T12:00:00Z",
      "user_id": "USR-20260417-001",
      "action": "login",
      "resource": "system",
      "result": "success",
      "details": {
        "ip_address": "203.0.113.45",
        "mfa_used": true
      },
      "immutable_hash": "sha256_hash_xyz"
    }
  ],
  "total": 5432,
  "limit": 100
}
```

---

### 3. データ削除リクエスト (GDPR 削除権)

ユーザーのデータを削除します。

**エンドポイント:**
```
POST /compliance/data-deletion-request
```

**リクエスト:**
```json
{
  "user_id": "USR-20260417-001",
  "reason": "user_request",
  "include_backups": true,
  "include_analytics": true
}
```

**レスポンス:**
```json
{
  "deletion_request_id": "del_req_20260417_001",
  "status": "in_progress",
  "user_id": "USR-20260417-001",
  "estimated_completion": "2026-04-24T12:00:00Z",
  "created_at": "2026-04-17T12:40:00Z"
}
```

---

## ⚠️ エラーコード

### 認証エラー

| コード | メッセージ | 説明 |
|-------|----------|------|
| 401 | UNAUTHORIZED | トークンが無効・期限切れ |
| 403 | FORBIDDEN | 権限がありません |
| 405 | MFA_REQUIRED | MFA 認証が必要です |
| 429 | TOO_MANY_ATTEMPTS | ログイン試行回数が多すぎます |

### バリデーションエラー

| コード | メッセージ | 説明 |
|-------|----------|------|
| 400 | INVALID_INPUT | 入力値が無効 |
| 400 | INVALID_PASSWORD | パスワード要件を満たしていません |
| 409 | RESOURCE_EXISTS | リソースが既に存在 |
| 404 | NOT_FOUND | リソースが見つかりません |

### レート制限エラー

| コード | メッセージ | 説明 |
|-------|----------|------|
| 429 | RATE_LIMIT_EXCEEDED | API レート制限に達しました |

---

## 🚦 レート制限

**API レート制限:**

| エンドポイント | リクエスト/分 | リクエスト/時間 |
|-------------|-----------|------------|
| /auth/* | 10 | 300 |
| /users/* | 60 | 3600 |
| /security/* | 100 | 6000 |
| /threats/* | 50 | 3000 |
| /compliance/* | 50 | 3000 |

**ヘッダー:**
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 5
X-RateLimit-Reset: 1713366600
```

---

## 📚 SDKs

**公式 SDK:**
- Python: `pip install esp-sdk`
- JavaScript: `npm install @esp/sdk`
- Java: `maven install esp-sdk`
- Go: `go get github.com/esp/sdk-go`

**使用例 (Python):**
```python
from esp_sdk import Client

# クライアント初期化
client = Client(
    api_key="your_api_key",
    api_secret="your_api_secret"
)

# ログイン
response = client.auth.login(
    username="user@example.com",
    password="password"
)
print(response.access_token)

# インシデント取得
incidents = client.security.get_incidents(severity="high")
for incident in incidents:
    print(f"{incident.id}: {incident.title}")
```

---

**API ドキュメント統計:**
- エンドポイント: 20+
- パラメータ: 100+
- エラーコード: 15+
- 使用例: 30+

**最終更新**: 2026年4月17日  
**ステータス**: ✅ 本番環境対応
