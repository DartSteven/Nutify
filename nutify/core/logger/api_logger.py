"""Logger API Module.

Defines API endpoints and response handlers for this feature domain.
"""

from flask import Blueprint, jsonify, request, current_app, send_file
from core.auth import require_admin
import os
import re
from datetime import datetime
import tempfile
import zipfile
from .logger import get_logger
from core.settings import LOG, LOG_LEVEL, LOG_WERKZEUG

logger = get_logger('options')

api_logger = Blueprint('api_logger', __name__, url_prefix='/api/log')

@api_logger.route('/settings', methods=['GET', 'POST'])
@require_admin
def update_log_setting():
    """Update and retrieve log settings"""
    if request.method == 'GET':
        # Instead of using cached values from imports, read directly from the file
        try:
            settings_path = os.path.join(current_app.root_path, 'config', 'settings.txt')
            log_enabled = False
            werkzeug_enabled = False
            log_level = "DEBUG"  # Default if not found

            with open(settings_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    if '=' in line:
                        key, value = [part.strip() for part in line.split('=', 1)]
                        if key == 'LOG':
                            log_enabled = value.lower() == 'true'
                            logger.debug(f"Read from file - LOG={value}, log_enabled={log_enabled}")
                        elif key == 'LOG_WERKZEUG':
                            werkzeug_enabled = value.lower() == 'true'
                            logger.debug(f"Read from file - LOG_WERKZEUG={value}, werkzeug_enabled={werkzeug_enabled}")
                        elif key == 'LOG_LEVEL':
                            log_level = value.upper()
                            logger.debug(f"Read from file - LOG_LEVEL={log_level}")
            
            # Log the values for debugging
            logger.debug(f"Settings from file: log_enabled={log_enabled}, level={log_level}, werkzeug={werkzeug_enabled}")
            
            return jsonify({
                'success': True,
                'data': {
                    'log': log_enabled,
                    'level': log_level,
                    'werkzeug': werkzeug_enabled
                }
            })
        except Exception as e:
            logger.error(f"Error reading settings from file: {str(e)}")
            # Fallback to imported values in case of error
            logger.debug(f"Fallback to imported values: LOG={LOG!r}, LOG_LEVEL={LOG_LEVEL!r}, LOG_WERKZEUG={LOG_WERKZEUG!r}")
            log_enabled = str(LOG).strip().lower() == 'true'
            werkzeug_enabled = str(LOG_WERKZEUG).strip().lower() == 'true'
            
            return jsonify({
                'success': True,
                'data': {
                    'log': log_enabled,
                    'level': LOG_LEVEL,
                    'werkzeug': werkzeug_enabled
                }
            })

    data = request.get_json()
    # If the data is empty or does not contain 'log', return the current state instead of an error
    if not data or len(data) == 0 or 'log' not in data:
        # Return the same response format as the GET method
        log_enabled = str(LOG).strip().lower() == 'true'
        werkzeug_enabled = str(LOG_WERKZEUG).strip().lower() == 'true'
        logger.debug(f"POST with empty data - Returning current settings: log={log_enabled}, level={LOG_LEVEL}, werkzeug={werkzeug_enabled}")
        
        return jsonify({
            'success': True,
            'data': {
                'log': log_enabled,
                'level': LOG_LEVEL,
                'werkzeug': werkzeug_enabled
            }
        })
    
    # Normalize 'log'
    new_value = str(data['log']).lower()
    if new_value not in ['true', 'false']:
        return jsonify(success=False, message="Invalid value for 'log' (must be true or false)"), 400
    
    # Optional: Normalize log level (handled below)
    
    # Normalize 'werkzeug'
    new_werkzeug = None
    if 'werkzeug' in data:
        new_werkzeug = str(data['werkzeug']).lower()
        if new_werkzeug not in ['true', 'false']:
            return jsonify(success=False, message="Invalid value for 'werkzeug' (must be true or false)"), 400
    
    new_level = None
    if 'level' in data:
        new_level = str(data['level']).upper()
        if new_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            return jsonify(success=False, message="Invalid log level (must be DEBUG, INFO, WARNING, ERROR, or CRITICAL)"), 400

    try:
        settings_path = os.path.join(current_app.root_path, 'config', 'settings.txt')
        with open(settings_path, 'r') as f:
            lines = f.readlines()
        new_lines = []
        pattern_log = r"^LOG\s*="
        pattern_level = r"^LOG_LEVEL\s*="
        pattern_werkzeug = r"^LOG_WERKZEUG\s*="
        updated_log = False
        updated_level = False
        updated_werkzeug = False
        for line in lines:
            if re.match(pattern_log, line):
                new_lines.append(f"LOG = {new_value}\n")
                updated_log = True
            elif new_level and re.match(pattern_level, line):
                new_lines.append(f"LOG_LEVEL = {new_level}\n")
                updated_level = True
            elif new_werkzeug and re.match(pattern_werkzeug, line):
                new_lines.append(f"LOG_WERKZEUG = {new_werkzeug}\n")
                updated_werkzeug = True
            else:
                new_lines.append(line)
        if not updated_log:
            new_lines.append(f"LOG = {new_value}\n")
        if new_level and (not updated_level):
            new_lines.append(f"LOG_LEVEL = {new_level}\n")
        if new_werkzeug and (not updated_werkzeug):
            new_lines.append(f"LOG_WERKZEUG = {new_werkzeug}\n")
        with open(settings_path, 'w') as f:
            f.writelines(new_lines)
        return jsonify(success=True, message="Log setting updated. Please restart the application for changes to take effect."), 200
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

@api_logger.route('/clear', methods=['POST'])
@require_admin
def clear_logs_api():
    """
    Clear log files for the specified log type.
    Query parameters:
      - type: log type (default 'all')
    """
    from core.options.options import clear_logs
    log_type = request.args.get('type', 'all')
    success, message = clear_logs(log_type)
    return jsonify(success=success, message=message)

@api_logger.route('/download', methods=['GET'])
@require_admin
def download_logs_api():
    """
    Download filtered log files as a zip archive.
    Query parameters:
      - type: log type (default 'all')
      - level: log level (default 'all')
      - range: date range (default 'all')
    """
    from core.options.options import get_filtered_logs
    log_type = request.args.get('type', 'all')
    log_level = request.args.get('level', 'all')
    date_range = request.args.get('range', 'all')
    
    # Get the log file metadata (without content)
    logs_data = get_filtered_logs(
        log_type=log_type, 
        log_level=log_level, 
        date_range=date_range,
        return_metadata_only=True
    )
    
    if not logs_data or not logs_data['files']:
        return jsonify(success=False, message="No logs found"), 404
    
    tmp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    try:
        with zipfile.ZipFile(tmp_zip, 'w') as zf:
            for log_file in logs_data['files']:
                file_path = log_file['path']
                try:
                    # Read the file content and filter by level if necessary
                    with open(file_path, 'r') as f:
                        content = f.read()
                        
                    # Filter by log level if specified
                    if log_level != 'all':
                        filtered_lines = []
                        for line in content.splitlines():
                            if re.search(f"\\b{log_level.upper()}\\b", line, re.I):
                                filtered_lines.append(line)
                        content = '\n'.join(filtered_lines)
                    
                    zf.writestr(log_file['name'], content)
                except Exception as e:
                    logger.error(f"Error adding log file {file_path} to zip: {str(e)}")
                    continue
        
        # Generate a file name with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        download_name = f'logs_{timestamp}.zip'
        
        return send_file(tmp_zip.name,
                         mimetype='application/zip',
                         as_attachment=True,
                         download_name=download_name)
    except Exception as e:
        logger.error(f"Error creating log zip file: {str(e)}")
        return jsonify(success=False, message=f"Error creating zip file: {str(e)}"), 500 
