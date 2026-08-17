from pydantic import BaseModel


class KnowledgeQARequest(BaseModel):
    user_id: str
    file_id: str
    question: str
    top_k: int = 3
