"""Power API Module.

Defines API endpoints and response handlers for this feature domain.
"""

from flask import jsonify, request, current_app
from datetime import datetime, timedelta
from core.logger import power_logger as logger
from core.auth import require_permission
from core.react_frontend import serve_react_index
from core.settings import get_ups_realpower_nominal
from core.db.ups import get_ups_model
from core.multi_nut.domain_proxy import (
    get_latest_metrics,
    get_metric_history,
    get_metric_stats,
    has_hour_data as target_has_hour_data,
    resolve_target_id,
)
from .power import (
    POTENTIAL_POWER_METRICS,
    get_available_power_metrics,
    get_power_stats,
    get_power_history,
)
from .outlet_groups import build_outlet_group_payload

logger.info("💪 Initializing power API routes")


TARGET_POWER_STATS_METRICS = (
    'ups_realpower',
    'input_voltage',
    'ups_load',
    'ups_realpower_nominal',
)


TARGET_POWER_HISTORY_METRICS = (
    'ups_realpower',
    'ups_power',
    'input_voltage',
)


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _legacy_realtime_window(tz, minutes=5):
    """Return HH:MM window for legacy single-profile realtime fallback."""
    now_local = datetime.now(tz)
    start_local = now_local - timedelta(minutes=max(1, int(minutes)))
    if start_local.date() != now_local.date():
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local.strftime('%H:%M'), now_local.strftime('%H:%M')


def _build_target_power_metrics(target_id):
    """Build available power metrics map from active target snapshot."""
    _, _, metrics = get_latest_metrics(target_id)
    result = {}

    for metric in POTENTIAL_POWER_METRICS:
        value = metrics.get(metric)
        if value is None:
            continue
        try:
            result[metric] = float(value)
        except (TypeError, ValueError):
            continue

    if 'ups_realpower' not in result and 'ups_power' in result:
        result['ups_realpower'] = result['ups_power']

    if 'ups_realpower_nominal' not in result:
        result['ups_realpower_nominal'] = _safe_float(get_ups_realpower_nominal(), 0.0)

    # Keep behavior aligned with legacy API: expose ups_realpower only.
    if 'ups_power' in result:
        del result['ups_power']

    return result


def _calculate_total_energy_wh(points):
    """Estimate energy from power time series."""
    if not points or len(points) < 2:
        return 0.0

    ordered = sorted(points, key=lambda item: item['timestamp'])
    total = 0.0
    previous = ordered[0]
    for current in ordered[1:]:
        delta_hours = (current['timestamp'] - previous['timestamp']) / 3600000.0
        if delta_hours <= 0:
            previous = current
            continue
        delta_hours = min(delta_hours, 1.0 / 3.0)
        total += max(0.0, _safe_float(previous.get('value'))) * delta_hours
        previous = current
    return total


def _build_target_power_stats(target_id, period='day', from_time=None, to_time=None, selected_date=None):
    """Build power stats payload compatible with existing frontend expectations."""
    tz = current_app.CACHE_TIMEZONE
    history = get_metric_history(
        target_id=target_id,
        metric_names=TARGET_POWER_STATS_METRICS,
        tz=tz,
        period=period,
        from_time=from_time,
        to_time=to_time,
        selected_date=selected_date,
    )
    summary = get_metric_stats(history)
    latest_metrics = _build_target_power_metrics(target_id)
    stats = {}

    for metric in TARGET_POWER_STATS_METRICS:
        metric_summary = summary.get(metric) or {
            'min': 0.0,
            'max': 0.0,
            'avg': 0.0,
            'current': 0.0,
            'available': False,
        }
        current_value = metric_summary.get('current', 0.0)
        if metric in latest_metrics:
            current_value = _safe_float(latest_metrics.get(metric), current_value)

        stats[metric] = {
            'min': _safe_float(metric_summary.get('min')),
            'max': _safe_float(metric_summary.get('max')),
            'avg': _safe_float(metric_summary.get('avg')),
            'current': _safe_float(current_value),
            'available': bool(metric_summary.get('available')) or metric in latest_metrics,
        }

    stats['ups_realpower']['total_energy'] = round(
        _calculate_total_energy_wh(history.get('ups_realpower', [])),
        4,
    )
    return stats


def _build_target_power_history(target_id, period='day', from_time=None, to_time=None, selected_day=None):
    """Build power history payload compatible with existing frontend expectations."""
    tz = current_app.CACHE_TIMEZONE
    history = get_metric_history(
        target_id=target_id,
        metric_names=TARGET_POWER_HISTORY_METRICS,
        tz=tz,
        period=period,
        from_time=from_time,
        to_time=to_time,
        selected_day=selected_day,
    )

    realpower_series = history.get('ups_realpower', [])
    upspower_series = history.get('ups_power', [])
    if not upspower_series and realpower_series:
        upspower_series = [{'timestamp': item['timestamp'], 'value': item['value']} for item in realpower_series]
    if not realpower_series and upspower_series:
        realpower_series = [{'timestamp': item['timestamp'], 'value': item['value']} for item in upspower_series]

    return {
        'ups_power': upspower_series,
        'ups_realpower': realpower_series,
        'input_voltage': history.get('input_voltage', []),
    }

