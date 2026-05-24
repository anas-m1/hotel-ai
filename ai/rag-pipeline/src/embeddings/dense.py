import asyncio
from functools import lru_cache

from fastembed import TextEmbedding

from ..config import settings


@lru_cache(maxsize=1)
def _model() -> TextEmbedding:
    # Downloaded once to ~/.cache/fastembed; subsequent calls are instant.
    return TextEmbedding(settings.dense_model)


async def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Runs fastembed in a thread pool so the event loop stays unblocked."""
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, lambda: list(_model().embed(texts)))
    return [v.tolist() for v in results]
