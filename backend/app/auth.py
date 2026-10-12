from typing import Optional, List
from fastapi import Header, HTTPException, status, Depends
from pydantic import BaseModel
from app.config import settings
from app.models.common import ErrorCode, ErrorDetail, ErrorResponse


class AuthContext(BaseModel):
    tenant: str
    role: str  # "agent" | "auditor" | "human"
    agent_id: Optional[str] = None
    token: str

_ROLES = ("agent", "auditor", "human")


def resolve_token(token: str) -> Optional[dict]:
    """
    The single place that turns a bearer token into {tenant, role, agent_id}, for the API and for MCP tools alike.

    Configured tokens (demo tokens plus QUORUM_TOKENS_JSON) always work. Ad-hoc tokens shaped like token_<role> or
    token_<tenant>_<role> only work when QUORUM_ALLOW_DYNAMIC_TOKENS is on (the default outside production), because
    anyone could otherwise forge a token for any tenant.
    """
    if not token:
        return None
    if token in settings.DEMO_TOKENS:
        return dict(settings.DEMO_TOKENS[token])
    if not settings.dynamic_tokens_allowed():
        return None
    parts = token.split("_")
    if parts[0] != "token" or len(parts) < 2 or parts[-1] not in _ROLES:
        return None
    role = parts[-1]
    if len(parts) == 2:
        return {"tenant": settings.DEFAULT_TENANT, "role": role, "agent_id": f"{role}_demo"}
    tenant = "_".join(parts[1:-1])
    return {"tenant": tenant, "role": role, "agent_id": f"{role}_{tenant}"}


def get_auth_context(authorization: Optional[str] = Header(None)) -> AuthContext:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": ErrorCode.UNAUTHENTICATED.value,
                    "message": "Missing or invalid Bearer token in Authorization header.",
                }
            },
        )

    token = authorization.split("Bearer ", 1)[1].strip()
    info = resolve_token(token)
    if info:
        return AuthContext(tenant=info["tenant"], role=info["role"], agent_id=info.get("agent_id"), token=token)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": ErrorCode.UNAUTHENTICATED.value, "message": "Invalid token."}},
    )


def require_role(allowed_roles: List[str]):
    def role_checker(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if auth.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": ErrorCode.FORBIDDEN_ROLE.value,
                        "message": f"Role '{auth.role}' is not permitted to perform this action. Required: {allowed_roles}",
                    }
                },
            )
        return auth
    return role_checker
