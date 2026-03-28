"""Snapshot persistence helpers for Multi-NUT."""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pytz
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from core.db.ups import db

from .storage_core import (
    coerce_int,
    get_target_with_policy,
    models,
    utc_now,
)
from .rollups import ensure_rollup_storage_support, update_rollups_after_snapshot


CANONICAL_FLOAT_FIELDS = (
    'ups_load',
    'ups_power',
    'ups_power_nominal',
    'ups_realpower',
    'ups_realpower_nominal',
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
    'input_voltage',
    'input_voltage_nominal',
    'input_transfer_low',
    'input_transfer_high',
    'input_current',
    'input_frequency',
    'input_frequency_nominal',
    'output_voltage',
    'output_voltage_nominal',
    'output_current',
    'output_frequency',
    'output_frequency_nominal',
)

CANONICAL_TEXT_FIELDS = (
    'ups_status',
    'input_sensitivity',
    'device_model',
    'device_serial',
    'device_mfr',
    'battery_type',
    'battery_date',
    'battery_mfr_date',
)

PROFILE_TEXT_FIELDS = (
    'input_sensitivity',
    'device_model',
    'device_serial',
    'device_mfr',
    'battery_type',
    'battery_date',
    'battery_mfr_date',
)

_PROFILE_CACHE: Dict[int, tuple[float, Dict[str, object]]] = {}
_PROFILE_CACHE_TTL = 30.0


_external_lock = threading.Lock()
_external_engines: Dict[str, object] = {}
_external_sessionmakers: Dict[str, object] = {}

ExternalBase = declarative_base()


class ExternalUPSMonitorData(ExternalBase):
    """External SQLite table for separate strategy."""

    __tablename__ = 'ups_monitor_data'

    id = Column(Integer, primary_key=True)
    target_id = Column(Integer, nullable=False, index=True)
    timestamp_utc = Column(DateTime(timezone=True), nullable=False, index=True)
    shard_key = Column(String(20), nullable=True, index=True)

    ups_status = Column(String(255), nullable=True)
    ups_load = Column(Float, nullable=True)
    ups_power = Column(Float, nullable=True)
    ups_power_nominal = Column(Float, nullable=True)
    ups_realpower = Column(Float, nullable=True)
    ups_realpower_nominal = Column(Float, nullable=True)

    battery_charge = Column(Float, nullable=True)
    battery_charge_low = Column(Float, nullable=True)
    battery_charge_warning = Column(Float, nullable=True)
    battery_runtime = Column(Float, nullable=True)
    battery_runtime_low = Column(Float, nullable=True)
    battery_voltage = Column(Float, nullable=True)
    battery_voltage_nominal = Column(Float, nullable=True)
    battery_current = Column(Float, nullable=True)
    battery_temperature = Column(Float, nullable=True)
    battery_alarm_threshold = Column(Float, nullable=True)

    input_voltage = Column(Float, nullable=True)
    input_voltage_nominal = Column(Float, nullable=True)
    input_transfer_low = Column(Float, nullable=True)
    input_transfer_high = Column(Float, nullable=True)
    input_sensitivity = Column(String(255), nullable=True)
    input_current = Column(Float, nullable=True)
    input_frequency = Column(Float, nullable=True)
    input_frequency_nominal = Column(Float, nullable=True)

    output_voltage = Column(Float, nullable=True)
    output_voltage_nominal = Column(Float, nullable=True)
    output_current = Column(Float, nullable=True)
    output_frequency = Column(Float, nullable=True)
    output_frequency_nominal = Column(Float, nullable=True)

    device_model = Column(String(255), nullable=True)
    device_serial = Column(String(255), nullable=True)
    device_mfr = Column(String(255), nullable=True)
    battery_type = Column(String(255), nullable=True)
    battery_date = Column(String(255), nullable=True)
    battery_mfr_date = Column(String(255), nullable=True)

    data_json = Column(Text, nullable=True)
    raw_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(pytz.UTC))


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_text(value):
    if value is None:
        return None
    return str(value)


