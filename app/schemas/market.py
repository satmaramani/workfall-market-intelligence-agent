from __future__ import annotations

from pydantic import BaseModel


class CompetitorPrice(BaseModel):
    seller: str
    price: float
    note: str


class MarketInsight(BaseModel):
    trend: str
    demand_signal: str
    pricing_opportunity: str
    recommended_price: float
    competitor_prices: list[CompetitorPrice]
    summary: str
