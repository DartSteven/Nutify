"""Upsmon Module.

Implements core runtime logic and helpers used by this feature.
"""

from __future__ import annotations

from flask import jsonify, current_app, has_app_context
from datetime import datetime, timezone
from typing import Dict
import pytz
from ..db.ups import db, data_lock
from ..logger import upsmon_logger as logger
from core.events.time_utils import serialize_utc_timestamp, utc_now
from core.multi_nut.target_scope import resolve_settings_target_id
from .event_dedupe import find_recent_duplicate_event
from .event_payload import normalize_event_type, resolve_target_id_from_payload, safe_positive_int

logger.info("🌑 Initializing upsmon_client")

# Initialize UPSEvent from ModelClasses
UPSEvent = None
_EVENT_METRIC_ALIASES = {
    'ups_status': ('ups_status', 'ups.status', 'status'),
    'battery_charge': ('battery_charge', 'battery.charge'),
    'battery_runtime': ('battery_runtime', 'battery.runtime'),
    'ups_load': ('ups_load', 'ups.load'),
    'ups_realpower': ('ups_realpower', 'ups.realpower'),
    'input_voltage': ('input_voltage', 'input.voltage'),
    'output_voltage': ('output_voltage', 'output.voltage'),
    'battery_voltage': ('battery_voltage', 'battery.voltage'),
    'battery_temperature': ('battery_temperature', 'battery.temperature', 'ups_temperature', 'ups.temperature'),
}
_NUMERIC_EVENT_METRICS = {
    'battery_charge',
    'battery_runtime',
    'ups_load',
    'ups_realpower',
    'input_voltage',
    'output_voltage',
    'battery_voltage',
    'battery_temperature',
}
def _resolve_active_db():
    """Resolve the SQLAlchemy handle bound to the active Flask app context."""
    if not has_app_context():
        return db

    try:
        extension = current_app.extensions.get('sqlalchemy')
    except Exception:
        return db

    if extension is None:
        return db

    # Flask-SQLAlchemy 3.x may store either db directly or an extension wrapper.
    if hasattr(extension, 'session') and hasattr(extension, 'Model'):
        return extension

    extension_db = getattr(extension, 'db', None)
    if extension_db is not None and hasattr(extension_db, 'session'):
        return extension_db

    return db


def _is_sqlalchemy_ready(active_db):
    """Return True when SQLAlchemy is initialized for current app."""
    if not has_app_context():
        return False
    if not hasattr(active_db, 'session'):
        return False
    try:
        return current_app.extensions.get('sqlalchemy') is not None
    except Exception:
        return False


def _init_models_if_needed(active_db=None, force_reload=False):
    """Initialize UPSEvent model from ModelClasses if needed."""
    global UPSEvent
    db_handle = active_db or _resolve_active_db()

    if UPSEvent is not None and not force_reload:
        return True

    model_space = getattr(db_handle, 'ModelClasses', None)
    if model_space is not None and hasattr(model_space, 'UPSEvent'):
        UPSEvent = model_space.UPSEvent
        logger.debug("📚 UPSEvent model initialized from db.ModelClasses")
        return True

    # Fall back to lazy model bootstrap.
    from ..db.models import init_models

    timezone_getter = None
    if has_app_context() and hasattr(current_app, 'CACHE_TIMEZONE'):
        timezone_getter = lambda: current_app.CACHE_TIMEZONE

    try:
        init_models(db_handle, timezone_getter)
    except Exception as exc:
        logger.warning(f"Could not initialize UPSEvent model lazily: {exc}")
        return False

    model_space = getattr(db_handle, 'ModelClasses', None)
    if model_space is not None and hasattr(model_space, 'UPSEvent'):
        UPSEvent = model_space.UPSEvent
        logger.debug("📚 UPSEvent model initialized after init_models")
        return True

    logger.error("❌ Failed to initialize UPSEvent model")
    return False


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_metric_value(metric_name: str, value):
    if value in (None, ''):
        return None
    if metric_name in _NUMERIC_EVENT_METRICS:
        return _safe_float(value)
    if metric_name == 'ups_status':
        normalized = str(value).strip()
        return normalized or None
    return value


def _extract_metric_from_payload(payload: dict, aliases: tuple[str, ...]):
    for alias in aliases:
        if alias in payload:
            return payload.get(alias)
    return None


