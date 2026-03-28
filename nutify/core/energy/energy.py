"""Energy Module.

Implements core runtime logic and helpers used by this feature.
"""

from flask import render_template, jsonify, request, current_app, has_request_context
from datetime import datetime, timedelta
from ..db.ups import (
    db, get_ups_data, get_historical_data, get_supported_value, get_ups_model,
    VariableConfig, data_lock, ups_data_cache
)
from sqlalchemy import func
import pytz
from .. import settings
from core.logger import energy_logger as logger
import requests
from ..mail import NotificationSettings
from typing import TypeVar
from core.settings import parse_time_format
from core.multi_nut.target_scope import apply_target_scope, apply_target_scope_with_global, resolve_settings_target_id

# Type annotation for UPSDynamicData
UPSDynamicData = TypeVar('UPSDynamicData')

logger.info("⚡ Initializing energy")


def _resolve_config_target_id():
    """Resolve target scope for settings reads in request or non-request contexts."""
    requested_target_id = None
    if has_request_context():
        requested_target_id = request.args.get('target_id', type=int)
    return resolve_settings_target_id(requested_target_id)


def _get_variable_config_model():
    """Return the active VariableConfig model class."""
    if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'VariableConfig'):
        return db.ModelClasses.VariableConfig
    if hasattr(VariableConfig, 'query'):
        return VariableConfig
    return None


def _get_variable_config_row(include_global_fallback=True):
    """
    Return VariableConfig row scoped by target_id.

    Args:
        include_global_fallback: if True, scoped reads can fallback to global rows.
    Returns:
        tuple(config_row|None, scoped_target_id|None)
    """
    model = _get_variable_config_model()
    scoped_target_id = _resolve_config_target_id()
    if not model:
        return None, scoped_target_id

    query = model.query
    if hasattr(model, 'target_id'):
        if include_global_fallback:
            query = apply_target_scope_with_global(model, query, scoped_target_id)
        else:
            query = apply_target_scope(model, query, scoped_target_id)

    row = query.order_by(model.id.desc()).first()
    return row, scoped_target_id

def calculate_trend(current, previous):
    """Calculate the percentage trend between two values"""
    if not previous or previous == 0:
        return 0
    if current < 0.001 and previous < 0.001:  # Avoid division by very small numbers
        return 0
    trend = ((current - previous) / previous) * 100
    return min(max(round(trend, 1), -100), 1000)  # Limit the trend between -100% and 1000%

def get_nominal_power(latest_data):
    """Get UPS nominal power following the hierarchy:
    1. From API data (ups_realpower_nominal)
    2. From database
    3. From settings.conf as fallback
    """
    try:
        # 1. Check API data: if latest_data is an instance, use it; if it's the class, get the latest record
        let_inst = None
        if latest_data:
            if isinstance(latest_data, type):
                let_inst = latest_data.query.order_by(latest_data.timestamp_utc.desc()).first()
            else:
                let_inst = latest_data
            if let_inst and hasattr(let_inst, 'ups_realpower_nominal') and let_inst.ups_realpower_nominal is not None:
                return float(let_inst.ups_realpower_nominal)
        
        # 2. Check database
        UPSDynamicData = get_ups_model()
        let_inst = UPSDynamicData.query.order_by(UPSDynamicData.timestamp_utc.desc()).first()
        if let_inst and hasattr(let_inst, 'ups_realpower_nominal') and let_inst.ups_realpower_nominal is not None:
            return float(let_inst.ups_realpower_nominal)
        
        # 3. Use settings.conf as fallback
        from core.settings import get_ups_realpower_nominal
        return float(get_ups_realpower_nominal())
        
    except Exception as e:
        logger.error(f"Error getting nominal power: {str(e)}")
        from core.settings import get_ups_realpower_nominal
        return float(get_ups_realpower_nominal())

