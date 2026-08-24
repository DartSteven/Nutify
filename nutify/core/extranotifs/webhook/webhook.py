"""
Webhook notification system for UPS events.
"""

import json
import logging
import urllib3
from flask import current_app
import datetime
from core.logger import webhook_logger as logger
import socket
import ssl
import os
import time
import hmac
import hashlib
import re
import uuid
from urllib3.exceptions import InsecureRequestWarning
import urllib.parse

# --- Imports for urllib approach ---
import urllib.request
import urllib.error
import base64 
from core.notifications import (
    build_notification_card,
    build_webhook_event_data_from_card,
    fill_missing_target_metrics,
    normalize_event_code,
    normalize_render_mode,
    render_notification_card_png,
    render_mail_html_from_card,
    render_ntfy_text_from_card,
)

# Disable insecure request warnings when verify=False is used
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def _get_server_name():
    """Get the server name from database without fallback"""
    try:
        from core.settings import get_server_name

        server_name = get_server_name()
        logger.debug(f"Webhook using server name: {server_name}")
        return server_name
    except Exception as e:
        logger.error(f"Failed to get server name in Webhook: {str(e)}")
        raise  # Re-raise the error rather than providing a fallback


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_target_scoped_ups_info(target_id):
    """Build webhook UPS info directly from Multi-NUT target snapshots."""
    if target_id is None:
        return None

    try:
        from core.multi_nut.storage import get_target_with_policy
        from core.multi_nut.storage_snapshots import extract_metric, get_latest_target_snapshot

        target, _policy = get_target_with_policy(int(target_id))
        latest_snapshot = get_latest_target_snapshot(int(target_id)) or {}
        if not target and not latest_snapshot:
            return None

        def metric(name, default=None):
            value = extract_metric(latest_snapshot, name)
            return default if value is None else value

        ups_model = str(metric('device_model') or metric('ups_model') or getattr(target, 'name', 'Unknown'))
        ups_status = str(metric('ups_status') or ('NOCOMM' if target and getattr(target, 'last_test_status', True) is False else 'UNKNOWN'))
        battery_charge = _safe_float(metric('battery_charge'))
        input_voltage = _safe_float(metric('input_voltage'))

        return {
            'ups_model': ups_model,
            'device_serial': str(metric('device_serial') or 'Unknown'),
            'ups_status': ups_status,
            'battery_charge': f"{battery_charge:.1f}" if battery_charge is not None else '0',
            'input_voltage': f"{input_voltage:.1f}V" if input_voltage is not None else '0V',
        }
    except Exception as exc:
        logger.warning(f"Failed to build target-scoped webhook UPS info for target_id={target_id}: {exc}")
        return None

