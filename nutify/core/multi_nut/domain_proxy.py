"""Domain adapters that map active Multi-NUT target snapshots to existing APIs."""

from __future__ import annotations

import math
import time
from datetime import date as date_cls
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

import pytz
from sqlalchemy import func

from core.db.ups import db
from core.settings import get_ups_realpower_nominal, parse_time_format
from core.options.operations_runtime import (
    compute_co2_kg,
    compute_cost,
    compute_energy_wh,
    compute_realpower_watts,
)

from .active_target import get_request_or_active_target_id
from .analytics import get_powerflow_settings
from .storage_core import models
from .storage import get_target_with_policy
from .storage_snapshots import (
    extract_metric,
    get_latest_target_snapshot,
    infer_error_status,
    load_target_history,
    parse_iso_timestamp,
)
from .rollups import load_rollup_history

_CURRENCY_SYMBOLS = {
    'EUR': '€',
    'USD': '$',
    'GBP': '£',
    'JPY': '¥',
    'AUD': 'A$',
    'CAD': 'C$',
    'CHF': 'Fr',
    'CNY': '¥',
    'INR': '₹',
    'NZD': 'NZ$',
    'BRL': 'R$',
    'RUB': '₽',
    'KRW': '₩',
    'PLN': 'PLN',
}

_TARGET_TIMEZONE_CACHE: Dict[int, Tuple[float, object]] = {}
_TARGET_TIMEZONE_CACHE_TTL = 30.0


def _safe_float(value, default: Optional[float] = None) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _default_nominal_power() -> float:
    """Return safe nominal real power default."""
    nominal = _safe_float(get_ups_realpower_nominal(), 0.0)
    return nominal if nominal is not None else 0.0


def _currency_symbol(currency_code: Optional[str]) -> str:
    normalized = str(currency_code or 'EUR').strip().upper()
    if not normalized:
        normalized = 'EUR'
    return _CURRENCY_SYMBOLS.get(normalized, normalized)


def _is_runtime_offline(target) -> bool:
    return bool(target and target.last_test_status is False)


def resolve_target_id() -> Optional[int]:
    """Resolve request/session active target id when in multi profile."""
    return get_request_or_active_target_id()


def _timezone_from_name(timezone_name: Optional[str], fallback_tz) -> object:
    fallback_name = str(getattr(fallback_tz, 'zone', '') or 'UTC').strip() or 'UTC'
    normalized = str(timezone_name or '').strip() or fallback_name
    try:
        return pytz.timezone(normalized)
    except Exception:
        try:
            return pytz.timezone(fallback_name)
        except Exception:
            return pytz.UTC


def _resolve_target_timezone(target_id: Optional[int], fallback_tz):
    if not target_id:
        return _timezone_from_name(None, fallback_tz)

    cache_key = int(target_id)
    cached = _TARGET_TIMEZONE_CACHE.get(cache_key)
    now_monotonic = time.monotonic()
    if cached and cached[0] > now_monotonic:
        return cached[1]

    resolved_tz = _timezone_from_name(None, fallback_tz)
    try:
        from core.options.options import get_variable_config_row

        row, _ = get_variable_config_row(target_id=cache_key, include_global_fallback=True)
        timezone_name = str(getattr(row, 'timezone', '') or '').strip()
        if timezone_name:
            resolved_tz = _timezone_from_name(timezone_name, fallback_tz)
    except Exception:
        pass

    _TARGET_TIMEZONE_CACHE[cache_key] = (now_monotonic + _TARGET_TIMEZONE_CACHE_TTL, resolved_tz)
    return resolved_tz


