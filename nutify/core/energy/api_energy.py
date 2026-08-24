"""Energy API Module.

Defines API endpoints and response handlers for this feature domain.
"""

from flask import jsonify, request, current_app
from datetime import datetime, timedelta, timezone, time
from sqlalchemy import func
import pytz

from core.db.ups import (
    get_ups_model, data_lock, VariableConfig
)
from core.logger import energy_logger as logger
from core.multi_nut.domain_proxy import (
    build_energy_cost_series,
    build_energy_detailed_series,
    build_energy_payload,
    has_hour_data as target_has_hour_data,
    list_available_years,
    resolve_target_id,
)

# Import functions from energy module
from .energy import (
    get_energy_data, get_energy_rate, calculate_cost_distribution,
    get_cost_trend_for_range, format_cost_series, calculate_energy_stats, format_realtime_data
)

def register_api_routes(app):
    """Register all API routes for the energy section"""
    
    @app.route('/api/energy/data')
    def get_energy_data_api():
        try:
            target_id = resolve_target_id()
            if target_id:
                period_type = str(request.args.get('type') or request.args.get('period') or 'day').strip().lower()
                from_time = request.args.get('from_time')
                to_time = request.args.get('to_time')
                selected_date = request.args.get('selected_date')
                selected_day = request.args.get('selected_day')

                data = build_energy_payload(
                    target_id=target_id,
                    tz=current_app.CACHE_TIMEZONE,
                    period=period_type,
                    from_time=from_time,
                    to_time=to_time,
                    selected_date=selected_date,
                    selected_day=selected_day,
                )

                data['distribution'] = []
                return jsonify(data)

            days = request.args.get('days', type=int, default=1)
            data = get_energy_data(days)
            # Ensure we're not returning a Response object
            if hasattr(data, 'get_json'):
                data = data.get_json()
            return jsonify(data)
        except Exception as e:
            logger.error(f"Error getting energy data: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/energy/has_hour_data')
    def api_energy_has_hour_data():
        """
        API endpoint to check if there is at least 60 minutes of energy data.
        
        Returns:
            JSON response with a boolean indicating if enough data exists.
        """
        try:
            target_id = resolve_target_id()
            if target_id:
                has_data = target_has_hour_data(target_id, metric_name='ups_realpower')
                if not has_data:
                    has_data = target_has_hour_data(target_id, metric_name='ups_load')
                return jsonify({'has_data': bool(has_data)})

            UPSDynamicData = get_ups_model()
            tz = current_app.CACHE_TIMEZONE
            logger.debug(f"Using timezone: {tz.zone}")
            
            # Get current time in UTC directly (using naive datetime for SQLite compatibility)
            now_utc = datetime.utcnow()
            one_hour_ago_utc = now_utc - timedelta(hours=1)
            
            # Format for logging
            now_str = now_utc.strftime('%Y-%m-%d %H:%M:%S')
            one_hour_ago_str = one_hour_ago_utc.strftime('%Y-%m-%d %H:%M:%S')
            
            # Log the time values for debugging
            logger.debug(f"Checking for energy data between {one_hour_ago_str} and {now_str} (UTC)")
            
            # Query to find records in the last hour with valid ups_realpower
            data = UPSDynamicData.query\
                .filter(
                    UPSDynamicData.timestamp_utc >= one_hour_ago_utc,
                    UPSDynamicData.timestamp_utc <= now_utc,
                    UPSDynamicData.ups_realpower.isnot(None)
                ).order_by(UPSDynamicData.timestamp_utc.asc()).all()
            
            # Get the count of data points
            data_count = len(data)
            logger.debug(f"Found {data_count} energy data points in the query")
            
            # Check if we have at least 30 data points (minimum threshold)
            if data_count < 30:
                logger.debug(f"Insufficient data points: {data_count} < 30")
                return jsonify({'has_data': False})
            
            # Check if we have data spanning at least 50 minutes
            if data:
                timestamps = [record.timestamp_utc for record in data]
                first_timestamp = min(timestamps)
                last_timestamp = max(timestamps)
                
                time_span_minutes = (last_timestamp - first_timestamp).total_seconds() / 60
                
                logger.debug(f"Data time span: {time_span_minutes:.2f} minutes with {data_count} points")
                logger.debug(f"First record: {first_timestamp}, Last record: {last_timestamp}")
                
                # Require at least 50 minutes of data
                has_sufficient_data = time_span_minutes >= 50
                
                # Add additional debug output
                logger.debug(f"Final decision - has_sufficient_data: {has_sufficient_data}")
                
                return jsonify({'has_data': has_sufficient_data})
            
            logger.debug("No data found after filtering")
            return jsonify({'has_data': False})
            
        except Exception as e:
            logger.error(f"Error checking for hour data: {str(e)}")
            return jsonify({'has_data': False, 'error': str(e)})

    @app.route('/api/energy/cost-trend')
    def get_cost_trend_data():
        """Get cost trend data for the specified period"""
        try:
            period_type = request.args.get('type', 'day')
            from_time = request.args.get('from_time')
            to_time = request.args.get('to_time')
            selected_date = request.args.get('selected_date')
            selected_day = request.args.get('selected_day')
            target_id = resolve_target_id()

            if target_id:
                series = build_energy_cost_series(
                    target_id=target_id,
                    tz=current_app.CACHE_TIMEZONE,
                    period=period_type,
                    from_time=from_time,
                    to_time=to_time,
                    selected_date=selected_date,
                    selected_day=selected_day,
                )
                return jsonify({
                    'success': True,
                    'series': series
                })

            UPSDynamicData = get_ups_model()
            
            logger.debug(f"Cost trend request - type: {period_type}, from: {from_time}, to: {to_time}")
            series = []
            
            tz = current_app.CACHE_TIMEZONE
            
            if period_type == 'range':
                # Improved timezone handling for date range data
                tz = current_app.CACHE_TIMEZONE
                
                try:
                    # Parse dates in the configured timezone
                    from_date_local = datetime.strptime(from_time, '%Y-%m-%d').date()
                    to_date_local = datetime.strptime(to_time, '%Y-%m-%d').date()
                    
                    # Create start and end datetime objects in the local timezone
                    start_time_local = tz.localize(datetime.combine(from_date_local, time.min))  # Start of first day
                    end_time_local = tz.localize(datetime.combine(to_date_local, time.max))     # End of last day
                    
                    # Convert to UTC for database query
                    start_time = start_time_local.astimezone(pytz.UTC)
                    end_time = end_time_local.astimezone(pytz.UTC)
                    
                    # Detailed logging for debugging
                    logger.debug(f"RANGE query parameters:")
                    logger.debug(f"  Local timezone: {tz.zone}")
                    logger.debug(f"  From date: {from_time}, To date: {to_time}")
                    logger.debug(f"  Start time (local): {start_time_local.isoformat()}")
                    logger.debug(f"  End time (local): {end_time_local.isoformat()}")
                    logger.debug(f"  Start time (UTC): {start_time.isoformat()}")
                    logger.debug(f"  End time (UTC): {end_time.isoformat()}")
                    
                    # Get the cost trend data for the date range
                    series = get_cost_trend_for_range(start_time, end_time)
                    logger.debug(f"RANGE query returned {len(series)} data points")
                    
                except ValueError as e:
                    logger.error(f"Invalid date format: {str(e)}")
                    return jsonify({
                        'success': False,
                        'error': f"Invalid date format: {str(e)}"
                    })
                    
            elif period_type == 'realtime':
                # Improved timezone handling for realtime data
                tz = current_app.CACHE_TIMEZONE
                
                # Get current time in the configured timezone
                end_time_local = datetime.now(tz)
                # Get time 5 minutes ago in the configured timezone
                start_time_local = end_time_local - timedelta(minutes=5)
                
                # Convert to UTC for database query
                end_time = end_time_local.astimezone(pytz.UTC)
                start_time = start_time_local.astimezone(pytz.UTC)
                
                # Detailed logging for debugging
                logger.debug(f"REALTIME query parameters:")
                logger.debug(f"  Local timezone: {tz.zone}")
                logger.debug(f"  Current time (local): {end_time_local.isoformat()}")
                logger.debug(f"  Start time (local): {start_time_local.isoformat()}")
                logger.debug(f"  Start time (UTC): {start_time.isoformat()}")
                logger.debug(f"  End time (UTC): {end_time.isoformat()}")
                
                # Query with explicit UTC timestamp filter
                data = UPSDynamicData.query\
                    .filter(
                        UPSDynamicData.timestamp_utc >= start_time,
                        UPSDynamicData.timestamp_utc <= end_time
                    ).order_by(UPSDynamicData.timestamp_utc.asc()).all()
                
                # Log query results
                logger.debug(f"REALTIME query found {len(data)} records")
                
                # Check if we have ups_realpower data
                if data and hasattr(data[0], 'ups_realpower') and any(d.ups_realpower is not None for d in data):
                    logger.debug(f"REALTIME using ups_realpower data")
                    series = format_cost_series(data, 'realtime')
                else:
                    # If no ups_realpower data, try load and nominal power
                    logger.debug(f"REALTIME falling back to calculated values")
                    series = format_cost_series(data, 'calculated')

            elif period_type == 'today':
                # Improved timezone handling for today's data
                tz = current_app.CACHE_TIMEZONE
                
                # Get current local time in the configured timezone
                now_local = datetime.now(tz)
                today_local = now_local.date()
                
                # Parse time strings
                try:
                    from_time_obj = datetime.strptime(from_time, '%H:%M').time()
                    to_time_obj = datetime.strptime(to_time, '%H:%M').time()
                except ValueError as e:
                    logger.error(f"Invalid time format: {str(e)}")
                    return jsonify({
                        'success': False,
                        'error': f"Invalid time format: {str(e)}"
                    })
                
                # Create timezone-aware datetime objects in local timezone
                start_time_local = tz.localize(datetime.combine(today_local, from_time_obj))
                end_time_local = tz.localize(datetime.combine(today_local, to_time_obj))
                
                # Convert to UTC for database query
                start_time = start_time_local.astimezone(pytz.UTC)
                end_time = end_time_local.astimezone(pytz.UTC)
                
                # Comprehensive logging for debugging
                logger.debug(f"TODAY query parameters:")
                logger.debug(f"  Local timezone: {tz.zone}")
                logger.debug(f"  Current time (local): {now_local.isoformat()}")
                logger.debug(f"  Today's date (local): {today_local.isoformat()}")
                logger.debug(f"  From time: {from_time}, To time: {to_time}")
                logger.debug(f"  Start time (local): {start_time_local.isoformat()}")
                logger.debug(f"  End time (local): {end_time_local.isoformat()}")
                logger.debug(f"  Start time (UTC): {start_time.isoformat()}")
                logger.debug(f"  End time (UTC): {end_time.isoformat()}")
                
                # Query data for the range using UTC timestamps
                data = UPSDynamicData.query\
                    .filter(
                        UPSDynamicData.timestamp_utc >= start_time,
                        UPSDynamicData.timestamp_utc <= end_time
                    ).order_by(UPSDynamicData.timestamp_utc.asc()).all()
                
                logger.debug(f"TODAY query found {len(data)} records")

                # --- Start Strict Priority Logic (copied from DAY block) ---
                series = []
                # 1. Try hrs
                has_hrs_data = data and hasattr(data[0], 'ups_realpower_hrs') and any(d.ups_realpower_hrs is not None for d in data)
                if has_hrs_data:
                    logger.debug("TODAY (logic copied from DAY) trying 'hrs' data...")
                    series = format_cost_series(data, 'hrs')
                
                # 2. Try aggregated minutes if hrs failed
                if not series:
                    logger.debug("TODAY (logic copied from DAY) 'hrs' failed, trying aggregation...")
                    has_realpower_data = data and hasattr(data[0], 'ups_realpower') and any(d.ups_realpower is not None for d in data)
                    if has_realpower_data:
                         # Assuming aggregate_minute_data_to_hourly_series exists and works as intended
                         try:
                             # Try importing the aggregation function if it exists
                             from .energy import aggregate_minute_data_to_hourly_series
                             series = aggregate_minute_data_to_hourly_series(data)
                             if series: logger.debug(f"TODAY (logic copied from DAY) aggregation succeeded ({len(series)} points)")
                             else: logger.debug("TODAY (logic copied from DAY) aggregation failed or returned empty")
                         except ImportError:
                             logger.warning("TODAY (logic copied from DAY) aggregate_minute_data_to_hourly_series function not found.")
                             series = [] # Ensure series is empty if function missing
                         except Exception as agg_err:
                             logger.error(f"TODAY (logic copied from DAY) error during aggregation: {agg_err}")
                             series = []
                    else: logger.debug("TODAY (logic copied from DAY) no ups_realpower data for aggregation")

                # 3. Try calculated if both failed
                if not series:
                    logger.debug("TODAY (logic copied from DAY) aggregation failed, trying 'calculated'...")
                    has_calc_data = data and hasattr(data[0], 'ups_load') and hasattr(data[0], 'ups_realpower_nominal') and any(d.ups_load is not None and d.ups_realpower_nominal is not None for d in data)
                    if has_calc_data:
                        series = format_cost_series(data, 'calculated')
                        if series: logger.debug(f"TODAY (logic copied from DAY) 'calculated' succeeded ({len(series)} points)")
                        else: logger.debug("TODAY (logic copied from DAY) 'calculated' failed")
                    else: logger.debug("TODAY (logic copied from DAY) no ups_load/nominal data for calculation")
                
                # 4. Ensure empty list if all failed
                if not series:
                     series = []
                     logger.warning("TODAY (logic copied from DAY) All data formatting attempts failed, returning empty series.")
                # --- End Strict Priority Logic (copied from DAY block) ---
                
            elif period_type == 'day':
                # Improved timezone handling for specific day data
                tz = current_app.CACHE_TIMEZONE
                
                try:
                    # Parse the date in the local timezone
                    date_local = datetime.strptime(from_time, '%Y-%m-%d').date()
                    
                    # Create start and end datetime objects in the local timezone
                    start_time_local = tz.localize(datetime.combine(date_local, time.min))  # Start of day (00:00:00)
                    end_time_local = tz.localize(datetime.combine(date_local, time.max))    # End of day (23:59:59)
                    
                    # Convert to UTC for database query
                    start_time = start_time_local.astimezone(pytz.UTC)
                    end_time = end_time_local.astimezone(pytz.UTC)
                    
                    # Detailed logging for debugging
                    logger.debug(f"DAY query parameters:")
                    logger.debug(f"  Local timezone: {tz.zone}")
                    logger.debug(f"  Requested date: {from_time}")
                    logger.debug(f"  Date parsed as: {date_local.isoformat()}")
                    logger.debug(f"  Start time (local): {start_time_local.isoformat()}")
                    logger.debug(f"  End time (local): {end_time_local.isoformat()}")
                    logger.debug(f"  Start time (UTC): {start_time.isoformat()}")
                    logger.debug(f"  End time (UTC): {end_time.isoformat()}")
                except ValueError as e:
                    logger.error(f"Invalid date format: {str(e)}")
                    return jsonify({
                        'success': False,
                        'error': f"Invalid date format: {str(e)}"
                    })
                
                # Query data for the UTC date range
                data = UPSDynamicData.query\
                    .filter(
                        UPSDynamicData.timestamp_utc >= start_time,
                        UPSDynamicData.timestamp_utc <= end_time
                    ).order_by(UPSDynamicData.timestamp_utc.asc()).all()
                
                logger.debug(f"DAY query found {len(data)} records")

                # --- Start Strict Priority Logic (similar to today) ---
                series = []
                # 1. Try hrs
                has_hrs_data = data and hasattr(data[0], 'ups_realpower_hrs') and any(d.ups_realpower_hrs is not None for d in data)
                if has_hrs_data:
                    logger.debug("DAY trying 'hrs' data...")
                    series = format_cost_series(data, 'hrs')
                
                # 2. Try aggregated minutes if hrs failed
                if not series:
                    logger.debug("DAY 'hrs' failed, trying aggregation...")
                    has_realpower_data = data and hasattr(data[0], 'ups_realpower') and any(d.ups_realpower is not None for d in data)
                    if has_realpower_data:
                         series = aggregate_minute_data_to_hourly_series(data)
                         if series: logger.debug(f"DAY aggregation succeeded ({len(series)} points)")
                         else: logger.debug("DAY aggregation failed")
                    else: logger.debug("DAY no ups_realpower data for aggregation")

                # 3. Try calculated if both failed
                if not series:
                    logger.debug("DAY aggregation failed, trying 'calculated'...")
                    has_calc_data = data and hasattr(data[0], 'ups_load') and hasattr(data[0], 'ups_realpower_nominal') and any(d.ups_load is not None and d.ups_realpower_nominal is not None for d in data)
                    if has_calc_data:
                        series = format_cost_series(data, 'calculated')
                        if series: logger.debug(f"DAY 'calculated' succeeded ({len(series)} points)")
                        else: logger.debug("DAY 'calculated' failed")
                    else: logger.debug("DAY no ups_load/nominal data for calculation")
                
                # 4. Ensure empty list if all failed
                if not series:
                     series = []
                     logger.warning("DAY All data formatting attempts failed, returning empty series.")
                # --- End Strict Priority Logic ---

            # Log data points being sent back
            logger.debug(f"Returning {len(series)} data points for period_type: {period_type}")
            if series and len(series) > 0:
                logger.debug(f"First point: timestamp={datetime.fromtimestamp(series[0]['x']/1000, tz=timezone.utc).isoformat()}, value={series[0]['y']}")
                logger.debug(f"Last point: timestamp={datetime.fromtimestamp(series[-1]['x']/1000, tz=timezone.utc).isoformat()}, value={series[-1]['y']}")

            return jsonify({
                'success': True,
                'series': series
            })
            
        except Exception as e:
            logger.error(f"Error getting cost trend data: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            })

    @app.route('/api/energy/available-years')
    def get_available_years():
        """Return the years for which data is available, limited to the last 5"""
        try:
            target_id = resolve_target_id()
            if target_id:
                return jsonify(list_available_years(target_id))

            UPSDynamicData = get_ups_model()
            with data_lock:
                years = UPSDynamicData.query\
                    .with_entities(func.extract('year', UPSDynamicData.timestamp_utc))\
                    .distinct()\
                    .order_by(func.extract('year', UPSDynamicData.timestamp_utc).desc())\
                    .limit(5)\
                    .all()
                
            return jsonify([int(year[0]) for year in years])
        except Exception as e:
            logger.error(f"Error getting available years: {str(e)}")
            return jsonify([])

    @app.route('/api/energy/detailed')
    def get_energy_detailed_data():
        try:
            from_time = request.args.get('from_time')
            to_time = request.args.get('to_time')
            detail_type = request.args.get('detail_type')  # 'day', 'hour', 'minute'
            target_id = resolve_target_id()
            
            logger.debug(f"Get detailed energy data - type: {detail_type}, from: {from_time}, to: {to_time}")
            
            if not from_time or not to_time or not detail_type:
                logger.error(f"Missing required parameters: from_time={from_time}, to_time={to_time}, detail_type={detail_type}")
                return jsonify({
                    'success': False,
                    'error': 'Missing required parameters'
                })

            if target_id:
                series = build_energy_detailed_series(
                    target_id=target_id,
                    tz=current_app.CACHE_TIMEZONE,
                    from_iso=from_time,
                    to_iso=to_time,
                    detail_type=detail_type,
                )
                return jsonify({
                    'success': True,
                    'series': series
                })
            
            tz = current_app.CACHE_TIMEZONE
            
            try:
                # Fix timezone format for ISO parsing if needed (input is UTC string)
                if from_time.endswith("Z"):
                    from_time_utc_str = from_time.replace("Z", "+00:00")
                elif "+" not in from_time:
                     # Assume UTC if no offset specified
                    from_time_utc_str = from_time + "+00:00" 
                else:
                    from_time_utc_str = from_time
                    
                if to_time.endswith("Z"):
                    to_time_utc_str = to_time.replace("Z", "+00:00")
                elif "+" not in to_time:
                    to_time_utc_str = to_time + "+00:00"
                else:
                    to_time_utc_str = to_time

                # Parse the UTC strings into UTC-aware datetime objects
                start_time_utc = datetime.fromisoformat(from_time_utc_str)
                end_time_utc = datetime.fromisoformat(to_time_utc_str)

                # Ensure they are indeed UTC, might not be needed if fromisoformat handles +00:00 correctly
                start_time_utc = start_time_utc.astimezone(pytz.utc)
                end_time_utc = end_time_utc.astimezone(pytz.utc)
                
                # Log the UTC range used for query
                logger.debug(f"Querying DB with UTC range: {start_time_utc.isoformat()} to {end_time_utc.isoformat()}")

            except Exception as e:
                logger.error(f"Error parsing time format or converting to UTC: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': f"Invalid time format: {str(e)}"
                })
            
            UPSDynamicData = get_ups_model()
            
            if detail_type == 'day':
                # For the DateRange modal: show the 24 hours of the day
                data = UPSDynamicData.query\
                    .filter(
                        UPSDynamicData.timestamp_utc >= start_time_utc, # Use UTC time
                        UPSDynamicData.timestamp_utc <= end_time_utc  # Use UTC time
                    )\
                    .order_by(UPSDynamicData.timestamp_utc.asc()).all()
                    
                logger.debug(f"Found {len(data)} records for day detail between {start_time_utc} and {end_time_utc}") # Log UTC
                    
                # Check if we have ups_realpower_hrs data
                has_hrs_data = data and len(data) > 0 and hasattr(data[0], 'ups_realpower_hrs') and any(d.ups_realpower_hrs is not None for d in data)
                
                if has_hrs_data:
                    logger.debug("Using ups_realpower_hrs for day detail")
                    series = format_cost_series(data, 'hrs')
                else:
                    logger.debug("Falling back to calculated values for day detail")
                    # Fall back to calculated values
                    series = format_cost_series(data, 'calculated')
                
            elif detail_type == 'hour':
                # For the hour modal: show the 60 minutes
                data = UPSDynamicData.query\
                    .filter(
                        UPSDynamicData.timestamp_utc >= start_time_utc, # Use UTC time
                        UPSDynamicData.timestamp_utc <= end_time_utc  # Use UTC time
                    )\
                    .order_by(UPSDynamicData.timestamp_utc.asc()).all()
                    
                logger.debug(f"Found {len(data)} records for hour detail between {start_time_utc} and {end_time_utc}") # Log UTC
                    
                # --- Start Strict Priority Logic ---
                series = []
                # 1. Try realtime (ups_realpower)
                logger.debug("Hour Detail trying 'realtime' format...")
                series = format_cost_series(data, 'realtime')
                
                # 2. Try calculated if realtime failed
                if not series:
                    logger.debug("Hour Detail 'realtime' failed, trying 'calculated'...")
                    # Check if data for calculated exists before calling
                    has_calc_data = data and hasattr(data[0], 'ups_load') and hasattr(data[0], 'ups_realpower_nominal') and any(d.ups_load is not None and d.ups_realpower_nominal is not None for d in data)
                    if has_calc_data:
                        series = format_cost_series(data, 'calculated')
                        if series: logger.debug(f"Hour Detail 'calculated' succeeded ({len(series)} points)")
                        else: logger.debug("Hour Detail 'calculated' failed")
                    else:
                        logger.debug("Hour Detail no ups_load/nominal data for calculation")
                else:
                     logger.debug(f"Hour Detail 'realtime' succeeded ({len(series)} points)")
                
                # 3. Ensure empty list if all failed
                if not series:
                     series = []
                     logger.warning("Hour Detail: All data formatting attempts failed, returning empty series.")
                # --- End Strict Priority Logic ---
            
            elif detail_type == 'minute':
                # For the minute modal: show the 60 minutes (Note: Typo in original comment, should query minutes?)
                # Assuming the query should still fetch data based on the provided UTC range for the hour
                data = UPSDynamicData.query\
                    .filter(
                        UPSDynamicData.timestamp_utc >= start_time_utc, # Use UTC time
                        UPSDynamicData.timestamp_utc <= end_time_utc  # Use UTC time
                    )\
                    .order_by(UPSDynamicData.timestamp_utc.asc()).all()
                    
                logger.debug(f"Found {len(data)} records for minute detail between {start_time_utc} and {end_time_utc}") # Log UTC
                    
                # Check if we have ups_realpower data
                has_realpower_data = data and len(data) > 0 and hasattr(data[0], 'ups_realpower') and any(d.ups_realpower is not None for d in data)
                
                if has_realpower_data:
                    logger.debug("Using ups_realpower for minute detail")
                    series = format_cost_series(data, 'realtime')
                else:
                    logger.debug("Falling back to calculated values for minute detail")
                    # Fall back to calculated values if data exists but no ups_realpower
                    if len(data) > 0:
                        series = format_cost_series(data, 'calculated')
                    else:
                        # Data query was empty
                        series = [] # Explicitly set to empty if no data
            
            else:
                logger.error(f"Invalid detail type: {detail_type}")
                return jsonify({
                    'success': False,
                    'error': f"Invalid detail type: {detail_type}"
                })

            logger.debug(f"Returning series with {len(series)} actual data points")
            
            return jsonify({
                'success': True,
                'series': series
            })
            
        except Exception as e:
            logger.error(f"Error getting detailed energy data: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            })

    return app 
