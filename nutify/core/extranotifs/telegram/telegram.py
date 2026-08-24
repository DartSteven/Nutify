"""Telegram notification sender for UPS events."""

from __future__ import annotations

import logging
import requests

from core.logger import system_logger
from core.notifications import (
    build_notification_card,
    fill_missing_target_metrics,
    normalize_event_code,
    normalize_render_mode,
    render_notification_card_png,
    render_telegram_text_from_card,
)

logger = logging.getLogger(__name__)
_VALID_PARSE_MODES = {'HTML', 'MARKDOWN', 'MARKDOWNV2', 'NONE'}


def _normalize_event_type(event_type: str) -> str:
    return normalize_event_code(event_type)


def _normalize_parse_mode(value: str | None) -> str:
    parse_mode = str(value or 'HTML').strip().upper()
    if parse_mode in _VALID_PARSE_MODES:
        return parse_mode
    return 'HTML'


def _effective_parse_mode(render_mode: str, parse_mode: str) -> str:
    # Graphic mode relies on Telegram HTML markup from the canonical renderer.
    if normalize_render_mode(render_mode) == 'graphic':
        return 'HTML'
    return _normalize_parse_mode(parse_mode)


def _message_preview(value: str, max_chars: int = 220) -> str:
    text = str(value or '').replace('\n', '\\n')
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}..."


def _trace(message: str, *args) -> None:
    logger.info(message, *args)
    try:
        system_logger.info(message, *args)
    except Exception:
        pass


def _build_photo_caption(card: dict) -> str:
    context = card.get('context') or {}
    status = card.get('status') or {}
    lines = [
        f"{card.get('title') or 'UPS EVENT'}",
        f"{status.get('label') or 'Status'}: {status.get('value') or 'UNKNOWN'}",
    ]
    target_name = str(context.get('targetName') or '').strip()
    target_label = str(context.get('targetLabel') or '').strip()
    if target_name or target_label:
        lines.append(f"Target: {target_name or 'Unknown'} ({target_label or 'Unknown'})")
    reason = str(context.get('reason') or '').strip()
    if reason:
        lines.append(f"Reason: {reason}")
    caption = "\n".join(line for line in lines if line).strip()
    return caption[:1000]