def get_energy_data(days=1, start_date=None, end_date=None):
    """
    Collects energy data using pre-calculated values
    Args:
        days: number of days (default=1)
        start_date: optional start date (datetime)
        end_date: optional end date (datetime)
    """
    try:
        # Import db instance early to ensure availability
        from core.db.ups import db 
        
        UPSDynamicData = get_ups_model()
        
        # If specific dates are provided, use them
        if start_date and end_date:
            # Query without filtering on specific columns
            data = UPSDynamicData.query\
                .filter(
                    UPSDynamicData.timestamp_utc >= start_date,
                    UPSDynamicData.timestamp_utc <= end_date
                ).order_by(UPSDynamicData.timestamp_utc.asc()).all()
                
            stats = calculate_energy_stats(data, 'hrs')
            rate = get_energy_rate()
            stats['cost_distribution'] = calculate_cost_distribution(data, rate)
            return stats
            
        # Otherwise, use the existing logic with request.args
        period_type = request.args.get('type', 'day')
        from_time = request.args.get('from_time')
        to_time = request.args.get('to_time')
        
        logger.debug(f"Getting energy data - type: {period_type}, from: {from_time}, to: {to_time}")
        
        # Custom range of dates
        if period_type == 'range':
            tz = current_app.CACHE_TIMEZONE
            start_dt = datetime.strptime(from_time, '%Y-%m-%d')
            end_dt = datetime.strptime(to_time, '%Y-%m-%d')
            start_time = tz.localize(start_dt)
            end_time = tz.localize(end_dt.replace(hour=23, minute=59, second=59))
            
            # Query without filtering on specific columns
            data = UPSDynamicData.query\
                .filter(
                    UPSDynamicData.timestamp_utc >= start_time,
                    UPSDynamicData.timestamp_utc <= end_time
                ).order_by(UPSDynamicData.timestamp_utc.asc()).all()
                
            stats = calculate_energy_stats(data, 'hrs')
            
            # Add cost distribution
            rate = get_energy_rate()
            stats['cost_distribution'] = calculate_cost_distribution(data, rate)
            
            return stats
        
        # For Real-time uses data from cache
        elif period_type == 'realtime':
            try:
                from core.db.ups import ups_data_cache
                cache_data = ups_data_cache.data
                if cache_data and len(cache_data) > 0:
                    # Ensure the last data is valid
                    latest_cache = cache_data[-1]
                    if 'ups_load' in latest_cache and 'ups_realpower_nominal' in latest_cache:
                        return format_realtime_data(latest_cache)
            except Exception as e:
                logger.error(f"Error getting cache data: {str(e)}")
            # Fallback to existing method if cache fails
            latest = UPSDynamicData.query\
                .filter(
                    UPSDynamicData.ups_load.isnot(None) | 
                    UPSDynamicData.ups_realpower.isnot(None)
                )\
                .order_by(UPSDynamicData.timestamp_utc.desc())\
                .first()
            if latest:
                return format_realtime_data(latest)
        
        # For Today with From-To
        elif period_type == 'today':
            now = datetime.now(current_app.CACHE_TIMEZONE)
            today = now.date()
            
            # Use the utility function to parse time formats
            from_time_obj = parse_time_format(from_time, datetime.strptime("00:00", '%H:%M').time())
            to_time_obj = parse_time_format(to_time, now.time())
            
            start_time = current_app.CACHE_TIMEZONE.localize(datetime.combine(today, from_time_obj))
            end_time = current_app.CACHE_TIMEZONE.localize(datetime.combine(today, to_time_obj))
            
            # Get data without filtering on specific columns
            data = UPSDynamicData.query\
                .filter(
                    UPSDynamicData.timestamp_utc >= start_time,
                    UPSDynamicData.timestamp_utc <= end_time
                ).all()
                
            logger.debug(f"Found {len(data)} records for today query between {start_time} and {end_time}")
            
            # Check if there are no records at all or if data is empty
            if not data:
                # Get the latest record to estimate energy
                logger.debug("No data found for the specified time range, getting latest record")
                latest = UPSDynamicData.query\
                    .filter(
                        UPSDynamicData.ups_load.isnot(None),
                        UPSDynamicData.ups_realpower_nominal.isnot(None)
                    )\
                    .order_by(UPSDynamicData.timestamp_utc.desc())\
                    .first()
                    
                if latest:
                    # Create a basic estimation
                    duration_hours = (end_time - start_time).total_seconds() / 3600
                    power = (float(latest.ups_realpower_nominal) * float(latest.ups_load)) / 100  # W
                    energy_wh = power * duration_hours  # Wh
                    
                    rate = get_energy_rate()
                    energy_kwh = energy_wh / 1000
                    cost = energy_kwh * rate
                    
                    # Safely access VariableConfig via db.ModelClasses
                    config, _ = _get_variable_config_row(include_global_fallback=True)
                    if config is None:
                        logger.warning("VariableConfig row not found for scoped energy estimation, using defaults")
                    
                    co2_factor = float(config.co2_factor) if config and hasattr(config, 'co2_factor') else 0.4
                    co2 = energy_kwh * co2_factor
                    
                    # Create estimated result
                    result = {
                        'totalEnergy': round(energy_wh, 2),  # In Wh
                        'totalCost': round(cost, 2),
                        'avgLoad': round(float(latest.ups_load), 1),
                        'co2': round(co2, 2),
                        'efficiency': {
                            'peak': round(float(latest.ups_load), 1),
                            'average': round(float(latest.ups_load), 1)
                        },
                        'cost_distribution': calculate_cost_distribution([latest], rate),
                        'trends': {'energy': 0, 'cost': 0, 'load': 0, 'co2': 0}
                    }
                    
                    logger.debug(f"Generated estimated result with latest record: {result}")
                    return result
                
            # Calculate stats from available data
            stats = calculate_energy_stats(data, 'hrs')
            
            # If energy is still zero, try to estimate from load data
            if stats['totalEnergy'] == 0 and data:
                load_data = [row for row in data if hasattr(row, 'ups_load') and row.ups_load is not None]
                if load_data:
                    # Get the average load
                    avg_load = sum(float(row.ups_load or 0) for row in load_data) / len(load_data)
                    # Get nominal power (use the first record that has it, or fallback)
                    nominal_power = None
                    for row in load_data:
                        if hasattr(row, 'ups_realpower_nominal') and row.ups_realpower_nominal is not None:
                            nominal_power = float(row.ups_realpower_nominal)
                            break
                    
                    if not nominal_power:
                        nominal_power = float(settings.UPS_REALPOWER_NOMINAL)
                    
                    # Calculate estimated power and energy
                    power = (nominal_power * avg_load) / 100  # W
                    duration_hours = (end_time - start_time).total_seconds() / 3600
                    energy_wh = power * duration_hours  # Wh
                    
                    # Safely access VariableConfig via db.ModelClasses
                    config, _ = _get_variable_config_row(include_global_fallback=True)
                    if config is None:
                        logger.warning("VariableConfig row not found for scoped load estimation, using defaults")
                    
                    co2_factor = float(config.co2_factor) if config and hasattr(config, 'co2_factor') else 0.4
                    co2 = energy_wh / 1000 * co2_factor
                    
                    stats['totalEnergy'] = round(energy_wh, 2)
                    stats['totalCost'] = round(energy_wh / 1000 * get_energy_rate(), 2)
                    stats['co2'] = round(co2, 2)
                    
                    logger.debug(f"Updated stats with estimated values: {stats}")
            
            # Add cost distribution
            rate = get_energy_rate()
            stats['cost_distribution'] = calculate_cost_distribution(data, rate)
            
            return stats
            
        # For Select Day (uses ups_realpower_hrs)
        elif period_type == 'day':
            selected_dt = datetime.strptime(from_time, '%Y-%m-%d')
            selected_date = current_app.CACHE_TIMEZONE.localize(selected_dt)
            return get_single_day_data(selected_date)
            
    except Exception as e:
        logger.error(f"Error getting energy data: {str(e)}")
        return default_energy_response()

def get_today_detailed_data(now, from_time, to_time):
    """Handles today's data by combining complete hours and partial minutes"""
    try:
        UPSDynamicData = get_ups_model()
        
        start_time = now.replace(
            hour=int(from_time.split(':')[0]),
            minute=int(from_time.split(':')[1]),
            second=0
        )
        end_time = now.replace(
            hour=int(to_time.split(':')[0]),
            minute=int(to_time.split(':')[1]),
            second=59
        )
        
        logger.debug(f"Getting detailed data from {start_time} to {end_time}")
        
        # Get hourly data for complete hours
        hourly_data = UPSDynamicData.query\
            .filter(
                UPSDynamicData.timestamp_utc >= start_time,
                UPSDynamicData.timestamp_utc <= end_time,
                UPSDynamicData.ups_realpower_hrs.isnot(None)
            ).all()
            
        # Get minute data for the last partial hour
        last_hour = end_time.replace(minute=0, second=0)
        minute_data = UPSDynamicData.query\
            .filter(
                UPSDynamicData.timestamp_utc >= last_hour,
                UPSDynamicData.timestamp_utc <= end_time,
                UPSDynamicData.ups_realpower.isnot(None)
            ).all()
            
        # Calculate statistics for hourly data
        hourly_stats = calculate_energy_stats(hourly_data, 'hrs')
        
        # Calculate statistics for minute data
        minute_stats = calculate_energy_stats(minute_data, 'realtime')
        
        # Combine results
        combined_stats = {
            'totalEnergy': round(hourly_stats['totalEnergy'] + minute_stats['totalEnergy'], 2),
            'totalCost': round(hourly_stats['totalCost'] + minute_stats['totalCost'], 2),
            'avgLoad': round((hourly_stats['avgLoad'] + minute_stats['avgLoad']) / 2, 1),
            'co2': round(hourly_stats['co2'] + minute_stats['co2'], 2),
            'efficiency': {
                'peak': max(hourly_stats['efficiency']['peak'], minute_stats['efficiency']['peak']),
                'average': round((hourly_stats['efficiency']['average'] + minute_stats['efficiency']['average']) / 2, 1)
            }
        }

        # Add trends
        previous_start = start_time - timedelta(days=1)
        previous_end = end_time - timedelta(days=1)
        
        previous_data = UPSDynamicData.query\
            .filter(
                UPSDynamicData.timestamp_utc >= previous_start,
                UPSDynamicData.timestamp_utc <= previous_end
            ).all()
            
        previous_stats = calculate_energy_stats(previous_data, 'hrs')
        
        combined_stats['trends'] = {
            'energy': calculate_trend(combined_stats['totalEnergy'], previous_stats['totalEnergy']),
            'cost': calculate_trend(combined_stats['totalCost'], previous_stats['totalCost']),
            'load': calculate_trend(combined_stats['avgLoad'], previous_stats['avgLoad']),
            'co2': calculate_trend(combined_stats['co2'], previous_stats['co2'])
        }
        
        return combined_stats
        
    except Exception as e:
        logger.error(f"Error in get_today_detailed_data: {str(e)}")
        return default_energy_response()

