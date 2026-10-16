from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from platform_api.database import get_db
from platform_api.environment_safety import require_active_environment
from platform_api.identity_repository import (
    AuditLogRepository,
    EnvironmentRepository,
    ProjectRepository,
)
from platform_api.rag_service.schemas import (
    DocumentCreate,
    DocumentRecord,
    DocumentScopeUpdate,
    DocumentShareCreate,
    DocumentShareRecord,
    DocumentType,
    RetrievalResult,
)
from platform_api.rag_service.service import (
    assign_document_scope,
    delete_document,
    ingest_document,
    list_document_shares,
    repository,
    retrieve,
    revoke_document_share,
    share_document,
)
from platform_api.security import Principal, require_permission

router = APIRouter(prefix="/rag", tags=["rag"])


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10_000)
    limit: int = Field(default=5, ge=1, le=20)
    document_type: DocumentType | None = None
    service: str | None = None
    environment: str | None = None
    tags: list[str] | None = None
    include_stale: bool = True


@router.post("/documents", response_model=DocumentRecord)
async def ingest(
    body: DocumentCreate,
    principal: Annotated[Principal, Depends(require_permission("rag:write"))],
) -> DocumentRecord:
    if not principal.project_id or not principal.environment_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Select a project and environment before adding knowledge.",
        )
    if body.scope == "project":
        body.environment = None
    return ingest_document(
        principal.tenant_id,
        body,
        project_id=principal.project_id,
        environment_id=principal.environment_id,
    )


@router.get("/documents", response_model=list[DocumentRecord])
async def list_documents(
    principal: Annotated[Principal, Depends(require_permission("rag:read"))],
) -> list[DocumentRecord]:
    if not principal.project_id or not principal.environment_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Select a project and environment before viewing scoped knowledge.",
        )
    return repository.list_documents(
        principal.tenant_id, principal.project_id, principal.environment_id
    )


@router.patch("/documents/{document_id}/scope", response_model=DocumentRecord)
async def set_document_scope(
    document_id: str,
    body: DocumentScopeUpdate,
    principal: Annotated[Principal, Depends(require_permission("rag:write"))],
) -> DocumentRecord:
    if not principal.project_id or not principal.environment_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Select a project and environment before assigning a knowledge scope.",
        )
    document = assign_document_scope(
        principal.tenant_id,
        document_id,
        principal.project_id,
        principal.environment_id if body.scope == "environment" else None,
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_document(
    document_id: str,
    principal: Annotated[Principal, Depends(require_permission("rag:write"))],
    db: Annotated[Session, Depends(get_db)],
    confirm_production_environment: Annotated[
        str | None,
        Header(alias="X-Confirm-Production-Environment"),
    ] = None,
) -> None:
    environment = require_active_environment(
        db,
        principal,
        confirm_production_environment,
        destructive=True,
    )
    document = repository.get_document(principal.tenant_id, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if not delete_document(
        principal.tenant_id,
        document_id,
        environment.project_id,
        environment.id,
        db,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    AuditLogRepository().record_event(
        db,
        actor=principal.subject,
        actor_email=principal.email,
        action="rag.document.deleted",
        resource_type="rag_document",
        resource_id=document_id,
        organization_id=principal.tenant_id,
        project_id=principal.project_id,
        environment_id=environment.id,
        details={
            "title": document.title,
            "scope": document.scope,
            "production_confirmation": environment.type == "Production",
        },
    )
    db.commit()


@router.post("/retrieve", response_model=RetrievalResult)
async def retrieve_context(
    body: RetrievalRequest,
    principal: Annotated[Principal, Depends(require_permission("rag:read"))],
) -> RetrievalResult:
    if not principal.project_id or not principal.environment_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Select a project and environment before searching scoped knowledge.",
        )
    return retrieve(
        tenant_id=principal.tenant_id,
        roles=principal.roles,
        query=body.query,
        limit=body.limit,
        document_type=body.document_type,
        service=body.service,
        environment=body.environment,
        project_id=principal.project_id,
        environment_id=principal.environment_id,
        tags=body.tags,
        include_stale=body.include_stale,
    )


@router.post(
    "/documents/{document_id}/shares",
    response_model=DocumentShareRecord,
    status_code=status.HTTP_201_CREATED,
)
async def share_document_endpoint(
    document_id: str,
    body: DocumentShareCreate,
    principal: Annotated[Principal, Depends(require_permission("rag:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> DocumentShareRecord:
    document = repository.get_document(principal.tenant_id, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Validate target project belongs to the owning organization
    target_project = ProjectRepository().get_project_by_id(db, body.target_project_id)
    if not target_project or target_project.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Target project does not belong to your organization. "
                "Cross-organization sharing is forbidden."
            ),
        )

    # If target environment specified, validate it belongs to target project and organization
    if body.target_environment_id:
        target_env = EnvironmentRepository().get_environment_by_id(db, body.target_environment_id)
        if (
            not target_env
            or target_env.project_id != body.target_project_id
            or target_env.tenant_id != principal.tenant_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target environment not found in specified target project.",
            )

    share = share_document(
        tenant_id=principal.tenant_id,
        document_id=document_id,
        target_project_id=body.target_project_id,
        target_environment_id=body.target_environment_id,
        shared_by=principal.subject,
    )

    AuditLogRepository().record_event(
        db,
        actor=principal.subject,
        actor_email=principal.email,
        action="rag.document.shared",
        resource_type="rag_document",
        resource_id=document_id,
        organization_id=principal.tenant_id,
        project_id=principal.project_id,
        environment_id=principal.environment_id,
        details={
            "document_id": document_id,
            "target_project_id": body.target_project_id,
            "target_environment_id": body.target_environment_id,
        },
    )
    db.commit()
    return share


@router.get("/documents/{document_id}/shares", response_model=list[DocumentShareRecord])
async def list_document_shares_endpoint(
    document_id: str,
    principal: Annotated[Principal, Depends(require_permission("rag:read"))],
) -> list[DocumentShareRecord]:
    document = repository.get_document(principal.tenant_id, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return list_document_shares(principal.tenant_id, document_id)


@router.delete("/documents/{document_id}/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_document_share_endpoint(
    document_id: str,
    share_id: str,
    principal: Annotated[Principal, Depends(require_permission("rag:write"))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    document = repository.get_document(principal.tenant_id, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    revoked = revoke_document_share(principal.tenant_id, document_id, share_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share grant not found")

    AuditLogRepository().record_event(
        db,
        actor=principal.subject,
        actor_email=principal.email,
        action="rag.document.share_revoked",
        resource_type="rag_document",
        resource_id=document_id,
        organization_id=principal.tenant_id,
        project_id=principal.project_id,
        environment_id=principal.environment_id,
        details={"share_id": share_id},
    )
    db.commit()
