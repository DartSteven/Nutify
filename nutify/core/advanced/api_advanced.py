"""
API routes for advanced NUT configuration management.
"""

from flask import jsonify, request
from core.auth import require_admin
from core.logger import system_logger as logger

from .advanced import (
    read_nut_config_file,
    write_nut_config_file,
    restart_nut_services,
    get_available_nut_files,
    get_nut_file_documentation
)

def register_api_routes(app):
    """Register all API routes for the advanced NUT configuration section"""
    
    @app.route('/api/advanced/nut/files', methods=['GET'])
    @require_admin
    def get_nut_files():
        """Get list of available NUT configuration files"""
        try:
            files = get_available_nut_files()
            return jsonify({
                "success": True,
                "files": files
            })
        except Exception as e:
            logger.error(f"Error getting NUT configuration files: {str(e)}")
            return jsonify({
                "success": False,
                "message": f"Error getting NUT configuration files: {str(e)}"
            }), 500
    
    @app.route('/api/advanced/nut/config/<filename>', methods=['GET'])
    @require_admin
    def get_nut_config(filename):
        """Get content of a NUT configuration file"""
        try:
            config = read_nut_config_file(filename)
            if config.get("success", False):
                return jsonify({
                    "success": True,
                    "config": config
                })
            else:
                return jsonify({
                    "success": False,
                    "message": config.get("message", "Unknown error")
                }), 404
        except Exception as e:
            logger.error(f"Error reading NUT configuration file {filename}: {str(e)}")
            return jsonify({
                "success": False,
                "message": f"Error reading configuration file: {str(e)}"
            }), 500
    
    @app.route('/api/advanced/nut/config/<filename>', methods=['POST'])
    @require_admin
    def update_nut_config(filename):
        """Update a NUT configuration file"""
        try:
            data = request.json
            if not data or "content" not in data:
                return jsonify({
                    "success": False,
                    "message": "Missing required parameter: content"
                }), 400
            
            result = write_nut_config_file(filename, data["content"])
            if result.get("success", False):
                return jsonify({
                    "success": True,
                    "message": result.get("message", "Configuration updated successfully")
                })
            else:
                return jsonify({
                    "success": False,
                    "message": result.get("message", "Unknown error")
                }), 500
        except Exception as e:
            logger.error(f"Error updating NUT configuration file {filename}: {str(e)}")
            return jsonify({
                "success": False,
                "message": f"Error updating configuration file: {str(e)}"
            }), 500
    
    @app.route('/api/advanced/nut/restart', methods=['POST'])
    @require_admin
    def restart_nut():
        """Restart NUT services"""
        try:
            result = restart_nut_services()
            if result.get("success", False):
                return jsonify({
                    "success": True,
                    "message": result.get("message", "Services restarted successfully")
                })
            else:
                return jsonify({
                    "success": False,
                    "message": result.get("message", "Unknown error")
                }), 500
        except Exception as e:
            logger.error(f"Error restarting NUT services: {str(e)}")
            return jsonify({
                "success": False,
                "message": f"Error restarting NUT services: {str(e)}"
            }), 500
    
    @app.route('/api/advanced/nut/docs/<filename>', methods=['GET'])
    @require_admin
    def get_nut_docs(filename):
        """Get documentation for a NUT configuration file"""
        try:
            docs = get_nut_file_documentation(filename)
            return jsonify({
                "success": True,
                "documentation": docs
            })
        except Exception as e:
            logger.error(f"Error getting documentation for {filename}: {str(e)}")
            return jsonify({
                "success": False,
                "message": f"Error getting documentation: {str(e)}"
            }), 500
    
    logger.info("✅ Registered Advanced NUT Configuration API routes")
    return app 
