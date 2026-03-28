"""Voltage API Module.

Defines API endpoints and response handlers for this feature domain.
"""

from flask import jsonify, request, current_app
from datetime import datetime, timedelta
from core.logger import voltage_logger as logger
from core.db.ups import get_ups_data, get_ups_model
from core.multi_nut.domain_proxy import (
    get_latest_metrics,
    get_metric_history,
    get_metric_stats,
    has_hour_data as target_has_hour_data,
    resolve_target_id,
)
from .voltage import get_voltage_stats, get_voltage_history

logger.info("🔌 Initializing voltage API routes")


TARGET_VOLTAGE_METRICS = (
    'input_voltage',
    'output_voltage',
    'input_voltage_nominal',
    'output_voltage_nominal',
    'input_transfer_low',
    'input_transfer_high',
    'input_current',
    'output_current',
    'input_frequency',
    'output_frequency',
    'ups_load',
)


TARGET_VOLTAGE_STATS_METRICS = (
    'input_voltage',
    'output_voltage',
    'input_current',
    'output_current',
    'input_frequency',
    'output_frequency',
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


def _build_target_voltage_metrics(target_id):
    """Build voltage metrics map from active target snapshot."""
    _, _, snapshot_metrics = get_latest_metrics(target_id)
    metrics = {}

    for metric in TARGET_VOLTAGE_METRICS:
        value = snapshot_metrics.get(metric)
        if value is None:
            continue
        metrics[metric] = _safe_float(value)

    if snapshot_metrics.get('input_sensitivity') is not None:
        metrics['input_sensitivity'] = str(snapshot_metrics.get('input_sensitivity'))

    ups_status = snapshot_metrics.get('ups_status')
    if ups_status is not None:
        metrics['ups_status'] = str(ups_status).split()[0]

    return metrics


def _build_target_voltage_stats(target_id, period='day', from_time=None, to_time=None):
    """Build voltage stats payload from active target history."""
    history = get_metric_history(
        target_id=target_id,
        metric_names=TARGET_VOLTAGE_STATS_METRICS,
        tz=current_app.CACHE_TIMEZONE,
        period=period,
        from_time=from_time,
        to_time=to_time,
    )
    summary = get_metric_stats(history)
    stats = {}
    for metric in TARGET_VOLTAGE_STATS_METRICS:
        metric_summary = summary.get(metric) or {
            'min': 0.0,
            'max': 0.0,
            'avg': 0.0,
            'current': 0.0,
            'available': False,
        }
        stats[metric] = {
            'min': _safe_float(metric_summary.get('min')),
            'max': _safe_float(metric_summary.get('max')),
            'avg': _safe_float(metric_summary.get('avg')),
            'current': _safe_float(metric_summary.get('current')),
            'available': bool(metric_summary.get('available')),
        }
    return stats


def _build_target_voltage_history(target_id, period='day', from_time=None, to_time=None, selected_day=None):
    """Build voltage history payload from active target history."""
    history = get_metric_history(
        target_id=target_id,
        metric_names=TARGET_VOLTAGE_METRICS,
        tz=current_app.CACHE_TIMEZONE,
        period=period,
        from_time=from_time,
        to_time=to_time,
        selected_day=selected_day,
    )

    payload = {}
    for metric in TARGET_VOLTAGE_METRICS:
        payload[metric] = history.get(metric, [])
    return payload

def register_api_routes(app):
    """Register all API routes related to voltage"""
    
    @app.route('/api/voltage/metrics')
    def get_voltage_metrics():
        try:
            target_id = resolve_target_id()
            if target_id:
                metrics = _build_target_voltage_metrics(target_id)
            else:
                metrics = {}
                ups_data = get_ups_data()
                
                # Complete list of metrics to monitor
                voltage_metrics = [
                    'input_voltage', 'output_voltage',
                    'input_voltage_nominal', 'output_voltage_nominal',
                    'input_transfer_low', 'input_transfer_high',
                    'input_current', 'output_current',
                    'input_frequency', 'output_frequency',
                    'input_sensitivity', 'ups_status', 'ups_load',
                    'input_frequency_nominal', 'output_frequency_nominal'
                ]
                
                # Map all available metrics
                for metric in voltage_metrics:
                    if hasattr(ups_data, metric):
                        try:
                            value = getattr(ups_data, metric)
                            if value is not None:
                                if metric in ['ups_status', 'input_sensitivity']:
                                    metrics[metric] = str(value)
                                else:
                                    metrics[metric] = float(value)
                        except (ValueError, TypeError):
                            continue

            return jsonify({'success': True, 'data': metrics})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/api/voltage/stats')
    def api_voltage_stats():
        """API for voltage statistics"""
        period = request.args.get('period', 'day')
        from_time = request.args.get('from_time')
        to_time = request.args.get('to_time')
        target_id = resolve_target_id()
        if target_id:
            stats = _build_target_voltage_stats(target_id, period, from_time, to_time)
        else:
            if period == 'realtime':
                from_time, to_time = _legacy_realtime_window(current_app.CACHE_TIMEZONE)
                stats = get_voltage_stats(period='day', from_time=from_time, to_time=to_time)
            else:
                stats = get_voltage_stats(period, from_time, to_time)
        return jsonify({'success': True, 'data': stats})
    
    @app.route('/api/voltage/history')
    def api_voltage_history():
        """API for the data history"""
        period = request.args.get('period', 'day')
        from_time = request.args.get('from_time')
        to_time = request.args.get('to_time')
        selected_day = request.args.get('selected_day')
        target_id = resolve_target_id()

        if target_id:
            history = _build_target_voltage_history(target_id, period, from_time, to_time, selected_day)
        else:
            if period == 'realtime':
                from_time, to_time = _legacy_realtime_window(current_app.CACHE_TIMEZONE)
                history = get_voltage_history(period='today', from_time=from_time, to_time=to_time)
            else:
                history = get_voltage_history(period, from_time, to_time, selected_day)
        return jsonify({'success': True, 'data': history})

    @app.route('/api/voltage/has_hour_data')
    def api_voltage_has_hour_data():
        """
        API endpoint to check if there is at least 60 minutes of voltage data.
        
        Returns:
            JSON response with a boolean indicating if enough data exists.
        """
        try:
            target_id = resolve_target_id()
            if target_id:
                has_data = target_has_hour_data(target_id, metric_name='input_voltage')
                if not has_data:
                    has_data = target_has_hour_data(target_id, metric_name='input_voltage_nominal')
                return jsonify({'has_data': bool(has_data)})

            UPSDynamicData = get_ups_model()
            # Use CACHE_TIMEZONE from app
            tz = current_app.CACHE_TIMEZONE
            logger.debug(f"Using timezone: {tz.zone}")
            
            # Get current time in UTC directly (using naive datetime for SQLite compatibility)
            now_utc = datetime.utcnow()
            one_hour_ago_utc = now_utc - timedelta(hours=1)
            
            # Format for logging
            now_str = now_utc.strftime('%Y-%m-%d %H:%M:%S')
            one_hour_ago_str = one_hour_ago_utc.strftime('%Y-%m-%d %H:%M:%S')
            
            # Log the time values for debugging
            logger.debug(f"Checking for voltage data between {one_hour_ago_str} and {now_str} (UTC)")
            
            # First try with input_voltage
            data = UPSDynamicData.query\
                .filter(
                    UPSDynamicData.timestamp_utc >= one_hour_ago_utc,
                    UPSDynamicData.timestamp_utc <= now_utc,
                    UPSDynamicData.input_voltage.isnot(None)
                ).order_by(UPSDynamicData.timestamp_utc.asc()).all()
            
            # If no input_voltage data found, try with input_voltage_nominal
            if not data:
                logger.debug("No input_voltage data found, trying input_voltage_nominal instead")
                data = UPSDynamicData.query\
                    .filter(
                        UPSDynamicData.timestamp_utc >= one_hour_ago_utc,
                        UPSDynamicData.timestamp_utc <= now_utc,
                        UPSDynamicData.input_voltage_nominal.isnot(None)
                    ).order_by(UPSDynamicData.timestamp_utc.asc()).all()
            
            # Get the count of data points
            data_count = len(data)
            logger.debug(f"Found {data_count} voltage data points in the query")
            
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
