from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_memory_maintenance_scheduler, get_memory_service
from app.memory.maintenance.scheduler import MemoryMaintenanceScheduler
from app.memory.mem_service import MemoryService
from app.schemas.mem_query_request import MemoryQueryRequest
from app.schemas.mem_write_request import MemoryWriteRequest
from app.schemas.memory_edit_request import MemoryEditRequest
from app.schemas.memory_settings_request import MemorySettingsRequest
from app.schemas.memory_item_response import MemoryItemResponse
from app.schemas.memory_list_response import MemoryListResponse
from app.memory.governance import governance_response_fields
from app.memory.settings import settings_schema

router = APIRouter(prefix="/memory", tags=["memory"])


def _to_memory_response(mem) -> MemoryItemResponse:
    return MemoryItemResponse(
        memory_id=mem.memory_id,
        content=mem.content,
        mem_type=mem.mem_type,
        score=mem.score,
        importance=mem.importance,
        created_at=mem.created_at,
        last_accessed_at=mem.last_accessed_at,
        access_count=mem.access_count,
        status=mem.status,
        **governance_response_fields(mem.metadata),
    )


@router.post("/write")
def write_mem(
    req: MemoryWriteRequest,
    mem_service: MemoryService = Depends(get_memory_service),
    scheduler: MemoryMaintenanceScheduler | None = Depends(get_memory_maintenance_scheduler),
):
    if not req.user_id.strip() or not req.content.strip():
        raise HTTPException(status_code=400, detail="user_id and content are required")
    result = mem_service.process_user_input(
        req.user_id,
        req.content,
        source="user_explicit",
        allow_unstructured_manual_write=True,
    )
    _schedule_if_changed(scheduler, req.user_id, bool(result.get("written")))
    return result


@router.post("/query")
def query_mem(req: MemoryQueryRequest, mem_service: MemoryService = Depends(get_memory_service)):
    if not req.user_id.strip() or not req.content.strip():
        raise HTTPException(status_code=400, detail="user_id and content are required")
    memories = mem_service.retrieve_for_context(req.user_id, req.content)
    return {
        "memories": [m.content for m in memories]
    }


@router.get("/list/{user_id}", response_model=MemoryListResponse)
def list_memories(
    user_id: str,
    mem_type: str | None = None,
    mem_service: MemoryService = Depends(get_memory_service),
):
    memories = mem_service.list_memories(user_id, mem_type=mem_type)
    return MemoryListResponse(
        memories=[_to_memory_response(mem) for mem in memories]
    )


@router.get("/pending/{user_id}", response_model=MemoryListResponse)
def list_pending_memories(user_id: str, mem_service: MemoryService = Depends(get_memory_service)):
    memories = mem_service.list_pending_memories(user_id)
    return MemoryListResponse(
        memories=[_to_memory_response(mem) for mem in memories]
    )


@router.get("/settings/{user_id}")
def get_memory_settings(user_id: str, mem_service: MemoryService = Depends(get_memory_service)):
    return {
        "user_id": user_id,
        "settings": mem_service.settings_store.get(user_id).to_dict(),
        "schema": settings_schema(),
    }


@router.patch("/settings/{user_id}")
def update_memory_settings(
    user_id: str,
    req: MemorySettingsRequest,
    mem_service: MemoryService = Depends(get_memory_service),
):
    patch = req.model_dump(exclude_none=True) if hasattr(req, "model_dump") else req.dict(exclude_none=True)
    settings = mem_service.settings_store.update(user_id, patch)
    return {
        "user_id": user_id,
        "settings": settings.to_dict(),
        "schema": settings_schema(),
    }


@router.post("/{user_id}/{memory_id}/accept", response_model=MemoryItemResponse)
def accept_memory(
    user_id: str,
    memory_id: str,
    mem_service: MemoryService = Depends(get_memory_service),
    scheduler: MemoryMaintenanceScheduler | None = Depends(get_memory_maintenance_scheduler),
):
    try:
        memory = mem_service.update_review_status(user_id, memory_id, "accepted")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    _schedule_if_changed(scheduler, user_id, True)
    return _to_memory_response(memory)


@router.post("/{user_id}/{memory_id}/reject", response_model=MemoryItemResponse)
def reject_memory(
    user_id: str,
    memory_id: str,
    mem_service: MemoryService = Depends(get_memory_service),
    scheduler: MemoryMaintenanceScheduler | None = Depends(get_memory_maintenance_scheduler),
):
    try:
        memory = mem_service.update_review_status(user_id, memory_id, "rejected")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    _schedule_if_changed(scheduler, user_id, True)
    return _to_memory_response(memory)


@router.patch("/{user_id}/{memory_id}", response_model=MemoryItemResponse)
def edit_memory(
    user_id: str,
    memory_id: str,
    req: MemoryEditRequest,
    mem_service: MemoryService = Depends(get_memory_service),
    scheduler: MemoryMaintenanceScheduler | None = Depends(get_memory_maintenance_scheduler),
):
    try:
        memory = mem_service.edit_memory(
            user_id,
            memory_id,
            content=req.content,
            mem_type=req.mem_type,
            scope=req.scope,
            sensitivity=req.sensitivity,
            importance=req.importance,
            retrieval_enabled=req.retrieval_enabled,
            pinned=req.pinned,
            user_hidden=req.user_hidden,
            user_locked=req.user_locked,
            is_current=req.is_current,
            user_control_reason=req.user_control_reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    _schedule_if_changed(scheduler, user_id, True)
    return _to_memory_response(memory)


@router.delete("/{user_id}/{memory_id}")
def delete_memory(
    user_id: str,
    memory_id: str,
    mem_service: MemoryService = Depends(get_memory_service),
    scheduler: MemoryMaintenanceScheduler | None = Depends(get_memory_maintenance_scheduler),
):
    deleted = mem_service.delete_memory(user_id, memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    _schedule_if_changed(scheduler, user_id, True)
    return {"deleted": True}


def _schedule_if_changed(
    scheduler: MemoryMaintenanceScheduler | None,
    user_id: str,
    changed: bool,
) -> None:
    if changed and scheduler is not None:
        try:
            scheduler.schedule(user_id)
        except Exception:
            # Maintenance is best-effort post-processing. A queue-capacity or
            # shutdown race must not turn an already-applied memory mutation into
            # an ambiguous 5xx response.
            return
