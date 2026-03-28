"""Socket Package.

Defines package exports and module-level initialization helpers.
"""

from .socket_events import (
    emit_command_stats, 
    emit_command_logs, 
    notify_command_executed, 
    notify_variable_update,
    emit_updated_history
)
from .socket_manager import socketio, init_socketio

__all__ = [
    'emit_command_stats',
    'emit_command_logs',
    'notify_command_executed',
    'notify_variable_update',
    'emit_updated_history',
    'socketio',
    'init_socketio'
] 