"""Live backend contract test; excludes model inference and Telegram transport.

Opt in only against a disposable local stack:
    HOTEL_AI_E2E=1 uv run --locked --project ai/booking-assistant pytest tests/e2e -v

Creates one fictional guest and cancels its reservation in a finally block.
The guest remains as test data. Telegram and model behavior have separate checks.
"""

import os
import uuid
from datetime import date, timedelta
from decimal import Decimal

import httpx
import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.environ.get("HOTEL_AI_E2E") != "1", reason="Live database writes require HOTEL_AI_E2E=1"
    ),
]
INVENTORY = os.environ.get("HOTEL_INVENTORY_URL", "http://localhost:8080")
BOOKINGS = os.environ.get("BOOKING_OPS_URL", "http://localhost:8081")


def test_reservation_lifecycle():
    with httpx.Client(timeout=30) as client:
        for service in [INVENTORY, BOOKINGS]:
            response = client.get(service + "/healthz")
            response.raise_for_status()
        response = client.get(INVENTORY + "/v1/hotels")
        response.raise_for_status()
        hotels = response.json()
        assert hotels, "Seed the local catalog before running E2E checks"
        start = date.today() + timedelta(days=180 + uuid.uuid4().int % 180)
        end = start + timedelta(days=2)
        chosen = None
        for hotel in hotels:
            response = client.get(f"{INVENTORY}/v1/hotels/{hotel['hotel_code']}/rooms")
            response.raise_for_status()
            for room in response.json():
                params = {
                    "room_id": room["id"],
                    "check_in": start.isoformat(),
                    "check_out": end.isoformat(),
                }
                available = client.get(BOOKINGS + "/v1/availability", params=params)
                available.raise_for_status()
                if available.json()["available"]:
                    chosen = (hotel, room, params)
                    break
            if chosen:
                break
        assert chosen, "No available seeded room for test dates"
        hotel, room, params = chosen
        guest_response = client.post(
            BOOKINGS + "/v1/guests",
            json={
                "first_name": "E2E",
                "last_name": "Demo",
                "email": f"e2e-{uuid.uuid4()}@example.com",
            },
        )
        guest_response.raise_for_status()
        guest = guest_response.json()
        payload = {
            "guest_id": guest["id"],
            "hotel_code": hotel["hotel_code"],
            "room_id": room["id"],
            "check_in_date": start.isoformat(),
            "check_out_date": end.isoformat(),
            "total_price": str(Decimal(room["base_price"]) * 2),
            "currency": room["currency"],
        }
        created = client.post(BOOKINGS + "/v1/bookings", json=payload)
        assert created.status_code == 201
        booking_id = created.json()["id"]
        try:
            fetched = client.get(f"{BOOKINGS}/v1/bookings/{booking_id}")
            fetched.raise_for_status()
            assert fetched.json()["guest_id"] == guest["id"]
            assert fetched.json()["room_id"] == room["id"]
            available = client.get(BOOKINGS + "/v1/availability", params=params)
            available.raise_for_status()
            assert available.json()["available"] is False
            duplicate = client.post(BOOKINGS + "/v1/bookings", json=payload)
            assert duplicate.status_code == 409
        finally:
            cancelled = client.delete(f"{BOOKINGS}/v1/bookings/{booking_id}")
            assert cancelled.status_code in [200, 204]
        fetched = client.get(f"{BOOKINGS}/v1/bookings/{booking_id}")
        fetched.raise_for_status()
        assert fetched.json()["status"] == "cancelled"
        available = client.get(BOOKINGS + "/v1/availability", params=params)
        available.raise_for_status()
        assert available.json()["available"] is True
