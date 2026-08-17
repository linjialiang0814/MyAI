from pydantic import BaseModel


class TaskRunAccessRequest(BaseModel):
    user_id: str
