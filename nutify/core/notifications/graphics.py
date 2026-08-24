"""Raster notification card renderer shared by all providers."""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .support_links import BUYMEACOFFEE_URL, GITHUB_URL

def _safe_float(value: Any):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_percent(value: Any) -> str:
    parsed = _safe_float(value)
    return f"{parsed:.1f}%" if parsed is not None else "N/A"


def _format_watts(value: Any) -> str:
    parsed = _safe_float(value)
    return f"{parsed:.1f}W" if parsed is not None else "N/A"


def _format_voltage(value: Any) -> str:
    parsed = _safe_float(value)
    return f"{parsed:.1f}V" if parsed is not None else "N/A"


def _format_runtime_minutes(value: Any) -> str:
    parsed = _safe_float(value)
    return f"{max(0, int(parsed / 60))} min" if parsed is not None else "N/A"


def _format_input_output_metrics(input_value: Any, output_value: Any) -> List[Tuple[str, str]]:
    input_text = _format_voltage(input_value)
    output_text = _format_voltage(output_value)
    return [
        ("Input", input_text),
        ("Output", output_text),
    ]


def _format_battery_voltage_temp_metric(voltage_value: Any, temp_value: Any) -> Tuple[str, str]:
    voltage_text = _format_voltage(voltage_value)
    temp = _safe_float(temp_value)
    temp_text = f"{temp:.1f}C" if temp is not None else "N/A"
    if voltage_text != "N/A" and temp_text != "N/A":
        return ("Battery Voltage / Temp", f"{voltage_text} / {temp_text}")
    if voltage_text != "N/A":
        return ("Battery Voltage", voltage_text)
    if temp_text != "N/A":
        return ("Battery Temp", temp_text)
    return ("Battery Voltage / Temp", "N/A")


def _severity_colors(severity: str) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    severity_key = str(severity or "info").lower()
    palette = {
        "success": ((22, 163, 74), (74, 222, 128)),
        "warning": ((217, 119, 6), (251, 191, 36)),
        "critical": ((185, 28, 28), (248, 113, 113)),
        "info": ((8, 145, 178), (56, 189, 248)),
    }
    return palette.get(severity_key, palette["info"])


def _font_candidates(bold: bool) -> List[str]:
    if bold:
        return [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Helvetica.ttc",
        ]
    return [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
    ]


def _load_font(image_font, size: int, bold: bool = False):
    for path in _font_candidates(bold):
        try:
            return image_font.truetype(path, size=size)
        except Exception:
            continue
    return image_font.load_default()


def _line_wrap(draw, text: str, font, max_width: int) -> List[str]:
    raw_text = str(text or "").strip()
    if not raw_text:
        return []

    lines: List[str] = []
    for paragraph in raw_text.splitlines():
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            width = draw.textbbox((0, 0), candidate, font=font)[2]
            if width <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _metric_rows(card: Dict[str, Any]) -> List[Tuple[str, str]]:
    metrics = card.get("metrics") or {}
    battery_label, battery_text = _format_battery_voltage_temp_metric(
        metrics.get("batteryVoltage"),
        metrics.get("temperatureC"),
    )
    return [
        ("Battery", _format_percent(metrics.get("batteryPercent"))),
        ("Runtime", _format_runtime_minutes(metrics.get("runtimeSeconds"))),
        ("Load", _format_percent(metrics.get("loadPercent"))),
        ("Real Power", _format_watts(metrics.get("realPowerWatts"))),
        *_format_input_output_metrics(metrics.get("inputVoltage"), metrics.get("outputVoltage")),
        (battery_label, battery_text),
    ]


@lru_cache(maxsize=1)
def _load_logo_bytes() -> bytes:
    base_dir = Path(__file__).resolve().parents[2]
    candidates = [
        base_dir / "frontend" / "app" / "public" / "Nutify-Logo.png",
        base_dir / "frontend" / "app" / "dist" / "Nutify-Logo.png",
    ]
    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate.read_bytes()
        except Exception:
            continue
    return b""


def _safe_target_id(card: Dict[str, Any]) -> int | None:
    context = card.get("context") or {}
    try:
        return int(context.get("targetId"))
    except (TypeError, ValueError):
        return None


