"""
MCP server: hotel-inventory

Thin facade over hotel-inventory:8080. Exposes hotel and room data
as MCP tools so Claude Desktop and other MCP clients can search and
browse the hotel catalogue without any business logic here.
"""

from __future__ import annotations

import httpx
import structlog
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from config import settings

log = structlog.get_logger()
mcp = FastMCP(
    "hotel-inventory",
    # Disable DNS-rebinding host guard: server is exposed publicly via a
    # Cloudflare tunnel, so the request Host is the tunnel hostname.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

# ── Hotels ────────────────────────────────────────────────────────────────────


@mcp.tool()
async def list_hotels(city_code: str = "", limit: int = 20) -> str:
    """List hotels in the catalogue, optionally filtered by city.

    Args:
        city_code: Optional 3-letter IATA city code (e.g. "DXB", "LHR", "JFK").
        limit: Maximum number of hotels to return (default 20, max 100).
    """
    params: dict[str, str | int] = {"limit": min(limit, 100)}
    if city_code:
        params["city_code"] = city_code.upper()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{settings.hotel_inventory_url}/v1/hotels", params=params)
        resp.raise_for_status()
        hotels = resp.json()

    if not hotels:
        return "No hotels found."

    lines = [f"Found {len(hotels)} hotel(s):\n"]
    for h in hotels:
        stars = "★" * int(h.get("star_rating", 0))
        lines.append(
            f"• {h['name']} [{h['hotel_code']}]\n"
            f"  City: {h['city_code']} | Rating: {stars} ({h.get('star_rating', 'N/A')})\n"
            f"  Address: {h.get('address', 'N/A')}\n"
        )
    return "\n".join(lines)


@mcp.tool()
async def get_hotel(hotel_code: str) -> str:
    """Get detailed information about a specific hotel.

    Args:
        hotel_code: The unique hotel identifier (e.g. "HTL001").
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{settings.hotel_inventory_url}/v1/hotels/{hotel_code}")
        if resp.status_code == 404:
            return f"Hotel '{hotel_code}' not found."
        resp.raise_for_status()
        h = resp.json()

    stars = "★" * int(h.get("star_rating", 0))
    facilities = ", ".join(h.get("facilities", [])) or "N/A"
    return (
        f"**{h['name']}** ({h['hotel_code']})\n"
        f"Rating: {stars} ({h.get('star_rating')} stars)\n"
        f"City: {h['city_code']}\n"
        f"Address: {h.get('address', 'N/A')}\n"
        f"Description: {h.get('description', 'N/A')}\n"
        f"Facilities: {facilities}\n"
        f"Check-in: {h.get('check_in_time', 'N/A')} | Check-out: {h.get('check_out_time', 'N/A')}"
    )


# ── Rooms ─────────────────────────────────────────────────────────────────────


@mcp.tool()
async def list_rooms(hotel_code: str) -> str:
    """List all room types at a hotel with pricing and capacity.

    Args:
        hotel_code: The hotel identifier (e.g. "HTL001").
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{settings.hotel_inventory_url}/v1/hotels/{hotel_code}/rooms")
        if resp.status_code == 404:
            return f"Hotel '{hotel_code}' not found."
        resp.raise_for_status()
        rooms = resp.json()

    if not rooms:
        return f"No rooms found for hotel {hotel_code}."

    lines = [f"Rooms at {hotel_code}:\n"]
    for r in rooms:
        amenities = ", ".join(r.get("amenities", [])) or "standard"
        lines.append(
            f"• {r['room_type']} [id: {r['room_id']}]\n"
            f"  Capacity: {r['capacity']} guests | Base price: ${r['base_price']}/night\n"
            f"  Amenities: {amenities}\n"
        )
    return "\n".join(lines)


@mcp.tool()
async def check_room_availability(
    hotel_code: str,
    room_id: str,
    check_in: str,
    check_out: str,
) -> str:
    """Check whether a specific room is available for a date range.

    Args:
        hotel_code: Hotel identifier (e.g. "HTL001").
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
            return f"Room {room_id} at hotel {hotel_code} not found."
        resp.raise_for_status()
        data = resp.json()

    available = data.get("available", False)
    nights = data.get("nights", 0)
    total = data.get("total_price")

    if available:
        return (
            f"✓ Room {room_id} is AVAILABLE for {check_in} → {check_out}\n"
            f"  {nights} night(s) × base rate = **${total} total**"
        )
    return f"✗ Room {room_id} is NOT available for {check_in} → {check_out}."


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(mcp.streamable_http_app(), host=settings.host, port=settings.port)
