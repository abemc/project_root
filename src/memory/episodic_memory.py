"""Episodic memory: store and query past episodes (MVP)

Stores episodes as JSONL in `logs/episodes.jsonl` and provides simple keyword query.
"""
from typing import List, Dict, Optional
from pathlib import Path
import json
import uuid
import os
from datetime import datetime


class EpisodicMemory:
    def __init__(self, storage_dir: str = None):
        if storage_dir is None:
            storage_dir = Path('logs') / 'episodes'
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.storage_dir / 'episodes.jsonl'
        self._load()

    def _load(self):
        self.episodes: List[Dict] = []
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            self.episodes.append(json.loads(line))
            except Exception:
                self.episodes = []

    def store_episode(self, episode: Dict) -> str:
        eid = episode.get('episode_id') or str(uuid.uuid4())
        entry = {**episode}
        entry['episode_id'] = eid
        entry.setdefault('timestamp', datetime.now().isoformat())
        self.episodes.append(entry)
        try:
            with open(self.file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception:
            pass
        return eid

    def query_episodes(self, query: str, top_k: int = 5, filters: Optional[Dict] = None) -> List[Dict]:
        # Simple keyword scoring across 'query', 'action', 'result', 'resolution'
        q = query.lower()
        scored = []
        for ep in self.episodes:
            text = ' '.join([
                str(ep.get('trigger', '')),
                str(ep.get('query', '')),
                str(ep.get('action', '')),
                str(ep.get('result', '')),
                str(ep.get('resolution', '')),
            ]).lower()
            score = text.count(q)
            if score > 0:
                scored.append((score, ep))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:top_k]]
