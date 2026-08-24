"""Options API Module.

Defines API endpoints and response handlers for this feature domain.
"""

from flask import Blueprint, jsonify, request, current_app, send_file
import os
import re
import sys
import tempfile
import zipfile
from datetime import datetime
from datetime import timezone
from .options import (
    get_database_stats,
    backup_database,
    optimize_database,
    vacuum_database,
    download_logs,
    get_system_info,
    get_filtered_logs,
    clear_logs,
    get_variable_config,
    get_variable_config_row
)
from .operations_runtime import get_operation_settings, save_operation_settings
from core.logger import options_logger as logger
from core.db.ups import db, VariableConfig
from core.settings import LOG, LOG_LEVEL, LOG_WERKZEUG, UPS_CONF_PATH
from core.mail import test_notification, get_mail_config_model
from core.multi_nut.target_scope import apply_target_scope, resolve_settings_target_id
from core.scripts.executor import run_shell_script
from core.auth import require_admin
import pytz

TIMEZONE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'config',
    'TimeZone.readme'
)


def _resolve_active_db():
    """Resolve SQLAlchemy handle bound to current Flask app context."""
    try:
        extension = current_app.extensions.get('sqlalchemy')
    except Exception:
        extension = None

    if extension is None:
        return db

    if hasattr(extension, 'session') and hasattr(extension, 'Model'):
        return extension

    extension_db = getattr(extension, 'db', None)
    if extension_db is not None and hasattr(extension_db, 'session'):
        return extension_db

    return db


def _resolve_variable_model():
    """Resolve VariableConfig model, lazily initializing ORM models when needed."""
    db_handle = _resolve_active_db()

    model_space = getattr(db_handle, 'ModelClasses', None)
    model_class = getattr(model_space, 'VariableConfig', None) if model_space else None
    if model_class is not None and hasattr(model_class, 'query'):
        return model_class

    if hasattr(VariableConfig, 'query'):
        return VariableConfig

    try:
        from core.db.models import init_models

        timezone_getter = None
        if hasattr(current_app, 'CACHE_TIMEZONE'):
            timezone_getter = lambda: current_app.CACHE_TIMEZONE

        init_models(db_handle, timezone_getter)
        model_space = getattr(db_handle, 'ModelClasses', None)
        model_class = getattr(model_space, 'VariableConfig', None) if model_space else None
        if model_class is not None and hasattr(model_class, 'query'):
            return model_class
    except Exception as lazy_error:
        logger.debug(f"VariableConfig lazy initialization failed: {lazy_error}")

    return None


def _read_timezones():
    """Read available timezones from the shared timezone catalog file."""
    try:
        rows = []
        with open(TIMEZONE_FILE, 'r') as timezone_file:
            for raw_line in timezone_file:
                line = raw_line.strip()
                if not line or line.startswith('#') or line.startswith('##'):
                    continue
                rows.append(line)
        if rows:
            return rows
    except Exception as error:
        logger.warning(f"Unable to read timezone catalog: {error}")

    return ['Europe/Rome', 'Europe/London', 'America/New_York', 'Asia/Tokyo', 'UTC']

# Blueprint for /api/options routes
api_options = Blueprint('api_options', __name__, url_prefix='/api/options')

# Blueprint for backward compatibility routes
api_options_compat = Blueprint('api_options_compat', __name__)

@api_options.route('/database/stats', methods=['GET'])
def get_db_stats():
    """API endpoint to get database statistics"""
    stats = get_database_stats()
    if stats:
        return jsonify(stats)
    return jsonify({'error': 'Could not get database statistics'}), 500

@api_options.route('/database/backup', methods=['POST'])
def create_backup():
    """API endpoint to create database backup"""
    backup_path = backup_database()
    if backup_path:
        return jsonify({'success': True, 'backup_path': backup_path})
    return jsonify({'error': 'Failed to create backup'}), 500

@api_options.route('/database/optimize', methods=['POST'])
def optimize_db():
    """API endpoint to optimize database"""
    success = optimize_database()
    if success:
        return jsonify({'success': True, 'message': 'Database optimized successfully'})
    return jsonify({'error': 'Failed to optimize database'}), 500

@api_options.route('/database/vacuum', methods=['POST'])
def vacuum_db():
    """API endpoint to vacuum database"""
    success = vacuum_database()
    if success:
        return jsonify({'success': True, 'message': 'Database vacuumed successfully'})
    return jsonify({'error': 'Failed to vacuum database'}), 500

@api_options.route('/logs', methods=['GET'])
def api_get_logs():
    """API endpoint to get logs with filtering"""
    log_type = request.args.get('type', 'all')
    log_level = request.args.get('level', 'all')
    date_range = request.args.get('date_range', 'all')
    try:
        page = int(request.args.get('page', '1'))
    except ValueError:
        page = 1
    try:
        page_size = int(request.args.get('page_size', '1000'))
    except ValueError:
        page_size = 1000
        
    logs = get_filtered_logs(
        log_type=log_type, 
        log_level=log_level, 
        date_range=date_range,
        page=page,
        page_size=page_size
    )
    
    return jsonify(logs)