def _serialize_json(payload: Dict[str, object]) -> str:
    try:
        return json.dumps(payload or {}, ensure_ascii=True)
    except Exception:
        return '{}'


def _model_space():
    return getattr(db, 'ModelClasses', None)


def _profile_model():
    model_space = _model_space()
    if model_space is None:
        return None
    return getattr(model_space, 'UPSMonitorTargetProfile', None)


def _rollup_model():
    model_space = _model_space()
    if model_space is None:
        return None
    return getattr(model_space, 'UPSMonitorRollup', None)


def _load_profile_payload(target_id: int) -> Dict[str, object]:
    cache_key = int(target_id)
    now_monotonic = time.monotonic()
    cached = _PROFILE_CACHE.get(cache_key)
    if cached and cached[0] > now_monotonic:
        return dict(cached[1])

    Profile = _profile_model()
    if Profile is None:
        return {}

    row = Profile.query.filter(Profile.target_id == cache_key).first()
    if row is None:
        payload: Dict[str, object] = {}
    else:
        payload = row.to_dict() if hasattr(row, 'to_dict') else {
            field_name: getattr(row, field_name, None) for field_name in PROFILE_TEXT_FIELDS
        }

    _PROFILE_CACHE[cache_key] = (now_monotonic + _PROFILE_CACHE_TTL, dict(payload))
    return payload


def _persist_profile_fields(target_id: int, metrics: Dict[str, object]):
    Profile = _profile_model()
    if Profile is None:
        return

    row = Profile.query.filter(Profile.target_id == int(target_id)).first()
    if row is None:
        row = Profile(target_id=int(target_id))
        db.session.add(row)

    changed = False
    for field_name in PROFILE_TEXT_FIELDS:
        value = _safe_text(metrics.get(field_name))
        if value is None:
            continue
        if getattr(row, field_name, None) != value:
            setattr(row, field_name, value)
            changed = True

    if changed:
        _PROFILE_CACHE[int(target_id)] = (
            time.monotonic() + _PROFILE_CACHE_TTL,
            row.to_dict() if hasattr(row, 'to_dict') else {
                field_name: getattr(row, field_name, None) for field_name in PROFILE_TEXT_FIELDS
            },
        )


def _latest_non_null_payload(target_id: int, payload_field: str) -> Optional[str]:
    _, _, Data = models()
    if not hasattr(Data, payload_field):
        return None
    column = getattr(Data, payload_field)
    row = db.session.query(column).filter(
        Data.target_id == int(target_id),
        column.isnot(None),
    ).order_by(
        Data.timestamp_utc.desc()
    ).first()
    if not row:
        return None
    return row[0]


def _shard_key_for(timestamp_utc: datetime, strategy: str, granularity: str) -> Optional[str]:
    if strategy == 'shared':
        return 'shared'
    if strategy != 'sharded':
        return None
    if granularity == 'day':
        return timestamp_utc.strftime('%Y%m%d')
    return timestamp_utc.strftime('%Y%m')


def _snapshot_row_kwargs(
    metrics: Dict[str, object],
    timestamp_utc: datetime,
    strategy: str,
    granularity: str,
    raw_payload: Optional[Dict[str, object]] = None,
    previous_data_json: Optional[str] = None,
    previous_raw_json: Optional[str] = None,
) -> Dict[str, object]:
    canonical_metrics = dict(metrics or {})
    for field_name in PROFILE_TEXT_FIELDS:
        canonical_metrics.pop(field_name, None)

    canonical_json = _serialize_json(canonical_metrics)
    source_raw_json = _serialize_json(raw_payload or {})

    kwargs = {
        'timestamp_utc': timestamp_utc,
        'shard_key': _shard_key_for(timestamp_utc, strategy, granularity),
        'data_json': None if canonical_json == previous_data_json else canonical_json,
        'raw_json': None if source_raw_json == previous_raw_json else source_raw_json,
    }

    for field_name in CANONICAL_FLOAT_FIELDS:
        kwargs[field_name] = _safe_float(metrics.get(field_name))
    for field_name in CANONICAL_TEXT_FIELDS:
        if field_name in PROFILE_TEXT_FIELDS:
            kwargs[field_name] = None
            continue
        kwargs[field_name] = _safe_text(metrics.get(field_name))

    return kwargs


