"""
Smoke tests for PantauBumi API.

Runs against a real database (Neon PostgreSQL via DATABASE_URL in .env).
Tables are created before tests run via the FastAPI lifespan.
"""

import pytest
from fastapi.testclient import TestClient

# TestClient triggers the FastAPI lifespan (creates tables, starts scheduler)
from app.main import app

client = TestClient(app)


# ── Health ─────────────────────────────────────────────────────────────────────

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ── GET /risk ──────────────────────────────────────────────────────────────────

def test_get_risk():
    response = client.get("/risk", params={"lat": -6.2, "lng": 106.8})
    assert response.status_code == 200
    data = response.json()
    assert "flood_score" in data
    assert "landslide_score" in data
    assert "earthquake_score" in data
    assert data["overall_risk"] in ("low", "medium", "high", "critical")
    assert 0.0 <= data["flood_score"] <= 1.0
    assert 0.0 <= data["landslide_score"] <= 1.0
    assert 0.0 <= data["earthquake_score"] <= 1.0


def test_get_risk_out_of_bounds():
    # Latitude outside Indonesia validation range
    response = client.get("/risk", params={"lat": 50.0, "lng": 106.8})
    assert response.status_code == 422


# ── GET /alerts ────────────────────────────────────────────────────────────────

def test_get_alerts_returns_list():
    response = client.get("/alerts", params={"lat": -6.2, "lng": 106.8})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ── GET /evacuation ────────────────────────────────────────────────────────────

def test_get_evacuation_returns_list():
    response = client.get("/evacuation", params={"lat": -6.2, "lng": 106.8})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ── GET /reports ───────────────────────────────────────────────────────────────

def test_get_reports_returns_list():
    response = client.get(
        "/reports", params={"lat": -6.2, "lng": 106.8, "radius": 10}
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ── POST /reports ──────────────────────────────────────────────────────────────

def test_post_report_flood():
    payload = {
        "lat": -6.2,
        "lng": 106.8,
        "text": "Banjir parah di depan rumah saya, air sudah setinggi lutut!",
        "category": "flood",
    }
    response = client.post("/reports", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "verified" in data
    assert isinstance(data["verified"], bool)
    assert 0.0 <= data["verification_score"] <= 1.0


def test_post_report_too_short():
    payload = {"lat": -6.2, "lng": 106.8, "text": "Banjir", "category": "flood"}
    response = client.post("/reports", json=payload)
    assert response.status_code == 422


def test_post_report_then_visible_in_get():
    """A verified report should appear in the GET /reports response."""
    payload = {
        "lat": -6.21,
        "lng": 106.80,
        "text": "Tanah longsor terjadi di lereng bukit, warga diminta mengungsi segera!",
        "category": "landslide",
    }
    post_resp = client.post("/reports", json=payload)
    assert post_resp.status_code == 201
    created = post_resp.json()

    if created["verified"]:
        get_resp = client.get(
            "/reports", params={"lat": -6.21, "lng": 106.80, "radius": 5}
        )
        assert get_resp.status_code == 200
        ids = [r["id"] for r in get_resp.json()]
        assert created["id"] in ids


# ── POST /fcm-token ────────────────────────────────────────────────────────────

def test_post_fcm_token():
    payload = {
        "token": "test-fcm-registration-token-abcdef1234567890",
        "device_id": "test-device-001",
    }
    response = client.post("/fcm-token", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["token"] == payload["token"]


def test_post_fcm_token_upsert():
    """Posting the same token twice should succeed (upsert semantics)."""
    payload = {"token": "upsert-test-token-xyz9876543210abcdef", "device_id": "device-a"}
    assert client.post("/fcm-token", json=payload).status_code == 200
    payload["device_id"] = "device-b"
    assert client.post("/fcm-token", json=payload).status_code == 200


# ── Utility unit tests ─────────────────────────────────────────────────────────

def test_haversine_jakarta_surabaya():
    from app.utils.geo import haversine
    dist = haversine(-6.2088, 106.8456, -7.2575, 112.7521)
    assert 600 < dist < 720, f"Expected ~664 km, got {dist:.1f} km"


def test_earthquake_critical():
    from app.ai.earthquake_alert import assess_earthquake
    result = assess_earthquake(magnitude=6.5, distance_km=100)
    assert result.triggered and result.severity == "critical"


def test_earthquake_no_trigger():
    from app.ai.earthquake_alert import assess_earthquake
    result = assess_earthquake(magnitude=2.5, distance_km=600)
    assert not result.triggered and result.severity == "low"


def test_report_verifier_detects_flood():
    from app.ai.report_verifier import verify_report
    result = verify_report("Banjir besar melanda kampung kami, air sudah sangat tinggi!")
    assert result.is_valid and result.category == "flood"


def test_report_verifier_rejects_non_disaster():
    from app.ai.report_verifier import verify_report
    result = verify_report("Hari ini cuaca sangat cerah dan menyenangkan sekali.")
    assert not result.is_valid


def test_cache_get_set():
    from app.utils.cache import cache_set, cache_get
    cache_set("smoke_test_key", {"ok": True}, ttl=60)
    assert cache_get("smoke_test_key") == {"ok": True}
    assert cache_get("nonexistent_key") is None
