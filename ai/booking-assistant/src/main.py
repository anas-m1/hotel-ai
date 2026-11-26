import structlog
import uvicorn
from fastapi import FastAPI
from langgraph.checkpoint.memory import MemorySaver

from agent.graph import build_graph
from agent.instance import set_graph
from config import settings
from router.chat import router as chat_router

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()

app = FastAPI(
    title="Booking Assistant",
    description="LangGraph ReAct agent for hotel search, availability, and reservations",
    version="0.1.0",
)

app.include_router(chat_router, prefix="/v1")


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup() -> None:
    try:
        from langgraph.checkpoint.redis.aio import AsyncRedisSaver

        # The installed langgraph-checkpoint-redis exposes the URL as its
        # constructor argument; its `from_url` attribute is not available.
        checkpointer = AsyncRedisSaver(settings.redis_url)
        await checkpointer.asetup()
        set_graph(build_graph(checkpointer))
        log.info("checkpointer_redis", url=settings.redis_url)
    except Exception as exc:
        log.warning("checkpointer_fallback_memory", reason=str(exc))
        set_graph(build_graph(MemorySaver()))

    log.info("booking_assistant_started", port=settings.port, model=settings.agent_model)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=True)