class WebhookNotifier:
    def __init__(self, config):
        self.config = config
        self.name = config.get('display_name', config.get('name', 'Webhook'))  # Accept both name and display_name for backward compatibility
        self.url = config.get('url', '')
        self.server_type = config.get('server_type', 'custom')
        self.auth_type = config.get('auth_type', 'none')
        self.auth_username = config.get('auth_username', '')
        self.auth_password = config.get('auth_password', '')
        self.auth_token = config.get('auth_token', '')
        self.content_type = config.get('content_type', 'application/json')
        self.custom_headers = self._parse_custom_headers(config.get('custom_headers', ''))
        self.include_ups_data = config.get('include_ups_data', True)
        
        # Discord-specific configuration
        self.discord = config.get('discord', {})
        
        # Enhanced SSL verification options
        self.verify_ssl = config.get('verify_ssl', True)
        self.custom_ca_cert = config.get('custom_ca_cert', None)
        
        # Retry configuration
        self.max_retries = config.get('max_retries', 3)
        self.retry_backoff = config.get('retry_backoff', True)
        self.retry_timeout = config.get('retry_timeout', 30)
        
        # Webhook security options
        self.signing_enabled = config.get('signing_enabled', False)
        self.signing_secret = config.get('signing_secret', '')
        self.signing_header = config.get('signing_header', 'X-Nutify-Signature')
        self.signing_algorithm = config.get('signing_algorithm', 'sha256')
        
        # Testing options
        self.ignore_response_errors = config.get('ignore_response_errors', False)
        
        # Server name
        self.server_name = config.get('server_name', '')
    
    def _parse_custom_headers(self, headers_str):
        """Parse custom headers from JSON string or return empty dict"""
        try:
            if not headers_str:
                return {}
            return json.loads(headers_str)
        except Exception as e:
            logger.error(f"Error parsing custom headers: {str(e)}")
            return {}
    
    def _get_auth(self):
        """Get authentication based on auth_type"""
        if self.auth_type == 'basic':
            return (self.auth_username, self.auth_password)
        return None
    
    def _prepare_headers(self, payload_str=None):
        """
        Prepare HTTP headers for the webhook request
        
        Args:
            payload_str (str, optional): JSON payload string for signing. Defaults to None.
            
        Returns:
            dict: Prepared headers
        """
        headers = {
            'Content-Type': self.content_type,
            'User-Agent': 'Nutify-UPS-Monitor/1.0'
        }
        
        # Add bearer token if specified
        if self.auth_type == 'bearer' and self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        
        # Add signature if enabled and payload provided
        if self.signing_enabled and self.signing_secret and payload_str:
            signature = self._generate_signature(payload_str)
            if signature:
                headers[self.signing_header] = signature
                logger.debug(f"Added payload signature to {self.signing_header} header")
            
        # Add custom headers
        if self.custom_headers:
            headers.update(self.custom_headers)
            
        return headers
    
    def _generate_signature(self, payload_str):
        """
        Generate HMAC signature for the payload
        
        Args:
            payload_str (str): JSON payload string to sign
            
        Returns:
            str: Hex-encoded signature
        """
        try:
            if not self.signing_secret:
                logger.warning("Signature generation failed: No signing secret provided")
                return None
                
            # Convert string to bytes
            message = payload_str.encode('utf-8')
            secret = self.signing_secret.encode('utf-8')
            
            # Choose algorithm
            if self.signing_algorithm == 'sha256':
                hash_func = hashlib.sha256
            elif self.signing_algorithm == 'sha512':
                hash_func = hashlib.sha512
            else:
                hash_func = hashlib.sha256  # Default to SHA-256
            
            # Create signature
            signature = hmac.new(secret, message, hash_func).hexdigest()
            logger.debug(f"Generated {self.signing_algorithm} signature for payload")
            
            return signature
        except Exception as e:
            logger.error(f"Error generating signature: {str(e)}")
            return None
    
    def _prepare_payload(self, event_type, event_data, payload=None):
        """
        Prepare the webhook payload
        
        Args:
            event_type (str): Event type (ONLINE, ONBATT, etc.)
            event_data (dict): Additional event data
            payload (dict, optional): Custom payload data. Defaults to None.
            
        Returns:
            dict: Prepared payload
        """
        # Handle Discord webhook payloads differently
        if self.server_type == 'discord':
            return self._prepare_discord_payload(event_type, event_data, payload)
        
        # For regular webhooks, use the standard payload format
        # Start with base payload or provided payload
        result = payload or {}
        
        # Get current time with the configured timezone
        now = datetime.datetime.now()
        local_tz = current_app.CACHE_TIMEZONE
        if local_tz:
            now = now.astimezone(local_tz)
            
        # Add standard fields with timezone-aware timestamp
        result.update({
            'event_type': event_type,
            'event_timestamp': now.isoformat(),
            'event_description': self._get_event_description(event_type),
            'server_name': self.server_name  # Add server_name to payload
        })

        # Add UPS data if requested
        if self.include_ups_data and event_data.get('ups_info'):
            result['ups_data'] = event_data.get('ups_info')

        notification_card = event_data.get('notification_card')
        if isinstance(notification_card, dict):
            result['notification_card'] = notification_card

        message_text = str(event_data.get('message_text') or event_data.get('message') or '').strip()
        if not message_text and isinstance(notification_card, dict):
            message_text = str(notification_card.get('message') or notification_card.get('subtitle') or '').strip()
        title_text = str(event_data.get('title') or '').strip()
        if not title_text and isinstance(notification_card, dict):
            title_text = str(notification_card.get('title') or '').strip()
        if not title_text:
            title_text = f"UPS Event: {event_type}"
        if not message_text:
            message_text = self._get_event_description(event_type)

        result.setdefault('title', title_text)
        result.setdefault('message', message_text)
        result.setdefault('priority', 5 if event_type in ['ONBATT', 'LOWBATT', 'COMMBAD', 'NOCOMM', 'SHUTDOWN', 'REPLBATT', 'NOBATT'] else 2)
            
        return result
    
    def _prepare_discord_payload(self, event_type, event_data, custom_payload=None):
        """
        Prepare a Discord webhook payload
        
        Args:
            event_type (str): Event type (ONLINE, ONBATT, etc.)
            event_data (dict): Additional event data
            custom_payload (dict, optional): Custom payload data. Defaults to None.
            
        Returns:
            dict: Discord webhook payload
        """
        # Get UPS data if available
        ups_data = event_data.get('ups_info', {}) if self.include_ups_data else {}
        notification_card = event_data.get('notification_card') if isinstance(event_data, dict) else None
        
        # Determine color based on event type
        color = 0x00FF00  # Default green
        if event_type in ['ONBATT', 'LOWBATT', 'COMMBAD', 'NOCOMM', 'SHUTDOWN', 'REPLBATT', 'NOBATT']:
            color = 0xFF0000  # Red for critical events
        elif event_type in ['OVERLOAD', 'TRIM', 'BOOST', 'BYPASS']:
            color = 0xFFA500  # Orange for warning events
            
        # Include server_name in title
        title = None
        if self.discord.get('title'):
            title = self.discord.get('title')
        elif isinstance(notification_card, dict) and notification_card.get('title'):
            card_title = str(notification_card.get('title'))
            title = f"{self.server_name} - {card_title}" if self.server_name else card_title
        elif self.server_name:
            title = f"{self.server_name} - UPS Event: {event_type}"
        else:
            title = f"UPS Event: {event_type}"
        
        # Get current time with the configured timezone
        now = datetime.datetime.now()
        local_tz = current_app.CACHE_TIMEZONE
        if local_tz:
            now = now.astimezone(local_tz)
        
        # Create base embed with timezone-aware timestamp
        embed = {
            "title": title,
            "description": self._get_event_description(event_type),
            "color": color,
            "timestamp": now.isoformat(),
            "fields": []
        }

        if isinstance(notification_card, dict):
            card_message = str(notification_card.get('message') or '').strip()
            if card_message:
                embed["description"] = card_message

            card_status = notification_card.get('status') or {}
            status_value = str(card_status.get('value') or '').strip()
            if status_value:
                embed["fields"].append({
                    "name": str(card_status.get('label') or 'Status'),
                    "value": status_value,
                    "inline": True,
                })

            for detail in notification_card.get('details') or []:
                detail_text = str(detail).strip()
                if detail_text:
                    embed["fields"].append({
                        "name": "Detail",
                        "value": detail_text,
                        "inline": False,
                    })
        
        # Add server_name as a field if available
        if self.server_name:
            embed["fields"].append({
                "name": "Server Name",
                "value": self.server_name,
                "inline": True
            })
        
        # Add UPS data fields if available
        if ups_data:
            if 'ups_model' in ups_data:
                embed["fields"].append({
                    "name": "UPS Model",
                    "value": ups_data.get('ups_model', 'Unknown'),
                    "inline": True
                })
            
            if 'ups_status' in ups_data:
                embed["fields"].append({
                    "name": "UPS Status",
                    "value": ups_data.get('ups_status', 'Unknown'),
                    "inline": True
                })
                
            if 'battery_charge' in ups_data:
                embed["fields"].append({
                    "name": "Battery",
                    "value": f"{ups_data.get('battery_charge', '0')}%",
                    "inline": True
                })
                
            if 'input_voltage' in ups_data:
                embed["fields"].append({
                    "name": "Input Voltage",
                    "value": ups_data.get('input_voltage', 'Unknown'),
                    "inline": True
                })
                
            if 'device_serial' in ups_data:
                embed["fields"].append({
                    "name": "Device Serial",
                    "value": ups_data.get('device_serial', 'Unknown'),
                    "inline": True
                })
        
        # Build final payload
        discord_payload = {
            "embeds": [embed]
        }
        
        # Add content if provided
        if self.discord.get('content'):
            discord_payload["content"] = self.discord.get('content')
            
        # Add username if provided
        if self.discord.get('username'):
            discord_payload["username"] = self.discord.get('username')
            
        # Add avatar URL if provided
        if self.discord.get('avatar_url'):
            discord_payload["avatar_url"] = self.discord.get('avatar_url')
            
        # Override with custom payload data if provided
        if custom_payload:
            for key, value in custom_payload.items():
                if key not in ["embeds", "content", "username", "avatar_url"]:
                    continue
                discord_payload[key] = value
                
        return discord_payload

    def _extract_graphic_image_bytes(self, event_data):
        """Return decoded PNG bytes from canonical payload when present."""
        if not isinstance(event_data, dict):
            return None

        raw_b64 = event_data.get('message_image_png_base64')
        if not raw_b64:
            return None

        try:
            decoded = base64.b64decode(str(raw_b64), validate=False)
            if not decoded:
                return None
            return decoded
        except Exception as exc:
            logger.warning("Failed to decode webhook graphic image payload: %s", exc)
            return None

    def _build_discord_multipart(self, payload, image_bytes):
        """Build multipart/form-data body accepted by Discord webhooks."""
        boundary = f"----NutifyBoundary{uuid.uuid4().hex}"
        payload_json = json.dumps(payload or {}, separators=(',', ':'))
        chunks = [
            (
                f"--{boundary}\r\n"
                "Content-Disposition: form-data; name=\"payload_json\"\r\n"
                "Content-Type: application/json\r\n\r\n"
            ).encode('utf-8'),
            payload_json.encode('utf-8'),
            b"\r\n",
            (
                f"--{boundary}\r\n"
                "Content-Disposition: form-data; name=\"files[0]\"; filename=\"nutify-notification.png\"\r\n"
                "Content-Type: image/png\r\n\r\n"
            ).encode('utf-8'),
            image_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode('utf-8'),
        ]
        return b"".join(chunks), boundary
    
    def _get_event_description(self, event_type):
        """Get human-readable description for an event type"""
        event_descriptions = {
            'ONLINE': 'UPS is now running on line power',
            'ONBATT': 'UPS has switched to battery power',
            'LOWBATT': 'UPS battery is running low',
            'COMMOK': 'Communication with UPS has been restored',
            'COMMBAD': 'Communication with UPS has been lost',
            'SHUTDOWN': 'System shutdown is imminent due to low battery',
            'REPLBATT': 'UPS battery needs replacement',
            'NOCOMM': 'Cannot communicate with the UPS',
            'NOPARENT': 'Parent process has been lost',
            'CAL': 'UPS is performing calibration',
            'TRIM': 'UPS is trimming incoming voltage',
            'BOOST': 'UPS is boosting incoming voltage',
            'OFF': 'UPS is switched off',
            'OVERLOAD': 'UPS is overloaded',
            'BYPASS': 'UPS is in bypass mode',
            'NOBATT': 'UPS has no battery',
            'DATAOLD': 'UPS data is too old'
        }
        return event_descriptions.get(event_type, f'Unknown event: {event_type}')
    
    def _get_ssl_verify_param(self):
        """Determine the correct 'verify' parameter for requests.post"""
        if not self.verify_ssl:
            # Disable SSL verification if requested
            urllib3.disable_warnings(InsecureRequestWarning)
            logger.info("SSL certificate verification is disabled")
            return False # Return verify=False
        elif self.custom_ca_cert:
            # Use custom CA certificate if provided
            if os.path.exists(self.custom_ca_cert):
                logger.info(f"Using custom CA certificate: {self.custom_ca_cert}")
                return self.custom_ca_cert # Return path to CA cert
            else:
                logger.warning(f"Custom CA certificate not found: {self.custom_ca_cert}. Using system CA.")
                return True # Default to True
        else:
            # Use system CA certificates
            logger.info("Using system CA certificates for SSL verification")
            return True # Return verify=True
    
    def send_notification(self, event_type, event_data=None, custom_payload=None):
        # Initialize variables
        request_headers = {}
        payload = {}
        json_data, data, payload_str = None, None, None
        auth = None
        verify_param = True
        
        try:
            # --- Prepare payload, initial headers, auth, verify param ---
            payload = self._prepare_payload(event_type, event_data or {}, custom_payload)

            render_mode = normalize_render_mode((event_data or {}).get('render_mode'))
            discord_image_bytes = None
            if self.server_type == 'discord' and render_mode == 'graphic':
                discord_image_bytes = self._extract_graphic_image_bytes(event_data)
                if discord_image_bytes and isinstance(payload, dict):
                    # Graphic mode for Discord should prioritize image-only delivery.
                    payload.pop('content', None)
                    payload['embeds'] = [
                        {
                            'image': {'url': 'attachment://nutify-notification.png'},
                        }
                    ]

            if self.content_type == 'application/json':
                json_data = payload
                payload_str = json.dumps(payload, separators=(',', ':'))
            else:
                payload_str = json.dumps(payload)
                data = payload_str
            headers = self._prepare_headers(payload_str)
            auth = self._get_auth()
            verify_param = self._get_ssl_verify_param()
            request_headers = headers.copy() # Start with prepared headers

            # --- Log actual request attempt details --- 
            ssl_mode = "disabled" if not verify_param else ("custom_ca" if isinstance(verify_param, str) else "enabled")
            signing_mode = "enabled" if self.signing_enabled and self.signing_secret else "disabled"
            if discord_image_bytes:
                logger.info(
                    "Discord graphic webhook trace event=%s render_mode=%s image_bytes=%s",
                    event_type,
                    render_mode,
                    len(discord_image_bytes),
                )
            logger.info(f"Attempting POST to: {self.url}") # Log original URL
            logger.info(f"SSL verification: {ssl_mode}, Payload signing: {signing_mode}, Host header: {request_headers.get('Host')}")

            # Prepare data payload
            request_data = None
            if discord_image_bytes:
                multipart_data, boundary = self._build_discord_multipart(payload, discord_image_bytes)
                request_headers['Content-Type'] = f'multipart/form-data; boundary={boundary}'
                request_data = multipart_data
            elif data:
                request_data = data.encode('utf-8') # urllib expects bytes
            elif json_data:
                request_data = json.dumps(json_data).encode('utf-8')
                if 'Content-Type' not in request_headers and 'Content-type' not in request_headers:
                    request_headers['Content-Type'] = 'application/json'

            # --- Make the HTTP request using urllib.request --- 
            req = urllib.request.Request(self.url, method='POST')
            
            # Add headers
            for key, value in request_headers.items():
                req.add_header(key, value)
                
            # Add basic auth if needed
            if auth:
                auth_str = f'{auth[0]}:{auth[1]}'
                auth_bytes = base64.b64encode(auth_str.encode('utf-8'))
                req.add_header('Authorization', f'Basic {auth_bytes.decode("utf-8")}')
                    
            # Handle SSL verification
            ssl_context = None
            if self.url.startswith('https'):
                ssl_context = ssl.create_default_context()
                if not verify_param: # verify_ssl is False
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                    logger.warning("urllib: Disabling SSL certificate verification.")
                elif isinstance(verify_param, str): # custom_ca_cert path
                    try:
                        ssl_context.load_verify_locations(cafile=verify_param)
                        logger.info(f"urllib: Using custom CA certificate: {verify_param}")
                    except FileNotFoundError:
                        logger.error(f"urllib: Custom CA certificate not found: {verify_param}. Falling back to default verification.")
                    except Exception as ssl_err:
                        logger.error(f"urllib: Error loading custom CA certificate: {ssl_err}. Falling back to default verification.")
                # Else (verify_param is True), use default context
                
            # Make the request
            response = None
            try:
                response = urllib.request.urlopen(req, data=request_data, timeout=self.retry_timeout, context=ssl_context)
                status_code = response.getcode()
                response_body = response.read().decode('utf-8', errors='ignore')
                
                # Process successful response
                if status_code < 400:
                    logger.info(f"Webhook sent successfully via urllib: {status_code}")
                    return {
                        'success': True,
                        'message': f'Webhook sent successfully: {status_code}',
                        'status_code': status_code
                    }
                # Process failed response (HTTPError should catch this, but check anyway)
                else:
                    logger.error(f"Webhook failed via urllib: {status_code} - {response_body}")
                    return {
                        'success': False,
                        'message': f'Webhook failed: {status_code}',
                        'status_code': status_code,
                        'response': response_body[:200]
                    }
            except urllib.error.HTTPError as exc:
                status_code = exc.code
                try:
                    response_body = exc.read().decode('utf-8', errors='ignore')
                except Exception:
                    response_body = "(Could not read error body)"
                logger.error(f"Webhook HTTP error via urllib: {status_code} - {response_body}")
                return {
                    'success': False,
                    'message': f'Webhook failed: {status_code}',
                    'status_code': status_code,
                    'response': response_body[:200]
                }
            except urllib.error.URLError as exc:
                reason = str(exc.reason)
                logger.error(f"Webhook URL error via urllib: {reason}")
                # Check for DNS specific errors
                if isinstance(exc.reason, socket.gaierror):
                    error_type = 'dns_error'
                    message = f'DNS resolution error: {reason}'
                elif isinstance(exc.reason, socket.timeout) or "timed out" in reason.lower():
                    error_type = 'timeout_error'
                    message = f'Request timed out: {reason}'
                else:
                    error_type = 'connection_error'
                    message = f'Connection error: {reason}'
                return {
                    'success': False,
                    'message': message,
                    'error_type': error_type
                }
            except socket.timeout as exc:
                logger.error(f"Webhook socket timeout via urllib: {str(exc)}")
                return {'success': False, 'message': f'Request timed out: {str(exc)}', 'error_type': 'timeout_error'}
            finally:
                if response: response.close() # Ensure response is closed

        except RecursionError as rec_err: # Specific catch for RecursionError
            logger.error(f"CRITICAL: Maximum recursion depth exceeded. Likely eventlet/requests issue with IP+Host header. Error: {str(rec_err)}")
            try: logger.error(f"Recursion occurred attempting request to URL: {self.url}")
            except NameError: pass
            return {'success': False, 'message': 'Maximum recursion depth exceeded', 'error_type': 'recursion_error'}
        except Exception as e:
            logger.error(f"Unexpected error during webhook processing: {str(e)}")
            try: logger.error(f"Error occurred processing URL: {self.url}")
            except AttributeError: pass
            return {'success': False, 'message': str(e)}

