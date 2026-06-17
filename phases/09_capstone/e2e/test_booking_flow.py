"""
Phase 9 end-to-end test: complete hotel booking flow.

Tests the full golden path across all services running together:
  1. Health check all services
  2. Search for hotels (RAG pipeline)
  3. GraphRAG search (knowledge graph)
  4. Get hotel details and list rooms
  5. Check room availability
  6. Create a guest
  7. Book a room via the booking assistant agent
  8. Retrieve and verify the booking
  9. Cancel the booking

Run with full stack up:
    docker compose -f infra/docker/docker-compose.yml up -d
    cd phases/09_capstone/e2e
    pytest test_booking_flow.py -v -s
"""

from __future__ import annotations

import uuid
import pytest
import httpx

HOTEL_INVENTORY = "http://localhost:8080"
BOOKING_OPS     = "http://localhost:8081"
LLM_GATEWAY     = "http://localhost:8090"
RAG_PIPELINE    = "http://localhost:8091"
BOOKING_ASST    = "http://localhost:8092"
MULTI_AGENT     = "http://localhost:8093"
KNOWLEDGE_GRAPH = "http://localhost:8094"

TIMEOUT = 60.0


@pytest.fixture(scope="session")
def http():
    with httpx.Client(timeout=TIMEOUT) as c:
        yield c


# ── 1. Health checks ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("url,name", [
    (HOTEL_INVENTORY, "hotel-inventory"),
    (BOOKING_OPS,     "booking-ops"),
    (LLM_GATEWAY,     "llm-gateway"),
    (RAG_PIPELINE,    "rag-pipeline"),
    (BOOKING_ASST,    "booking-assistant"),
    (MULTI_AGENT,     "multi-agent"),
    (KNOWLEDGE_GRAPH, "knowledge-graph"),
])
def test_service_health(http, url, name):
    resp = http.get(f"{url}/healthz")
    assert resp.status_code == 200, f"{name} is not healthy"


# ── 2. Hotel inventory ────────────────────────────────────────────────────────

def test_list_hotels(http):
    resp = http.get(f"{HOTEL_INVENTORY}/v1/hotels")
    assert resp.status_code == 200
    hotels = resp.json()
    assert isinstance(hotels, list)
    assert len(hotels) > 0, "No hotels in inventory — seed some data first"


def test_get_hotel(http):
    hotels = http.get(f"{HOTEL_INVENTORY}/v1/hotels").json()
    hotel_code = hotels[0]["hotel_code"]

    resp = http.get(f"{HOTEL_INVENTORY}/v1/hotels/{hotel_code}")
    assert resp.status_code == 200
    hotel = resp.json()
    assert hotel["hotel_code"] == hotel_code
    assert "name" in hotel


def test_list_rooms(http):
    hotels = http.get(f"{HOTEL_INVENTORY}/v1/hotels").json()
    hotel_code = hotels[0]["hotel_code"]

    resp = http.get(f"{HOTEL_INVENTORY}/v1/hotels/{hotel_code}/rooms")
    assert resp.status_code == 200
    rooms = resp.json()
    assert len(rooms) > 0, f"No rooms found for hotel {hotel_code}"


# ── 3. RAG search ─────────────────────────────────────────────────────────────

def test_semantic_search(http):
    resp = http.get(f"{RAG_PIPELINE}/v1/search", params={"query": "luxury hotel with pool"})
    assert resp.status_code == 200
    results = resp.json()
    assert isinstance(results, list)


# ── 4. GraphRAG search ────────────────────────────────────────────────────────

def test_graphrag_search(http):
    resp = http.get(
        f"{KNOWLEDGE_GRAPH}/v1/search",
        params={"query": "hotel with spa near city centre"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "entities_extracted" in data


# ── 5–9. Full booking flow ────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def available_room(http):
    """Find any hotel + room that can be booked for test dates."""
    hotels = http.get(f"{HOTEL_INVENTORY}/v1/hotels").json()
    check_in  = "2027-03-01"
    check_out = "2027-03-05"

    for hotel in hotels:
        code = hotel["hotel_code"]
        rooms = http.get(f"{HOTEL_INVENTORY}/v1/hotels/{code}/rooms").json()
        for room in rooms:
            avail = http.get(
                f"{HOTEL_INVENTORY}/v1/hotels/{code}/rooms/{room['room_id']}/availability",
                params={"check_in": check_in, "check_out": check_out},
            ).json()
            if avail.get("available"):
                return {
                    "hotel_code": code,
                    "room_id": room["room_id"],
                    "check_in": check_in,
                    "check_out": check_out,
                    "total_price": avail["total_price"],
                }

    pytest.skip("No available rooms found for test dates")


@pytest.fixture(scope="module")
def guest(http):
    """Create a unique test guest."""
    unique = str(uuid.uuid4())[:8]
    resp = http.post(
        f"{BOOKING_OPS}/v1/guests",
        json={
            "first_name": "E2E",
            "last_name": "Test",
            "email": f"e2e-{unique}@test.hotel-ai",
            "phone": "+1-555-0100",
        },
    )
    assert resp.status_code in (200, 201), f"Failed to create guest: {resp.text}"
    return resp.json()


def test_create_guest(guest):
    assert "guest_id" in guest
    assert guest["email"].startswith("e2e-")


def test_check_availability(http, available_room):
    room = available_room
    resp = http.get(
        f"{HOTEL_INVENTORY}/v1/hotels/{room['hotel_code']}/rooms/{room['room_id']}/availability",
        params={"check_in": room["check_in"], "check_out": room["check_out"]},
    )
    assert resp.status_code == 200
    assert resp.json()["available"] is True


@pytest.fixture(scope="module")
def booking(http, guest, available_room):
    """Create a booking via booking-ops directly."""
    room = available_room
    resp = http.post(
        f"{BOOKING_OPS}/v1/bookings",
        json={
            "guest_id": guest["guest_id"],
            "hotel_code": room["hotel_code"],
            "room_id": room["room_id"],
            "check_in": room["check_in"],
            "check_out": room["check_out"],
        },
    )
    assert resp.status_code in (200, 201), f"Failed to create booking: {resp.text}"
    return resp.json()


def test_booking_created(booking):
    assert "booking_id" in booking
    assert booking["status"] in ("confirmed", "pending")
    assert booking["total_price"]


def test_get_booking(http, booking):
    resp = http.get(f"{BOOKING_OPS}/v1/bookings/{booking['booking_id']}")
    assert resp.status_code == 200
    fetched = resp.json()
    assert fetched["booking_id"] == booking["booking_id"]
    assert fetched["guest_id"] == booking["guest_id"]


def test_booking_assistant_chat(http):
    """Single turn: agent search query returns a non-empty response."""
    session_id = f"e2e-{uuid.uuid4()}"
    resp = http.post(
        f"{BOOKING_ASST}/v1/chat",
        json={"message": "What hotels do you have available?", "session_id": session_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"]
    assert data["session_id"] == session_id


def test_multi_agent_search(http):
    """Multi-agent: search request routes to search_agent."""
    resp = http.post(
        f"{MULTI_AGENT}/v1/chat",
        json={"message": "Find luxury hotels with a spa"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "search_agent" in data["workers_called"]
    assert data["response"]


def test_cancel_booking(http, booking):
    resp = http.delete(f"{BOOKING_OPS}/v1/bookings/{booking['booking_id']}")
    assert resp.status_code in (200, 204)


def test_booking_is_cancelled(http, booking):
    resp = http.get(f"{BOOKING_OPS}/v1/bookings/{booking['booking_id']}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
