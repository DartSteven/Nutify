"""Runtime helpers for configurable UPS script actions."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

from flask import current_app

from core.logger import system_logger as logger
from core.multi_nut.target_scope import apply_target_scope, resolve_settings_target_id

from .executor import run_shell_script


ALLOWED_EVENTS = {'ONBATT', 'LOWBATT'}
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='nutify-script')
_evaluation_lock = Lock()


def _safe_int(value, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(fallback)


def _battery_charge_value(metrics: Optional[dict], payload: Optional[dict]) -> Optional[float]:
    candidates = []
    for source in (metrics, payload):
        if isinstance(source, dict):
            candidates.extend((source.get('battery_charge'), source.get('battery.charge')))
    for value in candidates:
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _status_tokens(metrics: Optional[dict], payload: Optional[dict]) -> set[str]:
    values = []
    for source in (metrics, payload):
        if isinstance(source, dict):
            values.extend((source.get('ups_status'), source.get('ups.status'), source.get('status')))
    for value in values:
        text = str(value or '').strip().upper()
        if text:
            return set(text.replace(',', ' ').split())
    return set()


def _condition_matches(trigger_event: str, event_type: str, status_tokens: set[str]) -> bool:
    if trigger_event == 'ONBATT':
        return event_type == 'ONBATT' or bool({'OB', 'ONBATT'} & status_tokens)
    if trigger_event == 'LOWBATT':
        return event_type == 'LOWBATT' or bool({'LB', 'LOWBATT'} & status_tokens)
    return False


def _normalize_last_run(value) -> Optional[datetime]:
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _complete_action(app, active_db, action_id: int, script_body: str) -> None:
    result = run_shell_script(script_body, timeout_seconds=30)
    with app.app_context():
        model_space = getattr(active_db, 'ModelClasses', None)
        model = getattr(model_space, 'ScriptAction', None) if model_space is not None else None
        row = model.query.filter(model.id == int(action_id)).first() if model is not None else None
        if row is None:
            return
        row.last_exit_code = result.exit_code
        row.last_output = result.output
        active_db.session.add(row)
        active_db.session.commit()
        logger.info("Script action completed id=%s exit_code=%s", action_id, result.exit_code)


def maybe_execute_script_actions(
    active_db,
    event_type: str,
    metrics: Optional[dict],
    payload: Optional[dict] = None,
    target_id: Optional[int] = None,
) -> None:
    """Evaluate target-scoped actions and queue newly active conditions once."""
    model_space = getattr(active_db, 'ModelClasses', None)
    model = getattr(model_space, 'ScriptAction', None) if model_space is not None else None
    if model is None:
        return

    normalized_event = str(event_type or '').strip().upper()
    battery_charge = _battery_charge_value(metrics, payload)
    status_tokens = _status_tokens(metrics, payload)
    scoped_target_id = resolve_settings_target_id(target_id)
    now_utc = datetime.now(timezone.utc)
    app = current_app._get_current_object()

    with _evaluation_lock:
        query = apply_target_scope(model, model.query, scoped_target_id)
        actions = query.filter(model.enabled.is_(True)).order_by(model.id.asc()).all()
        changed = False
        queued = []

        for action in actions:
            trigger = str(getattr(action, 'trigger_event', '') or '').upper()
            threshold = _safe_int(getattr(action, 'battery_threshold', 0), 0)
            condition = (
                trigger in ALLOWED_EVENTS
                and battery_charge is not None
                and battery_charge <= float(threshold)
                and _condition_matches(trigger, normalized_event, status_tokens)
            )

            if not condition:
                if bool(getattr(action, 'condition_active', False)):
                    action.condition_active = False
                    active_db.session.add(action)
                    changed = True
                continue

            if bool(getattr(action, 'condition_active', False)):
                continue

            cooldown = max(0, _safe_int(getattr(action, 'cooldown_seconds', 300), 300))
            last_run = _normalize_last_run(getattr(action, 'last_executed_at', None))
            if last_run is not None and (now_utc - last_run).total_seconds() < cooldown:
                continue

            body = str(getattr(action, 'script_body', '') or '').strip()
            if not body:
                continue

            action.condition_active = True
            action.last_executed_at = now_utc
            action.last_exit_code = None
            action.last_output = 'Queued'
            active_db.session.add(action)
            changed = True
            queued.append((int(action.id), body))
            logger.info(
                "Script action queued id=%s event=%s target_id=%s threshold=%s battery_charge=%s",
                action.id,
                trigger,
                scoped_target_id,
                threshold,
                battery_charge,
            )

        if changed:
            active_db.session.commit()

        for action_id, body in queued:
            _executor.submit(_complete_action, app, active_db, action_id, body)
