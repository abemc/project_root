#!/usr/bin/env python3
"""
マークダウンの最終修正スクリプト
"""

md_file = '/home/abemc/project_root/docs/reports/PHASE7_IMPLEMENTATION_REPORT.md'

with open(md_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 修正1: 文脈理解の深さセクション
old_text = """### 文脈理解の深さ

**従来** (3層):
```
ユーザークエリ → ドメイン検出 → 知識検索
```

**Phase 7後** (8+層):
```
ユーザークエリ
  → 背景分析
  → 明示的・隠れた意図検出
  → ドメイン推定
  → 複数ドメイン検索
  → 知識統合
  → 因果分析
  → 不確実性評価
```"""

new_text = """### 文脈理解の深さ

**従来** (3層):

ユーザークエリ → ドメイン検出 → 知識検索

**Phase 7後** (8+層):

1. ユーザークエリ
2. 背景分析
3. 明示的・隠れた意図検出
4. ドメイン推定
5. 複数ドメイン検索
6. 知識統合
7. 因果分析
8. 不確実性評価"""

content = content.replace(old_text, new_text)

# ファイルに保存
with open(md_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ マークダウンを修正しました")
print("📄 ファイル: " + md_file)
print("🎉 完成版フォーマットが統一されました")
