"""Shared parsing and readiness rules for NUT ``upsc`` responses."""

from __future__ import annotations

from typing import Mapping


_TRANSIENT_STATUS_TOKENS = frozenset({'WAIT', 'NOCOMM'})
_STALE_MARKERS = (
    'data stale',
    'stale',
    'nocomm',
    'communication lost',
    'not responding',
)


def parse_upsc_output(raw_stdout: str) -> dict[str, str]:
    """Parse ``upsc`` output while preserving canonical dot-separated keys."""
    parsed = {}
    for line in str(raw_stdout or '').splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        normalized_key = key.strip()
        if normalized_key:
            parsed[normalized_key] = value.strip()
    return parsed


def contains_stale_marker(value: object) -> bool:
    """Return whether a NUT value reports stale or unavailable communication."""
    normalized = str(value or '').strip().lower()
    return bool(normalized and any(marker in normalized for marker in _STALE_MARKERS))


def evaluate_upsc_readiness(payload: Mapping[str, object] | None) -> tuple[bool, str]:
    """Classify an ``upsc`` payload without requiring model-specific metrics."""
    values = payload if isinstance(payload, Mapping) else {}
    if not values:
        return False, 'upsc returned an empty payload'

    for key in ('driver.state', 'driver.status', 'ups.status'):
        value = values.get(key)
        if contains_stale_marker(value):
            return False, f'{key} reports stale communication ({value})'

    status = str(values.get('ups.status') or '').strip()
    if not status:
        return False, 'ups.status is not available yet'

    status_tokens = {token.upper() for token in status.split() if token.strip()}
    transient_tokens = sorted(status_tokens.intersection(_TRANSIENT_STATUS_TOKENS))
    if transient_tokens:
        return False, f"ups.status is not ready ({' '.join(transient_tokens)})"

    return True, ''


def is_transient_readiness_error(error: object) -> bool:
    """Return whether an error was produced by readiness classification."""
    normalized = str(error or '').lower()
    markers = (
        'upsc returned an empty payload',
        'reports stale communication',
        'ups.status is not available yet',
        'ups.status is not ready',
    )
    return any(marker in normalized for marker in markers)


def nominal_power_metadata(
    payload: Mapping[str, object] | None,
    manual_value: object = None,
) -> dict[str, object]:
    """Describe automatic/manual nominal real-power resolution."""
    values = payload if isinstance(payload, Mapping) else {}
    inspected_upsc = bool(values)
    nominal_value = None
    source_key = None

    for candidate in ('ups.realpower.nominal', 'ups_realpower_nominal'):
        raw_value = values.get(candidate)
        try:
            parsed_value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if parsed_value > 0:
            nominal_value = int(parsed_value) if parsed_value.is_integer() else parsed_value
            source_key = candidate
            break

    if nominal_value is None:
        try:
            parsed_manual = float(manual_value)
        except (TypeError, ValueError):
            parsed_manual = 0.0
        if parsed_manual > 0:
            nominal_value = int(parsed_manual) if parsed_manual.is_integer() else parsed_manual
            source_key = 'manual_input'

    ready, _ = evaluate_upsc_readiness(values) if inspected_upsc else (False, '')
    return {
        'found': nominal_value is not None,
        'value': nominal_value,
        'source': source_key,
        'requires_manual_input': bool(inspected_upsc and ready and nominal_value is None),
        'inspected_upsc': inspected_upsc,
    }
