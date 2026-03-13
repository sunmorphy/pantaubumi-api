"""
Stub Model Trainer — generates lightweight but realistic ML model weights.

Run this script once to create the .pkl files used by flood_model.py and
landslide_model.py. In production, replace these with models trained on real data.

Usage:
    python app/ai/train_stubs.py
"""

import os
import numpy as np
import joblib

from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier


WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "weights")
FLOOD_PATH = os.path.join(WEIGHTS_DIR, "flood_model.pkl")
LANDSLIDE_PATH = os.path.join(WEIGHTS_DIR, "landslide_model.pkl")

N_SAMPLES = 2000
RANDOM_STATE = 42


def generate_flood_data():
    """Synthetic flood training data: X=[rainfall_mm, river_level_m], y=binary."""
    rng = np.random.default_rng(RANDOM_STATE)
    rainfall = rng.uniform(0, 200, N_SAMPLES)
    river_level = rng.uniform(0, 10, N_SAMPLES)

    # Label: flood likely when rainfall > 100 and river > 5 (with some noise)
    y = ((rainfall > 100) & (river_level > 5)).astype(int)
    noise_mask = rng.random(N_SAMPLES) < 0.08
    y[noise_mask] = 1 - y[noise_mask]

    return np.column_stack([rainfall, river_level]), y


def generate_landslide_data():
    """Synthetic landslide training: X=[rainfall_mm, soil_saturation], y=binary."""
    rng = np.random.default_rng(RANDOM_STATE + 1)
    rainfall = rng.uniform(0, 150, N_SAMPLES)
    soil_sat = rng.uniform(0, 1, N_SAMPLES)

    # Label: landslide likely when rainfall > 80 and saturation > 0.7
    y = ((rainfall > 80) & (soil_sat > 0.7)).astype(int)
    noise_mask = rng.random(N_SAMPLES) < 0.08
    y[noise_mask] = 1 - y[noise_mask]

    return np.column_stack([rainfall, soil_sat]), y


def train_flood_model():
    print("Training flood model (XGBoost)...")
    X, y = generate_flood_data()
    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        eval_metric="logloss",
        random_state=RANDOM_STATE,
    )
    model.fit(X, y)
    joblib.dump(model, FLOOD_PATH)
    print(f"  ✓ Saved to {FLOOD_PATH}")


def train_landslide_model():
    print("Training landslide model (Random Forest)...")
    X, y = generate_landslide_data()
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=6,
        random_state=RANDOM_STATE,
    )
    model.fit(X, y)
    joblib.dump(model, LANDSLIDE_PATH)
    print(f"  ✓ Saved to {LANDSLIDE_PATH}")


if __name__ == "__main__":
    os.makedirs(WEIGHTS_DIR, exist_ok=True)

    if not os.path.exists(FLOOD_PATH):
        train_flood_model()
    else:
        print(f"Flood model already exists at {FLOOD_PATH}, skipping.")

    if not os.path.exists(LANDSLIDE_PATH):
        train_landslide_model()
    else:
        print(f"Landslide model already exists at {LANDSLIDE_PATH}, skipping.")

    print("\nDone! Stub models are ready.")
