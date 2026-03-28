"""Energy Package.

Defines package exports and module-level initialization helpers.
"""

from .energy import (
    get_energy_data,
    calculate_energy_stats,
    get_single_day_data,
    format_realtime_data,
    get_energy_rate,
    calculate_cost_distribution,
    get_cost_trend_for_range,
    format_cost_series,
    get_period_energy_data
)

from .routes_energy import register_routes
from .api_energy import register_api_routes

__all__ = [
    'register_routes',
    'register_api_routes',
    'get_energy_data',
    'calculate_energy_stats',
    'get_single_day_data',
    'format_realtime_data',
    'get_energy_rate',
    'calculate_cost_distribution',
    'get_cost_trend_for_range',
    'format_cost_series',
    'get_period_energy_data'
] 