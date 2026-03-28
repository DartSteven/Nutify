"""Routes.Py Module.

Implements core runtime logic and helpers used by this feature.
"""

from flask import redirect, url_for
from .energy.routes_energy import register_routes as register_energy_routes
from .battery.routes_battery import register_routes as register_battery_routes
from .power.routes_power import register_routes as register_power_routes
from .voltage.routes_voltage import register_routes as register_voltage_routes
from .voltage.api_voltage import register_api_routes as register_voltage_api_routes
from .upscmd.routes_upscmd import register_routes as register_upscmd_routes
from .upsrw.routes_upsrw import register_routes as register_upsrw_routes
from .advanced.routes_advanced import register_routes as register_advanced_routes
from .options import api_options, api_options_compat, routes_options
from core.logger import web_logger as logger
from core.auth import require_permission
from core.react_frontend import serve_react_index
from core.events import routes_events
from core.infoapi import routes_info
from core.infoups.routes_infoups import routes_infoups
logger.info("📡 Initializing routes")

def register_routes(app):
    """Registers all web routes for the application"""
    
    register_energy_routes(app)
    register_battery_routes(app)
    register_power_routes(app)
    register_voltage_routes(app)
    register_voltage_api_routes(app)
    register_upscmd_routes(app)
    register_upsrw_routes(app)
    register_advanced_routes(app)
    
    # Register options blueprints
    app.register_blueprint(api_options)
    app.register_blueprint(api_options_compat)  # Register compatibility routes
    app.register_blueprint(routes_options)
    
    # Register events blueprint
    app.register_blueprint(routes_events)
    
    # Register infoapi blueprint for API documentation
    app.register_blueprint(routes_info)
    app.register_blueprint(routes_infoups)
    
    @app.route('/')
    @require_permission('home')
    def index():
        """Main dashboard view - served by React SPA."""
        try:
            # Check authentication first
            from core.auth import is_login_configured, is_authenticated
            
            if not is_login_configured():
                return redirect(url_for('auth.setup'))
            if not is_authenticated():
                return redirect(url_for('auth.login'))
            return serve_react_index()
        except Exception as e:
            logger.exception(f"Error in index route: {str(e)}")
            return serve_react_index()
    
    @app.route('/websocket-test')
    def websocket_test():
        """Render the WebSocket test page - served by React SPA."""
        try:
            # Check authentication first
            from core.auth import is_login_configured, is_authenticated
            
            if not is_login_configured():
                return redirect(url_for('auth.setup'))
            if not is_authenticated():
                return redirect(url_for('auth.login'))
            return serve_react_index()
        except Exception as e:
            logger.warning(f"Error getting UPS data for websocket test page: {str(e)}")
            return serve_react_index()

    return app
