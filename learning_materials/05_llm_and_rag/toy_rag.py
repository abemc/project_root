#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Toy RAG (Retrieval-Augmented Generation) Sandbox
RAGの仕組み（埋め込み・検索・プロンプト・生成）を、外部APIや重いライブラリなしで
ステップバイステップで学ぶための超軽量スクリプトです。
"""

import os
import math
import re
from collections import Counter
from typing import List, Dict, Tuple

# 1. 簡易ナレッジベース (知識データベース)
KNOWLEDGE_BASE = [
    {
        "id": 1,
        "content": "Pythonは1991年にグイド・ヴァンロッサムによって開発された、コードの可読性を重視するオープンソースのプログラミング言語です。AIやデータ分析で広く使われています。"
    },
    {
        "id": 2,
        "content": "RAG (Retrieval-Augmented Generation / 検索拡張生成) は、LLMに外部の知識ベース（データベースなど）から検索した関連コンテキストを入力として与え、回答の正確性を高める技術です。"
    },
    {
        "id": 3,
        "content": "Transformerは2017年にGoogleの研究者らによって提案されたニューラルネットワーク構造で、現在のほぼすべてのLLM（ChatGPTなど）の基礎となっています。自己注意機構 (Self-Attention) を持ちます。"
    },
    {
        "id": 4,
        "content": "ベクトル埋め込み (Vector Embedding) とは、テキストなどのデータを多次元空間上の実数ベクトルとして表現する手法です。似た意味を持つ言葉同士は、ベクトル空間上で近い位置に配置されます。"
    }
]

# 2. 簡易テキスト解析・類似度計算 (Bag of Words & Cosine Similarity)
# 本物のベクトルデータベースの代わりに、Pythonの標準機能だけで簡易的な検索エンジンを作ります。

def tokenize(text: str) -> List[str]:
    """テキストを単語（トークン）に簡易分割する（英語＋日本語の文字ベースのハイブリッド）。"""
    text = text.lower()
    # 日本語の句読点や英単語を簡易分割
    words = re.findall(r'[a-zA-Z0-9_]+|[\u4e00-\u9fff]|[ぁ-ん]|[ァ-ヴ]', text)
    # 助詞や助動詞などの頻出ひらがな1文字をストップワードとして簡易除外
    stopwords = set("てにおはがのとものですかいるするあるっつ")
    return [w for w in words if w.strip() and (len(w) > 1 or w not in stopwords)]


def get_cosine_similarity(vec1: Dict[str, int], vec2: Dict[str, int]) -> float:
    """2つの頻度ベクトル（単語カウント）のコサイン類似度を計算する。"""
    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum(vec1[x] * vec2[x] for x in intersection)

    sum1 = sum(val ** 2 for val in vec1.values())
    sum2 = sum(val ** 2 for val in vec2.values())
    denominator = math.sqrt(sum1) * math.sqrt(sum2)

    if not denominator:
        return 0.0
    return numerator / denominator

def retrieve(query: str, top_k: int = 1) -> List[Tuple[Dict[str, any], float]]:
    """クエリに最も関連するドキュメントを知識データベースから検索（Retrieval）する。"""
    query_tokens = tokenize(query)
    query_vector = Counter(query_tokens)
    
    results = []
    for doc in KNOWLEDGE_BASE:
        doc_tokens = tokenize(doc["content"])
        doc_vector = Counter(doc_tokens)
        
        sim = get_cosine_similarity(query_vector, doc_vector)
        results.append((doc, sim))
    
    # 類似度の降順でソート
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]

# 3. 擬似LLM生成エンジン (Generation)
def mock_llm_generate(prompt: str, retrieved_content: str, query: str) -> str:
    """APIを使わない場合の、ルールベースによる擬似LLM回答生成。"""
    if "rag" in query.lower() or "検索拡張" in query:
        return "【擬似LLMの回答】: RAGは、あらかじめ用意したデータベースなどから関連情報を「検索」し、それを「コンテキスト（背景知識）」としてLLMへ渡すことで、嘘（ハルシネーション）を減らす非常に強力な仕組みです。"
    elif "python" in query.lower() or "パイソン" in query:
        return "【擬似LLMの回答】: Pythonは、初心者にも読みやすく書きやすいプログラミング言語です。豊富なライブラリ（Scikit-learnやPyTorchなど）があるため、AIや機械学習の学習・開発に最適です。"
    elif "transformer" in query.lower() or "トランスフォーマー" in query:
        return "【擬似LLMの回答】: Transformerは、並列処理が得意なAttention（注意機構）を中核に据えたアーキテクチャです。この登場によって、巨大なLLMが作れるようになりました。"
    elif "ベクトル" in query or "埋め込み" in query or "embedding" in query.lower():
        return "【擬似LLMの回答】: ベクトル埋め込みは、言葉の「意味」を数値のリスト（座標）に変換します。例えば「王様」から「男性」を引いて「女性」を足すと「女王」のベクトルに近くなる、といったセマンティックな計算が可能です。"
    
    return f"【擬似LLMの回答】: コンテキストとして「{retrieved_content[:30]}...」を受け取りました。ご質問「{query}」に対する詳細な情報は提供された知識ベースにはありませんが、本物のLLMであればこのコンテキストを要約して自然な返答を生成します。"

def run_rag_pipeline(query: str):
    print("\n" + "="*60)
    print(f"🕵️ ユーザーの質問: {query}")
    print("="*60)
    
    # --- STEP 1: Retrieval (検索) ---
    print("\n🔍 [STEP 1] Retrieval（関連情報の検索）を実行中...")
    matches = retrieve(query, top_k=1)
    doc, score = matches[0]
    
    print(f"  -> 最も類似度の高いドキュメントを検出 (類似度スコア: {score:.4f}):")
    print(f"     「{doc['content']}」")
    
    # --- STEP 2: Prompt Engineering (プロンプトの組み立て) ---
    print("\n✍️ [STEP 2] Prompt Engineering（プロンプトの構築）...")
    system_prompt = "あなたは優秀なアシスタントです。提供された【参考知識】のみに基づいて、質問に正確に答えてください。"
    
    final_prompt = f"""{system_prompt}

