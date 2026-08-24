"""Extranotifs Module.

Implements core runtime logic and helpers used by this feature.
"""

import requests
import json
import logging
from flask import current_app

from core.logger import system_logger
from core.notifications import (
    build_notification_card,
    fill_missing_target_metrics,
    normalize_event_code,
    normalize_render_mode,
    render_notification_card_png,
    render_ntfy_text_from_card,
)

logger = logging.getLogger(__name__)


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


def _header_safe(value: str, max_len: int = 180, fallback: str = "Nutify Notification") -> str:
    compact = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())
    # HTTP headers are latin-1 encoded by the client stack.
    compact = compact.encode("latin-1", errors="ignore").decode("latin-1", errors="ignore")
    if not compact.strip():
        compact = fallback
    return compact[:max_len]


def _is_attachment_rejected_response(response) -> bool:
    if response is None:
        return False
    try:
        body = str(response.text or "").lower()
    except Exception:
        body = ""
    return (
        int(getattr(response, "status_code", 0) or 0) in (400, 413, 415)
        and (
            "attachments not allowed" in body
            or '"code":40014' in body
            or "code:40014" in body
        )
    )


class NtfyNotifier:
    def __init__(self, config):
        self.config = config
        self.server = config.get('server', 'https://ntfy.sh')
        self.topic = config.get('topic', '')
        self.use_auth = config.get('use_auth', False)
        self.username = config.get('username', '')
        self.password = config.get('password', '')
        self.priority = config.get('priority', 3)
        self.use_tags = config.get('use_tags', True)
        self.render_mode = normalize_render_mode(config.get('render_mode'))
        self.server_name = config.get('server_name', '')
    
    def send_notification(self, title, message, event_type=None, priority=None, image_bytes=None):
        """
        Send a notification to Ntfy
        
        Args:
            title (str): Notification title
            message (str): Notification message
            event_type (str, optional): Event type for tagging. Defaults to None.
            priority (int, optional): Override default priority. Defaults to None.
        
        Returns:
            dict: Response with success status and message
        """
        try:
            # Prepare headers
            safe_title = _header_safe(title, 120)
            headers = {
                "Title": safe_title,
                "X-Title": safe_title,
                "Priority": str(priority if priority is not None else self.priority),
                "Markdown": "yes",
                "X-Markdown": "yes",
            }
            
            # Add tags based on event type if enabled
            if self.use_tags and event_type:
                tag = self._get_tag_for_event(event_type)
                if tag:
                    headers["Tags"] = tag
                    headers["X-Tags"] = tag
            
            # Add the server name to message if it exists and isn't already included
            if self.server_name and not message.startswith(f"[{self.server_name}]"):
                message = f"[{self.server_name}] {message}"

            _trace(
                "Ntfy send trace event=%s render_mode=%s priority=%s preview=%s",
                event_type or 'TEST',
                self.render_mode,
                priority if priority is not None else self.priority,
                _message_preview(message),
            )
            
            # Prepare auth
            auth = None
            if self.use_auth and self.username and self.password:
                # If the password is asterisks, we need to get the real password from the database
                if self.password == '********':
                    # Get the real password from the database
                    from app import db
                    from core.extranotifs.ntfy.db import get_ntfy_model
                    
                    NtfyConfig = get_ntfy_model() or db.ModelClasses.NtfyConfig
                    config_id = self.config.get('id')
                    
                    if config_id:
                        config = NtfyConfig.query.get(config_id)
                        if config and config.password:
                            self.password = config.password
                
                # Set auth tuple with username and password
                auth = (self.username, self.password)
            
            # Send notification
            url = f"{self.server}/{self.topic}"
            logger.debug(f"Sending ntfy notification to {url} with auth: {bool(auth)}")
            delivery_mode = "text"
            used_text_fallback = False

            if image_bytes and self.render_mode == 'graphic':
                delivery_mode = "image"
                headers["Filename"] = "nutify-notification.png"
                headers["X-Filename"] = "nutify-notification.png"
                safe_caption = _header_safe(
                    message or title or "Nutify notification attachment",
                    180,
                    fallback=safe_title,
                )
                headers["Message"] = safe_caption
                headers["X-Message"] = safe_caption
                _trace(
                    "Ntfy graphic delivery trace event=%s render_mode=%s image_bytes=%s title=%s caption=%s",
                    event_type or 'TEST',
                    self.render_mode,
                    len(image_bytes),
                    safe_title,
                    safe_caption,
                )
                response = requests.post(
                    url,
                    data=image_bytes,
                    headers=headers,
                    auth=auth,
                    timeout=20,
                )
                if _is_attachment_rejected_response(response):
                    used_text_fallback = True
                    delivery_mode = "text_fallback"
                    _trace(
                        "Ntfy graphic fallback trace event=%s reason=attachments_not_allowed status=%s",
                        event_type or 'TEST',
                        response.status_code,
                    )
                    fallback_headers = dict(headers)
                    fallback_headers.pop("Filename", None)
                    fallback_headers.pop("X-Filename", None)
                    fallback_headers.pop("Message", None)
                    fallback_headers.pop("X-Message", None)
                    response = requests.post(
                        url,
                        data=message,
                        headers=fallback_headers,
                        auth=auth,
                        timeout=10,
                    )
            else:
                response = requests.post(
                    url,
                    data=message,
                    headers=headers,
                    auth=auth,
                    timeout=10
                )
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"Ntfy notification sent successfully to {self.topic}")
                success_message = "Notification sent successfully"
                if used_text_fallback:
                    success_message = "Notification sent successfully (text fallback)"
                return {
                    "success": True,
                    "message": success_message,
                    "delivery_mode": delivery_mode,
                    "render_mode": self.render_mode,
                }
            else:
                logger.error(f"Failed to send Ntfy notification: {response.text}")
                return {
                    "success": False,
                    "message": f"Error {response.status_code}: {response.text}",
                    "delivery_mode": delivery_mode,
                    "render_mode": self.render_mode,
                }
                
        except Exception as e:
            logger.error(f"Error sending Ntfy notification: {str(e)}")
            _trace(
                "Ntfy send failure trace event=%s render_mode=%s error=%s",
                event_type or 'TEST',
                self.render_mode,
                str(e),
            )
            return {
                "success": False,
                "message": str(e),
                "delivery_mode": "text",
                "render_mode": self.render_mode,
            }
    
    def _get_tag_for_event(self, event_type):
        """Map event types to appropriate Ntfy tags"""
        event_tags = {
            "ONLINE": "white_check_mark",
            "ONBATT": "battery",
            "LOWBATT": "warning,battery",
            "COMMOK": "signal_strength",
            "COMMBAD": "no_mobile_phones",
            "SHUTDOWN": "sos,warning",
            "REPLBATT": "wrench,battery",
            "NOCOMM": "no_entry,warning",
            "NOPARENT": "ghost"
        }
        return event_tags.get(event_type, "")

