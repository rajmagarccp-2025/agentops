from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from platform_api.config import get_settings
from platform_api.identity_repository import ROLE_PERMISSIONS_MAP


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: str
    roles: frozenset[str]
    permissions: frozenset[str]
    # Enhanced trusted principal fields required for OIDC / Keycloak & gateway integration:
    subject_id: str | None = None
    email: str | None = None
    display_name: str | None = None
    tenant_memberships: tuple[dict[str, Any], ...] = ()
    issuer: str | None = None
    audience: str | tuple[str, ...] | None = None
    authentication_context: dict[str, Any] | None = None
    session_id: str | None = None
    project_id: str | None = None
    environment_id: str | None = None
    is_owner: bool = False
    read_only_demo: bool = False
    email_verified: bool = False

    def __post_init__(self):
        # Default subject_id to subject if not explicitly supplied
        if self.subject_id is None:
            object.__setattr__(self, "subject_id", self.subject)


bearer_scheme = HTTPBearer(auto_error=False)


def _canonical_permission(p: str) -> str:
    """Map dot and colon notations bidirectionally to ensure full compatibility."""
    return p.strip()


# Cached PyJWKClients for OIDC certificate endpoints
_jwks_clients: dict[str, jwt.PyJWKClient] = {}


def _get_jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    if jwks_url not in _jwks_clients:
        _jwks_clients[jwks_url] = jwt.PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)
    return _jwks_clients[jwks_url]


