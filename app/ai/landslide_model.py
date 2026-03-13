"""
Landslide Risk Model — Random Forest binary classifier.

Inputs : rainfall_mm (float), soil_saturation (float, 0.0 – 1.0)
Output : landslide_risk_score (float, 0.0 – 1.0)

Stub trained on synthetic data:
  - rainfall > 80 mm AND soil_saturation > 0.7 → score ~0.85
"""

import os
import joblib
import numpy as np

from app.config import settings


_model = None


def _load_model():
    global _model
    if _model is None:
        path = settings.landslide_model_path
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Landslide model not found at '{path}'. "
                "Run 'python app/ai/train_stubs.py' to generate stub weights."
            )
        _model = joblib.load(path)
    return _model


def predict_landslide_risk(rainfall_mm: float, soil_saturation: float) -> float:
    """Return a landslide risk probability in [0, 1]."""
    model = _load_model()
    features = np.array([[rainfall_mm, soil_saturation]])
    prob = model.predict_proba(features)[0][1]
    return float(np.clip(prob, 0.0, 1.0))
