"""Tokens: configured ones work, forged ones do not (in production), and garbage never becomes a human."""
import pytest
from fastapi.testclient import TestClient

from app.auth import resolve_token
from app.config import settings
from app.main import app
from app.services import mcp_tools


def test_garbage_token_is_not_a_human_anymore():
    with TestClient(app) as c:
        assert c.get("/api/meta", headers={"Authorization": "Bearer nonsense"}).status_code == 401
        assert c.get("/api/meta", headers={"Authorization": "Bearer token_x_wizard"}).status_code == 401


def test_configured_tokens_work():
    assert resolve_token("token_human")["role"] == "human"
    assert resolve_token("token_agent_scout")["tenant"] == "acme"


def test_dynamic_tokens_are_refused_in_production(monkeypatch):
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "ALLOW_DYNAMIC_TOKENS", None)
    assert resolve_token("token_globex_auditor") is None
    assert resolve_token("token_auditor") is not None  # a configured demo token, still valid
    with TestClient(app) as c:
        assert c.get("/api/meta", headers={"Authorization": "Bearer token_globex_auditor"}).status_code == 401


def test_dynamic_tokens_work_in_development(monkeypatch):
    monkeypatch.setattr(settings, "ENV", "development")
    monkeypatch.setattr(settings, "ALLOW_DYNAMIC_TOKENS", None)
    assert resolve_token("token_globex_auditor") == {"tenant": "globex", "role": "auditor", "agent_id": "auditor_globex"}


def test_mcp_tool_rejects_a_bad_token():
    out = mcp_tools.guarded(mcp_tools.retrieve_context)("anything", "not-a-token")
    assert out["success"] is False and "token" in out["error"].lower()


def test_cors_is_not_wildcard():
    assert "*" not in settings.cors_origin_list()


def test_demo_tokens_are_not_valid_in_production_when_tokens_are_configured(monkeypatch):
    import importlib
    import app.config as cfg

    monkeypatch.setenv("QUORUM_ENV", "production")
    monkeypatch.setenv("QUORUM_TOKENS_JSON", '{"real-token-1": {"tenant": "acme", "role": "human", "agent_id": "ops"}}')
    fresh = importlib.reload(cfg)
    try:
        assert fresh.settings.DEMO_TOKENS == {"real-token-1": {"tenant": "acme", "role": "human", "agent_id": "ops"}}
        assert "token_human" not in fresh.settings.DEMO_TOKENS
    finally:
        monkeypatch.delenv("QUORUM_ENV")
        monkeypatch.delenv("QUORUM_TOKENS_JSON")
        importlib.reload(cfg)
