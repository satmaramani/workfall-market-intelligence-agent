from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException

from app.core.config import (
    OPENAI_API_KEY,
    OPENAI_MARKET_MODEL,
    OPENAI_WEB_SEARCH_ENABLED,
    SERVICE_NAME,
    SERVICE_PORT,
    LANGSMITH_TRACING,
    LANGSMITH_PROJECT,
    MARKET_CACHE_ALLOW_STALE_FALLBACK,
    MARKET_CACHE_ENABLED,
    MARKET_CACHE_TTL_MINUTES,
)
from app.core.db import clear_market_cache, fetch_recent_analyses, list_latest_cache_entries
from app.core.security import require_agent_token, require_api_token
from app.core.utils import now_iso
from app.schemas.common import A2AError, A2AMeta, A2ARequest, A2AResponse
from app.services.market_service import analyze_market


router = APIRouter(prefix="/api/v1")


def _enrich_cache_entry(entry: dict) -> dict:
    created_at_raw = entry.get("created_at")
    if not created_at_raw:
        return {
            **entry,
            "cache_age_minutes": None,
            "cache_expires_at": None,
            "is_stale": False,
        }

    created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
    expires_at = created_at + timedelta(minutes=MARKET_CACHE_TTL_MINUTES)
    now = datetime.now(timezone.utc)
    return {
        **entry,
        "cache_age_minutes": round((now - created_at).total_seconds() / 60, 2),
        "cache_expires_at": expires_at.isoformat(),
        "is_stale": now > expires_at,
    }


@router.get("/health")
def health() -> dict:
    from app.main import app
    db_available = app.state.db_available
    openai_configured = bool(OPENAI_API_KEY)

    return {
        "status": "ok" if db_available and openai_configured else "degraded",
        "service": SERVICE_NAME,
        "port": SERVICE_PORT,
        "db_available": db_available,
        "openai_configured": openai_configured,
        "model": OPENAI_MARKET_MODEL,
        "web_search_enabled": OPENAI_WEB_SEARCH_ENABLED,
        "langsmith_tracing": LANGSMITH_TRACING,
        "langsmith_project": LANGSMITH_PROJECT if LANGSMITH_TRACING else None,
        "market_cache_enabled": MARKET_CACHE_ENABLED,
        "market_cache_ttl_minutes": MARKET_CACHE_TTL_MINUTES,
        "market_cache_allow_stale_fallback": MARKET_CACHE_ALLOW_STALE_FALLBACK,
        "timestamp": now_iso(),
    }


@router.get("/capabilities")
def capabilities() -> dict:
    return {"service": SERVICE_NAME, "intents": ["market_analysis", "pricing_support"]}


@router.get("/cache/market")
def get_market_cache(limit: int = 100, x_api_token: str | None = Header(default=None)) -> dict:
    require_api_token(x_api_token)
    entries = [
        _enrich_cache_entry(entry)
        for entry in list_latest_cache_entries(limit=min(max(limit, 1), 500))
    ]
    return {
        "cache_enabled": MARKET_CACHE_ENABLED,
        "cache_ttl_minutes": MARKET_CACHE_TTL_MINUTES,
        "allow_stale_fallback": MARKET_CACHE_ALLOW_STALE_FALLBACK,
        "entry_count": len(entries),
        "entries": entries,
    }


@router.delete("/cache/market")
def clear_all_market_cache(x_api_token: str | None = Header(default=None)) -> dict:
    require_api_token(x_api_token)
    deleted_rows = clear_market_cache()
    return {
        "status": "success",
        "message": "Cleared all market cache entries.",
        "deleted_rows": deleted_rows,
    }


@router.delete("/cache/market/{product_id}")
def clear_product_market_cache(product_id: str, x_api_token: str | None = Header(default=None)) -> dict:
    require_api_token(x_api_token)
    deleted_rows = clear_market_cache(product_id)
    return {
        "status": "success",
        "product_id": product_id,
        "message": f"Cleared market cache for {product_id}.",
        "deleted_rows": deleted_rows,
    }


@router.get("/insights/{product_id}")
async def get_insight(
    product_id: str,
    force_refresh: bool = False,
    x_api_token: str | None = Header(default=None),
) -> dict:
    require_api_token(x_api_token)
    return await analyze_market(product_id, force_refresh=force_refresh)


@router.get("/insights/{product_id}/history")
def get_insight_history(product_id: str, limit: int = 5, x_api_token: str | None = Header(default=None)) -> dict:
    require_api_token(x_api_token)
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
        force_refresh = bool(request.payload.get("force_refresh", False))
        result = await analyze_market(product_id, request.context, force_refresh=force_refresh)
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
