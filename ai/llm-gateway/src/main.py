import structlog
import uvicorn
from fastapi import FastAPI

from .config import settings
from .router import chat, models

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
    title="LLM Gateway",
    description="Unified LLM routing with cost tracking and prompt versioning",
    version="1.0.0",
)

app.include_router(chat.router, prefix="/v1")
app.include_router(models.router, prefix="/v1")


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup() -> None:
    log.info("gateway_started", port=settings.port, default_model=settings.default_model)


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=settings.port, reload=True)
