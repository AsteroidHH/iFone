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

    # Match demo/static tokens first
    if token in settings.DEMO_TOKENS:
        info = settings.DEMO_TOKENS[token]
        return AuthContext(
            tenant=info["tenant"],
            role=info["role"],
            agent_id=info.get("agent_id"),
            token=token,
        )

    # Simple token heuristic for dynamic tokens (e.g. token_tenant_role)
    parts = token.split("_")
    if len(parts) >= 2 and parts[0] == "token":
        # format: token_<role> or token_<tenant>_<role>
        if len(parts) == 2:
            role = parts[1]
            if role in ["agent", "auditor", "human"]:
                return AuthContext(
                    tenant=settings.DEFAULT_TENANT,
                    role=role,
                    agent_id=f"{role}_demo",
                    token=token,
                )
        elif len(parts) >= 3:
            role = parts[-1]
            tenant = "_".join(parts[1:-1])
            if role in ["agent", "auditor", "human"]:
                return AuthContext(
                    tenant=tenant,
                    role=role,
                    agent_id=f"{role}_{tenant}",
                    token=token,
                )

    # In debug/demo mode, accept fallback default
    if settings.DEBUG:
        return AuthContext(
            tenant=settings.DEFAULT_TENANT,
            role="human",
            agent_id="human_dev",
            token=token,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": {
                "code": ErrorCode.UNAUTHENTICATED.value,
                "message": "Invalid token.",
            }
        },
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