def _downsample(values: List[float], target_points: int = 60) -> List[float]:
    if len(values) <= target_points:
        return values
    if target_points <= 1:
        return [values[-1]]
    step = (len(values) - 1) / float(target_points - 1)
    return [values[round(i * step)] for i in range(target_points)]


def _extract_recent_trends(card: Dict[str, Any]) -> Dict[str, List[float]]:
    target_id = _safe_target_id(card)
    if target_id is None:
        return {}

    try:
        from app import db
    except Exception:
        return {}

    model_classes = getattr(db, "ModelClasses", None)
    monitor_model = getattr(model_classes, "UPSMonitorData", None) if model_classes else None
    if monitor_model is None:
        return {}

    try:
        rows = (
            db.session.query(monitor_model)
            .filter(monitor_model.target_id == target_id)
            .order_by(monitor_model.timestamp_utc.desc())
            .limit(900)
            .all()
        )
    except Exception:
        return {}

    if not rows:
        return {}

    rows = list(reversed(rows))
    last_ts = getattr(rows[-1], "timestamp_utc", None)
    if last_ts is not None:
        window_start = last_ts - timedelta(minutes=10)
        window_rows = [
            row for row in rows
            if getattr(row, "timestamp_utc", None) is not None and getattr(row, "timestamp_utc") >= window_start
        ]
        if len(window_rows) >= 8:
            rows = window_rows

    power_values: List[float] = []
    voltage_values: List[float] = []
    battery_values: List[float] = []
    energy_values: List[float] = []

    cumulative_wh = 0.0
    previous_ts = None
    for row in rows:
        power = _safe_float(getattr(row, "ups_realpower", None))
        if power is None:
            power = _safe_float(getattr(row, "ups_power", None))
        power = max(0.0, power or 0.0)

        in_voltage = _safe_float(getattr(row, "input_voltage", None))
        out_voltage = _safe_float(getattr(row, "output_voltage", None))
        voltage = out_voltage if out_voltage is not None else (in_voltage if in_voltage is not None else 0.0)

        battery = _safe_float(getattr(row, "battery_charge", None))
        battery = max(0.0, battery or 0.0)

        current_ts = getattr(row, "timestamp_utc", None)
        delta_hours = 1.0 / 3600.0
        if current_ts is not None and previous_ts is not None:
            try:
                delta_sec = max(1.0, float((current_ts - previous_ts).total_seconds()))
            except Exception:
                delta_sec = 1.0
            delta_hours = delta_sec / 3600.0
        cumulative_wh += power * delta_hours
        previous_ts = current_ts

        power_values.append(power)
        voltage_values.append(voltage)
        battery_values.append(battery)
        energy_values.append(cumulative_wh)

    return {
        "power": _downsample(power_values, 72),
        "voltage": _downsample(voltage_values, 72),
        "energy": _downsample(energy_values, 72),
        "battery": _downsample(battery_values, 72),
    }


def _draw_sparkline(draw, bounds, values: List[float], label: str, line_color, font) -> None:
    x1, y1, x2, y2 = bounds
    draw.rounded_rectangle((x1, y1, x2, y2), radius=10, fill=(12, 18, 34), outline=(47, 64, 89), width=1)
    draw.text((x1 + 10, y1 + 8), label, fill=(161, 180, 206), font=font)

    if not values or len(values) < 2:
        draw.text((x1 + 10, y1 + 34), "No data", fill=(113, 128, 150), font=font)
        return

    plot_x1 = x1 + 10
    plot_x2 = x2 - 10
    plot_y1 = y1 + 30
    plot_y2 = y2 - 10
    min_v = min(values)
    max_v = max(values)
    span = max(max_v - min_v, 1e-6)

    points = []
    count = len(values)
    for idx, value in enumerate(values):
        ratio_x = idx / float(max(count - 1, 1))
        ratio_y = (value - min_v) / span
        px = plot_x1 + int((plot_x2 - plot_x1) * ratio_x)
        py = plot_y2 - int((plot_y2 - plot_y1) * ratio_y)
        points.append((px, py))

    draw.line(points, fill=line_color, width=3)


