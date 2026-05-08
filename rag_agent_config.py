#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG Agent 設定管理モジュール
RAG Agentの設定をJSON形式で保存・復元
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

class RAGAgentConfig:
    """RAG Agent 設定クラス"""
    
    def __init__(self, config_dir: str = "/home/abemc/project_root/config"):
        # 設定ディレクトリとファイルの初期化
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)  # ディレクトリが存在しない場合は作成
        self.config_file = self.config_dir / "rag_agent_config.json"  # 設定ファイルパス
        self.backup_dir = self.config_dir / "rag_backups"  # バックアップディレクトリ
        self.backup_dir.mkdir(parents=True, exist_ok=True)  # バックアップディレクトリが存在しない場合は作成

    def load_config(self) -> Dict:
        """設定ファイルを読み込む"""
        # 設定ファイルが存在する場合は読み込む
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # 設定ファイルが存在しない場合はデフォルト設定を返す
        return self.get_default_config()

    def get_default_config(self) -> Dict:
        """デフォルト設定を返す"""
        # デフォルト設定を定義
        return {
            "version": "1.0",
            "created": datetime.now().isoformat(),
            "llm_model": "GPT-4o",
            "search_method": "ハイブリッド",
            "top_k": 5,
            "confidence_threshold": 0.7,
            "document_categories": ["root", "reports", "guides"],
            "enable_cache": True,
            "cache_ttl": 3600,
            "max_tokens": 2000,
            "temperature": 0.7,
            "system_prompt": "あなたは優秀なドキュメント分析専門家です。ユーザーの質問に対して、参照ドキュメントから正確で有用な情報を抽出して回答してください。",
            "enable_source_attribution": True,
            "enable_follow_up_questions": True,
            "language": "ja",
            "backup_location": "/mnt/d/backups"
        }

    def save_config(self, config: Dict) -> bool:
        """設定ファイルを保存"""
        try:
            # 最終更新日時を追加
            config['last_modified'] = datetime.now().isoformat()
            # 設定をファイルに保存
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            # エラー発生時のログ出力
            print(f"❌ 設定保存エラー: {str(e)}")
            return False

    def backup_config(self) -> Optional[str]:
        """設定をバックアップ"""
        try:
            # 現在の設定を読み込む
            config = self.load_config()
            # タイムスタンプ付きのバックアップファイル名を生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"rag_config_backup_{timestamp}.json"
            
            # バックアップファイルに保存
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            return str(backup_file)
        except Exception as e:
            # エラー発生時のログ出力
            print(f"❌ バックアップエラー: {str(e)}")
            return None

    def restore_config(self, backup_file: Optional[str] = None) -> bool:
        """設定をリストア"""
        try:
            # 指定がない場合は最新のバックアップを取得
            if backup_file is None:
                backups = sorted(self.backup_dir.glob("rag_config_backup_*.json"), reverse=True)
                if not backups:
                    print("❌ バックアップが見つかりません")
                    return False
                backup_file = str(backups[0])
            
            # バックアップファイルを読み込んで設定を復元
            if backup_file and Path(backup_file).exists():
                with open(backup_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                self.save_config(config)
                return True
            else:
                print("❌ バックアップファイルが見つかりません")
                return False
        except Exception as e:
            # エラー発生時のログ出力
            print(f"❌ リストアエラー: {str(e)}")
            return False

    def get_backups_list(self) -> list:
        """バックアップ一覧を取得"""
        backups = []
        try:
            # バックアップファイルを取得し、情報をリスト化
            for backup_file in sorted(self.backup_dir.glob("rag_config_backup_*.json"), reverse=True):
                stat = backup_file.stat()
                backups.append({
                    'name': backup_file.name,
                    'path': str(backup_file),
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
        except Exception as e:
            # エラー発生時のログ出力
            print(f"❌ エラー: {str(e)}")
        
        return backups

    def export_config(self, export_path: str) -> Optional[str]:
        """設定をエクスポート"""
        try:
            # エクスポート先ディレクトリを確認・作成
            export_dir = Path(export_path)
            if not export_dir.exists():
                export_dir.mkdir(parents=True, exist_ok=True)
            
            # 書き込み権限を確認
            if not os.access(export_dir, os.W_OK):
                raise PermissionError(f"書き込み権限がありません: {export_path}")
            
            # エクスポートファイルパスを生成
            config = self.load_config()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_file = export_dir / f"rag_agent_config_{timestamp}.json"
            
            # 設定をエクスポート
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            # ファイル生成確認
            if export_file.exists():
                file_size = export_file.stat().st_size
                print(f"✅ エクスポート成功: {export_file} ({file_size} bytes)")
                return str(export_file)
            else:
                raise IOError(f"ファイルが生成されませんでした: {export_file}")
                
        except PermissionError as e:
            # 権限エラーの処理
            print(f"❌ 権限エラー: {str(e)}")
            raise
        except OSError as e:
            # ファイルシステムエラーの処理
            print(f"❌ ファイルシステムエラー: {str(e)}")
            raise
        except Exception as e:
            # その他のエラー処理
            print(f"❌ エクスポートエラー: {str(e)}")
            return None

    def import_config(self, import_file: str) -> bool:
        """設定をインポート"""
        try:
            # インポートファイルを読み込む
            with open(import_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 設定を保存
            self.save_config(config)
            return True
        except Exception as e:
            # エラー発生時のログ出力
            print(f"❌ インポートエラー: {str(e)}")
            return False

    def validate_config(self, config: Dict) -> tuple:
        """設定を検証"""
        errors = []
        
        # 必須フィールドの存在確認
        required_fields = [
            'llm_model', 'search_method', 'top_k', 
            'confidence_threshold', 'temperature'
        ]
        
        for field in required_fields:
            if field not in config:
                errors.append(f"❌ 必須フィールドが不足: {field}")
        
        # 値の妥当性チェック
        if config.get('top_k', 0) < 1 or config.get('top_k', 0) > 50:
            errors.append("❌ top_k は 1-50 の範囲内である必要があります")
        if config.get('confidence_threshold', 0) < 0 or config.get('confidence_threshold', 0) > 1:
            errors.append("❌ confidence_threshold は 0-1 の範囲内である必要があります")
        if config.get('temperature', 0) < 0 or config.get('temperature', 0) > 2:
            errors.append("❌ temperature は 0-2 の範囲内である必要があります")
        
        return len(errors) == 0, errors

    def get_config_summary(self) -> str:
        """設定サマリーを取得"""
        # 現在の設定を読み込む
        config = self.load_config()
        # サマリーを整形して返す
        summary = f"""
📊 RAG Agent 設定サマリー
═══════════════════════════════════════

🤖 モデル設定:
  • LLMモデル: {config.get('llm_model', 'N/A')}
  • 検索方式: {config.get('search_method', 'N/A')}
  • 言語: {config.get('language', 'N/A')}

🎯 検索パラメータ:
  • 取得ドキュメント数: {config.get('top_k', 'N/A')}
  • 信頼度閾値: {config.get('confidence_threshold', 'N/A')}
  • 対象カテゴリ: {', '.join(config.get('document_categories', []))}

⚙️ 生成パラメータ:
  • 温度(Temperature): {config.get('temperature', 'N/A')}
  • トークン上限: {config.get('max_tokens', 'N/A')}
  • キャッシュ有効: {config.get('enable_cache', False)}

📁 バックアップ先:
  • {config.get('backup_location', 'N/A')}

✅ 最終更新: {config.get('last_modified', 'N/A')}
═══════════════════════════════════════
"""
        return summary