def get_today_energy_data(now):
    """Get hourly data for today"""
    start_time = now.replace(hour=0, minute=0, second=0)
    
    # Query only on hourly data
    hourly_data = UPSDynamicData.query\
        .filter(
            UPSDynamicData.timestamp_utc >= start_time,
            UPSDynamicData.timestamp_utc <= now,
            UPSDynamicData.ups_realpower_hrs.isnot(None)
        ).order_by(UPSDynamicData.timestamp_utc.asc()).all()
        
    return calculate_energy_stats(hourly_data, 'hrs')

def get_period_energy_data(now, days):
    """Get data for periods longer than one day"""
    try:
        UPSDynamicData = get_ups_model()
        
        start_time = now - timedelta(days=days)
        
        logger.debug(f"Getting period data from {start_time} to {now}")
        
        # Query on daily data
        daily_data = UPSDynamicData.query\
            .filter(
                UPSDynamicData.timestamp_utc >= start_time,
                UPSDynamicData.timestamp_utc <= now,
                UPSDynamicData.ups_realpower_days.isnot(None)
            ).order_by(UPSDynamicData.timestamp_utc.asc()).all()
            
        return calculate_energy_stats(daily_data, 'days')
        
    except Exception as e:
        logger.error(f"Error in get_period_energy_data: {str(e)}")
        return default_energy_response()

def calculate_energy_stats(data, period_type):
    """Calculate energy statistics based on the period"""
    try:
        logger.debug(f"Starting energy stats calculation for period_type: {period_type}")
        logger.debug(f"Number of records to process: {len(data)}")
        
        # Initialize total energy
        total_energy = 0
        
        # If not realtime, try to calculate with available data
        if period_type != 'realtime':
            # Check if we have ups_realpower_hrs data
            has_hrs_data = len(data) > 0 and hasattr(data[0], 'ups_realpower_hrs') and any(row.ups_realpower_hrs is not None for row in data)
            has_load_data = len(data) > 0 and hasattr(data[0], 'ups_load') and hasattr(data[0], 'ups_realpower_nominal')
            
            if has_hrs_data:
                # We don't divide by 1000 because ups_realpower_hrs is already in Wh
                total_energy = sum(float(row.ups_realpower_hrs or 0) for row in data)  # Wh
                logger.debug(f"Calculated energy using ups_realpower_hrs: {total_energy}Wh")
            # If ups_realpower_hrs is not available, try to calculate from load and nominal power
            elif has_load_data:
                # Calculate energy based on load percentage and nominal power
                valid_data_points = [row for row in data if row.ups_load is not None and row.ups_realpower_nominal is not None]
                
                # If we have at least one valid data point, use a min calculation for a single point
                if len(valid_data_points) == 1:
                    row = valid_data_points[0]
                    # Assume a 15-minute window for a single data point (0.25 hours)
                    power = (float(row.ups_realpower_nominal) * float(row.ups_load)) / 100  # W
                    total_energy = power * 0.25  # Wh (power × 0.25 hours)
                    logger.debug(f"Calculated energy from single point: {total_energy}Wh")
                elif len(valid_data_points) > 1:
                    # Process multiple points with time difference
                    for i in range(1, len(valid_data_points)):
                        # Calculate duration between points in hours
                        time_diff = (valid_data_points[i].timestamp_utc - valid_data_points[i-1].timestamp_utc).total_seconds() / 3600
                        
                        # Skip if time difference is too large (more than 2 hours)
                        if time_diff > 2:
                            continue
                            
                        # Calculate power for this interval (average of current and previous)
                        current_power = (float(valid_data_points[i].ups_realpower_nominal) * float(valid_data_points[i].ups_load)) / 100
                        prev_power = (float(valid_data_points[i-1].ups_realpower_nominal) * float(valid_data_points[i-1].ups_load)) / 100
                        avg_power = (current_power + prev_power) / 2
                        
                        # Energy in Wh = Power (W) * Time (h)
                        interval_energy = avg_power * time_diff
                        total_energy += interval_energy
                    
                    logger.debug(f"Calculated energy using load and nominal power: {total_energy}Wh")
                    
                    # If still zero (e.g., all intervals skipped), use minimum estimate
                    if total_energy == 0 and valid_data_points:
                        latest = valid_data_points[-1]
                        power = (float(latest.ups_realpower_nominal) * float(latest.ups_load)) / 100  # W
                        # Assume at least 15 minutes (0.25 hours)
                        total_energy = power * 0.25  # Wh
                        logger.debug(f"Fallback calculation from single latest point: {total_energy}Wh")
            else:
                logger.warning("No suitable data found to calculate energy usage")
        else:
            # Keep the existing logic for realtime
            power = float(data.ups_realpower or 0)
            total_energy = power  # W
            
        # Calculate other statistics
        rate = float(get_energy_rate())  # Convert the Decimal to float
        # Convert to kWh only for cost calculation
        total_cost = (total_energy / 1000) * rate
        
        # Safely get VariableConfig
        co2_factor = 0.4  # Default value
        try:
            # Import here to avoid circular imports
            from core.db.ups import db
            
            config, _ = _get_variable_config_row(include_global_fallback=True)
            if config and hasattr(config, 'co2_factor'):
                co2_factor = float(config.co2_factor)
        except Exception as e:
            logger.error(f"Error getting VariableConfig for CO2 factor: {str(e)}")
        
        total_co2 = (total_energy / 1000) * co2_factor  # Convert to kWh for CO2 calculation
        
        # Calculate load statistics
        if period_type == 'realtime':
            avg_load = float(data.ups_load or 0)
            peak_load = avg_load
        else:
            loads = [float(row.ups_load or 0) for row in data if row.ups_load is not None]
            avg_load = sum(loads) / len(loads) if loads else 0
            peak_load = max(loads) if loads else 0
            
        result = {
            'totalEnergy': round(total_energy, 2),  # In Wh
            'totalCost': round(total_cost, 2),
            'avgLoad': round(avg_load, 1),
            'co2': round(total_co2, 2),
            'efficiency': {
                'peak': round(peak_load, 1),
                'average': round(avg_load, 1)
            }
        }
        
        logger.debug(f"Calculation results: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error calculating energy stats: {str(e)}", exc_info=True)
        return default_energy_response()

