"""
Smoke tests for PantauBumi API.

All responses are now wrapped in the standard envelope:
    {"code": int, "status": str, "message": str|null, "data": any}
"""

import uuid
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


def _device_headers(device_id: str = None) -> dict:
    """Return headers dict with a unique X-Device-ID."""
    return {"X-Device-ID": device_id or str(uuid.uuid4())}


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
    # Bounds: lat (-11, 7), lng (95, 141)
    # This should fail validation
    _err(client.get("/risk", params={"lat": 10.0, "lng": 106.8}), 422)
    _err(client.get("/risk", params={"lat": -6.2, "lng": 150.0}), 422)


def test_get_risk_zones():
    resp = client.get(
        "/risk/zones",
        params={
            "min_lat": -6.3,
            "max_lat": -6.1,
            "min_lng": 106.7,
            "max_lng": 106.9,
        },
    )
    data = _ok(resp)
    assert isinstance(data, list)
    assert len(data) == 9  # 3x3 grid
    
    # Check that individual points have expected keys
    first = data[0]
    assert "flood_score" in first
    assert "landslide_score" in first
    assert "earthquake_score" in first
    assert first["overall_risk"] in ("low", "medium", "high", "critical")



def test_get_risk_out_of_bounds():
    resp = client.get("/risk", params={"lat": 50.0, "lng": 106.8})
    body = _err(resp, 422)
    assert "lat" in body["message"].lower() or "latitude" in body["message"].lower()


# ── GET /alerts ────────────────────────────────────────────────────────────────

def test_get_alerts_returns_paginated_response():
    resp = client.get("/alerts", params={"lat": -6.2, "lng": 106.8})
    data = _ok(resp)
    # Response shape: {items: [...], next_cursor: int|null, has_more: bool}
    assert isinstance(data, dict)
    assert "items" in data
    assert "next_cursor" in data
    assert "has_more" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["has_more"], bool)
    assert data["next_cursor"] is None or isinstance(data["next_cursor"], int)


def test_get_alerts_pagination_cursor():
    """Passing before_id should filter results — returns 200 with valid envelope."""
    resp = client.get("/alerts", params={"lat": -6.2, "lng": 106.8, "limit": 1, "before_id": 999999})
    data = _ok(resp)
    assert isinstance(data["items"], list)


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


def test_get_reports_category_filter():
    """Test that the category query param correctly filters results."""
    # Note: we assume the test DB has random records, so we just test the param is accepted
    resp = client.get("/reports", params={"lat": -6.2, "lng": 106.8, "radius": 10, "category": "flood"})
    data = _ok(resp)
    assert isinstance(data, list)
    for report in data:
        assert report["category"] == "flood"


def test_get_reports_limit():
    """Test that the limit query param correctly restricts the number of results."""
    resp = client.get("/reports", params={"lat": -6.2, "lng": 106.8, "limit": 2})
    data = _ok(resp)
    assert isinstance(data, list)
    assert len(data) <= 2

    # Test max limit constraint
    resp_err = client.get("/reports", params={"lat": -6.2, "lng": 106.8, "limit": 101})
    _err(resp_err, 422)


# ── POST /reports ──────────────────────────────────────────────────────────────

def test_post_report_flood():
    payload = {
        "lat": -6.2, "lng": 106.8,
        "text": "Banjir parah di depan rumah saya, air sudah setinggi lutut!",
        "category": "flood",
    }
    resp = client.post("/reports", data=payload, headers=_device_headers())
    data = _ok(resp, 201)
    assert "id" in data
    assert isinstance(data["verified"], bool)
    assert 0.0 <= data["verification_score"] <= 1.0
    assert "flag_count" in data
    # device_id must NOT be in the response
    assert "device_id" not in data


def test_post_report_too_short():
    payload = {"lat": -6.2, "lng": 106.8, "text": "Banjir", "category": "flood"}
    _err(client.post("/reports", data=payload), 422)


from unittest.mock import AsyncMock, patch

@patch("app.services.storage.upload_image_to_storage", new_callable=AsyncMock)
def test_post_report_with_image(mock_upload):
    mock_upload.return_value = "https://example.com/mock_image.jpg"
    
    payload = {
        "lat": -6.2, "lng": 106.8,
        "text": "Banjir parah di depan rumah saya, air sudah setinggi lutut!",
        "category": "flood",
    }
    files = {"image": ("photo.jpg", b"fake-image-bytes", "image/jpeg")}
    
    resp = client.post("/reports", data=payload, files=files, headers=_device_headers())
    data = _ok(resp, 201)
    
    assert data["image_url"] == "https://example.com/mock_image.jpg"
    mock_upload.assert_called_once()


def test_post_report_then_visible_in_get():
    payload = {
        "lat": -6.21, "lng": 106.80,
        "text": "Tanah longsor terjadi di lereng bukit, warga diminta mengungsi segera!",
        "category": "landslide",
    }
    post_resp = client.post("/reports", data=payload, headers=_device_headers())
    created = _ok(post_resp, 201)

    if created["verified"]:
        get_resp = client.get("/reports", params={"lat": -6.21, "lng": 106.80, "radius": 5})
        data = _ok(get_resp)
        ids = [r["id"] for r in data]
        assert created["id"] in ids


