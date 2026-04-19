from __future__ import annotations

import httpx

from app.core.config import API_SHARED_TOKEN, INVENTORY_BASE_URL


def _headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if API_SHARED_TOKEN:
        headers["X-API-Token"] = API_SHARED_TOKEN
    return headers


async def fetch_product_details(product_id: str) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{INVENTORY_BASE_URL}/api/v1/products/{product_id}",
            headers=_headers(),
        )
        response.raise_for_status()
        return response.json()
