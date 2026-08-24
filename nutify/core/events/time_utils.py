"""UTC timestamp helpers for UPS events."""

from __future__ import annotations

from datetime import datetime, timezone

import pytz


def utc_now() -> datetime:
    """Return current aware UTC timestamp for event storage."""
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime | str | None) -> datetime | None:
    """Normalize an event timestamp from DB/API code to aware UTC."""
    if value is None:
        return None

    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None

    if value.tzinfo is None:
        return pytz.UTC.localize(value)

    return value.astimezone(timezone.utc)


def serialize_utc_timestamp(value: datetime | str | None) -> str | None:
    """Serialize event timestamps as explicit UTC ISO strings."""
    normalized = ensure_utc(value)
    if normalized is None:
        return None
    return normalized.isoformat().replace('+00:00', 'Z')