def register_api_routes(app):
    """
    Register all API routes related to power data.
    
    Args:
        app: The Flask application instance.
        
    Returns:
        app: Modified Flask application with power routes registered.
    """
    @app.route('/power')
    @require_permission('power')
    def power_page():
        """Render the power page with React SPA."""
        return serve_react_index()

    @app.route('/api/power/metrics')
    def api_power_metrics():
        """
        API endpoint to retrieve available power metrics.
        
        Returns:
            JSON response with a dictionary of available power metrics.
        """
        target_id = resolve_target_id()
        metrics = _build_target_power_metrics(target_id) if target_id else get_available_power_metrics()
        return jsonify({'success': True, 'data': metrics})

    @app.route('/api/power/stats')
    def api_power_stats():
        """
        API endpoint to retrieve power statistics.
        
        Query parameters:
          - period: The time period type ('day', 'range', etc.)
          - from_time, to_time: Time range (if applicable)
          - selected_date: Specific date (if applicable)
          
        Returns:
            JSON response with a dictionary of power statistics.
        """
        period = request.args.get('period', 'day')
        from_time = request.args.get('from_time')
        to_time = request.args.get('to_time')
        target_id = resolve_target_id()
        
        # Log the request for debugging
        logger.debug(f"Power stats API request: period={period}, from_time={from_time}, to_time={to_time}")
        
        if target_id:
            selected_date = request.args.get('selected_date')
            stats = _build_target_power_stats(
                target_id=target_id,
                period=period,
                from_time=from_time,
                to_time=to_time,
                selected_date=selected_date,
            )
        else:
            # For 'today' period, explicitly call get_power_stats with today's date
            if period == 'realtime':
                tz = current_app.CACHE_TIMEZONE
                from_time, to_time = _legacy_realtime_window(tz)
                stats = get_power_stats(period='day', from_time=from_time, to_time=to_time)
            elif period == 'today':
                tz = current_app.CACHE_TIMEZONE
                today = datetime.now(tz)
                logger.debug(f"Using explicit TODAY period for power stats, date: {today.date()}")
                stats = get_power_stats(period='today')
            elif period == 'day':
                selected_date = request.args.get('selected_date')
                tz = current_app.CACHE_TIMEZONE
                if selected_date:
                    try:
                        selected_date_dt = datetime.strptime(selected_date, '%Y-%m-%d')
                        if selected_date_dt.tzinfo is None:
                            selected_date_dt = tz.localize(selected_date_dt)
                    except ValueError:
                        logger.error(f"Invalid selected_date format: {selected_date}")
                        selected_date_dt = datetime.now(tz)
                else:
                    selected_date_dt = datetime.now(tz)
                stats = get_power_stats(period, from_time, to_time, selected_date_dt)
            else:
                stats = get_power_stats(period, from_time, to_time)
        return jsonify({'success': True, 'data': stats})

    @app.route('/api/power/history')
    def api_power_history():
        """API for historical data"""
        period = request.args.get('period', 'day')
        from_time = request.args.get('from_time')
        to_time = request.args.get('to_time')
        selected_day = request.args.get('selected_day')
        target_id = resolve_target_id()
        
        # Log the incoming request for debugging
        logger.debug(f"Power history API request: period={period}, from_time={from_time}, to_time={to_time}, selected_day={selected_day}")
        
        if target_id:
            history = _build_target_power_history(
                target_id=target_id,
                period=period,
                from_time=from_time,
                to_time=to_time,
                selected_day=selected_day,
            )
        else:
            # For 'today' period, pass it directly to get_power_history
            if period == 'realtime':
                tz = current_app.CACHE_TIMEZONE
                from_time, to_time = _legacy_realtime_window(tz)
                history = get_power_history(period='day', from_date=from_time, to_date=to_time)
                logger.debug(f"Using realtime fallback window for power history: {from_time}-{to_time}")
            elif period == 'today':
                history = get_power_history(period='today')
                logger.debug("Using explicit TODAY period for power history")
            else:
                history = get_power_history(period, from_time, to_time, selected_day)
            
        return jsonify({'success': True, 'data': history})

    @app.route('/api/power/outlet-groups')
    def api_power_outlet_groups():
        """Return discovered outlet-group real-power metrics and history."""
        target_id = resolve_target_id()
        if not target_id:
            return jsonify({'success': True, 'data': {'groups': [], 'has_data': False}})

        payload = build_outlet_group_payload(
            target_id=int(target_id),
            period=request.args.get('period', 'day'),
            from_time=request.args.get('from_time'),
            to_time=request.args.get('to_time'),
            selected_date=request.args.get('selected_date'),
            selected_day=request.args.get('selected_day'),
        )
        return jsonify({'success': True, 'data': payload})

    @app.route('/api/power/has_hour_data')
    def api_power_has_hour_data():
        """
        API endpoint to check if there is at least 60 minutes of power data.
        
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
            logger.debug(f"Checking for power data between {one_hour_ago_str} and {now_str} (UTC)")
            
            # Query to find records in the last hour with valid power data
            # Looking for ups_realpower (direct measure) or ups_load (indirect measure)
            data = UPSDynamicData.query\
                .filter(
                    UPSDynamicData.timestamp_utc >= one_hour_ago_utc,
                    UPSDynamicData.timestamp_utc <= now_utc,
                    (UPSDynamicData.ups_realpower.isnot(None) | 
                     UPSDynamicData.ups_load.isnot(None))
                ).order_by(UPSDynamicData.timestamp_utc.asc()).all()
            
            # Get the count of data points
            data_count = len(data)
            
            # Log the data count for debugging
            logger.debug(f"Found {data_count} power data points in the query")
            
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

    return app 
