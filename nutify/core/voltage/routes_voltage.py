"""Voltage Routes Module.

Registers HTTP routes and page handlers for this feature domain.
"""

from core.auth import require_permission
from core.react_frontend import serve_react_index


def register_routes(app):
    """Register voltage page route served by the React SPA."""

    @app.route('/voltage')
    @require_permission('voltage')
    def voltage_page():
        return serve_react_index()

    return app
