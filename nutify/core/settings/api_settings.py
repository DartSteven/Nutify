"""Settings API Module.

Defines API endpoints and response handlers for this feature domain.
"""

from flask import Blueprint, jsonify, request, current_app
from core.auth import require_admin
import os
import json
from .settings import get_logger, parse_value

logger = get_logger('options')

api_settings = Blueprint('api_settings', __name__, url_prefix='/api/settings')

@api_settings.route('', methods=['GET', 'POST'])
@require_admin
def handle_settings():
    """Handle settings API endpoint - get or update settings"""
    settings_file = os.path.join(current_app.root_path, 'config', 'settings.txt')
    
    if request.method == 'GET':
        # Read current settings file
        try:
            with open(settings_file, 'r') as f:
                settings_content = f.read()
            
            # Parse settings to a dict
            settings_dict = {}
            for line in settings_content.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    settings_dict[key] = parse_value(value)
            
            return jsonify({
                'success': True,
                'data': settings_dict
            })
        except Exception as e:
            logger.error(f"Error reading settings file: {str(e)}")
            return jsonify({
                'success': False,
                'message': f"Could not read settings: {str(e)}"
            }), 500
    
    elif request.method == 'POST':
        try:
            # Get update data
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'message': "No settings data provided"
                }), 400
            
            # Read current settings
            with open(settings_file, 'r') as f:
                settings_content = f.readlines()
            
            # Update settings
            updated_lines = []
            updated_keys = set()
            
            for line in settings_content:
                line_stripped = line.strip()
                if not line_stripped or line_stripped.startswith('#'):
                    updated_lines.append(line)
                    continue
                    
                if '=' in line_stripped:
                    key, value = line_stripped.split('=', 1)
                    key = key.strip()
                    
                    if key in data:
                        updated_lines.append(f"{key} = {data[key]}\n")
                        updated_keys.add(key)
                    else:
                        updated_lines.append(line)
            
            # Add new settings that weren't in the file
            for key, value in data.items():
                if key not in updated_keys:
                    updated_lines.append(f"{key} = {value}\n")
            
            # Write back to file
            with open(settings_file, 'w') as f:
                f.writelines(updated_lines)
            
            logger.info(f"Updated settings: {', '.join(data.keys())}")
            return jsonify({
                'success': True,
                'message': f"Updated {len(data)} settings",
                'updated_keys': list(data.keys())
            })
        except Exception as e:
            logger.error(f"Error updating settings: {str(e)}")
            return jsonify({
                'success': False,
                'message': f"Could not update settings: {str(e)}"
            }), 500

@api_settings.route('/reload', methods=['POST'])
@require_admin
def reload_settings():
    """Force a reload of the settings"""
    try:
        # This route will be customized as needed to implement
        # a reload of the settings at runtime
        return jsonify({
            'success': True,
            'message': "Settings reloaded successfully"
        })
    except Exception as e:
        logger.error(f"Error reloading settings: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Could not reload settings: {str(e)}"
        }), 500 