【参考知識】
{doc['content']}

質問: {query}
回答:"""
    
    print("-" * 50)
    print("📋 LLMへ送信される最終的なプロンプト:")
    print(final_prompt)
    print("-" * 50)
    
    # --- STEP 3: Generation (回答の生成) ---
    print("\n🤖 [STEP 3] Generation（LLMによる回答の生成）...")
    
    # 環境変数に OpenAI キーがある場合は本物を呼ぶことも可能（勉強用）
    if os.getenv("OPENAI_API_KEY"):
        try:
            import openai
            print("  -> OpenAI API を呼び出しています...")
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"【参考知識】\n{doc['content']}\n\n質問: {query}"}
                ],
                temperature=0.0
            )
            answer = "【本物のOpenAI LLMの回答】: " + response.choices[0].message.content
        except Exception as e:
            print(f"  -> OpenAI呼び出し中にエラー (モック回答にフォールバックします): {e}")
            answer = mock_llm_generate(final_prompt, doc['content'], query)
    else:
        print("  -> (APIキーが未設定のため、ローカルの擬似LLM機能で回答をシミュレートします)")
        answer = mock_llm_generate(final_prompt, doc['content'], query)
        
    print("\n💬 最終出力:")
    print(answer)
    print("="*60 + "\n")

if __name__ == "__main__":
    print("🤖 Toy RAG Sandbox へようこそ！")
    print("このスクリプトは、RAGのコアプロセスを目で追うための勉強用ツールです。")
    print("知識ベースには「Python」「RAG」「Transformer」「ベクトル埋め込み」に関する情報が登録されています。")
    
    # デモ用の質問を実行
    run_rag_pipeline("RAGってどういう仕組みですか？")
    
    # インタラクティブモード
    while True:
        try:
            user_input = input("質問を入力してください (終了するには Ctrl+C または 'q' を入力): ").strip()
            if not user_input or user_input.lower() == 'q':
                break
            run_rag_pipeline(user_input)
        except KeyboardInterrupt:
            print("\n終了します。学習頑張ってください！")
            break
