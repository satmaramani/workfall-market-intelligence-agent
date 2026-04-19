from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

SERVICE_NAME = os.getenv("SERVICE_NAME", "market-intelligence-agent")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8003"))
A2A_SHARED_TOKEN = os.getenv("A2A_SHARED_TOKEN", "")
API_SHARED_TOKEN = os.getenv("API_SHARED_TOKEN", "local-dev-ui-token")
INVENTORY_BASE_URL = os.getenv("INVENTORY_BASE_URL", "http://localhost:8001")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://workfall:workfall@localhost:5432/workfall_multi_agent",
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MARKET_MODEL = os.getenv("OPENAI_MARKET_MODEL", "gpt-5-mini")
OPENAI_MARKET_REASONING_EFFORT = os.getenv("OPENAI_MARKET_REASONING_EFFORT", "low")
OPENAI_WEB_SEARCH_ENABLED = os.getenv("OPENAI_WEB_SEARCH_ENABLED", "true").lower() == "true"
MARKET_CACHE_ENABLED = os.getenv("MARKET_CACHE_ENABLED", "true").lower() == "true"
MARKET_CACHE_TTL_MINUTES = int(os.getenv("MARKET_CACHE_TTL_MINUTES", "60"))
MARKET_CACHE_ALLOW_STALE_FALLBACK = os.getenv("MARKET_CACHE_ALLOW_STALE_FALLBACK", "true").lower() == "true"
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "workfall-sam-mvp-project")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "")
LANGSMITH_WORKSPACE_ID = os.getenv("LANGSMITH_WORKSPACE_ID", "")
