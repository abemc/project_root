import shutil
import datetime
import os
import argparse
from pathlib import Path
import sys

# デフォルト設定
DEFAULT_CORPUS_DIR = "/mnt/d/rag_corpus"
DEFAULT_BACKUP_ROOT = "backups"

def cleanup_old_backups(backup_root, keep):
    """古いバックアップを削除して、指定された数以下に保つ"""
    root = Path(backup_root)
    if not root.exists():
        return

    # バックアップ一覧を取得 (名前順 = 日時順)
    # pre_restore_ で始まるディレクトリも含め、辞書順でソートされます。
    # 数字で始まる通常のバックアップが 'p' で始まる pre_restore よりも先に来るため、
    # 通常のバックアップから先に削除される安全な挙動になります。
    backups = sorted([d for d in root.iterdir() if d.is_dir()])
    
    if len(backups) > keep:
        num_to_delete = len(backups) - keep
        print(f"\nバックアップ保存数が制限({keep})を超えています。古いバックアップ {num_to_delete} 件を削除します...")
        
        to_delete = backups[:num_to_delete]
        for d in to_delete:
            try:
                print(f"  - 削除中: {d.name}")
                shutil.rmtree(d)
            except Exception as e:
                print(f"  - 削除エラー ({d.name}): {e}")

def create_backup(corpus_dir, backup_root, keep_count=5):
    """知識ベースのバックアップを作成する"""
    src = Path(corpus_dir)
    if not src.exists():
        print(f"エラー: 知識ベースのディレクトリ '{src}' が見つかりません。")
        print("\n【よくある原因と対処法】")
        print("- パスの指定ミス → --corpus オプションで正しいパスを指定してください")
        print("- ディレクトリがまだ作成されていない → 先に知識ベースを作成してください")
        print("- 権限エラー → 実行ユーザーの権限を確認してください")
        print("- 詳細はAIベギナーガイドのFAQも参照してください")
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = Path(backup_root) / timestamp

    print(f"バックアップを作成中: '{src}' -> '{dest}' ...")
    try:
        shutil.copytree(src, dest)
        print(f"成功: バックアップが '{dest}' に作成されました。")

        # 古いバックアップの削除
        if keep_count > 0:
            cleanup_old_backups(backup_root, keep_count)

    except Exception as e:
        print(f"エラー: バックアップの作成に失敗しました: {e}")
        raise

def get_backup_list(backup_root):
    """利用可能なバックアップのリストを日時の降順で返す"""
    root = Path(backup_root)
    if not root.exists():
        return []
    
    # ユーザーがリストア対象として選択すべきではない pre_restore_ バックアップは除外する
    backups = sorted(
        [d for d in root.iterdir() if d.is_dir() and not d.name.startswith("pre_restore_")], 
        key=lambda p: p.name, 
        reverse=True
    )
    return [b.name for b in backups]

def execute_restore(backup_name, backup_root, corpus_dir):
    """指定された名前のバックアップから知識ベースを復元する"""
    backup_path = Path(backup_root) / backup_name
    target_path = Path(corpus_dir)

    if not backup_path.exists() or not backup_path.is_dir():
        print(f"エラー: 指定されたバックアップ '{backup_name}' が見つかりません。")
        print("\n【よくある原因と対処法】")
        print("- バックアップ名のタイプミス → 利用可能なリストから正しい名前を選択してください")
        print("- バックアップが削除・移動されていないか確認してください")
        print("- 詳細はAIベギナーガイドのFAQも参照してください")
        return

    # 現在の状態を安全のために退避
    if target_path.exists():
        safety_backup_name = f"pre_restore_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        safety_backup_path = Path(backup_root) / safety_backup_name
        print(f"現在の状態を一時退避中: '{target_path}' -> '{safety_backup_path}' ...")
        shutil.move(str(target_path), str(safety_backup_path))
    
    # 復元実行
    print(f"復元中: '{backup_path}' -> '{target_path}' ...")
    shutil.copytree(backup_path, target_path)
    print("完了: 知識ベースが復元されました。")

def restore_backup(backup_root, corpus_dir):
    """バックアップから復元する"""
    root = Path(backup_root)
    if not root.exists():
        print(f"エラー: バックアップディレクトリ '{root}' が見つかりません。")
        print("\n【よくある原因と対処法】")
        print("- --backups オプションで正しいパスを指定してください")
        print("- ディレクトリがまだ作成されていない場合は backup 操作を先に実行してください")
        print("- 権限エラー → 実行ユーザーの権限を確認してください")
        print("- 詳細はAIベギナーガイドのFAQも参照してください")
        return

    # バックアップ一覧を取得
    backup_names = get_backup_list(backup_root)
    if not backup_names:
        print("利用可能なバックアップがありません。")
        print("\n【よくある原因と対処法】")
        print("- まだ一度も backup 操作を実行していない → 先に backup を実行してください")
        print("- バックアップ保存先パスが間違っていないか確認してください")
        print("- 詳細はAIベギナーガイドのFAQも参照してください")
        return

    print("\n=== 利用可能なバックアップ ===")
    for i, name in enumerate(backup_names):
        print(f"{i+1}. {name}")
    print("============================")

    try:
        choice = input("\n復元したいバックアップの番号を入力してください (中止するには 'q'): ")
        if choice.lower() == 'q':
            print("キャンセルしました。")
            return
        
        idx = int(choice) - 1
        if 0 <= idx < len(backup_names):
            selected_backup_name = backup_names[idx]

            print(f"\n'{selected_backup_name}' を '{corpus_dir}' に復元します。")
            confirm = input("現在の知識ベースは上書きされます（自動で退避されます）。よろしいですか？ [y/N]: ")
            if confirm.lower() != 'y':
                print("キャンセルしました。")
                return

            # 復元実行
            print("復元中...")
            execute_restore(selected_backup_name, backup_root, corpus_dir)
        else:
            print("エラー: 無効な番号です。")
    except ValueError:
        print("エラー: 数字を入力してください。")
        print("\n【ヒント】リストに表示された番号を半角数字で入力してください。キャンセルは 'q' です。")
    except Exception as e:
        print(f"エラー: 復元中に問題が発生しました: {e}")
        print("\n【よくある原因と対処法】")
        print("- ディスク容量不足や権限エラーの可能性があります")
        print("- 詳細なエラー内容をAIベギナーガイドのFAQと照らし合わせてください")

def main():
    parser = argparse.ArgumentParser(description="知識ベース（Corpus）のバックアップとリストアツール")
    parser.add_argument("action", choices=["backup", "restore"], help="実行する操作: backup または restore")
    parser.add_argument("--corpus", default=DEFAULT_CORPUS_DIR, help=f"知識ベースのディレクトリパス (デフォルト: {DEFAULT_CORPUS_DIR})")
    parser.add_argument("--backups", default=DEFAULT_BACKUP_ROOT, help=f"バックアップ保存先ディレクトリ (デフォルト: {DEFAULT_BACKUP_ROOT})")
    parser.add_argument("--keep", type=int, default=5, help="保持するバックアップの最大数 (デフォルト: 5, 0で無制限)")
    
    args = parser.parse_args()
    
    if args.action == "backup":
        create_backup(args.corpus, args.backups, args.keep)
    elif args.action == "restore":
        restore_backup(args.backups, args.corpus)

if __name__ == "__main__":
    main()