from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Market Intelligence needs its own schema ready before it can store analyses or cache entries.
    try:
        init_db()
        app.state.db_available = True
    except Exception:
        app.state.db_available = False
        raise
    yield


app = FastAPI(title="Market Intelligence Agent", version="0.2.0", lifespan=lifespan)
app.state.db_available = False
app.include_router(router)
