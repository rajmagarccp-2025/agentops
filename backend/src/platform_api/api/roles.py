from typing import Any

from fastapi import APIRouter

from platform_api.identity_repository import ROLE_PERMISSIONS_MAP

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("")
async def list_roles() -> list[dict[str, Any]]:
    """Return available system roles and their assigned permission sets."""
    role_descriptions = {
        "ADMIN": "Full administrative control over Organization, Projects, Environments, and Member management.",
        "WRITE": "Read and Write access for operations, telemetry ingestion, actions, and AI queries. Cannot manage members.",
        "READ": "Strict read-only access across platform domains. Prohibited from mutating data or submitting AI queries.",
        "OWNER": "Organization owner with ownership transfer capabilities and full administrative control.",
    }
    return [
        {
            "name": role,
            "description": role_descriptions.get(role, f"{role} role"),
            "permissions": sorted(list(perms)),
        }
        for role, perms in ROLE_PERMISSIONS_MAP.items()
    ]
