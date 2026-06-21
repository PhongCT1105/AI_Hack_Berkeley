"""Local JSON-backed queue of domains flagged by the degradation monitor.

Same pattern as terac_store.py: a small file-backed store, not a real task
queue — sufficient for a single-process hackathon deployment. Each entry
tracks why a domain was flagged and whether the monitor has already acted on
it (queued a Terac comparison pair for it).
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone

from app.core.config import settings

_lock = threading.Lock()


def _path() -> str:
    return settings.retrain_queue_path


def _read() -> list[dict]:
    try:
        with open(_path(), "r") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _write(items: list[dict]) -> None:
    os.makedirs(os.path.dirname(_path()) or ".", exist_ok=True)
    with open(_path(), "w") as fh:
        json.dump(items, fh, indent=2)


def enqueue(domain: str, reasons: list[str]) -> dict:
    """Add or refresh a pending entry for this domain. Dedupes — re-flagging
    an already-pending domain just updates its reasons/timestamp."""
    with _lock:
        items = _read()
        existing = next((it for it in items if it["domain"] == domain and it["status"] == "pending"), None)
        if existing:
            existing["reasons"] = reasons
            existing["flagged_at"] = datetime.now(timezone.utc).isoformat()
        else:
            existing = {
                "domain": domain,
                "reasons": reasons,
                "status": "pending",
                "flagged_at": datetime.now(timezone.utc).isoformat(),
            }
            items.append(existing)
        _write(items)
        return existing


def list_queue() -> list[dict]:
    return _read()


def mark_processed(domain: str) -> None:
    with _lock:
        items = _read()
        for it in items:
            if it["domain"] == domain and it["status"] == "pending":
                it["status"] = "queued_for_annotation"
        _write(items)
