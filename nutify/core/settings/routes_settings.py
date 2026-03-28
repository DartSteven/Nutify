"""Settings Routes Module.

Registers HTTP routes and page handlers for this feature domain.
"""

from flask import Blueprint, redirect, url_for

from core.auth import require_permission
from core.react_frontend import serve_react_index


routes_settings = Blueprint('routes_settings', __name__)

@routes_settings.route('/settings')
@routes_settings.route('/options')
@require_permission('options')
def settings_page():
    """Serve settings page via React SPA."""
    return serve_react_index()


@routes_settings.route('/settings/system')
@require_permission('options')
def system_settings():
    return redirect(url_for('routes_settings.settings_page', view='system'))


@routes_settings.route('/settings/advanced')
@require_permission('options')
def advanced_settings():
    return redirect(url_for('routes_settings.settings_page', view='system'))


@routes_settings.route('/settings/backup')
@require_permission('options')
def backup_settings():
    return redirect(url_for('routes_settings.settings_page', view='system'))
