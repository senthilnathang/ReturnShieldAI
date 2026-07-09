from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api_v1 import router as v1_router
from app.core.config import settings
from app.core.database import async_engine
from app.core.redis import redis_client
from app.core.logging import setup_logging

logger = logging.getLogger("returnshield")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Starting ReturnShield production API")
    if redis_client:
        await redis_client.initialize()
    yield
    await async_engine.dispose()
    if redis_client:
        await redis_client.close()


app = FastAPI(
    title="ReturnShield Production API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
