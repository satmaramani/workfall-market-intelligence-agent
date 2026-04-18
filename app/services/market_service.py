from __future__ import annotations

from fastapi import HTTPException, status
from openai import OpenAI

from app.clients.inventory import fetch_product_details
from app.core.config import (
    OPENAI_API_KEY,
    OPENAI_MARKET_MODEL,
    OPENAI_MARKET_REASONING_EFFORT,
    OPENAI_WEB_SEARCH_ENABLED,
)
from app.core.db import persist_analysis, record_trace
from app.core.utils import now_iso
from app.schemas.market import MarketInsight


def get_openai_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured for Market Intelligence",
        )
    return OpenAI(api_key=OPENAI_API_KEY)


def extract_sources(response) -> list[dict[str, str]]:
    raw = response.model_dump() if hasattr(response, "model_dump") else response
    sources: list[dict[str, str]] = []
    for item in raw.get("output", []):
        if item.get("type") == "web_search_call":
            for source in item.get("action", {}).get("sources", []) or []:
                url = source.get("url")
                title = source.get("title")
                if url and not any(existing["url"] == url for existing in sources):
                    sources.append({"url": url, "title": title or url})
        if item.get("type") == "message":
            for content in item.get("content", []):
                for annotation in content.get("annotations", []) or []:
                    if annotation.get("type") == "url_citation":
                        url = annotation.get("url")
                        title = annotation.get("title")
                        if url and not any(existing["url"] == url for existing in sources):
                            sources.append({"url": url, "title": title or url})
    return sources


async def analyze_market(product_id: str, context=None) -> dict:
    product = await fetch_product_details(product_id)
    client = get_openai_client()

    tools = []
    include = []
    if OPENAI_WEB_SEARCH_ENABLED:
        tools = [{"type": "web_search"}]
        include = ["web_search_call.action.sources"]

    system_prompt = (
        "You are a Market Intelligence Agent for an internal e-commerce system. "
        "Research current competitor pricing and demand signals for the provided product. "
        "Return concise, evidence-backed pricing guidance. "
        "Keep the response short and UI-friendly. "
        "Write a brief summary in 2 to 4 sentences only. "
        "Limit competitor price examples to the strongest few references. "
        "Use web search when available. "
        "Prefer only the strongest and most relevant sources. "
        "Cite at most 5 sources total. "
        "Avoid duplicate links, tracking-parameter variants, low-quality directories, stale PDFs, and weak references."
    )
    user_prompt = {
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "category": product["category"],
        "current_unit_price": product["unit_price"],
        "task": (
            "Provide competitor pricing, demand trend, pricing opportunity, and a recommended price. "
            "Keep the summary compact for dashboard display."
        ),
    }
    response = client.responses.parse(
        model=OPENAI_MARKET_MODEL,
        reasoning={"effort": OPENAI_MARKET_REASONING_EFFORT},
        tools=tools,
        include=include,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": str(user_prompt)},
        ],
        text_format=MarketInsight,
    )
    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI could not generate a structured market analysis",
        )
    usage = getattr(response, "usage", None)
    citations = extract_sources(response)
    persist_analysis(product["product_id"], product["product_name"], parsed, citations)
    result = {
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "category": product["category"],
        "current_unit_price": product["unit_price"],
        "trend": parsed.trend,
        "demand_signal": parsed.demand_signal,
        "pricing_opportunity": parsed.pricing_opportunity,
        "recommended_price": parsed.recommended_price,
        "competitor_prices": [item.model_dump() for item in parsed.competitor_prices],
        "summary": parsed.summary,
        "citations": citations,
        "generated_at": now_iso(),
    }
    record_trace(
        context=context,
        step_name="market_openai_analysis",
        step_type="ai_call",
        status="success",
        input_payload=user_prompt,
        output_payload=result,
        model_name=OPENAI_MARKET_MODEL,
        prompt_tokens=getattr(usage, "input_tokens", None) if usage else None,
        completion_tokens=getattr(usage, "output_tokens", None) if usage else None,
        total_tokens=getattr(usage, "total_tokens", None) if usage else None,
    )
    return result