def _decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()

    # If unverified header indicates RS256 or Keycloak public key configured, attempt RSA decoding
    try:
        unverified_header = jwt.get_unverified_header(token)
    except Exception:
        unverified_header = {}

    alg = unverified_header.get("alg", settings.jwt_algorithm)

    # 1. If RS256, verify cryptographic signature via configured public key or Keycloak JWKS
    if alg == "RS256":
        allowed_issuers = [
            iss
            for iss in [
                settings.oidc_issuer_url,
                "http://localhost:8080/realms/agentops",
                "http://keycloak:8080/realms/agentops",
                "http://localhost:8080/realms/platform",
                "http://keycloak:8080/realms/platform",
                settings.jwt_issuer,
            ]
            if iss
        ]

        expected_audiences = [
            aud
            for aud in [
                settings.oidc_audience,
                settings.jwt_audience,
                "agentops-api",
                "agentic-platform-api",
            ]
            if aud
        ]

        # Check static public key first if provided
        if settings.oidc_public_key:
            try:
                return jwt.decode(
                    token,
                    settings.oidc_public_key,
                    algorithms=["RS256"],
                    audience=expected_audiences,
                    issuer=allowed_issuers,
                )
            except jwt.PyJWTError as exc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid or expired OIDC access token: {exc}",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from exc

        # Dynamic JWKS certificate retrieval from Keycloak
        candidate_jwks_urls = [
            "http://keycloak:8080/realms/agentops/protocol/openid-connect/certs",
            "http://localhost:8080/realms/agentops/protocol/openid-connect/certs",
            "http://keycloak:8080/realms/platform/protocol/openid-connect/certs",
            "http://localhost:8080/realms/platform/protocol/openid-connect/certs",
        ]
        if settings.oidc_issuer_url:
            base_url = settings.oidc_issuer_url.rstrip("/")
            candidate_jwks_urls.insert(0, f"{base_url}/protocol/openid-connect/certs")

        last_error = None
        for jwks_url in candidate_jwks_urls:
            try:
                client = _get_jwks_client(jwks_url)
                signing_key = client.get_signing_key_from_jwt(token)
                return jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256"],
                    audience=expected_audiences,
                    issuer=allowed_issuers,
                )
            except Exception as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Invalid or expired OIDC access token: "
                    f"{last_error}"
                ),
                headers={"WWW-Authenticate": "Bearer"},
            ) from last_error

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OIDC access token: Keycloak JWKS resolution failed",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    # 2. Otherwise default to configured jwt_demo_secret (HS256)
    try:
        return jwt.decode(
            token,
            settings.jwt_demo_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _build_principal_from_claims(claims: dict[str, Any], require_tenant: bool = True) -> Principal:
    subject = claims.get("sub") or claims.get("subject_id")
    tenant_id = claims.get("tenant_id")
    email = claims.get("email") or claims.get("preferred_username")
    display_name = claims.get("name") or claims.get("display_name") or subject

    # Tenant memberships claim parsing
    raw_memberships = claims.get("tenant_memberships")
    memberships: list[dict[str, Any]] = []
    if isinstance(raw_memberships, list):
        for m in raw_memberships:
            if isinstance(m, dict):
                memberships.append(m)

    # If tenant_id was not explicitly in claims but tenant_memberships exists, pick first
    if not tenant_id and memberships:
        tenant_id = memberships[0].get("tenant_id")

    # Extract roles:
    # 1. Top-level 'roles' claim
    roles_list = _string_values(claims.get("roles"))
    # 2. Keycloak realm roles ('realm_access.roles')
    if isinstance(claims.get("realm_access"), dict):
        roles_list.extend(_string_values(claims["realm_access"].get("roles")))
    # 3. Keycloak client/resource roles ('resource_access.<client>.roles')
    if isinstance(claims.get("resource_access"), dict):
        for res_data in claims["resource_access"].values():
            if isinstance(res_data, dict):
                roles_list.extend(_string_values(res_data.get("roles")))
    # 4. Extract roles mapped to active tenant from tenant_memberships if not already populated
    if not roles_list:
        for m in memberships:
            if m.get("tenant_id") == tenant_id and "roles" in m:
                roles_list.extend(_string_values(m["roles"]))

    # Deduplicate roles preserving order
    roles_list = list(dict.fromkeys(roles_list))

    if tenant_id and not memberships:
        memberships.append({"tenant_id": tenant_id, "roles": list(roles_list)})

    # Keycloak scopes/permissions
    perms_list = _string_values(claims.get("permissions"))
    scope_str = claims.get("scope")
    if isinstance(scope_str, str):
        perms_list.extend(scope_str.split())

    # Merge permissions implied by roles (ADMIN, WRITE, READ, OWNER)
    for r in roles_list:
        r_upper = r.upper()
        if r_upper in ROLE_PERMISSIONS_MAP:
            perms_list.extend(ROLE_PERMISSIONS_MAP[r_upper])

    # Map permissions canonically between dot and colon notations (e.g. inventory.read <-> inventory:read)
    canonical_perms = set(perms_list)
    for p in perms_list:
        if "." in p:
            canonical_perms.add(p.replace(".", ":"))
        elif ":" in p:
            canonical_perms.add(p.replace(":", "."))

    if not isinstance(subject, str) or not subject.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject missing",
        )

    if require_tenant and (not isinstance(tenant_id, str) or not tenant_id.strip()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token lacks tenant context",
        )

    resolved_tenant = tenant_id if isinstance(tenant_id, str) else ""
    is_owner = bool(claims.get("is_owner", False)) or ("OWNER" in [r.upper() for r in roles_list])

    return Principal(
        subject=subject,
        subject_id=subject,
        tenant_id=resolved_tenant,
        email=email,
        display_name=display_name,
        tenant_memberships=tuple(memberships),
        roles=frozenset(roles_list),
        permissions=frozenset(canonical_perms),
        issuer=claims.get("iss"),
        audience=claims.get("aud"),
        authentication_context={
            "auth_time": claims.get("auth_time"),
            "token_use": claims.get("token_use", "access_token"),
            "acr": claims.get("acr"),
            "client_id": claims.get("azp") or claims.get("client_id"),
        },
        session_id=claims.get("sid") or claims.get("session_id") or claims.get("jti"),
        project_id=claims.get("project_id"),
        environment_id=claims.get("environment_id"),
        is_owner=is_owner,
        read_only_demo=claims.get("read_only_demo") is True,
        email_verified=claims.get("email_verified") is True,
    )


def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Principal:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer access token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = _decode_token(credentials.credentials)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return _build_principal_from_claims(claims, require_tenant=True)


