"""Power Module.

Implements core runtime logic and helpers used by this feature.
"""

from datetime import datetime, timedelta
from core.logger import power_logger as logger
from core.db.ups import (
    db, get_ups_data, get_historical_data, get_supported_value, get_ups_model
)
from sqlalchemy import func
import pytz
from flask import current_app
from core.settings import parse_time_format

logger.info("💪 Initialization power module")

# List of potential power-related metrics
POTENTIAL_POWER_METRICS = [
    # UPS Power Metrics
    'ups_power',                # UPS measured power in watts
    'ups_realpower',           # UPS real power consumption
    'ups_realpower_nominal',   # UPS nominal real power
    'ups_realpower_hrs',       # UPS real power hours
    'ups_realpower_days',      # UPS real power days
    'ups_load',                # UPS load percentage
    'ups_efficiency',          # UPS efficiency
    'ups_power_nominal',       # UPS nominal power
    
    # Input Metrics
    'input_voltage',           # Input voltage
    'input_voltage_nominal',   # Nominal input voltage
    'input_voltage_minimum',   # Minimum input voltage
    'input_voltage_maximum',   # Maximum input voltage
    'input_transfer_low',      # Low transfer voltage
    'input_transfer_high',     # High transfer voltage
    'input_frequency',         # Input frequency
    'input_frequency_nominal', # Nominal input frequency
    'input_current',          # Input current
    'input_current_nominal',  # Nominal input current
    'input_realpower',        # Input real power
    'input_realpower_nominal', # Nominal input real power
    
    # Output Metrics
    'output_voltage',         # Output voltage
    'output_voltage_nominal', # Nominal output voltage
    'output_frequency',       # Output frequency
    'output_frequency_nominal', # Nominal output frequency
    'output_current',         # Output current
    'output_current_nominal'  # Nominal output current
]

def get_available_power_metrics():
    """
    Retrieve the list of power metrics available from the UPS dynamic data.
    """
    try:
        UPSDynamicData = get_ups_model()
        available_metrics = {}
        
        # Get the latest record from dynamic data table
        latest = UPSDynamicData.query.order_by(UPSDynamicData.timestamp_utc.desc()).first()
        if not latest:
            logger.warning("No UPS data found in database")
            return available_metrics

        # Check each potential metric
        for metric in POTENTIAL_POWER_METRICS:
            if hasattr(latest, metric):
                value = getattr(latest, metric)
                if value is not None:
                    try:
                        # Convert to float for uniformity
                        float_value = float(value)
                        available_metrics[metric] = float_value
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Could not convert {metric} value to float: {e}")
                        continue

        # Add manual nominal power from settings if not available from UPS
        # Check in order: ups_realpower_nominal, ups_power_nominal, then settings
        if 'ups_realpower_nominal' not in available_metrics:
            if 'ups_power_nominal' in available_metrics:
                # Use ups_power_nominal as fallback
                available_metrics['ups_realpower_nominal'] = available_metrics['ups_power_nominal']
                logger.info("Using ups_power_nominal as fallback for nominal power")
            else:
                # Use settings as last resort
                from core.settings import get_ups_realpower_nominal
                try:
                    available_metrics['ups_realpower_nominal'] = float(get_ups_realpower_nominal())
                    logger.info("Using manual nominal power from settings")
                except (ValueError, TypeError, NameError) as e:
                    # If get_ups_realpower_nominal() fails or UPS_REALPOWER_NOMINAL is not defined
                    logger.warning(f"Error getting UPS_REALPOWER_NOMINAL: {str(e)}")
                    # Use default value
                    available_metrics['ups_realpower_nominal'] = 1000.0
                    logger.info("Using default value 1000.0 for nominal power")

        # Remove ups_power if present, we'll use only ups_realpower
        if 'ups_power' in available_metrics:
            del available_metrics['ups_power']
            logger.debug("Removed ups_power, using ups_realpower instead")

        logger.info(f"Found {len(available_metrics)} available power metrics")
        logger.debug(f"Available metrics: {available_metrics}")
        return available_metrics

    except Exception as e:
        logger.error(f"Error getting available power metrics: {str(e)}")
        return {}

