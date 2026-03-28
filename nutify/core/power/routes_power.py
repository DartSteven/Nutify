"""Power Routes Module.

Registers HTTP routes and page handlers for this feature domain.
"""

from core.logger import power_logger as logger
from .api_power import register_api_routes

logger.info("💪 Initializing power routes")

def register_routes(app):
    """
    Register all power-related routes.
    
    This function is called from core/routes.py and serves as
    an entry point for registering all power-related routes.
    
    Args:
        app: Flask application instance
    
    Returns:
        The Flask application with power routes registered
    """
    app = register_api_routes(app)
    return app 