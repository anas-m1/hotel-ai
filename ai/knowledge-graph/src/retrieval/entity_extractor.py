"""
LLM-based entity extraction from a natural language hotel search query.

Calls the llm-gateway with structured output to extract cities, amenities,
and attractions mentioned in the query. These drive the graph traversal step
of GraphRAG.
"""

from __future__ import annotations

import httpx
import structlog
from pydantic import BaseModel

from config import settings

log = structlog.get_logger()

_SYSTEM = """\
You are an entity extractor for hotel searches. Given a user query, extract:
- cities: city names or IATA codes mentioned
- amenities: hotel facilities mentioned (pool, spa, gym, restaurant, etc.)
- attractions: landmarks, museums, beaches, or points of interest mentioned
- min_star_rating: minimum star rating if mentioned (0 if not)

Return valid JSON only. No explanation.
"""

_SCHEMA = """\
{
  "cities": ["list of city names or codes"],
  "amenities": ["list of amenity names"],
  "attractions": ["list of attraction names"],
  "min_star_rating": 0.0
}
"""


class ExtractedEntities(BaseModel):
    cities: list[str] = []
    amenities: list[str] = []
    attractions: list[str] = []
    min_star_rating: float = 0.0


async def extract_entities(query: str) -> ExtractedEntities:
    """Call llm-gateway to extract structured entities from a search query."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{settings.llm_gateway_url}/v1/chat/completions",
                json={
                    "model": settings.entity_model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM},
                        {
                            "role": "user",
                            "content": (
                                f"Query: {query}\n\n"
                                f"Return JSON matching this schema:\n{_SCHEMA}"
                            ),
                        },
                    ],
                    "temperature": 0.0,
                    "max_tokens": 256,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()

            # Strip markdown fences if the model wraps the JSON
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            import json
            data = json.loads(content)
            return ExtractedEntities.model_validate(data)

    except Exception as exc:
        log.warning("entity_extraction_failed", error=str(exc), query=query)
        return ExtractedEntities()
