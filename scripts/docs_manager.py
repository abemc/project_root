#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ドキュメント管理・検索ツール
全プロジェクトドキュメントの一元管理と素早い検索を実現

使用方法:
    python docs_manager.py --search キーワード
    python docs_manager.py --list category
    python docs_manager.py --dashboard
    python docs_manager.py --index
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

class DocumentManager:
    """プロジェクトドキュメント管理クラス"""
    
    def __init__(self, docs_root: str = "/home/abemc/project_root/docs"):
        self.docs_root = Path(docs_root)
        self.documents = []
        self.metadata_file = Path(docs_root) / ".doc_metadata.json"
        self.scan_documents()
        
    def scan_documents(self):
        """全ドキュメントをスキャンしメタデータを収集"""
        self.documents = []
        
        for root, dirs, files in os.walk(self.docs_root):
            # アーカイブフォルダは後で処理
            if 'markdown_archive' in root:
                continue
                
            for file in files:
                if file.endswith(('.md', '.json')):
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(self.docs_root)
                    
                    doc_info = {
                        'name': file,
                        'path': str(rel_path),
                        'full_path': str(file_path),
                        'category': self._extract_category(str(rel_path)),
                        'size': file_path.stat().st_size,
                        'modified': datetime.fromtimestamp(
                            file_path.stat().st_mtime
                        ).strftime('%Y-%m-%d'),
                        'tags': self._extract_tags(file),
                        'phase': self._extract_phase(file),
                    }
                    
                    self.documents.append(doc_info)
    
    def _extract_category(self, path: str) -> str:
        """ファイルパスからカテゴリを抽出"""
        parts = path.split('/')
        if len(parts) > 1 and parts[0].startswith('0'):
            return parts[0]
        if 'guides' in parts:
            return 'guides'
        if 'reports' in parts:
            return 'reports'
        if 'implementation' in parts:
            return 'implementation'
        return 'root'
    
    def _extract_phase(self, filename: str) -> Optional[str]:
        """ファイル名からPhaseを抽出"""
        match = re.search(r'PHASE(\d+|Week\d+)', filename, re.IGNORECASE)
        if match:
            return match.group(1)
        return None
    
    def _extract_tags(self, filename: str) -> List[str]:
        """ファイル名から適切なタグを自動判定"""
        tags = []
        filename_lower = filename.lower()
        
        # タグマッピング
        tag_mapping = {
            'guide': ['guide', 'manual'],
            'report': ['report', 'summary'],
            'plan': ['plan', 'design'],
            'test': ['test', 'verify'],
            'deploy': ['deployment', 'release'],
            'api': ['api', 'integration'],
            'security': ['security', 'hardening'],
            'benchmark': ['benchmark', 'performance'],
            'rag': ['rag', 'retrieval'],
            'llm': ['llm', 'model'],
            'backup': ['backup', 'recovery'],
        }
        
        for key, keywords in tag_mapping.items():
            if any(kw in filename_lower for kw in keywords):
                tags.append(key)
        
        # セキュリティ関連の特別タグ
        if any(x in filename_lower for x in ['security', 'hardening', 'gap', 'ethics', 'adversarial']):
            tags.append('security')
        
        # 学習関連
        if any(x in filename_lower for x in ['learning', 'guide', 'blueprint']):
            tags.append('learning')
        
        return tags if tags else ['other']
    
    def search(self, keyword: str) -> List[Dict]:
        """キーワードでドキュメント検索"""
        keyword_lower = keyword.lower()
        results = []
        
        for doc in self.documents:
            # ファイル名、カテゴリ、タグで検索
            if (keyword_lower in doc['name'].lower() or
                keyword_lower in doc['category'].lower() or
                any(keyword_lower in tag for tag in doc['tags'])):
                results.append(doc)
        
        return sorted(results, key=lambda x: x['modified'], reverse=True)
    
    def get_by_category(self, category: str) -> List[Dict]:
        """カテゴリ別にドキュメント取得"""
        return [doc for doc in self.documents if doc['category'] == category]
    
    def get_by_phase(self, phase: str) -> List[Dict]:
        """フェーズ別にドキュメント取得"""
        return [doc for doc in self.documents if doc['phase'] == phase]
    
    def get_by_tag(self, tag: str) -> List[Dict]:
        """タグ別にドキュメント取得"""
        return [doc for doc in self.documents if tag in doc['tags']]
    
    def get_recent(self, days: int = 30) -> List[Dict]:
        """最近更新されたドキュメント取得"""
        cutoff = datetime.now().timestamp() - (days * 86400)
        recent = []
        
        for doc in self.documents:
            file_path = Path(doc['full_path'])
            if file_path.stat().st_mtime > cutoff:
                recent.append(doc)
        
        return sorted(recent, key=lambda x: x['modified'], reverse=True)
    
    def print_search_results(self, keyword: str):
        """検索結果を表示"""
        results = self.search(keyword)
        
        if not results:
            print(f"\n❌ '{keyword}' に該当するドキュメントは見つかりません。")
            print(f"\n💡 ヒント:")
            print("   - キーワードを別の言葉で試してみてください")
            print("   - [--list category] でカテゴリ一覧を表示")
            print("   - [--phase ##] でフェーズ別検索")
            return
        
        print(f"\n🔍 '{keyword}' の検索結果: {len(results)} 件\n")
        print(f"{'ファイル名':<50} {'カテゴリ':<15} {'更新日':<12} {'タグ'}")
        print("-" * 110)
        
        for doc in results[:20]:  # 最初の20件のみ表示
            tags = ', '.join(doc['tags'][:2])  # 最初の2つのタグのみ表示
            print(f"{doc['name']:<50} {doc['category']:<15} {doc['modified']:<12} {tags}")
        
        if len(results) > 20:
            print(f"\n... 他 {len(results) - 20} 件\n")
    
    def print_category_list(self):
        """カテゴリ別一覧を表示"""
        categories = defaultdict(list)
        
        for doc in self.documents:
            categories[doc['category']].append(doc)
        
        print("\n📂 ドキュメント カテゴリ別一覧\n")
        
        for category in sorted(categories.keys()):
            docs = categories[category]
            print(f"\n【{category}】 ({len(docs)} ファイル)")
            print("-" * 80)
            
            for doc in sorted(docs, key=lambda x: x['modified'], reverse=True)[:5]:
                tags = ', '.join(doc['tags'][:2])
                print(f"  • {doc['name']:<45} [{doc['modified']}] {tags}")
            
            if len(docs) > 5:
                print(f"  ... 他 {len(docs) - 5} ファイル")
    
    def print_dashboard(self):
        """ドキュメント管理ダッシュボード表示"""
        print("\n" + "=" * 80)
        print("📊 ドキュメント管理ダッシュボード")
        print("=" * 80 + "\n")
        
        # 統計情報
        categories = defaultdict(int)
        tags = defaultdict(int)
        phases = defaultdict(int)
        
        for doc in self.documents:
            categories[doc['category']] += 1
            for tag in doc['tags']:
                tags[tag] += 1
            if doc['phase']:
                phases[doc['phase']] += 1
        
        print("📈 統計情報")
        print("-" * 40)
        print(f"総ファイル数：          {len(self.documents)} ファイル")
        print(f"カテゴリ数：           {len(categories)} カテゴリ")
        print(f"タグ数：               {len(tags)} タイプ")
        print(f"フェーズ数：           {len(phases)} フェーズ")
        
        # トップカテゴリ
        print("\n🗂️ トップカテゴリ")
        print("-" * 40)
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {cat:<20} {count:>3} ファイル")
        
        # 最新更新ファイル
        print("\n⏰ 最近更新されたファイル（過去30日）")
        print("-" * 40)
        recent = self.get_recent(30)
        for doc in recent[:5]:
            print(f"  {doc['modified']} - {doc['name'][:50]}")
        
        # タグ別分布
        print("\n🏷️ タグ別分布")
        print("-" * 40)
        for tag, count in sorted(tags.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {tag:<15} {count:>3} ファイル")
        
        print("\n" + "=" * 80 + "\n")
    
    def update_metadata(self, doc_path: str, tags: List[str] = None, 
                       phase: str = None, category: str = None) -> bool:
        """ドキュメントのメタデータを更新"""
        for doc in self.documents:
            if doc['path'] == doc_path:
                if tags is not None:
                    doc['tags'] = tags
                if phase is not None:
                    doc['phase'] = phase
                if category is not None:
                    doc['category'] = category
                return True
        return False
    
    def check_document_quality(self) -> List[Dict]:
        """ドキュメント品質をチェック"""
        quality_issues = []
        
        for doc in self.documents:
            issues = {
                'path': doc['path'],
                'name': doc['name'],
                'issues': [],
                'level': 'OK'
            }
            
            try:
                file_path = Path(doc['full_path'])
                
                # 1. ファイルサイズチェック
                if file_path.stat().st_size < 100:
                    issues['issues'].append('⚠️ ドキュメントが非常に短い（<100 bytes）')
                
                # 2. 最終更新日チェック
                mtime = file_path.stat().st_mtime
                days_ago = (datetime.now().timestamp() - mtime) / 86400
                if days_ago > 90:
                    issues['issues'].append(f'⚠️ 90日以上更新されていない（{int(days_ago)}日前）')
                elif days_ago > 30:
                    issues['issues'].append(f'ℹ️ 30日以上更新されていない（{int(days_ago)}日前）')
                
                # 3. コンテンツ解析（マークダウンファイルのみ）
                if file_path.suffix == '.md':
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # TODO/FIXME検出
                    todos = len(re.findall(r'TODO|FIXME|XXX|HACK', content))
                    if todos > 0:
                        issues['issues'].append(f'⚠️ TODO/FIXMEが{todos}個ある')
                    
                    # リンク切れ検出
                    broken_links = []
                    # ファイルリンク
                    for link in re.findall(r'\]\(([^)]+)\)', content):
                        if link.startswith('http'):
                            continue
                        linked_file = file_path.parent / link.split('#')[0]
                        if not linked_file.exists() and '..' not in link:
                            broken_links.append(link)
                    
                    if broken_links:
                        issues['issues'].append(f'🔗 {len(broken_links)}個のリンク切れ: {", ".join(broken_links[:3])}...')
                    
                    # 見出しチェック
                    if not re.search(r'^#\s+', content, re.MULTILINE):
                        issues['issues'].append('📏 H1見出しがない')
                
            except Exception as e:
                issues['issues'].append(f'❌ エラー: {str(e)}')
            
            # レベルを判定
            if any('🔗' in i or '❌' in i for i in issues['issues']):
                issues['level'] = 'ERROR'
            elif any('⚠️' in i for i in issues['issues']):
                issues['level'] = 'WARNING'
            
            if issues['issues']:
                quality_issues.append(issues)
        
        return quality_issues
    
    def extract_references(self) -> Dict[str, List[str]]:
        """ドキュメント間の相互参照を抽出"""
        references = {}
        
        for doc in self.documents:
            if doc['full_path'].endswith('.md'):
                references[doc['path']] = []
                
                try:
                    with open(doc['full_path'], 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # マークダウンリンクを抽出
                    for link in re.findall(r'\]\(([^)]+)\)', content):
                        # URLは除外
                        if link.startswith('http'):
                            continue
                        
                        # アンカーを除外
                        link_path = link.split('#')[0]
                        
                        # 相対パスを解決
                        full_link_path = (Path(doc['full_path']).parent / link_path).resolve()
                        
                        # ドキュメント内のファイルを検索
                        for other_doc in self.documents:
                            if Path(other_doc['full_path']).resolve() == full_link_path:
                                if other_doc['path'] not in references[doc['path']]:
                                    references[doc['path']].append(other_doc['path'])
                
                except Exception:
                    pass
        
        return references
    
    def build_reference_graph(self) -> Dict:
        """相互参照グラフを構築"""
        refs = self.extract_references()
        
        # 逆参照（被参照）を計算
        reverse_refs = defaultdict(list)
        for doc_path, referenced_docs in refs.items():
            for ref_doc in referenced_docs:
                if ref_doc not in reverse_refs:
                    reverse_refs[ref_doc] = []
                reverse_refs[ref_doc].append(doc_path)
        
        return {
            'references': refs,      # 参照先
            'reverse_references': dict(reverse_refs),  # 参照元
        }
    
    def export_index_json(self, output_file: str = None):
        """ドキュメント索引をJSON形式でエクスポート"""
        if output_file is None:
            output_file = str(self.docs_root / "documents_index.json")
        
        # カテゴリ別に整理
        by_category = defaultdict(list)
        for doc in self.documents:
            by_category[doc['category']].append({
                'name': doc['name'],
                'path': doc['path'],
                'modified': doc['modified'],
                'tags': doc['tags'],
                'phase': doc['phase'],
            })
        
        # JSON生成
        index_data = {
            'generated': datetime.now().isoformat(),
            'total_documents': len(self.documents),
            'categories': dict(by_category),
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ JSON索引をエクスポート: {output_file}")
        return output_file
    
    def generate_html_index(self, output_file: str = None):
        """HTML形式の検索可能なインデックスを生成"""
        if output_file is None:
            output_file = str(self.docs_root / "documents_index.html")
        
        # カテゴリ別に整理
        categories = defaultdict(list)
        for doc in self.documents:
            categories[doc['category']].append(doc)
        
        # HTML生成
        html = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ドキュメント管理システム</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 20px; background: #f5f5f5; }
        h1 { color: #333; border-bottom: 3px solid #0066cc; padding-bottom: 10px; }
        .search-box { margin: 20px 0; }
        input[type="text"] { width: 100%; max-width: 500px; padding: 10px; font-size: 16px; }
        .category { background: white; margin: 20px 0; padding: 15px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .category h2 { color: #0066cc; margin-top: 0; }
        .doc-item { margin: 10px 0; padding: 10px; background: #f9f9f9; border-left: 3px solid #0066cc; }
        .doc-name { font-weight: bold; }
        .doc-meta { font-size: 0.9em; color: #666; margin-top: 5px; }
        .tag { display: inline-block; background: #e8f0ff; color: #0066cc; padding: 2px 8px; border-radius: 3px; margin-right: 5px; font-size: 0.85em; }
    </style>
    <script>
        function filterDocuments() {
            const input = document.getElementById('searchInput').value.toLowerCase();
            const items = document.querySelectorAll('.doc-item');
            
            items.forEach(item => {
                const text = item.textContent.toLowerCase();
                item.style.display = text.includes(input) ? '' : 'none';
            });
        }
    </script>
</head>
<body>
    <h1>📚 ドキュメント管理システム</h1>
    
    <div class="search-box">
        <input type="text" id="searchInput" placeholder="キーワードで検索..." onkeyup="filterDocuments()">
        <p style="color: #666; font-size: 0.9em;">💡 ファイル名やタグで検索できます</p>
    </div>
    
    <div id="content">
"""
        
        for category in sorted(categories.keys()):
            docs = sorted(categories[category], key=lambda x: x['modified'], reverse=True)
            html += f'        <div class="category">\n'
            html += f'            <h2>{category} ({len(docs)} ファイル)</h2>\n'
            
            for doc in docs:
                tags_html = ''.join([f'<span class="tag">{tag}</span>' for tag in doc['tags'][:3]])
                html += f'''            <div class="doc-item">
                <div class="doc-name">{doc['name']}</div>
                <div class="doc-meta">
                    📅 {doc['modified']} | 📁 {doc['path']} | {tags_html}
                </div>
            </div>
'''
            
            html += '        </div>\n'
        
        html += """    </div>
</body>
</html>"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"\n✅ HTML索引を生成: {output_file}")
        return output_file


def main():
    """メイン処理"""
    import sys
    
    manager = DocumentManager()
    
    if len(sys.argv) < 2:
        # ヘルプ表示
        print("""
📚 ドキュメント管理・検索ツール

使用方法:
    python docs_manager.py --search キーワード    # キーワード検索
    python docs_manager.py --dashboard            # ダッシュボード表示
    python docs_manager.py --list                 # カテゴリ別一覧
    python docs_manager.py --export-json          # JSON索引をエクスポート
    python docs_manager.py --export-html          # HTML索引を生成
    python docs_manager.py --phase NN             # フェーズ別表示
    python docs_manager.py --tag タグ名            # タグ別表示

例:
    python docs_manager.py --search "デプロイ"
    python docs_manager.py --dashboard
    python docs_manager.py --phase 15
    python docs_manager.py --tag "security"
""")
        return
    
    command = sys.argv[1]
    
    if command == '--search' and len(sys.argv) > 2:
        keyword = ' '.join(sys.argv[2:])
        manager.print_search_results(keyword)
    
    elif command == '--dashboard':
        manager.print_dashboard()
    
    elif command == '--list':
        manager.print_category_list()
    
    elif command == '--export-json':
        manager.export_index_json()
    
    elif command == '--export-html':
        manager.generate_html_index()
    
    elif command == '--phase' and len(sys.argv) > 2:
        phase = sys.argv[2]
        results = manager.get_by_phase(phase)
        print(f"\n📋 Phase {phase} の関連ドキュメント: {len(results)} 件\n")
        for doc in sorted(results, key=lambda x: x['modified'], reverse=True):
            print(f"  • {doc['name']:<50} [{doc['modified']}]")
    
    elif command == '--tag' and len(sys.argv) > 2:
        tag = sys.argv[2]
        results = manager.get_by_tag(tag)
        print(f"\n🏷️ '{tag}' タグのドキュメント: {len(results)} 件\n")
        for doc in sorted(results, key=lambda x: x['modified'], reverse=True):
            print(f"  • {doc['name']:<50} [{doc['modified']}]")
    
    else:
        print(f"❌ 不明なコマンド: {command}")


if __name__ == '__main__':
    main()