def get_latest_metrics(target_id: int) -> Tuple[Dict[str, object], Dict[str, object], Dict[str, object]]:
    """Return target metadata, latest snapshot row and flat metric map."""
    target, _ = get_target_with_policy(target_id)
    if not target:
        return {}, {}, {}

    latest = get_latest_target_snapshot(target_id) or {}
    metrics: Dict[str, object] = {}
    for key in (
        'ups_status',
        'ups_power',
        'battery_charge',
        'battery_charge_low',
        'battery_charge_warning',
        'battery_runtime',
        'battery_runtime_low',
        'battery_voltage',
        'battery_voltage_nominal',
        'battery_current',
        'battery_temperature',
        'battery_alarm_threshold',
        'ups_load',
        'ups_realpower',
        'ups_power_nominal',
        'ups_realpower_nominal',
        'input_voltage',
        'output_voltage',
        'input_transfer_low',
        'input_transfer_high',
        'input_sensitivity',
        'input_voltage_nominal',
        'output_voltage_nominal',
        'input_current',
        'output_current',
        'input_frequency',
        'output_frequency',
        'input_frequency_nominal',
        'output_frequency_nominal',
        'device_model',
        'device_serial',
        'device_mfr',
        'battery_type',
        'battery_date',
        'battery_mfr_date',
    ):
        value = extract_metric(latest, key)
        if value is not None:
            metrics[key] = value

    if _is_runtime_offline(target):
        offline_status = infer_error_status(getattr(target, 'last_test_error', None))
        metrics['ups_status'] = offline_status
        preserved = {'ups_status', 'device_model', 'device_serial', 'device_mfr'}
        for key in list(metrics.keys()):
            if key not in preserved:
                metrics.pop(key, None)

    return target.to_dict(), latest, metrics


def build_target_header_data(target_id: int) -> Dict[str, object]:
    """Build lightweight data map used by page templates/header."""
    target, _, metrics = get_latest_metrics(target_id)
    if not target:
        return {}

    return {
        'device_model': metrics.get('device_model') or target.get('name') or target.get('ups_name') or 'UPS',
        'device_serial': metrics.get('device_serial') or 'Unknown',
        'device_mfr': metrics.get('device_mfr') or 'Unknown',
        'ups_status': metrics.get('ups_status') or 'UNKNOWN',
        'battery_charge': _safe_float(metrics.get('battery_charge'), 0.0),
        'battery_runtime': _safe_float(metrics.get('battery_runtime'), 0.0),
        'battery_voltage': _safe_float(metrics.get('battery_voltage'), 0.0),
        'ups_load': _safe_float(metrics.get('ups_load'), 0.0),
        'ups_realpower': _safe_float(metrics.get('ups_realpower'), 0.0),
        'ups_realpower_nominal': _safe_float(metrics.get('ups_realpower_nominal'), _default_nominal_power()),
        'input_voltage': _safe_float(metrics.get('input_voltage'), 0.0),
        'input_transfer_low': _safe_float(metrics.get('input_transfer_low'), 0.0),
        'input_transfer_high': _safe_float(metrics.get('input_transfer_high'), 0.0),
        'input_sensitivity': metrics.get('input_sensitivity') or '',
    }


def _parse_iso_datetime(value: Optional[str], tz) -> Optional[datetime]:
    if not value:
        return None
    parsed = parse_iso_timestamp(value)
    if not parsed:
        return None
    return parsed.astimezone(tz)


def _parse_date_only(value: Optional[str]) -> Optional[date_cls]:
    raw = str(value or '').strip()
    if not raw:
        return None

    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return None


def _safe_localize(tz, dt_value: datetime) -> datetime:
    if dt_value.tzinfo is not None:
        return dt_value.astimezone(tz)
    try:
        return tz.localize(dt_value, is_dst=None)
    except Exception:
        return tz.localize(dt_value)


