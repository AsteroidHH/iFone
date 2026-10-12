import sys
from pathlib import Path

# Ensure repo root and backend are always in sys.path
_repo_root = str(Path(__file__).resolve().parent.parent.parent)
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import uuid
import time
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.models.common import ErrorCode, ErrorResponse, ErrorDetail
from app.routes import (
    meta,
    graph,
    events,
    scenario,
    blast,
    handoffs,
    actions,
    agents,
    procedures,
    prompt_diff,
    brain,
    system,
)

app = FastAPI(
    title="Quorum API",
    version=settings.CONTRACT_VERSION,
    description="Quorum Graph Memory & Multi-Agent Coordination Engine",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:8]}"
    request.state.request_id = req_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = req_id
    return response


# Standardized error responses matching docs/CONTRACT.md
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": ErrorCode.INTERNAL.value if exc.status_code == 500 else ErrorCode.VALIDATION.value,
                "message": str(exc.detail),
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": ErrorCode.VALIDATION.value,
                "message": "Invalid request parameters or payload.",
                "details": {"errors": exc.errors()},
            }
        },
    )


# Mount routes under /api
api_prefix = settings.API_PREFIX

app.include_router(meta.router, prefix=api_prefix, tags=["Meta"])
app.include_router(graph.router, prefix=api_prefix, tags=["Graph"])
app.include_router(events.router, prefix=api_prefix, tags=["Events"])
app.include_router(scenario.router, prefix=api_prefix, tags=["Scenario"])
app.include_router(blast.router, prefix=api_prefix, tags=["Blast"])
app.include_router(handoffs.router, prefix=api_prefix, tags=["Handoffs"])
app.include_router(actions.router, prefix=api_prefix, tags=["Actions"])
app.include_router(agents.router, prefix=api_prefix, tags=["Agents"])
app.include_router(procedures.router, prefix=api_prefix, tags=["Procedures"])
app.include_router(prompt_diff.router, prefix=api_prefix, tags=["Prompt Diff"])
app.include_router(brain.router, prefix=api_prefix, tags=["Company Brain"])
app.include_router(system.router, prefix=api_prefix, tags=["System & Benchmarks"])


@app.get("/")
def root():
    return {
        "service": "Quorum API",
        "version": settings.CONTRACT_VERSION,
        "docs": "/docs",
        "openapi": "/openapi.json",
    }
