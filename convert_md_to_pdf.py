#!/usr/bin/env python3
"""
Markdown ファイルを PDF に変換するスクリプト
LLM 学習資料用
"""

import os
import sys
import re
from pathlib import Path
from weasyprint import HTML, CSS
from io import StringIO

# markdown パッケージのシンプルな実装
def simple_markdown_to_html(text):
    """シンプルな Markdown → HTML 変換"""
    # 基本的な処理のみ
    html = text
    
    # # 見出し
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    
    # ** 太字
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'__(.+?)__', r'<strong>\1</strong>', html)
    
    # * イタリック
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    html = re.sub(r'_(.+?)_', r'<em>\1</em>', html)
    
    # ` コード
    html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)
    
    # ``` コードブロック
    html = re.sub(r'```(.+?)```', r'<pre><code>\1</code></pre>', html, flags=re.DOTALL)
    
    # > 引用
    html = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)
    
    # リンク
    html = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', html)
    
    # 改行
    html = html.replace('\n\n', '</p><p>')
    html = '<p>' + html + '</p>'
    
    return html

# 変換対象ファイル
LEARNING_MATERIALS_DIR = Path(__file__).parent / "docs" / "07_学習資料"

FILES_TO_CONVERT = [
    "01_LLM_basics_beginners_guide.md",
    "02_project_overview_diagram.md",
    "03_setup_and_hands_on.md",
    "04_inference_pipeline_analysis.md",
    "05_advanced_implementation_guide.md",
    "README_学習ガイド.md"
]

# CSS スタイル
PDF_CSS = """
    @page {
        size: A4;
        margin: 1cm;
    }
    body {
        font-family: 'Noto Sans JP', Arial, sans-serif;
        line-height: 1.6;
        color: #333;
        font-size: 10pt;
    }
    h1 {
        font-size: 24pt;
        color: #667eea;
        border-bottom: 3px solid #667eea;
        padding-bottom: 10px;
        margin-top: 20px;
        margin-bottom: 15px;
        page-break-after: avoid;
    }
    h2 {
        font-size: 18pt;
        color: #764ba2;
        margin-top: 15px;
        margin-bottom: 10px;
        page-break-after: avoid;
    }
    h3 {
        font-size: 14pt;
        color: #667eea;
        margin-top: 12px;
        margin-bottom: 8px;
    }
    h4, h5, h6 {
        font-size: 11pt;
        color: #555;
        margin-top: 10px;
        margin-bottom: 5px;
    }
    p {
        margin: 8px 0;
        text-align: justify;
    }
    ul, ol {
        margin: 10px 0;
        padding-left: 30px;
    }
    li {
        margin: 5px 0;
    }
    code {
        background-color: #f5f5f5;
        padding: 2px 6px;
        border-radius: 3px;
        font-family: 'Courier New', monospace;
        font-size: 9pt;
    }
    pre {
        background-color: #f8f9fa;
        border-left: 4px solid #667eea;
        padding: 12px;
        overflow-x: auto;
        margin: 10px 0;
        font-family: 'Courier New', monospace;
        font-size: 8.5pt;
        page-break-inside: avoid;
    }
    pre code {
        background-color: transparent;
        padding: 0;
        border-radius: 0;
    }
    blockquote {
        border-left: 4px solid #ffc107;
        padding-left: 15px;
        margin: 10px 0;
        color: #666;
        font-style: italic;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 10px 0;
        font-size: 9pt;
    }
    th {
        background-color: #667eea;
        color: white;
        padding: 8px;
        text-align: left;
        border: 1px solid #667eea;
    }
    td {
        padding: 6px 8px;
        border: 1px solid #ddd;
    }
    tr:nth-child(even) {
        background-color: #f9f9f9;
    }
    a {
        color: #667eea;
        text-decoration: none;
        border-bottom: 1px dotted #667eea;
    }
    img {
        max-width: 100%;
        height: auto;
        margin: 10px 0;
    }
    .highlight {
        background-color: #fff3cd;
        padding: 10px;
        border-left: 4px solid #ffc107;
        margin: 10px 0;
    }
    hr {
        border: none;
        border-top: 2px solid #ddd;
        margin: 20px 0;
    }
"""





def html_to_pdf(html_content, pdf_path):
    """
    HTML を PDF に変換
    """
    try:
        html_string = f"""
        <!DOCTYPE html>
        <html lang="ja">
        <head>
            <meta charset="UTF-8">
            <title>LLM Learning Material</title>
            <style>
                {PDF_CSS}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        
        HTML(string=html_string).write_pdf(pdf_path)
        return True
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False


def convert_file(md_file_path):
    """
    1つの Markdown ファイルを PDF に変換
    """
    if not md_file_path.exists():
        print(f"⚠️  ファイルが見つかりません: {md_file_path}")
        return False
    
    try:
        print(f"\n📄 処理中: {md_file_path.name}")
        
        # Markdown 読込
        with open(md_file_path, 'r', encoding='utf-8') as f:
            markdown_text = f.read()
        
        print(f"  ✓ Markdown 読込完了 ({len(markdown_text)} 文字)")
        
        # HTML に変換
        html_content = simple_markdown_to_html(markdown_text)
        print(f"  ✓ HTML 変換完了")
        
        # PDF に変換
        pdf_file_path = md_file_path.with_suffix('.pdf')
        if html_to_pdf(html_content, str(pdf_file_path)):
            file_size = os.path.getsize(pdf_file_path) / 1024 / 1024
            print(f"  ✅ PDF 作成完了: {pdf_file_path.name} ({file_size:.2f} MB)")
            return True
        else:
            print(f"  ❌ PDF 作成失敗")
            return False
    
    except Exception as e:
        print(f"  ❌ エラー発生: {e}")
        return False


def main():
    """
    メイン処理
    """
    print("=" * 70)
    print("📚 LLM 学習資料 - Markdown → PDF 変換")
    print("=" * 70)
    
    if not LEARNING_MATERIALS_DIR.exists():
        print(f"❌ ディレクトリが見つかりません: {LEARNING_MATERIALS_DIR}")
        return
    
    print(f"\n📁 対象ディレクトリ: {LEARNING_MATERIALS_DIR}")
    print(f"📊 変換ファイル数: {len(FILES_TO_CONVERT)}\n")
    
    # 変換処理
    success_count = 0
    for filename in FILES_TO_CONVERT:
        md_path = LEARNING_MATERIALS_DIR / filename
        if convert_file(md_path):
            success_count += 1
    
    # 完了報告
    print(f"\n" + "=" * 70)
    print(f"✅ 完了: {success_count}/{len(FILES_TO_CONVERT)} ファイルが PDF に変換されました")
    print("=" * 70)
    
    # 生成ファイル一覧
    pdf_files = sorted(LEARNING_MATERIALS_DIR.glob("*.pdf"))
    if pdf_files:
        print(f"\n📂 生成された PDF ファイル:")
        for pdf_file in pdf_files:
            size = os.path.getsize(pdf_file) / 1024
            print(f"  ✓ {pdf_file.name} ({size:.1f} KB)")
    
    print(f"\n💡 ヒント: PDF ファイルは {LEARNING_MATERIALS_DIR} に保存されています")


if __name__ == "__main__":
    main()
