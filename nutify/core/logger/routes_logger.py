"""Logger Routes Module.

Registers HTTP routes and page handlers for this feature domain.
"""

from flask import Blueprint

from core.react_frontend import serve_react_index

routes_logger = Blueprint('routes_logger', __name__)


@routes_logger.route('/logs')
def logs():
    """Serve logs page via React SPA."""
    return serve_react_index()


@routes_logger.route('/logs/view')
def logs_view():
    """Serve logs view page via React SPA."""
    return serve_react_index()
