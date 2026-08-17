import chromadb
import uuid
import numpy as np
from typing import List
from app.memory.model.mem_item_v0 import MemoryItem

class ChromaMemoryStore:
    """
    step 13 基于 ChromaDB 的长期记忆存储，替换原有的 MemoryStore
    """
    def __init__(self, persist_dir: str = "./chroma_db"):
        # 使用 PersistentClient 确保持久化
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=chromadb.config.Settings(anonymized_telemetry=False)
        )

        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name="long_term_memory",
            metadata={"hnsw:space": "cosine"}
        )

    def add(
            self,
            user_id: str,
            content: str,
            vector: np.ndarray,
            mem_type: str = "general",
            score: float = 1.0
    ) -> str:
        """
        添加记忆项（兼容原有接口）
        Returns: 记忆ID
        """
        memory_id = str(uuid.uuid4())

        # 准备元数据
        metadata = {
            "user_id": user_id,
            "mem_type": mem_type,
            "score": score
        }

        # 添加到 ChromaDB
        self.collection.add(
            ids=[memory_id],
            embeddings=[vector.tolist()],
            documents=[content],
            metadatas=[metadata]
        )

        return memory_id

    def add_memory_item(self, user_id: str, memory_item: MemoryItem) -> str:

        return self.add(
            user_id=user_id,
            content=memory_item.content,
            vector=memory_item.vector,
            mem_type=memory_item.mem_type,
            score=memory_item.score
        )

    def get_all(self, user_id: str) -> List[MemoryItem]:
        # 查询该用户的所有记忆
        results = self.collection.get(
            where={"user_id": user_id},
            include=["embeddings", "documents", "metadatas"]
        )

        # 转换为 MemoryItem 列表
        memories = []
        for i in range(len(results["ids"])):
            metadata_dict = dict(results["metadatas"][i]) if results["metadatas"][i] else 0
            item = MemoryItem(
                content=results["documents"][i],
                vector=np.array(results["embeddings"][i]),
                mem_type=metadata_dict.get("mem_type", "general"),
                score=metadata_dict.get("score", 1.0),
                metadata=metadata_dict
            )
            memories.append(item)

        return memories

    def replace_all(self, user_id: str, memories: List[MemoryItem]):
        # 先删除该用户的所有现有记忆
        existing = self.collection.get(
            where={"user_id": user_id},
            include=[]
        )
        if existing["ids"]:
            self.collection.delete(ids=existing["ids"])

        # 添加新的记忆
        for memory_item in memories:
            self.add_memory_item(user_id, memory_item)

    def update_score_by_id(self, memory_id: str, new_score: float):
        # 获取当前元数据
        current = self.collection.get(ids=[memory_id], include=["metadatas"])
        if not current["metadatas"]:
            return

        # 更新元数据中的分数
        metadata = current["metadatas"][0]
        metadata.score = new_score

        # 更新到 ChromaDB
        self.collection.update(
            ids=[memory_id],
            metadatas=[metadata]
        )

    def clear_user_memories(self, user_id: str):
        #清除用户记忆
        results = self.collection.get(
            where={"user_id": user_id},
            include=[]
        )
        if results["ids"]:
            self.collection.delete(ids=results["ids"])

    def size(self, user_id: str) -> int:
        results = self.collection.get(
            where={"user_id": user_id},
            include=[]
        )
        return len(results["ids"])