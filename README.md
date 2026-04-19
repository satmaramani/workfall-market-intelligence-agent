# Market Intelligence Agent

Market research and pricing guidance service for the multi-agent e-commerce system.

## What This Service Does

- performs external market research using OpenAI with web search
- uses internal context from Inventory and prior persisted market analyses
- analyzes competitor pricing and market trends
- identifies demand signals and pricing opportunities
- returns structured pricing guidance for Concierge and Invoice workflows
- persists market analysis history in PostgreSQL

## Default Port

`8003`

## Local Base URL

`http://localhost:8003`

## Depends On

- `inventory-agent` on `8001`
- PostgreSQL on `5432`
- OpenAI API key

## PostgreSQL Requirement

This service expects PostgreSQL to already be running before startup.

Recommended local database settings:

- host: `localhost`
- port: `5432`
- database: `workfall_multi_agent`
- user: `workfall`
- password: `workfall`

Tables are created automatically on startup. You do not need to manually create Market Intelligence tables if the configured database is reachable and the user has permission to create tables.

## Tech Used Here

- FastAPI
- OpenAI Python SDK
- PostgreSQL via `psycopg`
- lightweight LangChain-aligned LLM service structure

## Environment Setup

1. Copy the example file:

```powershell
copy .env.example .env
```

2. Update values if needed, especially:

- `OPENAI_API_KEY`
- `DATABASE_URL`
- `INVENTORY_BASE_URL`
- optional `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGSMITH_ENDPOINT`, `LANGSMITH_WORKSPACE_ID`
- optional `MARKET_CACHE_ENABLED`, `MARKET_CACHE_TTL_MINUTES`, `MARKET_CACHE_ALLOW_STALE_FALLBACK`

Example:

```env
DATABASE_URL=postgresql://workfall:workfall@localhost:5432/workfall_multi_agent
LANGSMITH_TRACING=false
LANGSMITH_PROJECT=workfall-sam-mvp-project
MARKET_CACHE_ENABLED=true
MARKET_CACHE_TTL_MINUTES=60
MARKET_CACHE_ALLOW_STALE_FALLBACK=true
```

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run Locally

```powershell
uvicorn app.main:app --reload --port 8003
```

## Key Endpoints

- `GET /api/v1/health`
- `GET /api/v1/capabilities`
- `GET /api/v1/insights/{product_id}`
- `GET /api/v1/insights/{product_id}/history`
- `GET /api/v1/cache/market`
- `DELETE /api/v1/cache/market`
- `DELETE /api/v1/cache/market/{product_id}`
- `POST /api/v1/a2a/request`

## Repo Structure

```text
market-intelligence-agent/
  app/
    api/
    clients/
    core/
    schemas/
    services/
  tests/
  .env.example
  requirements.txt
  .gitignore
  README.md
```

## Notes

- citations are normalized, deduplicated, and capped
- recommended prices are sanity-validated against market/history anchors
- historical analyses are reused as an internal research source
- fresh market analysis is cached in PostgreSQL by product id with a configurable TTL
- the first request for a new product goes live; later requests can be served from cache until the TTL expires
- if `LANGSMITH_TRACING=true`, direct OpenAI market-analysis calls are wrapped and traced into LangSmith
