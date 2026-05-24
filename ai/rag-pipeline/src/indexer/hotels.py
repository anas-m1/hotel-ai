import uuid
from typing import Any

import httpx
import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct
from qdrant_client.models import SparseVector as QdrantSparseVector

from ..config import settings
from ..embeddings import dense as dense_emb
from ..embeddings import sparse as sparse_emb
from .collection import DENSE_VECTOR, SPARSE_VECTOR

log = structlog.get_logger()

# How many hotels to fetch and embed in one batch.
# Larger = fewer round trips; smaller = lower peak memory.
_BATCH_SIZE = 50


def _hotel_text(hotel: dict[str, Any]) -> str:
    """Concatenate the fields that best describe a hotel for semantic search."""
    parts = [hotel.get("name", "")]
    for field in ("description", "facilities", "attractions", "address"):
        val = hotel.get(field, "")
        if val:
            parts.append(val)
    return " ".join(parts)


def _stable_id(hotel_code: str) -> str:
    """Deterministic UUID from hotel_code so re-indexing updates the same point."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, hotel_code))


async def _fetch_all_hotels() -> list[dict[str, Any]]:
    """Page through GET /v1/hotels until all hotels are fetched."""
    hotels: list[dict[str, Any]] = []
    limit = 100
    offset = 0

    async with httpx.AsyncClient(base_url=settings.hotel_inventory_url, timeout=30) as client:
        while True:
            resp = client.get("/v1/hotels", params={"limit": limit, "offset": offset})
            resp = await resp
            resp.raise_for_status()
            batch: list[dict[str, Any]] = resp.json()
            if not batch:
                break
            hotels.extend(batch)
            if len(batch) < limit:
                break
            offset += limit

    return hotels


async def index_hotels(qdrant: AsyncQdrantClient) -> int:
    """
    Full re-index: fetch all hotels, embed in batches, upsert into Qdrant.
    Returns the number of hotels indexed.
    """
    hotels = await _fetch_all_hotels()
    if not hotels:
        log.warning("no_hotels_found")
        return 0

    log.info("indexing_hotels", total=len(hotels))
    indexed = 0

    for start in range(0, len(hotels), _BATCH_SIZE):
        batch = hotels[start : start + _BATCH_SIZE]
        texts = [_hotel_text(h) for h in batch]

        dense_vecs, sparse_vecs = await dense_emb.embed(texts), await sparse_emb.embed(texts)

        points = [
            PointStruct(
                id=_stable_id(h["hotel_code"]),
                vector={
                    DENSE_VECTOR: dv,
                    SPARSE_VECTOR: QdrantSparseVector(
                        indices=sv.indices,
                        values=sv.values,
                    ),
                },
                payload={
                    "hotel_code": h["hotel_code"],
                    "name": h.get("name", ""),
                    "city_code": h.get("city_code", ""),
                    "rating": h.get("rating", ""),
                },
            )
            for h, dv, sv in zip(batch, dense_vecs, sparse_vecs)
        ]

        await qdrant.upsert(collection_name=settings.hotels_collection, points=points)
        indexed += len(points)
        log.info("batch_indexed", indexed=indexed, total=len(hotels))

    return indexed
