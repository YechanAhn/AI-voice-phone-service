"""FastAPI application entry point.

Run with:
    uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.database import close_db, init_db
from src.redis import close_redis, get_redis
from src.reservation.router import router as reservation_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle."""
    # --- Startup ---
    logger.info("app.starting")
    await init_db()
    await get_redis()
    logger.info("app.started")

    yield

    # --- Shutdown ---
    logger.info("app.shutting_down")
    await close_redis()
    await close_db()
    logger.info("app.stopped")


app = FastAPI(
    title="AI Voice Restaurant Reservation Service",
    description="AI 음성 전화 식당 예약 서비스 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reservation_router)


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "ai-voice-phone-service"}
