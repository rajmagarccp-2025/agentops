from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from platform_api.identity_repository import EnvironmentRepository
from platform_api.security import Principal


def require_active_environment(
    db: Session,
    principal: Principal,
    confirmation: str | None = None,
    *,
    destructive: bool = False,
):
    if not principal.project_id or not principal.environment_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Select a project and environment before continuing.",
        )
    environment = EnvironmentRepository().get_environment_by_id(db, principal.environment_id)
    if (
        not environment
        or environment.tenant_id != principal.tenant_id
        or environment.project_id != principal.project_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    if destructive and environment.type == "Production" and confirmation != environment.slug:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail=(
                "Production changes require the X-Confirm-Production-Environment "
                "header to match the environment slug."
            ),
        )
    return environment
