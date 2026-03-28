"""Web route for API documentation page served by React."""

from flask import Blueprint

from core.auth import require_auth
from core.react_frontend import serve_react_index


routes_info = Blueprint('routes_info', __name__)


@routes_info.route('/api')
@require_auth
def api_page():
    return serve_react_index()
