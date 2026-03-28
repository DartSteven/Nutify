"""Api.Py Module.

Implements core runtime logic and helpers used by this feature.
"""

from flask import jsonify, request, current_app
import json
import ipaddress
from .settings import (
    LOG, LOG_LEVEL, LOG_WERKZEUG
)
from .db.ups import (
    db, data_lock, get_ups_data, get_supported_value, get_ups_model,
    create_static_model
)
from .mail import (
    register_mail_api_routes
)
from .upsmon import handle_nut_event, get_event_history, get_events_table, acknowledge_event
from .events.api_events import register_api_routes as register_events_api_routes
import os
from datetime import datetime
import pytz
from core.logger import web_logger as logger
from .upscmd.api_upscmd import register_api_routes as register_upscmd_api_routes
from .upsrw.api_upsrw import register_api_routes as register_upsrw_api_routes
from .infoapi import register_api_routes as register_infoapi_routes
from flask_socketio import emit
logger.info("�� Initializing api")


def get_historical_data(start_time, end_time):
    try:
        UPSData = get_ups_model()
        logger.debug(f"Querying data from {start_time} to {end_time}")
        data = UPSData.query.filter(
            UPSData.timestamp_utc.between(start_time, end_time)
        ).order_by(UPSData.timestamp_utc.asc()).all()
        logger.debug(f"Found {len(data)} records")
        result = []
        for entry in data:
            try:
                nominal_power = entry.ups_realpower_nominal if entry.ups_realpower_nominal is not None else 960
                load = entry.ups_load if entry.ups_load is not None else 0
                calculated_power = (nominal_power * load) / 100
                item = {
                    'timestamp': entry.timestamp_utc.isoformat(),
                    'input_voltage': float(entry.input_voltage if entry.input_voltage is not None else 0),
                    'power': float(calculated_power),
                    'energy': float(calculated_power),
                    'battery_charge': float(entry.battery_charge if entry.battery_charge is not None else 0)
                }
                result.append(item)
            except (ValueError, TypeError, AttributeError) as e:
                logger.error(f"Error processing record {entry.id}: {e}")
                continue
        logger.debug(f"Processed {len(result)} valid records")
        return result
    except Exception as e:
        logger.error(f"Error retrieving historical data: {e}")
        return []

# Add SETTINGS_DIR
SETTINGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'settings')

