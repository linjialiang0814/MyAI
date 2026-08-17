from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.dependencies import get_knowledge_service
from app.knowledge.service import KnowledgeService
from app.schemas.knowledge_file_response import KnowledgeFileResponse
from app.schemas.knowledge_maintenance_request import KnowledgeMaintenanceRequest
from app.schemas.knowledge_maintenance_response import KnowledgeMaintenanceResponse
from app.schemas.knowledge_qa_request import KnowledgeQARequest
from app.schemas.knowledge_qa_response import KnowledgeQAResponse
from app.schemas.knowledge_query_request import KnowledgeQueryRequest
from app.schemas.knowledge_query_response import KnowledgeQueryResponse

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/upload", response_model=KnowledgeFileResponse)
async def upload_knowledge(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    suffix = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if suffix not in {"txt", "pdf", "docx"}:
        raise HTTPException(status_code=400, detail="Only txt, pdf, and docx files are supported")

    content = await file.read()
    try:
        result = knowledge_service.upload_file(user_id=user_id, filename=file.filename, content=content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return KnowledgeFileResponse(**result)


@router.post("/query", response_model=KnowledgeQueryResponse)
def query_knowledge(
    request: KnowledgeQueryRequest,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    hits = knowledge_service.query(
        request.user_id,
        request.query,
        top_k=request.top_k,
        file_id=request.file_id,
        retrieval_strategy=request.retrieval_strategy,
    )
    return KnowledgeQueryResponse(hits=hits)


@router.post("/qa", response_model=KnowledgeQAResponse)
def answer_document_question(
    request: KnowledgeQARequest,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    try:
        result = knowledge_service.answer_document_question(
            request.user_id,
            request.file_id,
            request.question,
            top_k=request.top_k,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return KnowledgeQAResponse(**result)


@router.post("/maintenance", response_model=KnowledgeMaintenanceResponse)
def maintain_knowledge(
    request: KnowledgeMaintenanceRequest,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    try:
        result = knowledge_service.maintain(
            request.user_id,
            dry_run=request.dry_run,
            file_id=request.file_id,
            rebuild=request.rebuild,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return KnowledgeMaintenanceResponse(**result)


@router.get("/files/{user_id}", response_model=List[KnowledgeFileResponse])
def list_knowledge_files(user_id: str, knowledge_service: KnowledgeService = Depends(get_knowledge_service)):
    files = knowledge_service.list_files(user_id)
    return [KnowledgeFileResponse(**item) for item in files]


@router.delete("/files/{user_id}/{file_id}")
def delete_knowledge_file(
    user_id: str,
    file_id: str,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
):
    deleted = knowledge_service.delete_file(user_id, file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Knowledge file not found")
    return {"deleted": True}