def test_notification(config, event_type=None):
    """
    Send a test webhook notification
    
    Args:
        config (dict): Webhook configuration
        event_type (str, optional): Event type for test. Defaults to None.
        
    Returns:
        dict: Response with success status and message
    """
    try:
        normalized_event = normalize_event_code(event_type)

        # Get server name
        server_name = _get_server_name()
        
        # Get current time with the configured timezone
        now = datetime.datetime.now()
        local_tz = current_app.CACHE_TIMEZONE
        if local_tz:
            now = now.astimezone(local_tz)
        
        # Add ignore_response_errors parameter for testing
        config_copy = config.copy() if config else {}
        config_copy['ignore_response_errors'] = True
        config_copy['server_name'] = server_name  # Add server_name to config
        
        notifier = WebhookNotifier(config_copy)
        
        # Use provided event type or default to TEST
        test_event_type = event_type or 'TEST'

        target_id = config_copy.get('target_id')
        try:
            target_id = int(target_id) if target_id is not None else None
        except (TypeError, ValueError):
            target_id = None

        scoped_ups_info = _build_target_scoped_ups_info(target_id)
        
        # Prepare test data
        test_data = {
            'ups_info': scoped_ups_info or {
                'ups_model': 'Test UPS',
                'device_serial': 'TEST123456',
                'battery_charge': '100',
                'ups_status': 'OL',
                'input_voltage': '230'
            }
        }

        if event_type:
            test_data['notification_card'] = build_notification_card(
                normalized_event,
                server_name=server_name,
                target_id=target_id,
                target_name=str(config_copy.get('display_name') or config_copy.get('name') or 'Webhook'),
                target_label='notify-test',
                metrics=fill_missing_target_metrics(target_id),
                reason='manual test',
                timestamp=now,
            )
        
        # Prepare test payload with timezone-aware timestamp and server_name
        test_payload = {
            'test': True,
            'message': f'This is a test notification from {server_name} UPS Monitor',
            'timestamp': now.isoformat(),
            'server_name': server_name  # Include server_name in payload
        }
        
        result = notifier.send_notification(test_event_type, test_data, test_payload)
        
        # If the test fails with connection errors but we're set to ignore them
        if not result['success'] and result.get('error_type') == 'connection_error' and config_copy.get('ignore_response_errors'):
            logger.warning("Connection error occurred but payload was likely sent. Marking as successful for testing purposes.")
            return {
                'success': True,
                'message': 'Webhook was sent to the server, but no response was received. This is normal with simple test servers like netcat.',
                'original_error': result.get('message', 'Connection error')
            }
            
        return result
    except Exception as e:
        logger.error(f"Error in Webhook test notification: {str(e)}")
        return {'success': False, 'message': str(e)}

