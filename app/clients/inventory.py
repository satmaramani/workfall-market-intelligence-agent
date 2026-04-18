from __future__ import annotations

import httpx

from app.core.config import INVENTORY_BASE_URL


async def fetch_product_details(product_id: str) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{INVENTORY_BASE_URL}/api/v1/products/{product_id}")
        response.raise_for_status()
        return response.json()
