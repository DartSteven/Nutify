"""Events API endpoints for managing UPS events and alerts."""

import hmac

from flask import current_app, jsonify, request
from ..logger import web_logger as logger
from ..upsmon import handle_nut_event, get_events_table, acknowledge_event, get_event_history
from ..db.ups import data_lock, db
from ..multi_nut.target_scope import apply_target_scope, resolve_settings_target_id
from .callback_token import get_configured_event_api_token


def _configured_event_api_token() -> str:
    """Return configured callback token from app/env/persisted token file."""
    return get_configured_event_api_token()


def _is_event_token_valid() -> bool:
    """Validate incoming X-Nutify-Token when token enforcement is enabled."""
    expected_token = _configured_event_api_token()
    if not expected_token:
        logger.error("Event callback token is missing; rejecting unsigned /api/nut_event request")
        return False
    received_token = (request.headers.get('X-Nutify-Token') or '').strip()
    return hmac.compare_digest(received_token, expected_token)


def register_api_routes(app):
    """Register events API routes with the Flask application."""
    
    # Import UPSEvent inside function to avoid circular imports
    from ..db.ups import UPSEvent
    from ..db.model_classes import ModelClasses
    
    # Helper function to ensure UPSEvent is initialized
    def _ensure_event_model():
        nonlocal UPSEvent
        if UPSEvent is None and hasattr(db, 'ModelClasses'):
            UPSEvent = db.ModelClasses.UPSEvent
            logger.debug("UPSEvent model initialized from ModelClasses")
        return UPSEvent is not None

    def _resolve_target_scope_id(payload=None):
        requested_target_id = request.args.get('target_id', type=int)
        if requested_target_id is None and isinstance(payload, dict):
            raw_target_id = payload.get('target_id')
            try:
                requested_target_id = int(raw_target_id) if raw_target_id is not None else None
            except (TypeError, ValueError):
                requested_target_id = None
        return resolve_settings_target_id(requested_target_id)

    @app.route('/api/nut_event', methods=['POST'])
    def nut_event():
        """Handles NUT events"""
        try:
            if not _is_event_token_valid():
                logger.warning(
                    "Rejected /api/nut_event due to invalid X-Nutify-Token from source_ip=%s",
                    request.headers.get('X-Forwarded-For', request.remote_addr),
                )
                return jsonify({"status": "error", "message": "Unauthorized"}), 401

            if not request.is_json:
                logger.error("No JSON data received")
                return jsonify({"status": "error", "message": "No JSON data received"}), 400

            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                logger.error("Invalid JSON payload for /api/nut_event")
                return jsonify({"status": "error", "message": "Invalid JSON payload"}), 400

            data = dict(payload)
            source_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            if source_ip:
                data.setdefault('source_ip', source_ip.split(',')[0].strip())

            logger.info(
                "NUT event callback received source_ip=%s ups=%s event=%s target_id=%s",
                data.get('source_ip'),
                data.get('ups'),
                data.get('event'),
                data.get('target_id'),
            )

            handled = handle_nut_event(app, data)
            if handled:
                return jsonify({"status": "ok", "message": "Event processed"}), 200

            logger.error(
                "NUT event processing failed source_ip=%s ups=%s event=%s target_id=%s",
                data.get('source_ip'),
                data.get('ups'),
                data.get('event'),
                data.get('target_id'),
            )
            return jsonify({"status": "error", "message": "Failed to process NUT event"}), 500
            
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            return jsonify({"status": "error", "message": str(e)}), 500

    nut_event._nutify_auth_kind = 'token'
    nut_event._nutify_auth_detail = 'X-Nutify-Token'

    @app.route('/api/nut_history')
    def nut_history():
        """Returns the NUT event history"""
        try:
            return get_event_history(app)
        except Exception as e:
            logger.error(f"Error getting NUT history: {str(e)}")
            return jsonify([]), 200  # Returns an empty list in case of error

    @app.route('/api/table/events', methods=['GET', 'POST'])
    def get_events_table_route():
        """API to get and manage events"""
        if request.method == 'GET':
            try:
                rows = request.args.get('rows', 'all')
                scoped_target_id = _resolve_target_scope_id()
                table_data = get_events_table(rows, target_id=scoped_target_id)
                return jsonify(table_data)
            except Exception as e:
                logger.error(f"Error getting events: {str(e)}", exc_info=True)
                return jsonify({'error': str(e)}), 500

        elif request.method == 'POST':
            try:
                payload = request.get_json(silent=True) or {}
                event_id = payload.get('event_id')
                scoped_target_id = _resolve_target_scope_id(payload)
                success, message = acknowledge_event(event_id, target_id=scoped_target_id)
                if success:
                    return jsonify({"status": "ok"})
                return jsonify({"status": "error", "message": message}), 404
            except Exception as e:
                logger.error(f"Error acknowledging event: {str(e)}", exc_info=True)
                return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/events/acknowledge/<int:event_id>', methods=['POST'])
    def acknowledge_event_route(event_id):
        """Acknowledges an event"""
        try:
            if not _ensure_event_model():
                return jsonify({'success': False, 'message': 'UPSEvent model not initialized'}), 500

            scoped_target_id = _resolve_target_scope_id()
            with data_lock:
                query = UPSEvent.query.filter(UPSEvent.id == event_id)
                query = apply_target_scope(UPSEvent, query, scoped_target_id)
                event = query.first()
                if event:
                    event.acknowledged = True
                    db.session.commit()
                    return jsonify({'success': True, 'message': 'Event acknowledged successfully'})
                return jsonify({'success': False, 'message': 'Event not found'}), 404
        except Exception as e:
            logger.error(f"Error acknowledging event: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/events/delete/<int:event_id>', methods=['DELETE'])
    def delete_event_route(event_id):
        """Deletes an event from the database"""
        try:
            if not _ensure_event_model():
                return jsonify({'success': False, 'message': 'UPSEvent model not initialized'}), 500

            scoped_target_id = _resolve_target_scope_id()
            with data_lock:
                query = UPSEvent.query.filter(UPSEvent.id == event_id)
                query = apply_target_scope(UPSEvent, query, scoped_target_id)
                event = query.first()
                if event:
                    db.session.delete(event)
                    db.session.commit()
                    return jsonify({'success': True, 'message': 'Event deleted successfully'})
                return jsonify({'success': False, 'message': 'Event not found'}), 404
        except Exception as e:
            logger.error(f"Error deleting event: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/events/acknowledge/bulk', methods=['POST'])
    def acknowledge_events_bulk():
        """Acknowledges multiple events"""
        try:
            if not _ensure_event_model():
                return jsonify({'success': False, 'message': 'UPSEvent model not initialized'}), 500

            data = request.get_json()
            event_ids = data.get('event_ids', [])

            if not event_ids:
                return jsonify({'success': False, 'message': 'No events specified'}), 400

            scoped_target_id = _resolve_target_scope_id(data)
            with data_lock:
                query = UPSEvent.query.filter(UPSEvent.id.in_(event_ids))
                query = apply_target_scope(UPSEvent, query, scoped_target_id)
                events = query.all()
                for event in events:
                    event.acknowledged = True
                db.session.commit()
                return jsonify({'success': True, 'message': f'{len(events)} events acknowledged successfully'})
        except Exception as e:
            logger.error(f"Error acknowledging events in bulk: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/events/delete/bulk', methods=['DELETE'])
    def delete_events_bulk():
        """Deletes multiple events from the database"""
        try:
            if not _ensure_event_model():
                return jsonify({'success': False, 'message': 'UPSEvent model not initialized'}), 500

            data = request.get_json()
            event_ids = data.get('event_ids', [])

            if not event_ids:
                return jsonify({'success': False, 'message': 'No events specified'}), 400

            scoped_target_id = _resolve_target_scope_id(data)
            with data_lock:
                query = UPSEvent.query.filter(UPSEvent.id.in_(event_ids))
                query = apply_target_scope(UPSEvent, query, scoped_target_id)
                events = query.all()
                for event in events:
                    db.session.delete(event)
                db.session.commit()
                return jsonify({'success': True, 'message': f'{len(events)} events deleted successfully'})
        except Exception as e:
            logger.error(f"Error deleting events in bulk: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/events/delete/all', methods=['DELETE'])
    def delete_all_events():
        """Deletes all events from the database"""
        try:
            if not _ensure_event_model():
                return jsonify({'success': False, 'message': 'UPSEvent model not initialized'}), 500

            scoped_target_id = _resolve_target_scope_id()
            with data_lock:
                # First count how many events we're deleting
                query = apply_target_scope(UPSEvent, UPSEvent.query, scoped_target_id)
                count = query.count()

                # Delete all events
                query.delete(synchronize_session=False)
                db.session.commit()

                return jsonify({'success': True, 'message': f'All {count} events deleted successfully'})
        except Exception as e:
            logger.error(f"Error deleting all events: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    return app 
