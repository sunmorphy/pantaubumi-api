# PantauBumi API Documentation

**Base URL (local):** `http://localhost:8000`  
**Base URL (production):** `https://your-app.up.railway.app`  
**Interactive Docs:** `{base_url}/docs` (dev only — disabled in production)

---

## Authentication

MVP: no authentication required. Rate limiting is enforced per IP address.

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
| `status` | string | Human-readable label (see table below) |
| `message` | string \| null | Error detail or `null` on success |
| `data` | object \| array \| null | Payload on success, `null` on error |

**Status labels by code:**

| Code | Status |
|---|---|
| 200 | `Success` |
| 201 | `Created` |
| 422 | `Unprocessable Entity` |
| 429 | `Too Many Requests` |
| 500 | `Internal Server Error` |

---

## Rate Limits

| Endpoint | Limit |
|---|---|
| All endpoints (global) | 60 requests / minute / IP |
| `POST /reports` | 10 requests / minute / IP |
| `POST /fcm-token` | 20 requests / minute / IP |

When exceeded → `429 Too Many Requests`:
```json
{ "code": 429, "status": "Too Many Requests", "message": "...", "data": null }
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

| Field | Type | Description |
|---|---|---|
| `flood_score` | float (0–1) | XGBoost flood probability |
| `landslide_score` | float (0–1) | Random Forest landslide probability |
| `earthquake_score` | float (0–1) | Normalised seismic risk |
| `overall_risk` | string | `low` / `medium` / `high` / `critical` |

**Overall risk thresholds:** ≥0.75 → `critical` · ≥0.50 → `high` · ≥0.25 → `medium` · else → `low`

#### Error `422`
```json
{
  "code": 422,
  "status": "Unprocessable Entity",
  "message": "query → lat: Input should be less than or equal to 7.0",
  "data": null
}
```

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

Returns at most 50 alerts, sorted newest first.

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
Submit a community disaster report. Auto-verified by the NLP classifier.

**Rate limit:** 10 requests / minute / IP

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
    "created_at": "2026-03-14T04:10:00Z"
  }
}
```

#### Error `422`
```json
{
  "code": 422,
  "status": "Unprocessable Entity",
  "message": "body → text: String should have at least 10 characters",
  "data": null
}
```

#### Example
```bash
curl -X POST http://localhost:8000/reports \
  -H "Content-Type: application/json" \
  -d '{"lat":-6.2,"lng":106.8,"text":"Tanah longsor di lereng bukit, ada rumah tertimbun!","category":"landslide"}'
```

---

### `POST /fcm-token`
Register or update a device FCM push notification token. Idempotent (upsert).

**Rate limit:** 20 requests / minute / IP

#### Request Body
```json
{
  "token": "eNGvgqk5T6q:APA91bHPRgkFjJiNvmMqLwV...",
  "device_id": "android-device-uuid-1234"
}
```

| Field | Type | Required | Constraints |
|---|---|---|---|
| `token` | string | ✅ | min 10 chars |
| `device_id` | string | ❌ | — |

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
| Flood Risk | XGBoost | `rainfall_mm`, `river_level_m` | `flood_score` |
| Landslide Risk | Random Forest | `rainfall_mm`, `soil_saturation` | `landslide_score` |
| Earthquake Alert | Rule-based | `magnitude`, `distance_km` | `earthquake_score` |
| Report Verifier | Keyword heuristic* | Report text (Indonesian) | `verified`, `confidence` |

\* Set `INDOBERT_ENABLED=true` for full HuggingFace `indobenchmark/indobert-base-p1` model.

---

## Push Notification Payload (FCM)

Sent to registered devices on `high` / `critical` earthquake alerts:

```json
{
  "title": "⚠️ Peringatan Gempa Bumi",
  "body": "[USGS] Gempa kuat M6.2 terdeteksi sejauh 95 km. WASPADA TINGGI!",
  "android": {
    "priority": "high",
    "notification": { "channel_id": "disaster_alerts", "sound": "default" }
  }
}
```

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
