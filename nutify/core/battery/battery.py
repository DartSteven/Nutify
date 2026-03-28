"""Battery Module.

Implements core runtime logic and helpers used by this feature.
"""

from datetime import datetime, timedelta
import logging
from ..db.ups import (
    db, get_ups_data, get_historical_data, get_supported_value, get_ups_model,
    UPSEvent
)
from sqlalchemy import func
import pytz
from flask import current_app
from core.settings import parse_time_format
from core.logger import battery_logger as logger

logger.info("🔋 Initializing battery")

POTENTIAL_BATTERY_METRICS = [
    'battery_charge',
    'battery_voltage', 
    'battery_runtime',
    'battery_type',
    'battery_date',
    'battery_mfr_date',
    'battery_temperature'
]

def get_available_battery_metrics():
    """
    Discover dynamically which battery metrics are available
    Returns: dict with available metrics and their latest values
    """
    try:
        UPSDynamicData = get_ups_model()
        available_metrics = {}
        
        # Log of raw data from the UPS
        ups_data = get_ups_data()
        logger.debug(f"🔍 Raw UPS data: {ups_data.__dict__}")
        
        # Complete list of possible battery metrics
        battery_metrics = [
            'battery_charge', 'battery_charge_low', 'battery_charge_warning',
            'battery_voltage', 'battery_voltage_nominal', 'battery_current',
            'battery_temperature', 'battery_runtime', 'battery_runtime_low',
            'battery_alarm_threshold', 'battery_date', 'battery_type',
            'battery_mfr_date', 'battery_packs', 'battery_packs_external',
            'battery_protection'
        ]
        
        # List of metrics that should be converted to float
        numeric_metrics = [
            'battery_charge', 'battery_charge_low', 'battery_charge_warning',
            'battery_voltage', 'battery_voltage_nominal', 'battery_current',
            'battery_temperature', 'battery_runtime', 'battery_runtime_low',
            'battery_alarm_threshold'
        ]
        
        # Check which are actually available
        for metric in battery_metrics:
            if hasattr(UPSDynamicData, metric):
                latest = UPSDynamicData.query.filter(
                    getattr(UPSDynamicData, metric).isnot(None)
                ).order_by(UPSDynamicData.timestamp_utc.desc()).first()
                
                if latest:
                    # Retrieve the value
                    value = getattr(latest, metric)
                    
                    # Convert numeric metrics to float
                    if metric in numeric_metrics and value is not None:
                        try:
                            value = float(value)
                        except (ValueError, TypeError) as ex:
                            logger.warning(f"Unable to convert {metric} to float: {ex}. Value: {value}")
                    
                    # If the metric is battery_date or battery_mfr_date, convert it to string
                    if metric in ['battery_date', 'battery_mfr_date'] and value is not None:
                        try:
                            value = value.isoformat()
                        except Exception as ex:
                            logger.warning(f"Unable to format {metric}: {ex}")
                    logger.debug(f"🔍 Found metric {metric}: {value}")
                    available_metrics[metric] = value
        
        # Fallback: if battery_date or battery_mfr_date not found in available_metrics,
        # use the value from ups_data.__dict__ if present
        for key in ['battery_date', 'battery_mfr_date']:
            if key not in available_metrics and key in ups_data.__dict__:
                value = ups_data.__dict__[key]
                if hasattr(value, 'isoformat'):
                    try:
                        value = value.isoformat()
                    except Exception as ex:
                        logger.warning(f"Unable to format {key}: {ex}")
                logger.debug(f"🔍 Fallback for metric {key}: {value}")
                available_metrics[key] = value
        
        return available_metrics
    
    except Exception as e:
        logger.error(f"Error getting available battery metrics: {str(e)}")
        return {}

