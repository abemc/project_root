import os
from src.rag.agent import RAGAgent


class DummyRetriever:
    def hybrid_search(self, q, top_k=10):
        return []


class DummyReranker:
    def rerank(self, q, docs, top_k=None):
        return docs


def test_agent_auto_presearch(monkeypatch):
    # 環境変数で事前検索を有効化
    os.environ["RAG_ENABLE_DATE_PRESEARCH"] = "true"

    # モジュール内の search_web_tool をモックして簡易的な結果を返す
    import src.rag.agent as agent_mod

    def fake_search(q):
        return [{"id": "w1", "text": "ダミー記事（昨日のニュース）", "score": 0.9}]

    monkeypatch.setattr(agent_mod, "search_web_tool", fake_search)

    # エージェントを作成（実際のRetriever/Rerankerは重いためダミーで代替）
    agent = RAGAgent("昨日の出来事を教えて", DummyRetriever(), DummyReranker())

    # プランは即時終了するように差し替え（事前検索の確認が目的）
    agent._plan_action = lambda: {"action": "answer", "thought": "", "tool_input": {}}
    agent._handle_answer = lambda thought: (setattr(agent, "finished", True), "Answer generated.")

    # 1ステップ実行して presearch が行われ current_docs が埋まることを確認
    agent.run_step()

    assert agent.state.get("interpreted_date") is not None
    assert isinstance(agent.state.get("current_docs"), list)
    assert len(agent.state.get("current_docs")) > 0
