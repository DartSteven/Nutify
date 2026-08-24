"""UPS event duplicate suppression helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional


DEFAULT_EVENT_DEDUPE_WINDOW_SECONDS = 30


def _normalize_reference_time(value: Optional[datetime]) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def find_recent_duplicate_event(
    *,
    session,
    event_model,
    event_type: str,
    target_id: Optional[int],
    reference_time: Optional[datetime] = None,
    window_seconds: int = DEFAULT_EVENT_DEDUPE_WINDOW_SECONDS,
):
    """Return a recent identical event row for the same target scope, if any."""
    if session is None or event_model is None or not event_type:
        return None

    now_utc = _normalize_reference_time(reference_time)
    lower_bound = now_utc - timedelta(seconds=max(1, int(window_seconds)))
    query = session.query(event_model).filter(
        event_model.event_type == str(event_type).upper(),
        event_model.timestamp_utc >= lower_bound,
    )

    if hasattr(event_model, 'target_id'):
        if target_id is None:
            query = query.filter(event_model.target_id.is_(None))
        else:
            query = query.filter(event_model.target_id == int(target_id))

    return query.order_by(event_model.timestamp_utc.desc()).first()
