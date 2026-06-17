"""
Populates Neo4j from hotel-inventory data.

Run once at startup (idempotent — uses MERGE so re-running is safe)
or trigger manually via POST /v1/admin/ingest.
"""

from __future__ import annotations

import structlog
import httpx

from config import settings
from graph.client import get_driver
from graph.schema import CITY_ATTRACTIONS, categorise_amenity

log = structlog.get_logger()


async def _fetch_all_hotels() -> list[dict]:
    hotels: list[dict] = []
    page, limit = 0, 100
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            resp = await client.get(
                f"{settings.hotel_inventory_url}/v1/hotels",
                params={"limit": limit, "offset": page * limit},
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            hotels.extend(batch)
            if len(batch) < limit:
                break
            page += 1
    return hotels


async def _create_constraints(driver) -> None:
    """Create uniqueness constraints — idempotent."""
    async with driver.session() as session:
        constraints = [
            "CREATE CONSTRAINT hotel_code IF NOT EXISTS FOR (h:Hotel) REQUIRE h.hotel_code IS UNIQUE",
            "CREATE CONSTRAINT city_code IF NOT EXISTS FOR (c:City) REQUIRE c.code IS UNIQUE",
            "CREATE CONSTRAINT amenity_name IF NOT EXISTS FOR (a:Amenity) REQUIRE a.name IS UNIQUE",
            "CREATE CONSTRAINT attraction_name IF NOT EXISTS FOR (a:Attraction) REQUIRE a.name IS UNIQUE",
        ]
        for cypher in constraints:
            await session.run(cypher)


async def _upsert_hotels(driver, hotels: list[dict]) -> None:
    async with driver.session() as session:
        for hotel in hotels:
            city_code = hotel.get("city_code", "")
            facilities: list[str] = hotel.get("facilities", [])

            # Hotel + City nodes
            await session.run(
                """
                MERGE (c:City {code: $city_code})
                ON CREATE SET c.name = $city_code

                MERGE (h:Hotel {hotel_code: $hotel_code})
                SET h.name = $name,
                    h.star_rating = $star_rating,
                    h.description = $description,
                    h.address = $address

                MERGE (h)-[:IN_CITY]->(c)
                """,
                hotel_code=hotel["hotel_code"],
                name=hotel["name"],
                star_rating=float(hotel.get("star_rating", 0)),
                description=hotel.get("description", ""),
                address=hotel.get("address", ""),
                city_code=city_code,
            )

            # Amenity nodes for each facility
            for facility in facilities:
                category = categorise_amenity(facility)
                await session.run(
                    """
                    MERGE (a:Amenity {name: $name})
                    ON CREATE SET a.category = $category
                    WITH a
                    MATCH (h:Hotel {hotel_code: $hotel_code})
                    MERGE (h)-[:HAS_AMENITY]->(a)
                    """,
                    name=facility.lower(),
                    category=category,
                    hotel_code=hotel["hotel_code"],
                )

            # Attraction nodes from static seed data
            for attraction_data in CITY_ATTRACTIONS.get(city_code, []):
                await session.run(
                    """
                    MERGE (a:Attraction {name: $name})
                    ON CREATE SET a.category = $category, a.city_code = $city_code
                    WITH a
                    MATCH (h:Hotel {hotel_code: $hotel_code})
                    MERGE (h)-[:NEAR_ATTRACTION {distance_km: 2.0}]->(a)
                    """,
                    name=attraction_data["name"],
                    category=attraction_data["category"],
                    city_code=city_code,
                    hotel_code=hotel["hotel_code"],
                )


async def run_ingestion() -> int:
    """Fetch hotels and populate Neo4j. Returns count of hotels ingested."""
    driver = get_driver()
    await _create_constraints(driver)

    hotels = await _fetch_all_hotels()
    if not hotels:
        log.warning("ingestion_no_hotels")
        return 0

    await _upsert_hotels(driver, hotels)
    log.info("ingestion_complete", hotel_count=len(hotels))
    return len(hotels)