def get_battery_stats(period='day', from_time=None, to_time=None, selected_date=None):
    """
    Calculate battery statistics for the specified period
    """
    try:
        tz = current_app.CACHE_TIMEZONE
        now = datetime.now(tz)
        logger.debug(f"Getting battery stats for period={period}, from={from_time}, to={to_time}")
        
        # Standardize time range calculation
        if period == 'day' and selected_date is not None:
            # selected_date already has the timezone, use directly replace
            start_time = selected_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = selected_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            logger.debug(f"Select Day stats range - Start: {start_time}, End: {end_time}")
        elif period == 'day' and from_time and to_time:
            today = now.date()
            
            # Parse time strings with timezone offset (format: HH:MM±HHMM)
            try:
                # Check if there's a timezone offset in the strings
                from_time_obj, from_tz_offset = parse_time_with_offset(from_time)
                to_time_obj, to_tz_offset = parse_time_with_offset(to_time)
                
                # Create datetime objects with timezone info
                start_time = datetime.combine(today, from_time_obj)
                end_time = datetime.combine(today, to_time_obj)
                
                # Special case for "00:00" start time - ensure it's exactly midnight of current day
                is_midnight_start = from_time_obj.hour == 0 and from_time_obj.minute == 0
                
                # Apply timezone offsets if they were provided
                if from_tz_offset:
                    start_time = start_time.replace(tzinfo=from_tz_offset)
                else:
                    start_time = tz.localize(start_time)
                    
                if to_tz_offset:
                    end_time = end_time.replace(tzinfo=to_tz_offset)
                else:
                    end_time = tz.localize(end_time)
                
                # Log times for debugging
                logger.debug(f"Original time range with timezone info - Start: {start_time}, End: {end_time}")
                
                # For "00:00" start time, ensure we get exactly midnight in the configured timezone
                if is_midnight_start:
                    midnight = datetime.combine(today, datetime.min.time())
                    midnight_tz = tz.localize(midnight)
                    logger.debug(f"Adjusted to exact midnight: {midnight_tz}")
                    start_time = midnight_tz
            except Exception as e:
                # Fallback to original parsing if new format fails
                logger.warning(f"Error parsing time with offset: {e}, falling back to simple parsing")
                from_time_obj = parse_time_format(from_time, datetime.strptime("00:00", '%H:%M').time())
                to_time_obj = parse_time_format(to_time, now.time())
                start_time = tz.localize(datetime.combine(today, from_time_obj))
                end_time = tz.localize(datetime.combine(today, to_time_obj))
        elif period == 'range' and from_time and to_time:
            start_time = tz.localize(datetime.strptime(from_time, '%Y-%m-%d'))
            end_time = tz.localize(datetime.strptime(to_time, '%Y-%m-%d')).replace(
                hour=23, minute=59, second=59, microsecond=999999)
        else:
            start_time = now - timedelta(days=1)
            end_time = now

        logger.debug(f"Query period: {start_time} to {end_time}")

        # Get the UPS model - with proper error handling
        UPSDynamicData = None
        try:
            UPSDynamicData = get_ups_model()
            if UPSDynamicData is None:
                logger.error("Failed to get UPS model - model is None")
                return _create_default_battery_stats()
        except Exception as e:
            logger.error(f"Error getting UPS model: {str(e)}")
            return _create_default_battery_stats()
        
        # Query with the correct period - with error handling for database issues
        try:
            query = UPSDynamicData.query.filter(
                UPSDynamicData.timestamp_utc >= start_time,
                UPSDynamicData.timestamp_utc <= end_time
            )
        except Exception as e:
            logger.error(f"Database query error: {str(e)}")
            return _create_default_battery_stats()
        
        # Initialize all possible metrics with default values
        stats = {
            'battery_charge': {'min': None, 'max': None, 'avg': None},
            'battery_charge_low': {'min': None, 'max': None, 'avg': None},
            'battery_charge_warning': {'min': None, 'max': None, 'avg': None},
            'battery_voltage': {'min': None, 'max': None, 'avg': None},
            'battery_voltage_nominal': {'min': None, 'max': None, 'avg': None},
            'battery_current': {'min': None, 'max': None, 'avg': None},
            'battery_temperature': {'min': None, 'max': None, 'avg': None},
            'battery_runtime': {'min': None, 'max': None, 'avg': None},
            'battery_runtime_low': {'min': None, 'max': None, 'avg': None},
            'battery_alarm_threshold': {'min': None, 'max': None, 'avg': None}
        }
        
        # Calculate statistics only for available metrics
        has_valid_data = False
        try:
            for metric in stats.keys():
                if hasattr(UPSDynamicData, metric):
                    column = getattr(UPSDynamicData, metric)
                    result = query.with_entities(
                        func.min(column).label('min'),
                        func.max(column).label('max'),
                        func.avg(column).label('avg')
                    ).filter(column.isnot(None)).first()
                    
                    if result and result.min is not None:
                        # Convert all values to float for consistent handling
                        try:
                            stats[metric] = {
                                'min': float(result.min) if result.min is not None else None,
                                'max': float(result.max) if result.max is not None else None,
                                'avg': float(result.avg) if result.avg is not None else None,
                                'available': True
                            }
                            
                            # Add current value from latest data if available
                            try:
                                latest = UPSDynamicData.query.filter(
                                    getattr(UPSDynamicData, metric).isnot(None)
                                ).order_by(UPSDynamicData.timestamp_utc.desc()).first()
                                
                                if latest:
                                    stats[metric]['current'] = float(getattr(latest, metric))
                                else:
                                    stats[metric]['current'] = stats[metric]['avg']
                            except Exception as e:
                                logger.warning(f"Error getting current value for {metric}: {str(e)}")
                                stats[metric]['current'] = stats[metric]['avg']
                            
                            has_valid_data = True
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Could not convert {metric} statistic to float: {e}")
                            stats[metric] = {
                                'min': result.min,
                                'max': result.max,
                                'avg': result.avg,
                                'current': result.avg,
                                'available': True
                            }
        except Exception as e:
            logger.error(f"Error calculating metric statistics: {str(e)}")
            
        # If we have no valid data at all, try to get at least the latest values
        if not has_valid_data:
            try:
                logger.warning("No valid statistics found, trying to get latest values")
                latest_data = UPSDynamicData.query.order_by(UPSDynamicData.timestamp_utc.desc()).first()
                
                if latest_data:
                    for metric in stats.keys():
                        if hasattr(latest_data, metric) and getattr(latest_data, metric) is not None:
                            try:
                                value = float(getattr(latest_data, metric))
                                stats[metric] = {
                                    'min': value,
                                    'max': value,
                                    'avg': value,
                                    'current': value,
                                    'available': True
                                }
                                has_valid_data = True
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Could not convert latest {metric} to float: {e}")
            except Exception as e:
                logger.error(f"Error getting latest values: {str(e)}")
        
        # Get battery events within the time period
        events_data = {
            'count': 0,
            'total_duration': 0,
            'longest_duration': 0,
            'available': False
        }
        
        try:
            # Try direct import first (best method)
            try:
                from core.db.ups import UPSEvent
                if UPSEvent is None:
                    raise ImportError("UPSEvent model is None")
                events = UPSEvent.query.filter(
                    UPSEvent.timestamp_utc >= start_time,
                    UPSEvent.timestamp_utc <= end_time,
                    UPSEvent.event_type.in_(['ONBATT', 'LOWBATT'])
                ).order_by(UPSEvent.timestamp_utc.asc()).all()
                
                # Calculate event statistics
                if events:
                    events_data['count'] = len(events)
                    events_data['available'] = True
                    
                    # Calculate durations
                    paired_events = []
                    open_event = None
                    for event in events:
                        if event.event_type == 'ONBATT':
                            open_event = event
                        elif event.event_type == 'ONLINE' and open_event:
                            duration = (event.timestamp_utc - open_event.timestamp_utc).total_seconds()
                            paired_events.append({
                                'start': open_event.timestamp_utc,
                                'end': event.timestamp_utc,
                                'duration': duration
                            })
                            events_data['total_duration'] += duration
                            if duration > events_data['longest_duration']:
                                events_data['longest_duration'] = duration
                    
                    # Check if there's an open event at the end of the period
                    if open_event:
                        duration = (end_time - open_event.timestamp_utc).total_seconds()
                        paired_events.append({
                            'start': open_event.timestamp_utc,
                            'end': end_time,
                            'duration': duration
                        })
                        events_data['total_duration'] += duration
                        if duration > events_data['longest_duration']:
                            events_data['longest_duration'] = duration
                
            except (ImportError, AttributeError) as e:
                logger.warning(f"Direct UPSEvent query failed: {str(e)}")
                # Fallback: try to get UPSEvent from db.ModelClasses
                try:
                    from core.db.ups import db
                    UPSEvent = db.ModelClasses.UPSEvent
                    events = UPSEvent.query.filter(
                        UPSEvent.timestamp_utc >= start_time,
                        UPSEvent.timestamp_utc <= end_time,
                        UPSEvent.event_type.in_(['ONBATT', 'LOWBATT'])
                    ).order_by(UPSEvent.timestamp_utc.asc()).all()
                    logger.debug(f"Retrieved {len(events)} events using db.ModelClasses.UPSEvent")
                except Exception as e2:
                    logger.warning(f"ModelClasses.UPSEvent query failed: {str(e2)}")
                    events = []
        except Exception as e:
            logger.error(f"Error getting battery events: {str(e)}")
            events = []
            
        # Add events data to the stats
        stats['events'] = events_data
        
        logger.debug(f"Stats calculated: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Error calculating battery stats: {str(e)}")
        return _create_default_battery_stats()