@api_options.route('/logs/download', methods=['GET'])
def api_download_logs():
    """API endpoint to download logs zip"""
    log_type = request.args.get('type', 'all')
    log_level = request.args.get('level', 'all')
    date_range = request.args.get('date_range', 'all')
    
    zip_path = download_logs(log_type, log_level, date_range)
    
    if zip_path:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return send_file(
            zip_path,
            as_attachment=True,
            download_name=f'logs_{timestamp}.zip',
            mimetype='application/zip'
        )
    
    return jsonify({'error': 'No logs to download'}), 404

@api_options.route('/logs/clear/<log_type>', methods=['DELETE'])
def api_clear_logs(log_type):
    """API endpoint to clear logs"""
    success, message = clear_logs(log_type)
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'error': message}), 500

@api_options.route('/system', methods=['GET'])
def api_system_info():
    """API endpoint to get system info"""
    info = get_system_info()
    if info:
        return jsonify(info)
    return jsonify({'error': 'Could not get system information'}), 500

@api_options.route('/variable-config', methods=['GET'])
def api_variable_config():
    """API endpoint to get variable configuration"""
    logger.info("GET request for variable configuration")
    requested_target_id = request.args.get('target_id', type=int)
    use_global_fallback = requested_target_id is None
    
    # Fetch directly from the database to avoid any caching issues
    try:
        config_from_db, scoped_target_id = get_variable_config_row(
            target_id=requested_target_id,
            include_global_fallback=use_global_fallback,
        )
        if config_from_db:
            logger.info(
                "Found configuration in DB: "
                f"target_id={getattr(config_from_db, 'target_id', None)}, "
                f"scope_target_id={scoped_target_id}, "
                f"polling_interval={config_from_db.polling_interval}"
            )
            response = jsonify({
                'currency': config_from_db.currency,
                'price_per_kwh': float(config_from_db.price_per_kwh),
                'co2_factor': float(config_from_db.co2_factor),
                'polling_interval': int(config_from_db.polling_interval),
                'target_id': getattr(config_from_db, 'target_id', None),
                'scope_target_id': scoped_target_id,
            })
        else:
            logger.warning("No configuration found in database, using get_variable_config()")
            config = get_variable_config(
                target_id=requested_target_id,
                include_global_fallback=use_global_fallback,
            )
            response = jsonify({
                **config,
                'target_id': None,
                'scope_target_id': scoped_target_id,
            })
            
        # Set no-cache headers
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        logger.error(f"Error in variable-config endpoint: {str(e)}")
        config = get_variable_config()  # This now returns default values on error
        if config:
            return jsonify(config)
        return jsonify({'error': 'Could not get variable configuration'}), 500

# Routes moved from core/routes.py
# These routes are kept at their original paths for backward compatibility

@api_options_compat.route('/api/database/stats', methods=['GET'])
def api_database_stats():
    """Return database statistics"""
    stats = get_database_stats()
    if stats is None:
        return jsonify({'success': False, 'error': 'Could not retrieve database statistics'}), 500
    return jsonify({'success': True, 'data': stats})

@api_options_compat.route('/api/logs', methods=['GET'])
def handle_get_logs():
    """Handle log retrieval API"""
    log_type = request.args.get('type', 'all')
    log_level = request.args.get('level', 'all')
    date_range = request.args.get('range', 'all')
    
    # Pagination parameters
    try:
        page = int(request.args.get('page', '1'))
        page_size = int(request.args.get('page_size', '1000'))
        metadata_only = request.args.get('metadata_only', 'false').lower() == 'true'
    except ValueError:
        page = 1
        page_size = 1000
        metadata_only = False
    
    # Limit the page size to avoid memory issues
    page_size = min(page_size, 5000)
    
    logs = get_filtered_logs(
        log_type=log_type, 
        log_level=log_level, 
        date_range=date_range,
        page=page,
        page_size=page_size,
        return_metadata_only=metadata_only
    )
    
    return jsonify({'success': True, 'data': logs})

@api_options_compat.route('/api/logs/clear', methods=['POST'])
def handle_clear_logs():
    """Handle log clearing API"""
    log_type = request.args.get('type', 'all')
    success, message = clear_logs(log_type)
    return jsonify({'success': success, 'message': message})

@api_options_compat.route('/api/system/info', methods=['GET'])
def api_system_info_compat():
    """Return system and project information"""
    info = get_system_info()
    if info is None:
        return jsonify({'success': False, 'error': 'Could not retrieve system info'}), 500
    return jsonify({'success': True, 'data': info})

@api_options_compat.route('/api/about/image', methods=['GET'])
def get_about_image():
    """Return the base64 encoded about image"""
    try:
        base_dir = os.path.dirname(current_app.root_path)
        image_candidates = [
            os.path.join(base_dir, 'nutify', 'frontend', 'app', 'public', 'about_png'),
            os.path.join(current_app.static_folder, 'img', 'about_png'),
        ]

        image_path = next((candidate for candidate in image_candidates if os.path.exists(candidate)), None)
        if not image_path:
            return jsonify({'success': False, 'error': 'Image not found'}), 404

        # Read the base64 content and add MIME type prefix if needed
        with open(image_path, 'r') as f:
            content = f.read().strip()
            if not content.startswith('data:'):
                content = 'data:image/png;base64,' + content
            return jsonify({
                'success': True,
                'data': content
            })

    except Exception as e:
        logger.error(f"Error getting about image: {str(e)}")
        return jsonify({
            'success': False, 
            'error': f'Error getting about image: {str(e)}'
        }), 500

