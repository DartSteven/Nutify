#!/usr/bin/env python3
"""
UPS Information Routes

This module provides routes for displaying detailed UPS information.
"""

from core.react_frontend import serve_react_index
from . import routes_infoups
from core.auth import require_permission

def register_routes():
    """
    Register routes for the UPS information module
    """
    # No additional initialization required
    pass

@routes_infoups.route('/ups_info')
@require_permission('info')
def ups_info_page():
    """Render the UPS info page with React SPA."""
    return serve_react_index()
