import structlog
import uvicorn
from fastapi import FastAPI
from qdrant_client import AsyncQdrantClient

from .config import settings
from .indexer.collection import ensure_collection
from .router import index, search

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
    title="RAG Pipeline",
    description="Hybrid dense+sparse hotel search over Qdrant",
    version="1.0.0",
)

app.include_router(search.router, prefix="/v1")
app.include_router(index.router, prefix="/v1")


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup() -> None:
    app.state.qdrant = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )
    await ensure_collection(app.state.qdrant)
    log.info("rag_pipeline_started", qdrant_url=settings.qdrant_url)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await app.state.qdrant.close()


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=settings.port, reload=True)