def _create_default_battery_stats():
    """
    Create default battery statistics with zero values
    """
    return {
        'battery_charge': {'min': 0.0, 'max': 0.0, 'avg': 0.0, 'current': 0.0, 'available': False},
        'battery_charge_low': {'min': 0.0, 'max': 0.0, 'avg': 0.0, 'current': 0.0, 'available': False},
        'battery_charge_warning': {'min': 0.0, 'max': 0.0, 'avg': 0.0, 'current': 0.0, 'available': False},
        'battery_voltage': {'min': 0.0, 'max': 0.0, 'avg': 0.0, 'current': 0.0, 'available': False},
        'battery_voltage_nominal': {'min': 0.0, 'max': 0.0, 'avg': 0.0, 'current': 0.0, 'available': False},
        'battery_current': {'min': 0.0, 'max': 0.0, 'avg': 0.0, 'current': 0.0, 'available': False},
        'battery_temperature': {'min': 0.0, 'max': 0.0, 'avg': 0.0, 'current': 0.0, 'available': False},
        'battery_runtime': {'min': 0.0, 'max': 0.0, 'avg': 0.0, 'current': 0.0, 'available': False},
        'battery_runtime_low': {'min': 0.0, 'max': 0.0, 'avg': 0.0, 'current': 0.0, 'available': False},
        'battery_alarm_threshold': {'min': 0.0, 'max': 0.0, 'avg': 0.0, 'current': 0.0, 'available': False},
        'events': {
            'count': 0,
            'total_duration': 0.0,
            'longest_duration': 0.0,
            'available': False
        }
    }

