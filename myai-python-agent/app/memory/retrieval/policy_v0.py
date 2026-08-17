from typing import List

from app.memory.retrieval.retriever_v1 import RetrievedMemory

#mem_type 标识出来的 可以乘一个系数 与相似度阈值比较

SIM_THRESHOLD = 0.2 #相似度阈值
MAX_MEMORIES = 3     #top_K

class MemoryPolicy:

    @staticmethod
    def filter_memories(memories: List[RetrievedMemory])-> List[RetrievedMemory]:
        #重要性系数
        coefficients = {"preference": 1.2, "fact": 1.1, "decision": 1.3, "important": 1.1} #系数后续根据测试或需要随时调整

        allowed_types = {"preference", "fact", "decision","important"}

        filtered = []
        for mem in memories:
            if not (SIM_THRESHOLD <= mem.similarity < 1):
                continue
            if mem.mem_type not in allowed_types:
                continue

            coefficient = coefficients.get(mem.mem_type, 1)
            importance = coefficient * mem.similarity

            filtered.append((mem, importance))

        filtered.sort(key = lambda x : x[1], reverse = True)
        return [mem for mem, _ in filtered[:MAX_MEMORIES]]
        #return filtered[:MAX_MEMORIES]