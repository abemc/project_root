import os
import zipfile
import datetime
from pathlib import Path
from src.utils.path_utils import get_corpus_path

# ============================================================
# バックアップスクリプト
# プロジェクトルート以下のファイルをzip圧縮して backups/ に保存します。
# ============================================================

# src/backup.py から見て parents[1] がプロジェクトルート (/home/abemc/project_root)
ROOT_DIR = Path(__file__).resolve().parents[1]
BACKUP_DIR = ROOT_DIR / "backups"
CORPUS_PATH = get_corpus_path()

# バックアップから除外するディレクトリ名と拡張子
EXCLUDE_DIRS = {
    "__pycache__", ".git", ".idea", ".vscode", "venv", ".venv", "env",
    "node_modules", "backups"
}
EXCLUDE_EXTENSIONS = {".pyc", ".pyo", ".pyd", ".DS_Store"}

# 保持するバックアップファイルの最大数
MAX_BACKUPS = 5

def create_backup():
    """プロジェクトディレクトリをzipアーカイブとしてバックアップする"""
    if not BACKUP_DIR.exists():
        BACKUP_DIR.mkdir()

    # タイムスタンプ付きファイル名 (例: project_backup_20231027_120000.zip)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = BACKUP_DIR / f"project_backup_{timestamp}.zip"

    print(f"Creating backup...")
    print(f"Target file:        {zip_filename}")

    # バックアップ対象リスト: (実際のディレクトリパス, ZIP内でのフォルダ名)
    targets = [
        (ROOT_DIR, "project_root"),
        (CORPUS_PATH, "rag_corpus"),
    ]

    try:
        with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
            for src_dir, arc_prefix in targets:
                if not src_dir.exists():
                    print(f"[WARN] Directory not found, skipping: {src_dir}")
                    continue
                
                print(f"  -> Archiving: {src_dir}")
                for root, dirs, files in os.walk(src_dir):
                    # 除外ディレクトリを探索対象から外す (in-place変更が必要)
                    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

                    for file in files:
                        file_path = Path(root) / file
                        if file_path.suffix in EXCLUDE_EXTENSIONS:
                            continue

                        # zip内でのパス名: prefix / (src_dirからの相対パス)
                        arcname = Path(arc_prefix) / file_path.relative_to(src_dir)
                        zipf.write(file_path, str(arcname))

        print(f"Backup created successfully!")
        print(f"Size: {zip_filename.stat().st_size / (1024*1024):.2f} MB")

        cleanup_old_backups()

    except Exception as e:
        print(f"[ERROR] Failed to create backup: {e}")

def cleanup_old_backups():
    """古いバックアップファイルを削除して、最新の MAX_BACKUPS 個だけ残す"""
    # ファイル名でソート（タイムスタンプ付きなので文字列ソートで時系列順になる）
    backups = sorted(list(BACKUP_DIR.glob("project_backup_*.zip")))

    if len(backups) > MAX_BACKUPS:
        # 削除対象: 古いものから (総数 - 保持数) 個
        files_to_delete = backups[: -MAX_BACKUPS]
        
        print(f"\nCleaning up old backups (keeping latest {MAX_BACKUPS})...")
        for f in files_to_delete:
            print(f"  - Deleting old backup: {f.name}")
            f.unlink()

if __name__ == "__main__":
    create_backup()