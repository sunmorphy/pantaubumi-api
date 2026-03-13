# PantauBumi API Documentation

**Base URL (local):** `http://localhost:8000`  
**Base URL (production):** `https://your-app.up.railway.app`  
**Interactive Docs:** `{base_url}/docs` (Swagger UI) · `{base_url}/redoc` (ReDoc)

---

## Authentication

This API currently does not require authentication (MVP). All endpoints are publicly accessible. Rate limiting and API key auth are recommended before production release.

---

## Common Response Formats

### Success
All successful responses return JSON with an HTTP `2xx` status code.

### Validation Error — `422 Unprocessable Entity`
Returned when query params or request body fail validation.
```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": ["query", "lat"],
      "msg": "Input should be greater than or equal to -11.0",
      "input": "-50"
    }
  ]
}
```

### Server Error — `500 Internal Server Error`
```json
{ "detail": "Internal server error" }
```

---

## Endpoints

---

### `GET /health`
Health check. Use this to verify the service is running.

**Response `200`**
```json
{
  "status": "ok",
  "service": "pantau-bumi-api"
}
```

---

### `GET /risk`
Returns AI-computed disaster risk scores for a given coordinate.

Scores are computed by:
- **Flood** — XGBoost model on rainfall + river level data
- **Landslide** — Random Forest on rainfall + soil saturation
- **Earthquake** — Rule-based threshold on latest USGS magnitude + distance

Results are cached per location for 2 minutes.

#### Query Parameters

| Parameter | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `lat` | float | ✅ | -11.0 ≤ lat ≤ 7.0 | Latitude (Indonesia range) |
| `lng` | float | ✅ | 95.0 ≤ lng ≤ 141.0 | Longitude (Indonesia range) |

#### Response `200`
```json
{
  "lat": -6.2,
  "lng": 106.8,
  "flood_score": 0.73,
  "landslide_score": 0.41,
  "earthquake_score": 0.12,
  "overall_risk": "high",
  "computed_at": "2026-03-14T04:00:00Z"
}
```

| Field | Type | Description |
|---|---|---|
| `flood_score` | float (0–1) | Flood probability from XGBoost |
| `landslide_score` | float (0–1) | Landslide probability from Random Forest |
| `earthquake_score` | float (0–1) | Normalised earthquake risk score |
| `overall_risk` | string | `"low"` / `"medium"` / `"high"` / `"critical"` |
| `computed_at` | ISO 8601 datetime | UTC timestamp of computation |

**Overall risk aggregation:**

| Max score | Label |
|---|---|
| ≥ 0.75 | `critical` |
| ≥ 0.50 | `high` |
| ≥ 0.25 | `medium` |
| < 0.25 | `low` |

#### Example
```bash
curl "http://localhost:8000/risk?lat=-6.2&lng=106.8"
```

---

### `GET /alerts`
Returns recent disaster alerts near the given coordinate, filtered by area radius and time window.

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `lat` | float | ✅ | — | Latitude |
| `lng` | float | ✅ | — | Longitude |
| `radius_km` | float | ❌ | `100.0` | Search radius in kilometres |
| `hours` | int | ❌ | `24` | Look-back window (1–168 hours) |

#### Response `200`
```json
[
  {
    "id": 42,
    "type": "earthquake",
    "lat": -6.5,
    "lng": 107.1,
    "severity": "high",
    "message": "[USGS] Gempa signifikan M5.2 sejauh 85 km. Bersiaplah. Lokasi: 23 km SE of Bogor",
    "source": "usgs",
    "created_at": "2026-03-14T03:55:00Z"
  }
]
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"flood"` / `"landslide"` / `"earthquake"` |
| `severity` | string | `"low"` / `"medium"` / `"high"` / `"critical"` |
| `source` | string | `"bmkg"` / `"usgs"` / `"system"` |

Returns at most **50 alerts**, sorted newest first.

#### Example
```bash
curl "http://localhost:8000/alerts?lat=-6.2&lng=106.8&radius_km=50&hours=6"
```

---

### `GET /evacuation`
Returns the nearest evacuation shelters, sorted by distance from the query point.

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `lat` | float | ✅ | — | Latitude |
| `lng` | float | ✅ | — | Longitude |
| `limit` | int | ❌ | `5` | Max results (1–10) |