def get_optional_tenant_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Principal:
    """Authenticates the token without requiring active tenant membership. Used for onboarding."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer access token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = _decode_token(credentials.credentials)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return _build_principal_from_claims(claims, require_tenant=False)


def require_permission(permission: str):
    def dependency(principal: Annotated[Principal, Depends(get_current_principal)]) -> Principal:
        # Check permission as well as dotted / coloned variants and platform admin bypass
        alt_permission = (
            permission.replace(".", ":") if "." in permission else permission.replace(":", ".")
        )
        has_perm = (
            permission in principal.permissions
            or alt_permission in principal.permissions
            or "platform:admin" in principal.permissions
            or "platform.admin" in principal.permissions
            or "platform-admin" in principal.roles
        )
        if not has_perm:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return principal

    return dependency


def require_role(role: str):
    def dependency(principal: Annotated[Principal, Depends(get_current_principal)]) -> Principal:
        normalized_roles = {r.upper() for r in principal.roles}
        target_role = role.upper()
        role_aliases = {
            "ADMIN": {"ADMIN", "OWNER"},
            "OWNER": {"OWNER"},
            "DEVELOPER": {"DEVELOPER", "WRITE", "OPERATOR", "MEMBER"},
            "WRITE": {"WRITE", "OPERATOR", "MEMBER", "DEVELOPER"},
            "READER": {"READER", "READ", "VIEWER"},
            "READ": {"READ", "VIEWER", "READER"},
        }
        matched_roles = role_aliases.get(target_role, {target_role})
        if not (normalized_roles & matched_roles or "PLATFORM-ADMIN" in normalized_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role forbidden")
        return principal

    return dependency


def verify_tenant_scope(principal: Principal, target_tenant_id: str) -> None:
    """Enforce that operations on a resource strictly match the authenticated principal's server-side tenant memberships."""
    # 1. Primary tenant check
    if principal.tenant_id == target_tenant_id:
        return

    # 2. Server-side tenant memberships check
    member_tenants = {
        m["tenant_id"]
        for m in principal.tenant_memberships
        if isinstance(m, dict) and "tenant_id" in m
    }
    if target_tenant_id not in member_tenants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant context mismatch: cross-tenant access is forbidden",
        )


def issue_demo_token(
    subject: str = "demo-user",
    tenant_id: str = "demo-tenant",
    roles: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
    issuer: str | None = None,
    audience: str | None = None,
    email: str | None = None,
    read_only_demo: bool = False,
    email_verified: bool = False,
    project_id: str | None = None,
    environment_id: str | None = None,
) -> str:
    settings = get_settings()
    if not settings.demo_mode:
        raise RuntimeError("Demo token issuance is disabled")
    now = datetime.now(UTC)
    claims = {
        "sub": subject,
        "tenant_id": tenant_id,
        "roles": list(roles),
        "permissions": list(permissions),
        "email": email or f"{subject}@enterprise.com",
        "email_verified": email_verified,
        "read_only_demo": read_only_demo,
        "iss": issuer or settings.jwt_issuer,
        "aud": audience or settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_demo_token_minutes),
    }
    if project_id:
        claims["project_id"] = project_id
    if environment_id:
        claims["environment_id"] = environment_id
    return jwt.encode(
        claims,
        settings.jwt_demo_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def issue_user_token(
    subject: str,
    email: str,
    tenant_id: str = "",
    roles: tuple[str, ...] | list[str] = (),
    permissions: tuple[str, ...] | list[str] = (),
    tenant_memberships: list[dict[str, Any]] | None = None,
    project_id: str | None = None,
    environment_id: str | None = None,
    display_name: str | None = None,
    is_owner: bool = False,
    expires_minutes: int | None = None,
    read_only_demo: bool = False,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    exp_mins = expires_minutes or settings.jwt_demo_token_minutes
    claims: dict[str, Any] = {
        "sub": subject,
        "email": email,
        "name": display_name or subject,
        "tenant_id": tenant_id,
        "roles": list(roles),
        "permissions": list(permissions),
        "tenant_memberships": tenant_memberships or [],
        "is_owner": is_owner,
        "read_only_demo": read_only_demo,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=exp_mins),
    }
    if project_id:
        claims["project_id"] = project_id
    if environment_id:
        claims["environment_id"] = environment_id
    return jwt.encode(
        claims,
        settings.jwt_demo_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def _string_values(value: object) -> list[str]:
    if not isinstance(value, list | tuple | set):
        return []
    return [item for item in value if isinstance(item, str)]
