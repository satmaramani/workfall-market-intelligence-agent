from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import HTTPException, status
from openai import OpenAI

from app.clients.inventory import fetch_product_details
from app.core.config import (
    OPENAI_API_KEY,
    OPENAI_MARKET_MODEL,
    OPENAI_MARKET_REASONING_EFFORT,
    OPENAI_WEB_SEARCH_ENABLED,
)
from app.core.db import fetch_recent_analyses, persist_analysis, record_trace
from app.core.utils import now_iso
from app.schemas.market import MarketInsight

MAX_CITATIONS = 5
MAX_COMPETITOR_PRICES = 3


def get_openai_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured for Market Intelligence",
        )
    return OpenAI(api_key=OPENAI_API_KEY)


def normalize_url(url: str) -> str:
    parsed = urlsplit(url)
    filtered_query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if not key.startswith("utm_")]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(filtered_query), ""))


def extract_sources(response) -> list[dict[str, str]]:
    raw = response.model_dump() if hasattr(response, "model_dump") else response
    sources: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for item in raw.get("output", []):
        if item.get("type") == "web_search_call":
            for source in item.get("action", {}).get("sources", []) or []:
                url = source.get("url")
                title = source.get("title")
                normalized_url = normalize_url(url) if url else None
                if normalized_url and normalized_url not in seen_urls:
                    seen_urls.add(normalized_url)
                    sources.append({"url": normalized_url, "title": title or normalized_url})
        if item.get("type") == "message":
            for content in item.get("content", []):
                for annotation in content.get("annotations", []) or []:
                    if annotation.get("type") == "url_citation":
                        url = annotation.get("url")
                        title = annotation.get("title")
                        normalized_url = normalize_url(url) if url else None
                        if normalized_url and normalized_url not in seen_urls:
                            seen_urls.add(normalized_url)
                            sources.append({"url": normalized_url, "title": title or normalized_url})
    return sources[:MAX_CITATIONS]


def summarize_internal_history(analyses: list[dict]) -> list[dict]:
    return [
        {
            "created_at": analysis["created_at"],
            "trend": analysis["trend"],
            "demand_signal": analysis["demand_signal"],
            "pricing_opportunity": analysis["pricing_opportunity"],
            "recommended_price": analysis["recommended_price"],
            "summary": analysis["summary"],
        }
        for analysis in analyses
    ]


def validate_competitor_prices(competitor_prices: list) -> list[dict]:
    validated = []
    for item in competitor_prices:
        data = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        price = float(data.get("price", 0))
        if price <= 0:
            continue
        validated.append(
            {
                "seller": data.get("seller", "Unknown"),
                "price": round(price, 2),
                "note": data.get("note", ""),
            }
        )
    return validated[:MAX_COMPETITOR_PRICES]


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def validate_recommended_price(
    recommended_price: float,
    current_unit_price: float,
    competitor_prices: list[dict],
    recent_analyses: list[dict],
) -> float:
    anchor_candidates = [item["price"] for item in competitor_prices if item.get("price", 0) > 0]
    anchor_candidates.extend(
        analysis["recommended_price"]
        for analysis in recent_analyses
        if analysis.get("recommended_price", 0) > 0
    )

    if anchor_candidates:
        reference_price = _median(anchor_candidates)
        if current_unit_price <= reference_price * 0.25 or current_unit_price >= reference_price * 4:
            lower_bound = reference_price * 0.5
            upper_bound = reference_price * 1.5
        else:
            lower_bound = min(current_unit_price * 0.5, reference_price * 0.5)
            upper_bound = max(current_unit_price * 1.5, reference_price * 1.5)
    else:
        if recommended_price <= 0:
            return round(current_unit_price, 2)
        lower_bound = current_unit_price * 0.5
        upper_bound = current_unit_price * 1.5

    if recommended_price <= 0:
        bounded_price = max(current_unit_price, lower_bound)
    else:
        bounded_price = min(max(recommended_price, lower_bound), upper_bound)
    return round(bounded_price, 2)


async def analyze_market(product_id: str, context=None) -> dict:
    product = await fetch_product_details(product_id)
    recent_analyses = fetch_recent_analyses(product_id)
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
        "internal_research_context": {
            "recent_analyses": summarize_internal_history(recent_analyses),
            "historical_analysis_count": len(recent_analyses),
        },
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
    competitor_prices = validate_competitor_prices(parsed.competitor_prices)
    recommended_price = validate_recommended_price(
        parsed.recommended_price,
        float(product["unit_price"]),
        competitor_prices,
        recent_analyses,
    )
    persist_analysis(
        product["product_id"],
        product["product_name"],
        trend=parsed.trend,
        demand_signal=parsed.demand_signal,
        pricing_opportunity=parsed.pricing_opportunity,
        recommended_price=recommended_price,
        competitor_prices=competitor_prices,
        summary=parsed.summary,
        citations=citations,
    )
    result = {
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "category": product["category"],
        "current_unit_price": product["unit_price"],
        "trend": parsed.trend,
        "demand_signal": parsed.demand_signal,
        "pricing_opportunity": parsed.pricing_opportunity,
        "recommended_price": recommended_price,
        "competitor_prices": competitor_prices,
        "summary": parsed.summary,
        "citations": citations,
        "internal_research_context": {
            "historical_analysis_count": len(recent_analyses),
            "recent_analyses": summarize_internal_history(recent_analyses),
        },
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
