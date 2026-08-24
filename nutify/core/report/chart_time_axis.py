"""Adaptive time-axis formatting for generated report charts."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable


def _as_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        try:
            return datetime.fromtimestamp(timestamp)
        except (OSError, OverflowError, ValueError):
            return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _series_timestamps(series: Iterable) -> list[datetime]:
    timestamps = []
    for point in series:
        raw_timestamp = None
        if isinstance(point, dict):
            raw_timestamp = point.get("x", point.get("timestamp"))
        elif isinstance(point, (list, tuple)) and point:
            raw_timestamp = point[0]
        parsed = _as_datetime(raw_timestamp)
        if parsed is not None:
            timestamps.append(parsed)
    return timestamps


def resolve_report_time_axis(timeseries: dict) -> tuple[str, str]:
    """Return title/tick format, including dates whenever data spans local dates."""
    timestamps = []
    for series in timeseries.values():
        if isinstance(series, (list, tuple)):
            timestamps.extend(_series_timestamps(series))
    if len(timestamps) >= 2:
        first = min(timestamps)
        last = max(timestamps)
        if first.date() != last.date():
            return "Date and Time", "%Y-%m-%d %H:%M"
    return "Time", "%H:%M"