#### Response `200`
```json
[
  {
    "id": 1,
    "name": "Gedung Serbaguna RW 05",
    "lat": -6.2010,
    "lng": 106.8490,
    "capacity": 200,
    "type": "community_hall",
    "address": "Jl. Merdeka No. 1, Jakarta Pusat",
    "distance_km": 0.18
  },
  {
    "id": 7,
    "name": "SDN Menteng 01",
    "lat": -6.1950,
    "lng": 106.8440,
    "capacity": 300,
    "type": "school",
    "address": "Jl. HOS Cokroaminoto, Jakarta",
    "distance_km": 0.94
  }
]
```

| Field | Type | Description |
|---|---|---|
| `type` | string | `"school"` / `"mosque"` / `"stadium"` / `"community_hall"` |
| `capacity` | int | Estimated person capacity |
| `distance_km` | float | Distance from query point (Haversine, rounded to 2 dp) |

> **Note:** The `evacuation_points` table must be seeded with shelter data. See the [Seeding Evacuation Data](#seeding-evacuation-data) section below.

#### Example
```bash
curl "http://localhost:8000/evacuation?lat=-6.2&lng=106.8&limit=3"
```

---

### `GET /reports`
Returns verified community disaster reports within a radius.

Only reports where `verified = true` (confidence ≥ threshold from IndoBERT / keyword heuristic) are returned.

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `lat` | float | ✅ | — | Latitude |
| `lng` | float | ✅ | — | Longitude |
| `radius` | float | ❌ | `10.0` | Search radius in km (max 500) |

#### Response `200`
```json
[
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
```

| Field | Type | Description |
|---|---|---|
| `category` | string | `"flood"` / `"landslide"` / `"earthquake"` / `"fire"` / `"other"` |
| `verified` | bool | `true` if NLP classifier confirmed it's a real disaster report |
| `verification_score` | float (0–1) | Classifier confidence |
| `source` | string | `"user"` (submitted via API) or `"petabencana"` (ingested) |

Returns at most **50 reports**, sorted newest first.

#### Example
```bash
curl "http://localhost:8000/reports?lat=-6.2&lng=106.8&radius=5"
```

---

### `POST /reports`
Submit a new community disaster report. The text is automatically analyzed by the NLP report verifier (keyword heuristic or IndoBERT) to determine `verified` status and `category`.

#### Request Body `application/json`

```json
{
  "lat": -6.2,
  "lng": 106.8,
  "text": "Banjir besar melanda kampung kami, air sudah setinggi dada orang dewasa!",
  "category": "flood"
}
```

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `lat` | float | ✅ | — | Incident latitude |
| `lng` | float | ✅ | — | Incident longitude |
| `text` | string | ✅ | 10–2000 chars | Incident description (Indonesian preferred) |
| `category` | string | ❌ | default `"other"` | Hint category; overridden by NLP if detected |

#### Response `201 Created`
```json
{
  "id": 16,
  "lat": -6.2,
  "lng": 106.8,
  "text": "Banjir besar melanda kampung kami, air sudah setinggi dada orang dewasa!",
  "category": "flood",
  "verified": true,
  "verification_score": 0.85,
  "source": "user",
  "created_at": "2026-03-14T04:10:00Z"
}
```

#### Error `422` — Text too short
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "text"],
      "msg": "String should have at least 10 characters",
      "input": "Banjir"
    }
  ]
}
```

#### Example
```bash
curl -X POST http://localhost:8000/reports \
  -H "Content-Type: application/json" \
  -d '{
    "lat": -6.2,
    "lng": 106.8,
    "text": "Tanah longsor di lereng bukit, ada rumah yang tertimbun!",
    "category": "landslide"
  }'
```

---

### `POST /fcm-token`
Register or update a device's Firebase Cloud Messaging token. Tokens are used to send push notifications when a high-severity alert is triggered for the user's area.

This endpoint is **idempotent** — posting the same token twice updates its `device_id` (upsert semantics).

#### Request Body `application/json`

```json
{
  "token": "eNGvgqk5T6q:APA91bHPRgkFjJiNvmMqLwV...",
  "device_id": "android-device-uuid-1234"
}
```

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `token` | string | ✅ | min 10 chars | FCM registration token from Firebase SDK |
| `device_id` | string | ❌ | — | Optional device identifier for deduplication |

#### Response `200 OK`
```json
{
  "id": 3,
  "token": "eNGvgqk5T6q:APA91bHPRgkFjJiNvmMqLwV...",
  "device_id": "android-device-uuid-1234"
}
```

#### Example
```bash
curl -X POST http://localhost:8000/fcm-token \
  -H "Content-Type: application/json" \
  -d '{
    "token": "eNGvgqk5T6q:APA91bHPRgkFjJiNvmMqLwV...",
    "device_id": "android-device-uuid-1234"
  }'
