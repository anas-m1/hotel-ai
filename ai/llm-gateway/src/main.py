import os
import sys
import types

import langfuse
import litellm
import structlog
import uvicorn
from fastapi import FastAPI

from .config import settings
from .router import chat, models, usage

# langfuse >= 4.0 moved its version string to `langfuse._version`, but litellm's
# langfuse integration (1.100.x) still reads `langfuse.version.__version__`.
# Provide the legacy module so the tracing callback can initialize.
if not hasattr(langfuse, "version"):
    _version = getattr(
        __import__("langfuse._version", fromlist=["__version__"]),
        "__version__",
        "0.0.0",
    )
    _shim = types.ModuleType("langfuse.version")
    _shim.__version__ = _version
    sys.modules["langfuse.version"] = _shim
    langfuse.version = _shim

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
app.include_router(usage.router, prefix="/v1")


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup() -> None:
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
        os.environ["LANGFUSE_HOST"] = settings.langfuse_host
        litellm.success_callback = ["langfuse"]
        log.info("langfuse_tracing_enabled", host=settings.langfuse_host)
    else:
        log.info("langfuse_tracing_disabled")

    log.info("gateway_started", port=settings.port, default_model=settings.default_model)


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=settings.port, reload=True)
