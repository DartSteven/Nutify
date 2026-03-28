"""
Battery module for UPS battery data management and analysis.
This package provides functionality for:
- Retrieving battery metrics
- Calculating battery statistics
- Analyzing battery health
- Formatting battery data for display
"""

from .battery import (
    get_available_battery_metrics,
    get_battery_stats,
    get_battery_history,
    calculate_battery_health,
    format_ups_status,
    format_battery_type,
    calculate_activity_level
)

from .routes_battery import register_routes
from .api_battery import register_api_routes

__all__ = [
    'get_available_battery_metrics',
    'get_battery_stats',
    'get_battery_history',
    'calculate_battery_health',
    'format_ups_status',
    'format_battery_type',
    'calculate_activity_level',
    'register_routes',
    'register_api_routes'
] 