@api_options_compat.route('/api/database/optimize', methods=['POST'])
def api_optimize_database():
    """Optimize database tables"""
    success = optimize_database()
    if success:
        return jsonify(success=True, message="Database optimized successfully")
    else:
        return jsonify(success=False, message="Error optimizing database"), 500

@api_options_compat.route('/api/database/vacuum', methods=['POST'])
def api_vacuum_database():
    """Vacuum database to reclaim space"""
    success = vacuum_database()
    if success:
        return jsonify(success=True, message="Database vacuumed successfully")
    else:
        return jsonify(success=False, message="Error vacuuming database"), 500

@api_options_compat.route('/api/database/backup', methods=['GET'])
def api_backup_database():
    """Create and download a backup of the database"""
    backup_path = backup_database()
    if backup_path:
        return send_file(backup_path,
                        mimetype="application/octet-stream",
                        as_attachment=True,
                        download_name=os.path.basename(backup_path))
    else:
        return jsonify(success=False, message="Error creating database backup"), 500

@api_options_compat.route('/api/settings/variables', methods=['GET'])
def get_variables_settings():
    """API endpoint to get variable configuration settings"""
    try:
        requested_target_id = request.args.get('target_id', type=int)
        use_global_fallback = requested_target_id is None
        logger.info("GET request for variables configuration")
        
        try:
            config, scoped_target_id = get_variable_config_row(
                target_id=requested_target_id,
                include_global_fallback=use_global_fallback,
            )
            if config:
                logger.info(
                    "Found configuration: "
                    f"target_id={getattr(config, 'target_id', None)}, "
                    f"scope_target_id={scoped_target_id}, "
                    f"timezone={getattr(config, 'timezone', None)}, "
                    f"ups_realpower_nominal={getattr(config, 'ups_realpower_nominal', None)}, "
                    f"currency={config.currency}, "
                    f"price_per_kwh={config.price_per_kwh}, "
                    f"co2_factor={config.co2_factor}"
                )
                return jsonify({
                    'success': True,
                    'data': {
                        'timezone': str(getattr(config, 'timezone', None) or getattr(current_app.CACHE_TIMEZONE, 'zone', 'UTC') or 'UTC'),
                        'ups_realpower_nominal': (
                            int(config.ups_realpower_nominal)
                            if getattr(config, 'ups_realpower_nominal', None) not in (None, '')
                            else None
                        ),
                        'currency': config.currency,
                        'price_per_kwh': float(config.price_per_kwh),
                        'co2_factor': float(config.co2_factor),
                        'target_id': getattr(config, 'target_id', None),
                        'scope_target_id': scoped_target_id,
                    }
                })

            defaults = get_variable_config(
                target_id=requested_target_id,
                include_global_fallback=use_global_fallback,
            )
            return jsonify({
                'success': True,
                'data': {
                    **defaults,
                    'target_id': None,
                    'scope_target_id': scoped_target_id,
                }
            })
        except Exception as db_error:
            logger.error(f"Database error while reading variables config: {str(db_error)}")
            defaults = get_variable_config(
                target_id=requested_target_id,
                include_global_fallback=use_global_fallback,
            )
            return jsonify({
                'success': True,
                'data': {
                    **defaults,
                    'target_id': None,
                    'scope_target_id': None,
                }
            })
    except Exception as e:
        logger.error(f"Error getting variables config: {str(e)}")
        return jsonify({'success': False, 'error': 'Database configuration error'}), 500

