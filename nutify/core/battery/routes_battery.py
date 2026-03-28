"""Battery Routes Module.

Registers HTTP routes and page handlers for this feature domain.
"""

from core.auth import require_permission
from core.react_frontend import serve_react_index


def register_routes(app):
    """Register battery page route served by the React SPA."""

    @app.route('/battery')
    @require_permission('battery')
    def battery_page():
        return serve_react_index()

    return app
