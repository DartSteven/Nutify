"""Voltage Module.

Implements core runtime logic and helpers used by this feature.
"""

from datetime import datetime, timedelta
from sqlalchemy import func
import pytz
from core.logger import voltage_logger as logger
from core.db.ups import (
    db, get_ups_data, get_historical_data, get_supported_value, get_ups_model
)
from core.settings import parse_time_format
from flask import current_app

logger.info("🔌 Initializing voltage")

def get_available_voltage_metrics():
    """
    Discovers which voltage-related metrics are available from the UPS
    Returns: dict with available metrics and their latest values
    """
    try:
        UPSDynamicData = get_ups_model()
        available_metrics = {}
        
        # List of possible voltage metrics
        voltage_metrics = [
            'input_voltage', 'input_voltage_nominal',
            'output_voltage', 'output_voltage_nominal',
            'ups_load',
            'input_current', 'output_current',
            'input_frequency', 'output_frequency',
            'input_transfer_low', 'input_transfer_high',
            'input_sensitivity'
        ]
        
        # Check which metrics are actually available and have data
        for metric in voltage_metrics:
            if hasattr(UPSDynamicData, metric):
                latest = UPSDynamicData.query.filter(
                    getattr(UPSDynamicData, metric).isnot(None)
                ).order_by(UPSDynamicData.timestamp_utc.desc()).first()
                
                if latest and getattr(latest, metric) is not None:
                    raw_value = getattr(latest, metric)
                    if metric == 'input_sensitivity':
                        available_metrics[metric] = str(raw_value)
                    else:
                        try:
                            available_metrics[metric] = float(raw_value)
                        except (ValueError, TypeError):
                            continue
        
        if hasattr(latest, 'ups_status'):
            nut_status = str(latest.ups_status).split()[0]  # Take the first status code
            available_metrics['ups_status'] = nut_status  # Ex: 'OL', 'OB', 'LB', etc.
        
        if hasattr(UPSDynamicData, 'ups_load'):
            available_metrics['ups_load'] = latest.ups_load
        
        return available_metrics
    
    except Exception as e:
        logger.error(f"Error getting available voltage metrics: {str(e)}")
        return {}

def get_voltage_stats(period='day', from_time=None, to_time=None):
    """
    Calculates voltage statistics for the specified period
    """
    try:
        UPSDynamicData = get_ups_model()
        # Use CACHE_TIMEZONE from app
        tz = current_app.CACHE_TIMEZONE
        now = datetime.now(tz)
        
        # Time period handling
        if period == 'day' and from_time and to_time:
            today = now.date()
            from_time_obj = parse_time_format(from_time, datetime.strptime("00:00", '%H:%M').time())
            to_time_obj = parse_time_format(to_time, now.time())
            start_time = datetime.combine(today, from_time_obj)
            end_time = datetime.combine(today, to_time_obj)
            start_time = tz.localize(start_time)
            end_time = tz.localize(end_time)
        elif period == 'range' and from_time and to_time:
            start_time = tz.localize(datetime.strptime(from_time, '%Y-%m-%d'))
            end_time = tz.localize(datetime.strptime(to_time, '%Y-%m-%d')) + timedelta(days=1)
        else:
            start_time = now - timedelta(days=1)
            end_time = now

        # Query with the correct period
        query = UPSDynamicData.query.filter(
            UPSDynamicData.timestamp_utc >= start_time,
            UPSDynamicData.timestamp_utc <= end_time
        )
        
        # Metrics to monitor
        voltage_metrics = [
            'input_voltage', 'output_voltage',
            'input_current', 'output_current',
            'input_frequency', 'output_frequency'
        ]
        
        stats = {}
        
        # Calculate statistics for each metric
        for metric in voltage_metrics:
            if hasattr(UPSDynamicData, metric):
                column = getattr(UPSDynamicData, metric)
                result = query.with_entities(
                    func.min(column).label('min'),
                    func.max(column).label('max'),
                    func.avg(column).label('avg')
                ).filter(column.isnot(None)).first()
                
                if result and result.min is not None:
                    stats[metric] = {
                        'min': float(result.min),
                        'max': float(result.max),
                        'avg': float(result.avg),
                        'available': True
                    }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error calculating voltage stats: {str(e)}")
        return {}

