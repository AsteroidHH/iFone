from typing import List
from fastapi import APIRouter, Depends
from app.auth import get_auth_context, AuthContext
from app.models.agents import ProcedureItem
from app.services.fixtures import get_fixture_procedures

router = APIRouter()


@router.get("/procedures", response_model=List[ProcedureItem])
def list_procedures(auth: AuthContext = Depends(get_auth_context)):
    return get_fixture_procedures()
