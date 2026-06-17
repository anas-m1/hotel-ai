"""
Self-RAG: LLM-based relevance scoring pass.

After GraphRAG produces fused candidates, Self-RAG asks the LLM to score
each result for relevance. Results scored "not relevant" are dropped before
returning to the caller.

The three Self-RAG predicates (from the paper):
  ISREL  — Is the retrieved passage relevant to the query?
  ISSUP  — Does it support answering the query?
  ISUSE  — Is the generated answer useful? (skipped here; we score documents, not answers)

We implement ISREL only — sufficient for filtering irrelevant graph artefacts.
"""

from __future__ import annotations

import asyncio

import httpx
import structlog

from config import settings

log = structlog.get_logger()

_SYSTEM = (
    "You are a relevance judge for hotel search results. "
    "Given a search query and a hotel description, answer with a single word: "
    "RELEVANT or NOT_RELEVANT. No explanation."
)


async def _score_one(client: httpx.AsyncClient, query: str, hotel: dict) -> bool:
    """Returns True if the LLM judges this hotel relevant to the query."""
    facilities = hotel.get("facilities", [])
    hotel_desc = (
        f"{hotel['name']} ({hotel.get('star_rating', '?')}★) "
        f"in {hotel.get('city_code', '?')}. "
        f"Facilities: {', '.join(facilities) if facilities else 'not specified'}."
    )
    try:
        resp = await client.post(
            f"{settings.llm_gateway_url}/v1/chat/completions",
            json={
                "model": settings.self_rag_model,
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {
                        "role": "user",
                        "content": f"Query: {query}\nHotel: {hotel_desc}",
                    },
                ],
                "temperature": 0.0,
                "max_tokens": 5,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        verdict = resp.json()["choices"][0]["message"]["content"].strip().upper()
        return "NOT_RELEVANT" not in verdict
    except Exception as exc:
        log.warning("self_rag_score_failed", error=str(exc), hotel=hotel.get("hotel_code"))
        return True  # fail open — keep the result if scoring errors


async def self_rag_filter(
    query: str,
    candidates: list[dict],
    final_limit: int,
) -> list[dict]:
    """
    Score candidates in parallel, keep RELEVANT ones, return top final_limit.
    If Self-RAG is disabled, returns candidates[:final_limit] directly.
    """
    if not settings.self_rag_enabled or not candidates:
        return candidates[:final_limit]

    async with httpx.AsyncClient() as client:
        tasks = [_score_one(client, query, h) for h in candidates]
        verdicts = await asyncio.gather(*tasks)

    relevant = [h for h, keep in zip(candidates, verdicts) if keep]
    dropped = len(candidates) - len(relevant)
    log.info("self_rag_complete", kept=len(relevant), dropped=dropped, query=query)

    return relevant[:final_limit]
