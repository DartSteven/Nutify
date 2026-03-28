"""Upsmon Package.

Defines package exports and module-level initialization helpers.
"""

from .upsmon_client import (
    handle_nut_event,
    get_event_history,
    get_events_table,
    acknowledge_event,
    logger
)

from .api_upsmon import api_upsmon
from .routes_upsmon import routes_upsmon

__all__ = [
    'handle_nut_event',
    'get_event_history',
    'get_events_table',
    'acknowledge_event',
    'logger',
    'api_upsmon',
    'routes_upsmon'
] 