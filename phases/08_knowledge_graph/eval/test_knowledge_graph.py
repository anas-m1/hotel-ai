"""
Phase 8 eval: GraphRAG + Self-RAG knowledge graph search.

Run with full stack up:
    cd phases/08_knowledge_graph/eval
    pytest test_knowledge_graph.py -v
"""

from __future__ import annotations

import pytest
import httpx

BASE = "http://localhost:8094"


@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=BASE, timeout=60.0) as c:
        yield c


# ── Health ────────────────────────────────────────────────────────────────────

def test_health(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200


# ── Ingestion ─────────────────────────────────────────────────────────────────

def test_ingest_returns_count(client):
    resp = client.post("/v1/admin/ingest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["hotels_ingested"] >= 0


# ── Search — basic ────────────────────────────────────────────────────────────

def test_search_returns_results(client):
    resp = client.get("/v1/search", params={"query": "luxury hotel in Dubai"})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert isinstance(data["results"], list)


def test_search_response_shape(client):
    resp = client.get("/v1/search", params={"query": "hotel with pool in London"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "hotel with pool in London"
    assert "entities_extracted" in data
    assert "total_candidates" in data
    assert "self_rag_filtered" in data


def test_search_result_fields(client):
    resp = client.get("/v1/search", params={"query": "beachfront hotel"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    if results:
        r = results[0]
        assert "hotel_code" in r
        assert "name" in r
        assert "city_code" in r
        assert "rrf_score" in r
        assert "source" in r
        assert r["source"] in ("graph", "vector", "both")


# ── Entity extraction ─────────────────────────────────────────────────────────

def test_city_entity_extracted(client):
    resp = client.get("/v1/search", params={"query": "5 star hotel in Paris"})
    assert resp.status_code == 200
    entities = resp.json()["entities_extracted"]
    cities = [c.upper() for c in entities.get("cities", [])]
    assert "PARIS" in cities or "CDG" in cities or any("paris" in c.lower() for c in entities.get("cities", []))


def test_amenity_entity_extracted(client):
    resp = client.get("/v1/search", params={"query": "hotel with spa and gym"})
    assert resp.status_code == 200
    entities = resp.json()["entities_extracted"]
    amenities = [a.lower() for a in entities.get("amenities", [])]
    assert any("spa" in a for a in amenities) or any("gym" in a for a in amenities)


def test_star_rating_entity_extracted(client):
    resp = client.get("/v1/search", params={"query": "5 star hotel in Singapore"})
    assert resp.status_code == 200
    entities = resp.json()["entities_extracted"]
    assert entities.get("min_star_rating", 0) >= 4.0


# ── Limit parameter ───────────────────────────────────────────────────────────

def test_limit_respected(client):
    resp = client.get("/v1/search", params={"query": "hotel", "limit": 3})
    assert resp.status_code == 200
    assert len(resp.json()["results"]) <= 3


def test_max_limit(client):
    resp = client.get("/v1/search", params={"query": "hotel", "limit": 50})
    assert resp.status_code == 200


# ── Error handling ────────────────────────────────────────────────────────────

def test_empty_query_returns_422(client):
    resp = client.get("/v1/search", params={"query": ""})
    assert resp.status_code == 422


def test_missing_query_returns_422(client):
    resp = client.get("/v1/search")
    assert resp.status_code == 422
