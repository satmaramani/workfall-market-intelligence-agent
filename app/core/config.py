from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

SERVICE_NAME = os.getenv("SERVICE_NAME", "market-intelligence-agent")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8003"))
A2A_SHARED_TOKEN = os.getenv("A2A_SHARED_TOKEN", "")
INVENTORY_BASE_URL = os.getenv("INVENTORY_BASE_URL", "http://localhost:8001")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://workfall:workfall@localhost:5432/workfall_multi_agent",
)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MARKET_MODEL = os.getenv("OPENAI_MARKET_MODEL", "gpt-5-mini")
OPENAI_MARKET_REASONING_EFFORT = os.getenv("OPENAI_MARKET_REASONING_EFFORT", "low")
OPENAI_WEB_SEARCH_ENABLED = os.getenv("OPENAI_WEB_SEARCH_ENABLED", "true").lower() == "true"
