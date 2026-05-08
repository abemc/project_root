#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG Agent サイドバーモジュール
ドキュメント管理ダッシュボードにRAG機能を統合
"""

import streamlit as st
from pathlib import Path
from datetime import datetime
import shutil
import os
from docs_manager import DocumentManager
from rag_agent_config import RAGAgentConfig

try:
    from src.rag.retriever import Retriever
    retriever_available = True
except ImportError:
    Retriever = None
    retriever_available = False


@st.cache_resource
def get_retriever():
    """Corpus 検索用 Retriever を初期化する。"""
    if not retriever_available:
        return None

    corpus_path = Path(__file__).resolve().parent / "corpus"
    index_path = corpus_path / "corpus.index"
    meta_path = corpus_path / "corpus_meta.json"

    try:
        return Retriever(index_path=index_path, meta_path=meta_path)
    except Exception:
        return None


def _search_corpus(retriever, question, search_method, top_k):
    """設定に応じて Corpus を検索する。"""
    if retriever is None:
        return []

    if search_method == "BM25":
        return retriever.search_keyword(question, top_k=top_k)
    if search_method == "ベクトル検索":
        return retriever.search(question, top_k=top_k)
    return retriever.hybrid_search(question, top_k=top_k)


def _enrich_result(doc, doc_lookup):
    """Retriever の結果を表示用に整形する。"""
    meta = doc.get("meta", {})
    source_name = meta.get("source") or doc.get("source") or doc.get("id", "unknown")
    doc_info = doc_lookup.get(source_name, {})
    return {
        "name": source_name,
        "category": doc_info.get("category", meta.get("category", "knowledge_base")),
        "path": doc_info.get("path", meta.get("path", "corpus/corpus_meta.json")),
        "score": float(doc.get("score", 0.0)),
        "text": doc.get("text", ""),
    }

def render_rag_sidebar():
    """RAG Agent サイドバーを表示"""
    st.sidebar.markdown("---")
    st.sidebar.title("🤖 RAG Agent")
    
    # RAG Agent 設定管理
    config_manager = RAGAgentConfig()
    current_config = config_manager.load_config()
    
    # RAG Agent 設定
    with st.sidebar.expander("⚙️ RAG 設定", expanded=True):
        # モデル選択
        model_options = [
            "GPT-4o",
            "Claude-3.5-Sonnet",
            "Llama-2-70B",
            "Mistral-7B",
            "ローカルモデル"
        ]
        
        # 現在のモデルのインデックスを取得
        current_model = current_config.get('llm_model', 'GPT-4o')
        model_index = model_options.index(current_model) if current_model in model_options else 0
        
        model_choice = st.selectbox(
            "LLMモデル",
            model_options,
            index=model_index,
            key="rag_model"
        )
        
        # 検索方式
        search_options = ["BM25", "ベクトル検索", "ハイブリッド"]
        current_search = current_config.get('search_method', 'ハイブリッド')
        search_index = search_options.index(current_search) if current_search in search_options else 2
        
        search_method = st.radio(
            "検索方式",
            search_options,
            index=search_index,
            horizontal=True,
            key="rag_search"
        )
        
        # 取得ドキュメント数
        top_k = st.slider(
            "取得するドキュメント数",
            min_value=1,
            max_value=20,
            value=current_config.get('top_k', 5),
            key="rag_top_k"
        )
        
        # 信頼度閾値
        confidence = st.slider(
            "信頼度閾値",
            min_value=0.0,
            max_value=1.0,
            value=current_config.get('confidence_threshold', 0.7),
            step=0.05,
            key="rag_confidence"
        )
        
        # 温度パラメータ
        temperature = st.slider(
            "温度(Temperature)",
            min_value=0.0,
            max_value=2.0,
            value=current_config.get('temperature', 0.7),
            step=0.1,
            help="値が低いほど確定的、高いほど創造的",
            key="rag_temperature"
        )
        
        # 設定保存
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💾 現在の設定を保存", use_container_width=True, key="save_rag_config"):
                # 設定を保存
                new_config = {
                    **current_config,
                    'llm_model': model_choice,
                    'search_method': search_method,
                    'top_k': top_k,
                    'confidence_threshold': confidence,
                    'temperature': temperature,
                }
                if config_manager.save_config(new_config):
                    st.success("✅ 設定を保存しました")
                    current_config = new_config
        
        with col2:
            if st.button("📋 現在の設定を表示", use_container_width=True, key="show_rag_summary"):
                st.info(config_manager.get_config_summary())
    
    # RAG 設定バックアップ・リストア
    with st.sidebar.expander("💾 RAG設定 バックアップ・リストア", expanded=False):
        st.subheader("設定管理")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 設定をバックアップ", use_container_width=True, key="backup_rag_config"):
                backup_file = config_manager.backup_config()
                if backup_file:
                    st.success(f"✅ バックアップ完了\n📄 {Path(backup_file).name}")
        
        with col2:
            if st.button("↩️ 設定をリストア", use_container_width=True, key="restore_rag_config"):
                if config_manager.restore_config():
                    st.success("✅ リストア完了\nページを再読み込みしてください")
        
        # 指定フォルダーへのエクスポート
        st.subheader("📤 指定フォルダーにバックアップ")
        
        st.info("💡 **パス指定方法:**\n- WSL/Linux: `/home/user/backups`\n- Windows (WSL経由): `D:/backups` → 自動変換 → `/mnt/d/backups`")
        
        export_path = st.text_input(
            "エクスポート先フォルダー",
            value=current_config.get('backup_location', '/home/abemc/project_root/backups'),
            placeholder="例: D:/backups または /home/abemc/backups",
            key="export_path"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📁 フォルダーを作成", use_container_width=True, key="create_export_folder"):
                try:
                    # Windows パスをWSLパスに変換
                    processed_path = export_path
                    if ":" in export_path:  # Windows パス判定
                        processed_path = convert_windows_path_to_wsl(export_path)
                        st.info(f"🔄 Windows パスを変換しました\n**元のパス:** {export_path}\n**変換後:** {processed_path}")
                    
                    export_dir = Path(processed_path)
                    export_dir.mkdir(parents=True, exist_ok=True)
                    st.success(f"✅ フォルダーを作成・確認しました\n📁 {processed_path}")
                except PermissionError:
                    st.error(f"❌ 権限エラー: {processed_path}\n\n**対応方法:**\n```bash\nsudo chmod 755 {processed_path}\n```")
                except Exception as e:
                    st.error(f"❌ フォルダー作成エラー: {str(e)}\n\n**確認事項:**\n- WSL ターミナルで実行済みか\n- 親フォルダーが存在するか\n- パスが正しいか")
        
        with col2:
            if st.button("💾 このフォルダーにエクスポート", use_container_width=True, key="export_to_folder"):
                try:
                    # Windows パスをWSLパスに変換
                    processed_path = export_path
                    if ":" in export_path:  # Windows パス判定
                        processed_path = convert_windows_path_to_wsl(export_path)
                    
                    # フォルダー存在確認
                    export_dir = Path(processed_path)
                    if not export_dir.exists():
                        st.warning("⚠️ フォルダーが存在しません。作成中...")
                        export_dir.mkdir(parents=True, exist_ok=True)
                    
                    # 書き込み権限確認
                    if not os.access(export_dir, os.W_OK):
                        raise PermissionError(f"書き込み権限がありません: {processed_path}")
                    
                    # エクスポート実行
                    export_file = config_manager.export_config(str(export_dir))
                    
                    if export_file:
                        # 設定を更新して保存
                        config = config_manager.load_config()
                        config['backup_location'] = export_path  # 元のパスを保存
                        config_manager.save_config(config)
                        
                        st.success(f"✅ エクスポート完了\n📄 {Path(export_file).name}\n📁 実際のパス: {processed_path}\n📏 ファイルサイズ: {Path(export_file).stat().st_size} bytes")
                        
                        # ファイル確認
                        with st.expander("📋 エクスポート情報詳細"):
                            st.json({
                                "ファイルパス": export_file,
                                "指定パス": export_path,
                                "実際のパス": processed_path,
                                "ファイルサイズ": Path(export_file).stat().st_size,
                                "作成時刻": datetime.now().isoformat()
                            })
                    else:
                        st.error("❌ エクスポート失敗\n\n**確認事項:**\n- 上記のパスが正しいか\n- ターミナルで存在確認: `ls -la /path/to/folder`\n- WSL ターミナルで実行中か")
                except PermissionError as e:
                    st.error(f"❌ 権限エラー: {str(e)}\n\n**対応方法:**\n1. WSL ターミナルで実行: `chmod 755 {processed_path}`\n2. または別のパスを指定\n3. 例: `/tmp/backups` (一時フォルダー)")
                except Exception as e:
                    st.error(f"❌ エラー: {str(e)}\n\n**デバッグ情報:**\n- 指定パス: {export_path}\n- 実際のパス: {processed_path if 'processed_path' in locals() else 'N/A'}\n- 存在確認: {Path(processed_path).exists() if 'processed_path' in locals() else 'N/A'}")
        
        # バックアップ一覧
        st.subheader("📋 バックアップ履歴")
        backups = config_manager.get_backups_list()
        
        if backups:
            for idx, backup in enumerate(backups, 1):
                with st.expander(f"{idx}. {backup['name']}", expanded=False):
                    st.caption(f"📅 {backup['modified']}")
                    st.caption(f"📊 {backup['size']} bytes")
                    if st.button("↩️ このバージョンをリストア", key=f"restore_backup_{idx}"):
                        if config_manager.restore_config(backup['path']):
                            st.success("✅ リストア完了")
        else:
            st.info("📭 バックアップがありません")
    
    # ドキュメント選択
    with st.sidebar.expander("📚 参照ドキュメント", expanded=False):
        manager = DocumentManager()
        
        # カテゴリフィルタ
        categories = sorted(list(set(doc['category'] for doc in manager.documents)))
        selected_categories = st.multiselect(
            "カテゴリを選択",
            categories,
            default=categories,
            key="rag_categories"
        )
        
        # 選択されたカテゴリのドキュメント
        filtered_docs = [
            doc for doc in manager.documents 
            if doc['category'] in selected_categories
        ]
        
        st.info(f"📊 {len(filtered_docs)} 個のドキュメントが参照可能です")
    
    # RAG 質問インターフェース
    st.sidebar.markdown("---")
    st.sidebar.subheader("💬 RAG 質問")
    
    question = st.sidebar.text_area(
        "質問を入力",
        placeholder="ドキュメントについて質問...",
        height=100,
        key="rag_question"
    )
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        query_button = st.button("🔍 質問を送信", use_container_width=True)
    
    with col2:
        clear_button = st.button("🗑️ リセット", use_container_width=True)
    
    # 実行結果
    if query_button and question:
        st.sidebar.info("⏳ RAG Agent が処理中...")
        # RAG処理の実装
        rag_response = perform_rag_query(
            question=question,
            model=model_choice,
            search_method=search_method,
            top_k=top_k,
            manager=manager,
            selected_categories=selected_categories
        )
        
        with st.sidebar.expander("✅ RAG 結果", expanded=True):
            st.markdown("**質問:**")
            st.write(question)
            
            st.markdown("**回答:**")
            st.write(rag_response['answer'])
            
            st.markdown("**参照ドキュメント:**")
            for idx, doc in enumerate(rag_response['sources'], 1):
                st.write(f"{idx}. {doc['name']} (信頼度: {doc['score']:.2%})")
    
    if clear_button:
        st.sidebar.success("✅ リセットしました")
    
    return {
        "model": model_choice,
        "search_method": search_method,
        "top_k": top_k,
        "confidence": confidence,
        "question": question
    }


def perform_rag_query(question, model, search_method, top_k, manager, selected_categories):
    """RAG クエリを実行"""
    doc_lookup = {doc['name']: doc for doc in manager.documents}
    retriever = get_retriever()
    corpus_results = _search_corpus(retriever, question, search_method, top_k)

    sources = []
    for result in corpus_results:
        enriched = _enrich_result(result, doc_lookup)
        if enriched['name'] in doc_lookup and enriched['category'] not in selected_categories:
            continue
        sources.append(enriched)

    if not sources:
        search_results = manager.search(question)
        filtered_results = [
            doc for doc in search_results
            if doc['category'] in selected_categories
        ]
        sources = [
            {
                "name": doc['name'],
                "category": doc['category'],
                "path": doc['path'],
                "score": 0.85,
                "text": "",
            }
            for doc in filtered_results[:top_k]
        ]
    
    # ダミー回答（実装時には実際のLLM統合が必要）
    answer = f"""
    ご質問「{question}」に対して、以下のドキュメントを参照して回答しました：
    
    質問内容を分析し、{len(sources)}個の関連ドキュメントから情報を抽出しました。
    
    【概要】
    質問の主要なポイント：
    - 主題の特定と検索
    - 関連ドキュメントの抽出
    - 情報の統合
    
    【参照ドキュメント】
    {len(sources)}個のドキュメントから最適な情報を統合しました。
    
    【推奨アクション】
    詳細は参照ドキュメントを確認してください。
    """
    
    return {
        "answer": answer,
        "sources": sources,
        "model": model,
        "search_method": search_method
    }


def convert_windows_path_to_wsl(windows_path: str) -> str:
    """Windows パスを WSL パスに変換
    例: D:\backups → /mnt/d/backups
    """
    # バックスラッシュをフォワードスラッシュに変換
    windows_path = windows_path.replace("\\", "/")
    
    # ドライブレターを抽出（例: D: → /mnt/d）
    if len(windows_path) >= 2 and windows_path[1] == ":":
        drive_letter = windows_path[0].lower()
        path_part = windows_path[2:].lstrip("/")
        wsl_path = f"/mnt/{drive_letter}/{path_part}"
        return wsl_path.rstrip("/")
    
    return windows_path


def render_backup_sidebar():
    """バックアップ・リストア サイドバーを表示"""
    st.sidebar.markdown("---")
    st.sidebar.title("💾 バックアップ・リストア")
    
    with st.sidebar.expander("🔧 ストレージ設定", expanded=False):
        # ドライブ選択
        drive_types = ["Linux/WSL パス", "Windows ドライブ（直接入力）", "Windows ドライブ（選択式）", "外部ストレージ"]
        drive_type = st.radio(
            "ドライブ種別",
            drive_types,
            index=0,
            key="backup_drive_type"
        )
        
        if drive_type == "Linux/WSL パス":
            backup_path = st.text_input(
                "WSL パス",
                value="/mnt/d/backups",
                help="WSL内のパス（例: /mnt/d/backups）",
                key="backup_wsl_path"
            )
        
        elif drive_type == "Windows ドライブ（直接入力）":
            windows_input = st.text_input(
                "Windows パス",
                value="D:\\backups",
                help="Windows形式のパスを入力（例: D:\\backups, E:\\docs\\backup）",
                key="backup_windows_direct"
            )
            
            # WSL パスに変換
            backup_path = convert_windows_path_to_wsl(windows_input)
            
            # 変換結果を表示
            st.info(f"📝 入力: `{windows_input}`")
            st.info(f"✅ WSL パス: `{backup_path}`")
        
        elif drive_type == "Windows ドライブ（選択式）":
            col1, col2 = st.columns(2)
            
            with col1:
                drive_options = ["C", "D", "E", "F", "G", "H"]
                drive_index = drive_options.index("D") if "D" in drive_options else 0
                drive_letter = st.selectbox(
                    "ドライブ選択",
                    drive_options,
                    index=drive_index,
                    key="backup_drive"
                )
            
            with col2:
                folder = st.text_input(
                    "フォルダパス",
                    value="backups",
                    help="例: backups, docs/backup, backup/2026-04",
                    key="backup_folder"
                )
            
            # WSL パスに変換
            backup_path = f"/mnt/{drive_letter.lower()}/{folder}"
            
            # Windows形式でも表示
            windows_format = f"{drive_letter}:\\{folder}".replace("/", "\\")
            st.info(f"📝 Windows: `{windows_format}`")
            st.info(f"✅ WSL パス: `{backup_path}`")
        
        else:
            backup_path = st.text_input(
                "外部ストレージ パス",
                value="/mnt/external/backups",
                key="backup_external_path"
            )
        
        # パス検証
        try:
            p = Path(backup_path)
            if p.exists():
                st.success(f"✅ パスが確認できました: `{backup_path}`")
                # ディレクトリ内のファイル/フォルダ数を表示
                try:
                    items = list(p.iterdir())
                    files = [x for x in items if x.is_file()]
                    dirs = [x for x in items if x.is_dir()]
                    st.caption(f"📊 ファイル数: {len(files)} | フォルダ数: {len(dirs)}")
                    
                    # 最近のバックアップを表示
                    if dirs:
                        latest_dir = sorted(dirs, key=lambda x: x.stat().st_mtime, reverse=True)[0]
                        st.caption(f"🕐 最新バックアップ: {latest_dir.name}")
                except Exception as e:
                    st.warning(f"⚠️ 内容確認エラー: {str(e)}")
            else:
                st.warning(f"⚠️ パスが存在しません: `{backup_path}`")
                if st.button("📁 フォルダを作成", key="create_backup_folder"):
                    try:
                        p.mkdir(parents=True, exist_ok=True)
                        st.success(f"✅ フォルダを作成しました: `{backup_path}`")
                    except PermissionError:
                        st.error(f"❌ アクセス権限がありません\n別のパスを指定してください")
                    except Exception as e:
                        st.error(f"❌ フォルダ作成エラー: {str(e)}")
        except Exception as e:
            st.error(f"❌ パス検証エラー: {str(e)}")
    
    # バックアップ操作
    st.sidebar.markdown("**📤 バックアップ操作**")
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("💾 バックアップ実行", use_container_width=True, key="backup_execute"):
            try:
                st.sidebar.info("⏳ バックアップ実行中...")
                # バックアップ処理
                backup_result = execute_backup(backup_path)
                if backup_result['success']:
                    st.sidebar.success(f"✅ バックアップが完了しました！\n📊 {backup_result['file_count']} ファイル | {backup_result['size']}")
                else:
                    st.sidebar.error(f"❌ バックアップエラー: {backup_result['error']}")
            except Exception as e:
                st.sidebar.error(f"❌ エラー: {str(e)}")
    
    with col2:
        if st.button("⬇️ リストア実行", use_container_width=True, key="backup_restore"):
            try:
                st.sidebar.info("⏳ リストア実行中...")
                # リストア処理
                restore_result = execute_restore(backup_path)
                if restore_result['success']:
                    st.sidebar.success(f"✅ リストアが完了しました！\n📊 {restore_result['file_count']} ファイル復元")
                else:
                    st.sidebar.error(f"❌ リストアエラー: {restore_result['error']}")
            except Exception as e:
                st.sidebar.error(f"❌ エラー: {str(e)}")
    
    # バックアップ先情報
    st.sidebar.markdown("**📁 現在のバックアップ先**")
    st.sidebar.code(backup_path, language="bash")
    
    # バックアップ履歴
    with st.sidebar.expander("📋 バックアップ履歴", expanded=False):
        try:
            backup_folder = Path(backup_path)
            if backup_folder.exists():
                items = list(backup_folder.iterdir())
                if items:
                    st.write("""
                    | ファイル | 更新日時 | サイズ |
                    |---------|---------|--------|
                    """)
                    for item in sorted(items, key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
                        size = item.stat().st_size
                        if size > 1024*1024:
                            size_str = f"{size/(1024*1024):.1f} MB"
                        elif size > 1024:
                            size_str = f"{size/1024:.1f} KB"
                        else:
                            size_str = f"{size} B"
                        
                        mtime = datetime.fromtimestamp(item.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                        st.write(f"| {item.name} | {mtime} | {size_str} |")
                else:
                    st.info("📭 バックアップファイルがありません")
            else:
                st.warning("⚠️ バックアップフォルダが見つかりません")
        except Exception as e:
            st.error(f"❌ エラー: {str(e)}")
    
    return backup_path


def execute_backup(backup_path: str) -> dict:
    """バックアップを実行
    
    Args:
        backup_path: バックアップ先パス
    
    Returns:
        成功状況とファイル情報
    """
    try:
        # 1. バックアップフォルダの作成確認
        backup_folder = Path(backup_path)
        
        # フォルダが存在しない場合は作成
        if not backup_folder.exists():
            try:
                backup_folder.mkdir(parents=True, exist_ok=True)
                print(f"✅ バックアップフォルダを作成しました: {backup_path}")
            except PermissionError:
                return {
                    "success": False,
                    "error": f"❌ アクセス権限がありません: {backup_path}\n別のフォルダを指定してください"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"❌ フォルダ作成エラー: {str(e)}"
                }
        
        # フォルダが書き込み可能か確認
        if not os.access(backup_folder, os.W_OK):
            return {
                "success": False,
                "error": f"❌ 書き込み権限がありません: {backup_path}"
            }
        
        # 2. ドキュメントフォルダの確認
        docs_source = Path("/home/abemc/project_root/docs")
        
        if not docs_source.exists():
            return {
                "success": False,
                "error": "❌ ドキュメントフォルダが見つかりません"
            }
        
        # 3. バックアップファイル名（サブフォルダー）の生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"docs_backup_{timestamp}"
        backup_dest = backup_folder / backup_name
        
        # サブフォルダーが既に存在する場合は削除
        if backup_dest.exists():
            shutil.rmtree(backup_dest)
            print(f"⚠️ 既存のバックアップを削除しました: {backup_dest}")
        
        # 4. フォルダコピーを実行
        try:
            shutil.copytree(docs_source, backup_dest, dirs_exist_ok=False)
            print(f"✅ コピー完了: {backup_dest}")
        except Exception as copy_error:
            return {
                "success": False,
                "error": f"❌ コピーエラー: {str(copy_error)}"
            }
        
        # 5. ファイル数とサイズを計算
        total_files = 0
        total_size = 0
        for root, dirs, files in os.walk(backup_dest):
            total_files += len(files)
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    total_size += os.path.getsize(file_path)
                except:
                    pass
        
        # サイズをフォーマット
        if total_size > 1024*1024:
            size_str = f"{total_size/(1024*1024):.1f} MB"
        elif total_size > 1024:
            size_str = f"{total_size/1024:.1f} KB"
        else:
            size_str = f"{total_size} B"
        
        print(f"✅ バックアップ完了: {total_files}ファイル, {size_str}")
        
        return {
            "success": True,
            "file_count": total_files,
            "size": size_str,
            "backup_path": str(backup_dest)
        }
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ 予期しないエラー: {str(e)}\n{error_details}")
        return {
            "success": False,
            "error": f"❌ 予期しないエラー: {str(e)}"
        }


def execute_restore(backup_path: str) -> dict:
    """リストアを実行
    
    Args:
        backup_path: バックアップ先パス
    
    Returns:
        成功状況とファイル情報
    """
    try:
        backup_folder = Path(backup_path)
        
        # 1. バックアップフォルダ確認
        if not backup_folder.exists():
            return {
                "success": False,
                "error": f"❌ バックアップフォルダが見つかりません: {backup_path}"
            }
        
        # 2. バックアップフォルダから最新のバックアップを探す
        # サブフォルダー（docs_backup_*）を探す
        backups = sorted(
            [f for f in backup_folder.iterdir() 
             if f.is_dir() and f.name.startswith('docs_backup_')],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        if not backups:
            return {
                "success": False,
                "error": f"❌ バックアップファイル（docs_backup_*）が見つかりません: {backup_path}"
            }
        
        # 最新のバックアップを使用
        latest_backup = backups[0]
        restore_dest = Path("/home/abemc/project_root/docs_restored")
        
        # 3. リストア先の準備
        if restore_dest.exists():
            shutil.rmtree(restore_dest)
            print(f"⚠️ 既存のリストア先を削除しました: {restore_dest}")
        
        # 4. バックアップをコピー
        try:
            shutil.copytree(latest_backup, restore_dest, dirs_exist_ok=False)
            print(f"✅ リストア完了: {restore_dest}")
        except Exception as copy_error:
            return {
                "success": False,
                "error": f"❌ リストアエラー: {str(copy_error)}"
            }
        
        # 5. ファイル数を計算
        total_files = 0
        for root, dirs, files in os.walk(restore_dest):
            total_files += len(files)
        
        print(f"✅ {total_files}ファイルをリストアしました")
        
        return {
            "success": True,
            "file_count": total_files,
            "restore_path": str(restore_dest),
            "backup_source": latest_backup.name
        }
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ 予期しないエラー: {str(e)}\n{error_details}")
        return {
            "success": False,
            "error": f"❌ 予期しないエラー: {str(e)}"
        }