def _normalize_period_window(
    tz,
    period: str = 'day',
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    selected_date: Optional[str] = None,
    selected_day: Optional[str] = None,
) -> Tuple[datetime, datetime]:
    now_local = datetime.now(tz)
    period = str(period or 'day').strip().lower()

    if period == 'range':
        from_date = _parse_date_only(from_time)
        to_date = _parse_date_only(to_time)
        if from_date and to_date:
            if to_date < from_date:
                from_date, to_date = to_date, from_date
            start = _safe_localize(tz, datetime.combine(from_date, datetime.min.time()))
            end = _safe_localize(tz, datetime.combine(to_date + timedelta(days=1), datetime.min.time()))
            return start, end
        return now_local - timedelta(days=1), now_local

    if period == 'today':
        start = _safe_localize(tz, datetime.combine(now_local.date(), datetime.min.time()))
        end = now_local
        if end <= start:
            end = start + timedelta(seconds=1)
        return start, end

    if period == 'realtime':
        if from_time and to_time and ':' in str(from_time) and ':' in str(to_time):
            start_time = parse_time_format(from_time, datetime.strptime('00:00', '%H:%M').time())
            end_time = parse_time_format(to_time, now_local.time())
            start = _safe_localize(tz, datetime.combine(now_local.date(), start_time))
            end = _safe_localize(tz, datetime.combine(now_local.date(), end_time))
            if end <= start:
                end = start + timedelta(minutes=5)
            return start, end

        end = now_local
        start = end - timedelta(minutes=5)
        return start, now_local

    if period == 'day':
        date_value = selected_date or selected_day or _parse_date_only(from_time)
        if isinstance(date_value, datetime):
            base_date = date_value.astimezone(tz).date()
        elif date_value:
            if isinstance(date_value, date_cls):
                base_date = date_value
            else:
                parsed = _parse_date_only(str(date_value))
                base_date = parsed or now_local.date()
        elif (
            from_time
            and to_time
            and ':' in str(from_time)
            and ':' in str(to_time)
            and len(str(from_time)) <= 8
            and len(str(to_time)) <= 8
        ):
            start_time = parse_time_format(from_time, datetime.strptime('00:00', '%H:%M').time())
            end_time = parse_time_format(to_time, now_local.time())
            start = _safe_localize(tz, datetime.combine(now_local.date(), start_time))
            end = _safe_localize(tz, datetime.combine(now_local.date(), end_time))
            if end <= start:
                end = start + timedelta(minutes=1)
            return start, end
        else:
            base_date = now_local.date()

        start = _safe_localize(tz, datetime.combine(base_date, datetime.min.time()))
        end = _safe_localize(tz, datetime.combine(base_date + timedelta(days=1), datetime.min.time()))
        return start, end

    return now_local - timedelta(days=1), now_local


def _load_rows_for_window(
    target_id: int,
    start_local: datetime,
    end_local: datetime,
    metric_hints: Optional[Iterable[str]] = None,
) -> List[Dict[str, object]]:
    start_utc = start_local.astimezone(pytz.UTC)
    end_utc = end_local.astimezone(pytz.UTC)
    if end_utc <= start_utc:
        return []

    _, _, Data = models()
    requested_metrics = {str(name).strip() for name in (metric_hints or []) if str(name).strip()}

    column_names: List[str] = ['timestamp_utc']
    include_payload_json = False
    for metric_name in sorted(requested_metrics):
        if hasattr(Data, metric_name):
            column_names.append(metric_name)
        else:
            include_payload_json = True
    if include_payload_json:
        if hasattr(Data, 'data_json') and 'data_json' not in column_names:
            column_names.append('data_json')
        if hasattr(Data, 'raw_json') and 'raw_json' not in column_names:
            column_names.append('raw_json')

    query_columns = [getattr(Data, name) for name in column_names]
    query = db.session.query(*query_columns).filter(
        Data.target_id == int(target_id),
        Data.timestamp_utc >= start_utc,
        Data.timestamp_utc < end_utc,
    ).order_by(Data.timestamp_utc.asc())

    raw_rows = query.all()

    filtered = []
    for row in raw_rows:
        mapping = getattr(row, '_mapping', None)
        if mapping is not None:
            payload = dict(mapping)
        elif isinstance(row, tuple):
            payload = {column_names[idx]: row[idx] for idx in range(min(len(row), len(column_names)))}
        else:
            payload = {'timestamp_utc': row}

        raw_timestamp = payload.get('timestamp_utc')
        if isinstance(raw_timestamp, str):
            ts = parse_iso_timestamp(raw_timestamp)
        elif isinstance(raw_timestamp, datetime):
            ts = raw_timestamp
            if ts.tzinfo is None:
                ts = pytz.UTC.localize(ts)
            else:
                ts = ts.astimezone(pytz.UTC)
        else:
            ts = None

        if not ts:
            continue

        payload['timestamp_utc'] = ts.isoformat()
        payload['_timestamp'] = ts
        payload['_timestamp_ms'] = int(ts.timestamp() * 1000)
        filtered.append(payload)

    return filtered


def _select_history_rollup_granularity(period: str, start_local: datetime, end_local: datetime) -> Optional[str]:
    normalized = str(period or '').strip().lower()
    if normalized != 'range':
        return None

    span_days = max(0.0, (end_local - start_local).total_seconds() / 86400.0)
    if span_days >= 365.0:
        return 'month'
    if span_days >= 45.0:
        return 'day'
    if span_days >= 3.0:
        return 'hour'
    return None


