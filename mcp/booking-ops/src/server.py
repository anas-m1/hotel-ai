"""
MCP server: booking-ops

Thin facade over booking-ops:8081. Exposes guest management and
reservation operations as MCP tools. No business logic lives here —
all validation, optimistic locking, and event publishing happens in
the Go service.
"""

from __future__ import annotations

import httpx
import structlog
from mcp.server.fastmcp import FastMCP

from config import settings

log = structlog.get_logger()
mcp = FastMCP("booking-ops")

# ── Guests ────────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_guest_by_email(email: str) -> str:
    """Look up a guest profile by email address.

    Args:
        email: The guest's email address.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.booking_ops_url}/v1/guests/by-email",
            params={"email": email},
        )
        if resp.status_code == 404:
            return f"No guest found with email '{email}'."
        resp.raise_for_status()
        g = resp.json()

    return (
        f"**Guest found**\n"
        f"Name: {g['first_name']} {g['last_name']}\n"
        f"Email: {g['email']}\n"
        f"Phone: {g.get('phone', 'N/A')}\n"
        f"Guest ID: {g['guest_id']}"
    )


@mcp.tool()
async def create_guest(
    first_name: str,
    last_name: str,
    email: str,
    phone: str = "",
) -> str:
    """Create a new guest profile.

    Args:
        first_name: Guest's first name.
        last_name: Guest's last name.
        email: Guest's email address (must be unique).
        phone: Optional phone number.
    """
    body: dict = {"first_name": first_name, "last_name": last_name, "email": email}
    if phone:
        body["phone"] = phone

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"{settings.booking_ops_url}/v1/guests", json=body)
        if resp.status_code == 409:
            return (
                f"A guest with email '{email}' already exists. "
                "Use get_guest_by_email to retrieve their profile."
            )
        resp.raise_for_status()
        g = resp.json()

    return (
        f"**Guest created**\n"
        f"Name: {g['first_name']} {g['last_name']}\n"
        f"Email: {g['email']}\n"
        f"Guest ID: {g['guest_id']}"
    )


# ── Bookings ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def create_booking(
    guest_id: str,
    hotel_code: str,
    room_id: str,
    check_in: str,
    check_out: str,
) -> str:
    """Create a new hotel room booking.

    Args:
        guest_id: UUID of the guest making the booking.
        hotel_code: Hotel identifier (e.g. "HTL001").
        room_id: UUID of the room to book.
        check_in: Check-in date in YYYY-MM-DD format.
        check_out: Check-out date in YYYY-MM-DD format.
    """
    body = {
        "guest_id": guest_id,
        "hotel_code": hotel_code,
        "room_id": room_id,
        "check_in": check_in,
        "check_out": check_out,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(f"{settings.booking_ops_url}/v1/bookings", json=body)
        if resp.status_code == 409:
            return (
                f"Room {room_id} is no longer available for {check_in} → {check_out}. "
                "Please check availability again and choose a different room or dates."
            )
        if resp.status_code == 422:
            detail = resp.json().get("message", resp.text)
            return f"Invalid booking request: {detail}"
        resp.raise_for_status()
        b = resp.json()

    return (
        f"**Booking confirmed!**\n"
        f"Booking ID: {b['booking_id']}\n"
        f"Hotel: {b['hotel_code']} | Room: {b['room_id']}\n"
        f"Dates: {b['check_in']} → {b['check_out']}\n"
        f"Total price: ${b['total_price']}\n"
        f"Status: {b['status']}"
    )


@mcp.tool()
async def get_booking(booking_id: str) -> str:
    """Retrieve details of an existing booking.

    Args:
        booking_id: UUID of the booking to look up.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{settings.booking_ops_url}/v1/bookings/{booking_id}")
        if resp.status_code == 404:
            return f"Booking '{booking_id}' not found."
        resp.raise_for_status()
        b = resp.json()

    return (
        f"**Booking {b['booking_id']}**\n"
        f"Status: {b['status']}\n"
        f"Guest ID: {b['guest_id']}\n"
        f"Hotel: {b['hotel_code']} | Room: {b['room_id']}\n"
        f"Dates: {b['check_in']} → {b['check_out']}\n"
        f"Total price: ${b['total_price']}\n"
        f"Created: {b.get('created_at', 'N/A')}"
    )


@mcp.tool()
async def cancel_booking(booking_id: str) -> str:
    """Cancel an existing booking.

    Args:
        booking_id: UUID of the booking to cancel.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.delete(f"{settings.booking_ops_url}/v1/bookings/{booking_id}")
        if resp.status_code == 404:
            return f"Booking '{booking_id}' not found."
        if resp.status_code == 409:
            return f"Booking '{booking_id}' cannot be cancelled in its current state."
        resp.raise_for_status()

    return f"Booking {booking_id} has been successfully cancelled."


@mcp.tool()
async def list_guest_bookings(guest_id: str) -> str:
    """List all bookings for a specific guest.

    Args:
        guest_id: UUID of the guest whose bookings to retrieve.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.booking_ops_url}/v1/bookings",
            params={"guest_id": guest_id},
        )
        if resp.status_code == 404:
            return f"Guest '{guest_id}' not found."
        resp.raise_for_status()
        bookings = resp.json()

    if not bookings:
        return f"No bookings found for guest {guest_id}."

    lines = [f"Bookings for guest {guest_id}:\n"]
    for b in bookings:
        lines.append(
            f"• [{b['status']}] {b['booking_id']}\n"
            f"  {b['hotel_code']} | {b['check_in']} → {b['check_out']} | ${b['total_price']}\n"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="sse", host=settings.host, port=settings.port)
