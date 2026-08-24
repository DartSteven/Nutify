"""Channel renderers for canonical notification cards."""

from __future__ import annotations

import base64
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, Optional

from .cards import normalize_event_code
from .support_links import support_footer_html, support_footer_markdown, support_footer_text

VALID_RENDER_MODES = {'graphic', 'text'}
DEFAULT_RENDER_MODE = 'graphic'
_RENDER_MODE_ALIASES = {
    'graphic': 'graphic',
    'graphic_html': 'graphic',
    'image': 'graphic',
    'png': 'graphic',
    'rich': 'graphic',
    'html': 'graphic',
    'text': 'text',
    'plain': 'text',
    'plain_text': 'text',
}


def normalize_render_mode(value: Any) -> str:
    normalized = str(value or '').strip().lower()
    if normalized in _RENDER_MODE_ALIASES:
        return _RENDER_MODE_ALIASES[normalized]
    return DEFAULT_RENDER_MODE


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_percent(value: Any) -> str:
    parsed = _safe_float(value)
    if parsed is None:
        return 'N/A'
    return f"{parsed:.1f}%"


def _format_watts(value: Any) -> str:
    parsed = _safe_float(value)
    if parsed is None:
        return 'N/A'
    return f"{parsed:.1f}W"


def _format_voltage(value: Any) -> str:
    parsed = _safe_float(value)
    if parsed is None:
        return 'N/A'
    return f"{parsed:.1f}V"


def _format_runtime_minutes(value: Any) -> str:
    parsed = _safe_float(value)
    if parsed is None:
        return 'N/A'
    return f"{max(0, int(parsed / 60))} min"


def _format_input_output_metric(input_value: Any, output_value: Any) -> tuple[str, str]:
    input_text = _format_voltage(input_value)
    output_text = _format_voltage(output_value)
    if input_text != 'N/A' and output_text != 'N/A':
        return ('Input / Output', f'{input_text} / {output_text}')
    if output_text != 'N/A':
        return ('Output', output_text)
    if input_text != 'N/A':
        return ('Input', input_text)
    return ('Input / Output', 'N/A')


def _format_battery_voltage_temp_metric(voltage_value: Any, temp_value: Any) -> tuple[str, str]:
    voltage_text = _format_voltage(voltage_value)
    parsed_temperature = _safe_float(temp_value)
    temp_text = f"{parsed_temperature:.1f}C" if parsed_temperature is not None else 'N/A'
    if voltage_text != 'N/A' and temp_text != 'N/A':
        return ('Battery Voltage / Temp', f'{voltage_text} / {temp_text}')
    if voltage_text != 'N/A':
        return ('Battery Voltage', voltage_text)
    if temp_text != 'N/A':
        return ('Battery Temp', temp_text)
    return ('Battery Voltage / Temp', 'N/A')


def _render_common_lines(card: Dict[str, Any]) -> list[str]:
    context = card.get('context') or {}
    metrics = card.get('metrics') or {}
    status = card.get('status') or {}

    lines = [
        f"{card.get('severity', 'INFO').upper()} | {card.get('title', 'UPS EVENT')}",
        card.get('subtitle', ''),
    ]
    if context.get('serverName'):
        lines.append(f"Server: {context.get('serverName')}")
    if context.get('targetName') or context.get('targetLabel'):
        target_name = context.get('targetName') or 'Unknown'
        target_label = context.get('targetLabel') or 'Unknown'
        lines.append(f"Target: {target_name} ({target_label})")
    if context.get('eventTimestamp'):
        lines.append(f"Time: {context.get('eventTimestamp')}")
    lines.append(f"{status.get('label', 'Status')}: {status.get('value', 'UNKNOWN')}")
    lines.append(f"Battery: {_format_percent(metrics.get('batteryPercent'))}")
    lines.append(f"Runtime: {_format_runtime_minutes(metrics.get('runtimeSeconds'))}")
    lines.append(f"Load: {_format_percent(metrics.get('loadPercent'))}")
    lines.append(f"Real Power: {_format_watts(metrics.get('realPowerWatts'))}")
    io_label, io_text = _format_input_output_metric(metrics.get('inputVoltage'), metrics.get('outputVoltage'))
    battery_label, battery_text = _format_battery_voltage_temp_metric(
        metrics.get('batteryVoltage'),
        metrics.get('temperatureC'),
    )
    lines.append(f"{io_label}: {io_text}")
    lines.append(f"{battery_label}: {battery_text}")
    reason = context.get('reason')
    if reason:
        lines.append(f"Reason: {reason}")
    for detail in card.get('details') or []:
        lines.append(f"- {detail}")
    lines.append("")
    lines.append(support_footer_text())
    return lines


