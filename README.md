# Market Intelligence Agent

Market research and pricing insight service for the multi-agent e-commerce system.

## Responsibilities

- analyze market and competitor pricing signals
- identify demand signals and pricing opportunities
- use OpenAI Responses API with web search for external-source research workflows
- return structured insights for invoice and concierge flows
- persist analysis history in PostgreSQL

## Default Port

`8003`

## Local Run Target

`http://localhost:8003`

## Planned Dependencies

- FastAPI
- Uvicorn
- Pydantic
- httpx
- LangChain
- optional transformers, vector DB, and RAG tooling

## Run Locally

```bash
uvicorn app.main:app --reload --port 8003
```

## Key Endpoints

- `GET /api/v1/health`
- `GET /api/v1/capabilities`
- `GET /api/v1/insights/{product_id}`
- `POST /api/v1/a2a/request`

## Repo Layout

```text
market-intelligence-agent/
  app/
    api/
    clients/
    core/
    models/
    schemas/
    services/
    agents/
    graphs/
  tests/
  .env.example
  requirements.txt
  .gitignore
  README.md
```