def get_battery_history(period='day', from_date=None, to_date=None, selected_date=None, today_mode=None):
    """
    Retrieve the battery history data for graphs
    Args:
        period: 'day', 'range', 'today'
        from_date: initial date (for period='range' or time for period='day')
        to_date: final date (for period='range' or time for period='day')
        selected_date: specific date for day view
        today_mode: flag to indicate this is a "Today" mode request
    """
    try:
        logger.debug(f"🔍 get_battery_history called with: period={period}, from={from_date}, to={to_date}, today_mode={today_mode}")
        
        # Get UPS model with error handling
        UPSDynamicData = None
        try:
            UPSDynamicData = get_ups_model()
            if UPSDynamicData is None:
                logger.error("Failed to get UPS model - model is None")
                return _create_empty_battery_history()
        except Exception as e:
            logger.error(f"Error getting UPS model: {str(e)}")
            return _create_empty_battery_history()
        
        tz = current_app.CACHE_TIMEZONE
        now = datetime.now(tz)
        today = now.date()
        
        # Set time range based on period and parameters
        if period == 'today' or today_mode:
            # For TODAY explicitly - use data from 00:00 today to current time
            start_time = tz.localize(datetime.combine(today, datetime.min.time()))
            end_time = now
            target_points = 96
            logger.debug(f"TODAY mode - Start: {start_time}, End: {end_time}")
        elif period == 'day' and selected_date is not None:
            # Use strict midnight start for selected day
            start_time = selected_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = selected_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            target_points = 96  # 96 points = 1 point every 15 minutes
            logger.debug(f"Select Day history range - Start: {start_time}, End: {end_time}")
        elif period == 'day' and from_date and to_date:
            # Custom time range within the current day
            try:
                # Parse from_date and to_date as time strings
                from_time_obj, from_tz_offset = parse_time_with_offset(from_date)
                to_time_obj, to_tz_offset = parse_time_with_offset(to_date)
                
                # Create full datetime objects for today with the specified times
                start_time = datetime.combine(today, from_time_obj)
                start_time = tz.localize(start_time) if not from_tz_offset else start_time.replace(tzinfo=from_tz_offset)
                
                end_time = datetime.combine(today, to_time_obj)
                end_time = tz.localize(end_time) if not to_tz_offset else end_time.replace(tzinfo=to_tz_offset)
                
                logger.debug(f"Custom day time range - Start: {start_time}, End: {end_time}")
            except Exception as e:
                logger.error(f"Error parsing time range: {e}, using full day")
                # Fallback to full day
                start_time = datetime.combine(today, datetime.min.time())
                start_time = tz.localize(start_time)
                end_time = now
            
            target_points = 96
        elif period == 'range' and from_date and to_date:
            logger.debug(f"Processing date range {from_date} - {to_date}")
            start_time = tz.localize(datetime.strptime(from_date, '%Y-%m-%d'))
            end_time = tz.localize(datetime.strptime(to_date, '%Y-%m-%d')).replace(
                hour=23, minute=59, second=59, microsecond=999999)
            target_points = 180  # One point every 4 hours (or adjust as needed)
        elif period == 'realtime':
            logger.debug("Processing realtime period for history, using last 30 seconds")
            start_time = now - timedelta(seconds=30)
            end_time = now
            target_points = 30
        else:
            # Fallback: if no period-specific parameters are provided, use last 24 hours
            start_time = now - timedelta(days=1)
            end_time = now
            target_points = 96
            logger.debug(f"Fallback to last 24 hours - Start: {start_time}, End: {end_time}")

        # Initialize history with empty lists for each metric
        history = {
            'battery_charge': [],
            'battery_runtime': [],
            'battery_voltage': [],
            'battery_temperature': [],
            'events': []
        }
        
        metrics = [
            'battery_charge',
            'battery_runtime', 
            'battery_voltage',
            'battery_temperature'
        ]
        
        has_any_data = False
        
        # Convert local start/end times to UTC for querying
        start_time_utc = start_time.astimezone(pytz.utc)
        end_time_utc = end_time.astimezone(pytz.utc)
        logger.debug(f"Querying database with UTC range: {start_time_utc} to {end_time_utc}")
        
        for metric in metrics:
            try:
                if hasattr(UPSDynamicData, metric):
                    # Query for data points in the given time range using UTC times
                    data_points = UPSDynamicData.query.filter(
                        UPSDynamicData.timestamp_utc >= start_time_utc, # Use UTC start time
                        UPSDynamicData.timestamp_utc <= end_time_utc,  # Use UTC end time
                        getattr(UPSDynamicData, metric).isnot(None)
                    ).order_by(UPSDynamicData.timestamp_utc.asc()).all()
                    
                    logger.debug(f"📊 Metric {metric}: found {len(data_points)} records")
                    
                    if data_points:
                        has_any_data = True
                        # Log first and last data points
                        first_timestamp = data_points[0].timestamp_utc
                        last_timestamp = data_points[-1].timestamp_utc
                        first_value = getattr(data_points[0], metric)
                        last_value = getattr(data_points[-1], metric)
                        logger.debug(f"🔢 {metric}: first at {first_timestamp}, last at {last_timestamp}")
                        logger.debug(f"🔢 {metric}: first value={first_value}, last value={last_value}")
                        
                        # --- START: Modified Sampling Logic ---
                        points_to_format = []
                        original_length = len(data_points)
                        
                        # Skip sampling for 'today' view to ensure latest data is included
                        if period == 'today':
                            points_to_format = data_points
                            logger.debug(f"Skipping sampling for 'today' view. Using all {original_length} points for {metric}.")
                        elif original_length > target_points:
                            # Basic sampling for other views, ensuring last point is kept
                            step = original_length // target_points
                            # Ensure step is at least 1
                            step = max(1, step)
                            
                            # Take every 'step' point
                            points_to_format = data_points[::step]
                            
                            # Explicitly add the last point if it wasn't included by the sampling
                            if data_points[-1] not in points_to_format:
                                points_to_format.append(data_points[-1])
                                logger.debug(f"Sampling {metric}: Added last point explicitly.")
                            
                            logger.debug(f"Sampling {metric}: Original={original_length}, Target={target_points}, Step={step}, Result={len(points_to_format)} points.")
                        else:
                            # No sampling needed if fewer points than target
                            points_to_format = data_points
                        # --- END: Modified Sampling Logic ---

                        # Format the data
                        for point in points_to_format: # Iterate over the potentially sampled list
                            value = getattr(point, metric)
                            if value is not None:
                                # Keep all values in original units
                                value = float(value)
                                
                                # --- START TIMESTAMP CONVERSION ---
                                timestamp_utc_naive = point.timestamp_utc
                                if timestamp_utc_naive is None: continue
                                
                                # Force UTC timezone info and then convert to local
                                timestamp_utc_aware = timestamp_utc_naive.replace(tzinfo=pytz.utc)
                                timestamp_local = timestamp_utc_aware.astimezone(current_app.CACHE_TIMEZONE)
                                timestamp_local_ms = timestamp_local.timestamp() * 1000
                                # --- END TIMESTAMP CONVERSION ---

                                # --- ADD DEBUG LOGGING --- 
                                logger.debug(f"  Point for {metric}: UTC={timestamp_utc_aware.isoformat()} (Hour: {timestamp_utc_aware.hour}), Local={timestamp_local.isoformat()} (Hour: {timestamp_local.hour}), Value={value}")
                                # --- END DEBUG LOGGING --- 
                                
                                history[metric].append({
                                    # Use local timestamp in ms for 'x' axis in frontend
                                    'timestamp': timestamp_local_ms, 
                                    'value': value
                                    # Optionally keep iso for debug/reference if needed
                                    # 'timestamp_utc_iso': timestamp_utc_aware.isoformat(),
                                    # 'timestamp_local_iso': timestamp_local.isoformat()
                                })
                        
                        # Sort by timestamp (now local ms) to ensure correct order
                        history[metric].sort(key=lambda x: x['timestamp'])
                        
                        # REMOVED redundant check after formatting
                else:
                    logger.debug(f"⚠️ Metric {metric} not available in UPS model")
            except Exception as e:
                logger.error(f"Error retrieving data for metric {metric}: {str(e)}")
        
        # If no data was found for any metrics, create synthetic data
        if not has_any_data:
            logger.warning("No battery history data found for any metric, creating synthetic data")
            history = _create_synthetic_battery_history(start_time, end_time, target_points)
            return history

        # Try to get UPSEvent model from db.ModelClasses
        UPSEvent = None
        try:
            # First try direct import
            try:
                from ..db.ups import UPSEvent
                if UPSEvent:
                    logger.debug("Successfully initialized UPSEvent model from direct import")
            except Exception as e:
                logger.warning(f"Could not import UPSEvent directly: {str(e)}")
                UPSEvent = None
                
            # If direct import fails, try ModelClasses
            if UPSEvent is None and hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'UPSEvent'):
                UPSEvent = db.ModelClasses.UPSEvent
                logger.debug("Successfully initialized UPSEvent model from db.ModelClasses")
            
            if UPSEvent is None:
                logger.error("UPSEvent model not available in db.ModelClasses")
                history['events'] = []
                return history
        except Exception as e:
            logger.error(f"Failed to get UPSEvent model: {str(e)}")
            history['events'] = []
            return history
        
        # Battery events (remain all because they are discrete events)
        events = []
        try:
            # Use the same UTC start/end times for event query
            events = UPSEvent.query.filter(
                UPSEvent.timestamp_utc >= start_time_utc, # Use UTC start time
                UPSEvent.timestamp_utc <= end_time_utc,  # Use UTC end time
                UPSEvent.event_type.in_(['ONBATT', 'LOWBATT', 'ONLINE'])
            ).order_by(UPSEvent.timestamp_utc.asc()).all()
        except Exception as e:
            logger.error(f"Error querying battery events: {str(e)}")
            events = []

        try:
            history['events'] = [{
                'type': event.event_type,
                'start_time': event.timestamp_utc.isoformat(),
                'end_time': event.timestamp_utc_end.isoformat() if hasattr(event, 'timestamp_utc_end') and event.timestamp_utc_end else event.timestamp_utc.isoformat()
            } for event in events]
        except Exception as e:
            logger.error(f"Error formatting battery events: {str(e)}")
            history['events'] = []

        logger.debug(f"📈 Available metrics in the response: {list(history.keys())}")
        return history
        
    except Exception as e:
        logger.error(f"❌ Error in get_battery_history: {str(e)}", exc_info=True)
        return _create_empty_battery_history()