def _get_server_name():
    """Get the server name from database without fallback"""
    try:
        from core.settings import get_server_name

        server_name = get_server_name()
        logger.debug(f"Ntfy using server name: {server_name}")
        return server_name
    except Exception as e:
        logger.error(f"Failed to get server name in Ntfy: {str(e)}")
        raise  # Re-raise the error rather than providing a fallback

def test_notification(config, event_type=None):
    """
    Send a test notification using the provided configuration
    
    Args:
        config (dict): Ntfy configuration
        event_type (str, optional): Event type for test. Defaults to None.
    
    Returns:
        dict: Response with success status and message
    """
    try:
        # Get server name
        server_name = _get_server_name()
        
        # Add server_name to config
        config['server_name'] = server_name
        
        notifier = NtfyNotifier(config)
        
        # Include server_name in title (more prominently)
        title = f"[{server_name}] Test Notification"
        if event_type:
            normalized_event = normalize_event_code(event_type)
            target_id = config.get('target_id')
            try:
                target_id = int(target_id) if target_id is not None else None
            except (TypeError, ValueError):
                target_id = None
            card = build_notification_card(
                normalized_event,
                server_name=server_name,
                target_id=target_id,
                target_name=str(config.get('display_name') or config.get('name') or 'Ntfy'),
                target_label='notify-test',
                metrics=fill_missing_target_metrics(target_id),
                reason='manual test',
            )
            message = render_ntfy_text_from_card(card, render_mode=notifier.render_mode)
            image_bytes = None
            if notifier.render_mode == 'graphic':
                try:
                    image_bytes = render_notification_card_png(card)
                except Exception as graphic_exc:
                    logger.warning("Ntfy graphic test fallback to text-only payload: %s", graphic_exc)
            title = f"[{server_name}] Test: {normalized_event}"
        else:
            message = "This is a test notification from Nutify"
            image_bytes = None

        result = notifier.send_notification(title, message, event_type, image_bytes=image_bytes)
        if isinstance(result, dict):
            result.setdefault('render_mode', notifier.render_mode)
            result.setdefault('delivery_mode', 'image' if image_bytes else 'text')
        return result
    except Exception as e:
        logger.error(f"Error in Ntfy test notification: {str(e)}")
        return {"success": False, "message": str(e)}