def _external_row_to_dict(row: ExternalUPSMonitorData) -> Dict[str, object]:
    payload = {
        'id': row.id,
        'target_id': row.target_id,
        'timestamp_utc': row.timestamp_utc.isoformat() if row.timestamp_utc else None,
        'shard_key': row.shard_key,
        'data_json': row.data_json,
        'raw_json': row.raw_json,
        'created_at': row.created_at.isoformat() if row.created_at else None,
    }

    for field_name in CANONICAL_FLOAT_FIELDS:
        payload[field_name] = getattr(row, field_name)
    for field_name in CANONICAL_TEXT_FIELDS:
        payload[field_name] = getattr(row, field_name)

    return payload


def _get_external_session(db_path: str):
    normalized_path = os.path.abspath(db_path)

    with _external_lock:
        if normalized_path not in _external_engines:
            directory = os.path.dirname(normalized_path)
            os.makedirs(directory, exist_ok=True)
            engine = create_engine(f"sqlite:///{normalized_path}")
            ExternalBase.metadata.create_all(engine)
            _external_engines[normalized_path] = engine
            _external_sessionmakers[normalized_path] = sessionmaker(bind=engine)

        session_factory = _external_sessionmakers[normalized_path]

    return session_factory()


def should_poll_target(policy, now_utc: datetime) -> bool:
    """Decide if target should be polled on this cycle."""
    if not policy:
        return True
    if not policy.last_polled_at:
        return True

    last_polled_at = policy.last_polled_at
    if isinstance(last_polled_at, datetime) and last_polled_at.tzinfo is None:
        last_polled_at = pytz.UTC.localize(last_polled_at)

    interval = coerce_int(policy.polling_interval, 5, 1, 60)
    return now_utc >= (last_polled_at + timedelta(seconds=interval))


def _save_snapshot_main_db(
    target_id: int,
    policy,
    metrics: Dict[str, object],
    timestamp_utc: datetime,
    raw_payload: Optional[Dict[str, object]] = None,
):
    ensure_rollup_storage_support()
    _, _, Data = models()
    _persist_profile_fields(target_id, metrics)

    previous_data_json = _latest_non_null_payload(target_id, 'data_json')
    previous_raw_json = _latest_non_null_payload(target_id, 'raw_json')

    row_kwargs = _snapshot_row_kwargs(
        metrics=metrics,
        timestamp_utc=timestamp_utc,
        strategy=policy.db_strategy,
        granularity=policy.shard_granularity,
        raw_payload=raw_payload,
        previous_data_json=previous_data_json,
        previous_raw_json=previous_raw_json,
    )
    row_kwargs['target_id'] = target_id
    record = Data(**row_kwargs)
    db.session.add(record)


def infer_error_status(error_message: str | None) -> str:
    """Map poll error message to a canonical offline status."""
    message = str(error_message or '').strip().lower()
    if not message:
        return 'ERROR'

    if 'timed out' in message or 'timeout' in message:
        return 'TIMEOUT'

    connection_markers = (
        'connection refused',
        'connection reset',
        'network is unreachable',
        'no route to host',
        'name or service not known',
        'unknown host',
        'not connected',
        'no such file',
        'driver not connected',
        'cannot open',
        'ups is unavailable',
        'data stale',
        'not responding',
    )
    if any(marker in message for marker in connection_markers):
        return 'NOCOMM'

    return 'ERROR'


