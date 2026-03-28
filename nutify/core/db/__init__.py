"""
Database Module.
This module provides functions and classes for interacting with the database.
"""

from core.db.ups import db

# Import the logger
from core.logger import database_logger as logger

# Import submodules
from .model_classes import init_model_classes, register_models_for_global_access
from .initializer import init_database
from .integrity import check_database_integrity
from .models import init_models
from .nut_parser import get_ups_connection_params, get_nut_configuration, refresh_config
from .internal_checker import (
    connection_monitor, 
    check_ups_connection, 
    is_ups_connected, 
    start_connection_monitoring, 
    stop_connection_monitoring,
    get_ups_connection_status
)

# Export the public API
__all__ = [
    'db',
    'init_model_classes',
    'register_models_for_global_access',
    'init_database',
    'check_database_integrity',
    'init_models',
    'get_ups_connection_params',
    'get_nut_configuration',
    'refresh_config',
    'connection_monitor',
    'check_ups_connection',
    'is_ups_connected',
    'start_connection_monitoring',
    'stop_connection_monitoring',
    'get_ups_connection_status'
] 
