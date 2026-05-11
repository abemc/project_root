#!/usr/bin/env python3
"""
RAG キャッシング問題診断スクリプト

目的: 同じ回答が繰り返される問題を診断
- PDFファイルがコーパスに正しく保存されているか確認
- 検索機能が正常に機能しているか確認
- LLM キャッシングの有無確認
"""

import json
from pathlib import Path

# プロジェクトルート設定
PROJECT_ROOT = Path(__file__).resolve().parent
CORPUS_BASE_PATH = PROJECT_ROOT / "rag_corpus"

print("=" * 80)
print("🔍 RAG キャッシング問題診断スクリプト")
print("=" * 80)

# 1. コーパスの確認
print("\n📚 【1】コーパス状態の確認")
print("-" * 80)

meta_path = CORPUS_BASE_PATH / "corpus_meta.json"
if meta_path.exists():
    with open(meta_path, "r", encoding="utf-8") as f:
        meta_data = json.load(f)
    
    print("✅ コーパスメタデータが存在します")
    print(f"   ファイル: {meta_path}")
    print(f"   保存ドキュメント数: {len(meta_data)}")
    
    if meta_data:
        print("\n   最初の3件のドキュメント:")
        for i, doc in enumerate(meta_data[:3]):
            source = doc.get("meta", {}).get("source") or doc.get("source", "不明")
            text_preview = (doc.get("text", doc.get("content", ""))[:100] + "...").replace("\n", " ")
            print(f"   [{i+1}] {source}")
            print(f"       テキスト: {text_preview}")
    else:
        print("\n   ⚠️ ドキュメントが0件です！")
else:
    print(f"❌ コーパスメタデータが見つかりません: {meta_path}")

# 2. FAISSインデックスの確認
print("\n\n🔎 【2】FAISSインデックスの確認")
print("-" * 80)

import faiss

index_path = CORPUS_BASE_PATH / "corpus.index"
if index_path.exists():
    try:
        index = faiss.read_index(str(index_path))
        print("✅ FAISSインデックスが存在します")
        print(f"   ファイル: {index_path}")
        print(f"   インデックス内のベクトル数: {index.ntotal}")
        
        if meta_path.exists() and index.ntotal != len(meta_data):
            print(f"   ⚠️  警告: ベクトル数 ({index.ntotal}) とメタデータ数 ({len(meta_data)}) が一致しません！")
        else:
            print("   ✅ ベクトル数とメタデータ数が一致しています")
    except Exception as e:
        print(f"❌ インデックス読み込みエラー: {e}")
else:
    print(f"❌ FAISSインデックスが見つかりません: {index_path}")

# 3. 検索テスト
print("\n\n🔍 【3】検索機能の確認")
print("-" * 80)

try:
    from src.rag.retriever import Retriever
    
    retriever = Retriever(
        index_path=str(index_path),
        meta_path=str(meta_path)
    )
    
    # 異なるクエリで検索テスト
    test_queries = [
        "PDF要約",
        "微分 積分",
        "第2章",
        "数学",
        "calculus"
    ]
    
    print("異なるクエリでの検索結果:")
    for query in test_queries:
        try:
            results = retriever.search(query, top_k=3)
            print(f"\n  クエリ: '{query}'")
            if results:
                print(f"  ✅ 検索結果: {len(results)}件")
                for i, result in enumerate(results[:2]):
                    source = result.get("meta", {}).get("source") or result.get("source", "不明")
                    score = result.get("score", "N/A")
                    text_preview = (result.get("text", result.get("content", ""))[:80] + "...").replace("\n", " ")
                    print(f"     [{i+1}] (Score: {score:.4f}) {source}")
                    print(f"         {text_preview}")
            else:
                print("  ❌ 検索結果: 0件")
        except Exception as e:
            print(f"  ❌ 検索エラー: {e}")
    
except Exception as e:
    print(f"❌ Retriever 初期化エラー: {e}")

# 4. LLM キャッシング確認
print("\n\n💾 【4】LLM キャッシング確認")
print("-" * 80)

