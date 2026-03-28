"""
Advanced NUT Configuration module.
This package provides functionality for:
- Reading NUT configuration files
- Updating NUT configuration files
- Restarting NUT services
"""

from .advanced import (
    read_nut_config_file,
    write_nut_config_file,
    restart_nut_services,
    get_available_nut_files,
    get_nut_file_documentation
)

from .routes_advanced import register_routes
from .api_advanced import register_api_routes

__all__ = [
    'register_routes',
    'register_api_routes',
    'read_nut_config_file',
    'write_nut_config_file',
    'restart_nut_services',
    'get_available_nut_files',
    'get_nut_file_documentation'
] 