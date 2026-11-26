from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, Fusion, FusionQuery, MatchValue, Prefetch
from qdrant_client.models import SparseVector as QdrantSparseVector

from ..config import settings
from ..embeddings import dense as dense_emb
from ..embeddings import sparse as sparse_emb
from ..indexer.collection import DENSE_VECTOR, SPARSE_VECTOR


async def search(
    qdrant: AsyncQdrantClient,
    query: str,
    *,
    city_code: str | None = None,
    rating: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Hybrid search over the hotels collection.

    Both vector types are searched independently (each fetching `prefetch_limit`
    candidates), then Qdrant merges the two ranked lists using Reciprocal Rank
    Fusion (RRF). Hotels that rank well in both lists float to the top.

    Optional payload filters (city_code, rating) are applied before scoring so
    Qdrant never retrieves irrelevant points.
    """
    dense_vecs, sparse_vecs = await dense_emb.embed([query]), await sparse_emb.embed([query])
    dv = dense_vecs[0]
    sv = sparse_vecs[0]

    qdrant_filter: Filter | None = None
    conditions = []
    if city_code:
        conditions.append(FieldCondition(key="city_code", match=MatchValue(value=city_code)))
    if rating:
        conditions.append(FieldCondition(key="rating", match=MatchValue(value=rating)))
    if conditions:
        qdrant_filter = Filter(must=conditions)

    results = await qdrant.query_points(
        collection_name=settings.hotels_collection,
        prefetch=[
            Prefetch(
                query=dv,
                using=DENSE_VECTOR,
                limit=settings.prefetch_limit,
                filter=qdrant_filter,
            ),
            Prefetch(
                query=QdrantSparseVector(indices=sv.indices, values=sv.values),
                using=SPARSE_VECTOR,
                limit=settings.prefetch_limit,
                filter=qdrant_filter,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=limit or settings.search_limit,
        with_payload=True,
    )

    return [
        {
            "hotel_code": pt.payload["hotel_code"],
            "name": pt.payload.get("name", ""),
            "city_code": pt.payload.get("city_code", ""),
            "rating": pt.payload.get("rating", ""),
            "score": pt.score,
        }
        for pt in results.points
    ]