try:
    from src.rag.llm import call_llm
    
    print("同じプロンプトを複数回実行して、LLMのキャッシング有無を確認します...\n")
    
    test_prompt = "次の計算をしてください: 2+3=?"
    
    responses = []
    for i in range(3):
        print(f"  [{i+1}] 実行中...", end="", flush=True)
        response = call_llm(test_prompt, model="qwen2.5:7b")
        responses.append(response)
        print(f" 完了: {response[:50]}")
    
    # 全て同じか確認
    if len(set(responses)) == 1:
        print("\n  ⚠️  警告: 3回全て同じ応答が返されました（キャッシングが疑われます）")
        print(f"     応答: {responses[0]}")
    else:
        print("\n  ✅ 異なる応答が返されました（キャッシングは見られません）")
        for i, resp in enumerate(set(responses), 1):
            print(f"     パターン {i}: {resp[:50]}")
    
except Exception as e:
    print(f"❌ LLM テストエラー: {e}")

# 5. RAGAgent のコンテキスト処理テスト
print("\n\n🤖 【5】RAGAgent コンテキスト処理テスト")
print("-" * 80)

try:
    from src.rag.agent import RAGAgent
    
    print("異なるクエリで RAGAgent を実行して、回答の違いを確認します...\n")
    
    # テストクエリ
    test_questions = [
        "第1章の内容は？",
        "第2章の内容は？",
        "第3章の内容は？"
    ]
    
    responses_agent = {}
    for question in test_questions:
        print(f"  質問: '{question}'")
        try:
            agent = RAGAgent(
                question,
                retriever,
                None,  # reranker
                max_steps=2,
                llm_model="qwen2.5:7b",
                history=[]
            )
            
            # 最初のステップだけ実行
            if not agent.finished:
                agent.run_step()
            
            # 状態確認
            docs_count = len(agent.state.get("current_docs", []))
            print(f"    ✅ 検索ドキュメント数: {docs_count}件")
            
            if docs_count > 0:
                doc_preview = agent.state["current_docs"][0].get("text", "")[:100]
                responses_agent[question] = doc_preview
                print(f"       最初のドキュメント: {doc_preview}...")
            else:
                responses_agent[question] = "(なし)"
                print("       ドキュメント: なし")
        except Exception as e:
            print(f"    ❌ エラー: {e}")
    
    # 結果分析
    unique_responses = len(set(responses_agent.values()))
    print(f"\n  結果: {len(test_questions)}個の質問に対して {unique_responses}種類の異なるドキュメントが検索されました")
    
    if unique_responses == 1:
        print("  ⚠️  警告: 全ての質問で同じドキュメントが返されています！")
        print(f"     内容: {list(responses_agent.values())[0]}")
    else:
        print("  ✅ 異なるドキュメントが返されています（正常）")
    
except Exception as e:
    print(f"❌ RAGAgent テストエラー: {e}")

# 6. 推奨アクション
print("\n\n📋 【推奨アクション】")
print("-" * 80)

print("""
問題の原因に応じた対応：

1️⃣ コーパスが空 (ドキュメント数 = 0)
   → アクション:
     - PDFファイルをアップロードしてください
     - app.py の「📚 知識・データ管理」セクションで PDF をアップロード

2️⃣ ベクトル数 ≠ メタデータ数
   → アクション:
     - コーパスを再構築してください
     - manage_kb.py を実行するか、UI で「知識ベースをリセット」

3️⃣ 検索結果が全て同じ
   → アクション:
     - PDFファイルのコンテンツが正しく抽出されているか確認
     - OCR キャッシュをクリア: rm -rf rag_corpus/ocr_cache
     - 別のPDFファイルを試してみる

4️⃣ LLM が同じ応答を返す
   → アクション:
     - Ollama のキャッシュをクリア
     - モデルを再ロード: ollama pull qwen2.5:7b
     - 別のモデルを試してみる (llama2 など)

5️⃣ 複数の問題
   → アクション:
     - 管理者に相談してください
     - このスクリプトの出力をコピーして共有
""")

print("=" * 80)
print("診断完了")
print("=" * 80)