def get_ups_info(ups_name=None, target_id=None):
    """
    Get UPS information from the database
    
    Args:
        ups_name (str, optional): Name of the UPS. Defaults to None.
        
    Returns:
        dict: UPS data
    """
    scoped_ups_info = _build_target_scoped_ups_info(target_id)
    if scoped_ups_info:
        return scoped_ups_info

    if target_id is not None:
        return {
            'ups_model': 'Unknown',
            'device_serial': 'Unknown',
            'ups_status': 'NOCOMM',
            'battery_charge': '0',
            'input_voltage': '0V'
        }

    try:
        # Legacy fallback for unscoped/single-monitor events.
        from core.events.ups_notifier import get_detailed_ups_info
        return get_detailed_ups_info(ups_name or 'ups@localhost')
    except Exception as e:
        logger.error(f"Error getting UPS info: {str(e)}")
        return {
            'ups_model': 'Unknown',
            'device_serial': 'Unknown',
            'ups_status': 'Unknown',
            'battery_charge': '0',
            'input_voltage': '0V'
        }

def send_event_notification(event_type, ups_name=None, target_id=None, event_data=None):
    """
    Send webhook notifications for a UPS event
    
    Args:
        event_type (str): Event type (ONLINE, ONBATT, etc.)
        ups_name (str, optional): Name of the UPS. Defaults to None.
        
    Returns:
        dict: Response with success status
    """
    try:
        from core.extranotifs.webhook.db import get_enabled_configs_for_event
        normalized_event = normalize_event_code(event_type)
        
        # Get server name
        server_name = _get_server_name()
        
        # Get UPS information
        ups_info = get_ups_info(ups_name, target_id=target_id)
        
        # Get webhooks enabled for this event
        webhooks = get_enabled_configs_for_event(normalized_event, target_id=target_id)
        
        if not webhooks:
            logger.debug(f"No webhooks enabled for event {event_type}")
            return {'success': False, 'message': 'No webhooks enabled for this event'}
        
        # Build canonical notification card when caller does not provide one.
        notification_card = None
        if isinstance(event_data, dict):
            maybe_card = event_data.get('notification_card')
            if isinstance(maybe_card, dict):
                notification_card = maybe_card

        if not isinstance(notification_card, dict):
            notification_card = build_notification_card(
                normalized_event,
                server_name=server_name,
                target_id=target_id,
                target_name=str((event_data or {}).get('target_name') or ''),
                target_label=str(ups_name or 'notification'),
                metrics={
                    'ups_status': ups_info.get('ups_status'),
                    'battery_charge': _safe_float(ups_info.get('battery_charge')),
                    'input_voltage': _safe_float(str(ups_info.get('input_voltage') or '').replace('V', '')),
                },
                reason='',
            )

        payload_data = build_webhook_event_data_from_card(notification_card, fallback_ups_info=ups_info)
        payload_data['ups_name'] = ups_name
        payload_data['server_name'] = server_name
        if isinstance(event_data, dict):
            payload_data.update(event_data)
        payload_data['notification_card'] = notification_card
        
        # Send to all enabled webhooks
        results = []
        for webhook_config in webhooks:
            try:
                # Add server_name to each webhook config
                webhook_config['server_name'] = server_name
                config_render_mode = normalize_render_mode(webhook_config.get('render_mode'))
                payload_for_config = dict(payload_data)
                payload_for_config['render_mode'] = config_render_mode
                payload_for_config['message_text'] = render_ntfy_text_from_card(
                    notification_card,
                    render_mode=config_render_mode,
                )
                if config_render_mode == 'graphic':
                    payload_for_config['message_html'] = render_mail_html_from_card(notification_card)
                    try:
                        image_bytes = render_notification_card_png(notification_card)
                        payload_for_config['message_image_png_base64'] = base64.b64encode(image_bytes).decode('ascii')
                        payload_for_config['message_image_mime'] = 'image/png'
                    except Exception as graphic_exc:
                        logger.warning(
                            "Webhook graphic image rendering fallback to text/html only for config_id=%s: %s",
                            webhook_config.get('id'),
                            graphic_exc,
                        )
                
                notifier = WebhookNotifier(webhook_config)
                result = notifier.send_notification(normalized_event, payload_for_config)
                results.append({
                    'webhook_id': webhook_config.get('id'),
                    'webhook_name': webhook_config.get('name'),
                    'success': result.get('success'),
                    'message': result.get('message')
                })
            except Exception as e:
                logger.error(f"Error sending to webhook {webhook_config.get('id')}: {str(e)}")
                results.append({
                    'webhook_id': webhook_config.get('id'),
                    'webhook_name': webhook_config.get('name'),
                    'success': False,
                    'message': str(e)
                })
        
        # Consider successful if at least one webhook was sent successfully
        success = any(result.get('success') for result in results)
        
        return {
            'success': success,
            'message': f"Sent to {len(results)} webhooks, {sum(1 for r in results if r.get('success'))} succeeded",
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Error sending webhook event notifications: {str(e)}")
        return {'success': False, 'message': str(e)} 
