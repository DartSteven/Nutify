"""Helpers to resolve canonical notification metrics from target storage."""

from __future__ import annotations

from typing import Any, Dict, Optional


NOTIFICATION_METRIC_KEYS = (
    'ups_status',
    'battery_charge',
    'battery_runtime',
    'ups_load',
    'ups_realpower',
    'input_voltage',
    'output_voltage',
    'battery_voltage',
    'battery_temperature',
    'ups_temperature',
)

_NUMERIC_KEYS = {
    'battery_charge',
    'battery_runtime',
    'ups_load',
    'ups_realpower',
    'input_voltage',
    'output_voltage',
    'battery_voltage',
    'battery_temperature',
    'ups_temperature',
}


def _safe_float(value: Any):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_metric(key: str, value: Any):
    if value in (None, ''):
        return None
    if key in _NUMERIC_KEYS:
        return _safe_float(value)
    normalized = str(value).strip()
    return normalized or None


def normalize_notification_metrics(metrics: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Keep only canonical notification metric keys with usable values."""
    normalized: Dict[str, Any] = {}
    for key in NOTIFICATION_METRIC_KEYS:
        value = _coerce_metric(key, (metrics or {}).get(key))
        if value is not None:
            normalized[key] = value
    return normalized


def fill_missing_target_metrics(target_id: Optional[int], metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fill missing canonical metrics from latest target snapshot/history."""
    resolved = normalize_notification_metrics(metrics)
    if target_id is None:
        return resolved

    missing = [key for key in NOTIFICATION_METRIC_KEYS if resolved.get(key) is None]
    if not missing:
        return resolved

    try:
        from core.multi_nut.storage import extract_metric, get_latest_target_snapshot, load_target_history

        latest = get_latest_target_snapshot(int(target_id))
        if isinstance(latest, dict):
            for key in list(missing):
                value = _coerce_metric(key, extract_metric(latest, key))
                if value is None:
                    continue
                resolved[key] = value
                missing.remove(key)

        if not missing:
            return resolved

        history = load_target_history(int(target_id), hours=24, limit=1440)
        for row in reversed(history):
            if not isinstance(row, dict):
                continue
            for key in list(missing):
                value = _coerce_metric(key, extract_metric(row, key))
                if value is None:
                    continue
                resolved[key] = value
                missing.remove(key)
            if not missing:
                break
    except Exception:
        return resolved

    return resolved

