"""Helpers to normalize incoming UPS event payloads."""

from __future__ import annotations

import re
from typing import Optional, Tuple

from core.db.ups import db as default_db


_EVENT_ALIASES = {
    'ON LINE POWER': 'ONLINE',
    'ONLINE': 'ONLINE',
    'ON BATT': 'ONBATT',
    'ON BATTERY': 'ONBATT',
    'ONBATT': 'ONBATT',
    'LOW BATTERY': 'LOWBATT',
    'LOWBATT': 'LOWBATT',
    'COMMUNICATION RESTORED': 'COMMOK',
    'COMM RESTORED': 'COMMOK',
    'COMMOK': 'COMMOK',
    'COMMUNICATION LOST': 'COMMBAD',
    'COMM LOST': 'COMMBAD',
    'COMMBAD': 'COMMBAD',
    'NO COMMUNICATION': 'NOCOMM',
    'NOCOMM': 'NOCOMM',
    'NO PARENT': 'NOPARENT',
    'NOPARENT': 'NOPARENT',
    'REPLACE BATTERY': 'REPLBATT',
    'REPLBATT': 'REPLBATT',
    'FSD': 'SHUTDOWN',
    'SHUTDOWN': 'SHUTDOWN',
}


def safe_positive_int(value) -> Optional[int]:
    """Parse positive integer, returning None when invalid."""
    try:
        parsed = int(value)
        return parsed if parsed > 0 else None
    except (TypeError, ValueError):
        return None


def normalize_event_type(value) -> str:
    """Normalize UPS event token to canonical code."""
    raw_value = str(value or '').strip()
    if not raw_value:
        return 'UNKNOWN'
    normalized = re.sub(r'[^A-Z0-9]+', ' ', raw_value.upper()).strip()
    return _EVENT_ALIASES.get(normalized, normalized.replace(' ', ''))


def _parse_ups_identity(value) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    normalized = str(value or '').strip()
    if not normalized:
        return None, None, None
    if '@' not in normalized:
        return normalized, None, None

    ups_part, host_part = normalized.split('@', 1)
    ups_name = ups_part.strip() or None
    host_part = host_part.strip()
    if ':' not in host_part:
        return ups_name, host_part or None, None

    host_name, raw_port = host_part.rsplit(':', 1)
    return ups_name, (host_name.strip() or None), safe_positive_int(raw_port)


def _normalize_host(host) -> Optional[str]:
    value = str(host or '').strip().strip('[]').lower()
    if ',' in value:
        value = value.split(',', 1)[0].strip()
    return value or None


def resolve_target_id_from_payload(active_db, payload, fallback_db=None) -> Optional[int]:
    """Try resolving target_id from target_name / host / ups identity."""
    if not isinstance(payload, dict):
        return None

    db_handle = fallback_db or default_db
    model_space = getattr(active_db, 'ModelClasses', None) or getattr(db_handle, 'ModelClasses', None)
    target_model = getattr(model_space, 'UPSMonitorTarget', None) if model_space is not None else None
    if target_model is None:
        return None

    targets = (
        active_db.session.query(target_model)
        .filter(target_model.enabled.is_(True))
        .order_by(target_model.is_primary.desc(), target_model.id.asc())
        .all()
    )
    if not targets:
        return None

    target_name = str(payload.get('target_name') or '').strip().lower()
    if target_name:
        for target in targets:
            if str(getattr(target, 'name', '')).strip().lower() == target_name:
                return int(target.id)

    parsed_ups_name, parsed_host, parsed_port = _parse_ups_identity(payload.get('ups'))
    ups_name = str(payload.get('ups_name') or parsed_ups_name or '').strip().lower() or None
    host = (
        _normalize_host(payload.get('host'))
        or _normalize_host(parsed_host)
        or _normalize_host(payload.get('source_ip'))
    )

    if ups_name and host:
        for target in targets:
            if str(getattr(target, 'ups_name', '')).strip().lower() != ups_name:
                continue
            if _normalize_host(getattr(target, 'host', None)) != host:
                continue
            target_port = safe_positive_int(getattr(target, 'port', None))
            if parsed_port is not None and target_port is not None and target_port != parsed_port:
                continue
            return int(target.id)

    if host:
        host_matches = [target for target in targets if _normalize_host(getattr(target, 'host', None)) == host]
        if len(host_matches) == 1:
            return int(host_matches[0].id)

    if ups_name:
        ups_matches = [target for target in targets if str(getattr(target, 'ups_name', '')).strip().lower() == ups_name]
        if len(ups_matches) == 1:
            return int(ups_matches[0].id)

    return None