def render_notification_card_png(card: Dict[str, Any], width: int = 1200, height: int = 920) -> bytes:
    """Render a canonical notification card to PNG bytes."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:
        raise RuntimeError("Pillow is required for graphic notification rendering") from exc

    canvas_width = max(780, min(int(width or 1200), 2200))
    canvas_height = max(720, min(int(height or 920), 1800))
    image = Image.new("RGB", (canvas_width, canvas_height), (9, 14, 29))
    draw = ImageDraw.Draw(image)

    accent_dark, accent_light = _severity_colors(str(card.get("severity") or "info"))
    header_height = int(canvas_height * 0.26)
    panel_margin = 28
    card_left = panel_margin
    card_top = panel_margin
    card_right = canvas_width - panel_margin
    card_bottom = canvas_height - panel_margin

    draw.rounded_rectangle(
        (card_left, card_top, card_right, card_bottom),
        radius=20,
        fill=(15, 23, 42),
        outline=(51, 65, 85),
        width=2,
    )
    draw.rounded_rectangle(
        (card_left, card_top, card_right, card_top + header_height),
        radius=20,
        fill=accent_dark,
    )
    draw.rectangle(
        (card_left, card_top + int(header_height * 0.55), card_right, card_top + header_height),
        fill=accent_light,
    )
    draw.rectangle(
        (card_left + 1, card_top + int(header_height * 0.55), card_right - 1, card_top + header_height),
        fill=accent_dark,
    )
    draw.rectangle((card_left, card_top, card_left + 10, card_bottom), fill=accent_light)

    title_font = _load_font(ImageFont, 52, bold=True)
    subtitle_font = _load_font(ImageFont, 28, bold=False)
    body_bold_font = _load_font(ImageFont, 34, bold=True)
    small_font = _load_font(ImageFont, 26, bold=False)
    metrics_key_font = _load_font(ImageFont, 28, bold=False)
    metrics_val_font = _load_font(ImageFont, 30, bold=True)

    content_x = card_left + 36
    title_y = card_top + 34
    title_text = str(card.get("title") or "UPS EVENT")
    subtitle_text = str(card.get("subtitle") or "").strip()
    message_text = str(card.get("message") or "").strip()
    status = card.get("status") or {}
    context = card.get("context") or {}

    draw.text((content_x, title_y), title_text, fill=(248, 250, 252), font=title_font)
    if subtitle_text:
        draw.text((content_x, title_y + 64), subtitle_text, fill=(226, 232, 240), font=subtitle_font)

    status_label = str(status.get("label") or "Status")
    status_value = str(status.get("value") or "UNKNOWN")
    header_meta = f"{status_label}: {status_value}"
    if context.get("targetName"):
        header_meta = f"{header_meta}   |   Target: {context.get('targetName')}"
    draw.text((content_x, card_top + header_height - 52), header_meta, fill=(226, 232, 240), font=small_font)

    logo_bytes = _load_logo_bytes()
    if logo_bytes:
        try:
            with Image.open(BytesIO(logo_bytes)) as logo_image:
                logo = logo_image.convert("RGBA")
                logo_size = int(header_height * 0.58)
                logo.thumbnail((logo_size, logo_size))
                logo_x = card_right - logo.width - 36
                logo_y = card_top + 24
                image.paste(logo, (logo_x, logo_y), logo)
        except Exception:
            pass

    body_top = card_top + header_height + 20
    left_col_x = content_x
    right_col_x = int(canvas_width * 0.56)
    body_width = right_col_x - left_col_x - 24
    details = [str(item).strip() for item in (card.get("details") or []) if str(item).strip()]

    if message_text:
        for idx, line in enumerate(_line_wrap(draw, message_text, body_bold_font, body_width)):
            draw.text((left_col_x, body_top + idx * 40), line, fill=(241, 245, 249), font=body_bold_font)

    context_y = body_top + 88
    context_lines = [
        f"Server: {context.get('serverName') or 'Unknown'}",
        f"Target: {context.get('targetName') or 'Unknown'} ({context.get('targetLabel') or 'Unknown'})",
        f"Time: {context.get('eventTimestamp') or 'Unknown'}",
    ]
    reason_text = str(context.get("reason") or "").strip()
    if reason_text:
        context_lines.append(f"Reason: {reason_text}")
    for idx, line in enumerate(context_lines):
        draw.text((left_col_x, context_y + idx * 34), line, fill=(203, 213, 225), font=small_font)

    details_top = context_y + (len(context_lines) * 34) + 20
    draw.text((left_col_x, details_top), "Details", fill=(248, 250, 252), font=body_bold_font)
    bullet_y = details_top + 42
    if details:
        for detail in details[:5]:
            wrapped = _line_wrap(draw, f"- {detail}", small_font, body_width)
            for line in wrapped:
                draw.text((left_col_x, bullet_y), line, fill=(226, 232, 240), font=small_font)
                bullet_y += 30
    else:
        draw.text((left_col_x, bullet_y), "- No additional details.", fill=(226, 232, 240), font=small_font)

    trends = _extract_recent_trends(card)
    if trends:
        chart_title_y = max(bullet_y + 8, card_bottom - 210)
        draw.text((left_col_x, chart_title_y), "Last 10 Minutes Trends", fill=(156, 203, 255), font=small_font)

        chart_top = chart_title_y + 34
        chart_width = int((body_width - 10) / 2)
        chart_height = 76
        gap_x = 10
        gap_y = 8

        charts = [
            ("Power", trends.get("power") or [], (52, 211, 153)),
            ("Voltage", trends.get("voltage") or [], (59, 130, 246)),
            ("Energy", trends.get("energy") or [], (251, 191, 36)),
            ("Battery", trends.get("battery") or [], (134, 239, 172)),
        ]
        for idx, (label, values, color) in enumerate(charts):
            row = idx // 2
            col = idx % 2
            x1 = left_col_x + col * (chart_width + gap_x)
            y1 = chart_top + row * (chart_height + gap_y)
            x2 = x1 + chart_width
            y2 = y1 + chart_height
            _draw_sparkline(draw, (x1, y1, x2, y2), values, label, color, small_font)

    metrics_rows = _metric_rows(card)
    metrics_panel = (
        right_col_x,
        body_top - 8,
        card_right - 28,
        card_bottom - 82,
    )
    draw.rounded_rectangle(
        metrics_panel,
        radius=14,
        fill=(17, 24, 39),
        outline=(71, 85, 105),
        width=2,
    )
    draw.text((right_col_x + 18, body_top + 10), "Metrics", fill=(248, 250, 252), font=body_bold_font)

    row_y = body_top + 62
    for key, value in metrics_rows:
        draw.text((right_col_x + 18, row_y), key, fill=(148, 163, 184), font=metrics_key_font)
        draw.text((right_col_x + 300, row_y), str(value), fill=(241, 245, 249), font=metrics_val_font)
        row_y += 52

    footer_font = _load_font(ImageFont, 15, bold=False)
    footer_x = right_col_x + 18
    footer_y = metrics_panel[3] + 12
    draw.text((footer_x, footer_y), f"GitHub: {GITHUB_URL}", fill=(132, 168, 214), font=footer_font)
    draw.text((footer_x, footer_y + 18), f"Buy me a coffee: {BUYMEACOFFEE_URL}", fill=(182, 156, 86), font=footer_font)

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def render_notification_trend_strip_png(card: Dict[str, Any], width: int = 900, height: int = 240) -> bytes:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:
        raise RuntimeError("Pillow is required for trend strip rendering") from exc

    trends = _extract_recent_trends(card)
    if not trends:
        return b""

    canvas_width = max(560, min(int(width or 900), 1600))
    canvas_height = max(180, min(int(height or 240), 600))
    image = Image.new("RGB", (canvas_width, canvas_height), (11, 18, 34))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, canvas_width - 1, canvas_height - 1), radius=14, fill=(11, 18, 34), outline=(47, 64, 89), width=1)

    label_font = _load_font(ImageFont, 18, bold=False)
    chart_width = int((canvas_width - 24 - 8) / 2)
    chart_height = int((canvas_height - 24 - 8) / 2)
    charts = [
        ("Power", trends.get("power") or [], (52, 211, 153)),
        ("Voltage", trends.get("voltage") or [], (59, 130, 246)),
        ("Energy", trends.get("energy") or [], (251, 191, 36)),
        ("Battery", trends.get("battery") or [], (134, 239, 172)),
    ]
    for idx, (label, values, color) in enumerate(charts):
        row = idx // 2
        col = idx % 2
        x1 = 12 + col * (chart_width + 8)
        y1 = 12 + row * (chart_height + 8)
        x2 = x1 + chart_width
        y2 = y1 + chart_height
        _draw_sparkline(draw, (x1, y1, x2, y2), values, label, color, label_font)

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