# ── GET /weather ───────────────────────────────────────────────────────────────

def test_get_weather():
    resp = client.get("/weather", params={"lat": -6.2, "lng": 106.8})
    data = _ok(resp)
    assert "rainfall_mm_per_hour" in data
    assert "river_level_m" in data
    assert "river_level_delta_per_hour" in data
    assert "latest_magnitude" in data
    assert "recorded_at" in data
    assert isinstance(data["rainfall_mm_per_hour"], float)
    assert isinstance(data["river_level_m"], float)
    assert isinstance(data["river_level_delta_per_hour"], float)
    assert data["latest_magnitude"] is None or isinstance(data["latest_magnitude"], float)


# ── Device rate limiting ───────────────────────────────────────────────────────

def test_device_cooldown_enforced():
    """Same device ID cannot submit two reports within the cooldown window."""
    device_id = str(uuid.uuid4())
    headers = _device_headers(device_id)
    payload = {
        "lat": -6.3, "lng": 106.9,
        "text": "Banjir parah melanda kawasan ini, jalan sudah tidak bisa dilalui!",
        "category": "flood",
    }

    # First submission should succeed
    r1 = client.post("/reports", data=payload, headers=headers)
    assert r1.status_code == 201, r1.text

    # Immediate second submission should be blocked by cooldown
    r2 = client.post("/reports", data=payload, headers=headers)
    assert r2.status_code == 429, r2.text
    body = r2.json()
    assert body["code"] == 429
    assert "minute" in body["message"].lower()


# ── Report flagging ────────────────────────────────────────────────────────────

def _submit_report(text_suffix: str = "") -> int:
    """Submit a new verified-looking report and return its ID."""
    payload = {
        "lat": -6.5, "lng": 107.2,
        "text": f"Banjir besar dan parah di wilayah ini, air terus naik! {text_suffix}",
        "category": "flood",
    }
    resp = client.post("/reports", data=payload, headers=_device_headers())
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def test_flag_report_once():
    """Flag a report with one device — flag_count increases, report stays visible."""
    report_id = _submit_report("flag_once")
    resp = client.post(f"/reports/{report_id}/flag", headers=_device_headers())
    data = _ok(resp)
    assert data["report_id"] == report_id
    assert data["flag_count"] == 1
    assert data["hidden"] is False


def test_flag_report_double_rejected():
    """Same device cannot flag the same report twice (409)."""
    report_id = _submit_report("double_flag")
    headers = _device_headers()
    client.post(f"/reports/{report_id}/flag", headers=headers)
    resp = client.post(f"/reports/{report_id}/flag", headers=headers)
    _err(resp, 409)


def test_flag_report_auto_hide():
    """Three unique devices flagging the same report hides it from GET /reports."""
    report_id = _submit_report("auto_hide")

    for _ in range(FLAG_HIDE_THRESHOLD := 3):
        resp = client.post(f"/reports/{report_id}/flag", headers=_device_headers())
        data = _ok(resp)

    # Last flag response should indicate hidden
    assert data["flag_count"] == FLAG_HIDE_THRESHOLD
    assert data["hidden"] is True

    # The report should no longer appear in GET /reports
    list_resp = client.get("/reports", params={"lat": -6.5, "lng": 107.2, "radius": 50})
    ids = [r["id"] for r in _ok(list_resp)]
    assert report_id not in ids


def test_flag_nonexistent_report():
    """Flagging a report that doesn't exist returns 404."""
    resp = client.post("/reports/999999/flag", headers=_device_headers())
    _err(resp, 404)


# ── FCM Token ──────────────────────────────────────────────────────────────────

def test_post_fcm_token():
    payload = {"token": "test-fcm-token-1", "device_id": "test-device-1"}
    resp = client.post("/fcm-token", data=payload)
    data = _ok(resp)
    assert data["token"] == "test-fcm-token-1"
    assert data["device_id"] == "test-device-1"

def test_post_fcm_token_upsert():
    # Update same token with new device ID
    payload = {"token": "test-fcm-token-1", "device_id": "test-device-2"}
    resp = client.post("/fcm-token", json=payload)
    data = _ok(resp)
    assert data["token"] == "test-fcm-token-1"
    assert data["device_id"] == "test-device-2"

def test_delete_fcm_token():
    # First, let's create a token specifically for deletion testing
    payload = {"token": "test-fcm-token-to-delete", "device_id": "test-device-del"}
    client.post("/fcm-token", json=payload)

    # Now, let's delete it
    resp = client.delete("/fcm-token", params={"token": "test-fcm-token-to-delete"})
    _ok(resp)

    # Let's try to delete it again to ensure 404
    resp = client.delete("/fcm-token", params={"token": "test-fcm-token-to-delete"})
    _err(resp, 404)



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
