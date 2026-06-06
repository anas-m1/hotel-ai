from __future__ import annotations

import asyncio

import structlog
import uvicorn
from fastapi import FastAPI

from config import settings
from kafka.consumer import run_consumer
from kafka.producer import start_producer, stop_producer
from router.chat import router

log = structlog.get_logger()

app = FastAPI(title="multi-agent", version="0.1.0")
app.include_router(router)

_consumer_task: asyncio.Task | None = None


@app.on_event("startup")
async def _startup() -> None:
    await start_producer()
    global _consumer_task
    _consumer_task = asyncio.create_task(run_consumer())
    log.info("multi_agent_started", port=settings.port)


@app.on_event("shutdown")
async def _shutdown() -> None:
    if _consumer_task:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
    await stop_producer()


@app.get("/healthz")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=False)