def _create_empty_battery_history():
    """Create an empty battery history structure for when no data is available"""
    return {
        'battery_charge': [],
        'battery_runtime': [],
        'battery_voltage': [],
        'battery_temperature': [],
        'events': []
    }

def _create_synthetic_battery_history(start_time, end_time, num_points):
    """Create synthetic battery history data when real data is not available"""
    history = {
        'battery_charge': [],
        'battery_runtime': [],
        'battery_voltage': [],
        'battery_temperature': [],
        'events': []
    }
    
    # Get default values for metrics
    default_stats = _create_default_battery_stats()
    
    # Calculate time interval between points
    duration = (end_time - start_time).total_seconds()
    interval = duration / (num_points - 1) if num_points > 1 else duration
    
    # Generate points with slight random variations
    for i in range(num_points):
        point_time = start_time + timedelta(seconds=(i * interval))
        
        # Battery charge (100% with slight variations)
        charge_value = default_stats['battery_charge']['avg']
        history['battery_charge'].append({
            'timestamp': point_time.isoformat(),
            'value': charge_value
        })
        
        # Runtime (with slight upward trend) - in seconds
        runtime_value = default_stats['battery_runtime']['avg']  # Value in seconds
        runtime_with_trend = runtime_value * (1.0 + (i / (num_points * 10)))  # Slight upward trend
        history['battery_runtime'].append({
            'timestamp': point_time.isoformat(),
            'value': runtime_with_trend
        })
        
        # Voltage (stable with tiny variations)
        voltage_value = default_stats['battery_voltage']['avg']
        history['battery_voltage'].append({
            'timestamp': point_time.isoformat(),
            'value': voltage_value
        })
        
        # Temperature (stable with tiny variations)
        temp_value = default_stats['battery_temperature']['avg'] 
        history['battery_temperature'].append({
            'timestamp': point_time.isoformat(),
            'value': temp_value
        })
    
    logger.debug(f"Created synthetic battery history with {num_points} data points per metric")
    return history

