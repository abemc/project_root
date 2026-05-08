#!/usr/bin/env python3
"""Streamlit UI での外部ドライブ指定機能の統合テスト"""

import sys
from pathlib import Path
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from backup.backup_manager import ProjectBackupManager

def test_ui_integration():
    """UI 統合テスト"""
    
    print("\n" + "="*70)
    print("🧪 Streamlit UI 外部ドライブ指定機能テスト")
    print("="*70)
    
    # Test 1: UI で選択される典型的なシナリオ
    print("\n[Test 1] Streamlit UI シナリオ: デフォルト保存先")
    manager1 = ProjectBackupManager(project_root=PROJECT_ROOT)
    result1 = manager1.create_backup(
        targets=["system_config", "source_code"],
        backup_name="ui_default"
    )
    print_result("デフォルト", result1)
    
    # Test 2: UI で Linux/WSL パスを入力
    print("\n[Test 2] UI シナリオ: Linux/WSL パス入力")
    with tempfile.TemporaryDirectory() as tmpdir:
        external_path = Path(tmpdir) / "external_usb"
        external_path.mkdir()
        
        manager2 = ProjectBackupManager(
            project_root=PROJECT_ROOT,
            backup_root=str(external_path)
        )
        result2 = manager2.create_backup(
            targets=["system_config", "source_code"],
            backup_name="ui_linux_path"
        )
        print_result("Linux/WSL パス指定", result2)
        assert str(external_path) in result2.get('backup_path', ''), "パスが正しく使用されていない"
    
    # Test 3: UI で Windows ドライブ選択（シミュレーション）
    print("\n[Test 3] UI シナリオ: Windows ドライブ選択（/mnt/d をシミュレート）")
    with tempfile.TemporaryDirectory() as tmpdir:
        # /mnt/d をシミュレート
        simulated_mnt_d = Path(tmpdir) / "mnt" / "d"
        simulated_mnt_d.mkdir(parents=True)
        
        manager3 = ProjectBackupManager(
            project_root=PROJECT_ROOT,
            backup_root=str(simulated_mnt_d)
        )
        result3 = manager3.create_backup(
            targets=["system_config", "source_code"],
            backup_name="ui_win_drive"
        )
        print_result("Windows ドライブ選択", result3)
        assert "mnt" in result3.get('backup_path', ''), "WSL パスが正しく使用されていない"
    
    # Test 4: UI で macOS パスを入力
    print("\n[Test 4] UI シナリオ: macOS パス入力")
    with tempfile.TemporaryDirectory() as tmpdir:
        mac_path = Path(tmpdir) / "Volumes" / "External"
        mac_path.mkdir(parents=True)
        
        manager4 = ProjectBackupManager(
            project_root=PROJECT_ROOT,
            backup_root=str(mac_path)
        )
        result4 = manager4.create_backup(
            targets=["system_config", "source_code"],
            backup_name="ui_mac_path"
        )
        print_result("macOS パス指定", result4)
        assert str(mac_path) in result4.get('backup_path', ''), "macOS パスが正しく使用されていない"
    
    # Test 5: 複数ターゲット選択（UI で typical selection）
    print("\n[Test 5] UI シナリオ: 複数ターゲット選択（推奨設定）")
    manager5 = ProjectBackupManager(project_root=PROJECT_ROOT)
    result5 = manager5.create_backup(
        targets=["system_config", "source_code", "documentation"],
        backup_name="ui_multi_targets"
    )
    print_result("複数ターゲット", result5)
    assert result5.get('file_count', 0) > 0, "ファイルが正しく含まれていない"
    
    # Test 6: 圧縮オプション有効
    print("\n[Test 6] UI シナリオ: 圧縮有効")
    manager6 = ProjectBackupManager(project_root=PROJECT_ROOT)
    result6 = manager6.create_backup(
        targets=["system_config"],
        backup_name="ui_compressed",
        compression=True
    )
    print_result("圧縮有効", result6)
    assert result6.get('backup_path', '').endswith('.tar.gz'), "圧縮されていない"
    
    # Test 7: 圧縮オプション無効
    print("\n[Test 7] UI シナリオ: 圧縮無効")
    manager7 = ProjectBackupManager(project_root=PROJECT_ROOT)
    result7 = manager7.create_backup(
        targets=["system_config"],
        backup_name="ui_no_compress",
        compression=False
    )
    print_result("圧縮無効", result7)
    assert not result7.get('backup_path', '').endswith('.tar.gz'), "圧縮されてしまった"
    
    # Test 8: メモ付きバックアップ
    print("\n[Test 8] UI シナリオ: メモ付きバックアップ")
    manager8 = ProjectBackupManager(project_root=PROJECT_ROOT)
    result8 = manager8.create_backup(
        targets=["system_config"],
        backup_name="ui_with_notes",
        notes="UI テスト: 2026-04-19 メモ付きバックアップ"
    )
    print_result("メモ付き", result8)
    assert result8.get('notes') == "UI テスト: 2026-04-19 メモ付きバックアップ", "メモが正しく保存されていない"
    
    print("\n" + "="*70)
    print("✅ すべての UI 統合テストが成功しました！")
    print("="*70)
    
    print("\n📋 Streamlit UI での外部ドライブ指定方法:")
    print("  1. サイドバー「💾 バックアップ・リストア」を展開")
    print("  2. 「🔧 ストレージ設定」エクスパンダーをクリック")
    print("  3. 「☑️ 外部ドライブを使用」にチェック")
    print("  4. ドライブ種別を選択（Linux/WSL, Windows, macOS）")
    print("  5. パスを入力またはドライブを選択")
    print("  6. バックアップ対象を選択して「✨ バックアップを作成」をクリック")
    
    return True

def print_result(label, result):
    """結果をフォーマットして表示"""
    if result.get("success"):
        print(f"  ✅ {label}: 成功")
        print(f"     ID: {result.get('backup_id')}")
        print(f"     パス: {result.get('backup_path')}")
        size_mb = result.get('total_size', 0) / (1024**2)
        print(f"     サイズ: {size_mb:.2f} MB")
    else:
        print(f"  ❌ {label}: 失敗")
        print(f"     エラー: {result.get('error')}")
        return False
    return True

if __name__ == "__main__":
    try:
        success = test_ui_integration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
