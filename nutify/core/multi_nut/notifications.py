"""Notification dispatch helpers for Multi-NUT target events."""

from __future__ import annotations

from datetime import datetime
from threading import Lock
import time
from typing import Any, Dict, Iterable, Optional

import pytz
from flask import current_app, has_app_context

from core.logger import system_logger as logger
from core.notifications import (
    build_mail_template_data_from_card,
    build_notification_card,
    build_webhook_event_data_from_card,
    fill_missing_target_metrics,
    normalize_notification_metrics,
    normalize_event_code,
)

from .storage import normalize_notify_scope


SUPPORTED_CHANNELS = ('mail', 'ntfy', 'telegram', 'webhook')
_DEDUPE_EVENT_TYPES = {'COMMBAD', 'COMMOK'}
_DEDUPE_WINDOW_SECONDS = 5.0
_recent_event_dispatches: Dict[tuple[int, str], float] = {}
_dedupe_lock = Lock()


def _should_suppress_duplicate_dispatch(target_id: int, event_type: str) -> bool:
    """Return True when the same target/event was dispatched very recently."""
    normalized_event = normalize_event_code(event_type)
    if normalized_event not in _DEDUPE_EVENT_TYPES:
        return False

    now_monotonic = time.monotonic()
    key = (int(target_id), normalized_event)

    with _dedupe_lock:
        last_dispatch = _recent_event_dispatches.get(key)
        if last_dispatch is not None and (now_monotonic - last_dispatch) < _DEDUPE_WINDOW_SECONDS:
            return True
        _recent_event_dispatches[key] = now_monotonic

        cutoff = now_monotonic - (_DEDUPE_WINDOW_SECONDS * 10)
        stale_keys = [entry_key for entry_key, ts in _recent_event_dispatches.items() if ts < cutoff]
        for stale_key in stale_keys:
            _recent_event_dispatches.pop(stale_key, None)

    return False


def _target_identifier(target) -> str:
    if int(getattr(target, 'port', 3493) or 3493) == 3493:
        return f"{target.ups_name}@{target.host}"
    return f"{target.ups_name}@{target.host}:{target.port}"


def _channels_from_scope(scope: str) -> Iterable[str]:
    if scope == 'none':
        return ()
    if scope in SUPPORTED_CHANNELS:
        return (scope,)
    return SUPPORTED_CHANNELS


def _local_now() -> datetime:
    tz = getattr(current_app, 'CACHE_TIMEZONE', None) if has_app_context() else None
    if tz is None:
        tz = pytz.UTC
    return datetime.now(tz)


def _resolve_server_name() -> str:
    try:
        from core.settings import get_server_name

        return str(get_server_name() or '').strip()
    except Exception:
        return ''


def _resolve_notification_metrics(target, metrics: Optional[Dict[str, object]]) -> Dict[str, object]:
    try:
        target_id = int(getattr(target, 'id'))
    except (TypeError, ValueError):
        return normalize_notification_metrics(metrics)
    return fill_missing_target_metrics(target_id, metrics)


def _build_unified_card(target, event_type: str, metrics: Optional[Dict[str, object]], reason: str) -> Dict[str, Any]:
    resolved_metrics = _resolve_notification_metrics(target, metrics)
    return build_notification_card(
        event_type,
        server_name=_resolve_server_name(),
        target_id=int(target.id),
        target_name=str(getattr(target, 'name', '') or ''),
        target_label=_target_identifier(target),
        metrics=resolved_metrics,
        reason=str(reason or ''),
        timestamp=_local_now(),
        notify_flag=str(event_type or '').upper() or None,
    )


