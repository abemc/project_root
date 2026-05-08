"""
Streamlit サイドバー設定の永続化管理モジュール

ユーザーが設定したサイドバー項目（LLMモデル、検索パラメータ、
マルチモーダル設定など）をJSON形式で保存・復元し、
セッション終了後も設定が残るようにします。
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class SidebarConfigManager:
    """Streamlit サイドバー設定の永続化マネージャー"""
    
    # デフォルト設定
    DEFAULT_CONFIG = {
        "basic": {
            "llm_model": "qwen2.5:7b",
            "max_steps": 5,
        },
        "search": {
            "retrieval_top_k": 5,
            "reranker_model": "BAAI/bge-reranker-base",
            "rerank_top_k": 3,
            "rerank_threshold": 0.1,
        },
        "multimodal": {
            "enabled": True,
            "vision_model": "clip",
            "enable_ocr": True,
            "audio_transcription_model": "whisper-small",
            "tts_engine": "edge-tts",
            "supported_languages": ["ja", "en"],
            "show_history": False,
        },
        "debug": {
            "show_logs": True,
            "show_memories": True,
            "show_debug": False,
            "auto_train_enabled": False,
        },
        "metadata": {
            "created_at": "",
            "updated_at": "",
            "version": "1.0"
        }
    }
    
    def __init__(self, config_dir: str = "config"):
        """
        初期化
        
        Args:
            config_dir: 設定ファイルの保存ディレクトリ
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "sidebar_config.json"
        self.backup_dir = self.config_dir / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def load_config(self) -> Dict[str, Any]:
        """
        設定ファイルから設定を読み込む
        
        Returns:
            設定辞書。ファイルがない場合はデフォルト設定を返す
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info(f"設定を読み込みました: {self.config_file}")
                return config
            else:
                logger.info("設定ファイルが見つかりません。デフォルト設定を使用します。")
                return self._get_default_config()
        except Exception as e:
            logger.error(f"設定の読み込みに失敗しました: {e}")
            return self._get_default_config()
    
    def save_config(self, config: Dict[str, Any], create_backup: bool = True) -> bool:
        """
        設定をファイルに保存
        
        Args:
            config: 保存する設定辞書
            create_backup: 保存前に前のバージョンのバックアップを作成するか
        
        Returns:
            成功した場合 True、失敗した場合 False
        """
        try:
            # バックアップを作成
            if create_backup and self.config_file.exists():
                self._create_backup()
            
            # メタデータを更新
            now = datetime.now().isoformat()
            if "metadata" not in config:
                config["metadata"] = {}
            
            if not config["metadata"].get("created_at"):
                config["metadata"]["created_at"] = now
            config["metadata"]["updated_at"] = now
            config["metadata"]["version"] = "1.0"
            
            # ファイルに保存
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            logger.info(f"設定を保存しました: {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"設定の保存に失敗しました: {e}")
            return False
    
    def update_config(self, section: str, key: str, value: Any) -> bool:
        """
        設定の特定の項目を更新
        
        Args:
            section: セクション名（'basic', 'search', 'multimodal' など）
            key: キー名
            value: 新しい値
        
        Returns:
            成功した場合 True、失敗した場合 False
        """
        config = self.load_config()
        
        if section not in config:
            config[section] = {}
        
        config[section][key] = value
        return self.save_config(config)
    
    def update_section(self, section: str, section_data: Dict[str, Any]) -> bool:
        """
        設定のセクション全体を更新
        
        Args:
            section: セクション名
            section_data: セクションのデータ辞書
        
        Returns:
            成功した場合 True、失敗した場合 False
        """
        config = self.load_config()
        config[section] = section_data
        return self.save_config(config)
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        特定のセクションを取得
        
        Args:
            section: セクション名
        
        Returns:
            セクションのデータ辞書
        """
        config = self.load_config()
        return config.get(section, {})
    
    def get_value(self, section: str, key: str, default: Any = None) -> Any:
        """
        設定の特定の値を取得
        
        Args:
            section: セクション名
            key: キー名
            default: デフォルト値
        
        Returns:
            設定値またはデフォルト値
        """
        config = self.load_config()
        return config.get(section, {}).get(key, default)
    
    def reset_to_default(self) -> bool:
        """
        設定をデフォルト値にリセット
        
        Returns:
            成功した場合 True、失敗した場合 False
        """
        return self.save_config(self._get_default_config())
    
    def list_backups(self) -> List[str]:
        """
        バックアップファイルのリストを取得
        
        Returns:
            バックアップファイルのパスリスト（最新順）
        """
        if not self.backup_dir.exists():
            return []
        
        backups = sorted(
            self.backup_dir.glob("sidebar_config_*.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        return [str(b) for b in backups]
    
    def restore_backup(self, backup_path: str) -> bool:
        """
        バックアップから設定を復元
        
        Args:
            backup_path: バックアップファイルのパス
        
        Returns:
            成功した場合 True、失敗した場合 False
        """
        try:
            if not Path(backup_path).exists():
                logger.error(f"バックアップファイルが見つかりません: {backup_path}")
                return False
            
            with open(backup_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            return self.save_config(config, create_backup=True)
        except Exception as e:
            logger.error(f"バックアップの復元に失敗しました: {e}")
            return False
    
    def export_config(self, export_path: str) -> bool:
        """
        設定をファイルにエクスポート
        
        Args:
            export_path: エクスポート先ファイルパス
        
        Returns:
            成功した場合 True、失敗した場合 False
        """
        try:
            config = self.load_config()
            Path(export_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            logger.info(f"設定をエクスポートしました: {export_path}")
            return True
        except Exception as e:
            logger.error(f"設定のエクスポートに失敗しました: {e}")
            return False
    
    def import_config(self, import_path: str) -> bool:
        """
        ファイルから設定をインポート
        
        Args:
            import_path: インポート元ファイルパス
        
        Returns:
            成功した場合 True、失敗した場合 False
        """
        try:
            if not Path(import_path).exists():
                logger.error(f"インポートファイルが見つかりません: {import_path}")
                return False
            
            with open(import_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            return self.save_config(config, create_backup=True)
        except Exception as e:
            logger.error(f"設定のインポートに失敗しました: {e}")
            return False
    
    def validate_config(self, config: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        設定の妥当性を検証
        
        Args:
            config: 検証する設定辞書
        
        Returns:
            (妥当性, エラーメッセージのリスト)
        """
        errors = []
        
        # 基本設定の検証
        basic = config.get("basic", {})
        if "max_steps" in basic:
            if not isinstance(basic["max_steps"], int) or basic["max_steps"] < 1 or basic["max_steps"] > 50:
                errors.append("max_steps は 1 から 50 の整数である必要があります")
        
        # 検索設定の検証
        search = config.get("search", {})
        if "retrieval_top_k" in search:
            if not isinstance(search["retrieval_top_k"], int) or search["retrieval_top_k"] < 1:
                errors.append("retrieval_top_k は 1 以上の整数である必要があります")
        
        if "rerank_threshold" in search:
            if not isinstance(search["rerank_threshold"], (int, float)) or not (0 <= search["rerank_threshold"] <= 1):
                errors.append("rerank_threshold は 0 から 1 の数値である必要があります")
        
        # マルチモーダル設定の検証
        multimodal = config.get("multimodal", {})
        if "supported_languages" in multimodal:
            if not isinstance(multimodal["supported_languages"], list):
                errors.append("supported_languages はリストである必要があります")
            valid_langs = ["ja", "en", "zh", "es", "fr", "de", "ko"]
            for lang in multimodal["supported_languages"]:
                if lang not in valid_langs:
                    errors.append(f"不正な言語コード: {lang}")
        
        return len(errors) == 0, errors
    
    def _create_backup(self) -> str:
        """
        現在の設定ファイルのバックアップを作成
        
        Returns:
            バックアップファイルのパス
        """
        if not self.config_file.exists():
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"sidebar_config_{timestamp}.json"
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            logger.info(f"設定のバックアップを作成しました: {backup_path}")
            return str(backup_path)
        except Exception as e:
            logger.error(f"バックアップの作成に失敗しました: {e}")
            return ""
    
    def _get_default_config(self) -> Dict[str, Any]:
        """デフォルト設定を取得"""
        import copy
        config = copy.deepcopy(self.DEFAULT_CONFIG)
        now = datetime.now().isoformat()
        config["metadata"]["created_at"] = now
        config["metadata"]["updated_at"] = now
        return config
    
    def cleanup_old_backups(self, keep_count: int = 10) -> int:
        """
        古いバックアップを削除（指定数のみ保持）
        
        Args:
            keep_count: 保持するバックアップ数
        
        Returns:
            削除されたバックアップの数
        """
        backups = self.list_backups()
        deleted_count = 0
        
        if len(backups) > keep_count:
            for backup_path in backups[keep_count:]:
                try:
                    Path(backup_path).unlink()
                    deleted_count += 1
                    logger.info(f"古いバックアップを削除しました: {backup_path}")
                except Exception as e:
                    logger.error(f"バックアップの削除に失敗しました: {e}")
        
        return deleted_count
