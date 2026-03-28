"""
API endpoints for data and table information.
This module provides API endpoints related to UPS data retrieval and table data visualization.
"""
from flask import jsonify, request, current_app
import json
from datetime import datetime
from core.db.ups import (
    db, get_ups_model, get_ups_data, create_static_model, get_supported_value
)
from core.settings import get_ups_realpower_nominal
from core.logger import web_logger as logger

def register_api_routes(app):
    """Register data and table API routes"""
    
    @app.route('/api/data/all')
    def api_data_all():
        """
        Returns all UPS data.
        
        This endpoint retrieves all available UPS data including UPS_REALPOWER_NOMINAL from settings.
        """
        try:
            # Multi-NUT active target override for target-scoped realtime pages.
            try:
                from core.multi_nut.active_target import get_active_target_snapshot_payload

                active_snapshot = get_active_target_snapshot_payload()
                if active_snapshot:
                    metrics = dict(active_snapshot.get('metrics') or {})
                    latest = active_snapshot.get('latest') or {}
                    timestamp_value = latest.get('timestamp_utc')
                    if timestamp_value and 'timestamp' not in metrics:
                        metrics['timestamp'] = timestamp_value

                    nominal_from_snapshot = metrics.get('ups_realpower_nominal')
                    metrics['UPS_REALPOWER_NOMINAL'] = (
                        nominal_from_snapshot
                        if nominal_from_snapshot is not None
                        else get_ups_realpower_nominal()
                    )

                    return jsonify({
                        'success': True,
                        'data': metrics,
                    })
            except Exception as active_target_error:
                logger.debug(f"Active target override skipped in /api/data/all: {active_target_error}")

            data = get_ups_data()

            # Convert the data object to a dictionary
            data_dict = {}
            for key in dir(data):
                if not key.startswith('_') and not callable(getattr(data, key)):
                    data_dict[key] = getattr(data, key)
            
            # Add the UPS_REALPOWER_NOMINAL value
            data_dict['UPS_REALPOWER_NOMINAL'] = get_ups_realpower_nominal()
            
            return jsonify({
                'success': True,
                'data': data_dict
            })
        except Exception as e:
            logger.error(f"Error in api_data_all: {str(e)}")
            return jsonify({
                'success': False,
                'message': str(e)
            })

    @app.route('/api/table/dynamic')
    def get_dynamic_table():
        """
        Returns the dynamic table data.
        
        This endpoint retrieves dynamic UPS data in a tabular format, with options to limit the number of rows.
        """
        try:
            rows = request.args.get('rows', 'all')
            UPSDynamicData = get_ups_model()
            tz = current_app.CACHE_TIMEZONE
            
            query = UPSDynamicData.query.order_by(UPSDynamicData.timestamp_utc.desc())
            
            if rows != 'all':
                try:
                    query = query.limit(int(rows))
                except ValueError:
                    query = query.limit(60)
                    
            data = query.all()
            
            if not data:
                return jsonify({
                    'success': True,
                    'columns': [],
                    'rows': []
                })
            
            columns = [column.name for column in UPSDynamicData.__table__.columns]
            
            rows_data = []
            for row in data:
                item = {}
                for column in columns:
                    try:
                        value = getattr(row, column)
                        if value is None:
                            item[column] = None
                        elif isinstance(value, datetime):
                            value = format_datetime_tz(value)
                            item[column] = value.isoformat()
                        elif isinstance(value, (int, float)):
                            item[column] = float(value) if isinstance(value, float) else int(value)
                        else:
                            item[column] = str(value)
                    except Exception as e:
                        logger.error(f"Error processing column {column}: {str(e)}")
                        item[column] = None
                rows_data.append(item)
                
            logger.debug(f"Returning {len(rows_data)} rows with columns: {columns}")
            
            return jsonify({
                'success': True,
                'columns': columns,
                'rows': rows_data
            })
            
        except Exception as e:
            logger.error(f"Error getting dynamic table: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e),
                'columns': [],
                'rows': []
            }), 500

    @app.route('/api/table/static')
    def get_static_table():
        """
        Returns the static table data.
        
        This endpoint retrieves static UPS configuration data in a tabular format.
        """
        try:
            UPSStaticData = create_static_model()
            data = UPSStaticData.query.first()
            
            if not data:
                return jsonify({
                    'success': True,
                    'columns': [],
                    'rows': []
                })
                
            # Get the columns
            columns = [column.name for column in UPSStaticData.__table__.columns]
            
            # Prepare the data for the response
            row_data = {}
            for column in columns:
                value = getattr(data, column)
                if isinstance(value, datetime):
                    value = value.isoformat()
                row_data[column] = value
                
            return jsonify({
                'success': True,
                'columns': columns,
                'rows': [row_data]
            })
            
        except Exception as e:
            logger.error(f"Error getting static table: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    return app

def format_datetime_tz(dt):
    """Format datetime with timezone"""
    if dt is None:
        return None
    tz = current_app.CACHE_TIMEZONE
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt 
