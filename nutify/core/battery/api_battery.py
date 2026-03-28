"""Battery API Module.

Defines API endpoints and response handlers for this feature domain.
"""

from flask import jsonify, request, current_app
from datetime import datetime, timedelta
from core.logger import battery_logger as logger
from core.db.ups import get_ups_model
from core.multi_nut.domain_proxy import (
    get_latest_metrics,
    get_metric_history,
    get_metric_stats,
    has_hour_data as target_has_hour_data,
    resolve_target_id,
)
from .battery import (
    get_available_battery_metrics,
    get_battery_stats,
    get_battery_history
)

# Import functions from battery module
logger.info("🔋 Initializing battery API routes")


TARGET_BATTERY_STATS_METRICS = (
    'battery_charge',
    'battery_charge_low',
    'battery_charge_warning',
    'battery_voltage',
    'battery_voltage_nominal',
    'battery_current',
    'battery_temperature',
    'battery_runtime',
    'battery_runtime_low',
    'battery_alarm_threshold',
)


TARGET_BATTERY_HISTORY_METRICS = (
    'battery_charge',
    'battery_runtime',
    'battery_voltage',
    'battery_temperature',
)


TARGET_BATTERY_TEXT_METRICS = (
    'battery_type',
    'battery_date',
    'battery_mfr_date',
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


def _build_target_battery_metrics(target_id):
    """Build available battery metrics map from active target snapshot."""
    _, _, metrics = get_latest_metrics(target_id)
    result = {}

    for metric in TARGET_BATTERY_STATS_METRICS:
        value = metrics.get(metric)
        if value is None:
            continue
        result[metric] = _safe_float(value)

    for metric in TARGET_BATTERY_TEXT_METRICS:
        value = metrics.get(metric)
        if value is None:
            continue
        result[metric] = str(value)

    return result


def _build_target_battery_stats(target_id, period='day', from_time=None, to_time=None, selected_date=None):
    """Build battery stats payload compatible with existing frontend expectations."""
    tz = current_app.CACHE_TIMEZONE
    history = get_metric_history(
        target_id=target_id,
        metric_names=TARGET_BATTERY_STATS_METRICS,
        tz=tz,
        period=period,
        from_time=from_time,
        to_time=to_time,
        selected_date=selected_date,
    )
    summary = get_metric_stats(history)
    latest_metrics = _build_target_battery_metrics(target_id)

    stats = {}
    for metric in TARGET_BATTERY_STATS_METRICS:
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

    stats['events'] = {
        'count': 0,
        'total_duration': 0.0,
        'longest_duration': 0.0,
        'available': False,
    }
    return stats


def _build_target_battery_history(target_id, period='day', from_time=None, to_time=None, selected_date=None):
    """Build battery history payload compatible with existing frontend expectations."""
    tz = current_app.CACHE_TIMEZONE
    history = get_metric_history(
        target_id=target_id,
        metric_names=TARGET_BATTERY_HISTORY_METRICS,
        tz=tz,
        period=period,
        from_time=from_time,
        to_time=to_time,
        selected_date=selected_date,
    )

    payload = {
        'battery_charge': history.get('battery_charge', []),
        'battery_runtime': history.get('battery_runtime', []),
        'battery_voltage': history.get('battery_voltage', []),
        'battery_temperature': history.get('battery_temperature', []),
        'events': [],
    }
    return payload

def register_api_routes(app):
    """Register all API routes related to the battery"""
    
    @app.route('/api/battery/metrics')
    def api_battery_metrics():
        """API for available metrics"""
        target_id = resolve_target_id()
        metrics = _build_target_battery_metrics(target_id) if target_id else get_available_battery_metrics()
        return jsonify({'success': True, 'data': metrics})
    
    @app.route('/api/battery/stats')
    def api_battery_stats():
        """API for statistics"""
        period = request.args.get('period', 'day')
        from_time = request.args.get('from_time')
        to_time = request.args.get('to_time')
        target_id = resolve_target_id()

        if target_id:
            selected_date = request.args.get('selected_date')
            stats = _build_target_battery_stats(
                target_id=target_id,
                period=period,
                from_time=from_time,
                to_time=to_time,
                selected_date=selected_date,
            )
        else:
            if period == 'realtime':
                tz = current_app.CACHE_TIMEZONE
                from_time, to_time = _legacy_realtime_window(tz)
                stats = get_battery_stats(period='day', from_time=from_time, to_time=to_time)
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
                stats = get_battery_stats(period, from_time, to_time, selected_date_dt)
            else:
                stats = get_battery_stats(period, from_time, to_time)
        return jsonify({'success': True, 'data': stats})
    
    @app.route('/api/battery/has_hour_data')
    def api_battery_has_hour_data():
        """
        API endpoint to check if there is at least 60 minutes of battery data.
        
        Returns:
            JSON response with a boolean indicating if enough data exists.
        """
        try:
            target_id = resolve_target_id()
            if target_id:
                has_data = target_has_hour_data(target_id, metric_name='battery_charge')
                if not has_data:
                    has_data = target_has_hour_data(target_id, metric_name='battery_runtime')
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
            logger.debug(f"Checking for battery data between {one_hour_ago_str} and {now_str} (UTC)")
            
            # Query to find records in the last hour with valid battery data
            # Using battery_charge as the main metric as it's usually the most reliable
            data = UPSDynamicData.query\
                .filter(
                    UPSDynamicData.timestamp_utc >= one_hour_ago_utc,
                    UPSDynamicData.timestamp_utc <= now_utc,
                    UPSDynamicData.battery_charge.isnot(None)
                ).order_by(UPSDynamicData.timestamp_utc.asc()).all()
            
            # Get the count of data points
            data_count = len(data)
            logger.debug(f"Found {data_count} battery data points in the query")
            
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
    
    @app.route('/api/battery/history')
    def api_battery_history():
        """API for history data"""
        period = request.args.get('period', 'day')
        from_time = request.args.get('from_time')
        to_time = request.args.get('to_time')
        selected_date = request.args.get('selected_date')
        today_mode = request.args.get('today_mode') == 'true'
        target_id = resolve_target_id()
        
        logger.debug(f"📊 API Battery History request: period={period}, from={from_time}, to={to_time}, today_mode={today_mode}")
        
        if target_id:
            effective_period = 'today' if (period == 'today' or today_mode) else period
            history = _build_target_battery_history(
                target_id=target_id,
                period=effective_period,
                from_time=from_time,
                to_time=to_time,
                selected_date=selected_date,
            )
        else:
            # For 'today' period or today_mode=true, pass it directly to get_battery_history as 'today'
            if period == 'today' or today_mode:
                history = get_battery_history(period='today')
                logger.debug("Using explicit TODAY period for battery history")
            elif period == 'day' and selected_date:
                tz = current_app.CACHE_TIMEZONE
                try:
                    selected_date_dt = datetime.strptime(selected_date, '%Y-%m-%d')
                    if selected_date_dt.tzinfo is None:
                        selected_date_dt = tz.localize(selected_date_dt)
                except ValueError:
                    logger.error(f"Invalid selected_date format in history: {selected_date}")
                    selected_date_dt = None
                history = get_battery_history(period, from_time, to_time, selected_date_dt)
            else:
                history = get_battery_history(period, from_time, to_time)
        
        return jsonify({'success': True, 'data': history})
    
    return app 
