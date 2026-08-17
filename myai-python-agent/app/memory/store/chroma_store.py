from typing import List, Optional
import numpy as np
from app.memory.model.mem_item import MemoryItem
from app.model.config import load_llm_settings
from app.runtime.chroma_client import create_chroma_client


class MemoryStoreUnavailableError(OSError):
    pass

class ChromaMemoryStore:
    """
    vector database long-term memory store
    """
    def __init__(
        self,
        persist_dir: str | None = None,
        collection_name: str | None = None,
        chroma_client=None,
    ):
        settings = load_llm_settings() if collection_name is None else None
        self.client = chroma_client if chroma_client is not None else create_chroma_client(persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name if collection_name is not None else settings.memory_collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self,
            user_id: str,
            content: str,
            vector: np.ndarray,
            mem_type: str = "general",
            score: float = 1.0,
            importance: float = 1.0,
            metadata: Optional[dict] = None,
    ) -> str:
        memory_item = MemoryItem(
            content=content,
            vector=np.array(vector, dtype=np.float32),
            mem_type=mem_type,
            score=score,
            user_id=user_id,
            importance=importance,
            metadata=metadata or {},
        )
        self.add_item(user_id, memory_item)
        return memory_item.memory_id

    def add_item(self, user_id: str, memory_item: MemoryItem) -> str:
        memory_item.user_id = user_id
        try:
            self.collection.add(
                ids=[memory_item.memory_id],
                embeddings=[memory_item.vector.astype(np.float32).tolist()],
                documents=[memory_item.content],
                metadatas=[memory_item.to_metadata()],
            )
        except Exception as exc:
            raise MemoryStoreUnavailableError("memory store write failed") from exc
        return memory_item.memory_id

    def get_all(self, user_id: str) -> List[MemoryItem]:
        try:
            results = self.collection.get(
                where={"user_id": user_id},
                include=["embeddings", "documents", "metadatas"]
            )
        except Exception as exc:
            raise MemoryStoreUnavailableError("memory store read failed") from exc
        memories: List[MemoryItem] = []
        for i in range(len(results.get("ids", []))):
            metadata_dict = dict(results["metadatas"][i]) if results["metadatas"][i] else {}
            item = MemoryItem.from_metadata(
                content=results["documents"][i],
                vector=np.array(results["embeddings"][i], dtype=np.float32),
                metadata=metadata_dict,
            )
            memories.append(item)
        return memories

    def get_by_id(self, user_id, memory_id: str) -> Optional[MemoryItem]:
        try:
            result = self.collection.get(
                ids=[memory_id],
                include=["embeddings", "documents", "metadatas"]
            )
        except Exception as exc:
            raise MemoryStoreUnavailableError("memory store lookup failed") from exc
        if not result.get("ids"):
            return None
        metadata_dict = dict(result["metadatas"][0]) if result["metadatas"][0] else {}
        item = MemoryItem.from_metadata(
            content=result["documents"][0],
            vector=np.array(result["embeddings"][0], dtype=np.float32),
            metadata=metadata_dict,
        )
        if item.user_id != user_id:
            return None
        return item

    def update_memory(self, user_id: str, memory_item: MemoryItem) -> bool:
        existing = self.get_by_id(user_id, memory_item.memory_id)
        if not existing:
            return False
        memory_item.user_id = user_id
        try:
            self.collection.update(
                ids=[memory_item.memory_id],
                embeddings=[memory_item.vector.astype(np.float32).tolist()],
                documents=[memory_item.content],
                metadatas=[memory_item.to_metadata()],
            )
        except Exception as exc:
            raise MemoryStoreUnavailableError("memory store update failed") from exc
        return True

    def update_score_by_id(self, user_id: str, memory_id: str, new_score: float) -> bool:
        item = self.get_by_id(user_id, memory_id)
        if not item:
            return False
        item.score = float(new_score)
        return self.update_memory(user_id, item)

    def touch_memory(self, user_id: str, memory_id: str, score: float | None = None) -> bool:
        item = self.get_by_id(user_id, memory_id)
        if not item:
            return False
        item.touch()
        if score is not None:
            item.score = float(score)
        return self.update_memory(user_id, item)

    def delete_by_id(self, user_id: str, memory_id: str) -> bool:
        item = self.get_by_id(user_id, memory_id)
        if not item:
            return False
        try:
            self.collection.delete(ids=[memory_id])
        except Exception as exc:
            raise MemoryStoreUnavailableError("memory store delete failed") from exc
        return True

    def replace_all(self, user_id: str, memories: List[MemoryItem])-> None:
        self.clear_user_memories(user_id)
        for mem in memories:
            self.add_item(user_id, mem)

    def clear_user_memories(self, user_id: str)-> None:
        try:
            results = self.collection.get(where={"user_id": user_id}, include=[])
        except Exception as exc:
            raise MemoryStoreUnavailableError("memory store cleanup failed") from exc
        if results["ids"]:
            try:
                self.collection.delete(ids=results["ids"])
            except Exception as exc:
                raise MemoryStoreUnavailableError("memory store cleanup failed") from exc

    def query_similar(self, user_id: str, query_vector: np.ndarray, top_k: int = 5) -> List[tuple[MemoryItem, float]]:
        try:
            results = self.collection.query(
                query_embeddings=[query_vector.astype(np.float32).tolist()],
                n_results=top_k,
                where={"user_id": user_id},
                include=["embeddings", "documents", "metadatas", "distances"],
            )
        except Exception as exc:
            raise MemoryStoreUnavailableError("memory store query failed") from exc
        items: List[tuple[MemoryItem, float]] = []
        ids = results.get("ids", [[]])[0]
        embeddings = results.get("embeddings", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for idx in range(len(ids)):
            item = MemoryItem.from_metadata(
                content=documents[idx],
                vector=np.array(embeddings[idx], dtype=np.float32),
                metadata=dict(metadatas[idx] or {}),
            )
            similarity = 1.0 - float(distances[idx])
            items.append((item, similarity))
        return items

    def size(self, user_id: str) -> int:
        try:
            return len(self.collection.get(where={"user_id": user_id}, include=[]).get("ids", []))
        except Exception as exc:
            raise MemoryStoreUnavailableError("memory store size query failed") from exc
