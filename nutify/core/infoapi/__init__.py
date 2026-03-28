"""
Information API module.

This module provides API endpoints and routes for retrieving UPS data and table information.
"""

from .api_info import register_api_routes
from .routes_info import routes_info

__all__ = ['register_api_routes', 'routes_info'] 