def _save_snapshot_separate_db(
    db_path: str,
    target_id: int,
    policy,
    metrics: Dict[str, object],
    timestamp_utc: datetime,
    raw_payload: Optional[Dict[str, object]] = None,
):
    session = _get_external_session(db_path)
    try:
        row_kwargs = _snapshot_row_kwargs(
            metrics=metrics,
            timestamp_utc=timestamp_utc,
            strategy=policy.db_strategy,
            granularity=policy.shard_granularity,
            raw_payload=raw_payload,
        )
        row_kwargs['target_id'] = target_id
        row_kwargs['created_at'] = utc_now()

        record = ExternalUPSMonitorData(**row_kwargs)
        session.add(record)
        session.commit()
    finally:
        session.close()


def _prune_main_db_data(target_id: int, retention_days: int):
    if retention_days <= 0:
        return
    _, _, Data = models()
    cutoff = utc_now() - timedelta(days=retention_days)
    Data.query.filter(
        Data.target_id == target_id,
        Data.timestamp_utc < cutoff,
    ).delete(synchronize_session=False)


def _prune_separate_db_data(db_path: str, target_id: int, retention_days: int):
    if retention_days <= 0:
        return
    session = _get_external_session(db_path)
    try:
        cutoff = utc_now() - timedelta(days=retention_days)
        session.query(ExternalUPSMonitorData).filter(
            ExternalUPSMonitorData.target_id == target_id,
            ExternalUPSMonitorData.timestamp_utc < cutoff,
        ).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()


def record_target_snapshot(
    target,
    policy,
    metrics: Dict[str, object],
    timestamp_utc: Optional[datetime] = None,
    raw_payload: Optional[Dict[str, object]] = None,
):
    """Persist one target snapshot based on selected db strategy."""
    timestamp_utc = timestamp_utc or utc_now()
    _save_snapshot_main_db(
        target_id=target.id,
        policy=policy,
        metrics=metrics,
        timestamp_utc=timestamp_utc,
        raw_payload=raw_payload,
    )
    try:
        update_rollups_after_snapshot(
            target_id=target.id,
            timestamp_utc=timestamp_utc,
            metrics=metrics,
        )
    except Exception as rollup_exc:
        logger.debug(f"Rollup update skipped for target {target.id}: {rollup_exc}")
    _prune_main_db_data(target.id, coerce_int(policy.retention_days, 0, 0, 3650))

    policy.last_polled_at = timestamp_utc
    policy.last_success_at = timestamp_utc
    policy.last_error = None
    db.session.commit()


def mark_poll_error(target_id: int, error_message: str, timestamp_utc: Optional[datetime] = None):
    """Persist error status for target policy."""
    _, Policy, _ = models()
    policy = Policy.query.filter_by(target_id=target_id).first()
    if not policy:
        return

    timestamp_utc = timestamp_utc or utc_now()
    policy.last_polled_at = timestamp_utc
    policy.last_error = str(error_message)[:1000]
    db.session.commit()


def record_target_error_snapshot(
    target,
    policy,
    error_message: str,
    timestamp_utc: Optional[datetime] = None,
) -> str:
    """
    Persist an offline snapshot for a failed target poll and mark policy error state.

    Returns the canonical offline status assigned to the snapshot.
    """
    timestamp_utc = timestamp_utc or utc_now()
    normalized_error = str(error_message or '').strip()
    offline_status = infer_error_status(normalized_error)
    metrics = {'ups_status': offline_status}
    raw_payload = {'poll_error': normalized_error, 'offline_status': offline_status}
    _save_snapshot_main_db(
        target_id=target.id,
        policy=policy,
        metrics=metrics,
        timestamp_utc=timestamp_utc,
        raw_payload=raw_payload,
    )
    try:
        update_rollups_after_snapshot(
            target_id=target.id,
            timestamp_utc=timestamp_utc,
            metrics=metrics,
        )
    except Exception as rollup_exc:
        logger.debug(f"Rollup update skipped for error snapshot target {target.id}: {rollup_exc}")
    _prune_main_db_data(target.id, coerce_int(policy.retention_days, 0, 0, 3650))

    policy.last_polled_at = timestamp_utc
    policy.last_error = normalized_error[:1000]
    db.session.commit()
    return offline_status


