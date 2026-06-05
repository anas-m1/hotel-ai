import structlog
import uvicorn
from fastapi import FastAPI

from .config import settings
from .router.chat import router as chat_router

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
    log.info("booking_assistant_started", port=settings.port, model=settings.agent_model)


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=settings.port, reload=True)
