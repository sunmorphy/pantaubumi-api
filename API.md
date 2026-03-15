# PantauBumi API Documentation

**Base URL (local):** `http://localhost:8000`  
**Base URL (production):** `https://your-app.up.railway.app`  
**Interactive Docs:** `{base_url}/docs` (dev only — disabled in production)

---

## Authentication

MVP: no authentication required. Rate limiting is enforced per device ID and per IP address.

---

## Response Envelope

**Every** response — success or error — is wrapped in the same envelope:

```json
{
  "code":    200,
  "status":  "Success",
  "message": null,
  "data":    { }
}
```

| Field | Type | Description |
|---|---|---|
| `code` | int | HTTP status code |
| `status` | string | Human-readable label |
| `message` | string \| null | Error detail or `null` on success |
| `data` | object \| array \| null | Payload on success, `null` on error |

**Status labels:**

| Code | Status |
|---|---|
| 200 | `Success` |
| 201 | `Created` |
| 404 | `Not Found` |
| 409 | `Conflict` |
| 422 | `Unprocessable Entity` |
| 429 | `Too Many Requests` |
| 500 | `Internal Server Error` |

---

## Anonymous Device Identity

The Android app generates a UUID on first install and sends it silently on every report-related request. This gives the backend a stable, privacy-preserving device identity with zero login UI.

```
X-Device-ID: 550e8400-e29b-41d4-a716-446655440000
```

- Generated once with `UUID.randomUUID()` and persisted in `SharedPreferences`
- **Never** returned in any API response
- Used only for server-side rate limiting and cooldown enforcement
- If omitted, IP-based limiting still applies

---

## Rate Limits

| Endpoint | Limit |
|---|---|
| All endpoints (global, per IP) | 60 req / min |
| `POST /reports` (per device ID) | **5 reports / hour** |
| `POST /reports` cooldown (per device ID) | **10-minute wait** between submissions |
| `POST /reports/{id}/flag` | 30 req / min / IP |
| `POST /fcm-token` | 20 req / min / IP |

**429 response:**
```json
{
  "code": 429,
  "status": "Too Many Requests",
  "message": "Please wait 8 minute(s) before submitting another report.",
  "data": null
}
```

---

## Endpoints

---

### `GET /health`

**Response `200`**
```json
{
  "code": 200,
  "status": "Success",
  "message": null,
  "data": { "service": "pantau-bumi-api" }
}
```

---

### `GET /risk`
AI-computed disaster risk scores for a coordinate.

#### Query Parameters

| Parameter | Type | Required | Constraints |
|---|---|---|---|
| `lat` | float | ✅ | -11.0 ≤ lat ≤ 7.0 |
| `lng` | float | ✅ | 95.0 ≤ lng ≤ 141.0 |

#### Response `200`
```json
{
  "code": 200,
  "status": "Success",
  "message": null,
  "data": {
    "lat": -6.2,
    "lng": 106.8,
    "flood_score": 0.73,
    "landslide_score": 0.41,
    "earthquake_score": 0.12,
    "overall_risk": "high",
    "computed_at": "2026-03-14T04:00:00Z"
  }
}
```

**Overall risk thresholds:** ≥0.75 → `critical` · ≥0.50 → `high` · ≥0.25 → `medium` · else → `low`

#### Example
```bash
curl "http://localhost:8000/risk?lat=-6.2&lng=106.8"
```

---

### `GET /alerts`
Recent disaster alerts near a coordinate.

#### Query Parameters

| Parameter | Type | Required | Default |
|---|---|---|---|
| `lat` | float | ✅ | — |
| `lng` | float | ✅ | — |
| `radius_km` | float | ❌ | `100.0` |
| `hours` | int | ❌ | `24` (max 168) |

#### Response `200`
```json
{
  "code": 200,
  "status": "Success",
  "message": null,
  "data": [
    {
      "id": 42,
      "type": "earthquake",
      "lat": -6.5,
      "lng": 107.1,
      "severity": "high",
      "message": "[USGS] Gempa signifikan M5.2 sejauh 85 km. Bersiaplah.",
      "source": "usgs",
      "created_at": "2026-03-14T03:55:00Z"
    }
  ]
}
```

#### Example
```bash
curl "http://localhost:8000/alerts?lat=-6.2&lng=106.8&radius_km=50&hours=6"
```

---

### `GET /evacuation`
Nearest evacuation shelters sorted by distance.

#### Query Parameters

| Parameter | Type | Required | Default |
|---|---|---|---|
| `lat` | float | ✅ | — |
| `lng` | float | ✅ | — |
| `limit` | int | ❌ | `5` (max 10) |

