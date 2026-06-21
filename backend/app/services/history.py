"""Persistent score-call history for dashboard, MCP demos, and threat feed."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.score import ScoreResponse


MAX_HISTORY_ITEMS = 500


class ScoreHistory:
    def __init__(self, path: str, max_items: int = MAX_HISTORY_ITEMS) -> None:
        self.path = Path(path)
        self.max_items = max_items
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        caller: str,
        request_url: str,
        request_task: str,
        response: ScoreResponse,
    ) -> dict[str, Any]:
        item = {
            "received_at": datetime.now(timezone.utc).isoformat(),
            "caller": caller or "api",
            "request": {
                "url": request_url,
                "task": request_task,
            },
            "response": response.model_dump(mode="json"),
        }

        with self._lock:
            items = self._read_unlocked()
            items = [item, *[x for x in items if x.get("response", {}).get("trace_id") != response.trace_id]]
            self._write_unlocked(items[: self.max_items])
        return item

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read_unlocked()

    def get(self, trace_id: str) -> dict[str, Any] | None:
        with self._lock:
            return next(
                (
                    item
                    for item in self._read_unlocked()
                    if item.get("response", {}).get("trace_id") == trace_id
                ),
                None,
            )

    def _read_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return raw if isinstance(raw, list) else []

    def _write_unlocked(self, items: list[dict[str, Any]]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(items, indent=2), encoding="utf-8")
        tmp.replace(self.path)


def response_from_history_item(item: dict[str, Any]) -> ScoreResponse | None:
    try:
        return ScoreResponse(**item["response"])
    except (KeyError, TypeError, ValueError):
        return None
