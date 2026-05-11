"""プロジェクトバックアップシステムのテスト"""

import unittest
import tempfile
import shutil
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from backup.backup_manager import ProjectBackupManager
from backup.manifest import BackupManifest, BackupItem


class TestBackupManager(unittest.TestCase):
    """バックアップマネージャーテスト"""
    
    @classmethod
    def setUpClass(cls):
        """テストクラスのセットアップ"""
        cls.temp_dir = tempfile.mkdtemp()
        cls.project_root = Path(cls.temp_dir) / "project"
        cls.backup_root = Path(cls.temp_dir) / "backups"
        
        # テスト用プロジェクト構造を作成
        cls.project_root.mkdir(parents=True)
        (cls.project_root / "prompt.txt").write_text("Test prompt")
        (cls.project_root / "pyproject.toml").write_text("[project]\nname = test")
        
        # ディレクトリ構造
        (cls.project_root / "logs" / "feedback").mkdir(parents=True)
        (cls.project_root / "logs" / "feedback" / "feedback.jsonl").write_text("")
        
        (cls.project_root / "src" / "backup").mkdir(parents=True)
        (cls.project_root / "src" / "backup" / "test.py").write_text("# Test")
        
        (cls.project_root / "src" / "multimodal").mkdir(parents=True)
        (cls.project_root / "src" / "multimodal" / "test.py").write_text("# Test")
        
        (cls.project_root / "checkpoints").mkdir(parents=True)
        (cls.project_root / "checkpoints" / "ckpt.pt").write_text("checkpoint data")
    
    @classmethod
    def tearDownClass(cls):
        """テストクラスのクリーンアップ"""
        shutil.rmtree(cls.temp_dir)
    
    def setUp(self):
        """各テストのセットアップ"""
        self.manager = ProjectBackupManager(self.project_root, self.backup_root)
    
    def test_init(self):
        """初期化テスト"""
        self.assertIsNotNone(self.manager)
        self.assertTrue(self.backup_root.exists())
    
    def test_create_backup_config_only(self):
        """設定のみバックアップ"""
        result = self.manager.create_backup(
            targets=["system_config"],
            backup_name="test_config",
            compression=False
        )
        
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("backup_id"), "test_config")
        self.assertTrue(result.get("backup_path"))
    
    def test_create_backup_multiple_targets(self):
        """複数ターゲットバックアップ"""
        result = self.manager.create_backup(
            targets=["system_config", "source_code"],
            backup_name="test_multi",
            compression=False
        )
        
        self.assertTrue(result.get("success"))
        self.assertGreaterEqual(result.get("file_count", 0), 1)
    
    def test_create_backup_compressed(self):
        """圧縮バックアップ"""
        result = self.manager.create_backup(
            targets=["system_config"],
            backup_name="test_compressed",
            compression=True
        )
        
        self.assertTrue(result.get("success"))
        backup_path = result.get("backup_path", "")
        self.assertTrue(backup_path.endswith(".tar.gz"))
        self.assertTrue(Path(backup_path).exists())
    
    def test_list_backups(self):
        """バックアップ一覧"""
        # バックアップを作成
        self.manager.create_backup(
            targets=["config"],
            backup_name="test_list1",
            compression=False
        )
        self.manager.create_backup(
            targets=["config"],
            backup_name="test_list2",
            compression=True
        )
        
        backups = self.manager.list_backups()
        
        self.assertGreaterEqual(len(backups), 2)
        backup_ids = [b.get("backup_id") for b in backups]
        self.assertIn("test_list1", backup_ids)
        self.assertIn("test_list2", backup_ids)
    
    def test_manifest(self):
        """マニフェストテスト"""
        manifest = BackupManifest.create(
            backup_id="test",
            version="1.0.0",
            notes="Test backup"
        )
        
        item = BackupItem(
            source_path="test/path",
            relative_path="test/path",
            file_count=5,
            total_size=1024
        )
        manifest.add_item(item)
        
        self.assertEqual(len(manifest.items), 1)
        self.assertEqual(manifest.total_size, 1024)
        
        # Save and load
        manifest_path = Path(self.temp_dir) / "test_manifest.json"
        manifest.save(manifest_path)
        
        loaded_manifest = BackupManifest.load(manifest_path)
        self.assertEqual(loaded_manifest.backup_id, "test")
        self.assertEqual(len(loaded_manifest.items), 1)
    
    def test_get_backup_size(self):
        """バックアップサイズ取得"""
        result = self.manager.create_backup(
            targets=["system_config"],
            backup_name="test_size",
            compression=False
        )
        result.get("backup_path")
        
        size = self.manager.get_backup_size("test_size")
        self.assertIsNotNone(size)
        self.assertGreater(size, 0)
    
    def test_delete_backup(self):
        """バックアップ削除"""
        self.manager.create_backup(
            targets=["config"],
            backup_name="test_delete",
            compression=False
        )
        
        backups_before = len(self.manager.list_backups())
        
        result = self.manager.delete_backup("test_delete")
        self.assertTrue(result)
        
        backups_after = len(self.manager.list_backups())
        self.assertEqual(backups_before - 1, backups_after)
    
    def test_exclude_patterns(self):
        """除外パターン"""
        # __pycache__ ディレクトリを作成
        pycache_dir = self.project_root / "src" / "__pycache__"
        pycache_dir.mkdir(parents=True, exist_ok=True)
        (pycache_dir / "test.pyc").write_text("compiled")
        
        # バックアップ作成
        result = self.manager.create_backup(
            targets=["system_config"],
            compression=False
        )
        result.get("backup_path")
    """バックアップアイテムテスト"""
    
    def test_create_item(self):
        """アイテム作成"""
        item = BackupItem(
            source_path="src/test.py",
            relative_path="src/test.py",
            file_count=1,
            total_size=1024,
            item_type="file"
        )
        
        self.assertEqual(item.source_path, "src/test.py")
        self.assertEqual(item.file_count, 1)


def run_tests():
    """テスト実行"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestBackupManager))
    suite.addTests(loader.loadTestsFromTestCase(TestBackupItem))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