def send_event_notification(event_type, message, target_id=None, notification_card=None):
    """
    Send a notification for a specific event type
    
    Args:
        event_type (str): Event type
        message (str): Notification message
    
    Returns:
        dict: Response with success status
    """
    try:
        from core.extranotifs.ntfy.db import get_config_for_event

        normalized_event = normalize_event_code(event_type)
        config = get_config_for_event(normalized_event, target_id=target_id)
        if not config:
            logger.debug("No Ntfy configuration enabled for event %s target_id=%s", normalized_event, target_id)
            return {"success": False, "message": f"No configuration enabled for {normalized_event}"}

        logger.debug(
            "Using Ntfy config ID %s for %s notification (target_id=%s)",
            config.get('id'),
            normalized_event,
            target_id,
        )
        
        # Get server name
        server_name = _get_server_name()
        
        # Add server_name to config
        config['server_name'] = server_name
        
        # Send notification
        notifier = NtfyNotifier(config)
        
        event_titles = {
            "ONLINE": "UPS Online",
            "ONBATT": "UPS On Battery",
            "LOWBATT": "UPS Low Battery",
            "COMMOK": "UPS Communication Restored",
            "COMMBAD": "UPS Communication Lost",
            "SHUTDOWN": "System Shutdown Imminent",
            "REPLBATT": "UPS Battery Replacement Needed",
            "NOCOMM": "UPS Not Reachable",
            "NOPARENT": "Parent Process Lost"
        }
        
        # Add server_name to the title in a more prominent way
        base_title = event_titles.get(normalized_event, f"UPS Event: {normalized_event}")
        title = f"[{server_name}] {base_title}"

        if isinstance(notification_card, dict):
            card = dict(notification_card)
        else:
            card = build_notification_card(
                normalized_event,
                server_name=server_name,
                target_id=target_id,
                target_name=str(config.get('display_name') or config.get('name') or 'UPS'),
                target_label='notification',
                metrics={},
                reason=str(message or '').strip(),
            )
        rendered_message = render_ntfy_text_from_card(card, render_mode=notifier.render_mode)
        _trace(
            "Ntfy event renderer trace target_id=%s event=%s config_id=%s render_mode=%s preview=%s",
            target_id,
            normalized_event,
            config.get('id'),
            notifier.render_mode,
            _message_preview(rendered_message),
        )
        card_title = str(card.get('title') or '').strip()
        if card_title:
            title = f"[{server_name}] {card_title}"

        logger.debug(f"Sending event notification for {normalized_event} with config ID {config.get('id')}")
        image_bytes = None
        if notifier.render_mode == 'graphic':
            try:
                image_bytes = render_notification_card_png(card)
            except Exception as graphic_exc:
                logger.warning("Ntfy graphic event fallback to text-only payload: %s", graphic_exc)
        result = notifier.send_notification(
            title,
            rendered_message,
            normalized_event,
            image_bytes=image_bytes,
        )
        if isinstance(result, dict):
            result.setdefault('config_id', config.get('id'))
            result.setdefault('render_mode', notifier.render_mode)
            result.setdefault('delivery_mode', 'image' if image_bytes else 'text')
        return result
        
    except Exception as e:
        logger.error(f"Error sending Ntfy event notification: {str(e)}")
        return {"success": False, "message": str(e)} 