def _extract_event_metrics(payload: dict) -> Dict[str, object]:
    metrics: Dict[str, object] = {}
    if not isinstance(payload, dict):
        return metrics

    for metric_name, aliases in _EVENT_METRIC_ALIASES.items():
        raw_value = _extract_metric_from_payload(payload, aliases)
        value = _coerce_metric_value(metric_name, raw_value)
        if value is not None:
            metrics[metric_name] = value
    return metrics


def _merge_missing_metrics_from_latest_rows(active_db, target_id: int, metrics: Dict[str, object]) -> Dict[str, object]:
    if not target_id:
        return metrics

    model_space = getattr(active_db, 'ModelClasses', None)
    data_model = getattr(model_space, 'UPSMonitorData', None) if model_space is not None else None
    if data_model is None:
        return metrics

    missing = [key for key in _EVENT_METRIC_ALIASES.keys() if metrics.get(key) is None]
    if not missing:
        return metrics

    try:
        rows = (
            active_db.session.query(data_model)
            .filter(data_model.target_id == int(target_id))
            .order_by(data_model.timestamp_utc.desc())
            .limit(1440)
            .all()
        )
    except Exception as exc:
        logger.debug("Could not query UPSMonitorData for notification metrics target_id=%s: %s", target_id, exc)
        return metrics

    for row in rows:
        for metric_name in list(missing):
            if not hasattr(row, metric_name):
                missing.remove(metric_name)
                continue
            value = _coerce_metric_value(metric_name, getattr(row, metric_name, None))
            if value is None:
                continue
            metrics[metric_name] = value
            missing.remove(metric_name)
        if not missing:
            break

    return metrics


def _resolve_notification_metrics(payload: dict, parsed_target_id: int | None, active_db, is_db_ready: bool) -> Dict[str, object]:
    metrics = _extract_event_metrics(payload)
    if parsed_target_id is None or not is_db_ready:
        return metrics
    return _merge_missing_metrics_from_latest_rows(active_db, parsed_target_id, metrics)


