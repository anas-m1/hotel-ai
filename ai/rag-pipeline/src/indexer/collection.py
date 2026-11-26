from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, SparseVectorParams, VectorParams

from ..config import settings

DENSE_VECTOR = "dense"
SPARSE_VECTOR = "sparse"

# Dense vector size must match the embedding model output.
# bge-small-en-v1.5 → 384 dims. If you change settings.dense_model, update this.
_DENSE_SIZE = 384


async def ensure_collection(client: AsyncQdrantClient) -> None:
    """Create the hotels collection if it doesn't already exist."""
    existing = await client.get_collections()
    names = {c.name for c in existing.collections}
    if settings.hotels_collection in names:
        return

    await client.create_collection(
        collection_name=settings.hotels_collection,
        vectors_config={
            DENSE_VECTOR: VectorParams(size=_DENSE_SIZE, distance=Distance.COSINE),
        },
        sparse_vectors_config={
            SPARSE_VECTOR: SparseVectorParams(),
        },
    )
