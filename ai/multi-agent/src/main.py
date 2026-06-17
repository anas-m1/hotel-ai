from __future__ import annotations

import asyncio

import structlog
import uvicorn
from fastapi import FastAPI
from langgraph.checkpoint.memory import MemorySaver

from agents.graph import build_graph
from config import settings
from kafka.consumer import run_consumer
from kafka.producer import start_producer, stop_producer
from router.chat import router, set_graph

log = structlog.get_logger()

app = FastAPI(title="multi-agent", version="0.1.0")
app.include_router(router)

_consumer_task: asyncio.Task | None = None


@app.on_event("startup")
async def _startup() -> None:
    # Initialise Redis checkpointer; fall back to in-memory if Redis is unreachable
    try:
        from langgraph.checkpoint.redis.aio import AsyncRedisSaver

        checkpointer = AsyncRedisSaver.from_url(settings.redis_url)
        await checkpointer.asetup()
        set_graph(build_graph(checkpointer))
        log.info("checkpointer_redis", url=settings.redis_url)
    except Exception as exc:
        log.warning("checkpointer_fallback_memory", reason=str(exc))
        set_graph(build_graph(MemorySaver()))

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
