"""Multi-NUT module exports."""

from .api_multi_nut import api_multi_nut, register_api_routes as register_multi_nut_api_routes
from .api_notifycmd_script import api_notifycmd_script, register_api_routes as register_notifycmd_script_api_routes
from .polling import get_multi_nut_runtime_state, get_multi_polling_sleep_seconds, poll_multi_targets_once
from .routes_multi_nut import register_routes, routes_multi_nut
from .storage import (
    bootstrap_primary_target,
    enabled_targets_count,
    has_multiple_enabled_targets,
    list_targets,
)


def register_api_routes(app):
    """Register Multi-NUT API blueprints."""
    register_multi_nut_api_routes(app)
    register_notifycmd_script_api_routes(app)
    return app


__all__ = [
    'api_multi_nut',
    'api_notifycmd_script',
    'bootstrap_primary_target',
    'enabled_targets_count',
    'get_multi_nut_runtime_state',
    'get_multi_polling_sleep_seconds',
    'has_multiple_enabled_targets',
    'list_targets',
    'poll_multi_targets_once',
    'register_api_routes',
    'register_routes',
    'routes_multi_nut',
]
