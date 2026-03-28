"""
NUT Configuration API endpoints.

This module provides API routes for NUT configuration management.
"""

from flask import Blueprint, jsonify, current_app
from core.auth import is_admin, is_auth_disabled, is_authenticated, is_login_configured
from core.logger import system_logger as logger
from core.settings import UPSD_BIN, UPSDRVCTL_BIN, NUT_STOP_SERVER_CMD, NUT_STOP_DRIVER_CMD
import os
import sys
import time
import threading
import subprocess

# Create blueprint for NUT config API
api_nut_config = Blueprint('api_nut_config', __name__, url_prefix='/nut_config')

@api_nut_config.route('/api/restart', methods=['POST'])
def restart_application():
    """
    Restart the application.
    This endpoint works in both setup and normal modes.
    First stops NUT services, then restarts the application.
    """
    try:
        if (not is_auth_disabled()) and is_login_configured():
            if not is_authenticated():
                return jsonify(success=False, message="Authentication required"), 401
            if not is_admin():
                return jsonify(success=False, message="Admin privileges required"), 403

        logger.info("Stopping NUT services before restart...")
        
        # Stop NUT services in the correct order
        try:
            # Parse the NUT_STOP_SERVER_CMD to get the arguments
            stop_server_cmd_parts = NUT_STOP_SERVER_CMD.split()
            # Make sure we use the correct binary path with arguments
            if len(stop_server_cmd_parts) > 1:
                stop_server_args = stop_server_cmd_parts[1:]
                subprocess.run([UPSD_BIN] + stop_server_args, stderr=subprocess.PIPE)
            else:
                subprocess.run([UPSD_BIN, "-c", "stop"], stderr=subprocess.PIPE)
            
            # Parse the NUT_STOP_DRIVER_CMD to get the arguments
            stop_driver_cmd_parts = NUT_STOP_DRIVER_CMD.split()
            # Make sure we use the correct binary path with arguments
            if len(stop_driver_cmd_parts) > 1:
                stop_driver_args = stop_driver_cmd_parts[1:]
                subprocess.run([UPSDRVCTL_BIN] + stop_driver_args, stderr=subprocess.PIPE)
            else:
                subprocess.run([UPSDRVCTL_BIN, "stop"], stderr=subprocess.PIPE)
                
            logger.info("Successfully stopped NUT services")
        except Exception as e:
            logger.warning(f"Error stopping NUT services: {str(e)}")
        
        logger.info("Restarting application...")
        # Return a success response before restarting
        response = jsonify(success=True, message="Application is restarting...")
        
        # Restart in a separate thread to allow response to be sent
        def restart_thread():
            # Wait a moment for response to be delivered
            time.sleep(1)
            try:
                # The following will replace the current process with a new one
                os.execv(sys.executable, [sys.executable] + sys.argv)
            except Exception as e:
                logger.error(f"Error during restart: {str(e)}")
                
        threading.Thread(target=restart_thread).start()
        return response
        
    except Exception as e:
        logger.error(f"Error initiating restart: {str(e)}")
        return jsonify(success=False, message=str(e)), 500

def register_api_routes(app):
    """
    Register NUT configuration API routes with the application.
    
    Args:
        app: Flask application instance
    """
    if api_nut_config.name not in app.blueprints:
        app.register_blueprint(api_nut_config)
        logger.info("Registered NUT configuration API routes") 
