"""Web routes for Multi-NUT pages."""

from __future__ import annotations

from flask import Blueprint, redirect, url_for

from core.auth import require_permission
from core.react_frontend import serve_react_index
from core.multi_nut.storage import get_monitoring_profile


routes_multi_nut = Blueprint('routes_multi_nut', __name__)



@routes_multi_nut.route('/multi-ups')
@require_permission('home')
def multi_ups_page():
    """Render the Multi-UPS monitoring page with React SPA."""
    monitoring_profile = get_monitoring_profile()

    if monitoring_profile != 'multi':
        return redirect(url_for('index'))
    return serve_react_index()



def register_routes(app):
    """Register Multi-NUT page routes."""
    if routes_multi_nut.name not in app.blueprints:
        app.register_blueprint(routes_multi_nut)
