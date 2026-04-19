from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.core.config import OPENAI_API_KEY, OPENAI_MARKET_MODEL, OPENAI_WEB_SEARCH_ENABLED, SERVICE_NAME, SERVICE_PORT
from app.core.db import fetch_recent_analyses
from app.core.security import require_agent_token
from app.core.utils import now_iso
from app.schemas.common import A2AError, A2AMeta, A2ARequest, A2AResponse
from app.services.market_service import analyze_market


router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> dict:
    from app.main import app

    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "port": SERVICE_PORT,
        "db_available": app.state.db_available,
        "openai_configured": bool(OPENAI_API_KEY),
        "model": OPENAI_MARKET_MODEL,
        "web_search_enabled": OPENAI_WEB_SEARCH_ENABLED,
        "timestamp": now_iso(),
    }


@router.get("/capabilities")
def capabilities() -> dict:
    return {"service": SERVICE_NAME, "intents": ["market_analysis", "pricing_support"]}


@router.get("/insights/{product_id}")
async def get_insight(product_id: str) -> dict:
    return await analyze_market(product_id)


@router.get("/insights/{product_id}/history")
def get_insight_history(product_id: str, limit: int = 5) -> dict:
    return {
        "product_id": product_id,
        "analyses": fetch_recent_analyses(product_id, limit=min(max(limit, 1), 20)),
    }


@router.post("/a2a/request", response_model=A2AResponse)
async def a2a_request(request: A2ARequest, x_agent_token: str | None = Header(default=None)) -> A2AResponse:
    require_agent_token(x_agent_token)
    if request.intent not in {"market_analysis", "pricing_support"}:
        return A2AResponse(
            request_id=request.request_id,
            status="failed",
            agent="market-intelligence",
            result=None,
            error=A2AError(code="UNSUPPORTED_INTENT", message="Unsupported market intent", retriable=False),
            meta=A2AMeta(retry_count=0, timestamp=now_iso(), source_service=SERVICE_NAME, target_service="caller"),
        )
    try:
        product_id = request.payload.get("product_id")
        if not product_id:
            raise HTTPException(status_code=422, detail="product_id is required")
        result = await analyze_market(product_id, request.context)
        return A2AResponse(
            request_id=request.request_id,
            status="success",
            agent="market-intelligence",
            result=result,
            error=None,
            meta=A2AMeta(retry_count=0, timestamp=now_iso(), source_service=SERVICE_NAME, target_service="caller"),
        )
    except HTTPException as exc:
        return A2AResponse(
            request_id=request.request_id,
            status="failed",
            agent="market-intelligence",
            result=None,
            error=A2AError(code="MARKET_ERROR", message=str(exc.detail), retriable=exc.status_code >= 500),
            meta=A2AMeta(retry_count=0, timestamp=now_iso(), source_service=SERVICE_NAME, target_service="caller"),
        )