@api_options_compat.route('/api/settings/variables', methods=['POST'])
def save_variables_config():
    """API endpoint to save variable configuration settings"""
    try:
        requested_target_id = request.args.get('target_id', type=int)
        model_class = _resolve_variable_model()
        if model_class is None:
            logger.error("No usable VariableConfig model found")
            return jsonify({'success': False, 'error': 'Database configuration error'}), 500
            
        data = request.get_json()
        if not data:
            logger.warning("No data provided in request")
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        logger.info(f"Received data: {data}")
        
        # Validate required fields
        required_fields = ['currency', 'price_per_kwh', 'co2_factor']
        for field in required_fields:
            if field not in data:
                logger.warning(f"Missing required field: {field}")
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400
        
        try:
            # Get existing configuration for current target scope or create a new one
            config, scoped_target_id = get_variable_config_row(
                target_id=requested_target_id,
                include_global_fallback=False,
            )
            if not config:
                logger.info(f"No existing configuration found for target scope {scoped_target_id}, creating new")
                config = model_class()
                if hasattr(config, 'target_id'):
                    config.target_id = scoped_target_id
                db.session.add(config)
            
            # Update fields
            timezone_value = str(data.get('timezone', getattr(config, 'timezone', '') or getattr(current_app.CACHE_TIMEZONE, 'zone', 'UTC'))).strip()
            if timezone_value:
                try:
                    pytz.timezone(timezone_value)
                except Exception:
                    logger.warning(f"Invalid timezone provided in variables config: {timezone_value}")
                    return jsonify({'success': False, 'error': 'Invalid timezone value'}), 400
            else:
                timezone_value = getattr(current_app.CACHE_TIMEZONE, 'zone', 'UTC')

            config.currency = data['currency']
            config.price_per_kwh = float(data['price_per_kwh'])
            config.co2_factor = float(data['co2_factor'])
            config.timezone = timezone_value

            if 'ups_realpower_nominal' in data:
                nominal_raw = data.get('ups_realpower_nominal')
                if nominal_raw in (None, ''):
                    config.ups_realpower_nominal = None
                else:
                    try:
                        nominal_value = int(nominal_raw)
                    except (TypeError, ValueError):
                        return jsonify({'success': False, 'error': 'UPS nominal power must be a valid integer'}), 400
                    if nominal_value <= 0:
                        return jsonify({'success': False, 'error': 'UPS nominal power must be greater than zero'}), 400
                    config.ups_realpower_nominal = nominal_value
            
            # Try to commit changes
            db.session.commit()
            logger.info(f"Configuration saved successfully: {data}")
            
            return jsonify({
                'success': True,
                'message': 'Variable configuration saved successfully',
                'data': {
                    'timezone': config.timezone,
                    'ups_realpower_nominal': config.ups_realpower_nominal,
                    'currency': config.currency,
                    'price_per_kwh': float(config.price_per_kwh),
                    'co2_factor': float(config.co2_factor),
                },
                'target_id': getattr(config, 'target_id', None),
                'scope_target_id': scoped_target_id,
            })
        except Exception as db_error:
            # Rollback on database error
            db.session.rollback()
            logger.error(f"Database error: {str(db_error)}")
            return jsonify({'success': False, 'error': 'Failed to save'}), 500
            
    except Exception as e:
        # Rollback if session exists
        if db and hasattr(db, 'session'):
            db.session.rollback()
        
        logger.error(f"Error saving variables config: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to save'}), 500


@api_options_compat.route('/api/settings/operations', methods=['GET'])
def get_operations_settings():
    """API endpoint to get formula/mapping operation settings."""
    try:
        requested_target_id = request.args.get('target_id', type=int)
        payload = get_operation_settings(target_id=requested_target_id)
        return jsonify({'success': True, 'data': payload})
    except Exception as exc:
        logger.error(f"Error getting operations settings: {exc}")
        return jsonify({'success': False, 'error': 'Could not get operations settings'}), 500


@api_options_compat.route('/api/settings/operations', methods=['POST'])
def save_operations_settings():
    """API endpoint to save formula/mapping operation settings."""
    try:
        requested_target_id = request.args.get('target_id', type=int)
        payload = request.get_json(silent=True) or {}
        saved = save_operation_settings(payload, target_id=requested_target_id)
        return jsonify(
            {
                'success': True,
                'message': 'Operations settings saved successfully',
                'data': saved,
            }
        )
    except Exception as exc:
        if db and hasattr(db, 'session'):
            db.session.rollback()
        logger.error(f"Error saving operations settings: {exc}")
        return jsonify({'success': False, 'error': 'Could not save operations settings'}), 500


@api_options_compat.route('/api/settings/polling-interval', methods=['POST'])
def update_polling_interval():
    """API endpoint to update polling interval and restart application"""
    try:
        # Check if database is initialized
        if not db:
            logger.error("Database not initialized")
            return jsonify({'success': False, 'error': 'Database configuration error'}), 500
            
        # Use ModelClasses.VariableConfig if available, otherwise use imported VariableConfig
        model_class = None
        if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'VariableConfig'):
            model_class = db.ModelClasses.VariableConfig
            logger.info("Using VariableConfig from ModelClasses")
        elif hasattr(VariableConfig, 'query'):
            model_class = VariableConfig
            logger.info("Using directly imported VariableConfig")
        else:
            logger.error("No usable VariableConfig model found")
            return jsonify({'success': False, 'error': 'Database configuration error'}), 500
            
        data = request.get_json()
        if not data or 'polling_interval' not in data:
            logger.warning("No polling_interval provided in request")
            return jsonify({'success': False, 'error': 'No polling_interval provided'}), 400

        polling_interval = int(data['polling_interval'])
        update_both = data.get('update_both', False)
        
        # Validate polling interval (1-60 seconds)
        if polling_interval < 1 or polling_interval > 60:
            logger.warning(f"Invalid polling interval: {polling_interval}. Must be between 1 and 60 seconds.")
            return jsonify({'success': False, 'error': 'Polling interval must be between 1 and 60 seconds'}), 400
        
        try:
            # Polling interval is global and stored on the global scope row.
            query = model_class.query
            if hasattr(model_class, 'target_id'):
                query = query.filter(model_class.target_id.is_(None))
            config = query.order_by(model_class.id.asc()).first()
            if not config:
                logger.info("No existing configuration found, creating new")
                config = model_class()
                if hasattr(config, 'target_id'):
                    config.target_id = None
                db.session.add(config)
            
            # Update polling interval in database
            config.polling_interval = polling_interval
            
            # Update pollfreq in the ups.conf file using the path from settings
            try:
                # Use the configured UPS configuration file path
                ups_conf_path = UPS_CONF_PATH
                
                # Check if file exists and is accessible
                if os.path.exists(ups_conf_path):
                    try:
                        # Read the current content of the file
                        with open(ups_conf_path, 'r') as f:
                            content = f.readlines()
                        
                        # Create new content with updated values
                        new_content = []
                        pollfreq_updated = False
                        pollinterval_exists = False
                        pollinterval_updated = False
                        
                        # Process each line
                        for line in content:
                            # Update pollfreq
                            if 'pollfreq' in line and '=' in line:
                                parts = line.split('=', 1)
                                new_line = f"{parts[0]}= {polling_interval}\n"
                                new_content.append(new_line)
                                pollfreq_updated = True
                            # Check if pollinterval exists and update it
                            elif update_both and 'pollinterval' in line and '=' in line:
                                parts = line.split('=', 1)
                                new_line = f"{parts[0]}= {polling_interval}\n"
                                new_content.append(new_line)
                                pollinterval_exists = True
                                pollinterval_updated = True
                            else:
                                new_content.append(line)
                        
                        # If update_both is true and pollinterval doesn't exist, add it after pollfreq
                        if update_both and not pollinterval_exists:
                            # Add pollinterval after pollfreq
                            with_pollinterval = []
                            for line in new_content:
                                with_pollinterval.append(line)
                                # After pollfreq line, add pollinterval
                                if 'pollfreq' in line and '=' in line:
                                    with_pollinterval.append(f"\tpollinterval = {polling_interval}\n")
                            new_content = with_pollinterval
                            pollinterval_updated = True
                        
                        # Write the updated content back to the file
                        with open(ups_conf_path, 'w') as f:
                            f.writelines(new_content)
                        
                        if pollfreq_updated:
                            logger.info(f"Updated pollfreq in {ups_conf_path} to {polling_interval}")
                        else:
                            logger.warning(f"Could not find pollfreq in {ups_conf_path}")
                            
                        if update_both:
                            if pollinterval_updated:
                                if pollinterval_exists:
                                    logger.info(f"Updated pollinterval in {ups_conf_path} to {polling_interval}")
                                else:
                                    logger.info(f"Added pollinterval to {ups_conf_path} with value {polling_interval}")
                            else:
                                logger.warning("Could not update or add pollinterval")
                    except Exception as e:
                        logger.error(f"Error updating UPS config file: {str(e)}")
                else:
                    logger.warning(f"UPS config file {ups_conf_path} not found or not accessible")
            except Exception as ups_error:
                logger.error(f"Failed to update UPS config file: {str(ups_error)}")
                # Continue with database update even if UPS config update fails
            
            # Try to commit changes to database
            db.session.commit()
            logger.info(f"Polling interval updated to {polling_interval} seconds")
            
            return jsonify({
                'success': True,
                'message': 'Polling interval updated successfully. Application restart required for changes to take effect.'
            })
        except Exception as db_error:
            # Rollback on database error
            db.session.rollback()
            logger.error(f"Database error: {str(db_error)}")
            return jsonify({'success': False, 'error': 'Failed to save polling interval'}), 500
            
    except Exception as e:
        # Rollback if session exists
        if db and hasattr(db, 'session'):
            db.session.rollback()
        
        logger.error(f"Error updating polling interval: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to update polling interval'}), 500

@api_options_compat.route('/api/restart', methods=['POST'])
def restart_application():
    """
    Restart the application.
    """
    try:
        logger.info("Restarting application...")
        
        # Create a clean response
        response = jsonify(success=True, message="Application is restarting...")
        
        # Import necessary modules
        import os, sys, gc, threading, multiprocessing
        
        # Force garbage collection to clean up resources
        gc.collect()
        
        # Close any multiprocessing resources
        try:
            # Check if multiprocessing is active and try to shut it down cleanly
            if hasattr(multiprocessing, 'resource_tracker') and multiprocessing.resource_tracker._resource_tracker is not None:
                # Access the _resource_tracker directly to shut it down
                multiprocessing.resource_tracker._resource_tracker._stop()
                # Set to None to avoid further use
                multiprocessing.resource_tracker._resource_tracker = None
        except:
            pass  # Silently continue if this fails
        
        # Close database connections if available
        if 'db' in globals() and hasattr(db, 'engine'):
            db.engine.dispose()
        
        # Get paths for restart
        executable = sys.executable
        args = sys.argv
        
        # Execute restart without using subprocess or threading
        os.execv(executable, [executable] + args)
        
        return response
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

@api_options_compat.route('/api/settings/log', methods=['GET', 'POST'])
def update_log_setting():
    """Update and retrieve log settings"""
    if request.method == 'GET':
        # Add log for debug
        logger.debug(f"Reading settings - RAW values: LOG={LOG!r}, LOG_LEVEL={LOG_LEVEL!r}, LOG_WERKZEUG={LOG_WERKZEUG!r}")
        log_enabled = str(LOG).strip().lower() == 'true'
        werkzeug_enabled = str(LOG_WERKZEUG).strip().lower() == 'true'
        logger.debug(f"Processed values: log_enabled={log_enabled}, level={LOG_LEVEL}, werkzeug={werkzeug_enabled}")
        
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

@api_options_compat.route('/api/logs/download', methods=['GET'])
def download_logs():
    """
    Download filtered log files as a zip archive.
    Query parameters:
      - type: log type (default 'all')
      - level: log level (default 'all')
      - range: date range (default 'all')
    """
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

@api_options_compat.route('/api/settings/test-notification', methods=['POST'])
def test_email_notification():
    """
    API endpoint to test email notifications for a specific event type
    Expects query parameters:
        - event_type: Type of event to test (e.g., 'ONLINE', 'ONBATT', etc.)
        - id_email: ID of the email configuration to use
    Returns:
        - JSON response with success status and message
    """
    try:
        # Get parameters from query string
        event_type = request.args.get('event_type')
        id_email = request.args.get('id_email')
        requested_target_id = request.args.get('target_id', type=int)
        scoped_target_id = resolve_settings_target_id(requested_target_id)
        
        # Validate parameters
        if not event_type:
            logger.error("Missing required parameter: event_type")
            return jsonify({
                'success': False,
                'message': 'Missing required parameter: event_type'
            }), 400
            
        if not id_email:
            logger.error("Missing required parameter: id_email")
            return jsonify({
                'success': False,
                'message': 'Missing required parameter: id_email'
            }), 400
        
        # Try to convert id_email to integer
        try:
            id_email = int(id_email)
        except ValueError:
            logger.error(f"Invalid id_email: {id_email}, must be an integer")
            return jsonify({
                'success': False,
                'message': 'Invalid id_email: must be an integer'
            }), 400
        
        # Verify that the email configuration exists
        MailConfig = get_mail_config_model()
        if not MailConfig:
            logger.error("MailConfig model not available")
            return jsonify({
                'success': False,
                'message': 'Email configuration system not available'
            }), 500
            
        mail_query = MailConfig.query
        if hasattr(MailConfig, 'target_id'):
            mail_query = mail_query.filter(MailConfig.target_id.is_(None))
        mail_config = mail_query.filter(MailConfig.id == id_email).first()
        if not mail_config:
            logger.error(f"Email configuration with ID {id_email} not found")
            return jsonify({
                'success': False,
                'message': f'Email configuration with ID {id_email} not found'
            }), 404
        
        # Prepare test data
        test_data = {
            'id_email': id_email,
            'is_test': True,
            'to_email': mail_config.to_email or mail_config.username,
            'target_id': scoped_target_id,
        }
        
        # Call test_notification function
        logger.info(f"Testing notification for event type {event_type} with email config {id_email}")
        success, message = test_notification(event_type, test_data)
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        logger.error(f"Error testing notification: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error testing notification: {str(e)}'
        }), 500