def get_power_stats(period='day', from_time=None, to_time=None, selected_date=None):
    """
    Calculate power statistics for each available metric.
    """
    try:
        tz = current_app.CACHE_TIMEZONE
        now = datetime.now(tz)
        logger.debug(f"Getting power stats - Period: {period}, From: {from_time}, To: {to_time}, Selected: {selected_date}")
        
        # Standardize time range calculation
        if period == 'day' and selected_date is not None:  # Case SELECT DAY
            # selected_date already has the timezone, we use it directly
            start_time = selected_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = selected_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            logger.debug(f"Select Day stats range - Start: {start_time}, End: {end_time}")
        elif period == 'today':  # Case TODAY
            # For TODAY explicitly - use data from 00:00 today to current time
            today = now.date()
            start_time = tz.localize(datetime.combine(today, datetime.min.time()))
            end_time = now
            logger.debug(f"TODAY stats range - Start: {start_time}, End: {end_time}")
        elif period == 'day':
            today = now.date()
            if from_time and to_time:
                # Case "today" or specific hourly range
                try:
                    from_time_obj = parse_time_format(from_time, datetime.strptime("00:00", '%H:%M').time())
                    to_time_obj = parse_time_format(to_time, now.time())
                    
                    # Create datetime with timezone
                    start_time = tz.localize(datetime.combine(today, from_time_obj))
                    end_time = tz.localize(datetime.combine(today, to_time_obj))
                    
                    logger.debug(f"Today time range - From: {start_time}, To: {end_time}")
                except ValueError as e:
                    logger.error(f"Error parsing time: {e}")
                    # Fallback to the entire day
                    start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_time = now
            else:
                # If not specified, use the entire day
                start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = now
        elif period == 'range':
            start_time = tz.localize(datetime.strptime(from_time, '%Y-%m-%d'))
            end_time = tz.localize(datetime.strptime(to_time, '%Y-%m-%d')).replace(
                hour=23, minute=59, second=59, microsecond=999999)
        else:
            start_time = now - timedelta(days=1)
            end_time = now

        logger.debug(f"Final time range - Start: {start_time}, End: {end_time}")

        # Get available metrics first
        available_metrics = get_available_power_metrics()
        
        # Initialize stats dictionary
        stats = {}
        model = get_ups_model()

        # Calculate stats for each metric
        for metric in available_metrics.keys():
            if metric == 'ups_realpower':
                # Calculate total energy using ups_realpower_hrs
                total_energy_query = model.query.filter(
                    model.timestamp_utc >= start_time,
                    model.timestamp_utc <= end_time,
                    model.ups_realpower_hrs.isnot(None)
                ).with_entities(func.sum(model.ups_realpower_hrs))
                
                total_energy = total_energy_query.scalar()
                logger.debug(f"Total energy query result: {total_energy}")

                # Calculate min, max, avg using ups_realpower
                stats_query = model.query.filter(
                    model.timestamp_utc >= start_time,
                    model.timestamp_utc <= end_time,
                    model.ups_realpower.isnot(None)
                ).with_entities(
                    func.min(model.ups_realpower).label('min'),
                    func.max(model.ups_realpower).label('max'),
                    func.avg(model.ups_realpower).label('avg')
                )
                
                result = stats_query.first()
                logger.debug(f"Stats query result: {result}")

                stats[metric] = {
                    'total_energy': float(total_energy) if total_energy is not None else 0,
                    'current': float(available_metrics[metric]),
                    'min': float(result.min) if result and result.min is not None else 0,
                    'max': float(result.max) if result and result.max is not None else 0,
                    'avg': float(result.avg) if result and result.avg is not None else 0,
                    'available': True if result and result.min is not None else False
                }
                
                logger.debug(f"Final stats for {metric}: {stats[metric]}")
            elif metric == 'ups_realpower_nominal' and not hasattr(model, 'ups_realpower_nominal'):
                # Special handling for ups_realpower_nominal when it was added as a fallback
                # but does not exist as a column in the table
                stats[metric] = {
                    'min': float(available_metrics[metric]),
                    'max': float(available_metrics[metric]),
                    'avg': float(available_metrics[metric]),
                    'current': float(available_metrics[metric]),
                    'available': True
                }
                logger.debug(f"Using fallback value for {metric}: {stats[metric]}")
            else:
                # For other metrics
                try:
                    # Check if the metric exists as a column in the table
                    if hasattr(model, metric):
                        result = model.query.filter(
                            model.timestamp_utc >= start_time,
                            model.timestamp_utc <= end_time,
                            getattr(model, metric).isnot(None)
                        ).with_entities(
                            func.min(getattr(model, metric)).label('min'),
                            func.max(getattr(model, metric)).label('max'),
                            func.avg(getattr(model, metric)).label('avg')
                        ).first()

                        stats[metric] = {
                            'min': float(result.min) if result and result.min is not None else 0,
                            'max': float(result.max) if result and result.max is not None else 0,
                            'avg': float(result.avg) if result and result.avg is not None else 0,
                            'current': float(available_metrics[metric]),
                            'available': True if result and result.min is not None else False
                        }
                    else:
                        # If the metric does not exist as a column, use the current value
                        stats[metric] = {
                            'min': float(available_metrics[metric]),
                            'max': float(available_metrics[metric]),
                            'avg': float(available_metrics[metric]),
                            'current': float(available_metrics[metric]),
                            'available': True
                        }
                        logger.debug(f"Using current value for {metric}: {stats[metric]}")
                except Exception as e:
                    logger.warning(f"Error calculating stats for {metric}: {str(e)}")
                    stats[metric] = {
                        'min': 0,
                        'max': 0,
                        'avg': 0,
                        'current': float(available_metrics[metric]),
                        'available': False
                    }

        return stats

    except Exception as e:
        logger.error(f"Error calculating power stats: {str(e)}")
        return {}