def handle_nut_event(app, data):
    """Handle NUT events received through the Unix socket bridge."""
    try:
        logger.info(f"Processing NUT event: {data}")
        
        if not data:
            logger.error("No data received")
            return False
            
        ups = data.get('ups', 'unknown')
        event = normalize_event_type(data.get('event', 'unknown'))
        parsed_target_id = safe_positive_int(data.get('target_id'))
        source_ip = data.get('source_ip')
        
        now_utc = utc_now()
        
        active_db = _resolve_active_db()
        is_db_ready = _is_sqlalchemy_ready(active_db)

        model_ready = _init_models_if_needed(active_db=active_db)

        if parsed_target_id is None and is_db_ready and model_ready:
            try:
                parsed_target_id = resolve_target_id_from_payload(active_db, data, fallback_db=db)
            except Exception as resolve_exc:
                logger.debug(f"Could not resolve target_id from event payload: {resolve_exc}")

        if parsed_target_id is not None:
            data['target_id'] = parsed_target_id
        data['event'] = event
        event_scope_target_id = resolve_settings_target_id(parsed_target_id)

        if is_db_ready and model_ready:
            with data_lock:
                duplicate_event = find_recent_duplicate_event(
                    session=active_db.session,
                    event_model=UPSEvent,
                    event_type=event,
                    target_id=event_scope_target_id,
                    reference_time=now_utc,
                )
                if duplicate_event:
                    logger.info(
                        "Suppressed duplicate UPS event id=%s target_id=%s event=%s",
                        getattr(duplicate_event, 'id', 'unknown'),
                        event_scope_target_id,
                        event,
                    )
                    return True
                db_event = UPSEvent(
                    ups_name=ups,
                    event_type=event,
                    event_message=str(data),
                    timestamp_utc=now_utc,
                    timestamp_utc_begin=now_utc,
                    source_ip=source_ip,
                    acknowledged=False
                )
                if hasattr(db_event, 'target_id'):
                    db_event.target_id = event_scope_target_id
                active_db.session.add(db_event)
                active_db.session.commit()
                logger.info(f"Event saved to database with id: {db_event.id}")
        else:
            logger.warning("Skipping UPS event DB write because SQLAlchemy is not ready")
        
        if not hasattr(app, 'events_log'):
            app.events_log = []
        app.events_log.append(data)
        
        if hasattr(app, 'socketio'):
            app.socketio.emit('nut_event', data)
            logger.debug("Event sent via WebSocket")
        
        resolved_metrics = _resolve_notification_metrics(
            payload=data,
            parsed_target_id=parsed_target_id,
            active_db=active_db,
            is_db_ready=is_db_ready,
        )

        notification_dispatched = False
        dispatch_target_id = event_scope_target_id if event_scope_target_id is not None else parsed_target_id

        # Use the real target for provider dispatch even when single profile stores settings globally.
        if dispatch_target_id is not None:
            try:
                from ..multi_nut.notifications import dispatch_target_event_notifications
                from ..multi_nut.storage import get_target_with_policy

                target, policy = get_target_with_policy(dispatch_target_id)
                if target and policy:
                    dispatch_result = dispatch_target_event_notifications(
                        target=target,
                        policy=policy,
                        event_type=event,
                        metrics=resolved_metrics,
                        reason=str(data.get('message') or data.get('error') or ''),
                    )
                    logger.info(
                        "Provider notification dispatch target_id=%s settings_scope=%s event=%s scope=%s success=%s",
                        dispatch_target_id,
                        event_scope_target_id,
                        event,
                        dispatch_result.get('scope'),
                        dispatch_result.get('success'),
                    )
                    notification_dispatched = True
                else:
                    logger.warning(
                        "Could not resolve target/policy for provider notification target_id=%s event=%s",
                        dispatch_target_id,
                        event,
                    )
            except Exception as e:
                logger.error(f"Error dispatching provider notifications: {str(e)}", exc_info=True)

        # Legacy fallback remains allowed whenever target-scoped dispatch did not run.
        if not notification_dispatched:
            try:
                from ..mail import handle_notification

                handle_notification(data)
                logger.info(
                    "Legacy notification handler executed (target_id=%s, event=%s)",
                    event_scope_target_id,
                    event,
                )
            except Exception as e:
                logger.error(f"Error sending legacy notification: {str(e)}")

        try:
            from ..scripts.script_actions import maybe_execute_script_actions

            maybe_execute_script_actions(
                active_db=active_db,
                event_type=event,
                metrics=resolved_metrics,
                payload=data,
                target_id=event_scope_target_id,
            )
        except Exception as script_exc:
            logger.error(f"Error executing script actions: {script_exc}", exc_info=True)
        
        if event == 'ONLINE' and is_db_ready and model_ready:
            _init_models_if_needed(active_db=active_db)
            
            with data_lock:
                prev_event_query = active_db.session.query(UPSEvent).filter(
                    UPSEvent.event_type == 'ONBATT',
                    UPSEvent.timestamp_utc_end.is_(None),
                )
                if hasattr(UPSEvent, 'target_id'):
                    if event_scope_target_id is not None:
                        prev_event_query = prev_event_query.filter(UPSEvent.target_id == event_scope_target_id)
                    else:
                        prev_event_query = prev_event_query.filter(UPSEvent.target_id.is_(None))
                prev_event = prev_event_query.order_by(UPSEvent.timestamp_utc.desc()).first()
                
                if prev_event:
                    prev_event.timestamp_utc_end = now_utc
                    active_db.session.commit()
                    logger.debug("Closed previous ONBATT event")
        
        return True
    except Exception as e:
        logger.error(f"Error handling NUT event: {str(e)}", exc_info=True)
        return False

