"""Scheduler Module.

Implements core runtime logic and helpers used by this feature.
"""

from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta
from typing import Optional, Tuple

import pytz
from flask import current_app, has_app_context

from core.settings import get_target_timezone


def _as_timezone(value) -> object | None:
    if value is None:
        return None
    if hasattr(value, "localize") and hasattr(value, "zone"):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return pytz.timezone(text)
    except Exception:
        return None


def resolve_schedule_timezone(target_id: Optional[int] = None, fallback_tz=None):
    """Resolve timezone for schedule execution and period calculations."""
    if target_id is not None:
        try:
            target_timezone = _as_timezone(get_target_timezone(target_id=target_id))
            if target_timezone is not None:
                return target_timezone
        except Exception:
            pass

    fallback_timezone = _as_timezone(fallback_tz)
    if fallback_timezone is not None:
        return fallback_timezone

    if has_app_context():
        app_timezone = _as_timezone(getattr(current_app, "CACHE_TIMEZONE", None))
        if app_timezone is not None:
            return app_timezone

    return pytz.UTC


def _localize_day_start(day_value, timezone_obj):
    return timezone_obj.localize(datetime.combine(day_value, dt_time.min))


def _localize_day_end(day_value, timezone_obj):
    return timezone_obj.localize(datetime.combine(day_value, dt_time.max))


def _rolling_year_start(day_value):
    try:
        anniversary = day_value.replace(year=day_value.year - 1)
    except ValueError:
        anniversary = day_value.replace(year=day_value.year - 1, day=28)
    return anniversary + timedelta(days=1)


def parse_schedule_range_dates(
    from_date_str: str,
    to_date_str: str,
    *,
    target_id: Optional[int] = None,
    fallback_tz=None,
) -> Tuple[datetime, datetime]:
    """Parse scheduler range dates in target-aware local timezone."""
    timezone_obj = resolve_schedule_timezone(target_id=target_id, fallback_tz=fallback_tz)

    from_date = datetime.strptime(str(from_date_str), "%Y-%m-%d").date()
    to_date = datetime.strptime(str(to_date_str), "%Y-%m-%d").date()
    if to_date < from_date:
        from_date, to_date = to_date, from_date

    return _localize_day_start(from_date, timezone_obj), _localize_day_end(to_date, timezone_obj)


def calculate_report_period(period_type: str, target_id: Optional[int] = None, fallback_tz=None):
    """Calculate start and end datetimes for scheduler report periods."""
    timezone_obj = resolve_schedule_timezone(target_id=target_id, fallback_tz=fallback_tz)
    now = datetime.now(timezone_obj)
    normalized_period = str(period_type or "").strip().lower()

    if normalized_period == "range":
        return None, None

    if normalized_period in {"daily", ""}:
        start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return start_date, now

    if normalized_period == "yesterday":
        yesterday = now.date() - timedelta(days=1)
        return _localize_day_start(yesterday, timezone_obj), _localize_day_end(yesterday, timezone_obj)

    if normalized_period == "last_week":
        start_day = now.date() - timedelta(days=6)
        return _localize_day_start(start_day, timezone_obj), _localize_day_end(now.date(), timezone_obj)

    if normalized_period == "last_month":
        start_day = now.date() - timedelta(days=29)
        return _localize_day_start(start_day, timezone_obj), _localize_day_end(now.date(), timezone_obj)

    if normalized_period == "last_year":
        start_day = _rolling_year_start(now.date())
        return _localize_day_start(start_day, timezone_obj), _localize_day_end(now.date(), timezone_obj)

    if normalized_period == "weekly":
        return (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0), now

    if normalized_period == "monthly":
        return (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0), now

    if normalized_period == "yearly":
        return (now - timedelta(days=365)).replace(hour=0, minute=0, second=0, microsecond=0), now

    start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start_date, now