def register_api_routes(app):
    """Registers all API routes for the application"""
    # Register mail API routes
    register_mail_api_routes(app)
    
    # Register upscmd API routes
    register_upscmd_api_routes(app)
    
    # Register upsrw API routes
    register_upsrw_api_routes(app)
    
    # Register events API routes
    register_events_api_routes(app)
    
    # Register infoapi routes
    register_infoapi_routes(app)

    @app.route('/api/data/<column>')
    def get_column_data(column):
        """Returns the value of a specific column"""
        try:
            logger.debug(f"Requesting column: {column}")

            # Multi-NUT active target override for dashboard-wide target switching.
            try:
                from core.multi_nut.active_target import get_active_target_snapshot_payload

                active_snapshot = get_active_target_snapshot_payload()
                if active_snapshot:
                    metrics = active_snapshot.get('metrics') or {}
                    latest = active_snapshot.get('latest') or {}
                    timestamp_value = latest.get('timestamp_utc') or datetime.now(app.CACHE_TIMEZONE).isoformat()

                    if column == 'timestamp':
                        return jsonify({
                            'success': True,
                            'data': {
                                'timestamp': timestamp_value,
                                column: timestamp_value,
                            },
                        })

                    if column in metrics and metrics.get(column) is not None:
                        return jsonify({
                            'success': True,
                            'data': {
                                column: metrics.get(column),
                                'timestamp': timestamp_value,
                            },
                        })
            except Exception as active_target_error:
                logger.debug(f"Active target override skipped in /api/data/{column}: {active_target_error}")
            
            # Access CACHE_TIMEZONE through app
            current_time = datetime.now(app.CACHE_TIMEZONE)

            # Special handling for ups_realpower_days
            if column == 'ups_realpower_days':
                UPSDynamicData = get_ups_model()
                # Query to find the last non-null and non-zero value
                last_value = UPSDynamicData.query\
                    .filter(UPSDynamicData.ups_realpower_days.isnot(None))\
                    .filter(UPSDynamicData.ups_realpower_days != 0)\
                    .order_by(UPSDynamicData.timestamp_utc.desc())\
                    .first()
                
                if last_value:
                    value = getattr(last_value, column)
                    timestamp = format_datetime_tz(last_value.timestamp_utc).isoformat()
                    return jsonify({
                        'success': True,
                        'data': {
                            column: float(value),
                            'timestamp': timestamp
                        }
                    })

            # If the requested column is timestamp, return the current timestamp
            if column == 'timestamp':
                return jsonify({
                    'success': True,
                    'data': {
                        'timestamp': current_time.isoformat(),
                        column: current_time.isoformat()
                    }
                })

            # First check in dynamic data
            UPSDynamicData = get_ups_model()
            dynamic_data = UPSDynamicData.query.order_by(UPSDynamicData.timestamp_utc.desc()).first()
            
            if dynamic_data and hasattr(dynamic_data, column):
                value = getattr(dynamic_data, column)
                if value is not None:
                    # Format the value based on type
                    if isinstance(value, datetime):
                        value = format_datetime_tz(value).isoformat()
                    elif isinstance(value, (float, int)):
                        value = float(value) if isinstance(value, float) else int(value)
                    else:
                        value = str(value)

                    # Ensure the timestamp is in the correct timezone
                    timestamp = format_datetime_tz(dynamic_data.timestamp_utc).isoformat()
                    
                    return jsonify({
                        'success': True,
                        'data': {
                            column: value,
                            'timestamp': timestamp
                        }
                    })

            # If not found in dynamic data, check in static data
            UPSStaticData = create_static_model()
            static_data = UPSStaticData.query.first()
            
            if static_data and hasattr(static_data, column):
                value = getattr(static_data, column)
                if value is not None:
                    # Format the value based on type
                    if isinstance(value, datetime):
                        value = format_datetime_tz(value).isoformat()
                    elif isinstance(value, (float, int)):
                        value = float(value) if isinstance(value, float) else int(value)
                    else:
                        value = str(value)

                    # Use the timestamp of the static data if available, otherwise use the current timestamp
                    timestamp = (format_datetime_tz(static_data.timestamp_utc) if hasattr(static_data, 'timestamp_utc') 
                               else current_time).isoformat()
                    
                    return jsonify({
                        'success': True,
                        'data': {
                            column: value,
                            'timestamp': timestamp
                        }
                    })
            
            # Special handling for ups_realpower_hrs
            if column == 'ups_realpower_hrs' and dynamic_data:
                value = get_realpower_hrs(dynamic_data)
                timestamp = format_datetime_tz(dynamic_data.timestamp_utc).isoformat()
                return jsonify({
                    'success': True,
                    'data': {
                        column: value,
                        'timestamp': timestamp
                    }
                })
            
            # If the column is not found, return 404
            logger.warning(f"Column {column} not found in either dynamic or static data")
            return jsonify({
                'success': False,
                'error': f'Column {column} not found or has no value',
                'data': {
                    column: None,
                    'timestamp': current_time.isoformat()
                }
            }), 404
            
        except Exception as e:
            logger.error(f"Error getting column {column}: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e),
                'data': {
                    column: None,
                    'timestamp': datetime.now(app.CACHE_TIMEZONE).isoformat()
                }
            }), 500

    @app.route('/health')
    def health_check():
        """ Checks the system status"""
        try:
            UPSDynamicData = get_ups_model()
            # Access CACHE_TIMEZONE through app
            current_time = datetime.now(app.CACHE_TIMEZONE)
            
            last_record = UPSDynamicData.query.order_by(UPSDynamicData.timestamp_utc.desc()).first()
            
            status = {
                'success': True,
                'timestamp': current_time.isoformat(),
                'database': {
                    'status': True if last_record else False,
                    'last_update': last_record.timestamp_utc.isoformat() if last_record else None,
                    'record_count': UPSDynamicData.query.count()
                }
            }
            
            # Check NUT service
            try:
                data = get_ups_data()
                status['nut_service'] = {
                    'status': True if data else False,
                    'ups_status': getattr(data, 'ups_status', 'unknown') if data else 'unknown',
                    'model': getattr(data, 'device_model', 'unknown') if data else 'unknown'
                }
            except Exception as e:
                status['nut_service'] = {
                    'status': False,
                    'error': str(e)
                }
            
            return jsonify(status)
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/settings/<filename>', methods=['POST'])
    def save_settings(filename):
        """Saves the settings in a JSON file"""
        if not filename.endswith('.json'):
            return jsonify({'error': 'Invalid file type. Only JSON files are allowed'}), 400

        try:
            file_path = os.path.join(SETTINGS_DIR, filename)
            if not os.path.realpath(file_path).startswith(os.path.realpath(SETTINGS_DIR)):
                return jsonify({'error': 'Invalid file path'}), 400

            try:
                with open(file_path, 'r') as f:
                    existing_data = json.load(f)
            except FileNotFoundError:
                existing_data = {}

            new_data = request.get_json()
            if new_data is None:
                return jsonify({'error': 'No JSON data provided'}), 400

            existing_data.update(new_data)
            os.makedirs(SETTINGS_DIR, exist_ok=True)
            
            with open(file_path, 'w') as f:
                json.dump(existing_data, f, indent=4)
            
            return jsonify({'status': 'success'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/system_stats', methods=['GET'])
    def system_stats():
        """API endpoint for system statistics (CPU, RAM)"""
        try:
            import psutil
            
            # Get system stats using psutil
            cpu = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory()
            
            # Return JSON response
            return jsonify({
                'cpu': cpu,
                'ram_total': memory.total,
                'ram_used': memory.used,
                'ram_percent': memory.percent
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/internal/ws_event', methods=['POST'])
    def internal_ws_event():
        """
        Internal endpoint to receive events from non-Flask components and
        forward them to WebSocket clients.
        
        This allows components like the ConnectionMonitor to send events
        to the frontend without directly accessing the WebSocket.
        """
        try:
            remote_ip = str(request.remote_addr or '').strip()
            forwarded_ip = str(request.headers.get('X-Forwarded-For') or '').split(',', 1)[0].strip()

            trusted_local = False
            for candidate in (remote_ip, forwarded_ip):
                if not candidate:
                    continue
                try:
                    if ipaddress.ip_address(candidate).is_loopback:
                        trusted_local = True
                        break
                except ValueError:
                    continue

            if not trusted_local:
                current_app.logger.warning(
                    "Rejected non-local /internal/ws_event request from remote_addr=%s forwarded_for=%s",
                    remote_ip,
                    forwarded_ip or '-',
                )
                return jsonify({"success": False, "message": "Forbidden"}), 403

            data = request.json
            if not data:
                return jsonify({"success": False, "message": "No data provided"}), 400
            
            event_type = data.get('event')
            if not event_type:
                return jsonify({"success": False, "message": "No event type provided"}), 400
            
            # Log the received event
            current_app.logger.info(f"Received internal event: {event_type}")
            
            # For USB disconnect events, emit a special event
            if event_type == 'usb_disconnect':
                # Add the usb_disconnect flag to data
                data['is_usb_disconnect'] = True
                
                # Emit via WebSocket
                emit('usb_disconnect', data, namespace='/', broadcast=True)
                
                # Also emit as a regular cache update with the flag set
                emit('cache_update', data, namespace='/', broadcast=True)
                
                current_app.logger.info(f"Forwarded USB disconnect event to WebSocket clients")
            else:
                # For other events, just forward them as is
                emit(event_type, data, namespace='/', broadcast=True)
                
            return jsonify({"success": True}), 200
            
        except Exception as e:
            current_app.logger.error(f"Error processing internal event: {str(e)}")
            return jsonify({"success": False, "message": str(e)}), 500

    return app

def format_datetime_tz(dt):
    """
    Format datetime with timezone.
    
    Note: This function should be called within a Flask request context.
    """
    if dt is None:
        return None
    # Get timezone from Flask current_app
    from flask import current_app
    tz = current_app.CACHE_TIMEZONE
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt

def get_realpower_hrs(dynamic_data):
    """Helper function to calculate ups_realpower_hrs if not present"""
    try:
        # First try to get the value directly
        if hasattr(dynamic_data, 'ups_realpower_hrs'):
            value = getattr(dynamic_data, 'ups_realpower_hrs')
            if value is not None:
                return float(value)
        
        # If not available, calculate from realpower and load
        realpower = getattr(dynamic_data, 'ups_realpower_nominal', None)
        load = getattr(dynamic_data, 'ups_load', None)
        
        if realpower is not None and load is not None:
            try:
                realpower = float(realpower)
                load = float(load)
                return (realpower * load) / 100.0
            except (ValueError, TypeError):
                logger.error("Error converting realpower or load to float")
                return 0.0
                
        logger.warning("Missing required attributes for ups_realpower_hrs calculation")
        return 0.0
        
    except Exception as e:
        logger.error(f"Error in get_realpower_hrs: {str(e)}")
        return 0.0 
