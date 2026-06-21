#!/usr/bin/env python3
"""Export labeled claim/source tasks from Supabase to JSONL.

Labels live in a separate annotations table (multiple annotators per task),
so this joins the task rows to a majority vote of their annotations rather
than reading an inline label column.

Example:
  cd backend
  .venv/bin/python scripts/pull_supabase_labels.py
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings  # noqa: E402
from app.ml.citation_classifier import normalize_label  # noqa: E402


def fetch_table(client: httpx.Client, endpoint: str, headers: dict, table: str, page_size: int) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        response = client.get(
            f"{endpoint}/{table}",
            params={"select": "*", "limit": page_size, "offset": offset},
            headers=headers,
        )
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, list):
            raise ValueError(f"Supabase response for {table} was not a JSON list")
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += len(page)


def majority_label(votes: list[int]) -> int | None:
    """Majority vote; ties (no clear majority) are dropped as ambiguous."""
    counts = Counter(votes)
    if len(counts) == 1:
        return votes[0]
    (label_a, count_a), (label_b, count_b) = counts.most_common(2)
    if count_a == count_b:
        return None
    return label_a


def build_labeled_tasks(
    tasks: list[dict], annotations: list[dict], join_key: str, label_column: str,
) -> list[dict]:
    votes_by_task: dict[str, list[int]] = defaultdict(list)
    for annotation in annotations:
        task_id = annotation.get(join_key)
        label = normalize_label(annotation.get(label_column))
        if task_id is not None and label is not None:
            votes_by_task[task_id].append(label)

    labeled: list[dict] = []
    for task in tasks:
        task_id = task.get(join_key)
        votes = votes_by_task.get(task_id)
        if not votes:
            continue
        label = majority_label(votes)
        if label is None:
            continue
        labeled.append({**task, "label": label, "annotator_votes": votes})
    return labeled


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Supabase labeled claim tasks as JSONL")
    parser.add_argument("--tasks-table", default=settings.supabase_tasks_table)
    parser.add_argument("--annotations-table", default=settings.supabase_annotations_table)
    parser.add_argument("--join-key", default=settings.supabase_join_key)
    parser.add_argument("--label-column", default=settings.supabase_label_column)
    parser.add_argument("--output", type=Path, default=Path(settings.supabase_export_path))
    parser.add_argument("--page-size", type=int, default=1000)
    args = parser.parse_args()

    if not settings.supabase_url or not settings.supabase_key:
        parser.error("SUPABASE_URL and SUPABASE_KEY must be set in backend/.env")
    if args.page_size < 1 or args.page_size > 1000:
        parser.error("--page-size must be between 1 and 1000")

    endpoint = f"{settings.supabase_url.rstrip('/')}/rest/v1"
    headers = {"apikey": settings.supabase_key, "Authorization": f"Bearer {settings.supabase_key}"}

    with httpx.Client(timeout=30.0) as client:
        tasks = fetch_table(client, endpoint, headers, args.tasks_table, args.page_size)
        annotations = fetch_table(client, endpoint, headers, args.annotations_table, args.page_size)

    labeled = build_labeled_tasks(tasks, annotations, args.join_key, args.label_column)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        for row in labeled:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(
        f"Exported {len(labeled)} labeled rows "
        f"({len(tasks)} tasks, {len(annotations)} annotations) to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
