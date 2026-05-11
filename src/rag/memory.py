import os

class MemoryManager:
    def __init__(self, retriever):
        self.retriever = retriever

    def summarize_and_store(self, question, answer, history=None):
        """
        対話内容を要約し、記憶として保存する。
        """
        # シンプルな要約形式 (今のところはそのまま保存、または簡易要約)
        summary = f"過去の質問: {question}\n過去の回答: {answer}"
        
        # Retrieverを使用して知識ベースに「記憶」として追加
        source_info = {
            "source": "memory",
            "type": "conversation_history",
            "created_at": os.uname()[3] # timestampの代わり
        }
        
        # 実際には datetime を使いたいが、ここでは Retrieverに合わせて
        import datetime
        source_info["created_at"] = datetime.datetime.now().isoformat()

        count = self.retriever.add_texts([summary], source_info)
        print(f"Memory stored: {count} entry added.")
        return count

    def search_memories(self, query, top_k=5):
        """
        現在のクエリに関連する過去の記憶を検索する。
        """
        # ソースを 'memory' に限定して検索
        memories = self.retriever.hybrid_search(query, top_k=top_k, source_filter="memory")
        return memories
