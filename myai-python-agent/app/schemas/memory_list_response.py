from pydantic import BaseModel

from app.schemas.memory_item_response import MemoryItemResponse


class MemoryListResponse(BaseModel):
    memories: list[MemoryItemResponse]