def _load_snapshots_main_db(target_id: int, hours: int, limit: int):
    _, _, Data = models()
    cutoff = utc_now() - timedelta(hours=hours)
    rows = Data.query.filter(
        Data.target_id == target_id,
        Data.timestamp_utc >= cutoff,
    ).order_by(Data.timestamp_utc.desc()).limit(limit).all()

    return [row.to_dict() for row in reversed(rows)]


def _load_snapshots_separate_db(db_path: str, target_id: int, hours: int, limit: int):
    session = _get_external_session(db_path)
    try:
        cutoff = utc_now() - timedelta(hours=hours)
        rows = session.query(ExternalUPSMonitorData).filter(
            ExternalUPSMonitorData.target_id == target_id,
            ExternalUPSMonitorData.timestamp_utc >= cutoff,
        ).order_by(ExternalUPSMonitorData.timestamp_utc.desc()).limit(limit).all()

        return [_external_row_to_dict(row) for row in reversed(rows)]
    finally:
        session.close()


def _latest_snapshot_main_db(target_id: int) -> Optional[Dict[str, object]]:
    _, _, Data = models()
    row = Data.query.filter(
        Data.target_id == target_id,
    ).order_by(Data.timestamp_utc.desc()).first()

    return row.to_dict() if row else None


def _latest_snapshot_separate_db(db_path: str, target_id: int) -> Optional[Dict[str, object]]:
    session = _get_external_session(db_path)
    try:
        row = session.query(ExternalUPSMonitorData).filter(
            ExternalUPSMonitorData.target_id == target_id,
        ).order_by(ExternalUPSMonitorData.timestamp_utc.desc()).first()

        if not row:
            return None

        return _external_row_to_dict(row)
    finally:
        session.close()


def load_target_history(target_id: int, hours: int = 24, limit: int = 5000) -> List[Dict[str, object]]:
    """Load target history from the shared storage backend."""
    target, policy = get_target_with_policy(target_id)
    if not target or not policy:
        return []

    bounded_hours = coerce_int(hours, 24, 1, 24 * 365)
    bounded_limit = coerce_int(limit, 5000, 10, 20000)
    return _load_snapshots_main_db(target.id, bounded_hours, bounded_limit)


def get_latest_target_snapshot(target_id: int) -> Optional[Dict[str, object]]:
    """Return latest snapshot for target."""
    target, policy = get_target_with_policy(target_id)
    if not target or not policy:
        return None

    return _latest_snapshot_main_db(target.id)


def extract_metric(row: Dict[str, object], key: str):
    """Extract metric from row or JSON payload fallback."""
    value = row.get(key)
    if value is not None:
        return value

    raw_json = row.get('data_json')
    if raw_json:
        try:
            payload = json.loads(raw_json)
            if isinstance(payload, dict):
                if key in payload:
                    return payload.get(key)
                dot_variant = key.replace('_', '.')
                if dot_variant in payload:
                    return payload.get(dot_variant)
        except Exception:
            pass

    original_raw = row.get('raw_json')
    if original_raw:
        try:
            payload = json.loads(original_raw)
            if isinstance(payload, dict):
                if key in payload:
                    return payload.get(key)
                dot_variant = key.replace('_', '.')
                if dot_variant in payload:
                    return payload.get(dot_variant)
        except Exception:
            pass

    if key in PROFILE_TEXT_FIELDS:
        target_id = row.get('target_id')
        if target_id is not None:
            profile_payload = _load_profile_payload(int(target_id))
            if key in profile_payload and profile_payload.get(key) is not None:
                return profile_payload.get(key)

    return None


def parse_iso_timestamp(value: str) -> Optional[datetime]:
    """Parse iso timestamp to UTC datetime."""
    if not value:
        return None

    normalized_value = str(value).strip()
    if normalized_value.endswith('Z'):
        normalized_value = f"{normalized_value[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(normalized_value)
    except (TypeError, ValueError):
        return None

    if parsed.tzinfo is None:
        return pytz.UTC.localize(parsed)
    return parsed.astimezone(pytz.UTC)
