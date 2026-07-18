"""Tools available to the search specialist agent."""

from __future__ import annotations

import httpx
from langchain_core.tools import tool

from config import settings


@tool
async def semantic_search_hotels(query: str, city_code: str = "", min_rating: float = 0.0) -> str:
    """Search hotels using semantic (natural language) queries via the RAG pipeline.

    Args:
        query: Natural language description of what the guest is looking for.
        city_code: Optional 3-letter IATA city code to restrict results (e.g. "DXB").
        min_rating: Minimum star rating filter (0.0 = no filter, 4.0 = 4-star+).
    """
    body: dict[str, str | float | int] = {"query": query, "limit": 10}
    if city_code:
        body["city_code"] = city_code
    if min_rating > 0:
        body["min_rating"] = min_rating

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{settings.rag_pipeline_url}/v1/search/hotels", json=body
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except Exception:
            return "Search service unavailable — please try again."

    if not results:
        return "No hotels found matching your criteria."

    lines = [f"Found {len(results)} hotels:"]
    for h in results:
        rating = h.get("rating", "N/A")
        stars = "★" * int(rating) if isinstance(rating, (int, float)) else ""
        lines.append(
            f"- {h.get('name', '?')} ({h.get('hotel_code', '?')}) | "
            f"{h.get('city_code', '?')} | {stars} ({rating})"
        )
    return "\n".join(lines)


@tool
async def list_rooms(hotel_code: str) -> str:
    """List all room types available at a specific hotel.

    Args:
        hotel_code: The hotel identifier (e.g. "HTL001").
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{settings.hotel_inventory_url}/v1/hotels/{hotel_code}/rooms")
        if resp.status_code == 404:
            return f"Hotel {hotel_code} not found."
        resp.raise_for_status()
        rooms = resp.json()

    if not rooms:
        return f"No rooms found for hotel {hotel_code}."

    lines = [f"Rooms at {hotel_code}:"]
    for r in rooms:
        lines.append(
            f"- [{r['room_id']}] {r['room_type']} | Capacity: {r['capacity']} | "
            f"Base price: ${r['base_price']}/night"
        )
    return "\n".join(lines)


@tool
async def check_availability(
    hotel_code: str,
    room_id: str,
    check_in: str,
    check_out: str,
) -> str:
    """Check if a specific room is available for given dates.

    Args:
        hotel_code: Hotel identifier.
        room_id: UUID of the room to check.
        check_in: Check-in date in YYYY-MM-DD format.
        check_out: Check-out date in YYYY-MM-DD format.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.hotel_inventory_url}/v1/hotels/{hotel_code}/rooms/{room_id}/availability",
            params={"check_in": check_in, "check_out": check_out},
        )
        if resp.status_code == 404:
            return f"Room {room_id} not found."
        resp.raise_for_status()
        data = resp.json()

    available = data.get("available", False)
    price = data.get("total_price")
    nights = data.get("nights")
    if available:
        return f"Room {room_id} is available. {nights} nights × base rate = ${price} total."
    return f"Room {room_id} is NOT available for {check_in} → {check_out}."


SEARCH_TOOLS = [semantic_search_hotels, list_rooms, check_availability]
