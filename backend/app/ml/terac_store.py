"""Local JSON-backed store for Terac arena pairs + labels.

UI-ONLY THIS BUILD. This is the seam a teammate replaces with the real Terac
API/MCP integration.

# TODO(terac): To go live, replace the local read/write below with calls to:
#   - Terac API:  launch annotation tasks (POST a comparison pair as a task) and
#                 poll/receive expert labels back. See API docs in Terac.docx
#                 ("View our API here") and the $250 credit per team.
#   - Terac MCP:  alternatively drive task creation via the Terac MCP server
#                 ("Setup our MCP here"). Wire TERAC_API_KEY in config.py (already
#                 added: settings.terac_api_key / settings.has_terac).
#   Keep this module's function signatures identical so api/terac.py and the
#   frontend Arena screen need no changes.
"""
from __future__ import annotations

import json
import os
import threading
import uuid

from app.core.config import settings

_lock = threading.Lock()


def _path() -> str:
    return settings.terac_store_path


def _read() -> dict:
    try:
        with open(_path(), "r") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"pairs": [], "labels": []}


def _write(data: dict) -> None:
    os.makedirs(os.path.dirname(_path()) or ".", exist_ok=True)
    with open(_path(), "w") as fh:
        json.dump(data, fh, indent=2)


def add_pair(pair: dict) -> dict:
    with _lock:
        data = _read()
        pair["pair_id"] = pair.get("pair_id") or uuid.uuid4().hex[:12]
        pair["labeled"] = False
        data["pairs"].append(pair)
        _write(data)
        return pair


def next_unlabeled() -> dict | None:
    data = _read()
    for pair in data["pairs"]:
        if not pair.get("labeled"):
            return pair
    return None


def all_pairs() -> list[dict]:
    return _read()["pairs"]


def add_label(label: dict) -> None:
    # TODO(terac): forward this label to Terac for verification/payout, or pull
    # the authoritative label from Terac instead of trusting the local submitter.
    with _lock:
        data = _read()
        data["labels"].append(label)
        for pair in data["pairs"]:
            if pair["pair_id"] == label["pair_id"]:
                pair["labeled"] = True
        _write(data)


def all_labels() -> list[dict]:
    return _read()["labels"]


def label_count() -> int:
    return len(_read()["labels"])
