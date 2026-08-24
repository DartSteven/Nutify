"""Consistency checks for direct UPS event callbacks."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Mapping, Optional


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip()
    if not raw:
        return None
    cleaned = re.sub(r"[^0-9.+-]", "", raw)
    if cleaned in {"", ".", "+", "-", "+.", "-."}:
        return None
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def _status_tokens(metrics: Mapping[str, object]) -> set[str]:
    raw = str(
        metrics.get("ups_status")
        or metrics.get("ups.status")
        or metrics.get("status")
        or ""
    ).upper().strip()
    return {token for token in re.split(r"[^A-Z0-9]+", raw) if token}


def _battery_low(metrics: Mapping[str, object], tokens: set[str]) -> bool:
    if {"LB", "LOWBATT"} & tokens:
        return True
    charge = _safe_float(metrics.get("battery_charge") or metrics.get("battery.charge"))
    low = _safe_float(metrics.get("battery_charge_low") or metrics.get("battery.charge.low"))
    return charge is not None and low is not None and charge <= low


def _parse_timestamp(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        ts = value
    else:
        raw = str(value).strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            ts = datetime.fromisoformat(raw)
        except ValueError:
            return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def is_recent_snapshot(snapshot: Mapping[str, object] | None, max_age_seconds: int = 30) -> bool:
    """Return True when snapshot is fresh enough to validate an external event."""
    if not isinstance(snapshot, Mapping):
        return False
    ts = _parse_timestamp(snapshot.get("timestamp_utc") or snapshot.get("timestamp"))
    if ts is None:
        return False
    age = abs((datetime.now(timezone.utc) - ts).total_seconds())
    return age <= max(1, int(max_age_seconds))


def describe_inconsistent_power_event(event_type: str, metrics: Mapping[str, object] | None) -> str:
    """Return a reason when a power event contradicts current UPS status metrics."""
    if not isinstance(metrics, Mapping):
        return ""

    normalized_event = str(event_type or "").upper().strip()
    tokens = _status_tokens(metrics)
    if not tokens:
        return ""

    online = bool({"OL", "ONLINE"} & tokens)
    on_battery = bool({"OB", "ONBATT"} & tokens)
    low_battery = _battery_low(metrics, tokens)

    if normalized_event == "ONBATT" and online and not on_battery:
        return "latest UPS status is online"
    if normalized_event == "LOWBATT" and online and not low_battery:
        return "latest UPS status is online and battery is not low"
    if normalized_event == "ONLINE" and on_battery and not online:
        return "latest UPS status is on battery"
    return ""