def get_voltage_history(period, from_time=None, to_time=None, selected_day=None):
    logger.debug(f"[GET_VOLTAGE_HISTORY] Called with: period={period}, from_time={from_time}, to_time={to_time}, selected_day={selected_day}")
    
    try:
        # Use CACHE_TIMEZONE from app
        tz = current_app.CACHE_TIMEZONE
        
        # Specific handling for the 'range' period
        if period == 'range':
            # Use from_time and to_time as dates for the range
            try:
                start_time = datetime.strptime(from_time, '%Y-%m-%d').replace(
                    hour=0, minute=0, second=0, microsecond=0, tzinfo=tz
                )
                end_time = datetime.strptime(to_time, '%Y-%m-%d').replace(
                    hour=23, minute=59, second=59, microsecond=999999, tzinfo=tz
                )
                logger.debug(f"Range period: start={start_time}, end={end_time}")
            except (ValueError, TypeError) as e:
                logger.error(f"Error parsing range dates: {str(e)}")
                # Fallback to today
                now = datetime.now(tz)
                start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = now

        # If a day is specified, use it as the base
        if selected_day:
            try:
                base_date = datetime.strptime(selected_day, '%Y-%m-%d').replace(tzinfo=tz)
            except ValueError:
                logger.error(f"Invalid selected_day format: {selected_day}")
                base_date = datetime.now(tz)
        else:
            base_date = datetime.now(tz)
        
        # Determine the time interval based on the period
        if period == 'today':
            start_time = base_date.replace(hour=0, minute=0, second=0, microsecond=0)
            if from_time and to_time:
                try:
                    # Use the specified hours
                    start_time = base_date.replace(
                        hour=int(from_time.split(':')[0]),
                        minute=int(from_time.split(':')[1]),
                        second=0,
                        microsecond=0
                    )
                    end_time = base_date.replace(
                        hour=int(to_time.split(':')[0]),
                        minute=int(to_time.split(':')[1]),
                        second=59,
                        microsecond=999999
                    )
                except (ValueError, IndexError):
                    end_time = base_date
            else:
                end_time = base_date
                
        elif period == 'day':
            start_time = base_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = base_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
        else:  # range
            try:
                # Convert range dates to the correct format
                start_time = datetime.strptime(from_time, '%Y-%m-%d').replace(
                    hour=0, minute=0, second=0, microsecond=0, tzinfo=tz
                )
                end_time = datetime.strptime(to_time, '%Y-%m-%d').replace(
                    hour=23, minute=59, second=59, microsecond=999999, tzinfo=tz
                )
            except (ValueError, TypeError) as e:
                logger.error(f"Error parsing range dates: {str(e)}")
                start_time = base_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = base_date
        
        logger.debug(f"Query time range: from {start_time} to {end_time}")
        
        # Convert the calculated local time range to UTC
        start_time_utc = None
        end_time_utc = None
        try:
            start_time_utc = start_time.astimezone(pytz.utc)
            end_time_utc = end_time.astimezone(pytz.utc)
            logger.debug(f"Querying database with UTC range: {start_time_utc} to {end_time_utc}")
        except Exception as e:
            logger.error(f"Error converting time range to UTC: {e}")
            # Return empty history if time conversion fails
            return {}

        UPSDynamicData = get_ups_model()
        history = {}
        # List of numeric metrics to monitor
        numeric_metrics = [
            'input_voltage', 'input_voltage_nominal',
            'output_voltage', 'output_voltage_nominal',
            'input_transfer_low', 'input_transfer_high',
            'ups_load',
            'input_current', 'output_current',
            'input_frequency', 'output_frequency'
        ]
        
        # Retrieve the data for each numeric metric
        for metric in numeric_metrics:
            if hasattr(UPSDynamicData, metric):
                try:
                    # Query using UTC times
                    data = UPSDynamicData.query.filter(
                        UPSDynamicData.timestamp_utc >= start_time_utc,
                        UPSDynamicData.timestamp_utc <= end_time_utc,
                        getattr(UPSDynamicData, metric).isnot(None)
                    ).order_by(UPSDynamicData.timestamp_utc.asc()).all()

                    logger.debug(f"Found {len(data)} records for metric {metric}")
                    
                    if data:
                        # --- START: Modified Sampling Logic ---
                        sampled_data = []
                        original_length = len(data)
                        target_points = 96 # Default target points

                        # Skip sampling for 'today' view
                        if period == 'today':
                            sampled_data = data
                            logger.debug(f"Skipping sampling for 'today' view. Using all {original_length} points for {metric}.")
                        elif original_length > target_points:
                            step = max(1, original_length // target_points)
                            sampled_data = data[::step]
                            # Explicitly add the last point
                            if data[-1] not in sampled_data:
                                sampled_data.append(data[-1])
                                logger.debug(f"Sampling {metric}: Added last point explicitly.")
                            logger.debug(f"Sampling {metric}: Original={original_length}, Target={target_points}, Step={step}, Result={len(sampled_data)} points.")
                        else:
                            # No sampling needed
                            sampled_data = data
                        # --- END: Modified Sampling Logic ---

                        logger.debug(f"Sampled {len(sampled_data)} points for metric {metric}")
                        
                        history[metric] = []
                        for entry in sampled_data:
                            try:
                                value = float(getattr(entry, metric))
                                history[metric].append({
                                    # Convert UTC timestamp from DB to local milliseconds
                                    'timestamp': entry.timestamp_utc.replace(tzinfo=pytz.utc).astimezone(tz).timestamp() * 1000,
                                    'value': value
                                })
                            except (ValueError, TypeError):
                                continue
                        
                        # Sort by timestamp (now local ms)
                        history[metric].sort(key=lambda x: x['timestamp'])

                        logger.debug(f"Final data points for {metric}: {len(history[metric])}")
                    else:
                        history[metric] = []
                except Exception as e:
                    logger.error(f"Error processing metric {metric}: {str(e)}")
                    history[metric] = []

        # Log the results before returning them
        logger.debug("[GET_VOLTAGE_HISTORY] Query completed, processing results")
        
        return history
        
    except Exception as e:
        logger.error(f"[GET_VOLTAGE_HISTORY] Error processing request: {str(e)}", exc_info=True)
        raise 