def _clean_line(value: Any) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split()).strip()


def _mail_logo_data_uri() -> str:
    base_dir = Path(__file__).resolve().parents[2]
    candidates = [
        base_dir / 'frontend' / 'app' / 'public' / 'Nutify-Logo.png',
        base_dir / 'frontend' / 'app' / 'dist' / 'Nutify-Logo.png',
    ]
    for candidate in candidates:
        try:
            if candidate.exists():
                encoded = base64.b64encode(candidate.read_bytes()).decode('ascii')
                return f"data:image/png;base64,{encoded}"
        except Exception:
            continue
    return ""


def _mail_trends_data_uri(card: Dict[str, Any]) -> str:
    try:
        from .graphics import render_notification_trend_strip_png
        image_bytes = render_notification_trend_strip_png(card, width=900, height=240)
    except Exception:
        return ""
    if not image_bytes:
        return ""
    encoded = base64.b64encode(image_bytes).decode('ascii')
    return f"data:image/png;base64,{encoded}"


def _render_ntfy_markdown_from_card(card: Dict[str, Any]) -> str:
    context = card.get('context') or {}
    status = card.get('status') or {}
    metrics = card.get('metrics') or {}
    details = [str(item).strip() for item in (card.get('details') or []) if str(item).strip()]
    severity = str(card.get('severity') or 'info').lower()
    severity_badge = {
        'success': '🟢',
        'warning': '🟠',
        'critical': '🔴',
        'info': '🔵',
    }.get(severity, '🔵')

    title = _clean_line(card.get('title') or 'UPS EVENT')
    subtitle = _clean_line(card.get('subtitle') or '')
    message = _clean_line(card.get('message') or '')
    status_label = _clean_line(status.get('label') or 'Status')
    status_value = _clean_line(status.get('value') or 'UNKNOWN')

    lines = [f"{severity_badge} **{title}**"]
    if subtitle:
        lines.append(f"`{subtitle}`")
    if message:
        lines.append(message)

    target_name = _clean_line(context.get('targetName') or 'Unknown')
    target_label = _clean_line(context.get('targetLabel') or 'Unknown')
    server_name = _clean_line(context.get('serverName') or 'Unknown')
    event_time = _clean_line(context.get('eventTimestamp') or 'Unknown')
    lines.append(
        f"`{status_label}: {status_value}` • `{server_name}` • `{target_name}` (`{target_label}`)"
    )
    lines.append(f"`{event_time}`")

    io_label, io_text = _format_input_output_metric(metrics.get('inputVoltage'), metrics.get('outputVoltage'))
    metric_summary = (
        f"🔋 `{_format_percent(metrics.get('batteryPercent'))}`  "
        f"⏱ `{_format_runtime_minutes(metrics.get('runtimeSeconds'))}`  "
        f"⚡ `{_format_watts(metrics.get('realPowerWatts'))}`  "
        f"🔌 `{io_label}: {io_text}`"
    )
    lines.append(metric_summary)

    if details:
        lines.append(f"- {_clean_line(details[0])}")
    lines.append("")
    lines.append(support_footer_markdown())

    return "\n".join(lines).strip()


