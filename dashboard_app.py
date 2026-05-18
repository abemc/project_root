#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ドキュメント管理ダッシュボード Webアプリケーション
Streamlitを使用したインタラクティブUIダッシュボード
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import sys

# docs_managerをインポート
sys.path.insert(0, '/home/abemc/project_root')
from docs_manager import DocumentManager
from rag_agent_sidebar import render_backup_sidebar

# ページ設定
st.set_page_config(
    page_title="📚 ドキュメント管理ダッシュボード",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS スタイル
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .metric-value {
        font-size: 2.5em;
        font-weight: bold;
        margin: 10px 0;
    }
    .metric-label {
        font-size: 0.9em;
        opacity: 0.9;
    }
    .doc-item {
        background: #f0f2f6;
        padding: 12px;
        border-radius: 8px;
        margin: 8px 0;
        border-left: 4px solid #667eea;
    }
    .doc-name {
        font-weight: bold;
        font-size: 1.1em;
        color: #333;
    }
    .doc-meta {
        font-size: 0.85em;
        color: #666;
        margin-top: 5px;
    }
    .tag {
        display: inline-block;
        background: #e8f0ff;
        color: #667eea;
        padding: 3px 10px;
        border-radius: 12px;
        margin-right: 5px;
        font-size: 0.8em;
    }
    .category-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 10px 15px;
        border-radius: 8px;
        margin-top: 20px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# キャッシング
@st.cache_resource
def load_document_manager():
    """ドキュメント管理システムの読み込み"""
    return DocumentManager()

# メイン
def main():
    # タイトル
    st.title("📚 ドキュメント管理ダッシュボード")
    st.markdown("プロジェクト全体のドキュメントを一元管理・検索できるシステムです")
    
    # ドキュメント管理システムの読み込み
    manager = load_document_manager()
    
    # ============================================
    # サイドバー - ドキュメント管理パネル
    # ============================================
    st.sidebar.title("📚 ドキュメント管理")
    
    with st.sidebar.expander("📊 表示オプション", expanded=True):
        view_mode = st.sidebar.radio(
            "表示モード",
            ["📊 ダッシュボード", "🔍 検索", "📂 カテゴリ", "🏷️ タグ", "📋 フェーズ", "📅 最新更新", "📄 ドキュメント表示"],
            key="view_mode"
        )
    
    # バックアップ・リストア サイドバー
    backup_path = render_backup_sidebar()
    
    # ============================================
    # ダッシュボード表示
    # ============================================
    if view_mode == "📊 ダッシュボード":
        show_dashboard(manager)
    
    # ============================================
    # 検索モード
    # ============================================
    elif view_mode == "🔍 検索":
        show_search(manager)
    
    # ============================================
    # カテゴリモード
    # ============================================
    elif view_mode == "📂 カテゴリ":
        show_categories(manager)
    
    # ============================================
    # タグモード
    # ============================================
    elif view_mode == "🏷️ タグ":
        show_tags(manager)
    
    # ============================================
    # フェーズモード
    # ============================================
    elif view_mode == "📋 フェーズ":
        show_phases(manager)
    
    # ============================================
    # 最新更新モード
    # ============================================
    elif view_mode == "📅 最新更新":
        show_recent(manager)
    
    # ============================================
    # ドキュメント表示モード
    # ============================================
    elif view_mode == "📄 ドキュメント表示":
        show_document_viewer(manager)


def show_dashboard(manager):
    """ダッシュボード表示"""
    st.header("📊 統計ダッシュボード")
    
    # 統計情報の計算
    categories = defaultdict(int)
    tags = defaultdict(int)
    phases = defaultdict(int)
    
    for doc in manager.documents:
        categories[doc['category']] += 1
        for tag in doc['tags']:
            tags[tag] += 1
        if doc['phase']:
            phases[doc['phase']] += 1
    
    # メトリクスカード
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📄 総ファイル数", f"{len(manager.documents)}")
    
    with col2:
        st.metric("📁 カテゴリ数", f"{len(categories)}")
    
    with col3:
        st.metric("🏷️ タグ数", f"{len(tags)}")
    
    with col4:
        st.metric("📋 フェーズ数", f"{len(phases)}")
    
    st.divider()
    
    # グラフ表示
    col1, col2 = st.columns(2)
    
    # トップカテゴリ
    with col1:
        st.subheader("🗂️ トップカテゴリ")
        top_categories = dict(sorted(categories.items(), key=lambda x: x[1], reverse=True)[:8])
        df_cat = pd.DataFrame({
            'カテゴリ': list(top_categories.keys()),
            'ファイル数': list(top_categories.values())
        })
        st.bar_chart(df_cat.set_index('カテゴリ'), use_container_width=True)
    
    # タグ分布
    with col2:
        st.subheader("🏷️ タグ分布 (TOP 8)")
        top_tags = dict(sorted(tags.items(), key=lambda x: x[1], reverse=True)[:8])
        df_tags = pd.DataFrame({
            'タグ': list(top_tags.keys()),
            '数': list(top_tags.values())
        })
        st.bar_chart(df_tags.set_index('タグ'), use_container_width=True)
    
    st.divider()
    
    # 最近更新されたファイル
    st.subheader("⏰ 最近更新されたファイル（過去30日）")
    recent = manager.get_recent(30)
    
    if recent:
        df_recent = pd.DataFrame([
            {
                '📅 更新日': doc['modified'],
                'ファイル名': doc['name'][:50],
                '📁 カテゴリ': doc['category'],
                '🏷️ タグ': ', '.join(doc['tags'][:2])
            }
            for doc in recent[:15]
        ])
        st.dataframe(df_recent, use_container_width=True, hide_index=True)
    else:
        st.info("最近30日間に更新されたファイルはありません。")
    
    # フッター
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📥 JSON索引をエクスポート"):
            manager.export_index_json()
            st.success("✅ JSON索引をエクスポートしました！")
    
    with col2:
        if st.button("📄 HTML索引を生成"):
            manager.generate_html_index()
            st.success("✅ HTML索引を生成しました！")
    
    with col3:
        st.info(f"最終更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def show_search(manager):
    """検索表示"""
    st.header("🔍 ドキュメント検索")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        keyword = st.text_input(
            "キーワードで検索",
            placeholder="例: デプロイ、セキュリティ、ベンチマーク...",
            label_visibility="collapsed"
        )
    
    with col2:
        search_button = st.button("🔍 検索", use_container_width=True)
    
    if keyword or search_button:
        if keyword:
            results = manager.search(keyword)
            
            st.markdown(f"### 検索結果: {len(results)} 件")
            
            if results:
                # フィルタオプション
                col1, col2 = st.columns(2)
                
                with col1:
                    filter_category = st.selectbox(
                        "カテゴリでフィルタ",
                        ["すべて"] + sorted(list(set(doc['category'] for doc in results))),
                        key="search_category"
                    )
                
                with col2:
                    filter_tag = st.selectbox(
                        "タグでフィルタ",
                        ["すべて"] + sorted(list(set(tag for doc in results for tag in doc['tags']))),
                        key="search_tag"
                    )
                
                # フィルタリング
                filtered = results
                if filter_category != "すべて":
                    filtered = [doc for doc in filtered if doc['category'] == filter_category]
                if filter_tag != "すべて":
                    filtered = [doc for doc in filtered if filter_tag in doc['tags']]
                
                st.markdown(f"**フィルタ後: {len(filtered)} 件**")
                st.divider()
                
                # 結果表示
                for idx, doc in enumerate(filtered[:50], 1):
                    with st.container():
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.markdown(f"**{idx}. {doc['name']}**")
                            st.markdown(
                                f"📁 `{doc['category']}` | 📅 {doc['modified']} | "
                                f"{''.join([f'`{tag}`' for tag in doc['tags'][:3]])}"
                            )
                        
                        with col2:
                            st.caption(f"📄 {doc['size']} bytes")
                        
                        st.markdown("---")
                
                if len(filtered) > 50:
                    st.info(f"💡 最初の50件を表示しています。全{len(filtered)}件があります。")
            else:
                st.warning("❌ 検索条件に合致するドキュメントが見つかりません。")
        else:
            st.info("💡 キーワードを入力して検索してください。")


def show_categories(manager):
    """カテゴリ別表示"""
    st.header("📂 カテゴリ別ドキュメント")
    
    categories = defaultdict(list)
    for doc in manager.documents:
        categories[doc['category']].append(doc)
    
    # カテゴリ選択
    selected_category = st.selectbox(
        "カテゴリを選択",
        sorted(categories.keys())
    )
    
    if selected_category:
        docs = sorted(categories[selected_category], key=lambda x: x['modified'], reverse=True)
        
        st.markdown(f"### {selected_category} ({len(docs)} ファイル)")
        st.divider()
        
        # タブを使用した表示方法の切り替え
        tab1, tab2 = st.tabs(["📋 一覧", "📊 統計"])
        
        with tab1:
            for idx, doc in enumerate(docs, 1):
                with st.container():
                    st.markdown(f"**{idx}. {doc['name']}**")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.caption(f"📅 更新: {doc['modified']}")
                    
                    with col2:
                        st.caption(f"📄 サイズ: {doc['size']} bytes")
                    
                    with col3:
                        tags_str = ' '.join([f"`{tag}`" for tag in doc['tags'][:3]])
                        st.caption(f"🏷️ {tags_str}")
                    
                    st.markdown("---")
        
        with tab2:
            # 統計
            col1, col2, col3 = st.columns(3)
            
            with col1:
                total_size = sum(doc['size'] for doc in docs)
                st.metric("📄 合計サイズ", f"{total_size:,} bytes")
            
            with col2:
                avg_size = total_size / len(docs) if docs else 0
                st.metric("📊 平均サイズ", f"{avg_size:,.0f} bytes")
            
            with col3:
                st.metric("📁 ファイル数", len(docs))
            
            st.divider()
            
            # タグ分布
            tag_count = defaultdict(int)
            for doc in docs:
                for tag in doc['tags']:
                    tag_count[tag] += 1
            
            st.subheader("🏷️ このカテゴリのタグ分布")
            df_tags = pd.DataFrame({
                'タグ': list(tag_count.keys()),
                '数': list(tag_count.values())
            }).sort_values('数', ascending=False)
            
            st.bar_chart(df_tags.set_index('タグ'), use_container_width=True)


def show_tags(manager):
    """タグ別表示"""
    st.header("🏷️ タグ別ドキュメント")
    
    # タグ一覧を取得
    all_tags = defaultdict(list)
    for doc in manager.documents:
        for tag in doc['tags']:
            all_tags[tag].append(doc)
    
    # タグ選択
    selected_tag = st.selectbox(
        "タグを選択",
        sorted(all_tags.keys())
    )
    
    if selected_tag:
        docs = sorted(all_tags[selected_tag], key=lambda x: x['modified'], reverse=True)
        
        st.markdown(f"### 🏷️ '{selected_tag}' タグ ({len(docs)} ファイル)")
        st.divider()
        
        # フィルタ
        col1, col2 = st.columns(2)
        
        with col1:
            filter_category = st.selectbox(
                "カテゴリでフィルタ",
                ["すべて"] + sorted(list(set(doc['category'] for doc in docs))),
                key="tag_category"
            )
        
        with col2:
            sort_by = st.selectbox(
                "ソート",
                ["📅 最新順", "📁 カテゴリ順", "📄 名前順"]
            )
        
        # フィルタリング
        filtered = docs
        if filter_category != "すべて":
            filtered = [doc for doc in filtered if doc['category'] == filter_category]
        
        # ソート
        if sort_by == "📅 最新順":
            filtered = sorted(filtered, key=lambda x: x['modified'], reverse=True)
        elif sort_by == "📁 カテゴリ順":
            filtered = sorted(filtered, key=lambda x: x['category'])
        elif sort_by == "📄 名前順":
            filtered = sorted(filtered, key=lambda x: x['name'])
        
        st.markdown(f"**表示件数: {len(filtered)} / {len(docs)}**")
        st.divider()
        
        # ドキュメント表示
        for idx, doc in enumerate(filtered, 1):
            with st.container():
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**{idx}. {doc['name']}**")
                    st.caption(
                        f"📁 {doc['category']} | "
                        f"📅 {doc['modified']} | "
                        f"📄 {doc['size']:,} bytes"
                    )
                
                with col2:
                    phase_text = f"Phase {doc['phase']}" if doc['phase'] else "N/A"
                    st.caption(f"📋 {phase_text}")
                
                st.markdown("---")


def show_phases(manager):
    """フェーズ別表示"""
    st.header("📋 フェーズ別ドキュメント")
    
    phases = defaultdict(list)
    for doc in manager.documents:
        if doc['phase']:
            phases[doc['phase']].append(doc)
    
    if not phases:
        st.info("フェーズ情報を持つドキュメントがありません。")
        return
    
    # フェーズ選択
    selected_phase = st.selectbox(
        "フェーズを選択",
        sorted(phases.keys(), key=lambda x: int(x) if x.isdigit() else 0, reverse=True)
    )
    
    if selected_phase:
        docs = sorted(phases[selected_phase], key=lambda x: x['modified'], reverse=True)
        
        st.markdown(f"### Phase {selected_phase} ({len(docs)} ファイル)")
        st.divider()
        
        # 統計
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("📄 ファイル数", len(docs))
        
        with col2:
            categories_in_phase = set(doc['category'] for doc in docs)
            st.metric("📁 カテゴリ数", len(categories_in_phase))
        
        with col3:
            total_size = sum(doc['size'] for doc in docs)
            st.metric("📊 合計サイズ", f"{total_size:,} B")
        
        st.divider()
        
        # ドキュメント一覧
        for idx, doc in enumerate(docs, 1):
            with st.container():
                st.markdown(f"**{idx}. {doc['name']}**")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.caption(f"📁 カテゴリ: {doc['category']}")
                    st.caption(f"📅 更新: {doc['modified']}")
                
                with col2:
                    tags_str = ' '.join([f"`{tag}`" for tag in doc['tags'][:3]])
                    st.caption(f"🏷️ {tags_str}")
                
                st.markdown("---")


def show_recent(manager):
    """最近更新されたファイル表示"""
    st.header("📅 最近更新されたファイル")
    
    # 期間選択
    col1, col2 = st.columns(2)
    
    with col1:
        days = st.slider("期間を選択", 1, 90, 30)
    
    with col2:
        limit = st.slider("表示件数", 5, 100, 30)
    
    recent = manager.get_recent(days)
    
    st.markdown(f"### 過去 {days} 日間に更新されたファイル: {len(recent)} 件")
    st.divider()
    
    if recent:
        # テーブル表示
        df_recent = pd.DataFrame([
            {
                '📅 更新日': doc['modified'],
                'ファイル名': doc['name'][:60],
                '📁 カテゴリ': doc['category'],
                '📄 サイズ': f"{doc['size']:,}",
                '🏷️ タグ': ', '.join(doc['tags'][:2])
            }
            for doc in recent[:limit]
        ])
        
        st.dataframe(df_recent, use_container_width=True, hide_index=True)
        
        # 日付別グループ化
        st.subheader("📊 日別更新数")
        date_count = defaultdict(int)
        for doc in recent:
            date_count[doc['modified']] += 1
        
        df_dates = pd.DataFrame({
            '日付': list(date_count.keys()),
            '更新数': list(date_count.values())
        }).sort_values('日付', ascending=False)
        
        st.bar_chart(df_dates.set_index('日付'), use_container_width=True)
    else:
        st.info(f"過去 {days} 日間に更新されたファイルはありません。")


def show_document_viewer(manager):
    """ドキュメント表示モード"""
    st.header("📄 ドキュメント表示")
    
    # ドキュメント選択方法
    col1, col2 = st.columns(2)
    
    with col1:
        selection_method = st.radio(
            "ドキュメント選択方法",
            ["検索で選択", "カテゴリから選択", "フェーズから選択"],
            horizontal=True
        )
    
    selected_doc = None
    
    # 検索で選択
    if selection_method == "検索で選択":
        st.subheader("🔍 キーワード検索")
        keyword = st.text_input("キーワード", placeholder="例: デプロイ、ドキュメント...")
        
        if keyword:
            results = manager.search(keyword)
            if results:
                doc_names = [f"{doc['name']} ({doc['category']})" for doc in results]
                selected_idx = st.selectbox("検索結果から選択", range(len(results)), 
                                          format_func=lambda i: doc_names[i])
                selected_doc = results[selected_idx]
            else:
                st.warning(f"❌ '{keyword}' に該当するドキュメントが見つかりません。")
    
    # カテゴリから選択
    elif selection_method == "カテゴリから選択":
        st.subheader("📂 カテゴリから選択")
        
        categories = defaultdict(list)
        for doc in manager.documents:
            categories[doc['category']].append(doc)
        
        selected_category = st.selectbox("カテゴリ", sorted(categories.keys()))
        
        if selected_category:
            docs = sorted(categories[selected_category], key=lambda x: x['modified'], reverse=True)
            doc_names = [f"{doc['name']} ({doc['modified']})" for doc in docs]
            selected_idx = st.selectbox("ドキュメント", range(len(docs)), 
                                      format_func=lambda i: doc_names[i])
            selected_doc = docs[selected_idx]
    
    # フェーズから選択
    elif selection_method == "フェーズから選択":
        st.subheader("📋 フェーズから選択")
        
        phases = defaultdict(list)
        for doc in manager.documents:
            if doc['phase']:
                phases[doc['phase']].append(doc)
        
        if phases:
            selected_phase = st.selectbox(
                "フェーズ",
                sorted(phases.keys(), key=lambda x: int(x) if x.isdigit() else 0, reverse=True)
            )
            
            if selected_phase:
                docs = sorted(phases[selected_phase], key=lambda x: x['modified'], reverse=True)
                doc_names = [f"{doc['name']} ({doc['modified']})" for doc in docs]
                selected_idx = st.selectbox("ドキュメント", range(len(docs)), 
                                          format_func=lambda i: doc_names[i])
                selected_doc = docs[selected_idx]
        else:
            st.info("フェーズ情報を持つドキュメントがありません。")
    
    # ドキュメント表示
    if selected_doc:
        st.divider()
        display_document(selected_doc)


def display_document(doc):
    """ドキュメントの詳細表示"""
    file_path = Path(doc['full_path'])
    
    # ドキュメント情報
    st.markdown(f"### 📄 {doc['name']}")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📁 カテゴリ", doc['category'])
    
    with col2:
        st.metric("📅 更新日", doc['modified'])
    
    with col3:
        st.metric("📊 サイズ", f"{doc['size']:,} B")
    
    with col4:
        phase_text = f"Phase {doc['phase']}" if doc['phase'] else "N/A"
        st.metric("📋 フェーズ", phase_text)
    
    # タグ表示
    st.markdown("**🏷️ タグ:**")
    for tag in doc['tags']:
        st.write(f"- `{tag}`")
    
    st.divider()
    
    # ドキュメント内容表示
    st.markdown("### 📖 ドキュメント内容")
    
    try:
        if doc['name'].endswith('.md'):
            # マークダウンファイル
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            st.markdown(content)
        
        elif doc['name'].endswith('.json'):
            # JSONファイル
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            st.json(json_data)
        
        else:
            # テキストファイル
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if len(content) > 50000:
                st.warning("⚠️ ファイルサイズが大きいため、最初の50,000文字のみ表示します。")
                content = content[:50000]
            
            st.code(content, language='text')
    
    except Exception as e:
        st.error(f"❌ ファイルの読み込みに失敗しました: {str(e)}")
    
    # ダウンロードボタン
    st.divider()
    
    with open(file_path, 'rb') as f:
        file_content = f.read()
    
    st.download_button(
        label="📥 ファイルをダウンロード",
        data=file_content,
        file_name=doc['name'],
        mime="text/plain"
    )


if __name__ == "__main__":
    main()
