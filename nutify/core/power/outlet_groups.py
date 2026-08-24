"""Outlet-group real power discovery and history helpers."""

from __future__ import annotations

import json
import re
from typing import Dict, Iterable, List, Optional

from flask import current_app
from sqlalchemy import or_

from core.db.ups import db
from core.multi_nut.domain_proxy import get_metric_history, get_metric_stats
from core.multi_nut.storage_core import models
from core.multi_nut.storage_snapshots import extract_metric, get_latest_target_snapshot


OUTLET_REALPOWER_RE = re.compile(r'^outlet(?:[._][a-z0-9-]+)*[._]realpower$', re.IGNORECASE)


def _safe_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _canonical_key(key: str) -> str:
    return re.sub(r'_+', '_', str(key or '').strip().lower().replace('.', '_')).strip('_')


def is_outlet_realpower_key(key: str) -> bool:
    """Return True for NUT outlet real-power metrics."""
    return bool(OUTLET_REALPOWER_RE.match(str(key or '').strip()))


def outlet_group_label(key: str) -> str:
    """Build readable label from outlet real-power key."""
    canonical = _canonical_key(key)
    parts = canonical.split('_')
    middle = parts[1:-1] if len(parts) >= 2 else []
    if not middle:
        return 'Outlet Total'
    return f"Outlet {' '.join(middle)}"


def _sort_key(key: str):
    canonical = _canonical_key(key)
    parts = canonical.split('_')[1:-1]
    if not parts:
        return (0, '')
    sortable = []
    for part in parts:
        sortable.append((0, int(part)) if part.isdigit() else (1, part))
    return (1, tuple(sortable))


def _parse_json_payload(value) -> Dict[str, object]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _iter_payload_keys(rows: Iterable[object]) -> Iterable[str]:
    for row in rows:
        mapping = getattr(row, '_mapping', None)
        payload = dict(mapping) if mapping is not None else {}
        for field in ('data_json', 'raw_json'):
            for key in _parse_json_payload(payload.get(field)).keys():
                yield str(key)


def discover_outlet_realpower_keys(target_id: int, limit: int = 500) -> List[str]:
    """Discover outlet real-power keys from recent JSON snapshots."""
    _, _, Data = models()
    if not all(hasattr(Data, field) for field in ('target_id', 'data_json', 'raw_json')):
        return []

    rows = (
        db.session.query(Data.data_json, Data.raw_json)
        .filter(Data.target_id == int(target_id))
        .filter(or_(Data.data_json.isnot(None), Data.raw_json.isnot(None)))
        .order_by(Data.timestamp_utc.desc())
        .limit(max(1, min(int(limit), 2000)))
        .all()
    )

    keys = {
        _canonical_key(key)
        for key in _iter_payload_keys(rows)
        if is_outlet_realpower_key(key)
    }
    return sorted(keys, key=_sort_key)


def build_outlet_group_payload(
    target_id: int,
    period: str = 'day',
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    selected_date: Optional[str] = None,
    selected_day: Optional[str] = None,
) -> Dict[str, object]:
    """Build frontend payload for outlet-group power split."""
    keys = discover_outlet_realpower_keys(target_id)
    if not keys:
        return {'groups': [], 'has_data': False}

    history = get_metric_history(
        target_id=int(target_id),
        metric_names=keys,
        tz=current_app.CACHE_TIMEZONE,
        period=period,
        from_time=from_time,
        to_time=to_time,
        selected_date=selected_date,
        selected_day=selected_day,
    )
    stats = get_metric_stats(history)
    latest = get_latest_target_snapshot(int(target_id)) or {}

    groups = []
    for key in keys:
        metric_stats = stats.get(key) or {}
        current = _safe_float(extract_metric(latest, key), metric_stats.get('current', 0.0))
        available = bool(metric_stats.get('available')) or current is not None
        series = history.get(key, [])
        groups.append({
            'key': key,
            'label': outlet_group_label(key),
            'current': round(_safe_float(current, 0.0), 4),
            'available': available,
            'stats': {
                'min': _safe_float(metric_stats.get('min'), 0.0),
                'max': _safe_float(metric_stats.get('max'), 0.0),
                'avg': _safe_float(metric_stats.get('avg'), 0.0),
                'current': _safe_float(metric_stats.get('current'), 0.0),
                'available': bool(metric_stats.get('available')),
            },
            'series': series,
        })

    return {
        'groups': groups,
        'has_data': any(group['available'] for group in groups),
    }