def format_realtime_data(latest):
    """Format realtime data using ups_realpower directly if available."""
    try:
        if isinstance(latest, dict):
            # Directly take the ups_realpower value (no fallback calculation!)
            total_energy = float(latest['ups_realpower'])
            load = float(latest.get('ups_load', 0))
            nominal_power = float(latest.get('ups_realpower_nominal', settings.UPS_REALPOWER_NOMINAL))
        else:
            total_energy = float(latest.ups_realpower)
            load = float(latest.ups_load) if latest.ups_load is not None else 0
            nominal_power = get_nominal_power(latest)
        
        # Safely get CO2 factor
        co2_factor = 0.4  # Default value
        try:
            # Import here to avoid circular imports
            from core.db.ups import db
            
            config, _ = _get_variable_config_row(include_global_fallback=True)
            if config and hasattr(config, 'co2_factor'):
                co2_factor = float(config.co2_factor)
        except Exception as e:
            logger.error(f"Error getting VariableConfig for CO2 factor: {str(e)}")
        
        total_cost = total_energy * get_energy_rate()
        total_co2 = total_energy * co2_factor
        total_saved = total_energy * get_efficiency_factor()
        
        return {
            'totalEnergy': round(total_energy, 2),
            'totalCost': round(total_cost, 2),
            'avgLoad': round(load, 1),
            'co2': round(total_co2, 2),
            'ups_realpower_nominal': nominal_power,
            'trends': {
                'energy': 0,
                'cost': 0,
                'load': 0,
                'co2': 0
            },
            'efficiency': {
                'peak': round(load, 1),
                'average': round(load, 1),
                'saved': round(total_saved, 2)
            }
        }
    except Exception as e:
        logger.error(f"Error formatting realtime data: {str(e)}")
        return default_energy_response()

def default_energy_response():
    """Default response in case of errors"""
    nominal_power = 0.0 # Default value
    try:
        from core.db.ups import db
        config, _ = _get_variable_config_row(include_global_fallback=True)
        if config is None:
            logger.warning("VariableConfig row not found in default_energy_response")
        
        if config and hasattr(config, 'ups_realpower_nominal') and config.ups_realpower_nominal is not None:
            nominal_power = float(config.ups_realpower_nominal)
            logger.debug(f"Using nominal power from DB in default response: {nominal_power}")
        else:
             logger.warning("Could not get UPS_REALPOWER_NOMINAL from VariableConfig in default_energy_response, using 0.0")

    except Exception as e:
        logger.error(f"Error getting UPS_REALPOWER_NOMINAL in default_energy_response: {str(e)}", exc_info=True)
        
    return {
        'totalEnergy': 0,
        'totalCost': 0,
        'avgLoad': 0,
        'co2': 0,
        'ups_realpower_nominal': nominal_power, # Use fetched or default value
        'trends': {'energy': 0, 'cost': 0, 'load': 0, 'co2': 0},
        'efficiency': {'peak': 0, 'average': 0, 'saved': 0}
    }

def calculate_efficiency(row):
    """Calculate efficiency for a single reading"""
    # Implement your logic for efficiency calculation
    # Example:
    nominal_power = float(row.ups_realpower_nominal)
    actual_power = (nominal_power * float(row.ups_load)) / 100
    # Example formula: efficiency = (actual_power / nominal_power) * 100
    return round((actual_power / nominal_power) * 100, 1) if nominal_power > 0 else 0

def get_cost_trend(type, start_time, end_time):
    """Helper function to get cost trend data"""
    try:
        UPSDynamicData = get_ups_model()
        logger.debug(f"get_cost_trend - type: {type}, start_time: {start_time}, end_time: {end_time}")
        data = UPSDynamicData.query\
            .filter(
                UPSDynamicData.timestamp_utc >= start_time,
                UPSDynamicData.timestamp_utc <= end_time
            )\
            .order_by(UPSDynamicData.timestamp_utc.asc())\
            .all()
                    
        cost_trend = []
        for row in data:
            if row.ups_realpower_nominal and row.ups_load:
                power = (float(row.ups_realpower_nominal) * float(row.ups_load)) / 100
                energy = power / 1000  # Convert to kWh
                cost = energy * get_energy_rate()
                cost_trend.append({
                    'x': row.timestamp_utc.isoformat(),
                    'y': round(cost, 4)
                })
        
        return cost_trend
    except Exception as e:
        logger.error(f"Error calculating cost trend: {str(e)}")
        return []

def get_energy_rate():
    """Get the energy rate from settings"""
    try:
        # Safely get the VariableConfig model
        VariableConfig = None
        from core.db.ups import db
        
        if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'VariableConfig'):
            VariableConfig = db.ModelClasses.VariableConfig
            logger.debug("Successfully initialized VariableConfig model from db.ModelClasses")
        else:
            logger.error("VariableConfig model not available in db.ModelClasses")
            return 0.25  # Default value if model isn't available
        
        # Query the config after ensuring the model is available
        config, _ = _get_variable_config_row(include_global_fallback=True)
        return float(config.price_per_kwh) if config and config.price_per_kwh else 0.25
    except Exception as e:
        logger.error(f"Error getting energy rate: {str(e)}", exc_info=True)
        return 0.25  # Default fallback

def get_efficiency_factor():
    """Get the efficiency factor from settings"""
    try:
        # Safely get the VariableConfig model
        VariableConfig = None
        from core.db.ups import db
        
        if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'VariableConfig'):
            VariableConfig = db.ModelClasses.VariableConfig
            logger.debug("Successfully initialized VariableConfig model from db.ModelClasses")
        else:
            logger.error("VariableConfig model not available in db.ModelClasses")
            return 0.06  # Default value if model isn't available
            
        config, _ = _get_variable_config_row(include_global_fallback=True)
        return float(config.efficiency) if config and hasattr(config, 'efficiency') else 0.06
    except Exception as e:
        logger.error(f"Error getting efficiency factor: {str(e)}", exc_info=True)
        return 0.06  # Default fallback