#### Response `200`
```json
{
  "code": 200,
  "status": "Success",
  "message": null,
  "data": [
    {
      "id": 1,
      "name": "Gedung Serbaguna RW 05",
      "lat": -6.201,
      "lng": 106.849,
      "capacity": 200,
      "type": "community_hall",
      "address": "Jl. Merdeka No. 1, Jakarta Pusat",
      "distance_km": 0.18
    }
  ]
}
```

#### Example
```bash
curl "http://localhost:8000/evacuation?lat=-6.2&lng=106.8&limit=3"
```

---

### `GET /reports`
Verified community disaster reports within a radius.

Only returns reports where **`verified=true` AND `visible=true`**. Reports auto-hidden by 3+ flags are excluded.

#### Query Parameters

| Parameter | Type | Required | Default |
|---|---|---|---|
| `lat` | float | ✅ | — |
| `lng` | float | ✅ | — |
| `radius` | float | ❌ | `10.0` (max 500) |

#### Response `200`
```json
{
  "code": 200,
  "status": "Success",
  "message": null,
  "data": [
    {
      "id": 15,
      "lat": -6.21,
      "lng": 106.80,
      "text": "Banjir parah di depan rumah saya, air sudah setinggi lutut!",
      "category": "flood",
      "verified": true,
      "verification_score": 0.85,
      "source": "user",
      "flag_count": 0,
      "created_at": "2026-03-14T03:40:00Z"
    }
  ]
}
```

#### Example
```bash
curl "http://localhost:8000/reports?lat=-6.2&lng=106.8&radius=5"
```

---

### `POST /reports`
Submit a community disaster report. Auto-verified by NLP classifier.

**Headers:**

| Header | Required | Description |
|---|---|---|
| `X-Device-ID` | Recommended | Anonymous device UUID for per-device rate limiting |

**Rate limit:** 5 reports / hour / device · 10-minute cooldown between submissions

#### Request Body
```json
{
  "lat": -6.2,
  "lng": 106.8,
  "text": "Banjir besar melanda kampung kami, air sudah setinggi dada!",
  "category": "flood"
}
```

| Field | Type | Required | Constraints |
|---|---|---|---|
| `lat` | float | ✅ | — |
| `lng` | float | ✅ | — |
| `text` | string | ✅ | 10–2000 chars |
| `category` | string | ❌ | default `"other"` |

#### Response `201`
```json
{
  "code": 201,
  "status": "Created",
  "message": null,
  "data": {
    "id": 16,
    "lat": -6.2,
    "lng": 106.8,
    "text": "Banjir besar melanda kampung kami, air sudah setinggi dada!",
    "category": "flood",
    "verified": true,
    "verification_score": 0.85,
    "source": "user",
    "flag_count": 0,
    "created_at": "2026-03-14T04:10:00Z"
  }
}
```

> **Note:** `device_id` is intentionally excluded from the response to protect anonymity.

#### Error `429` — Rate limit / cooldown
```json
{ "code": 429, "status": "Too Many Requests", "message": "Please wait 7 minute(s) before submitting another report.", "data": null }
```

#### Example
```bash
curl -X POST http://localhost:8000/reports \
  -H "Content-Type: application/json" \
  -H "X-Device-ID: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{"lat":-6.2,"lng":106.8,"text":"Tanah longsor di lereng bukit, ada rumah yang tertimbun!","category":"landslide"}'
```

---

### `POST /reports/{id}/flag`
Flag a report as inaccurate or a hoax.

**Headers:**

| Header | Required | Description |
|---|---|---|
| `X-Device-ID` | Recommended | Prevents same device flagging twice |

**Rate limit:** 30 req / min / IP

#### Response `200`
```json
{
  "code": 200,
  "status": "Success",
  "message": null,
  "data": {
    "report_id": 16,
    "flag_count": 2,
    "hidden": false
  }
}
```

| Field | Type | Description |
|---|---|---|
| `flag_count` | int | Total flags on this report |
| `hidden` | bool | `true` if report was auto-hidden (≥3 flags) |

#### Error `409` — Already flagged
```json
{ "code": 409, "status": "Conflict", "message": "You have already flagged this report.", "data": null }
```

#### Error `404` — Report not found
```json
{ "code": 404, "status": "Not Found", "message": "Report not found.", "data": null }
```

#### Example
```bash
curl -X POST http://localhost:8000/reports/16/flag \
  -H "X-Device-ID: 550e8400-e29b-41d4-a716-446655440000"
```

---

### `POST /fcm-token`
Register or update a device FCM push notification token. Idempotent (upsert).