class TelegramNotifier:
    """Simple Telegram Bot API notifier."""

    def __init__(self, config):
        self.config = dict(config or {})
        self.bot_token = str(self.config.get('bot_token') or '').strip()
        self.chat_id = str(self.config.get('chat_id') or '').strip()
        self.parse_mode = _normalize_parse_mode(self.config.get('parse_mode'))
        self.disable_web_preview = bool(self.config.get('disable_web_preview', False))
        self.render_mode = normalize_render_mode(self.config.get('render_mode'))
        self.server_name = str(self.config.get('server_name') or '').strip()
        self._hydrate_masked_secrets()

    def _hydrate_masked_secrets(self):
        """Resolve masked credentials from DB config if needed."""
        if self.bot_token != '********' and self.chat_id != '********':
            return
        config_id = self.config.get('id')
        if not config_id:
            return
        try:
            from core.extranotifs.telegram.db import get_config_by_id

            raw_config = get_config_by_id(config_id, target_id=self.config.get('target_id'), include_secrets=True)
            if not raw_config:
                return
            if self.bot_token == '********':
                self.bot_token = str(raw_config.get('bot_token') or '').strip()
            if self.chat_id == '********':
                self.chat_id = str(raw_config.get('chat_id') or '').strip()
        except Exception as exc:
            logger.debug("Unable to hydrate masked Telegram secrets for config %s: %s", config_id, exc)

    def _api_url(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def _photo_api_url(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"

    def send_notification(
        self,
        title: str,
        message: str,
        event_type: str | None = None,
        parse_mode_override: str | None = None,
        prepend_title: bool = True,
    ):
        """Send one Telegram message using configured bot and chat."""
        if not self.bot_token:
            return {"success": False, "message": "Missing Telegram bot token"}
        if not self.chat_id:
            return {"success": False, "message": "Missing Telegram chat ID"}

        safe_title = str(title or '').strip()
        safe_message = str(message or '').strip()
        server_prefix = f"[{self.server_name}] " if self.server_name else ""
        if prepend_title and safe_title and safe_message:
            payload_text = f"{server_prefix}{safe_title}\n{safe_message}"
        elif prepend_title and safe_title:
            payload_text = f"{server_prefix}{safe_title}"
        else:
            payload_text = safe_message or f"{server_prefix}{safe_title}".strip()
        effective_parse_mode = _normalize_parse_mode(parse_mode_override or self.parse_mode)
        payload = {
            "chat_id": self.chat_id,
            "text": payload_text,
            "disable_web_page_preview": self.disable_web_preview,
        }

        if effective_parse_mode in {'HTML', 'MARKDOWN', 'MARKDOWNV2'}:
            payload["parse_mode"] = effective_parse_mode

        _trace(
            "Telegram send trace event=%s render_mode=%s parse_mode=%s preview=%s",
            event_type or 'TEST',
            self.render_mode,
            effective_parse_mode,
            _message_preview(payload_text),
        )

        try:
            response = requests.post(self._api_url(), json=payload, timeout=10)
            data = response.json() if response.content else {}
            if response.status_code == 200 and bool(data.get('ok')):
                logger.info("Telegram notification sent successfully for event %s", event_type or 'TEST')
                return {"success": True, "message": "Notification sent successfully"}
            description = data.get('description') if isinstance(data, dict) else None
            error_text = description or response.text or f"HTTP {response.status_code}"
            logger.error("Telegram notification failed: %s", error_text)
            return {"success": False, "message": error_text}
        except Exception as exc:
            logger.error("Error sending Telegram notification: %s", exc)
            return {"success": False, "message": str(exc)}

    def send_photo_notification(
        self,
        image_bytes: bytes,
        caption: str = "",
        event_type: str | None = None,
    ):
        """Send one Telegram photo message with optional caption."""
        if not self.bot_token:
            return {"success": False, "message": "Missing Telegram bot token"}
        if not self.chat_id:
            return {"success": False, "message": "Missing Telegram chat ID"}
        if not image_bytes:
            return {"success": False, "message": "Missing image payload"}

        effective_parse_mode = _normalize_parse_mode(self.parse_mode)
        payload = {
            "chat_id": self.chat_id,
            "disable_notification": False,
        }
        if caption:
            payload["caption"] = str(caption or "")[:1000]
        if effective_parse_mode in {"HTML", "MARKDOWN", "MARKDOWNV2"} and caption:
            payload["parse_mode"] = effective_parse_mode
        files = {
            "photo": ("nutify-notification.png", image_bytes, "image/png"),
        }

        _trace(
            "Telegram sendPhoto trace event=%s render_mode=%s parse_mode=%s bytes=%s",
            event_type or "TEST",
            self.render_mode,
            effective_parse_mode,
            len(image_bytes),
        )

        try:
            response = requests.post(self._photo_api_url(), data=payload, files=files, timeout=20)
            data = response.json() if response.content else {}
            if response.status_code == 200 and bool(data.get("ok")):
                logger.info("Telegram photo notification sent successfully for event %s", event_type or "TEST")
                return {"success": True, "message": "Notification sent successfully"}
            description = data.get("description") if isinstance(data, dict) else None
            error_text = description or response.text or f"HTTP {response.status_code}"
            logger.error("Telegram photo notification failed: %s", error_text)
            return {"success": False, "message": error_text}
        except Exception as exc:
            logger.error("Error sending Telegram photo notification: %s", exc)
            return {"success": False, "message": str(exc)}


def _get_server_name():
    """Get the server name from settings database."""
    from core.settings import get_server_name

    return get_server_name()


def test_notification(config, event_type=None):
    """Send a test Telegram notification with optional event type."""
    try:
        cfg = dict(config or {})
        server_name = _get_server_name()
        cfg['server_name'] = server_name
        notifier = TelegramNotifier(cfg)

        normalized_event = _normalize_event_type(event_type or '')
        effective_parse_mode = _effective_parse_mode(notifier.render_mode, notifier.parse_mode)

        if normalized_event:
            title = f"Test: {normalized_event}"
            target_id = cfg.get('target_id')
            try:
                target_id = int(target_id) if target_id is not None else None
            except (TypeError, ValueError):
                target_id = None
            card = build_notification_card(
                normalized_event,
                server_name=server_name,
                target_id=target_id,
                target_name=str(cfg.get('display_name') or cfg.get('name') or 'Telegram'),
                target_label='notify-test',
                metrics=fill_missing_target_metrics(target_id),
                reason='manual test',
            )
            if notifier.render_mode == 'graphic':
                try:
                    image_bytes = render_notification_card_png(card)
                    result = notifier.send_photo_notification(
                        image_bytes=image_bytes,
                        caption=_build_photo_caption(card),
                        event_type=normalized_event,
                    )
                    if isinstance(result, dict):
                        result.setdefault('render_mode', notifier.render_mode)
                        result.setdefault('parse_mode', effective_parse_mode)
                        result.setdefault('delivery_mode', 'image')
                    return result
                except Exception as graphic_exc:
                    logger.warning("Telegram graphic test fallback to text: %s", graphic_exc)

            message = render_telegram_text_from_card(
                card,
                render_mode=notifier.render_mode,
                parse_mode=effective_parse_mode,
            )
        else:
            title = "Test Notification"
            message = "This is a test notification from Nutify."

        prepend_title = not (normalized_event and notifier.render_mode == 'graphic')
        result = notifier.send_notification(
            title,
            message,
            normalized_event or None,
            parse_mode_override=effective_parse_mode,
            prepend_title=prepend_title,
        )
        if isinstance(result, dict):
            result.setdefault('render_mode', notifier.render_mode)
            result.setdefault('parse_mode', effective_parse_mode)
        return result
    except Exception as exc:
        logger.error("Error in Telegram test notification: %s", exc)
        return {"success": False, "message": str(exc)}


def send_event_notification(event_type, message, target_id=None, notification_card=None):
    """Send one Telegram event notification for the active target scope."""
    try:
        from core.extranotifs.telegram.db import get_config_for_event

        normalized_event = _normalize_event_type(event_type)
        config = get_config_for_event(normalized_event, target_id=target_id, include_secrets=True)
        if not config:
            logger.debug("No Telegram configuration enabled for event %s", normalized_event)
            return {"success": False, "message": f"No configurations enabled for {normalized_event}"}

        config = dict(config)
        config['server_name'] = _get_server_name()
        notifier = TelegramNotifier(config)
        effective_parse_mode = _effective_parse_mode(notifier.render_mode, notifier.parse_mode)

        event_titles = {
            "ONLINE": "UPS Online",
            "ONBATT": "UPS On Battery",
            "LOWBATT": "UPS Low Battery",
            "COMMOK": "UPS Communication Restored",
            "COMMBAD": "UPS Communication Lost",
            "SHUTDOWN": "System Shutdown Imminent",
            "REPLBATT": "UPS Battery Replacement Needed",
            "NOCOMM": "UPS Not Reachable",
            "NOPARENT": "Parent Process Lost",
        }
        title = event_titles.get(normalized_event, f"UPS Event: {normalized_event}")
        if isinstance(notification_card, dict):
            card = dict(notification_card)
        else:
            card = build_notification_card(
                normalized_event,
                server_name=str(config.get('server_name') or ''),
                target_id=target_id,
                target_name=str(config.get('display_name') or config.get('name') or 'UPS'),
                target_label='notification',
                metrics={},
                reason=str(message or '').strip(),
            )
        rendered_message = render_telegram_text_from_card(
            card,
            render_mode=notifier.render_mode,
            parse_mode=effective_parse_mode,
        )
        _trace(
            "Telegram event renderer trace target_id=%s event=%s config_id=%s render_mode=%s parse_mode=%s preview=%s",
            target_id,
            normalized_event,
            config.get('id'),
            notifier.render_mode,
            effective_parse_mode,
            _message_preview(rendered_message),
        )
        card_title = str(card.get('title') or '').strip()
        if card_title:
            title = card_title

        if notifier.render_mode == 'graphic':
            try:
                image_bytes = render_notification_card_png(card)
                send_result = notifier.send_photo_notification(
                    image_bytes=image_bytes,
                    caption=_build_photo_caption(card),
                    event_type=normalized_event,
                )
                if isinstance(send_result, dict):
                    send_result.setdefault('config_id', config.get('id'))
                    send_result.setdefault('render_mode', notifier.render_mode)
                    send_result.setdefault('parse_mode', effective_parse_mode)
                    send_result.setdefault('delivery_mode', 'image')
                return send_result
            except Exception as graphic_exc:
                logger.warning("Telegram graphic event fallback to text: %s", graphic_exc)

        send_result = notifier.send_notification(
            title,
            rendered_message,
            normalized_event,
            parse_mode_override=effective_parse_mode,
            prepend_title=(notifier.render_mode != 'graphic'),
        )
        if isinstance(send_result, dict):
            send_result.setdefault('config_id', config.get('id'))
            send_result.setdefault('render_mode', notifier.render_mode)
            send_result.setdefault('parse_mode', effective_parse_mode)
        return send_result
    except Exception as exc:
        logger.error("Error sending Telegram event notification: %s", exc)
        return {"success": False, "message": str(exc)}
