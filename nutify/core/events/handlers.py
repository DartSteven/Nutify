"""
UPS Event Handlers.
This module provides functions for handling UPS events.
Extracted from db_module.py.
"""

import pytz
from datetime import datetime
from core.logger import database_logger as logger
from flask import current_app

# Will be set during initialization
db = None
UPSEvent = None

def init_handlers(db_instance, event_model, timezone_getter):
    """
    Initialize the event handlers with required dependencies.
    
    Args:
        db_instance: SQLAlchemy database instance
        event_model: UPSEvent model class
        timezone_getter: Function to get the configured timezone (not used anymore, kept for compatibility)
    """
    global db, UPSEvent
    db = db_instance
    UPSEvent = event_model

def get_event_type(event_message):
    """
    Determine the event type from the upsmon message.
    Handles messages in the format "UPS ups@localhost: <event>"
    """
    event_message = event_message.lower()
    
    # Remove the prefix "UPS ups@localhost"
    if 'ups ' in event_message:
        event_message = event_message.split('ups ')[1]
    if '@localhost' in event_message:
        event_message = event_message.split('@localhost')[1]
    if ': ' in event_message:
        event_message = event_message.split(': ')[1]
        
    event_message = event_message.strip()
    
    # Standard UPS states
    if 'on line power' in event_message:
        return 'ONLINE'
    elif 'on battery' in event_message:
        return 'ONBATT'
    elif 'low battery' in event_message:
        return 'LOWBATT'
    elif 'battery needs replacement' in event_message:
        return 'REPLBATT'
    elif 'communication lost' in event_message:
        return 'COMMFAULT'
    elif 'shutdown in progress' in event_message:
        return 'SHUTDOWN'
    elif 'ups overloaded' in event_message:
        return 'OVERLOAD'
    elif 'battery charging' in event_message:
        return 'CHARGING'
    elif 'battery discharging' in event_message:
        return 'DISCHARGING'
    elif 'bypass active' in event_message or 'on bypass' in event_message:
        return 'BYPASS'
    elif 'test in progress' in event_message or 'calibration in progress' in event_message:
        return 'CAL'  # Calibration/Test
    elif 'ups failed' in event_message:
        return 'FAULT'
    elif 'temperature high' in event_message:
        return 'OVERHEAT'
    elif 'input voltage high' in event_message:
        return 'OVERVOLTAGE'
    elif 'input voltage low' in event_message:
        return 'UNDERVOLTAGE'
    elif 'ups off' in event_message or 'off-line' in event_message:
        return 'OFF'
    elif 'ups initialized' in event_message or 'startup' in event_message:
        return 'STARTUP'
    elif 'trim' in event_message:
        return 'TRIM'
    elif 'boost' in event_message:
        return 'BOOST'
    elif 'no battery' in event_message or 'battery missing' in event_message:
        return 'NOBATT'
    elif 'data old' in event_message or 'stale data' in event_message:
        return 'DATAOLD'
    
    # If no specific match is found, return UNKNOWN
    logger.warning(f"Unknown UPS event type: {event_message}")
    return 'UNKNOWN'

def handle_ups_event(event_data):
    """
    Handle a UPS event by storing it in the database and emitting a socket event.
    
    Args:
        event_data: Dictionary containing event data
        
    Returns:
        tuple: (success, message, event_data)
    """
    global UPSEvent, db
    try:
        now = datetime.now(pytz.UTC)
        
        # Make sure UPSEvent is initialized
        if UPSEvent is None:
            from core.db.models import init_models
            from flask import current_app
            init_models(db, lambda: current_app.CACHE_TIMEZONE)
            UPSEvent = db.ModelClasses.UPSEvent
        
        event = UPSEvent(
            timestamp_utc=now,
            timestamp_utc_begin=now,
            ups_name=event_data.get('ups'),
            event_type=event_data.get('event'),
            event_message=str(event_data),
            source_ip=None,
            acknowledged=False
        )
        
        db.session.add(event)
        db.session.commit()

        # Send the event via WebSocket if possible
        try:
            from flask import current_app
            if hasattr(current_app, 'socketio'):
                current_app.socketio.emit('ups_event', {
                    'event_type': event_data['event'],
                    'ups_data': event_data
                })
        except Exception as ws_error:
            logger.warning(f"Could not emit WebSocket event: {ws_error}")

        return True, "Event handled successfully", event_data
    except Exception as e:
        logger.error(f"Error handling UPS event: {e}", exc_info=True)
        return False, str(e), None 