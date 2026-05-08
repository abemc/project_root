"""プロジェクトバックアップ・リストア管理"""

import logging
import shutil
import tarfile
import gzip
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import os

from .manifest import BackupManifest, BackupItem

logger = logging.getLogger(__name__)


class ProjectBackupManager:
    """プロジェクトのバックアップ・リストア管理"""
    
    # バックアップ対象ターゲット
    BACKUP_TARGETS = {
        "system_config": {
            "paths": [".env", ".github", "pyproject.toml", "requirements.txt", 
                     "Dockerfile", "docker-compose.yml", ".streamlit"],
            "description": "システム設定・CI/CD・インフラ設定"
        },
        "source_code": {
            "paths": ["src"],
            "description": "ソースコード（全モジュール）"
        },
        "scripts": {
            "paths": ["build_knowledge.py", "manage_kb.py", "main.py", "app.py",
                     "load_prompt.py", "fix_all_memory.py", "fix_faiss.py", "fix_memories.py",
                     "test_llm_fix.py", "verify_generator.py"],
            "description": "Python スクリプト・ユーティリティ"
        },
        "data_input": {
            "paths": ["raw_pdfs", "data", "notebooks"],
            "description": "入力データ・ノートブック"
        },
        "embeddings": {
            "paths": ["embeddings", "rag_corpus"],
            "description": "埋め込みベクトル・RAGコーパス（大容量注意）"
        },
        "models": {
            "paths": ["models", "fine_tuned_model", "checkpoints"],
            "description": "モデルファイル・チェックポイント"
        },
        "knowledge_base": {
            "paths": ["corpus"],
            "description": "知識ベースコーパス（大容量注意）"
        },
        "documentation": {
            "paths": ["BACKUP_GUIDE.md", "MULTIMODAL_COMPLETION_REPORT.md", 
                     "SYSTEM_INTEGRATION_GUIDE.md", "docs"],
            "description": "ドキュメント・マークダウン"
        },
        "logs": {
            "paths": ["logs"],
            "description": "実行ログ・履歴（バージョン管理）"
        }
    }
    
    # デフォルト除外パターン
    EXCLUDE_PATTERNS = [
        # Python関連
        "*.pyc", "__pycache__", ".pytest_cache", ".tox", "*.egg-info",
        # 仮想環境
        ".venv", "venv", "env", "node_modules",
        # ログ・キャッシュ
        "*.log", ".DS_Store", "*.tmp", ".cache",
        # 大容量キャッシュ
        "hf_cache",  # HuggingFaceキャッシュ
        ".streamlit/cache",
        # バージョン管理
        ".git", ".gitignore", ".github",
        # IDE
        ".vscode", ".idea", "*.swp", "*.swo",
        # OS
        "Thumbs.db", ".AppleDouble",
        # バックアップディレクトリ自体
        "backups"
    ]
    
    def __init__(
        self,
        project_root: str,
        backup_root: Optional[str] = None,
        compress: bool = True,
        compression_level: int = 6
    ):
        """
        初期化
        
        Args:
            project_root: プロジェクトルートパス
            backup_root: バックアップ保存先（デフォルト: project_root/backups）
                        環境変数 BACKUP_ROOT でも指定可能
            compress: tar.gzで圧縮するか
            compression_level: 圧縮レベル（1-9）
        """
        self.project_root = Path(project_root)
        
        # バックアップ先の決定順序: 引数 > 環境変数 > デフォルト
        if backup_root:
            backup_root_path = Path(backup_root)
        elif os.environ.get("BACKUP_ROOT"):
            backup_root_path = Path(os.environ["BACKUP_ROOT"])
            logger.info(f"環境変数 BACKUP_ROOT から指定: {backup_root_path}")
        else:
            backup_root_path = self.project_root / "backups"
        
        self.backup_root = backup_root_path
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self.compress = compress
        self.compression_level = compression_level
    
    def create_backup(
        self,
        targets: Optional[List[str]] = None,
        backup_name: Optional[str] = None,
        include_kb: bool = True,
        compression: bool = None,
        compress: bool = None,  # 後方互換性のため (compression が優先される)
        notes: str = ""
    ) -> Dict:
        """
        バックアップを作成
        
        Args:
            targets: バックアップ対象（config, self_improvement, multimodal等）
            backup_name: バックアップ名（デフォルト: タイムスタンプ）
            include_kb: 知識ベースを含めるか
            compression: 圧縮するか（Noneの場合はデフォルト値を使用）
            compress: 圧縮するか（後方互換性のため、compression が優先される）
            notes: バックアップの説明
        
        Returns:
            バックアップ情報辞書:
                - success: 成功したかどうか
                - backup_id: バックアップID
                - backup_path: バックアップパス
                - file_count: ファイル数
                - total_size: 合計サイズ（バイト）
                - timestamp: タイムスタンプ
                - notes: 説明
                - error: エラーメッセージ（失敗時）
        """
        # compression パラメータが優先、次に compress、最後にデフォルト値
        if compression is not None:
            use_compress = compression
        elif compress is not None:
            use_compress = compress
        else:
            use_compress = self.compress
        
        # バックアップID生成
        backup_id = backup_name or datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.backup_root / backup_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🔄 バックアップを開始: {backup_id}")
        
        # マニフェスト作成
        manifest = BackupManifest.create(
            backup_id=backup_id,
            version=self._get_project_version(),
            notes=notes
        )
        
        # デフォルトターゲット
        if targets is None:
            targets = list(self.BACKUP_TARGETS.keys())
            if not include_kb:
                targets.remove("knowledge_base")
        
        # 各ターゲットをバックアップ
        files_count = 0
        for target_key in targets:
            if target_key not in self.BACKUP_TARGETS:
                logger.warning(f"❌ 不明なターゲット: {target_key}")
                continue
            
            target_info = self.BACKUP_TARGETS[target_key]
            files_added = self._backup_target(
                target_key,
                target_info,
                backup_dir,
                manifest
            )
            files_count += files_added
        
        # マニフェストを保存
        manifest_path = backup_dir / "manifest.json"
        manifest.save(manifest_path)
        
        # 圧縮
        backup_path = backup_dir
        if use_compress:
            backup_path = self._compress_backup(backup_dir, backup_id)
            logger.info(f"✅ バックアップを圧縮: {backup_path}")
        
        logger.info(f"✅ バックアップ完了: {backup_id} ({files_count}ファイル)")
        
        return {
            "success": True,
            "backup_id": backup_id,
            "backup_path": str(backup_path),
            "file_count": files_count,
            "total_size": manifest.total_size,
            "timestamp": manifest.timestamp,
            "notes": notes
        }
    
    def restore_backup(
        self,
        backup_id: str,
        restore_root: Optional[str] = None,
        verify: bool = True
    ) -> bool:
        """
        バックアップをリストア
        
        Args:
            backup_id: バックアップID
            restore_root: リストア先（デフォルト: プロジェクトルート）
            verify: マニフェストで検証するか
        
        Returns:
            成功したかどうか
        """
        restore_root = Path(restore_root or self.project_root)
        
        # バックアップパスを探す
        backup_source = self._find_backup(backup_id)
        if not backup_source:
            logger.error(f"❌ バックアップが見つかりません: {backup_id}")
            return False
        
        logger.info(f"🔄 リストアを開始: {backup_id}")
        
        # 圧縮ファイルの場合は解凍
        backup_dir = backup_source
        if str(backup_source).endswith(".tar.gz"):
            backup_dir = self.backup_root / f"temp_{backup_id}"
            self._decompress_backup(backup_source, backup_dir)
        
        # マニフェストを読み込み
        manifest_path = backup_dir / "manifest.json"
        if verify and manifest_path.exists():
            try:
                manifest = BackupManifest.load(manifest_path)
                logger.info(f"📋 マニフェスト検証: {manifest.backup_id}")
            except Exception as e:
                logger.error(f"❌ マニフェスト検証失敗: {e}")
                return False
        
        # ファイルをリストア
        restored_count = 0
        for item in Path(backup_dir).glob("**/*"):
            if item.is_file() and item.name != "manifest.json":
                relative_path = item.relative_to(backup_dir)
                
                # 相対パスを復元先にマッピング
                for target_key, target_info in self.BACKUP_TARGETS.items():
                    for path_pattern in target_info["paths"]:
                        if str(relative_path).startswith(path_pattern.rstrip("*")):
                            dest_path = restore_root / relative_path
                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(item, dest_path)
                            restored_count += 1
                            break
        
        logger.info(f"✅ リストア完了: {restored_count}ファイル")
        
        # 一時ディレクトリをクリーンアップ
        if backup_dir != backup_source and backup_dir.exists():
            shutil.rmtree(backup_dir)
        
        return True
    
    def list_backups(self) -> List[Dict]:
        """利用可能なバックアップ一覧を取得"""
        backups = []
        
        # ディレクトリとtar.gzファイルをスキャン
        for item in sorted(self.backup_root.iterdir(), reverse=True):
            if item.name.startswith("temp_"):
                continue
            
            try:
                if item.is_dir() and (item / "manifest.json").exists():
                    manifest = BackupManifest.load(item / "manifest.json")
                    backups.append(manifest.get_summary())
                elif item.suffix == ".gz" and item.name.endswith(".tar.gz"):
                    # 圧縮ファイルの情報を取得
                    backups.append({
                        "backup_id": item.stem.replace(".tar", ""),
                        "size_mb": round(item.stat().st_size / (1024 ** 2), 2),
                        "type": "compressed"
                    })
            except Exception as e:
                logger.warning(f"⚠️ バックアップ情報取得失敗: {item.name} - {e}")
        
        return backups
    
    def delete_backup(self, backup_id: str) -> bool:
        """バックアップを削除"""
        backup_source = self._find_backup(backup_id)
        if not backup_source:
            logger.error(f"❌ バックアップが見つかりません: {backup_id}")
            return False
        
        try:
            if backup_source.is_dir():
                shutil.rmtree(backup_source)
            else:
                backup_source.unlink()
            
            logger.info(f"✅ バックアップを削除: {backup_id}")
            return True
        except Exception as e:
            logger.error(f"❌ 削除失敗: {e}")
            return False
    
    def cleanup_old_backups(self, keep_days: int = 30, keep_count: int = 5):
        """古いバックアップをクリーンアップ"""
        backups = sorted(self.backup_root.iterdir(), reverse=True)
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        
        removed_count = 0
        for backup_dir in backups[keep_count:]:
            if backup_dir.name.startswith("temp_"):
                continue
            
            try:
                # ディレクトリの作成日時を確認
                stat_info = backup_dir.stat()
                creation_date = datetime.fromtimestamp(stat_info.st_mtime)
                
                if creation_date < cutoff_date:
                    if backup_dir.is_dir():
                        shutil.rmtree(backup_dir)
                    else:
                        backup_dir.unlink()
                    removed_count += 1
                    logger.info(f"🗑️ 古いバックアップを削除: {backup_dir.name}")
            except Exception as e:
                logger.warning(f"⚠️ クリーンアップ失敗: {backup_dir.name} - {e}")
        
        if removed_count > 0:
            logger.info(f"✅ {removed_count}個の古いバックアップを削除")
        else:
            logger.info("ℹ️ 削除対象のバックアップはありません")
    
    def get_backup_size(self, backup_id: str) -> Optional[int]:
        """バックアップのサイズを取得（バイト）"""
        backup_source = self._find_backup(backup_id)
        if not backup_source:
            return None
        
        if backup_source.is_dir():
            total = 0
            for item in backup_source.rglob("*"):
                if item.is_file():
                    total += item.stat().st_size
            return total
        else:
            return backup_source.stat().st_size
    
    # ===== 内部メソッド =====
    
    def _backup_target(
        self,
        target_key: str,
        target_info: Dict,
        backup_dir: Path,
        manifest: BackupManifest
    ) -> int:
        """ターゲットをバックアップ"""
        files_count = 0
        
        for path_pattern in target_info["paths"]:
            source_paths = self._resolve_paths(path_pattern)
            
            for source_path in source_paths:
                if not source_path.exists():
                    logger.debug(f"⏭️ スキップ（未存在）: {source_path}")
                    continue
                
                # Destination path inside the backup. If the source path is not
                # under the configured project_root (we may have fallen back to
                # parent directories), compute a sensible relative path.
                try:
                    rel_path = source_path.relative_to(self.project_root)
                except Exception:
                    try:
                        rel_path = source_path.relative_to(self.project_root.parent)
                    except Exception:
                        # as a last resort, use the file/directory name only
                        rel_path = Path(source_path.name)

                dest_path = backup_dir / rel_path
                
                # コピー
                if source_path.is_file():
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, dest_path)
                    files_count += 1
                elif source_path.is_dir():
                    # ディレクトリをコピー（除外パターンを適用）
                    copied = self._copy_directory(
                        source_path,
                        dest_path
                    )
                    files_count += copied
                
                # マニフェストにアイテムを追加
                item = BackupItem(
                    source_path=str(rel_path),
                    relative_path=str(dest_path.relative_to(backup_dir)),
                    item_type="folder" if source_path.is_dir() else "file"
                )
                
                # 統計情報を計算
                if source_path.is_dir():
                    for f in source_path.rglob("*"):
                        if f.is_file():
                            item.file_count += 1
                            item.total_size += f.stat().st_size
                else:
                    item.file_count = 1
                    item.total_size = source_path.stat().st_size
                
                manifest.add_item(item)
        
        logger.info(f"  ✓ {target_key}: {files_count}ファイル")
        return files_count
    
    def _copy_directory(
        self,
        source_dir: Path,
        dest_dir: Path
    ) -> int:
        """ディレクトリをコピー（除外パターン適用）"""
        file_count = 0
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        for item in source_dir.rglob("*"):
            if item.is_file():
                # 除外パターンチェック
                if self._should_exclude(item):
                    continue
                
                relative = item.relative_to(source_dir)
                dest_path = dest_dir / relative
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                try:
                    shutil.copy2(item, dest_path)
                    file_count += 1
                except Exception as e:
                    logger.warning(f"⚠️ コピー失敗: {item} - {e}")
        
        return file_count
    
    def _resolve_paths(self, pattern: str) -> List[Path]:
        """パターンからパスを解決"""
        if "*" in pattern:
            # グロブパターン
            matches = list(self.project_root.glob(pattern))
            return [m for m in matches if m.exists()]
        else:
            path = self.project_root / pattern
            if path.exists():
                return [path]

            # テスト環境や UI シミュレーションでは project_root が tests/ の場合がある。
            # その際、リポジトリルート直下に対象が存在することが多いため
            # 親ディレクトリも検索してフォールバックする。
            parent_path = self.project_root.parent / pattern
            if parent_path.exists():
                return [parent_path]

            # さらに上位も試す（安全策）
            grand_parent_path = self.project_root.parent.parent / pattern
            if grand_parent_path.exists():
                return [grand_parent_path]

            return []
    
    def _should_exclude(self, path: Path) -> bool:
        """除外対象かチェック"""
        path_str = str(path)
        for pattern in self.EXCLUDE_PATTERNS:
            if "*" in pattern:
                # グロブパターン
                if path.match(pattern):
                    return True
            elif pattern in path_str:
                return True
        return False
    
    def _compress_backup(
        self,
        backup_dir: Path,
        backup_id: str
    ) -> Path:
        """バックアップをtar.gzで圧縮"""
        archive_path = self.backup_root / f"{backup_id}.tar.gz"
        
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(
                backup_dir,
                arcname=backup_id
            )
        
        # 元のディレクトリを削除
        shutil.rmtree(backup_dir)
        
        return archive_path
    
    def _decompress_backup(
        self,
        archive_path: Path,
        extract_dir: Path
    ):
        """tar.gzを解凍"""
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(extract_dir)
    
    def _find_backup(self, backup_id: str) -> Optional[Path]:
        """バックアップを探す"""
        # ディレクトリを探す
        backup_dir = self.backup_root / backup_id
        if backup_dir.exists():
            return backup_dir
        
        # 圧縮ファイルを探す
        archive_path = self.backup_root / f"{backup_id}.tar.gz"
        if archive_path.exists():
            return archive_path
        
        return None
    
    def _get_project_version(self) -> str:
        """プロジェクトバージョンを取得"""
        pyproject_path = self.project_root / "pyproject.toml"
        if pyproject_path.exists():
            with open(pyproject_path, "r") as f:
                for line in f:
                    if "version" in line:
                        return line.strip().split('"')[1]
        return "unknown"
