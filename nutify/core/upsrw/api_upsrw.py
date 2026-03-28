"""Upsrw API Module.

Defines API endpoints and response handlers for this feature domain.
"""

from flask import jsonify, request
from core.auth import require_admin, require_auth_json
from core.logger import ups_logger as logger
from core.multi_nut.target_scope import resolve_settings_target_id

# Import functions from upsrw module
from .upsrw import (
    get_ups_variables,
    set_ups_variable,
    get_variable_history,
    clear_variable_history
)

def register_api_routes(app):
    """Register all API routes for the upsrw section"""

    def _resolve_target_scope_id(payload=None):
        requested_target_id = request.args.get('target_id', type=int)
        if requested_target_id is None and isinstance(payload, dict):
            raw_target_id = payload.get('target_id')
            try:
                requested_target_id = int(raw_target_id) if raw_target_id is not None else None
            except (TypeError, ValueError):
                requested_target_id = None
        return resolve_settings_target_id(requested_target_id)
    
    @app.route('/api/upsrw/list')
    @require_auth_json
    def api_upsrw_list():
        """API to get the list of variables"""
        variables = get_ups_variables()
        return jsonify({
            'success': True,
            'variables': variables
        })
    
    @app.route('/api/upsrw/set', methods=['POST'])
    @require_admin
    def api_upsrw_set():
        """API to set a variable"""
        data = request.get_json(silent=True) or {}
        name = data.get('name')
        value = data.get('value')
        
        if not name or value is None:
            return jsonify({
                'success': False,
                'error': 'Name and value are required'
            })
        
        scoped_target_id = _resolve_target_scope_id(data)
        success, message = set_ups_variable(name, value, target_id=scoped_target_id)
        return jsonify({
            'success': success,
            'message': message
        })
    
    @app.route('/api/upsrw/history')
    @require_auth_json
    def api_upsrw_history():
        """API to get the variable history"""
        try:
            scoped_target_id = _resolve_target_scope_id()
            history = get_variable_history(target_id=scoped_target_id)
            return jsonify({
                'success': True,
                'history': history
            })
        except Exception as e:
            logger.error(f"Error getting variable history: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            })
            
    @app.route('/api/upsrw/history/<variable>')
    @require_auth_json
    def api_upsrw_history_variable(variable):
        """API to get the history of a specific variable"""
        try:
            scoped_target_id = _resolve_target_scope_id()
            history = get_variable_history(variable, target_id=scoped_target_id)
            return jsonify({
                'success': True,
                'history': history
            })
        except Exception as e:
            logger.error(f"Error getting variable history: {variable} {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            })
        
    @app.route('/api/upsrw/clear-history', methods=['POST'])
    @require_admin
    def api_upsrw_clear_history():
        """API to clear the history"""
        try:
            data = request.get_json(silent=True) or {}
            scoped_target_id = _resolve_target_scope_id(data)
            success = clear_variable_history(target_id=scoped_target_id)
            return jsonify({
                'success': success
            })
        except Exception as e:
            logger.error(f"Error clearing history: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
    return app 
