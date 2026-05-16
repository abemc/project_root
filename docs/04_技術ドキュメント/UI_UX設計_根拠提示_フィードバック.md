# UI/UX設計：根拠提示・フィードバック機能

## 概要

RAGシステムの回答品質を高め、ユーザーが根拠を確認・評価できるUI/UX機能の設計案です。

---

## 1. 根拠提示機能

### 表示要素
- **回答本文**：通常どおり表示
- **根拠文書パネル**：回答の根拠となった文書（ファイル名・スニペット・関連度スコア）を折りたたみ/展開で表示
- **ハイライト**：根拠文書の該当箇所を色付きでハイライト
- **出典リンク**：元ドキュメントへのリンクまたはパスを表示

### Streamlit実装イメージ
```python
with st.expander("📎 根拠文書を表示"):
    for doc in evidence_list:
        st.markdown(f"**{doc['source']}** (関連度: {doc['score']:.2f})")
        st.markdown(f"> {doc['snippet']}")
        if doc.get('link'):
            st.markdown(f"[元文書を開く]({doc['link']})")
```

---

## 2. フィードバック機能

### 評価ボタン
- 回答の各末尾に 👍（役に立った）/ 👎（役に立たなかった）ボタンを配置
- クリック時にフィードバックをJSONログとして保存

### フィードバックログ形式（例）
```json
{
  "timestamp": "2026-04-27T12:00:00",
  "query": "RAGとは？",
  "answer_snippet": "検索拡張生成です...",
  "rating": "positive",
  "comment": "分かりやすかった"
}
```

### Streamlit実装イメージ
```python
col1, col2 = st.columns(2)
with col1:
    if st.button("👍 役に立った"):
        save_feedback(query, answer, "positive")
        st.success("フィードバックを受け付けました")
with col2:
    if st.button("👎 改善が必要"):
        comment = st.text_input("改善点を教えてください")
        if st.button("送信"):
            save_feedback(query, answer, "negative", comment)
            st.info("フィードバックを送信しました")
```

---

## 3. フィードバック活用フロー

1. フィードバックログを定期集計
2. 低評価回答の原因分析（検索精度・コーパス品質・LLM応答）
3. コーパス改善・クエリ前処理改善・プロンプト調整にフィードバック
4. 改善後に自動評価スクリプトで精度を再確認

---

## 今後の実装優先度

| 機能 | 優先度 | 備考 |
|------|--------|------|
| 根拠文書パネル | 高 | まずexpanderで簡易実装 |
| フィードバックボタン | 高 | JSONログ保存から開始 |
| ハイライト表示 | 中 | streamlit-extras等活用 |
| フィードバック集計ダッシュボード | 低 | 運用フェーズで追加 |
