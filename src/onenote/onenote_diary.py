"""
OneNote Diary モジュール
Microsoft Graph API を使って OneNote に日記ページを作成する。
認証: OAuth 2.0 Device Code Flow (MSALなし、requestsのみ)
"""

import json
import html
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Microsoft Graph エンドポイント
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
LOGIN_BASE = "https://login.microsoftonline.com"
# 必要なスコープ
SCOPES = "Notes.Create Notes.ReadWrite offline_access"

# トークンキャッシュのパス
TOKEN_CACHE_PATH = Path(__file__).parent / "config" / "onenote_token.json"


def _format_aad_error(resp: requests.Response) -> str:
    """Azure AD のエラーレスポンスを人間向けに整形する。"""
    try:
        data = resp.json()
    except Exception:
        text = (resp.text or "").strip()
        return text or f"HTTP {resp.status_code}"

    error = data.get("error", "unknown_error")
    desc = data.get("error_description", "")
    codes = data.get("error_codes")
    trace_id = data.get("trace_id")
    correlation_id = data.get("correlation_id")

    parts = [f"{error}: {desc}".strip()]
    if codes:
        parts.append(f"error_codes={codes}")
    if trace_id:
        parts.append(f"trace_id={trace_id}")
    if correlation_id:
        parts.append(f"correlation_id={correlation_id}")
    return " | ".join(parts)


# ────────────────────────────────────────────
# トークン管理
# ────────────────────────────────────────────

def _save_token(token_data: dict) -> None:
    TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_CACHE_PATH.write_text(json.dumps(token_data, ensure_ascii=False, indent=2))


def _load_token() -> Optional[dict]:
    if TOKEN_CACHE_PATH.exists():
        try:
            return json.loads(TOKEN_CACHE_PATH.read_text())
        except Exception:
            return None
    return None


def _is_token_expired(token_data: dict) -> bool:
    expires_at = token_data.get("expires_at", 0)
    return time.time() >= expires_at - 60  # 60秒のバッファ


