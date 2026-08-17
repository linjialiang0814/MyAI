from pydantic import BaseModel, Field

class MemoryWriteRequest(BaseModel):
    #请求写内存
    user_id: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=100_000)
