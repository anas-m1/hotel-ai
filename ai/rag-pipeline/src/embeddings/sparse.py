import asyncio
from functools import lru_cache
from typing import NamedTuple

from fastembed.sparse import SparseTextEmbedding

from ..config import settings


class SparseVector(NamedTuple):
    indices: list[int]
    values: list[float]


@lru_cache(maxsize=1)
def _model() -> SparseTextEmbedding:
    return SparseTextEmbedding(settings.sparse_model)


async def embed(texts: list[str]) -> list[SparseVector]:
    """Embed a batch of texts into sparse BM42 vectors."""
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, lambda: list(_model().embed(texts)))
    return [
        SparseVector(indices=e.indices.tolist(), values=e.values.tolist())
        for e in results
    ]
