"""Unified notification card model and channel renderers."""

from .cards import build_notification_card, normalize_event_code
from .graphics import render_notification_card_png
from .metrics import fill_missing_target_metrics, normalize_notification_metrics
from .renderers import (
    DEFAULT_RENDER_MODE,
    build_mail_template_data_from_card,
    build_webhook_event_data_from_card,
    render_mail_html_from_card,
    render_mail_subject_from_card,
    render_mail_text_from_card,
    render_ntfy_text_from_card,
    render_telegram_text_from_card,
    normalize_render_mode,
)

__all__ = [
    'build_notification_card',
    'normalize_event_code',
    'render_notification_card_png',
    'fill_missing_target_metrics',
    'normalize_notification_metrics',
    'DEFAULT_RENDER_MODE',
    'build_mail_template_data_from_card',
    'build_webhook_event_data_from_card',
    'render_mail_html_from_card',
    'render_mail_subject_from_card',
    'render_mail_text_from_card',
    'render_ntfy_text_from_card',
    'render_telegram_text_from_card',
    'normalize_render_mode',
]
