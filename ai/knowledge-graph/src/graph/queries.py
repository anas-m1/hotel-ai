"""
Cypher queries for GraphRAG entity-aware hotel retrieval.

Each query returns hotel_code + a score so results can be fused
with the vector search scores using RRF.
"""

from __future__ import annotations

from graph.client import get_driver


async def find_by_entities(
    city_codes: list[str],
    city_names: list[str],
    amenity_names: list[str],
    attraction_names: list[str],
    min_star_rating: float,
    limit: int,
) -> list[dict]:
    """
    Score hotels by how many requested entities they satisfy.
    A hotel matching more amenities/attractions ranks higher.
    """
    driver = get_driver()
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (h:Hotel)-[:IN_CITY]->(c:City)
            WHERE (
                size($city_codes) = 0
                OR c.code IN $city_codes
                OR c.name IN $city_names
            )
            AND h.star_rating >= $min_star

            OPTIONAL MATCH (h)-[:HAS_AMENITY]->(a:Amenity)
            WHERE size($amenity_names) = 0 OR a.name IN $amenity_names
            WITH h, c, count(DISTINCT a) AS amenity_matches

            OPTIONAL MATCH (h)-[:NEAR_ATTRACTION]->(att:Attraction)
            WHERE size($attraction_names) = 0 OR att.name IN $attraction_names
            WITH h, c, amenity_matches, count(DISTINCT att) AS attraction_matches

            WITH h, c,
                 amenity_matches + attraction_matches AS total_matches,
                 h.star_rating AS star_rating

            ORDER BY total_matches DESC, star_rating DESC
            LIMIT $limit

            RETURN h.hotel_code AS hotel_code,
                   h.name AS name,
                   c.code AS city_code,
                   h.star_rating AS star_rating,
                   total_matches AS graph_score
            """,
            city_codes=[c.upper() for c in city_codes],
            city_names=[c.title() for c in city_names],
            amenity_names=[a.lower() for a in amenity_names],
            attraction_names=[a.title() for a in attraction_names],
            min_star=min_star_rating,
            limit=limit,
        )
        return [dict(r) async for r in result]


async def find_by_attraction_category(category: str, limit: int) -> list[dict]:
    """Find hotels near attractions of a given category (e.g. 'nature', 'culture')."""
    driver = get_driver()
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (h:Hotel)-[:NEAR_ATTRACTION]->(a:Attraction {category: $category})
            WITH h, count(a) AS match_count
            ORDER BY match_count DESC, h.star_rating DESC
            LIMIT $limit
            RETURN h.hotel_code AS hotel_code,
                   h.name AS name,
                   h.star_rating AS star_rating,
                   match_count AS graph_score
            """,
            category=category,
            limit=limit,
        )
        return [dict(r) async for r in result]
