"""Options Routes Module.

Registers HTTP routes and page handlers for this feature domain.
"""

from flask import Blueprint, redirect, request, url_for

from core.auth import require_permission
from core.react_frontend import serve_react_index


routes_options = Blueprint('routes_options', __name__, url_prefix='/options')

VALID_SETTINGS_VIEWS = {'target', 'system'}


def _get_settings_view() -> str:
    requested_view = (request.args.get('view') or 'target').strip().lower()
    if requested_view not in VALID_SETTINGS_VIEWS:
        return 'target'
    return requested_view


@routes_options.route('/')
@require_permission('options')
def options_dashboard():
    """Serve settings/options via React SPA."""
    return serve_react_index()


@routes_options.route('/settings')
@require_permission('options')
def settings_redirect():
    """Keep legacy /options/settings URL compatible."""
    return redirect(url_for('routes_options.options_dashboard', view=_get_settings_view()))


@routes_options.route('/database')
@require_permission('options')
def database_options():
    """Keep legacy /options/database URL compatible."""
    return serve_react_index()


@routes_options.route('/logs')
@require_permission('options')
def logs_page():
    """Keep legacy /options/logs URL compatible."""
    return serve_react_index()


@routes_options.route('/scripts')
@require_permission('options')
def scripts_page():
    """Serve target-scoped script automation settings."""
    return serve_react_index()


@routes_options.route('/system')
@require_permission('options')
def system_info_page():
    """Keep legacy /options/system URL compatible."""
    return serve_react_index()
