"""Write seam into the Supabase source_claim_tasks table.

scripts/pull_supabase_labels.py only reads this table (to export labeled
training data). This is the write counterpart: new candidate sources found
by the auto-launch pipeline are inserted with the SAME columns as the
existing 200 labeled rows (see data/supabase_labeled_tasks.jsonl), so they
flow through the identical annotation -> majority-vote -> export -> retrain
loop once a human labels them, rather than a parallel one-off schema.
"""
from __future__ import annotations

import logging

import httpx
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes

from app.core.config import settings
from app.core.observability import get_tracer

logger = logging.getLogger("captain_ddoski.supabase_writer")


async def insert_task_row(row: dict) -> str | None:
    """Insert one source_claim_tasks row. Returns the row's task_id on
    success, None on any failure (unconfigured or request error) — best
    effort, never raises."""
    tracer = get_tracer()
    with tracer.start_as_current_span("captain_ddoski.supabase.insert_task") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.TOOL.value)
        span.set_attribute("supabase.task_id", row.get("task_id", ""))
        span.set_attribute("supabase.configured", bool(settings.supabase_url and settings.supabase_key))

        if not (settings.supabase_url and settings.supabase_key):
            span.set_attribute("supabase.inserted", False)
            return None
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{settings.supabase_url.rstrip('/')}/rest/v1/{settings.supabase_tasks_table}",
                    headers={
                        "apikey": settings.supabase_key,
                        "Authorization": f"Bearer {settings.supabase_key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=representation",
                    },
                    json=row,
                )
                resp.raise_for_status()
            span.set_attribute("supabase.inserted", True)
            logger.info("Inserted Supabase task row task_id=%s", row.get("task_id"))
            return row.get("task_id")
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Supabase insert failed for task_id=%s: %s", row.get("task_id"), exc)
            span.set_attribute("supabase.inserted", False)
            span.record_exception(exc)
            return None
