"""Upsmon API Module.

Defines API endpoints and response handlers for this feature domain.
"""

from flask import Blueprint, jsonify, request, current_app
from .upsmon_client import get_events_table, acknowledge_event, logger

api_upsmon = Blueprint('api_upsmon', __name__, url_prefix='/api/upsmon')

@api_upsmon.route('/events', methods=['GET'])
def get_events():
    """Get UPS events from the database
    
    Query parameters:
      - rows: Number of rows to retrieve (default: all)
    """
    try:
        rows = request.args.get('rows', 'all')
        result = get_events_table(rows)
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        logger.error(f"Error retrieving events: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@api_upsmon.route('/events/<int:event_id>/acknowledge', methods=['POST'])
def handle_acknowledge_event(event_id):
    """Acknowledge a UPS event"""
    try:
        success, message = acknowledge_event(event_id)
        return jsonify({
            'success': success,
            'message': message
        })
    except Exception as e:
        logger.error(f"Error acknowledging event: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@api_upsmon.route('/history', methods=['GET'])
def get_history():
    """Get event history from app memory"""
    try:
        from .upsmon_client import get_event_history
        return get_event_history(current_app)
    except Exception as e:
        logger.error(f"Error retrieving event history: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500 