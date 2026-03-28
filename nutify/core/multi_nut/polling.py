"""Polling helpers for Multi-NUT targets."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional, Tuple

from core.db.ups import db
from core.db.ups.cache import websocket
from core.logger import system_logger as logger
from flask import current_app

from .connection import normalize_metrics, run_upsc_command
from .notifications import dispatch_target_event_notifications
from .power_events import collect_poll_failure_events, collect_power_transition_events, register_poll_success, reset_target_power_state
from .storage import (
    coerce_int,
    enabled_targets_count,
    get_enabled_targets,
    get_monitoring_profile,
    has_multiple_enabled_targets,
    mark_poll_error,
    record_target_error_snapshot,
    record_target_snapshot,
    should_poll_target,
    utc_now,
)


@dataclass
class _TargetBufferState:
    """In-memory per-target buffer used for minute-level DB aggregation."""

    minute_bucket: Optional[datetime] = None
    samples: List[Dict[str, object]] = field(default_factory=list)
    latest_raw_payload: Dict[str, object] = field(default_factory=dict)


class _MultiTargetMinuteBuffer:
    """Collect per-poll samples and expose one aggregated snapshot per minute."""

    def __init__(self):
        self._lock = Lock()
        self._states: Dict[int, _TargetBufferState] = {}

    @staticmethod
    def _minute_floor(timestamp_utc: datetime) -> datetime:
        return timestamp_utc.replace(second=0, microsecond=0)

    @staticmethod
    def _to_float(value: object) -> Optional[float]:
        if isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _state(self, target_id: int) -> _TargetBufferState:
        if target_id not in self._states:
            self._states[target_id] = _TargetBufferState()
        return self._states[target_id]

    def add_sample(
        self,
        target_id: int,
        timestamp_utc: datetime,
        metrics: Dict[str, object],
        raw_payload: Optional[Dict[str, object]] = None,
    ) -> None:
        with self._lock:
            state = self._state(target_id)
            if state.minute_bucket is None:
                state.minute_bucket = self._minute_floor(timestamp_utc)

            state.samples.append(dict(metrics or {}))
            state.latest_raw_payload = dict(raw_payload or {})

    def pop_completed_minute(
        self,
        target_id: int,
        now_utc: datetime,
    ) -> Optional[Tuple[datetime, Dict[str, object], Dict[str, object]]]:
        """
        Return one aggregated snapshot when minute bucket changes.

        A snapshot is returned only when at least one sample exists for the
        previous minute bucket.
        """
        with self._lock:
            state = self._state(target_id)
            current_bucket = self._minute_floor(now_utc)

            if state.minute_bucket is None:
                state.minute_bucket = current_bucket
                return None

            if current_bucket <= state.minute_bucket:
                return None

            completed_bucket = state.minute_bucket
            samples = list(state.samples)
            latest_raw_payload = dict(state.latest_raw_payload or {})

            state.minute_bucket = current_bucket
            state.samples = []
            state.latest_raw_payload = {}

        aggregated = self._aggregate_samples(samples)
        if not aggregated:
            return None
        return completed_bucket, aggregated, latest_raw_payload

    def _aggregate_samples(self, samples: List[Dict[str, object]]) -> Dict[str, object]:
        if not samples:
            return {}

        sums: Dict[str, float] = {}
        counts: Dict[str, int] = {}
        latest_text_values: Dict[str, object] = {}
        latest_sample = samples[-1]

        for sample in samples:
            for key, value in (sample or {}).items():
                if key in {'target_id', 'target_name'}:
                    continue

                numeric_value = self._to_float(value)
                if numeric_value is not None:
                    sums[key] = sums.get(key, 0.0) + numeric_value
                    counts[key] = counts.get(key, 0) + 1
                    continue

                if value is None:
                    continue
                latest_text_values[key] = value

        aggregated: Dict[str, object] = {
            key: round(sums[key] / counts[key], 4)
            for key in sums.keys()
            if counts.get(key)
        }
        aggregated.update(latest_text_values)

        for passthrough_key in (
            'ups_status',
            'device_model',
            'device_serial',
            'device_mfr',
            'input_sensitivity',
            'battery_type',
            'battery_date',
            'battery_mfr_date',
        ):
            if passthrough_key in latest_sample and latest_sample.get(passthrough_key) is not None:
                aggregated[passthrough_key] = latest_sample.get(passthrough_key)

        return aggregated


_minute_buffer = _MultiTargetMinuteBuffer()


def _flush_completed_minute_if_due(target, policy, now_utc: datetime):
    """Persist one aggregated row when minute rollover occurs for the target."""
    pending = _minute_buffer.pop_completed_minute(target.id, now_utc)
    if not pending:
        return

    minute_bucket, metrics, raw_payload = pending
    flush_timestamp = minute_bucket.replace(second=59, microsecond=999999)

    record_target_snapshot(
        target=target,
        policy=policy,
        metrics=metrics,
        timestamp_utc=flush_timestamp,
        raw_payload=raw_payload,
    )


def _mark_poll_success(policy, timestamp_utc: datetime):
    """Persist polling metadata without creating a data snapshot row."""
    policy.last_polled_at = timestamp_utc
    policy.last_success_at = timestamp_utc
    policy.last_error = None


def _emit_target_update(target_id: int, target_name: str, metrics: Dict[str, object], timestamp_iso: str):
    """Send websocket update for multi-target pages."""
    if websocket is None or not hasattr(websocket, 'emit'):
        logger.debug('Skipping Multi-NUT websocket emit: websocket transport is not available')
        return

    normalized_metrics: Dict[str, object] = {}
    for key, value in (metrics or {}).items():
        if key in {'target_id', 'target_name'}:
            continue
        normalized_metrics[str(key)] = value

    payload = {
        'target_id': target_id,
        'target_name': target_name,
        'timestamp': timestamp_iso,
        'metrics': normalized_metrics,
    }
    websocket.emit('multi_target_update', payload)


def _offline_metrics(status: str) -> Dict[str, object]:
    """Build minimal metric payload for offline websocket updates."""
    return {'ups_status': status, 'battery_charge': None, 'battery_runtime': None, 'ups_load': None, 'ups_realpower': None, 'input_voltage': None}


def _emit_lifecycle_event(*, target, policy, event_type: str, metrics: Optional[Dict[str, object]] = None, reason: Optional[object] = None) -> None:
    """Emit target COMMBAD/COMMOK through the canonical UPS event pipeline."""
    payload_metrics = dict(metrics or {})
    payload = {
        'ups': target.ups_name,
        'event': str(event_type).upper(),
        'target_id': int(target.id),
        'source_ip': target.host,
        'target_name': target.name,
    }
    if reason is not None:
        payload['message'] = str(reason)
    payload.update(payload_metrics)

    try:
        from core.upsmon import handle_nut_event

        if handle_nut_event(current_app, payload):
            return
        logger.warning("Multi-NUT lifecycle event handler returned False; using notification fallback target_id=%s event=%s", target.id, payload['event'])
    except Exception as exc:
        logger.warning("Multi-NUT lifecycle event dispatch failed; using notification fallback target_id=%s event=%s error=%s", target.id, payload['event'], exc)

    dispatch_result = dispatch_target_event_notifications(
        target=target,
        policy=policy,
        event_type=payload['event'],
        metrics=payload_metrics,
        reason=reason,
    )
    logger.info(
        "Multi-NUT fallback notifications for target=%s event=%s scope=%s success=%s",
        target.id,
        payload['event'],
        dispatch_result.get('scope'),
        dispatch_result.get('success'),
    )


def _persist_error_state(target, policy, error_message: str, timestamp_utc: datetime, had_previous_error: bool, target_context: str) -> str:
    """Persist failure metadata and first offline snapshot for a new outage."""
    offline_status = 'ERROR'
    if had_previous_error:
        mark_poll_error(target.id, error_message, timestamp_utc=timestamp_utc)
        offline_status = 'NOCOMM'
    else:
        try:
            offline_status = record_target_error_snapshot(
                target=target,
                policy=policy,
                error_message=error_message,
                timestamp_utc=timestamp_utc,
            )
        except Exception as snapshot_exc:
            db.session.rollback()
            mark_poll_error(target.id, error_message, timestamp_utc=timestamp_utc)
            logger.error(
                f"Multi-NUT failed to persist error snapshot for {target_context}: {snapshot_exc}"
            )

    target.last_test_status = False
    target.last_test_error = str(error_message)[:1000]
    db.session.commit()
    return offline_status


def get_multi_polling_sleep_seconds(default_interval: int = 1) -> int:
    """
    Return the scheduler cadence for the multi-target polling loop.

    The global loop has to wake up at least as fast as the smallest target
    interval so each target policy can be respected by should_poll_target().
    """
    try:
        intervals: List[int] = []
        for _target, policy in get_enabled_targets():
            if not policy:
                continue
            interval = coerce_int(getattr(policy, 'polling_interval', default_interval), 5, 1, 60)
            intervals.append(interval)

        if not intervals:
            return max(1, int(default_interval))
        return max(1, min(intervals))
    except Exception as exc:
        logger.debug(f"Unable to compute Multi-NUT loop interval: {exc}")
        return max(1, int(default_interval))


def poll_multi_targets_once(timeout: int = 10) -> Dict[str, object]:
    """Poll all enabled Multi-NUT targets once."""
    now_utc = utc_now()
    polled = 0
    skipped = 0
    failed = 0
    events: List[Dict[str, object]] = []

    for target, policy in get_enabled_targets():
        target_context = (
            f"id={target.id} name={target.name} "
            f"target={target.ups_name}@{target.host}:{target.port}"
        )
        had_previous_error = bool(getattr(policy, 'last_error', None))

        if not should_poll_target(policy, now_utc):
            skipped += 1
            logger.debug(f"Multi-NUT poll skipped for {target_context}")
            continue

        try:
            _flush_completed_minute_if_due(target=target, policy=policy, now_utc=now_utc)
        except Exception as flush_exc:
            db.session.rollback()
            logger.error(f"Multi-NUT minute flush failed for {target_context}: {flush_exc}")

        logger.debug(f"Multi-NUT polling target {target_context}")
        policy_interval = coerce_int(getattr(policy, 'polling_interval', 5), 5, 1, 60)
        request_timeout = max(2, min(int(timeout), policy_interval + 1))

        success, raw_payload, error = run_upsc_command(
            ups_name=target.ups_name,
            host=target.host,
            port=target.port,
            command_path=target.command_path,
            timeout=request_timeout,
            target_id=target.id,
        )

        if not success:
            failed += 1
            offline_status = _persist_error_state(
                target=target,
                policy=policy,
                error_message=str(error),
                timestamp_utc=now_utc,
                had_previous_error=had_previous_error,
                target_context=target_context,
            )

            logger.warning(f"Multi-NUT polling failed for {target_context}: {error}")

            _emit_target_update(
                target_id=target.id,
                target_name=target.name,
                metrics=_offline_metrics(offline_status),
                timestamp_iso=now_utc.isoformat(),
            )

            if not had_previous_error:
                reset_target_power_state(target.id)
                _emit_lifecycle_event(
                    target=target,
                    policy=policy,
                    event_type='COMMBAD',
                    metrics={},
                    reason=error,
                )
            for outage_event in collect_poll_failure_events(target.id, had_previous_error):
                _emit_lifecycle_event(
                    target=target,
                    policy=policy,
                    event_type=outage_event,
                    metrics={},
                    reason=error,
                )

            events.append(
                {
                    'target_id': target.id,
                    'target_name': target.name,
                    'status': 'error',
                    'ups_status': offline_status,
                    'error': error,
                }
            )
            continue

        metrics = normalize_metrics(raw_payload, target_id=target.id)

        try:
            _minute_buffer.add_sample(
                target_id=target.id,
                timestamp_utc=now_utc,
                metrics=metrics,
                raw_payload=raw_payload,
            )
            _mark_poll_success(policy, now_utc)

            polled += 1
            target.last_test_status = True
            target.last_test_error = None
            db.session.commit()

            _emit_target_update(
                target_id=target.id,
                target_name=target.name,
                metrics=metrics,
                timestamp_iso=now_utc.isoformat(),
            )

            logger.debug(f"Multi-NUT polling success for {target_context}")

            if had_previous_error:
                _emit_lifecycle_event(
                    target=target,
                    policy=policy,
                    event_type='COMMOK',
                    metrics=metrics,
                )
            register_poll_success(target.id)
            for power_event in collect_power_transition_events(target.id, metrics):
                _emit_lifecycle_event(
                    target=target,
                    policy=policy,
                    event_type=power_event,
                    metrics=metrics,
                )

            events.append(
                {
                    'target_id': target.id,
                    'target_name': target.name,
                    'status': 'ok',
                }
            )
        except Exception as exc:
            failed += 1
            db.session.rollback()

            offline_status = _persist_error_state(
                target=target,
                policy=policy,
                error_message=str(exc),
                timestamp_utc=now_utc,
                had_previous_error=had_previous_error,
                target_context=target_context,
            )

            _emit_target_update(
                target_id=target.id,
                target_name=target.name,
                metrics=_offline_metrics(offline_status),
                timestamp_iso=now_utc.isoformat(),
            )
            logger.error(f"Multi-NUT snapshot buffering failed for {target_context}: {exc}")
            events.append(
                {
                    'target_id': target.id,
                    'target_name': target.name,
                    'status': 'error',
                    'ups_status': offline_status,
                    'error': str(exc),
                }
            )

    if polled > 0 or failed > 0:
        logger.info(
            f"Multi-NUT polling cycle complete: polled={polled}, failed={failed}, skipped={skipped}"
        )

    return {
        'polled': polled,
        'failed': failed,
        'skipped': skipped,
        'events': events,
    }


def get_multi_nut_runtime_state() -> Dict[str, object]:
    """Return lightweight runtime info for top-bar/UI state."""
    count = enabled_targets_count()
    profile = get_monitoring_profile()
    has_multiple_targets = has_multiple_enabled_targets()
    return {
        'enabled_targets': count,
        'multi_enabled': profile == 'multi' and has_multiple_targets,
        'monitoring_profile': profile,
    }
