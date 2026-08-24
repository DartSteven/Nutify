"""Materialized rollups for Multi-NUT snapshots."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional

import pandas as pd
import pytz
from sqlalchemy import text

from core.db.ups import db
from core.logger import system_logger as logger


ROLLUP_FLOAT_FIELDS = (
    'ups_load',
    'ups_power',
    'ups_realpower',
    'ups_realpower_nominal',
    'battery_charge',
    'battery_runtime',
    'battery_voltage',
    'battery_temperature',
    'input_voltage',
    'output_voltage',
    'input_transfer_low',
    'input_transfer_high',
)

ROLLUP_GRANULARITIES = {'minute', 'hour', 'day', 'month', 'year'}

_SETUP_LOCK = threading.Lock()
_SETUP_DONE = False

_TZ_CACHE: Dict[int, tuple[float, object]] = {}
_TZ_CACHE_TTL = 30.0


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _model_space():
    model_space = getattr(db, 'ModelClasses', None)
    if model_space is not None:
        return model_space

    try:
        from core.db.models import init_models

        init_models(db)
        return getattr(db, 'ModelClasses', None)
    except Exception as exc:
        logger.debug(f"Could not initialize ModelClasses for rollups: {exc}")
        return None


def _rollup_model():
    model_space = _model_space()
    if model_space is None:
        return None
    return getattr(model_space, 'UPSMonitorRollup', None)


def ensure_rollup_storage_support():
    """Ensure required indexes exist for fast snapshot and rollup reads."""
    global _SETUP_DONE
    if _SETUP_DONE:
        return

    with _SETUP_LOCK:
        if _SETUP_DONE:
            return
        try:
            with db.engine.begin() as conn:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_ups_monitor_data_target_ts "
                        "ON ups_monitor_data(target_id, timestamp_utc)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_rollup_target_gran_bucket "
                        "ON ups_monitor_rollups(target_id, granularity, bucket_start_utc)"
                    )
                )
            _SETUP_DONE = True
        except Exception as exc:
            logger.debug(f"Could not ensure rollup indexes: {exc}")


def _safe_localize(tz, dt_value: datetime) -> datetime:
    if dt_value.tzinfo is not None:
        return dt_value.astimezone(tz)
    try:
        return tz.localize(dt_value, is_dst=None)
    except Exception:
        return tz.localize(dt_value)


def _bucket_start_local(ts_local: datetime, granularity: str) -> datetime:
    if granularity == 'year':
        return ts_local.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    if granularity == 'month':
        return ts_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if granularity == 'day':
        return ts_local.replace(hour=0, minute=0, second=0, microsecond=0)
    if granularity == 'hour':
        return ts_local.replace(minute=0, second=0, microsecond=0)
    return ts_local.replace(second=0, microsecond=0)


def _advance_local(bucket_start_local: datetime, granularity: str) -> datetime:
    tz = bucket_start_local.tzinfo or pytz.UTC
    if granularity == 'minute':
        return tz.normalize(bucket_start_local + timedelta(minutes=1))
    if granularity == 'hour':
        return tz.normalize(bucket_start_local + timedelta(hours=1))
    if granularity == 'day':
        return tz.normalize(bucket_start_local + timedelta(days=1))
    if granularity == 'month':
        if bucket_start_local.month == 12:
            next_year = bucket_start_local.year + 1
            next_month = 1
        else:
            next_year = bucket_start_local.year
            next_month = bucket_start_local.month + 1
        return _safe_localize(tz, datetime(next_year, next_month, 1))
    return _safe_localize(tz, datetime(bucket_start_local.year + 1, 1, 1))


def _resolve_target_timezone(target_id: int):
    cache_key = int(target_id)
    now_monotonic = time.monotonic()
    cached = _TZ_CACHE.get(cache_key)
    if cached and cached[0] > now_monotonic:
        return cached[1]

    resolved = pytz.UTC
    try:
        from core.options.options import get_variable_config_row

        row, _ = get_variable_config_row(target_id=cache_key, include_global_fallback=True)
        timezone_name = str(getattr(row, 'timezone', '') or '').strip()
        if timezone_name:
            resolved = pytz.timezone(timezone_name)
    except Exception:
        resolved = pytz.UTC

    _TZ_CACHE[cache_key] = (now_monotonic + _TZ_CACHE_TTL, resolved)
    return resolved


def _aggregate_with_pandas(records: List[Dict[str, object]]) -> tuple[Dict[str, float], int]:
    if not records:
        return {}, 0

    frame = pd.DataFrame(records)
    if frame.empty:
        return {}, 0

    if 'sample_count' not in frame.columns:
        frame['sample_count'] = 1
    frame['sample_count'] = pd.to_numeric(frame['sample_count'], errors='coerce').fillna(1.0).clip(lower=0.0)

    output: Dict[str, float] = {}
    for field_name in ROLLUP_FLOAT_FIELDS:
        if field_name not in frame.columns:
            continue
        values = pd.to_numeric(frame[field_name], errors='coerce')
        valid = values.notna() & (frame['sample_count'] > 0)
        if not valid.any():
            continue
        weights = frame.loc[valid, 'sample_count']
        weighted_sum = (values[valid] * weights).sum()
        weight_total = weights.sum()
        if float(weight_total) <= 0.0:
            continue
        output[field_name] = float(weighted_sum / weight_total)

    samples = int(max(0, round(float(frame['sample_count'].sum()))))
    return output, samples


def _upsert_rollup(
    target_id: int,
    granularity: str,
    bucket_start_local: datetime,
    metrics: Dict[str, object],
    sample_count: int,
):
    Rollup = _rollup_model()
    if Rollup is None:
        return

    bucket_end_local = _advance_local(bucket_start_local, granularity)
    bucket_start_utc = bucket_start_local.astimezone(pytz.UTC)
    bucket_end_utc = bucket_end_local.astimezone(pytz.UTC)

    row = Rollup.query.filter(
        Rollup.target_id == int(target_id),
        Rollup.granularity == granularity,
        Rollup.bucket_start_utc == bucket_start_utc,
    ).first()

    if row is None:
        row = Rollup(
            target_id=int(target_id),
            granularity=granularity,
            bucket_start_utc=bucket_start_utc,
        )
        db.session.add(row)

    row.bucket_end_utc = bucket_end_utc
    row.sample_count = int(max(0, sample_count))
    for field_name in ROLLUP_FLOAT_FIELDS:
        setattr(row, field_name, _safe_float(metrics.get(field_name)))


def _load_source_rows(
    target_id: int,
    granularity: str,
    start_local: datetime,
    end_local: datetime,
) -> List[Dict[str, object]]:
    Rollup = _rollup_model()
    if Rollup is None:
        return []

    start_utc = start_local.astimezone(pytz.UTC)
    end_utc = end_local.astimezone(pytz.UTC)
    rows = Rollup.query.filter(
        Rollup.target_id == int(target_id),
        Rollup.granularity == granularity,
        Rollup.bucket_start_utc >= start_utc,
        Rollup.bucket_start_utc < end_utc,
    ).order_by(Rollup.bucket_start_utc.asc()).all()

    records: List[Dict[str, object]] = []
    for row in rows:
        payload = {'sample_count': int(getattr(row, 'sample_count', 0) or 0)}
        for field_name in ROLLUP_FLOAT_FIELDS:
            payload[field_name] = getattr(row, field_name, None)
        records.append(payload)
    return records


def _rebuild_rollup_bucket(
    target_id: int,
    *,
    target_granularity: str,
    source_granularity: str,
    bucket_start_local: datetime,
):
    bucket_end_local = _advance_local(bucket_start_local, target_granularity)
    records = _load_source_rows(
        target_id=target_id,
        granularity=source_granularity,
        start_local=bucket_start_local,
        end_local=bucket_end_local,
    )
    if not records:
        return
    aggregated, samples = _aggregate_with_pandas(records)
    if not aggregated and samples <= 0:
        return
    _upsert_rollup(
        target_id=target_id,
        granularity=target_granularity,
        bucket_start_local=bucket_start_local,
        metrics=aggregated,
        sample_count=samples,
    )


def update_rollups_after_snapshot(target_id: int, timestamp_utc: datetime, metrics: Dict[str, object]):
    """
    Update minute rollup and keep its complete parent chain current.

    Rollup chain:
    - minute: on each new persisted minute snapshot
    - hour/day/month/year: once when a new minute starts

    Updating parent buckets incrementally preserves partial hours and days when
    polling stops or the application restarts before a calendar boundary.
    """
    Rollup = _rollup_model()
    if Rollup is None:
        return

    ensure_rollup_storage_support()
    tz = _resolve_target_timezone(int(target_id))

    minute_local = _bucket_start_local(timestamp_utc.astimezone(tz), 'minute')
    minute_start_utc = minute_local.astimezone(pytz.UTC)
    is_new_minute = Rollup.query.filter(
        Rollup.target_id == int(target_id),
        Rollup.granularity == 'minute',
        Rollup.bucket_start_utc == minute_start_utc,
    ).first() is None
    minute_metrics, _ = _aggregate_with_pandas(
        [
            {
                **{field_name: metrics.get(field_name) for field_name in ROLLUP_FLOAT_FIELDS},
                'sample_count': 1,
            }
        ]
    )
    _upsert_rollup(
        target_id=int(target_id),
        granularity='minute',
        bucket_start_local=minute_local,
        metrics=minute_metrics,
        sample_count=1,
    )

    if not is_new_minute:
        return

    parent_chain = (
        ('hour', 'minute'),
        ('day', 'hour'),
        ('month', 'day'),
        ('year', 'month'),
    )
    for target_granularity, source_granularity in parent_chain:
        _rebuild_rollup_bucket(
            target_id=int(target_id),
            target_granularity=target_granularity,
            source_granularity=source_granularity,
            bucket_start_local=_bucket_start_local(minute_local, target_granularity),
        )


def load_rollup_history(
    target_id: int,
    *,
    granularity: str,
    start_utc: datetime,
    end_utc: datetime,
    metric_names: Iterable[str],
) -> List[Dict[str, object]]:
    """Load rollup rows as domain-proxy compatible history rows."""
    normalized = str(granularity or '').strip().lower()
    if normalized not in ROLLUP_GRANULARITIES:
        return []

    Rollup = _rollup_model()
    if Rollup is None:
        return []

    requested_metrics = tuple(
        dict.fromkeys(str(name).strip() for name in metric_names if str(name).strip())
    )
    if any(not hasattr(Rollup, metric_name) for metric_name in requested_metrics):
        # Returning no rollup rows makes the caller use raw snapshots for dynamic metrics.
        return []

    rows = Rollup.query.filter(
        Rollup.target_id == int(target_id),
        Rollup.granularity == normalized,
        Rollup.bucket_start_utc >= start_utc,
        Rollup.bucket_start_utc < end_utc,
    ).order_by(Rollup.bucket_start_utc.asc()).all()

    payload_rows: List[Dict[str, object]] = []
    for row in rows:
        ts = row.bucket_start_utc
        if ts is None:
            continue
        if ts.tzinfo is None:
            ts = pytz.UTC.localize(ts)
        else:
            ts = ts.astimezone(pytz.UTC)

        payload = {
            'target_id': int(target_id),
            'timestamp_utc': ts.isoformat(),
            '_timestamp': ts,
            '_timestamp_ms': int(ts.timestamp() * 1000),
            '_sample_count': int(getattr(row, 'sample_count', 0) or 0),
        }
        for metric_name in requested_metrics:
            payload[metric_name] = getattr(row, metric_name)
        payload_rows.append(payload)
    return payload_rows
