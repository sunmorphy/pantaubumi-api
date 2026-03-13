"""
Flood Risk Model — XGBoost binary classifier.

Inputs : rainfall_mm (float), river_level_m (float)
Output : flood_risk_score (float, 0.0 – 1.0)

The stub is trained on synthetic but realistic-shaped data so that:
  - High rainfall (>100 mm) + high river level (>5 m) → score ~0.9
  - Low values → score ~0.1
"""

import os
import joblib
import numpy as np

from app.config import settings


_model = None


def _load_model():
    global _model
    if _model is None:
        path = settings.flood_model_path
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Flood model not found at '{path}'. "
                "Run 'python app/ai/train_stubs.py' to generate stub weights."
            )
        _model = joblib.load(path)
    return _model


def predict_flood_risk(rainfall_mm: float, river_level_m: float) -> float:
    """Return a flood risk probability in [0, 1]."""
    model = _load_model()
    features = np.array([[rainfall_mm, river_level_m]])
    prob = model.predict_proba(features)[0][1]
    return float(np.clip(prob, 0.0, 1.0))