def dispatch_target_event_notifications(
    target,
    policy,
    event_type: str,
    metrics: Optional[Dict[str, object]] = None,
    reason: str = '',
) -> Dict[str, object]:
    """Send one Multi-NUT target event notification honoring policy notify_scope."""
    unified_card = _build_unified_card(target, event_type, metrics, reason)
    normalized_event = str(unified_card.get('type') or normalize_event_code(event_type))

    if _should_suppress_duplicate_dispatch(int(target.id), normalized_event):
        logger.info(
            "Suppressed duplicate Multi-NUT notification target_id=%s event=%s within %.1fs window",
            target.id,
            normalized_event,
            _DEDUPE_WINDOW_SECONDS,
        )
        return {
            'event_type': normalized_event,
            'scope': normalize_notify_scope(getattr(policy, 'notify_scope', 'global')),
            'channels': [],
            'success': True,
            'results': {'dedupe': {'success': True, 'message': 'duplicate dispatch suppressed'}},
            'notification_card': unified_card,
        }

    scope = normalize_notify_scope(getattr(policy, 'notify_scope', 'global'))
    channels = tuple(_channels_from_scope(scope))
    result = {
        'event_type': normalized_event,
        'scope': scope,
        'channels': list(channels),
        'success': True,
        'results': {},
        'notification_card': unified_card,
    }

    if not channels:
        return result

    if 'mail' in channels:
        try:
            from core.mail.mail import EmailNotifier

            mail_payload = build_mail_template_data_from_card(unified_card)
            success, message = EmailNotifier.send_notification(normalized_event, mail_payload)
            result['results']['mail'] = {'success': bool(success), 'message': str(message)}
            if not success:
                result['success'] = False
        except Exception as exc:
            result['results']['mail'] = {'success': False, 'message': str(exc)}
            result['success'] = False
            logger.warning(f"Multi-NUT mail notification failed for target {target.id}: {exc}")

    if 'ntfy' in channels:
        try:
            from core.extranotifs.ntfy.ntfy import send_event_notification as send_ntfy_event_notification

            ntfy_result = send_ntfy_event_notification(
                normalized_event,
                str(reason or ''),
                target_id=int(target.id),
                notification_card=unified_card,
            )
            success = bool((ntfy_result or {}).get('success'))
            ntfy_payload = dict(ntfy_result or {})
            ntfy_payload.setdefault('success', success)
            ntfy_payload.setdefault('message', '')
            result['results']['ntfy'] = ntfy_payload
            if not success:
                result['success'] = False
        except Exception as exc:
            result['results']['ntfy'] = {'success': False, 'message': str(exc)}
            result['success'] = False
            logger.warning(f"Multi-NUT ntfy notification failed for target {target.id}: {exc}")

    if 'webhook' in channels:
        try:
            from core.extranotifs.webhook.webhook import send_event_notification as send_webhook_event_notification

            webhook_result = send_webhook_event_notification(
                normalized_event,
                _target_identifier(target),
                target_id=int(target.id),
                event_data=build_webhook_event_data_from_card(unified_card),
            )
            success = bool(webhook_result.get('success'))
            result['results']['webhook'] = {
                'success': success,
                'message': webhook_result.get('message', ''),
            }
            if not success:
                result['success'] = False
        except Exception as exc:
            result['results']['webhook'] = {'success': False, 'message': str(exc)}
            result['success'] = False
            logger.warning(f"Multi-NUT webhook notification failed for target {target.id}: {exc}")

    if 'telegram' in channels:
        try:
            from core.extranotifs.telegram.telegram import send_event_notification as send_telegram_event_notification

            telegram_result = send_telegram_event_notification(
                normalized_event,
                str(reason or ''),
                target_id=int(target.id),
                notification_card=unified_card,
            )
            success = bool((telegram_result or {}).get('success'))
            telegram_payload = dict(telegram_result or {})
            telegram_payload.setdefault('success', success)
            telegram_payload.setdefault('message', '')
            result['results']['telegram'] = telegram_payload
            if not success:
                result['success'] = False
        except Exception as exc:
            result['results']['telegram'] = {'success': False, 'message': str(exc)}
            result['success'] = False
            logger.warning(f"Multi-NUT telegram notification failed for target {target.id}: {exc}")

    try:
        compact_results = {
            channel: {
                'success': bool((channel_result or {}).get('success')),
                'message': str((channel_result or {}).get('message') or ''),
                'config_id': (channel_result or {}).get('config_id'),
                'render_mode': (channel_result or {}).get('render_mode'),
                'parse_mode': (channel_result or {}).get('parse_mode'),
            }
            for channel, channel_result in (result.get('results') or {}).items()
        }
        logger.info(
            "Multi-NUT notification trace target_id=%s event=%s scope=%s channels=%s",
            target.id,
            normalized_event,
            scope,
            compact_results,
        )
    except Exception:
        pass

    return result
