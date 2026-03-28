"""
API routes for NUT daemon services.

This module provides API endpoints for managing NUT services:
- Start NUT services
- Stop NUT services
- Restart NUT services
- Check NUT services status
- Get NUT service logs
"""

from flask import Blueprint, jsonify, request
from core.auth import require_admin
from core.logger import system_logger as logger

from .nut_daemon import (
    start_nut_services,
    stop_nut_services,
    restart_nut_services,
    check_all_services_status,
    get_service_logs,
    NUTStartupError,
    NUTShutdownError,
    NUTConfigError
)

# Create blueprint
api_nut = Blueprint('api_nut', __name__, url_prefix='/api/nut')

@api_nut.route('/status', methods=['GET'])
@require_admin
def get_nut_status():
    """Get status of all NUT services"""
    try:
        status = check_all_services_status()
        
        # Calculate overall status
        all_running = all(status.values())
        any_running = any(status.values())
        
        return jsonify({
            'success': True,
            'status': status,
            'all_running': all_running,
            'any_running': any_running
        })
    except Exception as e:
        logger.error(f"Error getting NUT services status: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Error getting NUT services status: {str(e)}"
        }), 500

@api_nut.route('/start', methods=['POST'])
@require_admin
def start_services():
    """Start all NUT services"""
    try:
        wait_time = request.json.get('wait_time', 2) if request.json else 2
        
        results = start_nut_services(wait_time)
        return jsonify({
            'success': True,
            'results': results
        })
    except NUTConfigError as e:
        logger.error(f"NUT configuration error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e),
            'error_type': 'config_error'
        }), 400
    except NUTStartupError as e:
        logger.error(f"NUT startup error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e),
            'error_type': 'startup_error'
        }), 500
    except Exception as e:
        logger.error(f"Error starting NUT services: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Error starting NUT services: {str(e)}"
        }), 500

@api_nut.route('/stop', methods=['POST'])
@require_admin
def stop_services():
    """Stop all NUT services"""
    try:
        wait_time = request.json.get('wait_time', 2) if request.json else 2
        
        results = stop_nut_services(wait_time)
        return jsonify({
            'success': True,
            'results': results
        })
    except NUTShutdownError as e:
        logger.error(f"NUT shutdown error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e),
            'error_type': 'shutdown_error'
        }), 500
    except Exception as e:
        logger.error(f"Error stopping NUT services: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Error stopping NUT services: {str(e)}"
        }), 500

@api_nut.route('/restart', methods=['POST'])
@require_admin
def restart_services():
    """Restart all NUT services"""
    try:
        wait_time = request.json.get('wait_time', 2) if request.json else 2
        
        results = restart_nut_services(wait_time)
        return jsonify({
            'success': results.get('success', False),
            'results': results
        })
    except Exception as e:
        logger.error(f"Error restarting NUT services: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Error restarting NUT services: {str(e)}"
        }), 500

@api_nut.route('/logs/<service_name>', methods=['GET'])
@require_admin
def get_logs(service_name):
    """Get logs for a specific NUT service"""
    try:
        lines = request.args.get('lines', 50, type=int)
        logs = get_service_logs(service_name, lines)
        
        return jsonify({
            'success': True,
            'service': service_name,
            'logs': logs
        })
    except Exception as e:
        logger.error(f"Error getting logs for {service_name}: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Error getting logs: {str(e)}"
        }), 500

def register_api_routes(app):
    """
    Register NUT daemon API routes with the application.
    
    Args:
        app: Flask application instance
    """
    if api_nut.name not in app.blueprints:
        app.register_blueprint(api_nut)
        logger.info("✅ Registered NUT daemon API routes")
    return app 
