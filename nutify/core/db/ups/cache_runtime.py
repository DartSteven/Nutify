"""Runtime helpers for UPS cache persistence and websocket handlers."""

from __future__ import annotations

from datetime import datetime

import pytz

from core.db.ups.data import get_ups_data


def save_ups_data(db, ups_dynamic_data_model, ups_data_cache, logger):
    """Collect UPS data, push it to cache, and persist aligned averages."""
    try:
        from core.db.internal_checker import is_ups_connected

        if not is_ups_connected():
            error_msg = "UPS connection unavailable, skipping data collection"
            logger.warning(f"⚠️ {error_msg}")
            return False, error_msg

        now_utc = datetime.now(pytz.UTC)

        try:
            if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'VariableConfig'):
                model_class = db.ModelClasses.VariableConfig
            else:
                from core.db.ups import VariableConfig
                model_class = VariableConfig

            query = model_class.query
            if hasattr(model_class, 'target_id'):
                query = query.filter(model_class.target_id.is_(None))
            config = query.order_by(model_class.id.desc()).first()
            polling_interval = config.polling_interval if config else 1
        except Exception as exc:
            logger.error(f"Error getting polling interval: {exc}. Using default of 1 second.")
            polling_interval = 1

        if polling_interval > 1:
            cache_seconds = 60
            target_buffer_size = max(5, int(cache_seconds / polling_interval))
            if ups_data_cache.size != target_buffer_size:
                logger.info(
                    "Adjusting cache buffer size from %s to %s based on polling interval of %s seconds",
                    ups_data_cache.size,
                    target_buffer_size,
                    polling_interval,
                )
                ups_data_cache.size = target_buffer_size

        data = get_ups_data()
        data_dict = vars(data)

        logger.debug(f"📥 Buffer status before add: {len(ups_data_cache.data)}")
        ups_data_cache.add(now_utc, data_dict)
        logger.debug(f"📥 Buffer status after add: {len(ups_data_cache.data)}")

        success = ups_data_cache.calculate_and_save_averages(db, ups_dynamic_data_model, now_utc)
        if success:
            logger.info("💾 Successfully saved aligned data to database")
        return True, None
    except Exception as exc:
        error_msg = f"Error saving data: {exc}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg


def register_cache_socket_handlers(websocket, ups_data_cache, logger):
    """Register cache websocket events for connect, refresh, and disconnect."""

    @websocket.on('connect')
    def handle_websocket_connect():
        from flask import request, session
        from core.auth import is_auth_disabled

        if not is_auth_disabled() and not session.get('user_id'):
            logger.warning("Rejected unauthenticated cache websocket connection - SID: %s", request.sid)
            return False
        logger.info(f"🟢 WebSocket client connected - SID: {request.sid}")
        latest_data = ups_data_cache.get_latest_cache_data()
        if latest_data:
            websocket.emit('cache_update', latest_data, room=request.sid)

    @websocket.on('request_cache_data')
    def handle_request_cache_data():
        from flask import request

        logger.debug(f"📤 Client {request.sid} requested cache data")
        latest_data = ups_data_cache.get_latest_cache_data()
        websocket.emit('cache_update', latest_data, room=request.sid)

    @websocket.on('disconnect')
    def handle_websocket_disconnect():
        from flask import request

        logger.info(f"🔴 WebSocket client disconnected - SID: {request.sid}")


def init_websocket(websocket, app, logger):
    """Initialize cache websocket transport for the Flask app."""
    logger.info("🔌 Initializing UPS Cache WebSocket")
    websocket.init_app(app, async_mode='eventlet')
    return websocket
