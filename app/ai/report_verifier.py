"""
Report Verifier — IndoBERT NLP text classifier stub.

In production this should use 'indobenchmark/indobert-base-p1' fine-tuned on
disaster report data. For MVP/stub mode, it uses a keyword-heuristic approach
that is fast and dependency-free.

The module supports two modes controlled by the INDOBERT_ENABLED env var:
  - False (default/stub): keyword heuristic
  - True: load HuggingFace pipeline (requires: pip install transformers torch)
"""

import os
import re
from dataclasses import dataclass


DISASTER_KEYWORDS = {
    "Banjir": [
        "banjir", "banjir bandang", "genangan", "air naik", "meluap",
        "tenggelam", "terendam", "hujan deras",
    ],
    "Longsor": [
        "tanah longsor", "longsor", "lereng ambles", "material longsoran",
        "kebun ambles",
    ],
    "Gempa": [
        "gempa", "gempa bumi", "guncangan", "getaran", "tsunami",
    ],
    "Kebakaran": [
        "kebakaran", "api", "terbakar", "asap tebal",
    ],
}

ALL_KEYWORDS = [kw for kws in DISASTER_KEYWORDS.values() for kw in kws]


@dataclass
class VerificationResult:
    is_valid: bool          # True if the report appears to be a real disaster report
    confidence: float       # 0.0 – 1.0
    category: str           # Detected category, or "Lainnya"

def _keyword_verify(text: str) -> VerificationResult:
    """Fast heuristic verifier based on Indonesian disaster keywords."""
    text_lower = text.lower()
    matched = [kw for kw in ALL_KEYWORDS if re.search(rf"\b{re.escape(kw)}\b", text_lower)]

    if not matched:
        return VerificationResult(is_valid=False, confidence=0.15, category="Lainnya")

    # Determine primary category by first match
    category = "Lainnya"
    for cat, kws in DISASTER_KEYWORDS.items():
        if any(kw in matched for kw in kws):
            category = cat
            break

    # Confidence scales with number of matched keywords (up to ~0.9)
    confidence = min(0.9, 0.4 + len(matched) * 0.15)
    return VerificationResult(is_valid=True, confidence=confidence, category=category)

def verify_report(text: str) -> VerificationResult:
    """
    Verify a community report text.

    Set env var INDOBERT_ENABLED=true to use the full HuggingFace pipeline.
    Defaults to fast keyword heuristic.
    """
    if os.getenv("INDOBERT_ENABLED", "false").lower() == "true":
        return _indobert_verify(text)
    return _keyword_verify(text)

def _indobert_verify(text: str) -> VerificationResult:
    """
    Production verifier using HuggingFace transformers.
    Lazily loads the pipeline on first call.
    Requires: pip install transformers torch
    """
    try:
        from transformers import pipeline  # type: ignore
    except ImportError:
        raise ImportError(
            "transformers and torch are required for IndoBERT mode. "
            "Install with: pip install transformers torch"
        )

    global _nlp_pipeline
    if "_nlp_pipeline" not in globals() or _nlp_pipeline is None:
        _nlp_pipeline = pipeline(
            "text-classification",
            model="indobenchmark/indobert-base-p1",
            tokenizer="indobenchmark/indobert-base-p1",
        )

    result = _nlp_pipeline(text[:512])[0]
    label = result["label"].lower()
    score = result["score"]

    # Map model label to our categories (adjust based on fine-tuned labels)
    is_valid = label not in ("label_0", "non_bencana", "false")
    return VerificationResult(
        is_valid=is_valid,
        confidence=float(score),
        category=label if label in DISASTER_KEYWORDS else "Lainnya",
    )


_nlp_pipeline = None
