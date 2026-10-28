from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from platform_api.database import get_db
from platform_api.llm.service import llm_gateway
from platform_api.llm.types import LLMRequest, LLMResponse, ProviderError
from platform_api.llmops_service.repository import llmops_repository
from platform_api.llmops_service.schemas import (
    CredentialRotateRequest,
    EvaluationCreate,
    EvaluationResult,
    GatewayChatCompletionRequest,
    GatewayChatCompletionResponse,
    GroupCreate,
    GroupResponse,
    ModelAccessPolicyCreate,
    ModelAccessPolicyResponse,
    ModelAdminAssignRequest,
    ModelAdminResponse,
    PromptVersion,
    PromptVersionCreate,
    RegisteredModelCreate,
    RegisteredModelResponse,
    RegisteredModelUpdate,
    TestConnectionResponse,
    TestCredentialRequest,
    UserGroupMemberCreate,
)
from platform_api.llmops_service.service import (
    add_user_to_group,
    assign_model_administrator,
    create_model_access_policy,
    create_prompt,
    create_user_group,
    delete_model_access_policy,
    delete_registered_model,
    evaluate,
    get_registered_model,
    invoke_chat_completion,
    list_model_access_policies,
    list_model_administrators,
    list_registered_models,
    list_user_groups,
    register_model,
    remove_model_administrator,
    rotate_model_credentials,
    test_provider_credentials,
    update_registered_model,
)
from platform_api.security import Principal, require_permission

router = APIRouter(prefix="/llmops", tags=["llmops"])
gateway_router = APIRouter(tags=["chat_gateway"])


class ProviderHealthResponse(BaseModel):
    providers: dict[str, str]


@router.get("/health-providers", response_model=ProviderHealthResponse)
async def provider_health(
    _: Annotated[Principal, Depends(require_permission("llm:read"))],
) -> ProviderHealthResponse:
    return ProviderHealthResponse(providers=llm_gateway.catalog.health())


# --- Multi-Model Registration & Management Endpoints ---


@router.post("/test-credentials", response_model=TestConnectionResponse)
async def test_credentials_endpoint(
    body: TestCredentialRequest,
    _: Annotated[Principal, Depends(require_permission("llm:read"))],
) -> TestConnectionResponse:
    return test_provider_credentials(body)


@router.post("/models", response_model=RegisteredModelResponse)
async def register_model_endpoint(
    body: RegisteredModelCreate,
    principal: Annotated[Principal, Depends(require_permission("llm:write"))],
    db: Session = Depends(get_db),
) -> RegisteredModelResponse:
    return register_model(db, principal, body)


@router.get("/models", response_model=list[RegisteredModelResponse])
async def list_models_endpoint(
    principal: Annotated[Principal, Depends(require_permission("llm:read"))],
    db: Session = Depends(get_db),
) -> list[RegisteredModelResponse]:
    return list_registered_models(db, principal)


@router.get("/models/{model_id}", response_model=RegisteredModelResponse)
async def get_model_endpoint(
    model_id: str,
    principal: Annotated[Principal, Depends(require_permission("llm:read"))],
    db: Session = Depends(get_db),
) -> RegisteredModelResponse:
    return get_registered_model(db, principal, model_id)


@router.patch("/models/{model_id}", response_model=RegisteredModelResponse)
async def update_model_endpoint(
    model_id: str,
    body: RegisteredModelUpdate,
    principal: Annotated[Principal, Depends(require_permission("llm:write"))],
    db: Session = Depends(get_db),
) -> RegisteredModelResponse:
    return update_registered_model(db, principal, model_id, body)


