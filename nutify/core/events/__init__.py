"""
UPS Events Package.
This package contains event handling functionality extracted from db_module.py.
"""

from core.events.handlers import get_event_type, handle_ups_event
from core.events.routes_events import routes_events
from core.events.api_events import register_api_routes

__all__ = [
    'get_event_type',
    'handle_ups_event',
    'routes_events',
    'register_api_routes',
] 