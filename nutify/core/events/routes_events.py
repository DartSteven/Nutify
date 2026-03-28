"""Routes for UPS events handling and display."""

import hmac

from flask import Blueprint, current_app, jsonify, request
from core.auth import require_permission
from core.logger import events_logger as logger
from core.react_frontend import serve_react_index
from core.upsmon import handle_nut_event
from .callback_token import get_configured_event_api_token

# Create a blueprint for events routes
routes_events = Blueprint('routes_events', __name__)


def _configured_event_api_token() -> str:
    """Return configured callback token from app/env/persisted token file."""
    return get_configured_event_api_token()


def _is_event_token_valid() -> bool:
    """Validate incoming X-Nutify-Token when token enforcement is enabled."""
    expected_token = _configured_event_api_token()
    if not expected_token:
        logger.error("Event callback token is missing; rejecting unsigned /nut_event request")
        return False
    received_token = (request.headers.get('X-Nutify-Token') or '').strip()
    return hmac.compare_digest(received_token, expected_token)

@routes_events.route('/events')
@require_permission('events')
def events_page():
    """Render the events page with React SPA."""
    return serve_react_index()

@routes_events.route('/nut_event', methods=['POST'])
def nut_event_route():
    """Handles incoming NUT events"""
    try:
        if not _is_event_token_valid():
            logger.warning(
                "Rejected /nut_event due to invalid X-Nutify-Token from source_ip=%s",
                request.headers.get('X-Forwarded-For', request.remote_addr),
            )
            return jsonify({"status": "error", "message": "Unauthorized"}), 401

        if not request.is_json:
            logger.error("No JSON data received on /nut_event")
            return jsonify({"status": "error", "message": "No JSON data received"}), 400

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            logger.error("Invalid JSON payload on /nut_event")
            return jsonify({"status": "error", "message": "Invalid JSON payload"}), 400

        data = dict(payload)
        source_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if source_ip:
            data.setdefault('source_ip', source_ip.split(',')[0].strip())

        logger.info(
            "Legacy NUT event callback received source_ip=%s ups=%s event=%s target_id=%s",
            data.get('source_ip'),
            data.get('ups'),
            data.get('event'),
            data.get('target_id'),
        )

        handled = handle_nut_event(current_app, data)
        if handled:
            return jsonify({"status": "ok", "message": "Event processed"}), 200

        logger.error(
            "Legacy NUT event processing failed source_ip=%s ups=%s event=%s target_id=%s",
            data.get('source_ip'),
            data.get('ups'),
            data.get('event'),
            data.get('target_id'),
        )
        return jsonify({"status": "error", "message": "Failed to process NUT event"}), 500
    except Exception as e:
        logger.error(f"Error handling NUT event: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500 
