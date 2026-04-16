import json
import os
import math
from typing import List, Dict, Optional, Any


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class MemoryStore:
    """长期记忆存储，支持向量语义检索，无 API key 时降级到关键词匹配。"""

    KEYWORD_HINTS = ["喜欢", "讨厌", "名字", "生日", "爱好", "工作", "学习", "城市", "家人", "朋友"]

    def __init__(self, role_dir: str, api_key: Optional[str] = None):
        self.role_dir = role_dir
        self.api_key = api_key
        self._vectors_path = os.path.join(role_dir, "memory", "long_term_vectors.json")
        self._data: List[Dict[str, Any]] = self._load()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def add(self, content: str, emotion: str = "中性", metadata: Optional[Dict] = None) -> None:
        entry: Dict[str, Any] = {
            "content": content,
            "emotion": emotion,
            "metadata": metadata or {},
            "embedding": self._embed(content),
        }
        self._data.append(entry)
        self._save()

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        if not self._data:
            return []

        query_embedding = self._embed(query)

        if query_embedding is not None:
            scored = [
                (entry, _cosine_similarity(query_embedding, entry["embedding"]))
                for entry in self._data
                if entry.get("embedding") is not None
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            return [
                {"content": e["content"], "emotion": e["emotion"], **e.get("metadata", {})}
                for e, _ in scored[:top_k]
            ]

        # 降级：关键词匹配
        results = [
            {"content": e["content"], "emotion": e["emotion"], **e.get("metadata", {})}
            for e in self._data
            if any(kw in query or kw in e["content"] for kw in self.KEYWORD_HINTS)
        ]
        return results[-top_k:]

    def all_memories(self) -> List[Dict]:
        return [
            {"content": e["content"], "emotion": e["emotion"], **e.get("metadata", {})}
            for e in self._data
        ]

    def clear(self) -> None:
        self._data = []
        self._save()

    def set_api_key(self, api_key: str) -> None:
        self.api_key = api_key

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _embed(self, text: str) -> Optional[List[float]]:
        if not self.api_key:
            return None
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            resp = client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            return resp.data[0].embedding
        except Exception:
            return None

    def _load(self) -> List[Dict]:
        if os.path.exists(self._vectors_path):
            try:
                with open(self._vectors_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return []

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._vectors_path), exist_ok=True)
        with open(self._vectors_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