def get_power_history(period='day', from_date=None, to_date=None, selected_date=None):
    """
    Retrieve historical power data (for ups_power, ups_realpower, input_voltage)
    to display in a chart.
    """
    try:
        model = get_ups_model()
        tz = current_app.CACHE_TIMEZONE
        now = datetime.now(tz)

        # Convert local start/end times to UTC for querying
        start_time_utc = None
        end_time_utc = None

        # Set time range based on period
        if period == 'day' and selected_date is not None:
            start_time = selected_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = selected_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            target_points = 96
            logger.debug(f"Selected Date range - Start: {start_time}, End: {end_time}")
        elif period == 'today':
            # For TODAY explicitly - use data from 00:00 today to current time
            today = now.date()
            start_time = tz.localize(datetime.combine(today, datetime.min.time()))
            end_time = now
            target_points = 96
            logger.debug(f"TODAY range - Start: {start_time}, End: {end_time}")
        elif period == 'day' and from_date and to_date:
            today = now.date()
            if from_date and to_date:
                # Case "today" or specific hourly range
                try:
                    from_time_obj = parse_time_format(from_date, datetime.strptime("00:00", '%H:%M').time())
                    to_time_obj = parse_time_format(to_date, now.time())
                    
                    # Create datetime with timezone
                    start_time = tz.localize(datetime.combine(today, from_time_obj))
                    end_time = tz.localize(datetime.combine(today, to_time_obj))
                    
                    logger.debug(f"Today time range - From: {start_time}, To: {end_time}")
                except ValueError as e:
                    logger.error(f"Error parsing time: {e}")
                    # Fallback to the entire day
                    start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_time = now
            else:
                # If not specified, use the entire day
                start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = now
            target_points = 96
        elif period == 'range' and from_date and to_date:
            start_time = tz.localize(datetime.strptime(from_date, '%Y-%m-%d'))
            end_time = tz.localize(datetime.strptime(to_date, '%Y-%m-%d')).replace(
                hour=23, minute=59, second=59, microsecond=999999)
            target_points = 180
        else:
            start_time = now - timedelta(days=1)
            end_time = now
            target_points = 96

        # Convert the calculated local time range to UTC
        try:
            start_time_utc = start_time.astimezone(pytz.utc)
            end_time_utc = end_time.astimezone(pytz.utc)
            logger.debug(f"Querying database with UTC range: {start_time_utc} to {end_time_utc}")
        except Exception as e:
            logger.error(f"Error converting time range to UTC: {e}")
            # Return empty history if time conversion fails
            return {
                'ups_power': [],
                'ups_realpower': [],
                'input_voltage': []
            }

        history = {}
        metrics = ['ups_power', 'ups_realpower', 'input_voltage']

        for metric in metrics:
            if hasattr(model, metric):
                # Use UTC times for the query
                data = model.query.filter(
                    model.timestamp_utc >= start_time_utc,
                    model.timestamp_utc <= end_time_utc,
                    getattr(model, metric).isnot(None)
                ).order_by(model.timestamp_utc.asc()).all()

                logger.debug(f"📊 Metric {metric}: found {len(data)} records")

                if data:
                    # --- START: Modified Sampling Logic ---
                    sampled_data = []
                    original_length = len(data)

                    # Skip sampling for 'today' view to ensure latest data is included
                    if period == 'today':
                        sampled_data = data
                        logger.debug(f"Skipping sampling for 'today' view. Using all {original_length} points for {metric}.")
                    elif original_length > target_points:
                        # Basic sampling for other views, ensuring last point is kept
                        step = max(1, original_length // target_points)
                        # Take every 'step' point
                        sampled_data = data[::step]

                        # Explicitly add the last point if it wasn't included by the sampling
                        if data[-1] not in sampled_data:
                            sampled_data.append(data[-1])
                            logger.debug(f"Sampling {metric}: Added last point explicitly.")
                        logger.debug(f"Sampling {metric}: Original={original_length}, Target={target_points}, Step={step}, Result={len(sampled_data)} points.")
                    else:
                        # No sampling needed if fewer points than target
                        sampled_data = data
                    # --- END: Modified Sampling Logic ---

                    history[metric] = [{
                        # Convert UTC timestamp from DB to local milliseconds for frontend
                        'timestamp': entry.timestamp_utc.replace(tzinfo=pytz.utc).astimezone(tz).timestamp() * 1000,
                        'value': float(getattr(entry, metric))
                    } for entry in sampled_data]

                    # Sort by timestamp (now local ms) to ensure correct order
                    history[metric].sort(key=lambda x: x['timestamp'])
                else:
                    history[metric] = []
        return history

    except Exception as e:
        logger.error(f"Error getting power history: {str(e)}")
        return {
            'ups_power': [],
            'ups_realpower': [],
            'input_voltage': []
        }

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