```

---

## Data Ingestion (Background Jobs)

The following jobs run automatically every **5 minutes** via APScheduler:

| Source | Data | Endpoint Used |
|---|---|---|
| **Open-Meteo** | Hourly rainfall forecast + soil moisture for 10 Indonesian cities | `https://api.open-meteo.com/v1/forecast` |
| **BMKG** | Current weather observations (autogempa JSON) | `https://data.bmkg.go.id/DataMKG/TEWS/autogempa.json` |
| **USGS** | Earthquakes ≥ M2.0 within Indonesia bbox (last 10 min) | `https://earthquake.usgs.gov/fdsnws/event/1/query` |
| **PetaBencana** | Community flood reports from Indonesian cities | `https://data.petabencana.id/floods/reports` |

None of these sources require API keys.

---

## AI Models

| Model | Algorithm | Inputs | Output |
|---|---|---|---|
| Flood Risk | XGBoost | `rainfall_mm`, `river_level_m` | `flood_score` (0–1) |
| Landslide Risk | Random Forest | `rainfall_mm`, `soil_saturation` (0–1) | `landslide_score` (0–1) |
| Earthquake Alert | Rule-based | `magnitude`, `distance_km` | `earthquake_score` (0–1) + severity |
| Report Verifier | Keyword heuristic* | Report text (Indonesian) | `verified` (bool) + `confidence` |

\* Set `INDOBERT_ENABLED=true` to use the full `indobenchmark/indobert-base-p1` model.

---

## Push Notification Payload

When a `high` or `critical` earthquake alert is triggered, all registered FCM tokens receive:

```json
{
  "title": "⚠️ Peringatan Gempa Bumi",
  "body": "[USGS] Gempa kuat M6.2 terdeteksi sejauh 95 km. WASPADA TINGGI! Lokasi: 12 km NW of Sukabumi",
  "android": {
    "priority": "high",
    "notification": {
      "channel_id": "disaster_alerts",
      "sound": "default"
    }
  }
}
```

---

## Seeding Evacuation Data

The `/evacuation` endpoint requires data in the `evacuation_points` table. Example seed SQL:

```sql
INSERT INTO evacuation_points (name, lat, lng, capacity, type, address) VALUES
  ('Gedung Serbaguna RW 05', -6.2000, 106.8500, 200, 'community_hall', 'Jl. Merdeka No. 1, Jakarta Pusat'),
  ('SDN Menteng 01',         -6.1950, 106.8440, 300, 'school',          'Jl. HOS Cokroaminoto, Jakarta'),
  ('Masjid Al-Ikhlas',       -6.2100, 106.8600, 150, 'mosque',          'Jl. Sudirman No. 10, Jakarta'),
  ('Stasiun Gambir',         -6.1765, 106.8306, 500, 'stadium',         'Jl. Merdeka Timur, Jakarta Pusat');
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string (any scheme auto-normalised to asyncpg) |
| `FIREBASE_CREDENTIALS_PATH` | ⚠️ | `firebase-credentials.json` | Path to Firebase service account JSON |
| `FIREBASE_CREDENTIALS_JSON` | ⚠️ | — | Inline JSON (for Railway env vars) |
| `APP_ENV` | ❌ | `development` | `"development"` enables SQL echo logging |
| `CORS_ORIGINS` | ❌ | `*` | Comma-separated allowed origins |
| `INGESTION_INTERVAL_MINUTES` | ❌ | `5` | Background job frequency |
| `FLOOD_MODEL_PATH` | ❌ | `app/ai/weights/flood_model.pkl` | XGBoost model file path |
| `LANDSLIDE_MODEL_PATH` | ❌ | `app/ai/weights/landslide_model.pkl` | Random Forest model file path |
| `INDOBERT_ENABLED` | ❌ | `false` | Set `true` to use full HuggingFace IndoBERT |

> Either `FIREBASE_CREDENTIALS_PATH` or `FIREBASE_CREDENTIALS_JSON` must be set for push notifications. If neither is configured, push notifications are silently disabled.

---

## HTTP Status Code Reference

| Code | Meaning |
|---|---|
| `200 OK` | Success (GET, upsert POST) |
| `201 Created` | New resource created (POST /reports) |
| `422 Unprocessable Entity` | Request body / query param validation failed |
| `500 Internal Server Error` | Unexpected server-side error |