def calculate_battery_health(metrics):
    """
    Calculate the actual battery health based on available metrics
    Returns: battery health percentage (0-100) or None if there is not enough data
    """
    try:
        health_components = []
        total_weight = 0
        
        # 1. Voltage (40% weight if available)
        if all(key in metrics for key in ['battery_voltage', 'battery_voltage_nominal']):
            try:
                voltage_ratio = (float(metrics['battery_voltage']) / float(metrics['battery_voltage_nominal']))
                voltage_health = min(100, voltage_ratio * 100)
                health_components.append(('voltage', voltage_health, 0.4))
                total_weight += 0.4
                logger.debug(f"Voltage Health: {voltage_health:.1f}% (Current: {metrics['battery_voltage']}V, Nominal: {metrics['battery_voltage_nominal']}V)")
            except (ValueError, ZeroDivisionError) as e:
                logger.warning(f"Could not calculate voltage health: {str(e)}")

        # 2. Runtime (40% weight if available)
        if all(key in metrics for key in ['battery_runtime', 'battery_runtime_low']):
            try:
                runtime_ratio = float(metrics['battery_runtime']) / float(metrics['battery_runtime_low'])
                runtime_health = min(100, runtime_ratio * 50)
                health_components.append(('runtime', runtime_health, 0.4))
                total_weight += 0.4
                logger.debug(f"Runtime Health: {runtime_health:.1f}% (Current: {metrics['battery_runtime']}s, Low: {metrics['battery_runtime_low']}s)")
            except (ValueError, ZeroDivisionError) as e:
                logger.warning(f"Could not calculate runtime health: {str(e)}")

        # 3. Charge (20% weight if available)
        if 'battery_charge' in metrics:
            try:
                charge_health = float(metrics['battery_charge'])
                health_components.append(('charge', charge_health, 0.2))
                total_weight += 0.2
                logger.debug(f"Charge Health: {charge_health:.1f}%")
            except ValueError as e:
                logger.warning(f"Could not calculate charge health: {str(e)}")

        # If we don't have enough data, return None
        if not health_components or total_weight == 0:
            logger.warning("Not enough data to calculate battery health")
            return None

        # Recalculate weights based on available metrics
        normalized_components = [
            (name, value, weight/total_weight) 
            for name, value, weight in health_components
        ]

        # Final weighted calculation
        health = sum(value * norm_weight for _, value, norm_weight in normalized_components)
        
        # Detailed calculation log
        logger.debug("Battery Health Calculation:")
        for name, value, weight in normalized_components:
            logger.debug(f"  - {name}: {value:.1f}% (weight: {weight:.2f})")
        logger.debug(f"Final Health: {health:.1f}%")

        return round(min(100, max(0, health)), 1)

    except Exception as e:
        logger.error(f"Error calculating battery health: {str(e)}")
        return None