**Rate limit:** 20 req / min / IP

#### Request Body
```json
{
  "token": "eNGvgqk5T6q:APA91bHPRgkFjJiNvmMqLwV...",
  "device_id": "android-device-uuid-1234"
}
```

#### Response `200`
```json
{
  "code": 200,
  "status": "Success",
  "message": null,
  "data": {
    "id": 3,
    "token": "eNGvgqk5T6q:APA91bHPRgkFjJiNvmMqLwV...",
    "device_id": "android-device-uuid-1234"
  }
}
```

#### Example
```bash
curl -X POST http://localhost:8000/fcm-token \
  -H "Content-Type: application/json" \
  -d '{"token":"eNGvgqk5T6q:APA91bHPRgkFjJiNvmMqLwV...","device_id":"android-device-uuid-1234"}'
```

---

## Anti-Spam System

```
Submit report
    ↓
X-Device-ID present?
    ↓ yes
Cooldown check (< 10 min since last?) → 429
    ↓ pass
Hourly count check (≥ 5 in last 60 min?) → 429
    ↓ pass
IndoBERT NLP classification
    ↓ verified=false → stored but never returned by GET /reports
Community flags (POST /reports/{id}/flag)
    ↓ flag_count ≥ 3 → visible=false → hidden from GET /reports
```

---

## Data Ingestion (Background Jobs)

Runs every **5 minutes** via APScheduler:

| Source | Data |
|---|---|
| **Open-Meteo** | Rainfall forecast + soil moisture for 10 Indonesian cities |
| **BMKG** | Current weather / earthquake observations |
| **USGS** | Earthquakes ≥ M2.0 within Indonesia bounding box |
| **PetaBencana** | Community flood reports from Indonesian cities |

---

## AI Models

| Model | Algorithm | Inputs | Output |
|---|---|---|---|
| Flood Risk | XGBoost | `rainfall_mm`, `river_level_m` | `flood_score` (0–1) |
| Landslide Risk | Random Forest | `rainfall_mm`, `soil_saturation` | `landslide_score` (0–1) |
| Earthquake Alert | Rule-based | `magnitude`, `distance_km` | `earthquake_score` (0–1) |
| Report Verifier | Keyword heuristic* | Report text (Indonesian) | `verified`, `confidence` |

\* Set `INDOBERT_ENABLED=true` for full HuggingFace `indobenchmark/indobert-base-p1` model.

---

## Database Schema (Reports)

| Column | Type | Description |
|---|---|---|
| `id` | int PK | Auto-increment |
| `lat`, `lng` | float | Incident coordinates |
| `text` | text | Report text |
| `category` | varchar | `flood` / `landslide` / `earthquake` / `fire` / `other` |
| `verified` | bool | IndoBERT classification result |
| `verification_score` | float | Classifier confidence (0–1) |
| `source` | varchar | `"user"` or `"petabencana"` |
| `device_id` | varchar(128) | Anonymous device UUID (never returned in responses) |
| `flag_count` | int | Number of community flags |
| `visible` | bool | `false` when `flag_count ≥ 3` |
| `created_at` | timestamptz | Creation timestamp |

---

## Seeding Evacuation Data

```sql
INSERT INTO evacuation_points (name, lat, lng, capacity, type, address) VALUES
  ('Gedung Serbaguna RW 05', -6.2000, 106.8500, 200, 'community_hall', 'Jl. Merdeka No. 1, Jakarta Pusat'),
  ('SDN Menteng 01',         -6.1950, 106.8440, 300, 'school',          'Jl. HOS Cokroaminoto, Jakarta'),
  ('Masjid Al-Ikhlas',       -6.2100, 106.8600, 150, 'mosque',          'Jl. Sudirman No. 10, Jakarta');
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | PostgreSQL URL (auto-normalised to asyncpg) |
| `APP_ENV` | ❌ | `development` | `production` hides `/docs`, enforces HSTS |
| `SECRET_KEY` | ✅ in prod | `change-me` | Must be changed in production |
| `CORS_ORIGINS` | ❌ | `*` | Comma-separated allowed origins |
| `FIREBASE_CREDENTIALS_PATH` | ⚠️ | `firebase-credentials.json` | Path to service account JSON |
| `FIREBASE_CREDENTIALS_JSON` | ⚠️ | — | Inline JSON (for Railway env vars) |
| `INGESTION_INTERVAL_MINUTES` | ❌ | `5` | Background job frequency |
| `INDOBERT_ENABLED` | ❌ | `false` | Use full HuggingFace IndoBERT model |
