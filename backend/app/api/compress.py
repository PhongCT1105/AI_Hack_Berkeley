"""Compression evaluation endpoint.

The standalone /compress demo page was removed (it wasn't linked from the
app nav). This now only serves the saved three-way evaluation report
(raw prompt vs. Ddoski capsule vs. The Token Company) that the /eval page's
ThreeWayCompressionEvaluation component reads.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["compression"])
_EVALUATION_REPORT = Path(__file__).resolve().parents[2] / "data" / "compression_evaluations" / "latest.json"


@router.get("/compress/evaluations/latest")
def latest_compression_evaluation() -> dict:
    """Return the saved raw/compressed prompt pairs for visualization."""

    try:
        with _EVALUATION_REPORT.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="No compression evaluation yet. Run scripts/eval_ttc_compression.py first.",
        ) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Latest compression evaluation is invalid JSON.") from exc