def calculate_period_stats(data):
    """Calculate statistics for a period of data"""
    try:
        logger.debug(f"=== START calculate_period_stats ===")
        logger.debug(f"Calculating stats for {len(data)} records")
        
        total_energy = 0
        total_cost = 0
        total_load = 0
        total_co2 = 0
        count = 0
        peak_load = 0
        avg_load = 0
        
        # Safely get the VariableConfig model
        VariableConfig = None
        from core.db.ups import db
        
        if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'VariableConfig'):
            VariableConfig = db.ModelClasses.VariableConfig
            logger.debug("Successfully initialized VariableConfig model from db.ModelClasses")
            # Get configurations from the database
            config, _ = _get_variable_config_row(include_global_fallback=True)
        else:
            logger.error("VariableConfig model not available in db.ModelClasses")
            config = None
            
        rate = get_energy_rate()
        co2_factor = float(config.co2_factor) if config and hasattr(config, 'co2_factor') else 0.4
        efficiency_factor = get_efficiency_factor()
        
        for row in data:
            if row.ups_realpower_nominal and row.ups_load:
                count += 1
                load = float(row.ups_load)
                power = (float(row.ups_realpower_nominal) * load) / 100
                
                # Update the peak load
                peak_load = max(peak_load, load)
                total_load += load
                
                # Calculate energy in kWh
                if hasattr(row, 'ups_realpower_hrs'):
                    energy = power / 1000  # kWh per hour
                elif hasattr(row, 'ups_realpower_days'):
                    energy = (power * 24) / 1000  # kWh per day
                else:
                    energy = power / 1000  # Default a kWh per hour
                
                total_energy += energy
                total_cost += energy * rate
                total_co2 += energy * co2_factor
        
        # Calculate averages
        avg_load = total_load / count if count > 0 else 0
        
        # Calculate saved energy using the efficiency factor
        saved_energy = total_energy * efficiency_factor
        
        stats = {
            'totalEnergy': round(total_energy, 2),
            'totalCost': round(total_cost, 2),
            'avgLoad': round(avg_load, 1),
            'co2': round(total_co2, 2),
            'efficiency': {
                'peak': round(peak_load, 1),
                'average': round(avg_load, 1),
                'saved': round(saved_energy, 2)
            }
        }
        
        logger.debug(f"Calculated stats: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Error in calculate_period_stats: {str(e)}", exc_info=True)
        raise 

def get_energy_data_for_period(start_time, end_time):
    """Helper function to calculate energy data for a period"""
    try:
        logger.debug(f"=== START get_energy_data_for_period ===")
        logger.debug(f"Parameters: start_time={start_time}, end_time={end_time}")
        
        UPSDynamicData = get_ups_model()
        
        # Calculate the same period in the past for trends
        period_length = end_time - start_time
        previous_start = start_time - period_length
        previous_end = start_time
        
        logger.debug(f"Previous period: {previous_start} to {previous_end}")
        
        # Query for the current period
        current_data = UPSDynamicData.query\
            .filter(
                UPSDynamicData.timestamp_utc >= start_time,
                UPSDynamicData.timestamp_utc <= end_time
            ).all()
        
        logger.debug(f"Found {len(current_data)} records for current period")
            
        # Query for the previous period
        previous_data = UPSDynamicData.query\
            .filter(
                UPSDynamicData.timestamp_utc >= previous_start,
                UPSDynamicData.timestamp_utc <= previous_end
            ).all()
            
        logger.debug(f"Found {len(previous_data)} records for previous period")
        
        # Calculate statistics for both periods
        current_stats = calculate_period_stats(current_data)
        previous_stats = calculate_period_stats(previous_data)
        
        logger.debug(f"Current stats: {current_stats}")
        logger.debug(f"Previous stats: {previous_stats}")
        
        # Calculate trends
        trends = {
            'energy': calculate_trend(current_stats['totalEnergy'], previous_stats['totalEnergy']),
            'cost': calculate_trend(current_stats['totalCost'], previous_stats['totalCost']),
            'load': calculate_trend(current_stats['avgLoad'], previous_stats['avgLoad']),
            'co2': calculate_trend(current_stats['co2'], previous_stats['co2'])
        }
        
        logger.debug(f"Calculated trends: {trends}")
        
        return {**current_stats, 'trends': trends}
        
    except Exception as e:
        logger.error(f"Error in get_energy_data_for_period: {str(e)}", exc_info=True)
        raise