def _load_rollup_rows_for_window(
    target_id: int,
    start_local: datetime,
    end_local: datetime,
    *,
    granularity: str,
    metric_hints: Iterable[str],
) -> List[Dict[str, object]]:
    start_utc = start_local.astimezone(pytz.UTC)
    end_utc = end_local.astimezone(pytz.UTC)
    if end_utc <= start_utc:
        return []
    return load_rollup_history(
        target_id=target_id,
        granularity=granularity,
        start_utc=start_utc,
        end_utc=end_utc,
        metric_names=metric_hints,
    )


def _downsample_extrema(points: List[Dict[str, float]], max_points: Optional[int]) -> List[Dict[str, float]]:
    if max_points is None or max_points <= 0 or len(points) <= max_points:
        return points
    if max_points <= 2:
        return [points[0], points[-1]]

    interior = points[1:-1]
    if not interior:
        return points[:max_points]

    bucket_count = max(1, (max_points - 2) // 2)
    bucket_size = max(1, math.ceil(len(interior) / bucket_count))
    sampled: List[Dict[str, float]] = [points[0]]

    for start_idx in range(0, len(interior), bucket_size):
        bucket = interior[start_idx:start_idx + bucket_size]
        if not bucket:
            continue
        low = min(bucket, key=lambda item: item['value'])
        high = max(bucket, key=lambda item: item['value'])
        if low['timestamp'] <= high['timestamp']:
            sampled.append(low)
            if high is not low:
                sampled.append(high)
        else:
            sampled.append(high)
            if low is not high:
                sampled.append(low)

    sampled.append(points[-1])
    sampled = sorted(sampled, key=lambda item: item['timestamp'])

    deduped_map: Dict[int, Dict[str, float]] = {}
    for point in sampled:
        deduped_map[int(point['timestamp'])] = point
    deduped = [deduped_map[key] for key in sorted(deduped_map.keys())]

    if len(deduped) <= max_points:
        return deduped

    middle = deduped[1:-1]
    keep_middle = max_points - 2
    step = max(1, math.ceil(len(middle) / keep_middle))
    return [deduped[0], *middle[::step][:keep_middle], deduped[-1]]


def get_metric_history(
    target_id: int,
    metric_names: Iterable[str],
    tz,
    period: str = 'day',
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    selected_date: Optional[str] = None,
    selected_day: Optional[str] = None,
    max_points: int = 1200,
) -> Dict[str, List[Dict[str, float]]]:
    """Return metric->time series map for selected target/period."""
    effective_tz = _resolve_target_timezone(target_id, tz)
    start_local, end_local = _normalize_period_window(
        tz=effective_tz,
        period=period,
        from_time=from_time,
        to_time=to_time,
        selected_date=selected_date,
        selected_day=selected_day,
    )
    rows: List[Dict[str, object]] = []
    rollup_granularity = _select_history_rollup_granularity(period, start_local, end_local)
    if rollup_granularity:
        rows = _load_rollup_rows_for_window(
            target_id=target_id,
            start_local=start_local,
            end_local=end_local,
            granularity=rollup_granularity,
            metric_hints=metric_names,
        )
    if not rows:
        rows = _load_rows_for_window(target_id, start_local, end_local, metric_hints=metric_names)

    result = {name: [] for name in metric_names}
    for row in rows:
        ts_ms = row['_timestamp_ms']
        for metric in metric_names:
            value = _safe_float(extract_metric(row, metric))
            if value is None:
                continue
            result[metric].append({'timestamp': ts_ms, 'value': value})

    for metric, points in result.items():
        result[metric] = _downsample_extrema(points, max_points=max_points)

    return result


def get_metric_stats(history: Dict[str, List[Dict[str, float]]]) -> Dict[str, Dict[str, object]]:
    """Compute min/max/avg/current payload from metric history map."""
    stats: Dict[str, Dict[str, object]] = {}
    for metric, points in history.items():
        values = [point['value'] for point in points]
        if not values:
            stats[metric] = {'min': 0.0, 'max': 0.0, 'avg': 0.0, 'current': 0.0, 'available': False}
            continue
        stats[metric] = {
            'min': round(min(values), 4),
            'max': round(max(values), 4),
            'avg': round(sum(values) / len(values), 4),
            'current': round(values[-1], 4),
            'available': True,
        }
    return stats


def has_hour_data(target_id: int, metric_name: str = 'ups_realpower') -> bool:
    """Check if target has at least 50 minutes of usable points in the last hour."""
    now_utc = datetime.now(pytz.UTC)
    start_utc = now_utc - timedelta(hours=1)
    rows = load_target_history(target_id, hours=2, limit=10000)

    points = []
    for row in rows:
        ts = parse_iso_timestamp(row.get('timestamp_utc'))
        if not ts or ts < start_utc or ts > now_utc:
            continue
        value = extract_metric(row, metric_name)
        if value is None:
            continue
        points.append(ts)

    if len(points) < 30:
        return False
    span_minutes = (max(points) - min(points)).total_seconds() / 60.0
    return span_minutes >= 50.0


def _compute_power_watts(row: Dict[str, object], nominal_default: float, target_id: Optional[int] = None) -> float:
    return compute_realpower_watts(
        row,
        target_id=target_id,
        nominal_default=nominal_default,
    )


def _distribute_cost(timestamp_local: datetime, cost: float, distribution: Dict[str, float]) -> None:
    hour = timestamp_local.hour
    if 6 <= hour < 12:
        distribution['morning'] += cost
    elif 12 <= hour < 18:
        distribution['afternoon'] += cost
    elif 18 <= hour < 23:
        distribution['evening'] += cost
    else:
        distribution['night'] += cost


def build_energy_payload(
    target_id: int,
    tz,
    period: str,
    from_time: Optional[str],
    to_time: Optional[str],
    selected_date: Optional[str] = None,
    selected_day: Optional[str] = None,
) -> Dict[str, object]:
    """Build `/api/energy/data` compatible payload from target snapshots."""
    effective_tz = _resolve_target_timezone(target_id, tz)
    currency, price_per_kwh, co2_factor = get_powerflow_settings(target_id=target_id)
    nominal_default = _default_nominal_power()

    start_local, end_local = _normalize_period_window(
        tz=effective_tz,
        period=period,
        from_time=from_time,
        to_time=to_time,
        selected_date=selected_date,
        selected_day=selected_day,
    )
    rows = _load_rows_for_window(
        target_id,
        start_local,
        end_local,
        metric_hints=('ups_realpower', 'ups_power', 'ups_load', 'ups_realpower_nominal'),
    )

    if not rows:
        return {
            'totalEnergy': 0.0,
            'totalCost': 0.0,
            'avgLoad': 0.0,
            'co2': 0.0,
            'total_energy': 0.0,
            'total_cost': 0.0,
            'avg_load': 0.0,
            'trends': {'energy': 0.0, 'cost': 0.0, 'load': 0.0, 'co2': 0.0},
            'efficiency': {'peak': 0.0, 'average': 0.0, 'saved': 0.0},
            'cost_distribution': {'morning': 0.0, 'afternoon': 0.0, 'evening': 0.0, 'night': 0.0},
            'currency': currency,
            'currency_symbol': _currency_symbol(currency),
        }

    total_energy_wh = 0.0
    loads: List[float] = []
    distribution = {'morning': 0.0, 'afternoon': 0.0, 'evening': 0.0, 'night': 0.0}
    previous_ts = None
    previous_power = None

    for row in rows:
        ts = row['_timestamp']
        power = _compute_power_watts(row, nominal_default=nominal_default, target_id=target_id)
        load = _safe_float(extract_metric(row, 'ups_load'))
        if load is not None:
            loads.append(load)

        if previous_ts is not None and previous_power is not None:
            delta_h = (ts - previous_ts).total_seconds() / 3600.0
            if delta_h > 0:
                delta_h = min(delta_h, 1 / 3)
                energy_part = compute_energy_wh(previous_power, delta_h, target_id=target_id)
                total_energy_wh += energy_part
                cost_part = compute_cost(energy_part, price_per_kwh, target_id=target_id)
                _distribute_cost(previous_ts.astimezone(effective_tz), cost_part, distribution)

        previous_ts = ts
        previous_power = power

    total_cost = compute_cost(total_energy_wh, price_per_kwh, target_id=target_id)
    co2_kg = compute_co2_kg(total_energy_wh, co2_factor, target_id=target_id)
    avg_load = (sum(loads) / len(loads)) if loads else 0.0
    peak_load = max(loads) if loads else 0.0

    return {
        'totalEnergy': round(total_energy_wh, 2),
        'totalCost': round(total_cost, 4),
        'avgLoad': round(avg_load, 2),
        'co2': round(co2_kg, 4),
        'total_energy': round(total_energy_wh, 2),
        'total_cost': round(total_cost, 4),
        'avg_load': round(avg_load, 2),
        'trends': {'energy': 0.0, 'cost': 0.0, 'load': 0.0, 'co2': 0.0},
        'efficiency': {'peak': round(peak_load, 2), 'average': round(avg_load, 2), 'saved': 0.0},
        'cost_distribution': {key: round(value, 6) for key, value in distribution.items()},
        'currency': currency,
        'currency_symbol': _currency_symbol(currency),
    }


def _normalize_energy_level(level: Optional[str], fallback: str = 'hour') -> str:
    normalized = str(level or '').strip().lower()
    if normalized in {'month', 'day', 'hour', 'minute'}:
        return normalized
    return fallback


def _resolve_energy_level(period: str, start_local: datetime, end_local: datetime) -> str:
    normalized_period = str(period or '').strip().lower()
    if normalized_period == 'realtime':
        return 'minute'
    if normalized_period in {'today', 'day'}:
        return 'hour'
    if normalized_period == 'range':
        span_days = max(0.0, (end_local - start_local).total_seconds() / 86400.0)
        if span_days >= 90.0:
            return 'month'
        if span_days > 2.0:
            return 'day'
        return 'hour'
    return 'hour'


def _energy_next_level(level: str) -> Optional[str]:
    if level == 'month':
        return 'day'
    if level == 'day':
        return 'hour'
    if level == 'hour':
        return 'minute'
    return None


def _bucket_start_local(timestamp_local: datetime, level: str) -> datetime:
    normalized_level = _normalize_energy_level(level)
    if normalized_level == 'month':
        return timestamp_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if normalized_level == 'day':
        return timestamp_local.replace(hour=0, minute=0, second=0, microsecond=0)
    if normalized_level == 'hour':
        return timestamp_local.replace(minute=0, second=0, microsecond=0)
    return timestamp_local.replace(second=0, microsecond=0)


def _advance_bucket_local(bucket_start: datetime, level: str) -> datetime:
    normalized_level = _normalize_energy_level(level)
    tz = bucket_start.tzinfo or pytz.UTC
    if normalized_level == 'month':
        if bucket_start.month == 12:
            next_year = bucket_start.year + 1
            next_month = 1
        else:
            next_year = bucket_start.year
            next_month = bucket_start.month + 1
        return _safe_localize(tz, datetime(next_year, next_month, 1))
    if normalized_level == 'day':
        next_date = bucket_start.astimezone(tz).date() + timedelta(days=1)
        return _safe_localize(tz, datetime.combine(next_date, datetime.min.time()))
    if normalized_level == 'hour':
        return bucket_start + timedelta(hours=1)
    return bucket_start + timedelta(minutes=1)


def _iter_bucket_starts(start_local: datetime, end_local: datetime, level: str):
    cursor = _bucket_start_local(start_local, level)
    while cursor < end_local:
        yield cursor
        next_cursor = _advance_bucket_local(cursor, level)
        if next_cursor <= cursor:
            break
        cursor = next_cursor


def _utc_iso(value: datetime) -> str:
    return value.astimezone(pytz.UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _bucket_title(bucket_start: datetime, level: str, next_level: Optional[str]) -> str:
    if not next_level:
        return ''

    if level == 'month':
        return f"Days detail for {bucket_start.strftime('%b %Y')}"
    if level == 'day':
        return f"Hours detail for {bucket_start.strftime('%Y-%m-%d')}"
    if level == 'hour':
        return f"Minutes detail for {bucket_start.strftime('%H:00')}"
    return ''


def _aggregate_energy_cost(
    rows: List[Dict[str, object]],
    *,
    target_id: int,
    level: str,
    timezone_obj,
    price_per_kwh: float,
    nominal_default: float,
) -> Dict[datetime, float]:
    aggregated: Dict[datetime, float] = {}
    previous_ts: Optional[datetime] = None
    previous_power: Optional[float] = None

    for row in rows:
        timestamp_utc = row['_timestamp']
        power = _compute_power_watts(row, nominal_default=nominal_default, target_id=target_id)
        if previous_ts is not None and previous_power is not None:
            delta_h = (timestamp_utc - previous_ts).total_seconds() / 3600.0
            if delta_h > 0:
                delta_h = min(delta_h, 1.0 / 3.0)
                energy_wh = compute_energy_wh(previous_power, delta_h, target_id=target_id)
                cost = max(0.0, compute_cost(energy_wh, price_per_kwh, target_id=target_id))
                local_ts = previous_ts.astimezone(timezone_obj)
                bucket = _bucket_start_local(local_ts, level)
                aggregated[bucket] = aggregated.get(bucket, 0.0) + cost
        previous_ts = timestamp_utc
        previous_power = power

    return aggregated


def _resolve_energy_rollup_source_level(level: str) -> Optional[str]:
    normalized_level = _normalize_energy_level(level, fallback='hour')
    if normalized_level == 'month':
        return 'day'
    if normalized_level == 'day':
        return 'hour'
    if normalized_level == 'hour':
        return 'minute'
    return None


def _aggregate_energy_cost_from_rollups(
    rows: List[Dict[str, object]],
    *,
    target_id: int,
    source_level: str,
    group_level: str,
    timezone_obj,
    price_per_kwh: float,
    nominal_default: float,
) -> Dict[datetime, float]:
    aggregated: Dict[datetime, float] = {}
    source_level = _normalize_energy_level(source_level, fallback='hour')
    group_level = _normalize_energy_level(group_level, fallback='hour')

    for row in rows:
        timestamp_utc = row.get('_timestamp')
        if not isinstance(timestamp_utc, datetime):
            continue

        local_start = _bucket_start_local(timestamp_utc.astimezone(timezone_obj), source_level)
        local_end = _advance_bucket_local(local_start, source_level)
        duration_hours = (local_end.astimezone(pytz.UTC) - local_start.astimezone(pytz.UTC)).total_seconds() / 3600.0
        if duration_hours <= 0:
            continue

        power = _compute_power_watts(row, nominal_default=nominal_default, target_id=target_id)
        energy_wh = compute_energy_wh(power, duration_hours, target_id=target_id)
        cost = max(0.0, compute_cost(energy_wh, price_per_kwh, target_id=target_id))
        group_bucket = _bucket_start_local(local_start, group_level)
        aggregated[group_bucket] = aggregated.get(group_bucket, 0.0) + cost

    return aggregated


def _build_energy_bucket_series(
    *,
    aggregated_cost: Dict[datetime, float],
    start_local: datetime,
    end_local: datetime,
    level: str,
) -> List[Dict[str, float]]:
    next_level = _energy_next_level(level)
    series: List[Dict[str, float]] = []
    for bucket_start in _iter_bucket_starts(start_local, end_local, level):
        bucket_end = _advance_bucket_local(bucket_start, level)
        if bucket_end > end_local:
            bucket_end = end_local
        window_start = bucket_start if bucket_start >= start_local else start_local

        value = round(aggregated_cost.get(bucket_start, 0.0), 6)
        series.append(
            {
                'x': int(bucket_start.astimezone(pytz.UTC).timestamp() * 1000),
                'y': value,
                'from_iso': _utc_iso(window_start),
                'to_iso': _utc_iso(bucket_end),
                'level': level,
                'next_level': next_level,
                'title': _bucket_title(bucket_start, level, next_level),
            }
        )
    return series


def build_energy_cost_series(
    target_id: int,
    tz,
    period: str,
    from_time: Optional[str],
    to_time: Optional[str],
    selected_date: Optional[str] = None,
    selected_day: Optional[str] = None,
) -> List[Dict[str, float]]:
    """Build cost trend series with adaptive bucket metadata for drilldown."""
    effective_tz = _resolve_target_timezone(target_id, tz)
    _, price_per_kwh, _ = get_powerflow_settings(target_id=target_id)
    nominal_default = _default_nominal_power()
    start_local, end_local = _normalize_period_window(
        tz=effective_tz,
        period=period,
        from_time=from_time,
        to_time=to_time,
        selected_date=selected_date,
        selected_day=selected_day,
    )
    rows = _load_rows_for_window(
        target_id,
        start_local,
        end_local,
        metric_hints=('ups_realpower', 'ups_power', 'ups_load', 'ups_realpower_nominal'),
    )
    level = _resolve_energy_level(period, start_local, end_local)
    aggregated_cost: Dict[datetime, float]
    use_rollups = str(period or '').strip().lower() == 'range' and level in {'month', 'day', 'hour'}
    if use_rollups:
        source_level = _resolve_energy_rollup_source_level(level)
        rollup_rows: List[Dict[str, object]] = []
        if source_level:
            rollup_rows = _load_rollup_rows_for_window(
                target_id=target_id,
                start_local=start_local,
                end_local=end_local,
                granularity=source_level,
                metric_hints=('ups_realpower', 'ups_power', 'ups_load', 'ups_realpower_nominal'),
            )
        if rollup_rows:
            aggregated_cost = _aggregate_energy_cost_from_rollups(
                rollup_rows,
                target_id=target_id,
                source_level=source_level or 'hour',
                group_level=level,
                timezone_obj=effective_tz,
                price_per_kwh=price_per_kwh,
                nominal_default=nominal_default,
            )
        else:
            aggregated_cost = _aggregate_energy_cost(
                rows,
                target_id=target_id,
                level=level,
                timezone_obj=effective_tz,
                price_per_kwh=price_per_kwh,
                nominal_default=nominal_default,
            )
    else:
        aggregated_cost = _aggregate_energy_cost(
            rows,
            target_id=target_id,
            level=level,
            timezone_obj=effective_tz,
            price_per_kwh=price_per_kwh,
            nominal_default=nominal_default,
        )
    return _build_energy_bucket_series(
        aggregated_cost=aggregated_cost,
        start_local=start_local,
        end_local=end_local,
        level=level,
    )


def build_energy_detailed_series(target_id: int, tz, from_iso: str, to_iso: str, detail_type: str) -> List[Dict[str, float]]:
    """Build bucketed cost bars for modal drilldown levels."""
    effective_tz = _resolve_target_timezone(target_id, tz)
    from_dt = _parse_iso_datetime(from_iso, effective_tz)
    to_dt = _parse_iso_datetime(to_iso, effective_tz)
    if not from_dt or not to_dt or from_dt >= to_dt:
        return []

    _, price_per_kwh, _ = get_powerflow_settings(target_id=target_id)
    nominal_default = _default_nominal_power()
    level = _normalize_energy_level(detail_type, fallback='hour')
    aggregated_cost: Dict[datetime, float]
    source_level = _resolve_energy_rollup_source_level(level)
    if source_level:
        rollup_rows = _load_rollup_rows_for_window(
            target_id=target_id,
            start_local=from_dt,
            end_local=to_dt,
            granularity=source_level,
            metric_hints=('ups_realpower', 'ups_power', 'ups_load', 'ups_realpower_nominal'),
        )
    else:
        rollup_rows = []

    if rollup_rows and level in {'month', 'day', 'hour'}:
        aggregated_cost = _aggregate_energy_cost_from_rollups(
            rollup_rows,
            target_id=target_id,
            source_level=source_level or 'hour',
            group_level=level,
            timezone_obj=effective_tz,
            price_per_kwh=price_per_kwh,
            nominal_default=nominal_default,
        )
    else:
        rows = _load_rows_for_window(
            target_id,
            from_dt,
            to_dt,
            metric_hints=('ups_realpower', 'ups_power', 'ups_load', 'ups_realpower_nominal'),
        )
        aggregated_cost = _aggregate_energy_cost(
            rows,
            target_id=target_id,
            level=level,
            timezone_obj=effective_tz,
            price_per_kwh=price_per_kwh,
            nominal_default=nominal_default,
        )
    return _build_energy_bucket_series(
        aggregated_cost=aggregated_cost,
        start_local=from_dt,
        end_local=to_dt,
        level=level,
    )


def list_available_years(target_id: int) -> List[int]:
    """Return up to 5 recent years available for target history."""
    _, _, Data = models()
    rows = db.session.query(
        func.strftime('%Y', Data.timestamp_utc)
    ).filter(
        Data.target_id == int(target_id)
    ).distinct().order_by(
        func.strftime('%Y', Data.timestamp_utc).desc()
    ).limit(5).all()

    years: List[int] = []
    for row in rows:
        raw_year = str(row[0] or '').strip()
        if not raw_year.isdigit():
            continue
        years.append(int(raw_year))
    return years
