from pydantic import BaseModel, Field

class MemoryQueryRequest(BaseModel):
    #从内存中查询
    user_id: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=100_000)