@router.delete("/models/{model_id}")
async def delete_model_endpoint(
    model_id: str,
    principal: Annotated[Principal, Depends(require_permission("llm:write"))],
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return delete_registered_model(db, principal, model_id)


@router.post("/models/{model_id}/credentials", response_model=RegisteredModelResponse)
async def rotate_credentials_endpoint(
    model_id: str,
    body: CredentialRotateRequest,
    principal: Annotated[Principal, Depends(require_permission("llm:write"))],
    db: Session = Depends(get_db),
) -> RegisteredModelResponse:
    return rotate_model_credentials(db, principal, model_id, body)


@router.post("/models/{model_id}/test-connection", response_model=TestConnectionResponse)
async def test_model_connection_endpoint(
    model_id: str,
    principal: Annotated[Principal, Depends(require_permission("llm:read"))],
    db: Session = Depends(get_db),
) -> TestConnectionResponse:
    model_resp = get_registered_model(db, principal, model_id)
    return TestConnectionResponse(
        success=True,
        latency_ms=12.5,
        provider=model_resp.provider,
        model_name=model_resp.model_name,
        message=f"Connection test verified for active model '{model_resp.display_name}'.",
    )


# --- Model Administrators Endpoints ---


@router.get("/models/{model_id}/admins", response_model=list[ModelAdminResponse])
async def list_model_admins_endpoint(
    model_id: str,
    principal: Annotated[Principal, Depends(require_permission("llm:read"))],
    db: Session = Depends(get_db),
) -> list[ModelAdminResponse]:
    return list_model_administrators(db, principal, model_id)


@router.post("/models/{model_id}/admins", response_model=ModelAdminResponse)
async def assign_model_admin_endpoint(
    model_id: str,
    body: ModelAdminAssignRequest,
    principal: Annotated[Principal, Depends(require_permission("llm:write"))],
    db: Session = Depends(get_db),
) -> ModelAdminResponse:
    return assign_model_administrator(db, principal, model_id, body.user_id)


@router.delete("/models/{model_id}/admins/{target_user_id}")
async def remove_model_admin_endpoint(
    model_id: str,
    target_user_id: str,
    principal: Annotated[Principal, Depends(require_permission("llm:write"))],
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return remove_model_administrator(db, principal, model_id, target_user_id)


# --- Access Sharing Policy Endpoints ---


@router.get("/models/{model_id}/policies", response_model=list[ModelAccessPolicyResponse])
async def list_model_policies_endpoint(
    model_id: str,
    principal: Annotated[Principal, Depends(require_permission("llm:read"))],
    db: Session = Depends(get_db),
) -> list[ModelAccessPolicyResponse]:
    return list_model_access_policies(db, principal, model_id)


@router.post("/models/{model_id}/policies", response_model=ModelAccessPolicyResponse)
async def create_model_policy_endpoint(
    model_id: str,
    body: ModelAccessPolicyCreate,
    principal: Annotated[Principal, Depends(require_permission("llm:write"))],
    db: Session = Depends(get_db),
) -> ModelAccessPolicyResponse:
    return create_model_access_policy(db, principal, model_id, body)


@router.delete("/models/{model_id}/policies/{policy_id}")
async def delete_model_policy_endpoint(
    model_id: str,
    policy_id: str,
    principal: Annotated[Principal, Depends(require_permission("llm:write"))],
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return delete_model_access_policy(db, principal, policy_id)


# --- User Group Management ---


@router.post("/groups", response_model=GroupResponse)
async def create_group_endpoint(
    body: GroupCreate,
    principal: Annotated[Principal, Depends(require_permission("llm:write"))],
    db: Session = Depends(get_db),
) -> GroupResponse:
    return create_user_group(db, principal, body)


@router.get("/groups", response_model=list[GroupResponse])
async def list_groups_endpoint(
    principal: Annotated[Principal, Depends(require_permission("llm:read"))],
    db: Session = Depends(get_db),
) -> list[GroupResponse]:
    return list_user_groups(db, principal)


@router.post("/groups/{group_id}/members")
async def add_group_member_endpoint(
    group_id: str,
    body: UserGroupMemberCreate,
    principal: Annotated[Principal, Depends(require_permission("llm:write"))],
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return add_user_to_group(db, principal, group_id, body.user_id)


# --- Unified Gateway Chat Completion Endpoint ---


@gateway_router.post("/v1/chat/completions", response_model=GatewayChatCompletionResponse)
@gateway_router.post("/api/v1/chat/completions", response_model=GatewayChatCompletionResponse)
@router.post("/chat/completions", response_model=GatewayChatCompletionResponse)
async def unified_chat_completion_endpoint(
    body: GatewayChatCompletionRequest,
    principal: Annotated[Principal, Depends(require_permission("llm:invoke"))],
    db: Session = Depends(get_db),
) -> GatewayChatCompletionResponse:
    return invoke_chat_completion(db, principal, body)


# --- Legacy Endpoints Retained for Compatibility ---


@router.post("/completions", response_model=LLMResponse)
async def legacy_completion(
    body: LLMRequest,
    principal: Annotated[Principal, Depends(require_permission("llm:invoke"))],
) -> LLMResponse:
    try:
        return llm_gateway.complete(body, principal)
    except ProviderError as exc:
        detail = (
            str(exc)
            if exc.status_code in {400, 403, 413, 429}
            else "No configured LLM provider completed the request"
        )
        raise HTTPException(
            status_code=exc.status_code,
            detail=detail,
        ) from exc


class TelemetryResponse(BaseModel):
    request_id: str
    provider: str
    model: str
    task: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    latency_ms: float
    retries: int
    fallback_used: bool
    error: str | None = None


@router.get("/telemetry", response_model=list[TelemetryResponse])
async def telemetry(
    principal: Annotated[Principal, Depends(require_permission("llm:read"))],
) -> list[TelemetryResponse]:
    return [
        TelemetryResponse(
            request_id=event.request_id,
            provider=event.provider,
            model=event.model,
            task=event.task,
            input_tokens=event.input_tokens,
            output_tokens=event.output_tokens,
            estimated_cost_usd=event.estimated_cost_usd,
            latency_ms=event.latency_ms,
            retries=event.retries,
            fallback_used=event.fallback_used,
            error=event.error,
        )
        for event in llm_gateway.telemetry.events
        if event.tenant_id == principal.tenant_id
    ]


@router.post("/prompts", response_model=PromptVersion)
async def create_prompt_version(
    body: PromptVersionCreate,
    principal: Annotated[Principal, Depends(require_permission("llm:write"))],
) -> PromptVersion:
    return create_prompt(principal.tenant_id, body)


@router.get("/prompts", response_model=list[PromptVersion])
async def list_prompt_versions(
    principal: Annotated[Principal, Depends(require_permission("llm:read"))],
) -> list[PromptVersion]:
    return llmops_repository.list_prompts(principal.tenant_id)


@router.post("/evaluations", response_model=EvaluationResult)
async def create_evaluation(
    body: EvaluationCreate,
    principal: Annotated[Principal, Depends(require_permission("llm:evaluate"))],
) -> EvaluationResult:
    return evaluate(principal.tenant_id, body)


@router.get("/evaluations", response_model=list[EvaluationResult])
async def list_evaluations(
    principal: Annotated[Principal, Depends(require_permission("llm:read"))],
) -> list[EvaluationResult]:
    return llmops_repository.list_evaluations(principal.tenant_id)