def format_ups_status(status):
    """
    Format UPS status codes into human-readable text.
    
    Args:
        status (str): UPS status code (e.g., 'OL', 'OB', 'LB')
        
    Returns:
        str: Human-readable status text
    """
    if not status:
        return 'Unknown'
    
    states = {
        'OL': 'Online',
        'OB': 'On Battery',
        'LB': 'Low Battery',
        'HB': 'High Battery',
        'RB': 'Replace Battery',
        'CHRG': 'Charging',
        'DISCHRG': 'Discharging',
        'BYPASS': 'Bypass Mode',
        'CAL': 'Calibration',
        'OFF': 'Offline',
        'OVER': 'Overloaded',
        'TRIM': 'Trimming Voltage',
        'BOOST': 'Boosting Voltage'
    }
    
    return ' + '.join([states.get(s, s) for s in status.split()])

def format_battery_type(battery_type):
    """
    Format battery type codes into human-readable text.
    
    Args:
        battery_type (str): Battery type code (e.g., 'PbAc')
        
    Returns:
        str: Human-readable battery type
    """
    if not battery_type:
        return 'Unknown'
    
    types = {
        'PbAc': 'Lead Acid',
        'Li': 'Lithium Ion',
        'LiP': 'Lithium Polymer',
        'NiCd': 'Nickel Cadmium',
        'NiMH': 'Nickel Metal Hydride',
        'SLA': 'Sealed Lead Acid',
        'VRLA': 'Valve Regulated Lead Acid',
        'AGM': 'Absorbed Glass Mat',
        'Gel': 'Gel Cell',
        'Flooded': 'Flooded Lead Acid'
    }
    
    return types.get(battery_type, battery_type)