@api_options_compat.route('/api/ups/json', methods=['GET'])
def get_ups_json():
    """API endpoint to get UPS data as JSON for download"""
    try:
        from core.db.ups import get_ups_data
        from datetime import datetime
        import json
        from flask import current_app
        
        # Get the UPS data
        ups_data = get_ups_data()
        
        # Convert DotDict to regular dict (it has a _data attribute that contains the actual dict)
        regular_dict = {}
        if ups_data and hasattr(ups_data, '_data'):
            regular_dict = dict(ups_data._data)
        
        # Format the timestamp with proper timezone
        tz = current_app.CACHE_TIMEZONE
        timestamp = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S %Z')
        
        # Create a correctly serializable structure
        result = {
            "timestamp": timestamp,
            "ups_data": regular_dict
        }
        
        # Return as JSON response with proper headers for download
        response = jsonify(result)
        response.headers['Content-Disposition'] = f'attachment; filename=ups_data_{datetime.now(tz).strftime("%Y%m%d_%H%M%S")}.json'
        return response
        
    except Exception as e:
        logger.error(f"Error getting UPS JSON data: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"Error getting UPS data: {str(e)}"
        }), 500

# Add a new endpoint for getting setup/master control variables
@api_options.route('/options-from-initial-setup', methods=['GET'])
def get_initial_setup_options():
    """API endpoint to get instance metadata and scoped target setup options."""
    try:
        timezones = _read_timezones()
        requested_target_id = request.args.get('target_id', type=int)
        scoped_target_id = resolve_settings_target_id(requested_target_id)

        master_model = None
        if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'MasterControl'):
            master_model = db.ModelClasses.MasterControl
        else:
            from core.db.orm.orm_nutify_master_control import init_model
            master_model = init_model(db.Model, logger)

        master_row = (
            master_model.query
            .filter_by(is_configured=True)
            .order_by(master_model.updated_at.desc(), master_model.id.desc())
            .first()
        )
        if not master_row:
            master_row = master_model.query.order_by(master_model.updated_at.desc(), master_model.id.desc()).first()

        variable_row, resolved_scope = get_variable_config_row(
            target_id=scoped_target_id,
            include_global_fallback=True,
        )
        variable_defaults = get_variable_config(
            target_id=scoped_target_id,
            include_global_fallback=(scoped_target_id is None),
        )

        timezone_value = (
            str(getattr(variable_row, 'timezone', None) or variable_defaults.get('timezone') or 'UTC')
            if variable_row or variable_defaults
            else 'UTC'
        )
        nominal_value = (
            int(variable_row.ups_realpower_nominal)
            if variable_row and getattr(variable_row, 'ups_realpower_nominal', None) not in (None, '')
            else variable_defaults.get('ups_realpower_nominal')
        )

        return jsonify({
            'success': True,
            'data': {
                'server_name': str(getattr(master_row, 'server_name', None) or 'Nutify'),
                'timezone': timezone_value,
                'is_configured': bool(getattr(master_row, 'is_configured', False)),
                'monitoring_profile': str(getattr(master_row, 'monitoring_profile', 'single') or 'single'),
                'ups_realpower_nominal': nominal_value,
                'target_id': getattr(variable_row, 'target_id', None) if variable_row else resolved_scope,
                'scope_target_id': resolved_scope,
                'timezones': timezones,
            }
        })

    except Exception as e:
        logger.error(f"Error retrieving initial setup configuration: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to retrieve initial setup configuration: {str(e)}"
        }), 500