def _render_telegram_html_from_card(card: Dict[str, Any]) -> str:
    context = card.get('context') or {}
    metrics = card.get('metrics') or {}
    status = card.get('status') or {}
    details = [str(item).strip() for item in (card.get('details') or []) if str(item).strip()]
    severity = str(card.get('severity') or 'info').lower()
    severity_badge = {
        'success': '🟢 OK',
        'warning': '🟠 WARN',
        'critical': '🔴 CRIT',
        'info': '🔵 INFO',
    }.get(severity, '🔵 INFO')

    lines = [
        f"<b>{escape(severity_badge)} | {escape(str(card.get('title') or 'UPS EVENT'))}</b>",
        f"<code>{escape(str(card.get('subtitle') or '').strip())}</code>",
        '',
        escape(str(card.get('message') or '').strip()),
        '',
        f"<b>{escape(str(status.get('label') or 'Status'))}:</b> {escape(str(status.get('value') or 'UNKNOWN'))}",
    ]

    if context.get('serverName'):
        lines.append(f"<b>Server:</b> {escape(str(context.get('serverName')))}")
    if context.get('targetName') or context.get('targetLabel'):
        target_name = escape(str(context.get('targetName') or 'Unknown'))
        target_label = escape(str(context.get('targetLabel') or 'Unknown'))
        lines.append(f"<b>Target:</b> {target_name} ({target_label})")
    if context.get('eventTimestamp'):
        lines.append(f"<b>Time:</b> {escape(str(context.get('eventTimestamp')))}")

    io_label, io_text = _format_input_output_metric(metrics.get('inputVoltage'), metrics.get('outputVoltage'))
    battery_label, battery_text = _format_battery_voltage_temp_metric(
        metrics.get('batteryVoltage'),
        metrics.get('temperatureC'),
    )
    lines.extend(
        [
            '',
            "<b>Metrics</b>",
            f"• <b>Battery:</b> {escape(_format_percent(metrics.get('batteryPercent')))}",
            f"• <b>Runtime:</b> {escape(_format_runtime_minutes(metrics.get('runtimeSeconds')))}",
            f"• <b>Load:</b> {escape(_format_percent(metrics.get('loadPercent')))}",
            f"• <b>Real Power:</b> {escape(_format_watts(metrics.get('realPowerWatts')))}",
            f"• <b>{escape(io_label)}:</b> {escape(io_text)}",
            f"• <b>{escape(battery_label)}:</b> {escape(battery_text)}",
        ]
    )

    if details:
        lines.append('')
        lines.append('<b>Details</b>')
        lines.extend(f"• {escape(detail)}" for detail in details)
    lines.append('')
    lines.append(
        f"<a href='{escape('https://github.com/DartSteven/Nutify')}'>GitHub</a> • "
        f"<a href='{escape('https://buymeacoffee.com/dartsteven')}'>Buy me a coffee</a>"
    )

    return "\n".join(line for line in lines if line)


def render_ntfy_text_from_card(card: Dict[str, Any], render_mode: str = DEFAULT_RENDER_MODE) -> str:
    mode = normalize_render_mode(render_mode)
    if mode == 'text':
        lines = _render_common_lines(card)
        return "\n".join(line for line in lines if line)
    return _render_ntfy_markdown_from_card(card)


def render_telegram_text_from_card(
    card: Dict[str, Any],
    render_mode: str = DEFAULT_RENDER_MODE,
    parse_mode: str = 'HTML',
) -> str:
    mode = normalize_render_mode(render_mode)
    normalized_parse_mode = str(parse_mode or 'HTML').strip().upper()
    if mode == 'graphic' and normalized_parse_mode == 'HTML':
        return _render_telegram_html_from_card(card)
    lines = _render_common_lines(card)
    return "\n".join(line for line in lines if line)


def render_mail_text_from_card(card: Dict[str, Any]) -> str:
    lines = _render_common_lines(card)
    return "\n".join(line for line in lines if line)


