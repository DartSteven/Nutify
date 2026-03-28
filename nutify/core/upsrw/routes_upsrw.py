"""
UPS Read/Write Routes.
"""

from flask import Blueprint
from core.auth import require_permission
from core.react_frontend import serve_react_index

routes_upsrw = Blueprint('routes_upsrw', __name__)

def register_routes(app):
    """Register UPS read/write routes with the Flask application."""
    
    @app.route('/upsrw')
    @require_permission('settings')
    def upsrw_page():
        """Render the UPS read/write page with React SPA."""
        return serve_react_index()
    
    @app.route('/upsrw/preview')
    @require_permission('settings')
    def upsrw_preview():
        """Render the UPS read/write preview page with React SPA."""
        return serve_react_index()
    
    return app 