def ensure_timezone_aware(dt):
    """Ensure datetime is timezone aware"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=current_app.CACHE_TIMEZONE)
    return dt

def get_single_day_data(date):
    try:
        UPSDynamicData = get_ups_model()
        
        start_time = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        logger.debug(f"Getting single day data from {start_time} to {end_time}")
        
        # Get data without filtering on specific columns
        data = UPSDynamicData.query\
            .filter(
                UPSDynamicData.timestamp_utc >= start_time,
                UPSDynamicData.timestamp_utc <= end_time
            ).order_by(UPSDynamicData.timestamp_utc.asc()).all()
        
        logger.debug(f"Found {len(data)} records for day query between {start_time} and {end_time}")
        
        # Check if there are no records at all 
        if not data:
            # Get the latest record to estimate energy
            logger.debug("No data found for the specified day, getting latest record")
            latest = UPSDynamicData.query\
                .filter(
                    UPSDynamicData.ups_load.isnot(None),
                    UPSDynamicData.ups_realpower_nominal.isnot(None)
                )\
                .order_by(UPSDynamicData.timestamp_utc.desc())\
                .first()
                
            if latest:
                # Create a basic estimation
                duration_hours = 24  # Full day
                power = (float(latest.ups_realpower_nominal) * float(latest.ups_load)) / 100  # W
                energy_wh = power * duration_hours  # Wh
                
                rate = get_energy_rate()
                energy_kwh = energy_wh / 1000
                cost = energy_kwh * rate
                
                # Safely access VariableConfig via db.ModelClasses
                config, _ = _get_variable_config_row(include_global_fallback=True)
                if config is None:
                    logger.warning("VariableConfig row not found for scoped single-day estimation, using defaults")
                
                co2_factor = float(config.co2_factor) if config and hasattr(config, 'co2_factor') else 0.4
                co2 = energy_kwh * co2_factor
                
                # Create estimated result
                result = {
                    'totalEnergy': round(energy_wh, 2),  # In Wh
                    'totalCost': round(cost, 2),
                    'avgLoad': round(float(latest.ups_load), 1),
                    'co2': round(co2, 2),
                    'efficiency': {
                        'peak': round(float(latest.ups_load), 1),
                        'average': round(float(latest.ups_load), 1)
                    },
                    'cost_distribution': calculate_cost_distribution([latest], rate),
                    'trends': {'energy': 0, 'cost': 0, 'load': 0, 'co2': 0}
                }
                
                logger.debug(f"Generated estimated day result with latest record: {result}")
                return result
            
        # Calculate stats from available data
        stats = calculate_energy_stats(data, 'hrs')
        
        # If energy is still zero, try to estimate from load data
        if stats['totalEnergy'] == 0 and data:
            load_data = [row for row in data if hasattr(row, 'ups_load') and row.ups_load is not None]
            if load_data:
                # Get the average load
                avg_load = sum(float(row.ups_load or 0) for row in load_data) / len(load_data)
                # Get nominal power (use the first record that has it, or fallback)
                nominal_power = None
                for row in load_data:
                    if hasattr(row, 'ups_realpower_nominal') and row.ups_realpower_nominal is not None:
                        nominal_power = float(row.ups_realpower_nominal)
                        break
                
                if not nominal_power:
                    nominal_power = float(settings.UPS_REALPOWER_NOMINAL)
                
                # Calculate estimated power and energy
                power = (nominal_power * avg_load) / 100  # W
                duration_hours = 24  # Full day
                energy_wh = power * duration_hours  # Wh
                
                # Safely access VariableConfig via db.ModelClasses
                config, _ = _get_variable_config_row(include_global_fallback=True)
                if config is None:
                    logger.warning("VariableConfig row not found for scoped single-day load estimation, using defaults")
                
                co2_factor = float(config.co2_factor) if config and hasattr(config, 'co2_factor') else 0.4
                co2 = energy_wh / 1000 * co2_factor
                
                stats['totalEnergy'] = round(energy_wh, 2)
                stats['totalCost'] = round(energy_wh / 1000 * get_energy_rate(), 2)
                stats['co2'] = round(co2, 2)
                
                logger.debug(f"Updated day stats with estimated values: {stats}")
        
        # Add cost distribution
        rate = get_energy_rate()
        stats['cost_distribution'] = calculate_cost_distribution(data, rate)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error in get_single_day_data: {str(e)}", exc_info=True)
        return default_energy_response()

def get_realtime_trend_data(start_time, end_time):
    """Get real-time data for the chart"""
    UPSDynamicData = get_ups_model()
    data = UPSDynamicData.query\
        .filter(
            UPSDynamicData.timestamp_utc >= start_time,
            UPSDynamicData.timestamp_utc <= end_time,
            UPSDynamicData.ups_realpower.isnot(None)
        ).order_by(UPSDynamicData.timestamp_utc.asc()).all()
        
    return format_trend_data(data, 'realtime')

def get_hourly_trend_data(start_time, end_time):
    """Get hourly data for the chart"""
    UPSDynamicData = get_ups_model()
    data = UPSDynamicData.query\
        .filter(
            UPSDynamicData.timestamp_utc >= start_time,
            UPSDynamicData.timestamp_utc <= end_time,
            UPSDynamicData.ups_realpower_hrs.isnot(None)
        ).order_by(UPSDynamicData.timestamp_utc.asc()).all()
        
    return format_trend_data(data, 'hrs')

def format_trend_data(data, period_type):
    """Format data for the chart"""
    series = []
    rate = get_energy_rate()
    
    for row in data:
        timestamp = int(row.timestamp_utc.timestamp() * 1000)  # Timestamp in milliseconds
        
        if period_type == 'realtime':
            power = float(row.ups_realpower or 0)
        elif period_type == 'hrs':
            power = float(row.ups_realpower_hrs or 0)
        else:
            power = float(row.ups_realpower_days or 0)
            
        cost = (power * rate) / 1000  # Convert to kWh and calculate the cost
        
        series.append([timestamp, round(cost, 2)])
        
    return series

def format_cost_series(data, energy_type='realtime'):
    """Format energy data for the cost chart"""
    rate = get_energy_rate()
    series = []
    
    try:
        if not data:
            return []

        # Batch process all rows for each type
        if energy_type == 'realtime':
            for row in data:
                # Use ups_realpower directly (already in W)
                if hasattr(row, 'ups_realpower') and row.ups_realpower is not None:
                    energy = float(row.ups_realpower) / 1000  # Convert W to kW
                    cost = energy * rate  # Cost per hour at this power
                    # Divide by 60 to get cost per minute
                    cost_per_minute = cost / 60
                    
                    # Get UTC timestamp (potentially naive)
                    timestamp_utc_naive = row.timestamp_utc
                    if timestamp_utc_naive is None: continue

                    # Force UTC timezone info and then convert to local
                    timestamp_utc_aware = timestamp_utc_naive.replace(tzinfo=pytz.utc)
                    timestamp_local = timestamp_utc_aware.astimezone(current_app.CACHE_TIMEZONE)
                    
                    # Log both timestamps for debugging
                    logger.debug(f"Data point: UTC={timestamp_utc_aware.isoformat()} (Hour: {timestamp_utc_aware.hour}), Local={timestamp_local.isoformat()} (Hour: {timestamp_local.hour})")
                    
                    series.append({
                        'x': timestamp_local.timestamp() * 1000,  # Convert LOCAL timestamp to milliseconds
                        'y': round(cost_per_minute, 4),
                        # Add debug info
                        'debug': {
                            'utc': timestamp_utc_aware.isoformat(),
                            'local': timestamp_local.isoformat(),
                            'hour_utc': timestamp_utc_aware.hour,
                            'hour_local': timestamp_local.hour
                        }
                    })
        elif energy_type == 'hrs':
            for row in data:
                if hasattr(row, 'ups_realpower_hrs') and row.ups_realpower_hrs is not None:
                    energy_kwh = float(row.ups_realpower_hrs) / 1000  # Convert Wh to kWh
                    cost = energy_kwh * rate
                    
                    # Get UTC timestamp (potentially naive)
                    timestamp_utc_naive = row.timestamp_utc
                    if timestamp_utc_naive is None: continue

                    # Force UTC timezone info and then convert to local
                    timestamp_utc_aware = timestamp_utc_naive.replace(tzinfo=pytz.utc)
                    timestamp_local = timestamp_utc_aware.astimezone(current_app.CACHE_TIMEZONE)
                    
                    # Log both timestamps for debugging
                    logger.debug(f"Data point (hrs): UTC={timestamp_utc_aware.isoformat()}, Local={timestamp_local.isoformat()}")
                    
                    series.append({
                        'x': timestamp_local.timestamp() * 1000,  # Convert LOCAL timestamp to milliseconds
                        'y': round(cost, 4),
                        # Add debug info
                        'debug': {
                            'utc': timestamp_utc_aware.isoformat(),
                            'local': timestamp_local.isoformat(),
                            'hour_utc': timestamp_utc_aware.hour,
                            'hour_local': timestamp_local.hour
                        }
                    })
        elif energy_type == 'calculated':
            prev_timestamp_aware = None # Initialize before loop for calculated block
            prev_power = None
            added_count = 0
            skipped_count = 0
            
            logger.debug("Format Cost Series: Trying 'calculated' method.")
            for i, row in enumerate(data):
                ts_str = getattr(row, 'timestamp_utc', 'N/A')
                
                # Check required attributes directly
                current_load = getattr(row, 'ups_load', None)
                current_nominal_power = getattr(row, 'ups_realpower_nominal', None)

                if current_load is None or current_nominal_power is None:
                    reason = []
                    if current_load is None: reason.append("ups_load is None")
                    if current_nominal_power is None: reason.append("ups_realpower_nominal is None")
                    logger.debug(f"format_cost_series (calculated): Skipping row {i} (ts={ts_str}) - Reason: {', '.join(reason)}")
                    skipped_count += 1
                    prev_power = None # Reset previous power as interval is broken
                    prev_timestamp_aware = None # Reset aware timestamp on error
                    continue
                
                # If we have load and nominal, proceed
                try:
                    current_timestamp_naive = row.timestamp_utc
                    if current_timestamp_naive is None: continue

                    # Make current timestamp UTC-aware
                    current_timestamp_aware = current_timestamp_naive.replace(tzinfo=pytz.utc)

                    # Calculate power here (this line was likely deleted)
                    current_power = (float(current_nominal_power) * float(current_load)) / 100  # W

                    # Ensure prev_timestamp_aware is defined and aware if not None
                    # (It should be aware from the previous iteration's assignment)

                    if prev_timestamp_aware is not None and prev_power is not None:
                        # Calculate duration in hours
                        duration = (current_timestamp_aware - prev_timestamp_aware).total_seconds() / 3600
                        
                        # Skip if time diff is too large or zero/negative
                        if duration <= 0 or duration > 2:
                            logger.debug(f"format_cost_series (calculated): Skipping interval at row {i} (ts={ts_str}) - Duration {duration:.4f}h out of bounds (0, 2]")
                            # Don't increment skipped_count here, just move the window
                        else: 
                            # Calculate average power during this interval
                            avg_power = (current_power + prev_power) / 2  # W
                            
                            # Energy in kWh
                            energy_kwh = (avg_power * duration) / 1000
                            
                            # Cost
                            cost = energy_kwh * rate
                            
                            # Convert the *current* timestamp to local for the x-axis value
                            timestamp_local = current_timestamp_aware.astimezone(current_app.CACHE_TIMEZONE)
                            
                            # Log both timestamps for debugging
                            logger.debug(f"Data point (calc): UTC={current_timestamp_aware.isoformat()}, Local={timestamp_local.isoformat()}")
                            
                            # Add to series at the current timestamp
                            series.append({
                                'x': timestamp_local.timestamp() * 1000,  # Convert LOCAL timestamp to milliseconds
                                'y': round(cost, 6), # Use more precision for minutes
                                # Add debug info
                                'debug': {
                                    'utc': current_timestamp_aware.isoformat(),
                                    'local': timestamp_local.isoformat(),
                                    'hour_utc': current_timestamp_aware.hour,
                                    'hour_local': timestamp_local.hour
                                }
                            })
                            added_count += 1
                    else:
                         # First point in a sequence, cannot calculate interval yet
                         logger.debug(f"format_cost_series (calculated): Row {i} (ts={ts_str}) - First point, initializing prev values")
                    
                    # Update previous values for the next iteration - store the AWARE timestamp
                    prev_timestamp_aware = current_timestamp_aware # Store aware timestamp
                    prev_power = current_power
                except Exception as e:
                     logger.warning(f"format_cost_series (calculated): Error processing row {i} (ts={ts_str}): {e}")
                     skipped_count += 1
                     # Reset prev values on error
                     prev_power = None
                     prev_timestamp_aware = None
                     
            logger.debug(f"format_cost_series (calculated): Processed {len(data)} rows, added {added_count} points, skipped {skipped_count} rows")
            
        # If series is empty, check if we can calculate from other available data
        if not series and energy_type != 'calculated' and hasattr(data[0], 'ups_load') and hasattr(data[0], 'ups_realpower_nominal'):
            logger.debug(f"No {energy_type} data found for cost series, using calculated values")
            return format_cost_series(data, 'calculated')
            
        return series
    except Exception as e:
        logger.error(f"Error formatting cost series: {str(e)}")
        return []

def calculate_cost_distribution(data, rate):
    """Calculate how energy cost is distributed across the day"""
    try:
        # Initialize the distribution structure
        distribution = {
            'morning': 0,    # 6:00-12:00
            'afternoon': 0,  # 12:00-18:00
            'evening': 0,    # 18:00-22:00
            'night': 0       # 22:00-6:00
        }
        
        if not data:
            return distribution
        
        # First check if we have ups_realpower_hrs data
        has_hrs_data = len(data) > 0 and hasattr(data[0], 'ups_realpower_hrs') and any(row.ups_realpower_hrs is not None for row in data)
        
        if has_hrs_data:
            # Process with ups_realpower_hrs
            for row in data:
                if row.ups_realpower_hrs is None:
                    continue
                    
                hour = row.timestamp_utc.hour
                energy_kwh = float(row.ups_realpower_hrs) / 1000
                cost = energy_kwh * rate
                
                # Assign to the appropriate time period
                if 6 <= hour < 12:
                    distribution['morning'] += cost
                elif 12 <= hour < 18:
                    distribution['afternoon'] += cost
                elif 18 <= hour < 22:
                    distribution['evening'] += cost
                else:
                    distribution['night'] += cost
        else:
            # Calculate from load and nominal power
            valid_data_points = [row for row in data if hasattr(row, 'ups_load') and 
                                               hasattr(row, 'ups_realpower_nominal') and
                                               row.ups_load is not None and 
                                               row.ups_realpower_nominal is not None]
            
            # If we have only one data point, estimate cost distribution based on time of day
            if len(valid_data_points) == 1:
                row = valid_data_points[0]
                hour = row.timestamp_utc.hour
                power = (float(row.ups_realpower_nominal) * float(row.ups_load)) / 100  # W
                # Estimate energy over a 15-minute period (0.25 hours)
                energy_kwh = (power * 0.25) / 1000  # kWh
                cost = energy_kwh * rate
                
                # Assign to the appropriate time period
                if 6 <= hour < 12:
                    distribution['morning'] += cost
                elif 12 <= hour < 18:
                    distribution['afternoon'] += cost
                elif 18 <= hour < 22:
                    distribution['evening'] += cost
                else:
                    distribution['night'] += cost
            elif len(valid_data_points) > 1:
                prev_timestamp_aware = None # Initialize before loop for calculated block
                prev_power = None
                
                for row in valid_data_points:                    
                    current_timestamp_naive = row.timestamp_utc
                    if current_timestamp_naive is None: continue # Skip if timestamp is missing

                    # Make current timestamp UTC-aware
                    current_timestamp_aware = current_timestamp_naive.replace(tzinfo=pytz.utc)

                    # Calculate power here (this line was likely deleted)
                    current_power = (float(row.ups_realpower_nominal) * float(row.ups_load)) / 100  # W

                    if prev_timestamp_aware is not None and prev_power is not None:
                        # Calculate duration in hours
                        duration = (current_timestamp_aware - prev_timestamp_aware).total_seconds() / 3600
                        
                        # Skip if time difference is too large (more than 2 hours)
                        if duration > 2:
                            prev_timestamp_aware = current_timestamp_aware
                            prev_power = current_power
                            continue
                            
                        # Calculate average power during this interval
                        avg_power = (current_power + prev_power) / 2  # W
                        
                        # Energy in kWh
                        energy_kwh = (avg_power * duration) / 1000
                        
                        # Cost
                        cost = energy_kwh * rate
                        
                        # Assign to the appropriate time period based on midpoint of interval
                        # Make midpoint aware for correct hour extraction
                        mid_timestamp_aware = prev_timestamp_aware + (current_timestamp_aware - prev_timestamp_aware) / 2
                        hour = mid_timestamp_aware.hour # Hour in UTC
                        
                        if 6 <= hour < 12:
                            distribution['morning'] += cost
                        elif 12 <= hour < 18:
                            distribution['afternoon'] += cost
                        elif 18 <= hour < 22:
                            distribution['evening'] += cost
                        else:
                            distribution['night'] += cost
                    
                    # Update previous values
                    prev_timestamp_aware = current_timestamp_aware # Store aware timestamp
                    prev_power = current_power
        
        # Check if we have a valid distribution (any non-zero value)
        has_distribution = any(value > 0 for value in distribution.values())
        
        # If all values are zero but we have valid data, create a minimum distribution
        if not has_distribution and (has_hrs_data or len(valid_data_points) > 0):
            # Calculate a minimum distribution based on current time
            current_hour = datetime.now().hour
            min_cost = 0.01  # Minimum cost to display
            
            if 6 <= current_hour < 12:
                distribution['morning'] = min_cost
            elif 12 <= current_hour < 18:
                distribution['afternoon'] = min_cost
            elif 18 <= current_hour < 22:
                distribution['evening'] = min_cost
            else:
                distribution['night'] = min_cost
        
        # Round values
        for key in distribution:
            distribution[key] = round(distribution[key], 2)
            
        return distribution
        
    except Exception as e:
        logger.error(f"Error calculating cost distribution: {str(e)}", exc_info=True)
        return {
            'morning': 0,
            'afternoon': 0,
            'evening': 0,
            'night': 0
        }

def get_cost_trend_for_range(start_time, end_time):
    """Get cost trend data for a date range"""
    try:
        UPSDynamicData = get_ups_model()
        
        logger.debug(f"Getting cost trend for range: {start_time} to {end_time}")
        
        # Get all data for the range without filtering on specific columns
        data = UPSDynamicData.query\
            .filter(
                UPSDynamicData.timestamp_utc >= start_time,
                UPSDynamicData.timestamp_utc <= end_time
            ).order_by(UPSDynamicData.timestamp_utc.asc()).all()
        
        logger.debug(f"Found {len(data)} records for date range")
        
        series = []
        rate = get_energy_rate()
        
        # Initialize day_data dictionary to track daily energy values
        day_data = {}
        
        # First try to use ups_realpower_hrs data (hourly energy data)
        has_hrs_data = data and len(data) > 0 and hasattr(data[0], 'ups_realpower_hrs') and any(d.ups_realpower_hrs is not None for d in data)
        
        if has_hrs_data:
            logger.debug("Using ups_realpower_hrs data for range trend")
            # Group by day and sum the energy
            for row in data:
                if not hasattr(row, 'ups_realpower_hrs') or row.ups_realpower_hrs is None:
                    continue
                    
                day_key = row.timestamp_utc.strftime('%Y-%m-%d')
                if day_key not in day_data:
                    day_data[day_key] = 0
                
                # Convert Wh to kWh for the cost calculation
                day_data[day_key] += float(row.ups_realpower_hrs) / 1000
        else:
            # Fall back to calculating from load and nominal power
            logger.debug("No ups_realpower_hrs data found, using load and nominal power")
            
            # First try to group records by day to calculate daily energy
            day_records = {}
            
            for row in data:
                if not hasattr(row, 'ups_load') or not hasattr(row, 'ups_realpower_nominal'):
                    continue
                    
                if row.ups_load is None or row.ups_realpower_nominal is None:
                    continue
                
                day_key = row.timestamp_utc.strftime('%Y-%m-%d')
                if day_key not in day_records:
                    day_records[day_key] = []
                
                day_records[day_key].append(row)
            
            # Now calculate energy for each day using time-weighted approach
            for day_key, records in day_records.items():
                if len(records) == 0:
                    continue
                    
                # Sort by timestamp to ensure proper sequential processing
                records.sort(key=lambda x: x.timestamp_utc)
                
                # Initialize day's energy
                day_energy_kwh = 0
                
                # Use time-weighted approach for multiple records in a day
                if len(records) > 1:
                    prev_timestamp_aware = None
                    prev_power = None
                    
                    for row in records:
                        current_timestamp_naive = row.timestamp_utc
                        if current_timestamp_naive is None: continue # Skip if timestamp is missing

                        # Make current timestamp UTC-aware
                        current_timestamp_aware = current_timestamp_naive.replace(tzinfo=pytz.utc)

                        # Calculate power here (this line was likely deleted)
                        current_power = (float(row.ups_realpower_nominal) * float(row.ups_load)) / 100  # W

                        if prev_timestamp_aware is not None and prev_power is not None:
                            # Calculate duration in hours
                            duration = (current_timestamp_aware - prev_timestamp_aware).total_seconds() / 3600
                            
                            # Skip if time difference is too large or non-positive
                            if duration <= 0 or duration > 2:
                                # Still update prev values even if skipping interval calculation
                                prev_timestamp_aware = current_timestamp_aware
                                prev_power = current_power
                                continue
                                
                            # Calculate average power during this interval
                            avg_power = (current_power + prev_power) / 2  # W
                            
                            # Energy in kWh = power (W) * time (h) / 1000
                            interval_energy_kwh = (avg_power * duration) / 1000
                            day_energy_kwh += interval_energy_kwh
                        
                        # Update previous values
                        prev_timestamp_aware = current_timestamp_aware # Store aware timestamp
                        prev_power = current_power
                else:
                    # For a single record in a day, estimate energy based on average load
                    row = records[0]
                    # Use 8 hours as a reasonable default duration if we only have one data point
                    power = (float(row.ups_realpower_nominal) * float(row.ups_load)) / 100  # W
                    day_energy_kwh = (power * 8) / 1000  # kWh
                
                # Store the day's energy
                day_data[day_key] = day_energy_kwh
        
        # Create a complete series with all days in the range, including those with zero energy
        current_date = start_time.date()
        end_date = end_time.date()
        
        while current_date <= end_date:
            day_key = current_date.strftime('%Y-%m-%d')
            timestamp = int(datetime.combine(current_date, datetime.min.time()).timestamp() * 1000)
            
            energy_kwh = day_data.get(day_key, 0)
            cost = energy_kwh * rate
            
            # Use more precision for small values
            if cost < 0.1:
                cost_rounded = round(cost, 3)
            else:
                cost_rounded = round(cost, 2)
                
            # Only add non-zero values if we have data
            if cost_rounded > 0 or not day_data:
                series.append({
                    'x': timestamp,
                    'y': cost_rounded
                })
            
            current_date += timedelta(days=1)
        
        # Ensure we have at least one data point per day
        if not series:
            # Create minimal placeholder data
            current_date = start_time.date()
            while current_date <= end_date:
                timestamp = int(datetime.combine(current_date, datetime.min.time()).timestamp() * 1000)
                series.append({
                    'x': timestamp,
                    'y': 0.01  # Minimal cost to display
                })
                current_date += timedelta(days=1)
        
        # Ensure the series is sorted by timestamp
        series.sort(key=lambda x: x['x'])
        
        logger.debug(f"Generated cost trend series with {len(series)} data points")
        return series
    
    except Exception as e:
        logger.error(f"Error in get_cost_trend_for_range: {str(e)}", exc_info=True)
        return []
