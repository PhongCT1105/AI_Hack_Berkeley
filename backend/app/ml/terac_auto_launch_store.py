"""File-backed dedupe/cap state for the auto-launch pipeline.

Same pattern as retrain_queue.py: a small JSON file, not a real task queue —
sufficient for a single-process deployment. Bounds real spend against the
Terac org balance two ways: a per-domain cooldown (a flaky domain doesn't
relaunch on every call) and a hard cap on total launches ever recorded here.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone

from app.core.config import settings

_lock = threading.Lock()


def _path() -> str:
    return settings.terac_auto_launch_store_path


def _read() -> dict:
    try:
        with open(_path(), "r") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {"launches": []}
    except (FileNotFoundError, json.JSONDecodeError):
        return {"launches": []}


def _write(data: dict) -> None:
    os.makedirs(os.path.dirname(_path()) or ".", exist_ok=True)
    with open(_path(), "w") as fh:
        json.dump(data, fh, indent=2)


def can_launch(domain: str) -> tuple[bool, str]:
    with _lock:
        data = _read()
        launches = data.get("launches", [])
        if len(launches) >= settings.terac_auto_launch_max_total:
            return False, f"reached terac_auto_launch_max_total={settings.terac_auto_launch_max_total}"

        cooldown = timedelta(hours=settings.terac_auto_launch_cooldown_hours)
        now = datetime.now(timezone.utc)
        for entry in reversed(launches):
            if entry["domain"] != domain:
                continue
            launched_at = datetime.fromisoformat(entry["launched_at"])
            if now - launched_at < cooldown:
                return False, f"domain {domain} launched {entry['launched_at']}, within cooldown"
            break
        return True, "ok"


def record_launch(
    domain: str,
    url: str,
    opportunity_id: str | None,
    supabase_task_id: str | None,
    launched: bool = False,
) -> dict:
    """Record a draft creation or a real launch — both consume the same
    per-domain cooldown and global cap slot, so "draft" mode still bounds
    how many opportunities pile up unreviewed."""
    with _lock:
        data = _read()
        entry = {
            "domain": domain,
            "url": url,
            "opportunity_id": opportunity_id,
            "supabase_task_id": supabase_task_id,
            "launched": launched,
            "launched_at": datetime.now(timezone.utc).isoformat(),
        }
        data.setdefault("launches", []).append(entry)
        _write(data)
        return entry


def list_launches() -> list[dict]:
    return _read().get("launches", [])