def get_event_history(app):
    """Return the in-memory event history payload."""
    try:
        if not hasattr(app, 'events_log'):
            app.events_log = []
        return jsonify(app.events_log)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def get_events_table(rows='all', target_id=None):
    """Return UPS events from the database for the selected target scope."""
    try:
        logger.debug(f"Request for events table with rows={rows}")
        
        active_db = _resolve_active_db()
        if not _is_sqlalchemy_ready(active_db):
            logger.warning("Events table requested while SQLAlchemy is not ready; returning empty payload")
            return {'columns': [], 'rows': []}

        if not _init_models_if_needed(active_db=active_db):
            logger.warning("UPSEvent model unavailable; returning empty events payload")
            return {'columns': [], 'rows': []}
        
        query = active_db.session.query(UPSEvent)
        if hasattr(UPSEvent, 'target_id'):
            try:
                parsed_target_id = int(target_id) if target_id is not None else None
                if parsed_target_id and parsed_target_id > 0:
                    query = query.filter(UPSEvent.target_id == parsed_target_id)
                else:
                    query = query.filter(UPSEvent.target_id.is_(None))
            except (TypeError, ValueError):
                query = query.filter(UPSEvent.target_id.is_(None))

        query = query.order_by(UPSEvent.timestamp_utc.desc())
        
        if rows != 'all':
            query = query.limit(int(rows))
            
        try:
            events = query.all()
        except RuntimeError as exc:
            if "not registered with this 'SQLAlchemy' instance" in str(exc):
                logger.warning("Refreshing UPSEvent model after SQLAlchemy binding mismatch")
                if _init_models_if_needed(active_db=active_db, force_reload=True):
                    retry_query = active_db.session.query(UPSEvent)
                    if hasattr(UPSEvent, 'target_id'):
                        try:
                            parsed_target_id = int(target_id) if target_id is not None else None
                            if parsed_target_id and parsed_target_id > 0:
                                retry_query = retry_query.filter(UPSEvent.target_id == parsed_target_id)
                            else:
                                retry_query = retry_query.filter(UPSEvent.target_id.is_(None))
                        except (TypeError, ValueError):
                            retry_query = retry_query.filter(UPSEvent.target_id.is_(None))
                    retry_query = retry_query.order_by(UPSEvent.timestamp_utc.desc())
                    if rows != 'all':
                        retry_query = retry_query.limit(int(rows))
                    try:
                        events = retry_query.all()
                    except RuntimeError as retry_exc:
                        if "not registered with this 'SQLAlchemy' instance" in str(retry_exc):
                            logger.warning("UPSEvent retry query still has SQLAlchemy binding mismatch; returning empty payload")
                            return {'columns': [], 'rows': []}
                        raise
                else:
                    return {'columns': [], 'rows': []}
            else:
                raise
        logger.debug(f"Found {len(events)} events")
        
        columns = [column.name for column in UPSEvent.__table__.columns]

        rows_data = []
        for event in events:
            if hasattr(event, 'to_dict'):
                event_dict = event.to_dict()
                for ts_field in ['timestamp_utc', 'timestamp_utc_begin', 'timestamp_utc_end']:
                    if hasattr(event, ts_field) and getattr(event, ts_field):
                        event_dict[ts_field] = serialize_utc_timestamp(getattr(event, ts_field))
                rows_data.append(event_dict)
            else:
                row = {}
                for column in columns:
                    value = getattr(event, column)
                    if isinstance(value, datetime):
                        value = serialize_utc_timestamp(value)
                    row[column] = value
                rows_data.append(row)
        return {
            'columns': columns,
            'rows': rows_data
        }
    except Exception as e:
        logger.error(f"Error retrieving events: {str(e)}", exc_info=True)
        return {'columns': [], 'rows': []}

def acknowledge_event(event_id, target_id=None):
    """Mark a UPS event as acknowledged."""
    try:
        active_db = _resolve_active_db()
        if not _is_sqlalchemy_ready(active_db):
            return False, "Database is not ready"

        if not _init_models_if_needed(active_db=active_db):
            return False, "Event model is not available"
        
        with data_lock:
            event_query = active_db.session.query(UPSEvent).filter(UPSEvent.id == event_id)
            if hasattr(UPSEvent, 'target_id'):
                try:
                    parsed_target_id = int(target_id) if target_id is not None else None
                    if parsed_target_id and parsed_target_id > 0:
                        event_query = event_query.filter(UPSEvent.target_id == parsed_target_id)
                    else:
                        event_query = event_query.filter(UPSEvent.target_id.is_(None))
                except (TypeError, ValueError):
                    event_query = event_query.filter(UPSEvent.target_id.is_(None))
            event = event_query.first()
            if event:
                event.acknowledged = True
                active_db.session.commit()
                return True, "Event acknowledged"
            return False, "Event not found"
    except Exception as e:
        logger.error(f"Error in handling the acknowledge: {str(e)}", exc_info=True)
        return False, str(e) 
