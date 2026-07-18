from typing import Any

import httpx
import structlog
from langchain_core.tools import tool

from ..config import settings

log = structlog.get_logger()


async def _get_json(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.json()


async def _post_json(
    client: httpx.AsyncClient, url: str, payload: dict[str, Any]
) -> dict[str, Any]:
    resp = await client.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()


@tool
async def search_hotels(
    city: str | None = None,
    query: str | None = None,
    rating: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search for hotels by city, text query, or rating filter."""
    params: dict[str, str | int] = {}
    if city:
        params["city"] = city
    if query:
        params["q"] = query
    if rating:
        params["rating"] = rating
    params["limit"] = limit

    async with httpx.AsyncClient(base_url=settings.hotel_inventory_url) as client:
        resp = await client.get("/v1/hotels", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("hotels", [])


@tool
async def get_hotel(hotel_code: str) -> dict[str, Any] | None:
    """Get detailed information about a specific hotel by its code."""
    async with httpx.AsyncClient(base_url=settings.hotel_inventory_url) as client:
        try:
            return await _get_json(client, f"/v1/hotels/{hotel_code}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise


@tool
async def list_rooms(hotel_code: str, room_type: str | None = None) -> list[dict[str, Any]]:
    """List available rooms for a hotel, optionally filtered by room type."""
    params: dict[str, str] = {}
    if room_type:
        params["type"] = room_type

    async with httpx.AsyncClient(base_url=settings.hotel_inventory_url) as client:
        resp = await client.get(f"/v1/hotels/{hotel_code}/rooms", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("rooms", [])


@tool
async def check_availability(
    room_id: str, check_in: str, check_out: str
) -> dict[str, Any]:
    """Check if a room is available for the given dates (YYYY-MM-DD format)."""
    async with httpx.AsyncClient(base_url=settings.booking_ops_url) as client:
        try:
            return await _get_json(
                client, f"/v1/availability?room_id={room_id}&check_in={check_in}&check_out={check_out}"
            )
        except httpx.HTTPStatusError as exc:
            return {"available": False, "error": str(exc)}


@tool
async def get_guest(email: str) -> dict[str, Any] | None:
    """Look up an existing guest by email."""
    async with httpx.AsyncClient(base_url=settings.booking_ops_url) as client:
        try:
            return await _get_json(client, f"/v1/guests/by-email/{email}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise


@tool
async def create_guest(
    email: str, first_name: str, last_name: str, phone: str = ""
) -> dict[str, Any]:
    """Create or update a guest profile."""
    async with httpx.AsyncClient(base_url=settings.booking_ops_url) as client:
        return await _post_json(
            client,
            "/v1/guests",
            {"email": email, "first_name": first_name, "last_name": last_name, "phone": phone},
        )


@tool
async def book_room(
    guest_id: str,
    hotel_code: str,
    room_id: str,
    check_in: str,
    check_out: str,
    total_price: str,
    currency: str = "USD",
    special_requests: str = "",
) -> dict[str, Any]:
    """Create a new booking. Requires guest_id, hotel_code, room_id, dates, and total_price."""
    async with httpx.AsyncClient(base_url=settings.booking_ops_url) as client:
        return await _post_json(
            client,
            "/v1/bookings",
            {
                "guest_id": guest_id,
                "hotel_code": hotel_code,
                "room_id": room_id,
                "check_in_date": check_in,
                "check_out_date": check_out,
                "total_price": total_price,
                "currency": currency,
                "special_requests": special_requests,
            },
        )


@tool
async def get_booking(booking_id: str) -> dict[str, Any]:
    """Get booking details and event history by booking ID."""
    async with httpx.AsyncClient(base_url=settings.booking_ops_url) as client:
        try:
            return await _get_json(client, f"/v1/bookings/{booking_id}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {"error": "Booking not found"}
            raise


@tool
async def semantic_search_hotels(
    query: str,
    city_code: str | None = None,
    rating: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search hotels by natural language description using semantic search.
    Good for queries like 'quiet hotels with ocean view' or 'family-friendly resorts'."""
    async with httpx.AsyncClient(base_url=settings.rag_pipeline_url) as client:
        try:
            resp = await client.post(
                "/v1/search/hotels",
                json={
                    "query": query,
                    "city_code": city_code,
                    "rating": rating,
                    "limit": limit,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", [])
        except httpx.HTTPStatusError as exc:
            log.error("semantic_search_failed", status=exc.response.status_code, error=str(exc))
            return []


tools = [
    search_hotels,
    get_hotel,
    list_rooms,
    check_availability,
    semantic_search_hotels,
    get_guest,
    create_guest,
    book_room,
    get_booking,
]
