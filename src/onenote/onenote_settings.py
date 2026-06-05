import json
import logging
from datetime import datetime
from src.utils.path_utils import PROJECT_ROOT

logger = logging.getLogger(__name__)

ONENOTE_SETTINGS_PATH = PROJECT_ROOT / "config" / "onenote_settings.json"

def _load_onenote_settings() -> dict:
    """保存済みのOneNote設定を読み込む。"""
    if not ONENOTE_SETTINGS_PATH.exists():
        return {}
    try:
        with open(ONENOTE_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as e:
        logger.warning(f"OneNote設定の読み込みに失敗: {e}")
    return {}

def _save_onenote_settings(client_id: str, tenant_id: str) -> None:
    """OneNote設定をファイルへ保存する。"""
    ONENOTE_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "client_id": client_id,
        "tenant_id": tenant_id,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(ONENOTE_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
