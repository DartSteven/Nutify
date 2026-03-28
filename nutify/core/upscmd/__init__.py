"""Upscmd Package.

Defines package exports and module-level initialization helpers.
"""

from .upscmd import (
    get_ups_commands,
    execute_command,
    get_command_stats
)

from .routes_upscmd import register_routes
from .api_upscmd import register_api_routes

__all__ = [
    'register_routes',
    'register_api_routes',
    'get_ups_commands',
    'execute_command',
    'get_command_stats'
] 