def get_valid_access_token(tenant_id: str, client_id: str) -> Optional[str]:
    """有効なアクセストークンを返す。期限切れなら自動リフレッシュ。"""
    token_data = _load_token()
    if not token_data:
        return None

    if not _is_token_expired(token_data):
        return token_data.get("access_token")

    # リフレッシュトークンで更新
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        return None

    saved_tenant = token_data.get("tenant_used")
    endpoint_candidates = [tenant_id]
    if saved_tenant and saved_tenant not in endpoint_candidates:
        endpoint_candidates.append(saved_tenant)
    for fallback in ["consumers", "common", "organizations"]:
        if fallback not in endpoint_candidates:
            endpoint_candidates.append(fallback)

    resp = None
    for endpoint in endpoint_candidates:
        resp = requests.post(
            f"{LOGIN_BASE}/{endpoint}/oauth2/v2.0/token",
            data={
                "grant_type": "refresh_token",
                "client_id": client_id,
                "refresh_token": refresh_token,
                "scope": SCOPES,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            new_token = resp.json()
            new_token["expires_at"] = time.time() + new_token.get("expires_in", 3600)
            new_token["tenant_used"] = endpoint
            _save_token(new_token)
            return new_token.get("access_token")

    if resp is not None:
        logger.warning(f"トークンリフレッシュ失敗: {_format_aad_error(resp)}")
    return None


def delete_token() -> None:
    """保存済みトークンを削除（ログアウト）"""
    if TOKEN_CACHE_PATH.exists():
        TOKEN_CACHE_PATH.unlink()


# ────────────────────────────────────────────
# Device Code Flow
# ────────────────────────────────────────────

def start_device_code_flow(tenant_id: str, client_id: str) -> dict:
    """
    Device Code Flow を開始し、ユーザーに表示する情報を返す。
    戻り値: {"user_code": ..., "verification_uri": ..., "device_code": ..., "interval": ...}
    """
    endpoints = [tenant_id]
    # MSA専用アプリ等で失敗しやすいため、既定で consumers/common にフォールバック
    for fallback in ["consumers", "common", "organizations"]:
        if fallback not in endpoints:
            endpoints.append(fallback)

    errors_by_endpoint: list[str] = []
    for endpoint in endpoints:
        resp = requests.post(
            f"{LOGIN_BASE}/{endpoint}/oauth2/v2.0/devicecode",
            data={"client_id": client_id, "scope": SCOPES},
            timeout=30,
        )
        if resp.status_code == 200:
            info = resp.json()
            info["tenant_used"] = endpoint
            return info
        errors_by_endpoint.append(f"{endpoint}: {_format_aad_error(resp)}")

    joined_errors = " || ".join(errors_by_endpoint)
    if "AADSTS70002" in joined_errors:
        raise RuntimeError(
            "Device Code開始に失敗しました。"
            " `/consumers` には到達していますが、アプリがパブリッククライアントとして有効化されていません。"
            " Azure Portal > アプリの登録 > 認証 > 『モバイルとデスクトップ アプリケーション』を追加し、"
            "必要に応じて『パブリック クライアント フローを許可』を有効化してください。"
            f" tenant={tenant_id}, client_id={client_id}. 詳細: {joined_errors}"
        )

    raise RuntimeError(
        "Device Code開始に失敗しました。"
        f" tenant={tenant_id}, client_id={client_id}. 詳細: {joined_errors}"
    )


def poll_device_code_token(tenant_id: str, client_id: str, device_code: str, interval: int = 5) -> dict:
    """
    デバイスコード認証の完了をポーリング（1回のみ試行）。
    戻り値: {"status": "pending"|"success"|"error", "token": {...} or None, "message": str}
    """
    resp = requests.post(
        f"{LOGIN_BASE}/{tenant_id}/oauth2/v2.0/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": client_id,
            "device_code": device_code,
        },
        timeout=30,
    )
    data = resp.json()

    if resp.status_code == 200:
        data["expires_at"] = time.time() + data.get("expires_in", 3600)
        data["tenant_used"] = tenant_id
        _save_token(data)
        return {"status": "success", "token": data, "message": "認証完了"}

    error = data.get("error", "")
    if error == "authorization_pending":
        return {"status": "pending", "token": None, "message": "認証待機中..."}
    if error == "slow_down":
        return {"status": "pending", "token": None, "message": "少し待ってから再試行..."}
    if error == "authorization_declined":
        return {"status": "error", "token": None, "message": "認証が拒否されました"}
    if error == "expired_token":
        return {"status": "error", "token": None, "message": "コードの有効期限が切れました。再度ログインしてください"}

    return {"status": "error", "token": None, "message": f"エラー: {data.get('error_description', error)}"}


# ────────────────────────────────────────────
# OneNote API
# ────────────────────────────────────────────

def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def list_notebooks(access_token: str) -> list[dict]:
    """ノートブック一覧を返す。各要素: {"id": ..., "displayName": ...}"""
    resp = requests.get(
        f"{GRAPH_BASE}/me/onenote/notebooks",
        headers=_auth_headers(access_token),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("value", [])


def list_sections(access_token: str, notebook_id: str) -> list[dict]:
    """指定ノートブックのセクション一覧を返す。各要素: {"id": ..., "displayName": ...}"""
    resp = requests.get(
        f"{GRAPH_BASE}/me/onenote/notebooks/{notebook_id}/sections",
        headers=_auth_headers(access_token),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("value", [])


def create_diary_page(
    access_token: str,
    section_id: str,
    title: str,
    body_text: str,
    date: Optional[datetime] = None,
) -> dict:
    """
    OneNote に日記ページを作成する。
    戻り値: {"success": bool, "page_url": str or None, "message": str}
    """
    if date is None:
        date = datetime.now()

    date_str = date.strftime("%Y年%m月%d日")
    time_str = date.strftime("%H:%M")

    # 本文のHTMLを構築（改行をbrに変換）
    escaped_title = html.escape(title)
    escaped_body = (
        body_text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <title>{escaped_title}</title>
  <meta name="created" content="{date.strftime('%Y-%m-%dT%H:%M:%S')}+09:00" />
</head>
<body>
  <h1>{escaped_title}</h1>
  <p><strong>{date_str} {time_str}</strong></p>
  <hr/>
  <p>{escaped_body}</p>
</body>
</html>"""

    headers = {
        **_auth_headers(access_token),
        "Content-Type": "application/xhtml+xml",
    }

    resp = requests.post(
        f"{GRAPH_BASE}/me/onenote/sections/{section_id}/pages",
        headers=headers,
        data=html_content.encode("utf-8"),
        timeout=30,
    )

    if resp.status_code == 201:
        page_data = resp.json()
        return {
            "success": True,
            "page_url": page_data.get("links", {}).get("oneNoteWebUrl", {}).get("href"),
            "message": "OneNote に保存しました",
        }

    try:
        err_msg = resp.json().get("error", {}).get("message", resp.text)
    except Exception:
        err_msg = resp.text
    return {"success": False, "page_url": None, "message": f"保存失敗: {err_msg}"}
