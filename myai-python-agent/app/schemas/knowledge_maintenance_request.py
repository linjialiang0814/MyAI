from pydantic import BaseModel


class KnowledgeMaintenanceRequest(BaseModel):
    user_id: str
    dry_run: bool = True
    file_id: str | None = None
    rebuild: bool = False
