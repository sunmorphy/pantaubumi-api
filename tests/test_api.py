"""
Smoke tests for PantauBumi API.

All responses are now wrapped in the standard envelope:
    {"code": int, "status": str, "message": str|null, "data": any}
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ok(resp, code=200):
    """Assert the response is a successful envelope and return the data payload."""
    assert resp.status_code == code, resp.text
    body = resp.json()
    assert body["code"] == code
    assert body["status"] in ("Success", "Created")
    return body["data"]


def _err(resp, code):
    """Assert the response is an error envelope with the given code."""
    assert resp.status_code == code, resp.text
    body = resp.json()
    assert body["code"] == code
    assert body["data"] is None
    assert body["message"] is not None
    return body


# ── Health ─────────────────────────────────────────────────────────────────────

def test_health_check():
    resp = client.get("/health")
    data = _ok(resp)
    assert data["service"] == "pantau-bumi-api"


# ── GET /risk ──────────────────────────────────────────────────────────────────

def test_get_risk():
    resp = client.get("/risk", params={"lat": -6.2, "lng": 106.8})
    data = _ok(resp)
    assert "flood_score" in data
    assert "landslide_score" in data
    assert "earthquake_score" in data
    assert data["overall_risk"] in ("low", "medium", "high", "critical")
    assert 0.0 <= data["flood_score"] <= 1.0


def test_get_risk_out_of_bounds():
    resp = client.get("/risk", params={"lat": 50.0, "lng": 106.8})
    body = _err(resp, 422)
    assert "lat" in body["message"].lower() or "latitude" in body["message"].lower()


# ── GET /alerts ────────────────────────────────────────────────────────────────

def test_get_alerts_returns_list():
    resp = client.get("/alerts", params={"lat": -6.2, "lng": 106.8})
    data = _ok(resp)
    assert isinstance(data, list)


# ── GET /evacuation ────────────────────────────────────────────────────────────

def test_get_evacuation_returns_list():
    resp = client.get("/evacuation", params={"lat": -6.2, "lng": 106.8})
    data = _ok(resp)
    assert isinstance(data, list)


# ── GET /reports ───────────────────────────────────────────────────────────────

def test_get_reports_returns_list():
    resp = client.get("/reports", params={"lat": -6.2, "lng": 106.8, "radius": 10})
    data = _ok(resp)
    assert isinstance(data, list)


# ── POST /reports ──────────────────────────────────────────────────────────────

def test_post_report_flood():
    payload = {
        "lat": -6.2, "lng": 106.8,
        "text": "Banjir parah di depan rumah saya, air sudah setinggi lutut!",
        "category": "flood",
    }
    resp = client.post("/reports", json=payload)
    data = _ok(resp, 201)
    assert "id" in data
    assert isinstance(data["verified"], bool)
    assert 0.0 <= data["verification_score"] <= 1.0


def test_post_report_too_short():
    payload = {"lat": -6.2, "lng": 106.8, "text": "Banjir", "category": "flood"}
    _err(client.post("/reports", json=payload), 422)


def test_post_report_then_visible_in_get():
    payload = {
        "lat": -6.21, "lng": 106.80,
        "text": "Tanah longsor terjadi di lereng bukit, warga diminta mengungsi segera!",
        "category": "landslide",
    }
    post_resp = client.post("/reports", json=payload)
    created = _ok(post_resp, 201)

    if created["verified"]:
        get_resp = client.get("/reports", params={"lat": -6.21, "lng": 106.80, "radius": 5})
        data = _ok(get_resp)
        ids = [r["id"] for r in data]
        assert created["id"] in ids


# ── POST /fcm-token ────────────────────────────────────────────────────────────

def test_post_fcm_token():
    payload = {"token": "test-fcm-registration-token-abcdef1234567890", "device_id": "test-device-001"}
    data = _ok(client.post("/fcm-token", json=payload))
    assert "id" in data
    assert data["token"] == payload["token"]


def test_post_fcm_token_upsert():
    payload = {"token": "upsert-test-token-xyz9876543210abcdef", "device_id": "device-a"}
    _ok(client.post("/fcm-token", json=payload))
    payload["device_id"] = "device-b"
    _ok(client.post("/fcm-token", json=payload))


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
