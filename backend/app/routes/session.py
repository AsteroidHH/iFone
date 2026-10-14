from fastapi import APIRouter, Depends, HTTPException

from app.auth import AuthContext, get_auth_context
from app.config import settings

router = APIRouter()


@router.get("/whoami")
def whoami(auth: AuthContext = Depends(get_auth_context)):
    """Who a token is. The console signs people in with this: paste a token, learn the tenant and role, or get 401."""
    return {"tenant": auth.tenant, "role": auth.role, "agent_id": auth.agent_id, "member_id": auth.member_id, "team_id": auth.team_id}


@router.get("/roles")
def role_guide(auth: AuthContext = Depends(get_auth_context)):
    """What each permission level can do, in plain words. The Team page shows this and lets an admin change a member's level."""
    from app.services import roles

    return roles.catalog()


@router.get("/dev-config")
def dev_config():
    """The built-in demo tokens, for the console in a local demo. It exists only when QUORUM_ENV=development."""
    if settings.ENV != "development":
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Not available outside development."}})
    tokens: dict = {}
    for tok, info in settings.DEMO_TOKENS.items():
        tokens.setdefault(info["tenant"], {})
        tokens[info["tenant"]].setdefault(info["role"], tok)
    return {"tokens": tokens, "tenants": list(tokens)}
