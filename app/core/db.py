from __future__ import annotations

from typing import Any

import psycopg
from fastapi import HTTPException, status
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.core.config import DATABASE_URL, SERVICE_NAME
from app.core.utils import now_iso
from app.schemas.common import A2AContext
from app.schemas.market import MarketInsight


def get_connection() -> psycopg.Connection[Any]:
    try:
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    except psycopg.Error as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Market Intelligence database unavailable: {exc}",
        ) from exc


def init_db() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS market_analyses (
                    analysis_id TEXT PRIMARY KEY,
                    product_id TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    trend TEXT NOT NULL,
                    demand_signal TEXT NOT NULL,
                    pricing_opportunity TEXT NOT NULL,
                    recommended_price NUMERIC(12, 2) NOT NULL,
                    competitor_prices JSONB NOT NULL,
                    summary TEXT NOT NULL,
                    citations JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_traces (
                    id BIGSERIAL PRIMARY KEY,
                    service_name TEXT NOT NULL,
                    session_id TEXT,
                    workflow_id TEXT,
                    trace_id TEXT,
                    step_name TEXT NOT NULL,
                    step_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_payload JSONB,
                    output_payload JSONB,
                    error_message TEXT,
                    model_name TEXT,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    total_tokens INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        conn.commit()


def record_trace(
    *,
    context: A2AContext | None,
    step_name: str,
    step_type: str,
    status: str,
    input_payload: dict | None = None,
    output_payload: dict | None = None,
    error_message: str | None = None,
    model_name: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workflow_traces (
                    service_name, session_id, workflow_id, trace_id,
                    step_name, step_type, status, input_payload, output_payload,
                    error_message, model_name, prompt_tokens, completion_tokens, total_tokens
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    SERVICE_NAME,
                    context.session_id if context else None,
                    context.workflow_id if context else None,
                    context.trace_id if context else None,
                    step_name,
                    step_type,
                    status,
                    Jsonb(input_payload) if input_payload is not None else None,
                    Jsonb(output_payload) if output_payload is not None else None,
                    error_message,
                    model_name,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                ),
            )
        conn.commit()


def persist_analysis(product_id: str, product_name: str, insight: MarketInsight, citations: list[dict[str, str]]) -> None:
    from uuid import uuid4

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO market_analyses (
                    analysis_id, product_id, product_name, trend, demand_signal,
                    pricing_opportunity, recommended_price, competitor_prices, summary, citations, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid4()),
                    product_id,
                    product_name,
                    insight.trend,
                    insight.demand_signal,
                    insight.pricing_opportunity,
                    insight.recommended_price,
                    Jsonb([item.model_dump() for item in insight.competitor_prices]),
                    insight.summary,
                    Jsonb(citations),
                    now_iso(),
                ),
            )
        conn.commit()
