"""
Diagram Settings: UI上での図解表示（Mermaid/HTML）のモード管理と、
クエリに応じた図解タイトル・ステップ自動生成などのヘルパー関数。
"""

from typing import List, Any
import re

# 定数定義
DIAGRAM_MODE_MERMAID = "mermaid"
DIAGRAM_MODE_HTML = "html"


def diagram_mode_options() -> List[str]:
    """StreamlitのUIのセレクトボックス等で表示するラベルのオプションリストを返します。"""
    return [
        "Mermaid (インタラクティブ図解)",
        "HTML (静的フロー図)"
    ]


def diagram_mode_to_label(mode: str) -> str:
    """内部モード値（'mermaid' / 'html'）をUI表示用ラベルに変換します。"""
    if mode == DIAGRAM_MODE_MERMAID:
        return "Mermaid (インタラクティブ図解)"
    return "HTML (静的フロー図)"


def diagram_mode_from_label(label: str) -> str:
    """UI表示用ラベルを内部モード値（'mermaid' / 'html'）に変換します。"""
    if not label:
        return DIAGRAM_MODE_HTML
    if "mermaid" in label.lower() or "Mermaid" in label:
        return DIAGRAM_MODE_MERMAID
    return DIAGRAM_MODE_HTML


def normalize_diagram_mode(mode: Any) -> str:
    """モード入力を標準的な内部表現 ('mermaid' または 'html') に正規化します。"""
    if not mode:
        return DIAGRAM_MODE_HTML
    mode_str = str(mode).lower()
    if "mermaid" in mode_str:
        return DIAGRAM_MODE_MERMAID
    return DIAGRAM_MODE_HTML


def diagram_title_for_query(query: str) -> str:
    """クエリに基づいて、図解の適切なタイトル（日本語）を自動生成します。"""
    q = (query or "質問").strip().replace("\n", " ")[:30]
    return f"「{q}...」の解決プロセスと関係図"


def diagram_steps_for_query(query: str) -> List[str]:
    """クエリの意図に基づいて、図解のフロー（ステップ）を自動生成します。"""
    q = (query or "").lower()
    
    # 構造やシステムに関する質問の場合
    if re.search(r"構造|仕組み|関係|システム|構成|設計|アーキテクチャ", q):
        return [
            "構成要素の洗い出し",
            "各モジュール間の依存関係整理",
            "データの入出力フロー定義",
            "システム全体の統合と動作確認"
        ]
    
    # 手順や方法に関する質問の場合
    elif re.search(r"流れ|手順|プロセス|やり方|方法|順序|学習", q):
        return [
            "前提条件と目的の明確化",
            "リソースおよびツールの準備",
            "コアプロセスの段階的実行",
            "検証テストと最終結果確認"
        ]
    
    # その他の一般的な質問の場合
    else:
        return [
            "質問の意図・要点整理",
            "関連ナレッジのセマンティック検索",
            "因果関係に基づく論理推論",
            "整合性の取れた最終結論の提示"
        ]