def calculate_activity_level(event_count, avg_charge, battery_events):
    """
    Calculate the activity level based on various factors
    Returns: 'low', 'medium', or 'high'
    """
    score = 0
    
    # More events = more activity
    if event_count > 1000: score += 3
    elif event_count > 500: score += 2
    elif event_count > 100: score += 1
    
    # Battery events weigh more
    if battery_events > 5: score += 3
    elif battery_events > 2: score += 2
    elif battery_events > 0: score += 1
    
    # Charge variations
    if avg_charge is not None:
        if avg_charge < 50: score += 2
        elif avg_charge < 80: score += 1
    
    if score >= 5: return 'high'
    if score >= 3: return 'medium'
    return 'low'

def parse_time_with_offset(time_str):
    """
    Parse a time string with timezone offset in the format HH:MM±HHMM.
    
    Args:
        time_str: String representing time with optional timezone offset (e.g., "14:30+0200")
    Returns:
        Tuple of (time_obj, timezone_obj or None)
    """
    if not time_str:
        return datetime.now().time(), None
    
    # Check if there's a timezone offset
    tz_offset = None
    time_part = time_str
    
    # Look for +/- followed by 4 digits as timezone offset
    import re
    match = re.search(r'([+-])(\d{2})(\d{2})$', time_str)
    if match:
        sign, hours, minutes = match.groups()
        hours, minutes = int(hours), int(minutes)
        
        # Extract the time part without the timezone
        time_part = time_str[:-5]  # Remove the +HHMM or -HHMM part
        
        # Calculate the total offset in minutes
        total_offset = hours * 60 + minutes
        if sign == '-':
            total_offset = -total_offset
            
        # Create a timezone object with this offset
        tz_offset = pytz.FixedOffset(-total_offset)  # Note: pytz wants opposite sign
        logger.debug(f"Parsed timezone offset: {sign}{hours:02d}:{minutes:02d} from {time_str}")
    
    # Parse the time part
    time_obj = None
    formats = ['%H:%M', '%I:%M %p', '%I:%M%p', '%H.%M', '%I.%M %p']
    
    for fmt in formats:
        try:
            time_obj = datetime.strptime(time_part, fmt).time()
            break
        except ValueError:
            continue
    
    if time_obj is None:
        logger.warning(f"Could not parse time part: {time_part}")
        time_obj = datetime.now().time()
    
    return time_obj, tz_offset 