# Add a new endpoint for updating instance and scoped target setup options
@api_options.route('/options-from-initial-setup', methods=['POST'])
def update_initial_setup_options():
    """API endpoint to update instance metadata and scoped target options."""
    try:
        requested_target_id = request.args.get('target_id', type=int)
        scoped_target_id = resolve_settings_target_id(requested_target_id)

        master_model = None
        if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'MasterControl'):
            master_model = db.ModelClasses.MasterControl
        else:
            from core.db.orm.orm_nutify_master_control import init_model
            master_model = init_model(db.Model, logger)

        # Get data from request
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        # Validate required fields
        required_fields = ['server_name']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({
                'success': False,
                'error': f"Missing required fields: {', '.join(missing_fields)}"
            }), 400

        monitoring_profile = str(data.get('monitoring_profile', 'single') or 'single').strip().lower()
        if monitoring_profile not in {'single', 'multi'}:
            return jsonify({
                'success': False,
                'error': "Invalid monitoring_profile. Supported values: single, multi"
            }), 400

        master_row = master_model.query.order_by(master_model.updated_at.desc(), master_model.id.desc()).first()
        if not master_row:
            master_row = master_model()
            db.session.add(master_row)

        master_row.server_name = str(data.get('server_name') or '').strip() or 'Nutify'
        master_row.monitoring_profile = monitoring_profile
        master_row.is_configured = True

        variable_model = None
        if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'VariableConfig'):
            variable_model = db.ModelClasses.VariableConfig
        else:
            variable_model = VariableConfig

        variable_row, resolved_scope = get_variable_config_row(
            target_id=scoped_target_id,
            include_global_fallback=False,
        )
        if not variable_row:
            variable_row = variable_model()
            if hasattr(variable_row, 'target_id'):
                variable_row.target_id = resolved_scope
            db.session.add(variable_row)

        previous_timezone = str(getattr(variable_row, 'timezone', '') or 'UTC')
        if 'timezone' in data and str(data.get('timezone') or '').strip():
            timezone_value = str(data.get('timezone')).strip()
            try:
                pytz.timezone(timezone_value)
            except Exception:
                return jsonify({
                    'success': False,
                    'error': 'Invalid timezone value'
                }), 400
            variable_row.timezone = timezone_value

        if 'ups_realpower_nominal' in data:
            raw_nominal = data.get('ups_realpower_nominal')
            if raw_nominal in (None, ''):
                variable_row.ups_realpower_nominal = None
            else:
                try:
                    parsed_nominal = int(raw_nominal)
                except (ValueError, TypeError):
                    return jsonify({
                        'success': False,
                        'error': 'UPS nominal power must be a valid integer'
                    }), 400
                if parsed_nominal <= 0:
                    return jsonify({
                        'success': False,
                        'error': 'UPS nominal power must be greater than zero'
                    }), 400
                variable_row.ups_realpower_nominal = parsed_nominal

        db.session.commit()
        logger.info(
            "Updated master control and scoped setup options: server_name=%s, target_id=%s",
            master_row.server_name,
            getattr(variable_row, 'target_id', resolved_scope),
        )

        try:
            if str(getattr(variable_row, 'timezone', 'UTC') or 'UTC') != previous_timezone:
                runtime_timezone = pytz.timezone(variable_row.timezone or 'UTC')
                if hasattr(current_app, 'CACHE_TIMEZONE'):
                    current_app.CACHE_TIMEZONE = runtime_timezone
                import app as app_module
                app_module.CACHE_TIMEZONE = runtime_timezone
                logger.info(f"Updated runtime CACHE_TIMEZONE from options to: {variable_row.timezone}")
        except Exception as timezone_error:
            logger.warning(f"Unable to refresh runtime CACHE_TIMEZONE after options update: {timezone_error}")

        return jsonify({
            'success': True,
            'message': 'Setup options updated successfully',
            'data': {
                'server_name': master_row.server_name,
                'timezone': str(getattr(variable_row, 'timezone', None) or 'UTC'),
                'is_configured': bool(master_row.is_configured),
                'monitoring_profile': str(getattr(master_row, 'monitoring_profile', monitoring_profile) or monitoring_profile),
                'ups_realpower_nominal': getattr(variable_row, 'ups_realpower_nominal', None),
                'target_id': getattr(variable_row, 'target_id', None),
                'scope_target_id': resolved_scope,
            }
        })
    
    except Exception as e:
        # Rollback on error
        if 'db' in locals() and hasattr(db, 'session'):
            db.session.rollback()
            
        logger.error(f"Error updating initial setup configuration: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to update initial setup configuration: {str(e)}"
        }), 500 