def render_mail_subject_from_card(card: Dict[str, Any], fallback_event_type: str = 'UPS EVENT') -> str:
    context = card.get('context') or {}
    server_name = str(context.get('serverName') or '').strip()
    target_name = str(context.get('targetName') or '').strip()
    event_type = normalize_event_code(card.get('type') or fallback_event_type)

    scope = target_name or server_name
    if scope:
        return f"{scope} UPS Event: {event_type}"
    return f"UPS Event: {event_type}"


def render_mail_html_from_card(card: Dict[str, Any]) -> str:
    context = card.get('context') or {}
    metrics = card.get('metrics') or {}
    status = card.get('status') or {}
    details = card.get('details') or []
    severity = str(card.get('severity') or 'info').lower()

    accent_by_severity = {
        'success': '#22c55e',
        'warning': '#f59e0b',
        'critical': '#ef4444',
        'info': '#38bdf8',
    }
    accent = accent_by_severity.get(severity, '#38bdf8')

    detail_items = ''.join(
        f"<li style='margin:0 0 6px 0'>{escape(str(detail))}</li>"
        for detail in details
        if str(detail).strip()
    ) or "<li style='margin:0'>No additional details.</li>"

    status_label = escape(str(status.get('label') or 'Status'))
    status_value = escape(str(status.get('value') or 'UNKNOWN'))
    server_name = escape(str(context.get('serverName') or 'Unknown'))
    target_name = escape(str(context.get('targetName') or 'Unknown'))
    target_label = escape(str(context.get('targetLabel') or 'Unknown'))
    event_timestamp = escape(str(context.get('eventTimestamp') or 'Unknown'))
    subtitle = escape(str(card.get('subtitle') or ''))
    message = escape(str(card.get('message') or ''))
    title = escape(str(card.get('title') or 'UPS EVENT'))
    logo_data_uri = _mail_logo_data_uri()
    trends_data_uri = _mail_trends_data_uri(card)
    logo_html = (
        "<img src='{src}' alt='Nutify' "
        "style='width:72px;height:72px;object-fit:contain;opacity:.95;border-radius:10px'/>"
    ).format(src=logo_data_uri) if logo_data_uri else ""
    trend_html = (
        "<div style='margin-top:12px'>"
        "<div style='font-size:14px;font-weight:700;margin-bottom:6px;color:#cbd5e1'>Trend Snapshot (10 min)</div>"
        "<img src='{src}' alt='Trend Snapshot' style='width:100%;max-width:900px;border-radius:10px;border:1px solid #1f2937'/>"
        "</div>"
    ).format(src=trends_data_uri) if trends_data_uri else ""

    io_label, io_text = _format_input_output_metric(metrics.get('inputVoltage'), metrics.get('outputVoltage'))
    battery_label, battery_text = _format_battery_voltage_temp_metric(
        metrics.get('batteryVoltage'),
        metrics.get('temperatureC'),
    )
    metrics_rows = [
        ("Battery", _format_percent(metrics.get('batteryPercent'))),
        ("Runtime", _format_runtime_minutes(metrics.get('runtimeSeconds'))),
        ("Load", _format_percent(metrics.get('loadPercent'))),
        ("Real Power", _format_watts(metrics.get('realPowerWatts'))),
        (io_label, io_text),
        (battery_label, battery_text),
    ]

    metrics_html = ''.join(
        "<tr>"
        f"<td style='padding:6px 8px;color:#94a3b8'>{escape(label)}</td>"
        f"<td style='padding:6px 8px;color:#e2e8f0;font-weight:600'>{escape(str(value))}</td>"
        "</tr>"
        for label, value in metrics_rows
    )

    return (
        "<div style='background:#0f172a;padding:18px;border-radius:12px;border:1px solid #1e293b;"
        f"border-left:6px solid {accent};font-family:Arial,sans-serif;color:#e2e8f0'>"
        "<div style='display:flex;justify-content:space-between;align-items:flex-start;gap:12px'>"
        "<div>"
        f"<h2 style='margin:0 0 6px 0;color:{accent};font-size:22px'>{title}</h2>"
        f"<div style='font-size:13px;color:#cbd5e1;margin-bottom:12px'>{subtitle}</div>"
        "</div>"
        f"{logo_html}"
        "</div>"
        f"<div style='margin-bottom:10px;font-size:16px;font-weight:600'>{message}</div>"
        "<div style='background:#111827;border:1px solid #1f2937;border-radius:8px;padding:10px;margin-bottom:12px'>"
        f"<div><strong>{status_label}:</strong> {status_value}</div>"
        f"<div><strong>Server:</strong> {server_name}</div>"
        f"<div><strong>Target:</strong> {target_name} ({target_label})</div>"
        f"<div><strong>Time:</strong> {event_timestamp}</div>"
        "</div>"
        "<table style='width:100%;border-collapse:collapse;background:#0b1220;border:1px solid #1f2937;border-radius:8px;"
        "overflow:hidden;margin-bottom:12px'>"
        f"{metrics_html}"
        "</table>"
        "<div style='background:#111827;border:1px solid #1f2937;border-radius:8px;padding:10px'>"
        "<div style='font-size:14px;font-weight:700;margin-bottom:6px;color:#cbd5e1'>Details</div>"
        f"<ul style='margin:0;padding-left:18px;color:#dbeafe'>{detail_items}</ul>"
        "</div>"
        f"{trend_html}"
        f"{support_footer_html()}"
        "</div>"
    )


