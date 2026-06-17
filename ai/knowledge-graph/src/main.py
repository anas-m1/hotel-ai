from __future__ import annotations

import structlog
import uvicorn
from fastapi import FastAPI

from config import settings
from graph.client import close_driver, init_driver
from graph.ingestion import run_ingestion
from router.admin import router as admin_router
from router.search import router as search_router

log = structlog.get_logger()

app = FastAPI(title="knowledge-graph", version="0.1.0")
app.include_router(search_router)
app.include_router(admin_router)


@app.get("/healthz")
async def health() -> dict:
    return {"status": "ok"}


@app.on_event("startup")
async def _startup() -> None:
    await init_driver()
    log.info("neo4j_connected", uri=settings.neo4j_uri)

    # Auto-ingest on first start so the graph is queryable immediately.
    # Subsequent restarts re-run ingestion (idempotent MERGE).
    try:
        count = await run_ingestion()
        log.info("startup_ingestion_complete", hotels=count)
    except Exception as exc:
        log.warning("startup_ingestion_failed", error=str(exc))

    log.info("knowledge_graph_started", port=settings.port)


@app.on_event("shutdown")
async def _shutdown() -> None:
    await close_driver()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=False)
