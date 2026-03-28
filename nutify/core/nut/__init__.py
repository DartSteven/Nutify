"""
NUT Daemon Module.

This package provides functionality for managing NUT services:
- Starting NUT services
- Stopping NUT services
- Restarting NUT services
- Checking NUT service status
- Getting NUT service logs
"""

from .nut_daemon import (
    start_nut_services,
    stop_nut_services,
    restart_nut_services,
    check_service_status,
    check_all_services_status,
    get_service_logs,
    NUTDaemonError,
    NUTStartupError,
    NUTShutdownError,
    NUTConfigError
)

from .api_nut import register_api_routes, api_nut

# Additional exports for command constants from settings
from core.settings import (
    NUT_START_DRIVER_CMD,
    NUT_START_SERVER_CMD,
    NUT_START_MONITOR_CMD,
    NUT_STOP_DRIVER_CMD,
    NUT_STOP_SERVER_CMD,
    NUT_STOP_MONITOR_CMD,
)

__all__ = [
    'start_nut_services',
    'stop_nut_services',
    'restart_nut_services',
    'check_service_status',
    'check_all_services_status',
    'get_service_logs',
    'NUTDaemonError',
    'NUTStartupError',
    'NUTShutdownError',
    'NUTConfigError',
    'register_api_routes',
    'api_nut',
    # Additional constants
    'NUT_START_DRIVER_CMD',
    'NUT_START_SERVER_CMD',
    'NUT_START_MONITOR_CMD',
    'NUT_STOP_DRIVER_CMD',
    'NUT_STOP_SERVER_CMD',
    'NUT_STOP_MONITOR_CMD',
] 