def build_mail_template_data_from_card(card: Dict[str, Any]) -> Dict[str, Any]:
    context = card.get('context') or {}
    metrics = card.get('metrics') or {}
    timestamp_value = context.get('eventTimestamp')
    event_dt = datetime.utcnow()
    if isinstance(timestamp_value, str) and timestamp_value:
        try:
            event_dt = datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
        except ValueError:
            event_dt = datetime.utcnow()

    return {
        'target_id': context.get('targetId'),
        'target_name': context.get('targetName') or None,
        'ups_host': context.get('targetLabel') or 'unknown',
        'ups_model': context.get('targetName') or 'Unknown UPS',
        'ups_status': context.get('upsStatus') or (card.get('status') or {}).get('value', 'UNKNOWN'),
        'event_date': event_dt.strftime('%Y-%m-%d'),
        'event_time': event_dt.strftime('%H:%M:%S'),
        'battery_charge': _format_percent(metrics.get('batteryPercent')),
        'runtime_estimate': _format_runtime_minutes(metrics.get('runtimeSeconds')),
        'input_voltage': _format_voltage(metrics.get('inputVoltage')),
        'battery_voltage': _format_voltage(metrics.get('batteryVoltage')),
        'comm_duration': context.get('reason') or 'N/A',
        'server_name': context.get('serverName') or '',
        'notification_card': card,
        'is_test': False,
    }


def build_webhook_event_data_from_card(card: Dict[str, Any], fallback_ups_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    context = card.get('context') or {}
    metrics = card.get('metrics') or {}
    ups_info = dict(fallback_ups_info or {})
    ups_info.setdefault('ups_status', context.get('upsStatus') or (card.get('status') or {}).get('value', 'UNKNOWN'))
    ups_info.setdefault('battery_charge', _format_percent(metrics.get('batteryPercent')).replace('%', ''))
    ups_info.setdefault('input_voltage', _format_voltage(metrics.get('inputVoltage')))
    ups_info.setdefault('ups_model', context.get('targetName') or 'Unknown UPS')
    ups_info.setdefault('device_serial', 'Unknown')

    return {
        'ups_info': ups_info,
        'ups_name': context.get('targetLabel') or context.get('targetName') or 'unknown',
        'server_name': context.get('serverName') or '',
        'notification_card': card,
    }
