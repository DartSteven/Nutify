"""Analytics helpers for Multi-NUT dashboards."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pytz
from flask import has_request_context

from core.db.ups import db
from core.logger import system_logger as logger
from core.options.operations_runtime import (
    compute_co2_kg,
    compute_cost,
    compute_energy_wh,
    compute_realpower_watts,
)

from .storage_core import get_monitoring_profile, list_targets
from .storage_snapshots import (
    extract_metric,
    get_latest_target_snapshot,
    infer_error_status,
    load_target_history,
    parse_iso_timestamp,
)



def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _extract_latest_metric(latest: Optional[Dict[str, object]], key: str):
    if not latest:
        return None
    return extract_metric(latest, key)


def _target_runtime_status(target: Dict[str, object], latest: Optional[Dict[str, object]], fallback: str) -> str:
    """Resolve effective target status with test-state fallback."""
    latest_status = _extract_latest_metric(latest, 'ups_status')
    if latest_status:
        latest_status = str(latest_status).strip()

    if target.get('last_test_status') is False:
        return infer_error_status(target.get('last_test_error'))

    if latest_status:
        return latest_status

    return str(fallback or 'UNKNOWN')


def _build_target_channels(target_id: int) -> Dict[str, bool]:
    mail_enabled = False
    ntfy_enabled = False
    telegram_enabled = False
    webhook_enabled = False

    try:
        if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'NotificationSettings'):
            model = db.ModelClasses.NotificationSettings
            query = model.query
            if hasattr(model, 'target_id'):
                query = query.filter(model.target_id == int(target_id))
            rows = query.all()
            for row in rows:
                if bool(getattr(row, 'enabled', False)) and getattr(row, 'id_email', None):
                    mail_enabled = True
                if bool(getattr(row, 'ntfy_enabled', False)) and getattr(row, 'id_ntfy', None):
                    ntfy_enabled = True
                if bool(getattr(row, 'telegram_enabled', False)) and getattr(row, 'id_telegram', None):
                    telegram_enabled = True
                if bool(getattr(row, 'webhook_enabled', False)) and getattr(row, 'id_webhook', None):
                    webhook_enabled = True
    except Exception as exc:
        logger.debug(f"Could not resolve notification channels for target={target_id}: {exc}")

    return {
        'mail': mail_enabled,
        'ntfy': ntfy_enabled,
        'telegram': telegram_enabled,
        'webhook': webhook_enabled,
        'extranotifs': ntfy_enabled or telegram_enabled or webhook_enabled,
    }



def _resolve_powerflow_target_id(explicit_target_id: Optional[int] = None) -> Optional[int]:
    explicit = _safe_int(explicit_target_id)
    if explicit is not None:
        return explicit

    try:
        profile = str(get_monitoring_profile() or 'single').strip().lower()
    except Exception:
        profile = 'single'

    if profile != 'multi' or not has_request_context():
        return None

    # Local import avoids circular dependency:
    # analytics -> active_target -> storage -> analytics
    from .active_target import get_request_or_active_target_id

    return _safe_int(get_request_or_active_target_id())


def get_powerflow_settings(target_id: Optional[int] = None) -> Tuple[str, float, float]:
    """Get cost/emission settings for selected target scope."""
    currency = 'EUR'
    price_per_kwh = 0.25
    co2_factor = 0.4
    scoped_target_id = _resolve_powerflow_target_id(target_id)

    try:
        if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'VariableConfig'):
            model = db.ModelClasses.VariableConfig
            query = model.query

            if hasattr(model, 'target_id'):
                if scoped_target_id is None:
                    config = (
                        query.filter(model.target_id.is_(None))
                        .order_by(model.id.desc())
                        .first()
                    )
                else:
                    config = (
                        query.filter(model.target_id == int(scoped_target_id))
                        .order_by(model.id.desc())
                        .first()
                    )
                    if not config:
                        logger.debug(
                            "No scoped VariableConfig row for target_id=%s; using built-in defaults",
                            scoped_target_id,
                        )
            else:
                config = query.order_by(model.id.desc()).first()

            if config:
                currency = config.currency or currency
                price_per_kwh = float(config.price_per_kwh or price_per_kwh)
                co2_factor = float(config.co2_factor or co2_factor)
    except Exception as exc:
        logger.debug(f"Could not read PowerFlow settings for Multi-NUT summary: {exc}")

    return currency, price_per_kwh, co2_factor



def build_target_dashboard(target_id: int, hours: int = 24) -> Dict[str, object]:
    """Build summary and chart series for target dashboard."""
    history = load_target_history(target_id, hours=hours, limit=20000)
    currency, price_per_kwh, co2_factor = get_powerflow_settings(target_id=target_id)

    if not history:
        return {
            'summary': {
                'energy_wh': 0.0,
                'cost': 0.0,
                'currency': currency,
                'co2_kg': 0.0,
                'avg_load': 0.0,
                'latest_status': 'UNKNOWN',
                'samples': 0,
                'events_count': 0,
            },
            'series': {
                'power': [],
                'battery': [],
                'load': [],
                'voltage': [],
                'status_events': [],
            },
        }

    power_series: List[Dict[str, object]] = []
    battery_series: List[Dict[str, object]] = []
    load_series: List[Dict[str, object]] = []
    voltage_series: List[Dict[str, object]] = []
    status_events: List[Dict[str, object]] = []

    energy_wh = 0.0
    load_samples: List[float] = []
    latest_status = 'UNKNOWN'
    previous_ts = None
    previous_power = None
    previous_status = None

    for row in history:
        ts = parse_iso_timestamp(row.get('timestamp_utc'))
        if not ts:
            continue

        ts_ms = int(ts.timestamp() * 1000)

        power = _safe_float(extract_metric(row, 'ups_realpower'))
        if power is None:
            power = compute_realpower_watts(row, target_id=target_id, nominal_default=0.0)
        battery = _safe_float(extract_metric(row, 'battery_charge'))
        load = _safe_float(extract_metric(row, 'ups_load'))
        voltage = _safe_float(extract_metric(row, 'input_voltage'))
        status = extract_metric(row, 'ups_status') or latest_status

        latest_status = str(status or 'UNKNOWN')

        if power is not None:
            power_series.append({'x': ts_ms, 'y': round(power, 2)})

        if battery is not None:
            battery_series.append({'x': ts_ms, 'y': round(battery, 2)})

        if load is not None:
            load_samples.append(load)
            load_series.append({'x': ts_ms, 'y': round(load, 2)})

        if voltage is not None:
            voltage_series.append({'x': ts_ms, 'y': round(voltage, 2)})

        normalized_status = str(status or 'UNKNOWN').strip().upper()
        if normalized_status and normalized_status != previous_status:
            status_events.append(
                {
                    'x': ts_ms,
                    'status': normalized_status,
                }
            )
            previous_status = normalized_status

        if previous_ts is not None and previous_power is not None and power is not None:
            delta_hours = (ts - previous_ts).total_seconds() / 3600
            if delta_hours > 0:
                # Prevent huge gaps from inflating estimates.
                delta_hours = min(delta_hours, 1 / 3)
                energy_wh += compute_energy_wh(previous_power, delta_hours, target_id=target_id)

        previous_ts = ts
        previous_power = power

    avg_load = round(sum(load_samples) / len(load_samples), 2) if load_samples else 0.0
    cost = round(compute_cost(energy_wh, price_per_kwh, target_id=target_id), 4)
    co2_kg = round(compute_co2_kg(energy_wh, co2_factor, target_id=target_id), 4)

    return {
        'summary': {
            'energy_wh': round(energy_wh, 2),
            'cost': cost,
            'currency': currency,
            'co2_kg': co2_kg,
            'avg_load': avg_load,
            'latest_status': latest_status,
            'samples': len(power_series),
            'events_count': len(status_events),
        },
        'series': {
            'power': power_series,
            'battery': battery_series,
            'load': load_series,
            'voltage': voltage_series,
            'status_events': status_events,
        },
    }



def list_targets_overview(hours: int = 24) -> List[Dict[str, object]]:
    """Build compact overview payload for all enabled targets."""
    targets = list_targets(include_disabled=False)
    overview = []

    for target in targets:
        dashboard = build_target_dashboard(target['id'], hours=hours)
        latest = get_latest_target_snapshot(target['id'])
        channels = _build_target_channels(target['id'])
        runtime_status = _target_runtime_status(
            target=target,
            latest=latest,
            fallback=dashboard['summary'].get('latest_status', 'UNKNOWN'),
        )
        is_runtime_offline = target.get('last_test_status') is False
        summary = dict(dashboard['summary'])
        summary['latest_status'] = runtime_status
        if is_runtime_offline:
            summary['avg_load'] = 0.0

        overview.append({
            'target': target,
            'latest': latest,
            'summary': summary,
            'channels': channels,
            'latest_metrics': {
                'ups_status': runtime_status,
                'battery_charge': None if is_runtime_offline else _safe_float(_extract_latest_metric(latest, 'battery_charge')),
                'battery_runtime': None if is_runtime_offline else _safe_float(_extract_latest_metric(latest, 'battery_runtime')),
                'ups_realpower': None if is_runtime_offline else _safe_float(_extract_latest_metric(latest, 'ups_realpower')),
                'ups_load': None if is_runtime_offline else _safe_float(_extract_latest_metric(latest, 'ups_load')),
                'input_voltage': None if is_runtime_offline else _safe_float(_extract_latest_metric(latest, 'input_voltage')),
            },
        })

    return overview


def build_multi_target_report(hours: int = 24, target_id: Optional[int] = None) -> Dict[str, object]:
    """Build a JSON-friendly report for one target or all enabled targets."""
    bounded_hours = max(1, min(int(hours or 24), 24 * 365))
    overview = list_targets_overview(hours=bounded_hours)
    generated_at = datetime.now(pytz.UTC).isoformat()

    if target_id is not None:
        selected = next((item for item in overview if item['target']['id'] == int(target_id)), None)
        if not selected:
            raise ValueError('Target not found')

        target_dashboard = build_target_dashboard(selected['target']['id'], hours=bounded_hours)
        return {
            'scope': 'selected',
            'generated_at': generated_at,
            'hours': bounded_hours,
            'target': selected['target'],
            'latest': selected['latest'],
            'summary': target_dashboard['summary'],
            'series': target_dashboard['series'],
        }

    totals = {
        'energy_wh': 0.0,
        'cost': 0.0,
        'co2_kg': 0.0,
        'samples': 0,
        'events_count': 0,
    }
    load_values: List[float] = []
    currency = 'EUR'

    for item in overview:
        summary = item['summary']
        totals['energy_wh'] += float(summary.get('energy_wh', 0.0) or 0.0)
        totals['cost'] += float(summary.get('cost', 0.0) or 0.0)
        totals['co2_kg'] += float(summary.get('co2_kg', 0.0) or 0.0)
        totals['samples'] += int(summary.get('samples', 0) or 0)
        totals['events_count'] += int(summary.get('events_count', 0) or 0)
        currency = summary.get('currency') or currency

        avg_load = _safe_float(summary.get('avg_load'))
        if avg_load is not None:
            load_values.append(avg_load)

    return {
        'scope': 'all',
        'generated_at': generated_at,
        'hours': bounded_hours,
        'targets': overview,
        'summary': {
            'energy_wh': round(totals['energy_wh'], 2),
            'cost': round(totals['cost'], 4),
            'currency': currency,
            'co2_kg': round(totals['co2_kg'], 4),
            'avg_load': round(sum(load_values) / len(load_values), 2) if load_values else 0.0,
            'samples': totals['samples'],
            'events_count': totals['events_count'],
            'target_count': len(overview),
        },
    }
