"""Socket Module.

Implements core runtime logic and helpers used by this feature.
"""

from flask_socketio import emit
from flask import request, current_app, session
from .socket_manager import socketio
from ..db.ups import db, data_lock
from ..logger import socket_logger as logger
from ..auth import is_auth_disabled
import json
from datetime import datetime
logger.info("🌐 Initializing socket_events")

# Initialize UPSCommand from ModelClasses
UPSCommand = None

def _init_models_if_needed():
    """Initialize UPSCommand model from ModelClasses if needed"""
    global UPSCommand
    if UPSCommand is None:
        # Check if we can get the model from the db.ModelClasses namespace
        if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'UPSCommand'):
            UPSCommand = db.ModelClasses.UPSCommand
            logger.debug("📚 UPSCommand model initialized from db.ModelClasses")
        else:
            # Fall back to using core.db.models if ModelClasses isn't initialized
            from core.db.models import init_models
            # Use CACHE_TIMEZONE from Flask app
            init_models(db, lambda: current_app.CACHE_TIMEZONE)
            
            # Try again to get the model
            if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'UPSCommand'):
                UPSCommand = db.ModelClasses.UPSCommand
                logger.debug("📚 UPSCommand model initialized after init_models")
            else:
                logger.error("❌ Failed to initialize UPSCommand model")

@socketio.on('connect')
def handle_connect():
    """Handles the connection of a client"""
    if not is_auth_disabled() and not session.get('user_id'):
        logger.warning(f'🟠 Rejected unauthenticated socket client - SID: {request.sid}')
        return False
    logger.info(f'🟢 Client connected - SID: {request.sid}')
    emit('connect_response', {'status': 'connected', 'sid': request.sid})
    # Send immediately the current data
    emit_command_stats()
    emit_command_logs()

@socketio.on('request_initial_data')
def handle_initial_data():
    """Handles the request for initial data"""
    emit_command_stats()
    emit_command_logs()

@socketio.on('disconnect')
def handle_disconnect():
    """Handles the disconnection of a client"""
    logger.info(f'🔴 Client disconnected - SID: {request.sid}')

def emit_command_stats():
    """Emits the command statistics"""
    try:
        # Ensure UPSCommand model is initialized
        _init_models_if_needed()
        
        with data_lock:
            # Calculate the statistics
            total_commands = UPSCommand.query.count()
            successful_commands = UPSCommand.query.filter_by(success=True).count()
            failed_commands = UPSCommand.query.filter_by(success=False).count()
            
            stats = {
                'total': total_commands,
                'successful': successful_commands,
                'failed': failed_commands
            }
            
            # DEBUG logging for troubleshooting
            logger.debug(f"Emitting stats: {stats}")
            
            # Emit the event with the statistics
            socketio.emit('command_stats_update', stats)
            
    except Exception as e:
        logger.error(f"Error in the emission of the statistics: {str(e)}")
        logger.error(f"Error details:", exc_info=True)

def emit_command_logs():
    """Emits the recent command logs"""
    try:
        # Ensure UPSCommand model is initialized
        _init_models_if_needed()
        
        with data_lock:
            # Retrieve the last 10 commands
            recent_commands = UPSCommand.query.order_by(
                UPSCommand.timestamp.desc()
            ).limit(10).all()
            
            # Convert to a format the frontend expects
            logs = []
            for cmd in recent_commands:
                logs.append({
                    'command': cmd.command,
                    'success': cmd.success,
                    'output': cmd.output,
                    'timestamp': cmd.timestamp.isoformat() if cmd.timestamp else None
                })
            
            # DEBUG logging for troubleshooting
            logger.debug(f"Emitting logs: {logs}")
            
            # Emit the event with the logs
            socketio.emit('command_logs_update', logs)
            
    except Exception as e:
        logger.error(f"Error in the emission of the logs: {str(e)}")
        logger.error(f"Error details:", exc_info=True)

def notify_command_executed(command, success, output):
    """
    Notify the execution of a new command
    Call after each command execution
    """
    try:
        with current_app.app_context():
            # Emit the event of the new command
            socketio.emit('command_executed', {
                'command': command,
                'success': success,
                'output': output,
                'timestamp': datetime.now(current_app.CACHE_TIMEZONE).isoformat()
            })
            
            # Update statistics and logs
            emit_command_stats()
            emit_command_logs()
            
    except Exception as e:
        logger.error(f"Error in the notification of the command: {str(e)}")

def notify_variable_update(data):
    """Notify the update of a variable"""
    try:
        socketio.emit('variable_update', data)
        emit_updated_history()
    except Exception as e:
        logger.error(f"Error in the notification of the variable: {str(e)}")

def emit_updated_history():
    """Emits the updated variable history"""
    try:
        from ..upsrw.upsrw import get_variable_history
        history = get_variable_history()
        socketio.emit('history_update', history)
    except Exception as e:
        logger.error(f"Error emitting updated history: {str(e)}")
        socketio.emit('history_update', []) 
