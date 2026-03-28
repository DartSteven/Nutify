"""Routes for UPSMON-related web views."""

from flask import Blueprint
from .upsmon_client import logger
from core.react_frontend import serve_react_index

routes_upsmon = Blueprint('routes_upsmon', __name__)

@routes_upsmon.route('/events/view')
def events_view():
    """Render the events view page with React SPA."""
    logger.info("Accessing events view page")
    return serve_react_index()
