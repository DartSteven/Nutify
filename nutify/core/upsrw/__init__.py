"""Upsrw Package.

Defines package exports and module-level initialization helpers.
"""

from .upsrw import (
    get_ups_variables,
    set_ups_variable,
    get_variable_history,
    clear_variable_history,
    UPSVariable
)

from .routes_upsrw import register_routes
from .api_upsrw import register_api_routes

__all__ = [
    'register_routes',
    'register_api_routes',
    'get_ups_variables',
    'set_ups_variable',
    'get_variable_history',
    'clear_variable_history',
    'UPSVariable'
] 