def _script_action_model():
    model_space = getattr(db, 'ModelClasses', None)
    return getattr(model_space, 'ScriptAction', None) if model_space is not None else None


def _script_action_scope():
    return resolve_settings_target_id(request.args.get('target_id', type=int))


def _script_action_query(model):
    return apply_target_scope(model, model.query, _script_action_scope())


def _safe_int(value, fallback=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(fallback)


def _sanitize_script_payload(payload):
    data = payload or {}
    name = str(data.get('name', '')).strip()
    trigger_event = str(data.get('trigger_event', 'LOWBATT')).strip().upper()
    battery_threshold = _safe_int(data.get('battery_threshold', 30), 30)
    cooldown_seconds = _safe_int(data.get('cooldown_seconds', 300), 300)
    script_body = str(data.get('script_body', '') or '')
    enabled = bool(data.get('enabled', True))

    if not name:
        return None, 'Name is required'
    if trigger_event not in {'ONBATT', 'LOWBATT'}:
        return None, 'trigger_event must be ONBATT or LOWBATT'
    if battery_threshold < 0 or battery_threshold > 100:
        return None, 'battery_threshold must be between 0 and 100'
    if cooldown_seconds < 0 or cooldown_seconds > 86400:
        return None, 'cooldown_seconds must be between 0 and 86400'
    if not script_body.strip():
        return None, 'script_body is required'

    normalized = {
        'name': name[:128],
        'trigger_event': trigger_event,
        'battery_threshold': battery_threshold,
        'cooldown_seconds': cooldown_seconds,
        'script_body': script_body,
        'enabled': enabled,
    }
    return normalized, None


@api_options.route('/script-actions', methods=['GET'])
@require_admin
def list_script_actions():
    ScriptAction = _script_action_model()
    if ScriptAction is None:
        return jsonify({'success': False, 'error': 'Script actions model not available'}), 500
    rows = _script_action_query(ScriptAction).order_by(ScriptAction.id.asc()).all()
    return jsonify({'success': True, 'data': [row.to_dict() for row in rows]})


@api_options.route('/script-actions', methods=['POST'])
@require_admin
def create_script_action():
    ScriptAction = _script_action_model()
    if ScriptAction is None:
        return jsonify({'success': False, 'error': 'Script actions model not available'}), 500
    normalized, error = _sanitize_script_payload(request.get_json(silent=True))
    if error:
        return jsonify({'success': False, 'error': error}), 400
    row = ScriptAction(**normalized, target_id=_script_action_scope())
    db.session.add(row)
    db.session.commit()
    return jsonify({'success': True, 'data': row.to_dict()})


@api_options.route('/script-actions/<int:action_id>', methods=['PUT'])
@require_admin
def update_script_action(action_id):
    ScriptAction = _script_action_model()
    if ScriptAction is None:
        return jsonify({'success': False, 'error': 'Script actions model not available'}), 500
    row = _script_action_query(ScriptAction).filter_by(id=action_id).first()
    if not row:
        return jsonify({'success': False, 'error': 'Script action not found'}), 404
    normalized, error = _sanitize_script_payload(request.get_json(silent=True))
    if error:
        return jsonify({'success': False, 'error': error}), 400
    for key, value in normalized.items():
        setattr(row, key, value)
    row.condition_active = False
    db.session.add(row)
    db.session.commit()
    return jsonify({'success': True, 'data': row.to_dict()})


@api_options.route('/script-actions/<int:action_id>', methods=['DELETE'])
@require_admin
def delete_script_action(action_id):
    ScriptAction = _script_action_model()
    if ScriptAction is None:
        return jsonify({'success': False, 'error': 'Script actions model not available'}), 500
    row = _script_action_query(ScriptAction).filter_by(id=action_id).first()
    if not row:
        return jsonify({'success': False, 'error': 'Script action not found'}), 404
    db.session.delete(row)
    db.session.commit()
    return jsonify({'success': True})


@api_options.route('/script-actions/<int:action_id>/test', methods=['POST'])
@require_admin
def test_script_action(action_id):
    ScriptAction = _script_action_model()
    if ScriptAction is None:
        return jsonify({'success': False, 'error': 'Script actions model not available'}), 500
    row = _script_action_query(ScriptAction).filter_by(id=action_id).first()
    if not row:
        return jsonify({'success': False, 'error': 'Script action not found'}), 404

    script_body = str(getattr(row, 'script_body', '') or '').strip()
    if not script_body:
        return jsonify({'success': False, 'error': 'Script body is empty'}), 400

    result = run_shell_script(script_body, timeout_seconds=30)
    exit_code = result.exit_code
    output = result.output

    row.last_executed_at = datetime.now(timezone.utc)
    row.last_exit_code = exit_code
    row.last_output = output
    db.session.add(row)
    db.session.commit()

    return jsonify({
        'success': exit_code == 0,
        'data': {
            'exit_code': exit_code,
            'output': output,
            'last_executed_at': row.last_executed_at.isoformat() if row.last_executed_at else None,
        },
    })
