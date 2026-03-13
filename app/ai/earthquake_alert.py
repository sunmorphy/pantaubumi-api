"""
Earthquake Alert — Rule-based threshold check on USGS data.

Rules (Indonesia seismic context):
  - Magnitude >= 6.0  AND distance <= 300 km → "critical"
  - Magnitude >= 5.0  AND distance <= 500 km → "high"
  - Magnitude >= 4.0  AND distance <= 300 km → "medium"
  - Otherwise                                → "low" / no alert
"""

from dataclasses import dataclass


@dataclass
class EarthquakeAlertResult:
    triggered: bool
    severity: str          # "low" | "medium" | "high" | "critical"
    score: float           # 0.0 – 1.0 normalized risk
    message: str


def assess_earthquake(magnitude: float, distance_km: float) -> EarthquakeAlertResult:
    """Evaluate USGS quake data and return a structured alert result."""

    if magnitude >= 6.0 and distance_km <= 300:
        return EarthquakeAlertResult(
            triggered=True,
            severity="critical",
            score=min(1.0, magnitude / 9.0),
            message=(
                f"Gempa kuat M{magnitude:.1f} terdeteksi sejauh "
                f"{distance_km:.0f} km. WASPADA TINGGI!"
            ),
        )
    elif magnitude >= 5.0 and distance_km <= 500:
        return EarthquakeAlertResult(
            triggered=True,
            severity="high",
            score=min(0.85, magnitude / 9.0),
            message=(
                f"Gempa signifikan M{magnitude:.1f} sejauh "
                f"{distance_km:.0f} km. Bersiaplah."
            ),
        )
    elif magnitude >= 4.0 and distance_km <= 300:
        return EarthquakeAlertResult(
            triggered=True,
            severity="medium",
            score=min(0.55, magnitude / 9.0),
            message=(
                f"Gempa M{magnitude:.1f} terdeteksi sejauh {distance_km:.0f} km."
            ),
        )
    else:
        return EarthquakeAlertResult(
            triggered=False,
            severity="low",
            score=max(0.0, (magnitude - 2.0) / 9.0),
            message="",
        )
