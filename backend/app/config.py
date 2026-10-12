import os
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Any, Literal

logger = logging.getLogger("quorum.config")


class Settings(BaseSettings):
    CONTRACT_VERSION: str = "0.1.0"
    API_PREFIX: str = "/api"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    MCP_PORT: int = 8001
    DEBUG: bool = True
    MODE: Literal["replay", "live"] = "replay"
    REPLAY_AVAILABLE: bool = True
    DEFAULT_TENANT: str = "acme"
    FALKORDB_URL: str = "redis://localhost:6379"

    # Static tokens for local dev and demo UI
    DEMO_TOKENS: Dict[str, Dict[str, Any]] = {
        "token_agent_scout": {"tenant": "acme", "role": "agent", "agent_id": "agent_scout"},
        "token_agent_refunder": {"tenant": "acme", "role": "agent", "agent_id": "agent_refunder"},
        "token_agent_analyst": {"tenant": "acme", "role": "agent", "agent_id": "agent_analyst"},
        "token_agent_comms": {"tenant": "acme", "role": "agent", "agent_id": "agent_comms"},
        "token_auditor": {"tenant": "acme", "role": "auditor", "agent_id": "auditor"},
        "token_human": {"tenant": "acme", "role": "human", "agent_id": "human_reviewer"},
        "token_globex_agent": {"tenant": "globex", "role": "agent", "agent_id": "globex_scout"},
    }

    model_config = SettingsConfigDict(env_prefix="QUORUM_")

    def get_effective_mode(self) -> Literal["replay", "live"]:
        requested = self.MODE
        if requested == "live":
            has_key = any(os.getenv(k) for k in ["GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"])
            if not has_key:
                logger.info("QUORUM_MODE is 'live' but no LLM API key detected. Gracefully falling back to 'replay' mode.")
                return "replay"
            return "live"
        return "replay"


settings = Settings()
