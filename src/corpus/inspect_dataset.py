from pathlib import Path
import warnings

# datasetsライブラリが内部でrequestsを呼び出す際の警告を抑制します。
# これは対症療法であり、根本的にはpipで依存関係を解決することが推奨されます。
try:
    from requests.exceptions import RequestsDependencyWarning
    warnings.filterwarnings("ignore", category=RequestsDependencyWarning)
except ImportError:
    pass  # requestsがなければ警告も出ない

from datasets import load_dataset

def main():
    """
    生成された dataset.jsonl を Hugging Face の Dataset オブジェクトとして読み込み、
    その内容を確認するためのスクリプト。
    """
    # 1. プロジェクトルートとデータセットファイルのパスを指定
    #    このスクリプトは src/corpus/ にあるため、parents[2]でルートを取得
    project_root = Path(__file__).resolve().parents[2]
    corpus_root = get_corpus_path()
    dataset_path = str(corpus_root / "dataset.jsonl")

    print(f"Loading dataset from: {dataset_path}")

    # 2. `load_dataset` 関数でJSONLファイルを読み込む
    #    - 第1引数に 'json' を指定します。
    #    - `data_files` 引数にファイルのパスを渡します。
    try:
        # data_filesに単一ファイルを指定した場合、デフォルトで 'train' スプリットとして読み込まれます。
        dataset_dict = load_dataset('json', data_files=dataset_path)

        # DatasetDictから'train'スプリットを取得
        dataset = dataset_dict['train']

        # 3. 読み込んだデータセットの情報を表示
        print("\n--- Dataset Info ---")
        print(dataset)

        # 4. データセットの最初の1件を表示して中身を確認
        print("\n--- First Record ---")
        print(dataset[0])

        # 5. カラム名（特徴量）を確認
        print("\n--- Features ---")
        print(dataset.features)

    except FileNotFoundError:
        print(f"\n[ERROR] Dataset file not found at: {dataset_path}")
        print("Please make sure you have run 'create_dataset.py' first.")
    except Exception as e:
        print(f"\n[ERROR] An error occurred: {e}")

if __name__ == "__main__":
    main()