"""
Phase 5 eval: multi-agent supervisor + worker routing.

Tests verify that the supervisor correctly routes requests to the right
specialist(s) and that the final response is coherent. Requires the full
stack to be running (docker compose up).

Run:
    cd phases/05_multi_agent/eval
    pytest test_multi_agent.py -v
"""

from __future__ import annotations

import pytest
import httpx

BASE = "http://localhost:8093"


@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=BASE, timeout=60.0) as c:
        yield c


# ── Health ────────────────────────────────────────────────────────────────────

def test_health(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Search-only routing ───────────────────────────────────────────────────────

def test_routes_to_search_agent_for_hotel_query(client):
    resp = client.post("/v1/chat", json={"message": "Find me luxury hotels in Dubai"})
    assert resp.status_code == 200
    data = resp.json()
    assert "search_agent" in data["workers_called"]
    assert data["response"]
    assert len(data["response"]) > 20


def test_routes_to_search_agent_for_availability_check(client):
    resp = client.post(
        "/v1/chat",
        json={"message": "Are there any available rooms in Paris for next week?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "search_agent" in data["workers_called"]


def test_search_response_mentions_hotels(client):
    resp = client.post(
        "/v1/chat",
        json={"message": "Show me beachfront hotels in Miami with a pool"},
    )
    assert resp.status_code == 200
    response_text = resp.json()["response"].lower()
    # Should mention hotel-related terms
    assert any(word in response_text for word in ["hotel", "resort", "property", "no hotels", "found"])


# ── Booking-only routing ──────────────────────────────────────────────────────

def test_routes_to_booking_agent_for_booking_lookup(client):
    fake_id = "00000000-0000-0000-0000-000000000001"
    resp = client.post(
        "/v1/chat",
        json={"message": f"What is the status of booking {fake_id}?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "booking_agent" in data["workers_called"]


def test_routes_to_booking_agent_for_cancellation(client):
    fake_id = "00000000-0000-0000-0000-000000000002"
    resp = client.post(
        "/v1/chat",
        json={"message": f"Please cancel my booking {fake_id}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "booking_agent" in data["workers_called"]


# ── Multi-step routing ────────────────────────────────────────────────────────

def test_search_then_book_calls_both_workers(client):
    """A 'find and book' request should invoke search_agent then booking_agent."""
    resp = client.post(
        "/v1/chat",
        json={
            "message": (
                "Find a 4-star hotel in London available from 2026-08-01 to 2026-08-05 "
                "and book it for guest john.doe@example.com"
            )
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    workers = data["workers_called"]
    assert "search_agent" in workers
    assert "booking_agent" in workers
    # search must come before booking
    assert workers.index("search_agent") < workers.index("booking_agent")


# ── Response quality ──────────────────────────────────────────────────────────

def test_response_is_non_empty_string(client):
    resp = client.post("/v1/chat", json={"message": "What hotels do you have in Tokyo?"})
    assert resp.status_code == 200
    assert isinstance(resp.json()["response"], str)
    assert resp.json()["response"].strip()


def test_session_id_echoed(client):
    resp = client.post(
        "/v1/chat",
        json={"message": "Hello", "session_id": "test-session-123"},
    )
    assert resp.status_code == 200
    assert resp.json()["session_id"] == "test-session-123"


# ── Error handling ────────────────────────────────────────────────────────────

def test_empty_message_returns_422(client):
    resp = client.post("/v1/chat", json={"message": ""})
    assert resp.status_code == 422


def test_whitespace_message_returns_422(client):
    resp = client.post("/v1/chat", json={"message": "   "})
    assert resp.status_code == 422
