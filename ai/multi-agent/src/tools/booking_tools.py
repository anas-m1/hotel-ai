"""Tools available to the booking specialist agent."""

from __future__ import annotations

import httpx
from langchain_core.tools import tool

from config import settings


@tool
async def get_guest(email: str) -> str:
    """Look up a guest profile by email address.

    Args:
        email: Guest's email address.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.booking_ops_url}/v1/guests/by-email",
            params={"email": email},
        )
        if resp.status_code == 404:
            return f"No guest found with email {email}."
        resp.raise_for_status()
        g = resp.json()
    return f"Guest found: {g['first_name']} {g['last_name']} (id={g['guest_id']}, email={g['email']})"


@tool
async def create_guest(first_name: str, last_name: str, email: str, phone: str = "") -> str:
    """Create a new guest profile.

    Args:
        first_name: Guest's first name.
        last_name: Guest's last name.
        email: Guest's email address.
        phone: Optional phone number.
    """
    body = {"first_name": first_name, "last_name": last_name, "email": email}
    if phone:
        body["phone"] = phone

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"{settings.booking_ops_url}/v1/guests", json=body)
        if resp.status_code == 409:
            return f"A guest with email {email} already exists. Use get_guest to look them up."
        resp.raise_for_status()
        g = resp.json()
    return f"Guest created: {g['first_name']} {g['last_name']} (id={g['guest_id']})"


@tool
async def book_room(
    guest_id: str,
    hotel_code: str,
    room_id: str,
    check_in: str,
    check_out: str,
) -> str:
    """Create a new booking for a guest.

    Args:
        guest_id: UUID of the guest making the booking.
        hotel_code: Hotel identifier.
        room_id: UUID of the room to book.
        check_in: Check-in date (YYYY-MM-DD).
        check_out: Check-out date (YYYY-MM-DD).
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
            return f"Room {room_id} is no longer available for those dates (conflict). Please search for another room."
        if resp.status_code == 422:
            return f"Invalid booking details: {resp.json().get('message', resp.text)}"
        resp.raise_for_status()
        b = resp.json()
    return (
        f"Booking confirmed! ID={b['booking_id']} | "
        f"{hotel_code} room {room_id} | "
        f"{check_in} → {check_out} | "
        f"Total: ${b['total_price']}"
    )


@tool
async def get_booking(booking_id: str) -> str:
    """Retrieve details of an existing booking.

    Args:
        booking_id: UUID of the booking to look up.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{settings.booking_ops_url}/v1/bookings/{booking_id}")
        if resp.status_code == 404:
            return f"Booking {booking_id} not found."
        resp.raise_for_status()
        b = resp.json()
    return (
        f"Booking {b['booking_id']}: status={b['status']} | "
        f"hotel={b['hotel_code']} | "
        f"{b['check_in']} → {b['check_out']} | "
        f"Total: ${b['total_price']}"
    )


@tool
async def cancel_booking(booking_id: str) -> str:
    """Cancel an existing booking.

    Args:
        booking_id: UUID of the booking to cancel.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.delete(f"{settings.booking_ops_url}/v1/bookings/{booking_id}")
        if resp.status_code == 404:
            return f"Booking {booking_id} not found."
        if resp.status_code == 409:
            return f"Booking {booking_id} cannot be cancelled in its current state."
        resp.raise_for_status()
    return f"Booking {booking_id} has been cancelled."


BOOKING_TOOLS = [get_guest, create_guest, book_room, get_booking, cancel_booking]
