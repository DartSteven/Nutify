"""Canonical notification card builder shared by all channels."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional


EVENT_CATALOG: Dict[str, Dict[str, Any]] = {
    'ONLINE': {
        'id': 'ups_online',
        'severity': 'success',
        'title': 'UPS ONLINE',
        'message': 'UPS is online and running normally.',
        'icon': {'name': 'check_circle', 'style': 'glow'},
        'theme': {'accent': 'green', 'background': 'dark_glass'},
        'status_label': 'STATUS',
    },
    'ONBATT': {
        'id': 'ups_on_battery',
        'severity': 'warning',
        'title': 'UPS ON BATTERY',
        'message': 'Running on battery backup.',
        'icon': {'name': 'battery_warning', 'style': 'glow'},
        'theme': {'accent': 'amber', 'background': 'dark_glass'},
        'status_label': 'Backup Mode',
    },
    'LOWBATT': {
        'id': 'ups_low_battery',
        'severity': 'critical',
        'title': 'UPS LOW BATTERY',
        'message': 'Battery level is critically low.',
        'icon': {'name': 'alert_triangle', 'style': 'glow'},
        'theme': {'accent': 'red', 'background': 'dark_glass'},
        'status_label': 'Battery',
    },
    'SHUTDOWN': {
        'id': 'ups_shutdown',
        'severity': 'critical',
        'title': 'UPS SHUTDOWN',
        'message': 'System shutdown sequence has been triggered.',
        'icon': {'name': 'power', 'style': 'glow'},
        'theme': {'accent': 'magenta_red', 'background': 'dark_glass'},
        'status_label': 'Shutdown',
    },
    'COMMOK': {
        'id': 'ups_commok',
        'severity': 'success',
        'title': 'COMMUNICATION RESTORED',
        'message': 'Communication with UPS has been restored.',
        'icon': {'name': 'wifi_ok', 'style': 'glow'},
        'theme': {'accent': 'green', 'background': 'dark_glass'},
        'status_label': 'Communication',
    },
    'COMMBAD': {
        'id': 'ups_commbad',
        'severity': 'critical',
        'title': 'COMMUNICATION LOST',
        'message': 'Communication with UPS has been lost.',
        'icon': {'name': 'wifi_off', 'style': 'glow'},
        'theme': {'accent': 'red', 'background': 'dark_glass'},
        'status_label': 'Communication',
    },
    'REPLBATT': {
        'id': 'ups_replbatt',
        'severity': 'warning',
        'title': 'BATTERY REPLACEMENT NEEDED',
        'message': 'UPS battery requires replacement.',
        'icon': {'name': 'battery_replace', 'style': 'glow'},
        'theme': {'accent': 'amber', 'background': 'dark_glass'},
        'status_label': 'Battery',
    },
    'NOCOMM': {
        'id': 'ups_nocomm',
        'severity': 'critical',
        'title': 'UPS NOT REACHABLE',
        'message': 'UPS is not reachable.',
        'icon': {'name': 'link_off', 'style': 'glow'},
        'theme': {'accent': 'red', 'background': 'dark_glass'},
        'status_label': 'Reachability',
    },
    'NOPARENT': {
        'id': 'ups_noparent',
        'severity': 'warning',
        'title': 'PARENT PROCESS LOST',
        'message': 'Parent monitoring process was lost.',
        'icon': {'name': 'process_alert', 'style': 'glow'},
        'theme': {'accent': 'amber', 'background': 'dark_glass'},
        'status_label': 'Supervisor',
    },
    'UNKNOWN': {
        'id': 'ups_unknown',
        'severity': 'info',
        'title': 'UPS EVENT',
        'message': 'An UPS event has been detected.',
        'icon': {'name': 'info', 'style': 'glow'},
        'theme': {'accent': 'blue', 'background': 'dark_glass'},
        'status_label': 'Status',
    },
}


def normalize_event_code(event_type: Optional[str]) -> str:
    raw = str(event_type or '').strip().upper()
    if not raw:
        return 'UNKNOWN'
    if raw == 'FSD':
        return 'SHUTDOWN'
    return raw


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _severity_status(event_code: str, metrics: Dict[str, Any]) -> str:
    if event_code == 'ONLINE':
        return 'ONLINE'
    if event_code == 'ONBATT':
        return 'ON BATTERY'
    if event_code == 'LOWBATT':
        return 'LOW'
    if event_code == 'SHUTDOWN':
        return 'IN PROGRESS'
    if event_code == 'COMMOK':
        return 'RESTORED'
    if event_code == 'COMMBAD':
        return 'LOST'
    if event_code == 'REPLBATT':
        return 'REPLACE REQUIRED'
    if event_code == 'NOCOMM':
        return 'UNREACHABLE'
    if event_code == 'NOPARENT':
        return 'LOST'
    return str(metrics.get('ups_status') or 'UNKNOWN')


def _event_details(event_code: str, reason: str) -> list[str]:
    if event_code == 'ONLINE':
        return ['Line power restored and UPS is stable.']
    if event_code == 'ONBATT':
        return [
            'Power failure detected.',
            'UPS is supplying backup power.',
            'Review runtime and active load.',
        ]
    if event_code == 'LOWBATT':
        return [
            'Battery level is critically low.',
            'Immediate action is required.',
        ]
    if event_code == 'SHUTDOWN':
        return [
            'Final shutdown sequence detected.',
            'Protected systems should stop safely now.',
        ]
    if event_code == 'COMMOK':
        return ['Communication restored with UPS target.']
    if event_code in {'COMMBAD', 'NOCOMM'}:
        details = ['Communication with UPS target is unavailable.']
        if reason:
            details.append(f"Reason: {reason}")
        return details
    if event_code == 'REPLBATT':
        return ['Battery replacement advisory active.']
    if event_code == 'NOPARENT':
        details = ['Parent process supervision issue detected.']
        if reason:
            details.append(f"Reason: {reason}")
        return details
    return []


def _metrics_payload(metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'batteryPercent': _safe_float(metrics.get('battery_charge')),
        'runtimeSeconds': _safe_float(metrics.get('battery_runtime')),
        'loadPercent': _safe_float(metrics.get('ups_load')),
        'realPowerWatts': _safe_float(metrics.get('ups_realpower')),
        'inputVoltage': _safe_float(metrics.get('input_voltage')),
        'outputVoltage': _safe_float(metrics.get('output_voltage')),
        'batteryVoltage': _safe_float(metrics.get('battery_voltage')),
        'temperatureC': _safe_float(metrics.get('battery_temperature') or metrics.get('ups_temperature')),
    }


def build_notification_card(
    event_type: Optional[str],
    *,
    server_name: str = '',
    target_id: Optional[int] = None,
    target_name: str = '',
    target_label: str = '',
    metrics: Optional[Dict[str, Any]] = None,
    reason: str = '',
    timestamp: Optional[datetime] = None,
    notify_flag: Optional[str] = None,
    countdown_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """Build one canonical event card used by all notification channels."""
    event_code = normalize_event_code(event_type)
    metric_data = dict(metrics or {})
    spec = EVENT_CATALOG.get(event_code, EVENT_CATALOG['UNKNOWN'])
    notify_token = str(notify_flag or event_type or event_code).strip().upper() or event_code
    event_time = timestamp or datetime.utcnow()

    status_value = _severity_status(event_code, metric_data)
    details = _event_details(event_code, reason)
    card_metrics = _metrics_payload(metric_data)
    if event_code == 'LOWBATT' and card_metrics.get('batteryPercent') is not None:
        card_metrics['actionText'] = 'RECHARGE NOW'

    countdown = None
    if event_code == 'SHUTDOWN' and countdown_seconds:
        minutes, seconds = divmod(max(0, int(countdown_seconds)), 60)
        countdown = {
            'label': 'Shutting down in',
            'seconds': int(countdown_seconds),
            'display': f"{minutes:02d}:{seconds:02d}",
        }

    return {
        'id': spec['id'],
        'type': event_code,
        'notifyFlag': notify_token,
        'severity': spec['severity'],
        'title': spec['title'],
        'subtitle': f"NOTIFYFLAG {notify_token} SYSLOG+WALL+EXEC",
        'channels': ['SYSLOG', 'WALL', 'EXEC'],
        'icon': spec['icon'],
        'status': {
            'label': spec.get('status_label', 'Status'),
            'value': status_value,
        },
        'message': spec['message'],
        'details': details,
        'metrics': card_metrics,
        'countdown': countdown,
        'theme': spec['theme'],
        'context': {
            'serverName': str(server_name or ''),
            'targetId': int(target_id) if target_id is not None else None,
            'targetName': str(target_name or ''),
            'targetLabel': str(target_label or ''),
            'eventTimestamp': event_time.isoformat(),
            'reason': str(reason or ''),
            'upsStatus': str(metric_data.get('ups_status') or ''),
        },
    }

