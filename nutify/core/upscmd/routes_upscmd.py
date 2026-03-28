"""
UPS Commands Routes.
"""

from flask import Blueprint
from core.auth import require_permission
from core.react_frontend import serve_react_index

routes_upscmd = Blueprint('routes_upscmd', __name__)

def register_routes(app):
    """Register all HTML routes for the UPS commands section"""
    
    @app.route('/upscmd')
    @require_permission('command')
    def upscmd_page():
        """Page for running commands directly on the UPS."""
        return serve_react_index()
    
    return app 
