# PantauBumi API 🌍⚠️

AI-Powered Multi-Disaster Early Warning System for Indonesia.

## Overview

PantauBumi API is a FastAPI backend that:
- **Ingests** external disaster data every 5 minutes (BMKG, Open-Meteo, USGS, PetaBencana)
- **Analyzes** risk using AI models (XGBoost, Random Forest, rule-based, IndoBERT)
- **Serves** REST endpoints to the Android app
- **Pushes** Firebase notifications for high-severity alerts

---

## Tech Stack

| Component | Technology |
|---|---|
| Framework | FastAPI + Uvicorn |
| Database | PostgreSQL via Supabase (asyncpg) |
| ORM | SQLAlchemy 2.0 (async) |
| Scheduler | APScheduler (AsyncIOScheduler) |
| AI/ML | XGBoost, scikit-learn, IndoBERT (HuggingFace) |
| Push Notifications | Firebase Admin SDK |
| Deployment | Railway |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/risk?lat=&lng=` | Overall risk + 3 hazard scores |
| GET | `/alerts?lat=&lng=` | Recent alerts for the area |
| GET | `/evacuation?lat=&lng=` | Nearest evacuation points |
| GET | `/reports?lat=&lng=&radius=` | Verified community reports |
| POST | `/reports` | Submit a new community report |
| POST | `/fcm-token` | Register device for push notifications |
| GET | `/health` | Health check |

Interactive docs available at `/docs` (Swagger UI) and `/redoc`.

---

## Project Structure

```
pantau-bumi-api/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings via pydantic-settings
│   ├── database.py          # Async SQLAlchemy engine
│   ├── scheduler.py         # APScheduler cron jobs
│   ├── ai/
│   │   ├── flood_model.py       # XGBoost flood risk
│   │   ├── landslide_model.py   # Random Forest landslide risk
│   │   ├── earthquake_alert.py  # Rule-based earthquake check
│   │   ├── report_verifier.py   # IndoBERT NLP classifier
│   │   ├── risk_engine.py       # Orchestrates all AI models
│   │   ├── train_stubs.py       # Generates stub model weights
│   │   └── weights/             # .pkl model files (git-ignored)
│   ├── ingestion/
│   │   ├── bmkg.py          # BMKG weather/rainfall
│   │   ├── open_meteo.py    # Rainfall forecast
│   │   ├── usgs.py          # USGS seismic data
│   │   └── petabencana.py   # Community flood reports
│   ├── models/              # SQLAlchemy ORM models
│   ├── routers/             # FastAPI route handlers
│   ├── schemas/             # Pydantic request/response models
│   ├── services/
│   │   └── firebase.py      # Firebase push notifications
│   └── utils/
│       ├── geo.py           # Haversine distance
│       └── cache.py         # In-memory TTL cache
├── tests/
│   └── test_api.py          # Smoke tests
├── Dockerfile
├── railway.toml
├── pyproject.toml
├── requirements.txt
└── .env.example
```

---

## Setup & Run

### 1. Prerequisites

- Python 3.11+
- A Supabase (or any PostgreSQL) database
- Firebase project with a service account JSON

### 2. Install dependencies

```bash
# Using pip
pip install -r requirements.txt

# Or using uv (faster)
pip install uv
uv pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your DB URL, Firebase credentials, etc.
```

Required variables:
```env
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/pantaubumi
FIREBASE_CREDENTIALS_PATH=firebase-credentials.json
```

### 4. Generate AI model stub weights

```bash
python app/ai/train_stubs.py
```

This creates `app/ai/weights/flood_model.pkl` and `landslide_model.pkl`.
Replace these with real trained models when you have labeled data.

### 5. Run the development server

```bash
uvicorn app.main:app --reload
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) to see the Swagger UI.

### 6. Run tests

```bash
# Install test extras
pip install aiosqlite pytest-asyncio

# Run tests
pytest tests/ -v
```

---

## Deploy to Railway

1. Push this repo to GitHub
2. Create a new Railway project and connect your GitHub repo
3. Add a PostgreSQL service in Railway (or use Supabase)
4. Set environment variables in Railway dashboard:
   - `DATABASE_URL`
   - `FIREBASE_CREDENTIALS_JSON` (paste the JSON content as a single-line string)
5. Railway auto-detects the `Dockerfile` and builds/deploys

---

## AI Models

| Model | Algorithm | Inputs | Output |
|---|---|---|---|
| Flood Risk | XGBoost | `rainfall_mm`, `river_level_m` | Probability 0–1 |
| Landslide Risk | Random Forest | `rainfall_mm`, `soil_saturation` | Probability 0–1 |
| Earthquake Alert | Rule-based | `magnitude`, `distance_km` | Severity label |
| Report Verifier | IndoBERT* | Report text (Indonesian) | `is_valid`, `confidence` |

*IndoBERT requires `INDOBERT_ENABLED=true` and `pip install transformers torch`. Default is fast keyword-heuristic mode.

---

## Data Sources

| Source | Data | Auth |
|---|---|---|
| [BMKG](https://data.bmkg.go.id) | Weather, current conditions | None (public) |
| [Open-Meteo](https://open-meteo.com) | Rainfall forecast, soil moisture | None (free) |
| [USGS](https://earthquake.usgs.gov) | Earthquake catalog | None (public) |
| [PetaBencana](https://petabencana.id) | Community flood reports | None (public) |

---

## Populating Evacuation Points

The `/evacuation` endpoint requires data in the `evacuation_points` table. You can seed it with a script or SQL:

```sql
INSERT INTO evacuation_points (name, lat, lng, capacity, type, address) VALUES
('Gedung Serbaguna RW 05', -6.2000, 106.8500, 200, 'community_hall', 'Jl. Merdeka No. 1, Jakarta'),
('SDN Menteng 01', -6.1950, 106.8440, 300, 'school', 'Jl. HOS Cokroaminoto, Jakarta');
```
