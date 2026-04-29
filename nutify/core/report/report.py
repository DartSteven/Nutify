"""Report Module.

Implements core runtime logic and helpers used by this feature.
"""

from datetime import datetime, timedelta
import pytz
from core.logger import report_logger as logger, get_logger
from core.db.ups import (
    db, data_lock, get_ups_data, get_historical_data, get_ups_model,
    UPSEvent, ReportSchedule, VariableConfig
)
from core.energy.energy import (
    get_energy_data, 
    get_cost_trend_for_range, 
    calculate_energy_stats, 
    get_period_energy_data,
    calculate_cost_distribution,
    get_energy_rate,
    format_cost_series
)
from core.battery.battery import get_battery_stats, get_battery_history
from core.power.power import get_power_stats, get_power_history
from core.voltage.voltage import get_voltage_stats, get_voltage_history
from core.mail import (
    send_email, 
    MailConfig,
    validate_emails,
    get_current_email_settings,
    get_mail_config_model
)
from core.multi_nut.target_scope import resolve_settings_target_id
from core.multi_nut.domain_proxy import (
    build_energy_cost_series,
    build_energy_payload,
    get_metric_history,
    get_metric_stats,
)
from flask import render_template, jsonify, request, current_app, has_app_context
import json
import os
import schedule
import time
import threading

import base64
from io import BytesIO
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from typing import List, Optional
from email_validator import validate_email, EmailNotValidError
import logging

logger.info("📄 Initializing report")
scheduler_logger = get_logger('scheduler')

class ReportManager:
    def __init__(self, app=None):
        logger.info("🚀 Initializing ReportManager with Schedule library")
        self.app = app
        self.tz = None  # Will be set in init_app from current_app.CACHE_TIMEZONE
        self.last_schedule_id = None
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize the report manager with Flask app"""
        try:
            self.app = app
            with app.app_context():
                # Always use current_app.CACHE_TIMEZONE as the only source of truth
                self.tz = current_app.CACHE_TIMEZONE
                logger.info(f"✅ ReportManager initialized with timezone: {self.tz.zone}")
            return self
        except Exception as e:
            logger.error(f"Error in init_app: {str(e)}", exc_info=True)
            return self

    def _ensure_timezone(self):
        """Guarantee timezone availability before report calculations."""
        if self.tz is not None:
            return self.tz

        try:
            if has_app_context():
                app_tz = getattr(current_app, 'CACHE_TIMEZONE', None)
                if app_tz is not None:
                    self.tz = app_tz
                    return self.tz
        except Exception:
            pass

        try:
            if self.app is not None:
                app_tz = getattr(self.app, 'CACHE_TIMEZONE', None)
                if app_tz is not None:
                    self.tz = app_tz
                    return self.tz
        except Exception:
            pass

        self.tz = pytz.UTC
        logger.warning("⚠️ ReportManager timezone was missing. Falling back to UTC.")
        return self.tz
    
    def _get_server_name(self):
        """Get the server name from database without fallback"""
        try:
            from core.settings import get_server_name

            server_name = get_server_name()
            logger.debug(f"Report manager using server name: {server_name}")
            return server_name
        except Exception as e:
            logger.error(f"Failed to get server name in report manager: {str(e)}")
            raise  # Re-raise the error rather than providing a fallback

    def _resolve_target_period_args(self, from_date, to_date):
        """Resolve period arguments compatible with Multi-NUT domain proxy."""
        self._ensure_timezone()
        local_from = from_date.astimezone(self.tz)
        local_to = to_date.astimezone(self.tz)
        is_single_day = local_from.date() == local_to.date()
        if is_single_day:
            return {
                'period': 'day',
                'from_time': None,
                'to_time': None,
                'selected_date': local_from.strftime('%Y-%m-%d'),
                'selected_day': None,
                'is_single_day': True,
            }
        return {
            'period': 'range',
            'from_time': local_from.strftime('%Y-%m-%d'),
            'to_time': local_to.strftime('%Y-%m-%d'),
            'selected_date': None,
            'selected_day': None,
            'is_single_day': False,
        }

    def _load_target_metric_payload(self, target_id, metric_names, from_date, to_date, max_points=1600):
        """Load metric history and stats for a specific target."""
        period_args = self._resolve_target_period_args(from_date, to_date)
        history = get_metric_history(
            target_id=target_id,
            metric_names=metric_names,
            tz=self.tz,
            period=period_args['period'],
            from_time=period_args['from_time'],
            to_time=period_args['to_time'],
            selected_date=period_args['selected_date'],
            selected_day=period_args['selected_day'],
            max_points=max_points,
        )
        stats = get_metric_stats(history)
        return history, stats, period_args

    @staticmethod
    def _stat_or_zero(stats, metric_name):
        metric_stats = stats.get(metric_name) or {}
        return {
            'min': float(metric_stats.get('min') or 0.0),
            'max': float(metric_stats.get('max') or 0.0),
            'avg': float(metric_stats.get('avg') or 0.0),
            'current': float(metric_stats.get('current') or 0.0),
            'available': bool(metric_stats.get('available')),
        }

    def _to_local_chart_datetime(self, raw_timestamp):
        """Convert chart timestamp payload to timezone-aware datetime for Plotly date axes."""
        self._ensure_timezone()
        if raw_timestamp is None:
            return None

        try:
            if isinstance(raw_timestamp, datetime):
                dt_value = raw_timestamp
                if dt_value.tzinfo is None:
                    dt_value = pytz.UTC.localize(dt_value)
                return dt_value.astimezone(self.tz)

            if isinstance(raw_timestamp, (int, float)):
                ts = float(raw_timestamp)
                # Heuristics for epoch unit normalization (ns/us/ms/s)
                if ts > 1e17:
                    ts /= 1_000_000_000.0
                elif ts > 1e14:
                    ts /= 1_000_000.0
                elif ts > 1e11:
                    ts /= 1000.0
                dt_value = datetime.fromtimestamp(ts, tz=pytz.UTC)
                return dt_value.astimezone(self.tz)

            text_value = str(raw_timestamp).strip()
            if not text_value:
                return None

            if text_value.isdigit():
                return self._to_local_chart_datetime(int(text_value))

            dt_value = datetime.fromisoformat(text_value.replace('Z', '+00:00'))
            if dt_value.tzinfo is None:
                dt_value = self.tz.localize(dt_value)
            return dt_value.astimezone(self.tz)
        except Exception:
            logger.debug(f"Skipping unparseable chart timestamp: {raw_timestamp}")
            return None

    def _build_xy_series(self, points, x_key='timestamp', y_key='value', value_transform=None):
        """Normalize generic point arrays into sorted (datetime, float) tuples."""
        normalized = []
        for point in points or []:
            if not isinstance(point, dict):
                continue
            x_raw = point.get(x_key)
            if x_raw is None and x_key != 'x':
                x_raw = point.get('x')
            dt_value = self._to_local_chart_datetime(x_raw)
            if dt_value is None:
                continue
            y_raw = point.get(y_key)
            if y_raw is None and y_key != 'y':
                y_raw = point.get('y')
            try:
                y_value = float(y_raw)
            except (TypeError, ValueError):
                continue
            if value_transform is not None:
                y_value = value_transform(y_value)
            normalized.append((dt_value, y_value))
        normalized.sort(key=lambda item: item[0])
        return normalized

    def _series_to_plotly_xy(self, series):
        """Convert any series tuples into Plotly-friendly ISO date/value arrays."""
        x_values = []
        y_values = []
        for raw_x, metric_value in series or []:
            dt_value = raw_x if isinstance(raw_x, datetime) else self._to_local_chart_datetime(raw_x)
            if dt_value is None:
                continue
            x_values.append(dt_value.isoformat())
            y_values.append(metric_value)
        return x_values, y_values

    def _get_energy_report_data(self, from_date, to_date, target_id=None):
        """Collect energy report data using existing APIs"""
        try:
            if target_id is not None:
                history_period = self._resolve_target_period_args(from_date, to_date)
                energy_payload = build_energy_payload(
                    target_id=target_id,
                    tz=self.tz,
                    period=history_period['period'],
                    from_time=history_period['from_time'],
                    to_time=history_period['to_time'],
                    selected_date=history_period['selected_date'],
                    selected_day=history_period['selected_day'],
                )
                cost_trend = build_energy_cost_series(
                    target_id=target_id,
                    tz=self.tz,
                    period=history_period['period'],
                    from_time=history_period['from_time'],
                    to_time=history_period['to_time'],
                    selected_date=history_period['selected_date'],
                    selected_day=history_period['selected_day'],
                )
                energy_stats = {
                    'totalEnergy': round(float(energy_payload.get('totalEnergy', 0.0)) / 1000.0, 2),
                    'totalCost': round(float(energy_payload.get('totalCost', 0.0)), 4),
                    'avgLoad': round(float(energy_payload.get('avgLoad', 0.0)), 2),
                    'co2': round(float(energy_payload.get('co2', 0.0)), 4),
                }
                chart_data = {
                    'data': cost_trend,
                    'from_date': from_date,
                    'to_date': to_date,
                    'is_single_day': history_period['is_single_day'],
                }
                chart_url = self._generate_chart_image(
                    chart_data,
                    'energy',
                    is_single_day=history_period['is_single_day'],
                )
                return {
                    'include_energy': True,
                    'energy_stats': energy_stats,
                    'energy_chart_url': chart_url,
                    'period_type': 'hrs' if history_period['is_single_day'] else 'days',
                    'currency': energy_payload.get('currency_symbol') or '€',
                }

            logger.debug(f"Retrieving energy data from {from_date} to {to_date}")
            # Calculate the duration in days to determine the type of visualization
            duration_days = (to_date.date() - from_date.date()).days
            
            # Determine the appropriate period_type based on the duration
            if duration_days > 0:
                # If more than one day, use 'days'
                period_type = 'days'
            else:
                # If the same day, use 'hrs'
                period_type = 'hrs'
                
            logger.debug(f"Energy data retrieval period: {duration_days} days, using period_type={period_type}")
                
            # Use the API exactly as defined in energy.py
            energy_data = get_energy_data(
                start_date=from_date,  # The API uses start_date, not period or from_time
                end_date=to_date,      # The API uses end_date, not to_time
            )
            
            # Log energy stats for debugging
            logger.debug(f"Energy stats retrieved: {energy_data}")
            
            # Convert totalEnergy from Wh to kWh for proper display in reports
            if 'totalEnergy' in energy_data:
                energy_data['totalEnergy'] = round(energy_data['totalEnergy'] / 1000, 2)  # Convert from Wh to kWh with 2 decimals
            
            # Take the cost trend using the correct API - capture possible exceptions and provide fallback data
            try:
                # Get cost trend from the API - use different methods based on period type
                is_single_day = from_date.date() == to_date.date()
                
                if is_single_day:
                    # For a single day, build hourly bars from the same energy formatters
                    # used by the Energy page (hrs -> calculated -> realtime fallback).
                    UPSDynamicData = get_ups_model()

                    local_day = from_date.astimezone(self.tz).date()
                    day_start_local = self.tz.localize(
                        datetime.combine(local_day, datetime.min.time())
                    )
                    day_end_local = self.tz.localize(
                        datetime.combine(local_day, datetime.max.time())
                    )
                    start_time = day_start_local.astimezone(pytz.UTC)
                    end_time = day_end_local.astimezone(pytz.UTC)

                    data = UPSDynamicData.query\
                        .filter(
                            UPSDynamicData.timestamp_utc >= start_time,
                            UPSDynamicData.timestamp_utc <= end_time
                        ).order_by(UPSDynamicData.timestamp_utc.asc()).all()

                    logger.debug(f"Retrieved {len(data)} raw data points for report day {local_day.isoformat()}")

                    base_series = format_cost_series(data, 'hrs')
                    if not base_series:
                        base_series = format_cost_series(data, 'calculated')
                    if not base_series:
                        base_series = format_cost_series(data, 'realtime')

                    hourly_totals = {hour: 0.0 for hour in range(24)}
                    for point in base_series or []:
                        timestamp_local = self._to_local_chart_datetime(point.get('x'))
                        if timestamp_local is None or timestamp_local.date() != local_day:
                            continue
                        try:
                            value = float(point.get('y') or 0.0)
                        except (TypeError, ValueError):
                            value = 0.0
                        hourly_totals[timestamp_local.hour] += max(0.0, value)

                    cost_trend = []
                    for hour in range(24):
                        hour_dt = day_start_local.replace(hour=hour, minute=0, second=0, microsecond=0)
                        cost_trend.append({
                            'x': int(hour_dt.timestamp() * 1000),
                            'y': round(hourly_totals[hour], 6),
                        })
                    logger.debug(f"Created {len(cost_trend)} hourly report points for single day")
                else:
                    local_start_date = from_date.astimezone(self.tz).date()
                    local_end_date = to_date.astimezone(self.tz).date()
                    range_start_local = self.tz.localize(
                        datetime.combine(local_start_date, datetime.min.time())
                    )
                    range_end_local = self.tz.localize(
                        datetime.combine(local_end_date, datetime.max.time())
                    )
                    cost_trend = get_cost_trend_for_range(
                        range_start_local.astimezone(pytz.UTC),
                        range_end_local.astimezone(pytz.UTC),
                    )
                
                # Log for debug: verify the format of cost_trend data
                if cost_trend:
                    if isinstance(cost_trend, list):
                        sample = cost_trend[0] if len(cost_trend) > 0 else "empty list"
                        logger.debug(f"Cost trend data format: list with {len(cost_trend)} items, first item: {sample}")
                    else:
                        logger.debug(f"Cost trend data format: {type(cost_trend)}")
                else:
                    logger.debug("Cost trend data is empty or None")
                    cost_trend = []
                    
            except Exception as e:
                logger.error(f"Error getting cost trend data: {str(e)}")
                cost_trend = []
            
            # Determine if it's a single day report
            is_single_day = from_date.date() == to_date.date()
            # Force period_type based on duration
            period_type = 'hrs' if is_single_day else 'days'
            logger.info(f"Energy report period_type determined as: {period_type}")
            
            # If the stats are missing or have zero values but we have cost trend data,
            # try to derive energy stats from the cost trend
            if energy_data.get('totalEnergy', 0) == 0 and cost_trend and len(cost_trend) > 0:
                total_energy = 0
                total_cost = 0
                
                for item in cost_trend:
                    if 'y' in item and item['y']:
                        cost = float(item['y'])
                        total_cost += cost
                        # Calculate energy based on cost
                        rate = get_energy_rate()
                        energy_kwh = 0
                        if rate > 0:
                            energy_kwh = cost / rate
                        total_energy += energy_kwh
                
                # Update energy data with derived values
                energy_data['totalEnergy'] = round(total_energy, 2)
                energy_data['totalCost'] = round(total_cost, 2)
                energy_data['avgLoad'] = energy_data.get('avgLoad', 10)  # Use a default if missing
                energy_data['co2'] = round(total_energy * 0.45, 2)  # Rough estimate based on 0.45kg CO2/kWh
                
                logger.debug(f"Derived energy stats from cost trend: {energy_data}")
            
            # Generate chart with proper period_type and actual date range
            # Pass the date range to the method to ensure the chart has the correct interval
            chart_data = {
                'data': cost_trend,
                'from_date': from_date,
                'to_date': to_date,
                'is_single_day': is_single_day
            }
            
            chart_url = self._generate_chart_image(chart_data, 'energy', is_single_day)
            
            return {
                'include_energy': True,
                'energy_stats': energy_data,
                'energy_chart_url': chart_url,
                'period_type': period_type,
                'currency': '€',
            }
        except Exception as e:
            logger.error(f"Error getting energy report data: {str(e)}")
            return {'include_energy': False}

    def _get_battery_report_data(self, from_date, to_date, target_id=None):
        """Collect battery report data"""
        try:
            if target_id is not None:
                metric_names = [
                    'battery_charge',
                    'battery_runtime',
                    'battery_voltage',
                    'battery_temperature',
                    'battery_voltage_nominal',
                    'input_voltage',
                    'output_voltage',
                ]
                history, stats, _ = self._load_target_metric_payload(
                    target_id=target_id,
                    metric_names=metric_names,
                    from_date=from_date,
                    to_date=to_date,
                    max_points=1600,
                )

                battery_charge = self._stat_or_zero(stats, 'battery_charge')
                battery_runtime = self._stat_or_zero(stats, 'battery_runtime')
                battery_voltage = self._stat_or_zero(stats, 'battery_voltage')
                battery_temperature = self._stat_or_zero(stats, 'battery_temperature')
                battery_voltage_nominal = self._stat_or_zero(stats, 'battery_voltage_nominal')
                input_voltage = self._stat_or_zero(stats, 'input_voltage')
                output_voltage = self._stat_or_zero(stats, 'output_voltage')

                runtime_avg_seconds = battery_runtime['avg']
                runtime_current_seconds = battery_runtime['current']

                # Convert runtime to minutes for template display, keep source history in seconds for chart.
                for key in ('min', 'max', 'avg', 'current'):
                    battery_runtime[key] = round(float(battery_runtime[key]) / 60.0, 1)

                nominal_voltage = battery_voltage_nominal['avg'] if battery_voltage_nominal['avg'] > 0 else 0.0
                voltage_ratio = (battery_voltage['avg'] / nominal_voltage) if nominal_voltage > 0 else 1.0
                health_score = (
                    min(100.0, battery_charge['avg']) * 0.55
                    + min(100.0, max(0.0, runtime_avg_seconds / 36.0)) * 0.30
                    + min(100.0, max(0.0, voltage_ratio * 100.0)) * 0.15
                )
                health_score = round(health_score, 1)
                if health_score >= 80:
                    health = 'Good'
                elif health_score >= 50:
                    health = 'Fair'
                else:
                    health = 'Poor'

                has_battery_voltage = battery_voltage['avg'] > 0
                has_input_voltage = input_voltage['avg'] > 0
                has_output_voltage = output_voltage['avg'] > 0
                show_voltage_section = has_battery_voltage or has_input_voltage or has_output_voltage

                chart_timeseries = {
                    'battery_charge': history.get('battery_charge') or [],
                    'battery_runtime': history.get('battery_runtime') or [],
                    'battery_voltage': history.get('battery_voltage') or [],
                    'battery_temperature': history.get('battery_temperature') or [],
                }
                chart_url = self._generate_chart_image({'timeseries': chart_timeseries}, 'battery')

                return {
                    'include_battery': True,
                    'battery_stats': {
                        'battery_charge': battery_charge,
                        'battery_runtime': battery_runtime,
                        'battery_voltage': battery_voltage,
                        'battery_temperature': battery_temperature,
                        'health_score': health_score,
                        'health': health,
                        'runtime_seconds_avg': runtime_avg_seconds,
                        'runtime_seconds_current': runtime_current_seconds,
                    },
                    'battery_chart_url': chart_url,
                    'has_battery_voltage': has_battery_voltage,
                    'has_input_voltage': has_input_voltage,
                    'has_output_voltage': has_output_voltage,
                    'show_voltage_section': show_voltage_section,
                    'input_voltage_value': input_voltage['avg'],
                    'output_voltage_value': output_voltage['avg'],
                }

            # Determine if the period is a single day
            is_same_day = from_date.date() == to_date.date()
            
            if is_same_day:
                # If the same day, use the period='day' format with selected_date
                battery_stats = get_battery_stats(
                    period='day',
                    selected_date=from_date
                )
                
                history_data = get_battery_history(
                    period='day',
                    selected_date=from_date
                )
                
                # Also get voltage data for the same period
                voltage_stats = get_voltage_stats(
                    period='day',
                    from_time="00:00",
                    to_time="23:59"
                )
            else:
                # For multi-day periods, use the period='range' format
                battery_stats = get_battery_stats(
                    period='range',
                    from_time=from_date.strftime('%Y-%m-%d'),
                    to_time=to_date.strftime('%Y-%m-%d')
                )
                
                history_data = get_battery_history(
                    period='range',
                    from_date=from_date.strftime('%Y-%m-%d'),
                    to_date=to_date.strftime('%Y-%m-%d')
                )
                
                # Also get voltage data for the same period
                voltage_stats = get_voltage_stats(
                    period='range',
                    from_time=from_date.strftime('%Y-%m-%d'),
                    to_time=to_date.strftime('%Y-%m-%d')
                )
            
            # Create default metrics dictionary to ensure all expected metrics exist
            default_metrics = {
                'battery_charge': {'min': 0, 'max': 0, 'avg': 0, 'current': 0},
                'battery_runtime': {'min': 0, 'max': 0, 'avg': 0, 'current': 0},
                'battery_voltage': {'min': 0, 'max': 0, 'avg': 0, 'current': 0},
                'battery_temperature': {'min': 0, 'max': 0, 'avg': 0, 'current': 0}
            }
            
            # Initialize battery_stats with default values if not present
            if not battery_stats:
                battery_stats = default_metrics
            else:
                # Ensure all expected metrics exist by updating with defaults
                for metric, default_values in default_metrics.items():
                    if metric not in battery_stats:
                        battery_stats[metric] = default_values
                    elif not isinstance(battery_stats[metric], dict):
                        # If metric exists but is not a dict, replace with default
                        battery_stats[metric] = default_values
                    else:
                        # If metric exists as dict but missing expected keys, add them
                        for key, value in default_values.items():
                            if key not in battery_stats[metric]:
                                battery_stats[metric][key] = value
            
            # Get current values using the UPS data
            try:
                from core.db.ups import get_ups_data
                current_ups_data = get_ups_data()
                
                # Get real charge value if available
                if hasattr(current_ups_data, 'battery_charge') and current_ups_data.battery_charge is not None:
                    battery_stats['battery_charge']['current'] = float(current_ups_data.battery_charge)
                    if battery_stats['battery_charge']['avg'] == 0:
                        battery_stats['battery_charge']['avg'] = float(current_ups_data.battery_charge)
                        battery_stats['battery_charge']['min'] = float(current_ups_data.battery_charge)
                        battery_stats['battery_charge']['max'] = float(current_ups_data.battery_charge)
                
                # Get real runtime value if available (preserve in seconds)
                if hasattr(current_ups_data, 'battery_runtime') and current_ups_data.battery_runtime is not None:
                    runtime_value = float(current_ups_data.battery_runtime)
                    # Store seconds directly, no conversion to minutes yet
                    battery_stats['battery_runtime']['current'] = runtime_value
                    if battery_stats['battery_runtime']['avg'] == 0:
                        battery_stats['battery_runtime']['avg'] = runtime_value
                        battery_stats['battery_runtime']['min'] = runtime_value
                        battery_stats['battery_runtime']['max'] = runtime_value
                
                # Get real battery voltage if available
                if hasattr(current_ups_data, 'battery_voltage') and current_ups_data.battery_voltage is not None:
                    battery_stats['battery_voltage']['current'] = float(current_ups_data.battery_voltage)
                    if battery_stats['battery_voltage']['avg'] == 0:
                        battery_stats['battery_voltage']['avg'] = float(current_ups_data.battery_voltage)
                        battery_stats['battery_voltage']['min'] = float(current_ups_data.battery_voltage)
                        battery_stats['battery_voltage']['max'] = float(current_ups_data.battery_voltage)
                
                # Get battery_voltage_nominal if available (for health calculation)
                if hasattr(current_ups_data, 'battery_voltage_nominal') and current_ups_data.battery_voltage_nominal is not None:
                    battery_stats['battery_voltage_nominal'] = {'avg': float(current_ups_data.battery_voltage_nominal)}
                    
            except Exception as e:
                logger.warning(f"Could not get current UPS data: {str(e)}")
            
            # Check if any voltage data is available from battery_stats
            has_battery_voltage = (
                'battery_voltage' in battery_stats and 
                battery_stats['battery_voltage'].get('avg', 0) > 0
            )
            
            # Check if any voltage data is available from voltage_stats
            has_input_voltage = False
            has_output_voltage = False
            input_voltage_value = 0
            output_voltage_value = 0
            
            # Check for input voltage
            if 'input_voltage' in voltage_stats and voltage_stats['input_voltage'].get('avg', 0) > 0:
                has_input_voltage = True
                input_voltage_value = voltage_stats['input_voltage']['avg']
                # If we don't have battery voltage, but we have input voltage, copy it to display in widget
                if not has_battery_voltage and battery_stats['battery_voltage']['avg'] == 0:
                    # Try using battery voltage, otherwise use input voltage
                    if hasattr(current_ups_data, 'battery_voltage') and current_ups_data.battery_voltage is not None:
                        battery_stats['battery_voltage']['avg'] = float(current_ups_data.battery_voltage)
                        battery_stats['battery_voltage']['current'] = float(current_ups_data.battery_voltage)
                    elif hasattr(current_ups_data, 'input_voltage') and current_ups_data.input_voltage is not None:
                        battery_stats['battery_voltage']['avg'] = float(current_ups_data.input_voltage)
                        battery_stats['battery_voltage']['current'] = float(current_ups_data.input_voltage)
                    else:
                        battery_stats['battery_voltage']['avg'] = input_voltage_value
                        battery_stats['battery_voltage']['current'] = input_voltage_value
                    # Set min and max to same value if they're still 0
                    if battery_stats['battery_voltage']['min'] == 0:
                        battery_stats['battery_voltage']['min'] = battery_stats['battery_voltage']['avg']
                    if battery_stats['battery_voltage']['max'] == 0:
                        battery_stats['battery_voltage']['max'] = battery_stats['battery_voltage']['avg']
                    has_battery_voltage = True
            
            # Check for output voltage
            if 'output_voltage' in voltage_stats and voltage_stats['output_voltage'].get('avg', 0) > 0:
                has_output_voltage = True
                output_voltage_value = voltage_stats['output_voltage']['avg']
            
            # Determine if we should show the voltage section
            show_voltage_section = has_battery_voltage or has_input_voltage or has_output_voltage
            
            # Add voltage data to the report
            voltage_data = {
                'has_battery_voltage': has_battery_voltage,
                'has_input_voltage': has_input_voltage,
                'has_output_voltage': has_output_voltage,
                'show_voltage_section': show_voltage_section,
                'input_voltage_value': input_voltage_value,
                'output_voltage_value': output_voltage_value
            }
            
            logger.debug(f"Processed battery stats: {battery_stats}")
            
            # Transform history_data into the format expected by _create_battery_chart
            # The chart expects a 'timeseries' structure while get_battery_history returns a different format
            transformed_history = {'timeseries': {}}
            
            # Check if history_data has the expected structure
            if history_data and isinstance(history_data, dict):
                # Process each metric in the history data
                for metric in ['battery_charge', 'battery_runtime', 'battery_voltage', 'battery_temperature']:
                    if metric in history_data and history_data[metric]:
                        # Copy the data directly to the timeseries section
                        transformed_history['timeseries'][metric] = history_data[metric]
                        logger.debug(f"Added {len(history_data[metric])} data points for {metric} to chart data")
                    else:
                        # No data for this metric, create an empty list
                        transformed_history['timeseries'][metric] = []
                
                # Also include events if available
                if 'events' in history_data:
                    transformed_history['events'] = history_data['events']
            else:
                logger.warning("No valid battery history data available - creating fallback data")
                # Create fallback/dummy data for visualization
                transformed_history['timeseries'] = {
                    'battery_charge': [],
                    'battery_runtime': [],
                    'battery_voltage': [],
                    'battery_temperature': []
                }
                
                # Create timestamps spanning the requested date range
                duration = (to_date - from_date).total_seconds()
                num_points = min(24, max(2, int(duration / 3600)))  # At least 2 points, at most 24
                
                # Create evenly spaced timestamps
                for i in range(num_points):
                    point_time = from_date + timedelta(seconds=(i * duration / (num_points - 1)))
                    
                    # Current charge from stats or fallback value
                    charge_value = battery_stats.get('battery_charge', {}).get('current', 100)
                    
                    # Add dummy point to each metric
                    transformed_history['timeseries']['battery_charge'].append({
                        'timestamp': point_time.isoformat(),
                        'value': charge_value
                    })
                    
                    # Runtime in seconds (no conversion)
                    runtime_value = battery_stats.get('battery_runtime', {}).get('current', 1800)  # Default 30 min = 1800 sec
                    transformed_history['timeseries']['battery_runtime'].append({
                        'timestamp': point_time.isoformat(),
                        'value': runtime_value
                    })
                    
                    # Voltage - use current voltage for better display
                    voltage_value = battery_stats.get('battery_voltage', {}).get('current', 24)
                    transformed_history['timeseries']['battery_voltage'].append({
                        'timestamp': point_time.isoformat(),
                        'value': voltage_value
                    })
                
                # If we have input voltage, use it for the chart
                if has_input_voltage and input_voltage_value > 0:
                    logger.debug(f"Using input voltage value as fallback: {input_voltage_value}V")
                    for point in transformed_history['timeseries']['battery_voltage']:
                        # If it's already a battery voltage value, leave it alone
                        # Otherwise, use input voltage (adapted to battery scale if needed)
                        if point['value'] == 24:  # Default value
                            # If UPS reports actual battery voltage as 24-30V range, use input_voltage directly
                            # Otherwise, scale it (typical case for a 12V or 48V battery)
                            if battery_stats['battery_voltage']['avg'] > 20:
                                point['value'] = input_voltage_value
                            else:
                                point['value'] = input_voltage_value / 10  # Scale to typical battery voltage
                
                transformed_history['events'] = []
            
            # Add current values to stats if missing
            if 'current' not in battery_stats.get('battery_charge', {}):
                if transformed_history['timeseries']['battery_charge']:
                    latest_point = transformed_history['timeseries']['battery_charge'][-1]
                    if 'battery_charge' not in battery_stats:
                        battery_stats['battery_charge'] = {}
                    battery_stats['battery_charge']['current'] = latest_point['value']
            
            if 'current' not in battery_stats.get('battery_runtime', {}):
                if transformed_history['timeseries']['battery_runtime']:
                    latest_point = transformed_history['timeseries']['battery_runtime'][-1]
                    if 'battery_runtime' not in battery_stats:
                        battery_stats['battery_runtime'] = {}
                    # Store value in seconds
                    battery_stats['battery_runtime']['current'] = latest_point['value']
            
            # Do NOT convert runtime to minutes here - keep original seconds for calculation
            # Store original values for health calculation
            original_runtime_seconds = battery_stats['battery_runtime']['avg']
            
            # Generate chart with the transformed data
            chart_url = self._generate_chart_image(transformed_history, 'battery')
            
            logger.debug(f"Battery chart generated: {'Success' if chart_url else 'Failed'}")
            
            # Determine battery health based on available metrics
            battery_health = "Unknown"
            health_score = None
            
            try:
                # If we have actual battery metrics, use them
                from core.battery.battery import calculate_battery_health
                available_metrics = {}
                
                if 'battery_charge' in battery_stats and battery_stats['battery_charge']['current'] > 0:
                    available_metrics['battery_charge'] = battery_stats['battery_charge']['current']
                
                if 'battery_voltage' in battery_stats and battery_stats['battery_voltage']['current'] > 0:
                    available_metrics['battery_voltage'] = battery_stats['battery_voltage']['current']
                    
                    # Check for battery_voltage_nominal - either from battery_stats or use a fixed 24V as fallback
                    # This is better than using input_voltage (which is typically ~230V)
                    if 'battery_voltage_nominal' in battery_stats:
                        available_metrics['battery_voltage_nominal'] = battery_stats['battery_voltage_nominal']['avg']
                    else:
                        # Use 24V as default nominal voltage for most battery UPS systems
                        available_metrics['battery_voltage_nominal'] = 24.0
                
                if 'battery_runtime' in battery_stats and original_runtime_seconds > 0:
                    available_metrics['battery_runtime'] = original_runtime_seconds  # Use seconds for calculation
                    available_metrics['battery_runtime_low'] = 300  # 5 minutes as low threshold (in seconds)
                
                # Calculate health if we have enough metrics
                if len(available_metrics) >= 2:
                    health_score = calculate_battery_health(available_metrics)
                    logger.debug(f"Calculated battery health score: {health_score}")
                    
                    if health_score is not None:
                        if health_score >= 80:
                            battery_health = "Good"
                        elif health_score >= 50:
                            battery_health = "Fair"
                        else:
                            battery_health = "Poor"
                else:
                    # Fallback to basic calculation if not enough metrics
                    charge = battery_stats['battery_charge']['avg']
                    runtime_minutes = original_runtime_seconds / 60
                    
                    if charge >= 80 and runtime_minutes > 30:
                        battery_health = "Good"
                        health_score = 85
                    elif charge >= 50 and runtime_minutes > 15:
                        battery_health = "Fair"
                        health_score = 65
                    else:
                        battery_health = "Poor"
                        health_score = 35
            except Exception as e:
                logger.error(f"Error calculating battery health: {str(e)}")
                
            # Add the battery health to the report
            battery_stats['health'] = battery_health
            battery_stats['health_score'] = health_score if health_score is not None else 0
            
            # NOW convert runtime to minutes for display in the report
            # This ensures we only do the conversion once, right before returning
            if 'avg' in battery_stats.get('battery_runtime', {}):
                logger.debug(f"Runtime before conversion: avg={battery_stats['battery_runtime']['avg']} seconds")
                # Always convert from seconds to minutes since battery.py no longer does the conversion
                # Use int(value * 10 + 0.5) / 10 for exact match with JavaScript's Math.round(value * 10) / 10
                battery_stats['battery_runtime']['avg'] = int(battery_stats['battery_runtime']['avg'] / 60 * 10 + 0.5) / 10
                battery_stats['battery_runtime']['min'] = int(battery_stats['battery_runtime']['min'] / 60 * 10 + 0.5) / 10
                battery_stats['battery_runtime']['max'] = int(battery_stats['battery_runtime']['max'] / 60 * 10 + 0.5) / 10
                battery_stats['battery_runtime']['current'] = int(battery_stats['battery_runtime']['current'] / 60 * 10 + 0.5) / 10
                logger.debug(f"Runtime after conversion: avg={battery_stats['battery_runtime']['avg']} minutes")
            
            return {
                'include_battery': True,
                'battery_stats': battery_stats,
                'battery_chart_url': chart_url,
                **voltage_data  # Include all voltage data
            }
        except Exception as e:
            logger.error(f"Error getting battery report data: {str(e)}", exc_info=True)
            # Return a safe structure with default values
            default_battery_stats = {
                'battery_charge': {'min': 100, 'max': 100, 'avg': 100, 'current': 100},
                'battery_runtime': {'min': 7380, 'max': 7380, 'avg': 7380, 'current': 7380},
                'battery_voltage': {'min': 24, 'max': 24, 'avg': 24, 'current': 24},
                'battery_temperature': {'min': 25, 'max': 25, 'avg': 25, 'current': 25},
                'health': 'Good',
                'health_score': 85
            }
            return {
                'include_battery': False,
                'battery_stats': default_battery_stats,
                'has_battery_voltage': False,
                'has_input_voltage': False,
                'has_output_voltage': False,
                'show_voltage_section': False,
                'input_voltage_value': 0,
                'output_voltage_value': 0
            }

    def _get_power_report_data(self, from_date, to_date, target_id=None):
        """Collect power report data"""
        try:
            if target_id is not None:
                metric_names = [
                    'ups_realpower',
                    'ups_load',
                    'input_voltage',
                    'output_voltage',
                    'ups_realpower_nominal',
                    'ups_power_nominal',
                ]
                history, stats, period_args = self._load_target_metric_payload(
                    target_id=target_id,
                    metric_names=metric_names,
                    from_date=from_date,
                    to_date=to_date,
                    max_points=1600,
                )

                energy_payload = build_energy_payload(
                    target_id=target_id,
                    tz=self.tz,
                    period=period_args['period'],
                    from_time=period_args['from_time'],
                    to_time=period_args['to_time'],
                    selected_date=period_args['selected_date'],
                    selected_day=period_args['selected_day'],
                )
                realpower_nominal = self._stat_or_zero(stats, 'ups_realpower_nominal')
                power_nominal = self._stat_or_zero(stats, 'ups_power_nominal')

                nominal_power = realpower_nominal['current'] or realpower_nominal['avg']
                if nominal_power <= 0:
                    nominal_power = power_nominal['current'] or power_nominal['avg']

                power_stats = {
                    'total_consumption': round(float(energy_payload.get('totalEnergy', 0.0)) / 1000.0, 3),
                    'input_voltage': self._stat_or_zero(stats, 'input_voltage')['avg'],
                    'output_voltage': self._stat_or_zero(stats, 'output_voltage')['avg'],
                    'nominal_power': nominal_power,
                    'load': self._stat_or_zero(stats, 'ups_load')['current'],
                }

                chart_payload = {
                    'timeseries': {
                        'ups_realpower': history.get('ups_realpower') or [],
                        'ups_load': history.get('ups_load') or [],
                        'input_voltage': history.get('input_voltage') or [],
                    }
                }
                chart_url = self._generate_chart_image(chart_payload, 'power')

                return {
                    'include_power': True,
                    'power_stats': power_stats,
                    'power_chart_url': chart_url,
                }

            # Determine if the period is a single day
            is_same_day = from_date.date() == to_date.date()
            
            if is_same_day:
                # If the same day, use the period='day' format with selected_date
                power_stats = get_power_stats(
                    period='day',
                    selected_date=from_date
                )
                
                history_data = get_power_history(
                    period='day',
                    selected_date=from_date
                )
            else:
                # For multi-day periods, use the period='range' format
                power_stats = get_power_stats(
                    period='range',
                    from_time=from_date.strftime('%Y-%m-%d'),
                    to_time=to_date.strftime('%Y-%m-%d')
                )
                
                history_data = get_power_history(
                    period='range',
                    from_date=from_date.strftime('%Y-%m-%d'),
                    to_date=to_date.strftime('%Y-%m-%d')
                )

            # Initialize defaults for processed stats
            processed_stats = {
                'total_consumption': 0,
                'input_voltage': 0,
                'output_voltage': 0,
                'nominal_power': 0,
                'load': 0
            }

            # Reorganize the data in the format expected by the template
            try:
                # Convert total_energy from Wh to kWh for proper display in reports
                total_energy_wh = 0
                total_energy_kwh = 0
                if power_stats and 'ups_realpower' in power_stats and 'total_energy' in power_stats['ups_realpower']:
                    total_energy_wh = power_stats['ups_realpower']['total_energy']
                    total_energy_kwh = total_energy_wh / 1000  # Convert from Wh to kWh
                
                # Get input voltage - try input_voltage first, then input_transfer_high/low
                input_voltage = 0
                if power_stats and 'input_voltage' in power_stats and 'avg' in power_stats['input_voltage']:
                    input_voltage = power_stats['input_voltage']['avg']
                elif power_stats and 'input_transfer_high' in power_stats and 'input_transfer_low' in power_stats:
                    # If input_voltage is not available, but input_transfer_high and input_transfer_low are,
                    # use the average as an approximation
                    high = 0
                    low = 0
                    
                    if isinstance(power_stats['input_transfer_high'], dict) and 'avg' in power_stats['input_transfer_high']:
                        high = power_stats['input_transfer_high']['avg']
                    elif isinstance(power_stats['input_transfer_high'], (int, float)):
                        high = power_stats['input_transfer_high']
                    
                    if isinstance(power_stats['input_transfer_low'], dict) and 'avg' in power_stats['input_transfer_low']:
                        low = power_stats['input_transfer_low']['avg']
                    elif isinstance(power_stats['input_transfer_low'], (int, float)):
                        low = power_stats['input_transfer_low']
                    
                    if high > 0 and low > 0:
                        input_voltage = (high + low) / 2
                        logger.debug(f"Using average of transfer thresholds as input voltage: {input_voltage}")
                
                # Get output voltage
                output_voltage = 0
                if power_stats and 'output_voltage' in power_stats:
                    if isinstance(power_stats['output_voltage'], dict) and 'avg' in power_stats['output_voltage']:
                        output_voltage = power_stats['output_voltage']['avg']
                    elif isinstance(power_stats['output_voltage'], (int, float)):
                        output_voltage = power_stats['output_voltage']
                
                # Get nominal power - try ups_realpower_nominal first, then ups_power_nominal
                nominal_power = 0
                if power_stats and 'ups_realpower_nominal' in power_stats:
                    if isinstance(power_stats['ups_realpower_nominal'], dict) and 'avg' in power_stats['ups_realpower_nominal']:
                        nominal_power = power_stats['ups_realpower_nominal']['avg']
                    elif isinstance(power_stats['ups_realpower_nominal'], (int, float)):
                        nominal_power = power_stats['ups_realpower_nominal']
                elif power_stats and 'ups_power_nominal' in power_stats:
                    if isinstance(power_stats['ups_power_nominal'], dict) and 'avg' in power_stats['ups_power_nominal']:
                        nominal_power = power_stats['ups_power_nominal']['avg']
                    elif isinstance(power_stats['ups_power_nominal'], (int, float)):
                        nominal_power = power_stats['ups_power_nominal']
                
                # Get load
                load = 0
                if power_stats and 'ups_load' in power_stats:
                    if isinstance(power_stats['ups_load'], dict):
                        if 'current' in power_stats['ups_load']:
                            load = power_stats['ups_load']['current']
                        elif 'avg' in power_stats['ups_load']:
                            load = power_stats['ups_load']['avg']
                    elif isinstance(power_stats['ups_load'], (int, float)):
                        load = power_stats['ups_load']
                
                processed_stats = {
                    'total_consumption': total_energy_kwh,  # Now in kWh instead of Wh
                    'input_voltage': input_voltage,
                    'output_voltage': output_voltage,
                    'nominal_power': nominal_power,
                    'load': load
                }
                
                # Log the processed stats for debugging
                logger.debug(f"Processed power stats: {processed_stats}")
                
            except (KeyError, TypeError) as e:
                logger.warning(f"Unable to process all power data: {str(e)}")

            # Transform history_data into the expected timeseries format for _create_power_chart
            timeseries_data = {'timeseries': {}}
            
            # Convert each metric's data into the expected format
            for metric, data_points in history_data.items():
                if data_points:
                    timeseries_data['timeseries'][metric] = data_points
            
            # If no data is available, create an empty structure
            if not timeseries_data['timeseries']:
                timeseries_data['timeseries'] = {
                    'ups_realpower': [],
                    'ups_load': [],
                    'input_voltage': []
                }

            return {
                'include_power': True,
                'power_stats': processed_stats,
                'power_chart_url': self._generate_chart_image(timeseries_data, 'power')
            }

        except Exception as e:
            logger.error(f"Error getting power report data: {str(e)}", exc_info=True)
            return {'include_power': False} 

    def _resolve_ups_event_model(self):
        """Resolve UPSEvent model with lazy ModelClasses fallback."""
        try:
            from core.db.ups import UPSEvent as direct_event_model, db as ups_db
        except Exception as exc:
            logger.error(f"Could not import core.db.ups for events: {exc}")
            return None, None

        if direct_event_model is not None:
            return direct_event_model, ups_db

        model_space = getattr(ups_db, 'ModelClasses', None)
        if model_space is None:
            try:
                from core.db.models import init_models
                from core.db.ups import register_models_from_modelclasses

                init_models(ups_db)
                model_space = getattr(ups_db, 'ModelClasses', None)
                if model_space is not None:
                    try:
                        register_models_from_modelclasses(model_space)
                    except Exception as register_exc:
                        logger.debug(f"Could not register lazy-loaded event model globally: {register_exc}")
            except Exception as exc:
                logger.error(f"Failed lazy initialization of ModelClasses for events: {exc}")

        if model_space is not None and hasattr(model_space, 'UPSEvent'):
            return model_space.UPSEvent, ups_db

        try:
            from core.db.orm.orm_ups_events import init_model

            return init_model(ups_db.Model), ups_db
        except Exception as exc:
            logger.error(f"Could not initialize UPSEvent ORM model directly: {exc}")

        return None, ups_db

    def _get_events_data(self, from_date, to_date, target_id=None):
        """Get UPS events for the report period."""
        try:
            event_model, ups_db = self._resolve_ups_event_model()
            if event_model is None:
                logger.error("UPSEvent model is not available")
                return {'include_events': False}
            if ups_db is None or not hasattr(ups_db, 'session'):
                logger.error("Database session is not available")
                return {'include_events': False}

            timestamp_field = 'timestamp_utc' if hasattr(event_model, 'timestamp_utc') else 'timestamp'
            query = ups_db.session.query(event_model)
            if target_id is not None and hasattr(event_model, 'target_id'):
                query = query.filter(event_model.target_id == int(target_id))

            if timestamp_field == 'timestamp_utc':
                query = query.filter(
                    event_model.timestamp_utc.between(from_date, to_date)
                ).order_by(event_model.timestamp_utc.desc())
            else:
                query = query.filter(
                    event_model.timestamp.between(from_date, to_date)
                ).order_by(event_model.timestamp.desc())

            events = query.all()
            if not events:
                logger.info("No UPS events found for the report period")
                return {'include_events': False}

            formatted_events = []
            for event in events:
                timestamp = getattr(event, timestamp_field, None)
                if timestamp is None:
                    continue
                if timestamp.tzinfo is None:
                    timestamp = pytz.UTC.localize(timestamp)

                formatted_events.append(
                    {
                        'timestamp': timestamp.astimezone(self.tz).strftime('%Y-%m-%d %H:%M:%S'),
                        'event_type': getattr(event, 'event_type', 'EVENT'),
                        'description': getattr(event, 'event_message', None)
                        or getattr(event, 'description', None)
                        or getattr(event, 'event_type', 'Event'),
                        'severity': getattr(event, 'severity', 'info'),
                    }
                )

            if not formatted_events:
                return {'include_events': False}

            logger.info(f"Retrieved {len(formatted_events)} UPS events for the report")
            return {
                'include_events': True,
                'events': formatted_events,
            }
        except Exception as exc:
            logger.error(f"Error getting events data: {exc}", exc_info=True)
            return {'include_events': False}

    def _generate_chart_image(self, data, chart_type, is_single_day=False):
        """Generate a chart image based on the provided data"""
        try:
            logger.debug(f"Generating {chart_type} chart image")
            
            # Check if plotly is available
            if not go or not px:
                logger.error("Plotly is not available, cannot generate chart image")
                return None
                
            # Create a figure based on chart type
            if chart_type == 'energy':
                if 'data' not in data:
                    logger.error("Energy data is missing 'data' key")
                    return None
                    
                # Check if we need to pass extra parameters
                chart_params = {}
                if 'from_date' in data and 'to_date' in data:
                    chart_params['from_date'] = data['from_date']
                    chart_params['to_date'] = data['to_date']
                
                # Use is_single_day if provided
                if 'is_single_day' in data:
                    is_single_day = data['is_single_day']
                
                logger.debug(f"Creating energy chart with is_single_day={is_single_day}")
                fig = self._create_energy_chart(data['data'], **chart_params, is_single_day=is_single_day)
            elif chart_type == 'battery':
                if 'timeseries' not in data:
                    logger.error("Battery data is missing 'timeseries' key")
                    return None
                fig = self._create_battery_chart(data)
            elif chart_type == 'power':
                if 'timeseries' not in data:
                    logger.error("Power data is missing 'timeseries' key")
                    return None
                fig = self._create_power_chart(data)
            elif chart_type == 'voltage':
                if 'timeseries' not in data:
                    logger.error("Voltage data is missing 'timeseries' key")
                    return None
                fig = self._create_voltage_chart(data)
            else:
                logger.error(f"Unknown chart type: {chart_type}")
                return None
                
            # Export the figure as an image
            img_bytes = BytesIO()
            fig.write_image(img_bytes, format='png', width=800, height=500)
            img_bytes.seek(0)
            
            # Convert to base64 for embedding in HTML
            encoded = base64.b64encode(img_bytes.read()).decode('ascii')
            chart_url = f"data:image/png;base64,{encoded}"
            
            return chart_url
            
        except Exception as e:
            logger.error(f"Error generating chart image: {str(e)}", exc_info=True)
            return None

    def _create_energy_chart(self, cost_trend, from_date=None, to_date=None, is_single_day=False):
        """Create energy consumption chart"""
        try:
            if not cost_trend or len(cost_trend) == 0:
                logger.warning("No cost trend data available for energy chart")
                fig = go.Figure()
                fig.add_annotation(
                    text="No energy data available for the selected period",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5,
                    showarrow=False,
                    font=dict(size=16)
                )
                return fig

            self._ensure_timezone()
            normalized_points = self._build_xy_series(cost_trend, x_key='x', y_key='y')
            if not normalized_points:
                logger.warning("No valid normalized points for energy chart")
                fig = go.Figure()
                fig.add_annotation(
                    text="No energy data available for the selected period",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5,
                    showarrow=False,
                    font=dict(size=16)
                )
                return fig

            if isinstance(from_date, datetime):
                local_from = from_date.astimezone(self.tz)
            else:
                local_from = normalized_points[0][0]
            if isinstance(to_date, datetime):
                local_to = to_date.astimezone(self.tz)
            else:
                local_to = normalized_points[-1][0]
            if local_to < local_from:
                local_from, local_to = local_to, local_from

            same_local_day = local_from.date() == local_to.date()
            duration_seconds = max(0.0, (local_to - local_from).total_seconds())
            month_span = ((local_to.year - local_from.year) * 12) + (local_to.month - local_from.month) + 1

            if same_local_day or duration_seconds <= 24 * 3600:
                bucket_granularity = 'hour'
            elif duration_seconds <= 31 * 24 * 3600:
                bucket_granularity = 'day'
            elif month_span <= 24:
                bucket_granularity = 'month'
            else:
                bucket_granularity = 'year'

            def _bucket_start(dt_value):
                if bucket_granularity == 'hour':
                    return dt_value.replace(minute=0, second=0, microsecond=0)
                if bucket_granularity == 'day':
                    return dt_value.replace(hour=0, minute=0, second=0, microsecond=0)
                if bucket_granularity == 'month':
                    return dt_value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                return dt_value.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

            bucket_cost = {}
            for dt_value, cost_value in normalized_points:
                bucket = _bucket_start(dt_value)
                bucket_cost[bucket] = bucket_cost.get(bucket, 0.0) + max(0.0, cost_value)

            if bucket_granularity == 'hour' and same_local_day:
                day_start = local_from.replace(hour=0, minute=0, second=0, microsecond=0)
                x_values = [day_start + timedelta(hours=hour) for hour in range(24)]
                cost_values = [round(bucket_cost.get(point, 0.0), 6) for point in x_values]
            else:
                if bucket_granularity == 'hour':
                    start_bucket = local_from.replace(minute=0, second=0, microsecond=0)
                    end_bucket = local_to.replace(minute=0, second=0, microsecond=0)
                    x_values = []
                    cursor = start_bucket
                    while cursor <= end_bucket:
                        x_values.append(cursor)
                        cursor += timedelta(hours=1)
                elif bucket_granularity == 'day':
                    start_bucket = local_from.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_bucket = local_to.replace(hour=0, minute=0, second=0, microsecond=0)
                    x_values = []
                    cursor = start_bucket
                    while cursor <= end_bucket:
                        x_values.append(cursor)
                        cursor += timedelta(days=1)
                elif bucket_granularity == 'month':
                    start_bucket = local_from.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    end_bucket = local_to.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    x_values = []
                    cursor = start_bucket
                    while cursor <= end_bucket:
                        x_values.append(cursor)
                        next_month = cursor.month + 1
                        next_year = cursor.year
                        if next_month > 12:
                            next_month = 1
                            next_year += 1
                        cursor = cursor.replace(year=next_year, month=next_month, day=1)
                else:
                    start_bucket = local_from.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                    end_bucket = local_to.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                    x_values = []
                    cursor = start_bucket
                    while cursor <= end_bucket:
                        x_values.append(cursor)
                        cursor = cursor.replace(year=cursor.year + 1, month=1, day=1)

                cost_values = [round(bucket_cost.get(point, 0.0), 6) for point in x_values]

            x_iso_values = [
                point.isoformat() if isinstance(point, datetime) else str(point)
                for point in x_values
            ]

            fig = go.Figure()

            fig.add_trace(go.Bar(
                x=x_iso_values,
                y=cost_values,
                name='Energy Cost',
                marker_color='#00A0FF',
                hovertemplate='%{y:.4f}<extra></extra>'
            ))

            fig.update_layout(
                plot_bgcolor='white',
                paper_bgcolor='white',
                xaxis=dict(
                    title=(
                        "Hour"
                        if bucket_granularity == 'hour'
                        else "Date"
                    ),
                    type='date',
                    tickformat=(
                        '%H:%M'
                        if bucket_granularity == 'hour'
                        else '%Y-%m-%d'
                        if bucket_granularity == 'day'
                        else '%Y-%m'
                        if bucket_granularity == 'month'
                        else '%Y'
                    ),
                    tickangle=0 if bucket_granularity == 'hour' else -45,
                    showgrid=False,
                ),
                yaxis=dict(
                    title="Energy Cost",
                    title_font=dict(color='#00A0FF'),
                    tickfont=dict(color='#00A0FF'),
                    rangemode='tozero',
                    showgrid=False,
                ),
                margin=dict(l=50, r=50, t=30, b=80),
                height=500,
                width=800,
                bargap=0.15,
                hovermode="x",
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )

            if bucket_granularity == 'hour' and same_local_day:
                start = local_from.replace(hour=0, minute=0, second=0, microsecond=0)
                end = start + timedelta(hours=23, minutes=59, seconds=59)
                fig.update_xaxes(range=[start.isoformat(), end.isoformat()])

            return fig

        except Exception as e:
            logger.error(f"Error creating energy chart: {str(e)}", exc_info=True)
            fig = go.Figure()
            fig.add_annotation(
                text=f"Error creating energy chart: {str(e)}",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color="red")
            )
            return fig

    def _create_battery_chart(self, data):
        """Create battery status chart"""
        try:
            if not data or not isinstance(data, dict) or 'timeseries' not in data:
                logger.warning("No valid battery data available for chart")
                # Return an empty chart with a message
                fig = go.Figure()
                fig.add_annotation(
                    text="No battery data available for the selected period",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5,
                    showarrow=False,
                    font=dict(size=16)
                )
                return fig
            
            timeseries = data['timeseries']
            
            # Create the figure for battery data
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # Add charge percentage as a line
            if 'battery_charge' in timeseries and timeseries['battery_charge']:
                charge_data = self._build_xy_series(timeseries['battery_charge'])
                charge_x, charge_y = self._series_to_plotly_xy(charge_data)
                fig.add_trace(
                    go.Scatter(
                        x=charge_x,
                        y=charge_y,
                        name='Battery Charge (%)',
                        line=dict(color='#4e73df', width=2),
                        hovertemplate='%{y:.1f}%<extra></extra>'
                    )
                )
            
            # Add runtime as a second y-axis
            if 'battery_runtime' in timeseries and timeseries['battery_runtime']:
                runtime_data = self._build_xy_series(
                    timeseries['battery_runtime'],
                    value_transform=lambda value: value / 60.0,
                )
                runtime_x, runtime_y = self._series_to_plotly_xy(runtime_data)
                fig.add_trace(
                    go.Scatter(
                        x=runtime_x,
                        y=runtime_y,
                        name='Runtime (min)',
                        yaxis='y2',
                        line=dict(color='#1cc88a', width=2, dash='dash'),
                        hovertemplate='%{y:.1f} min<extra></extra>'
                    ),
                    secondary_y=True
                )
            
            # Add voltage as third trace if available
            if 'battery_voltage' in timeseries and timeseries['battery_voltage']:
                voltage_data = self._build_xy_series(timeseries['battery_voltage'])
                voltage_x, voltage_y = self._series_to_plotly_xy(voltage_data)
                fig.add_trace(
                    go.Scatter(
                        x=voltage_x,
                        y=voltage_y,
                        name='Battery Voltage (V)',
                        yaxis='y3',
                        line=dict(color='#f6c23e', width=2, dash='dot'),
                        hovertemplate='%{y:.1f} V<extra></extra>'
                    ),
                    secondary_y=False
                )

            if not fig.data:
                fig.add_annotation(
                    text="No battery data available for the selected period",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5,
                    showarrow=False,
                    font=dict(size=16)
                )
                fig.update_layout(plot_bgcolor='white', paper_bgcolor='white')
                return fig
            
            # Configure layout to match the energy chart style
            fig.update_layout(
                # White background like energy chart
                plot_bgcolor='white',
                paper_bgcolor='white',
                
                # Legend at the top like energy chart
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                
                # Other layout settings
                margin=dict(l=50, r=50, t=30, b=80),
                height=500,
                width=800,
                hovermode="x unified",
            )
            
            # Update axes titles with improved styling
            fig.update_yaxes(
                title_text="Charge (%)",
                title_font=dict(color='#4e73df'),
                tickfont=dict(color='#4e73df'),
                gridcolor='#f0f0f0',  # Light grid lines
                secondary_y=False
            )
            
            fig.update_yaxes(
                title_text="Runtime (min)",
                title_font=dict(color='#1cc88a'),
                tickfont=dict(color='#1cc88a'),
                gridcolor='#f0f0f0',  # Light grid lines
                secondary_y=True
            )
            
            fig.update_xaxes(
                title_text="Time",
                type='date',
                tickformat='%H:%M',
                gridcolor='#f0f0f0'
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating battery chart: {str(e)}", exc_info=True)
            fig = go.Figure()
            fig.add_annotation(
                text=f"Error creating battery chart: {str(e)}",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color="red")
            )
            return fig

    def _create_power_chart(self, data):
        """Create power consumption chart"""
        try:
            if not data or not isinstance(data, dict) or 'timeseries' not in data:
                logger.warning("No valid power data available for chart")
                # Return an empty chart with a message
                fig = go.Figure()
                fig.add_annotation(
                    text="No power data available for the selected period",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5,
                    showarrow=False,
                    font=dict(size=16)
                )
                return fig
            
            timeseries = data['timeseries']
            
            # Create the figure for power data with a consistent title
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # Add real power (watts) as a line
            if 'ups_realpower' in timeseries and timeseries['ups_realpower']:
                power_data = self._build_xy_series(timeseries['ups_realpower'])
                power_x, power_y = self._series_to_plotly_xy(power_data)
                fig.add_trace(
                    go.Scatter(
                        x=power_x,
                        y=power_y,
                        name='Power (W)',
                        line=dict(color='#4e73df', width=2),
                        hovertemplate='%{y:.1f} W<extra></extra>',
                        fill='tozeroy',  # Add fill to make chart appear full
                        fillcolor='rgba(78, 115, 223, 0.1)'  # Light blue fill color
                    )
                )
            
            # Add load percentage as a second y-axis if available
            if 'ups_load' in timeseries and timeseries['ups_load']:
                load_data = self._build_xy_series(timeseries['ups_load'])
                load_x, load_y = self._series_to_plotly_xy(load_data)
                fig.add_trace(
                    go.Scatter(
                        x=load_x,
                        y=load_y,
                        name='Load (%)',
                        yaxis='y2',
                        line=dict(color='#e74a3b', width=2, dash='dash'),
                        hovertemplate='%{y:.1f}%<extra></extra>'
                    ),
                    secondary_y=True
                )
            
            # Add input voltage as a third line if available
            if 'input_voltage' in timeseries and timeseries['input_voltage']:
                voltage_data = self._build_xy_series(timeseries['input_voltage'])
                voltage_x, voltage_y = self._series_to_plotly_xy(voltage_data)
                fig.add_trace(
                    go.Scatter(
                        x=voltage_x,
                        y=voltage_y,
                        name='Input Voltage (V)',
                        yaxis='y2',
                        line=dict(color='#f6c23e', width=2, dash='dot'),
                        hovertemplate='%{y:.1f} V<extra></extra>'
                    ),
                    secondary_y=True
                )

            if not fig.data:
                fig.add_annotation(
                    text="No power data available for the selected period",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5,
                    showarrow=False,
                    font=dict(size=16)
                )
                fig.update_layout(plot_bgcolor='white', paper_bgcolor='white')
                return fig
            
            # Update layout with a consistent style matching other report charts
            fig.update_layout(
                title={
                    'text': 'Power Consumption and Load',
                    'y':0.95,
                    'x':0.5,
                    'xanchor': 'center',
                    'yanchor': 'top',
                    'font': {'size': 20}
                },
                legend={
                    'orientation': 'h',
                    'yanchor': 'bottom',
                    'y': 1.02,
                    'xanchor': 'center',
                    'x': 0.5
                },
                margin={'l': 60, 'r': 60, 't': 80, 'b': 60},
                height=500,  # Fixed height for consistent appearance
                hovermode='x unified',
                plot_bgcolor='rgba(255, 255, 255, 0.9)',
                paper_bgcolor='white'
            )
            
            # Update axes titles and formatting
            fig.update_yaxes(
                title_text="Power (W)", 
                secondary_y=False,
                gridcolor='rgba(0, 0, 0, 0.1)'
            )
            fig.update_yaxes(
                title_text="Load (%) / Voltage (V)", 
                secondary_y=True,
                gridcolor='rgba(0, 0, 0, 0.05)'
            )
            fig.update_xaxes(
                title_text="Time",
                type='date',
                tickformat='%H:%M',
                gridcolor='rgba(0, 0, 0, 0.1)'
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating power chart: {str(e)}", exc_info=True)
            fig = go.Figure()
            fig.add_annotation(
                text=f"Error creating power chart: {str(e)}",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color="red")
            )
            return fig

    def _create_voltage_chart(self, data):
        """Create voltage readings chart"""
        try:
            if not data or not isinstance(data, dict) or 'timeseries' not in data:
                logger.warning("No valid voltage data available for chart")
                # Return an empty chart with a message
                fig = go.Figure()
                fig.add_annotation(
                    text="No voltage data available for the selected period",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5,
                    showarrow=False,
                    font=dict(size=16)
                )
                return fig
            
            timeseries = data['timeseries']
            
            # Create the figure for voltage data
            fig = go.Figure()
            
            # Add input voltage as a line
            if 'input_voltage' in timeseries and timeseries['input_voltage']:
                input_data = self._build_xy_series(timeseries['input_voltage'])
                input_x, input_y = self._series_to_plotly_xy(input_data)
                fig.add_trace(
                    go.Scatter(
                        x=input_x,
                        y=input_y,
                        name='Input Voltage (V)',
                        line=dict(color='#4e73df', width=2),
                        hovertemplate='%{y:.1f} V<extra></extra>'
                    )
                )
            
            # Add output voltage as a second line
            if 'output_voltage' in timeseries and timeseries['output_voltage']:
                output_data = self._build_xy_series(timeseries['output_voltage'])
                output_x, output_y = self._series_to_plotly_xy(output_data)
                fig.add_trace(
                    go.Scatter(
                        x=output_x,
                        y=output_y,
                        name='Output Voltage (V)',
                        line=dict(color='#1cc88a', width=2, dash='dash'),
                        hovertemplate='%{y:.1f} V<extra></extra>'
                    )
                )
            
            # Add battery voltage as a third line if available
            if 'battery_voltage' in timeseries and timeseries['battery_voltage']:
                battery_data = self._build_xy_series(timeseries['battery_voltage'])
                battery_x, battery_y = self._series_to_plotly_xy(battery_data)
                fig.add_trace(
                    go.Scatter(
                        x=battery_x,
                        y=battery_y,
                        name='Battery Voltage (V)',
                        line=dict(color='#f6c23e', width=2, dash='dot'),
                        hovertemplate='%{y:.1f} V<extra></extra>'
                    )
                )

            if not fig.data:
                fig.add_annotation(
                    text="No voltage data available for the selected period",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5,
                    showarrow=False,
                    font=dict(size=16)
                )
                fig.update_layout(plot_bgcolor='white', paper_bgcolor='white')
                return fig
            
            # Update layout for better appearance
            fig.update_layout(
                title="Voltage Readings",
                title_x=0.5,
                plot_bgcolor='white',
                paper_bgcolor='white',
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                margin=dict(l=10, r=10, t=50, b=10),
                height=500,
                width=800
            )
            
            # Update axes titles and styling
            fig.update_yaxes(
                title_text="Voltage (V)",
                gridcolor='rgba(0, 0, 0, 0.1)',
                zeroline=False
            )
            
            fig.update_xaxes(
                title_text="Time",
                type='date',
                tickformat='%H:%M',
                gridcolor='rgba(0, 0, 0, 0.1)'
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating voltage chart: {str(e)}", exc_info=True)
            fig = go.Figure()
            fig.add_annotation(
                text=f"Error creating voltage chart: {str(e)}",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color="red")
            )
            return fig 

    def _get_voltage_report_data(self, from_date, to_date, target_id=None):
        """Collect voltage report data using existing APIs"""
        try:
            if target_id is not None:
                metric_names = [
                    'input_voltage',
                    'output_voltage',
                    'battery_voltage',
                    'input_transfer_low',
                    'input_transfer_high',
                    'input_frequency',
                    'output_frequency',
                ]
                history, stats, _ = self._load_target_metric_payload(
                    target_id=target_id,
                    metric_names=metric_names,
                    from_date=from_date,
                    to_date=to_date,
                    max_points=1600,
                )

                input_voltage = self._stat_or_zero(stats, 'input_voltage')
                output_voltage = self._stat_or_zero(stats, 'output_voltage')
                transfer_low = self._stat_or_zero(stats, 'input_transfer_low')
                transfer_high = self._stat_or_zero(stats, 'input_transfer_high')
                input_frequency = self._stat_or_zero(stats, 'input_frequency')
                output_frequency = self._stat_or_zero(stats, 'output_frequency')

                chart_payload = {
                    'timeseries': {
                        'input_voltage': history.get('input_voltage') or [],
                        'output_voltage': history.get('output_voltage') or [],
                        'battery_voltage': history.get('battery_voltage') or [],
                    }
                }
                chart_url = self._generate_chart_image(chart_payload, 'voltage')

                return {
                    'include_voltage': True,
                    'voltage_stats': {
                        'input_voltage': input_voltage['avg'],
                        'input_voltage_min': input_voltage['min'],
                        'input_voltage_max': input_voltage['max'],
                        'output_voltage': output_voltage['avg'],
                        'output_voltage_min': output_voltage['min'],
                        'output_voltage_max': output_voltage['max'],
                        'input_transfer_low': transfer_low['avg'],
                        'input_transfer_high': transfer_high['avg'],
                        'input_frequency': input_frequency['avg'],
                        'output_frequency': output_frequency['avg'],
                    },
                    'has_input_voltage': input_voltage['avg'] > 0,
                    'has_output_voltage': output_voltage['avg'] > 0,
                    'voltage_chart_url': chart_url,
                }

            logger.debug(f"Retrieving voltage data from {from_date} to {to_date}")
            
            # Import voltage functions
            from core.voltage.voltage import get_voltage_stats, get_voltage_history
            
            # Get voltage statistics
            voltage_stats = get_voltage_stats('range', from_date.strftime('%Y-%m-%d'), to_date.strftime('%Y-%m-%d'))
            
            # If no voltage stats are available, try to get from UPS data
            if not voltage_stats:
                from core.db.ups import get_ups_data
                ups_data = get_ups_data()
                
                # Create a minimal voltage_stats structure
                voltage_stats = {}
                voltage_metrics = [
                    'input_voltage', 'output_voltage', 
                    'input_transfer_low', 'input_transfer_high',
                    'input_frequency', 'output_frequency'
                ]
                
                for metric in voltage_metrics:
                    if hasattr(ups_data, metric) and getattr(ups_data, metric) is not None:
                        value = float(getattr(ups_data, metric))
                        voltage_stats[metric] = {
                            'min': value,
                            'max': value,
                            'avg': value,
                            'available': True,
                            'current': value
                        }
            
            # Get voltage history
            history_data = get_voltage_history('range', from_date.strftime('%Y-%m-%d'), to_date.strftime('%Y-%m-%d'))
            
            # Process voltage stats for the report
            has_input_voltage = 'input_voltage' in voltage_stats
            has_output_voltage = 'output_voltage' in voltage_stats
            
            voltage_data = {
                'has_input_voltage': has_input_voltage,
                'has_output_voltage': has_output_voltage,
                'voltage_stats': {
                    'input_voltage': voltage_stats.get('input_voltage', {}).get('avg', 0),
                    'input_voltage_min': voltage_stats.get('input_voltage', {}).get('min', 0),
                    'input_voltage_max': voltage_stats.get('input_voltage', {}).get('max', 0),
                    'output_voltage': voltage_stats.get('output_voltage', {}).get('avg', 0),
                    'output_voltage_min': voltage_stats.get('output_voltage', {}).get('min', 0),
                    'output_voltage_max': voltage_stats.get('output_voltage', {}).get('max', 0),
                    'input_transfer_low': voltage_stats.get('input_transfer_low', {}).get('avg', 0),
                    'input_transfer_high': voltage_stats.get('input_transfer_high', {}).get('avg', 0),
                    'input_frequency': voltage_stats.get('input_frequency', {}).get('avg', 0),
                    'output_frequency': voltage_stats.get('output_frequency', {}).get('avg', 0)
                }
            }
            
            # Transform history_data for the chart
            transformed_history = {'timeseries': {}}
            
            # Process voltage metrics if they exist in history data
            if history_data and isinstance(history_data, dict):
                for metric in ['input_voltage', 'output_voltage', 'battery_voltage']:
                    if metric in history_data and history_data[metric]:
                        transformed_history['timeseries'][metric] = history_data[metric]
            
            # Generate chart with the transformed data
            chart_url = self._generate_chart_image(transformed_history, 'voltage')
            
            logger.debug(f"Voltage chart generated: {'Success' if chart_url else 'Failed'}")
            
            return {
                'include_voltage': True,
                'voltage_stats': voltage_data['voltage_stats'],
                'has_input_voltage': has_input_voltage,
                'has_output_voltage': has_output_voltage,
                'voltage_chart_url': chart_url
            }
        except Exception as e:
            logger.error(f"Error getting voltage report data: {str(e)}", exc_info=True)
            # Return a safe structure with default values
            return {
                'include_voltage': False,
                'voltage_stats': {},
                'has_input_voltage': False,
                'has_output_voltage': False,
                'voltage_chart_url': None
            }

    def generate_report(self, from_date, to_date, report_type='daily', target_id=None):
        """Generate a report for the specified time period"""
        try:
            self._ensure_timezone()
            logger.info(f"Generating {report_type} report from {from_date} to {to_date}")
            
            # Check if dates are strings and convert to datetime if needed
            if isinstance(from_date, str):
                from_date = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            if isinstance(to_date, str):
                to_date = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
            
            # Ensure dates are timezone-aware
            if from_date.tzinfo is None:
                # Always use self.tz (which is set from current_app.CACHE_TIMEZONE)
                from_date = self.tz.localize(from_date)
            if to_date.tzinfo is None:
                # Always use self.tz (which is set from current_app.CACHE_TIMEZONE)
                to_date = self.tz.localize(to_date)
            
            resolved_target_id = resolve_settings_target_id(target_id)

            # Get data for the report sections
            energy_data = self._get_energy_report_data(from_date, to_date, target_id=resolved_target_id)
            battery_data = self._get_battery_report_data(from_date, to_date, target_id=resolved_target_id)
            power_data = self._get_power_report_data(from_date, to_date, target_id=resolved_target_id)
            voltage_data = self._get_voltage_report_data(from_date, to_date, target_id=resolved_target_id)
            events_data = self._get_events_data(from_date, to_date, target_id=resolved_target_id)
            
            # Check if there's no data at all
            if (not energy_data.get('include_energy', False) and 
                not battery_data.get('include_battery', False) and 
                not power_data.get('include_power', False) and
                not voltage_data.get('include_voltage', False) and
                not events_data.get('include_events', False)):
                
                logger.warning("No data available for the report period")
                return {
                    'status': 'error',
                    'message': 'No data available for the selected period'
                }
            
            # Add additional context data for template
            current_year = datetime.now(self.tz).year
            is_problematic_provider = False  # Set this based on email provider if needed
            currency = energy_data.get('currency') or "€"
            generation_date = datetime.now(self.tz).strftime('%Y-%m-%d %H:%M:%S')
            
            # Format the report period string based on the report type
            report_period = ""
            if report_type == 'yesterday':
                # For yesterday, ensure we show a single day (same day for start and end)
                yesterday_str = from_date.astimezone(self.tz).strftime('%Y-%m-%d')
                report_period = f"{yesterday_str} 00:00 - {yesterday_str} 23:59"
            elif report_type == 'last_week':
                # For last week, ensure proper Monday-to-Sunday range
                start_str = from_date.astimezone(self.tz).strftime('%Y-%m-%d')
                # Calculate end date (should be Sunday)
                monday = from_date.astimezone(self.tz).replace(hour=0, minute=0, second=0, microsecond=0)
                sunday = monday + timedelta(days=6)
                end_str = sunday.strftime('%Y-%m-%d')
                report_period = f"{start_str} 00:00 - {end_str} 23:59"
            elif report_type == 'last_month':
                # For last month, ensure it's the correct month range (1st to last day)
                # Calculate first day of the month
                
                # Get the first day of the current month
                first_day_current_month = datetime(to_date.year, to_date.month, 1, tzinfo=self.tz)
                
                # Calculate last day of previous month (day before first of this month)
                last_day = first_day_current_month - timedelta(days=1)
                
                # Calculate first day of the previous month
                if last_day.month == 12:  # December
                    first_day = datetime(last_day.year - 1, 12, 1, tzinfo=self.tz)
                else:
                    first_day = datetime(last_day.year, last_day.month, 1, tzinfo=self.tz)
                
                # Format the strings - ensure we're using the correct month for the report period
                start_str = first_day.strftime('%Y-%m-%d')
                end_str = last_day.strftime('%Y-%m-%d')
                report_period = f"{start_str} 00:00 - {end_str} 23:59"
            elif report_type == 'range' or report_type == 'custom':
                # For custom range, use exact selected dates
                from_str = from_date.astimezone(self.tz).strftime('%Y-%m-%d')
                to_str = to_date.astimezone(self.tz).strftime('%Y-%m-%d')
                report_period = f"{from_str} 00:00 - {to_str} 23:59"
            else:
                # Default format
                report_period = f"{from_date.astimezone(self.tz).strftime('%Y-%m-%d %H:%M')} - {to_date.astimezone(self.tz).strftime('%Y-%m-%d %H:%M')}"
            
            # Prepare the report context with all data
            context = {
                'report_title': f"{report_type.capitalize()} UPS Report",
                'report_date': datetime.now(self.tz).strftime('%Y-%m-%d %H:%M:%S'),
                'report_period': report_period,
                'server_name': self._get_server_name(),
                'current_year': current_year,
                'is_problematic_provider': is_problematic_provider,
                'currency': currency,
                'generation_date': generation_date,
                'from_date': from_date.astimezone(self.tz).strftime('%Y-%m-%d %H:%M'),
                'to_date': to_date.astimezone(self.tz).strftime('%Y-%m-%d %H:%M'),
                **energy_data,
                **battery_data,
                **power_data,
                **voltage_data,
                **events_data
            }
            
            # Generate the HTML report
            try:
                # First try using self.app if available
                if self.app:
                    with self.app.app_context():
                        html_content = render_template('dashboard/mail/report.html', **context)
                else:
                    # Try to import current_app from Flask if self.app is not available
                    from flask import current_app
                    
                    # Check if we're already in an app context
                    if current_app:
                        html_content = render_template('dashboard/mail/report.html', **context)
                    else:
                        # If we can't access the app context, create a dummy HTML report
                        logger.warning("Cannot access Flask app context, using fallback HTML report")
                        # Create a simple HTML report as fallback
                        html_content = self._create_fallback_html_report(context)
            except Exception as e:
                logger.error(f"Error rendering HTML template: {str(e)}", exc_info=True)
                # Create a simple HTML report as fallback
                html_content = self._create_fallback_html_report(context)
            
            # Return the report data
            return {
                'status': 'success',
                'html': html_content,
                'data': context
            }
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': f"Failed to generate report: {str(e)}"
            }

    def _create_fallback_html_report(self, context):
        """Create a simple fallback HTML report when Flask app context is not available"""
        try:
            # Basic HTML template as fallback
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{context.get('report_title', 'UPS Report')}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    h1 {{ color: #2b5797; }}
                    table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                </style>
            </head>
            <body>
                <h1>{context.get('report_title', 'UPS Report')}</h1>
                <p>Generated on: {context.get('report_date', datetime.now(self.tz).strftime('%Y-%m-%d %H:%M:%S'))}</p>
                <p>Period: {context.get('report_period', 'Unknown period')}</p>
                
                <h2>Summary</h2>
                <p>This is a basic fallback report generated because the Flask application context was not available.</p>
                <p>Please check the application logs for more information.</p>
            """
            
            # Add energy data if available
            if context.get('include_energy', False) and 'energy_stats' in context:
                energy_stats = context['energy_stats']
                html += f"""
                <h2>Energy Consumption</h2>
                <table>
                    <tr><th>Total Energy</th><td>{energy_stats.get('totalEnergy', 0)} kWh</td></tr>
                    <tr><th>Total Cost</th><td>{energy_stats.get('totalCost', 0)}</td></tr>
                    <tr><th>Average Load</th><td>{energy_stats.get('avgLoad', 0)}%</td></tr>
                </table>
                """
            
            # Add battery data if available
            if context.get('include_battery', False) and 'battery_stats' in context:
                battery_stats = context['battery_stats']
                html += f"""
                <h2>Battery Status</h2>
                <table>
                    <tr><th>Charge</th><td>{battery_stats.get('battery_charge', {}).get('avg', 0)}%</td></tr>
                    <tr><th>Runtime</th><td>{battery_stats.get('battery_runtime', {}).get('avg', 0)} minutes</td></tr>
                </table>
                """
            
            # Add power data if available
            if context.get('include_power', False) and 'power_stats' in context:
                power_stats = context['power_stats']
                html += f"""
                <h2>Power Consumption</h2>
                <table>
                    <tr><th>Total Consumption</th><td>{power_stats.get('total_consumption', 0)} kWh</td></tr>
                    <tr><th>Load</th><td>{power_stats.get('load', 0)}%</td></tr>
                </table>
                """
                
            # Add voltage data if available
            if context.get('include_voltage', False) and 'voltage_stats' in context:
                voltage_stats = context['voltage_stats']
                html += f"""
                <h2>Voltage Report</h2>
                <table>
                """
                
                if context.get('has_input_voltage', False):
                    html += f"""
                    <tr><th>Input Voltage</th><td>{voltage_stats.get('input_voltage', 0)} V</td></tr>
                    <tr><th>Min/Max Input</th><td>{voltage_stats.get('input_voltage_min', 0)} / {voltage_stats.get('input_voltage_max', 0)} V</td></tr>
                    """
                
                if context.get('has_output_voltage', False):
                    html += f"""
                    <tr><th>Output Voltage</th><td>{voltage_stats.get('output_voltage', 0)} V</td></tr>
                    <tr><th>Min/Max Output</th><td>{voltage_stats.get('output_voltage_min', 0)} / {voltage_stats.get('output_voltage_max', 0)} V</td></tr>
                    """
                
                if voltage_stats.get('input_transfer_low', 0) > 0 and voltage_stats.get('input_transfer_high', 0) > 0:
                    html += f"""
                    <tr><th>Transfer Thresholds</th><td>{voltage_stats.get('input_transfer_low', 0)} - {voltage_stats.get('input_transfer_high', 0)} V</td></tr>
                    """
                
                html += "</table>"
            
            # Add events if available
            if context.get('include_events', False) and 'events' in context:
                events = context['events']
                html += f"""
                <h2>Events ({len(events)})</h2>
                <table>
                    <tr><th>Timestamp</th><th>Type</th><th>Description</th></tr>
                """
                
                for event in events[:10]:  # Limit to first 10 events
                    html += f"""
                    <tr>
                        <td>{event.get('timestamp', '')}</td>
                        <td>{event.get('event_type', '')}</td>
                        <td>{event.get('description', '')}</td>
                    </tr>
                    """
                
                if len(events) > 10:
                    html += f"<tr><td colspan='3'>... and {len(events) - 10} more events</td></tr>"
                
                html += "</table>"
            
            html += """
            </body>
            </html>
            """
            
            return html
        except Exception as e:
            logger.error(f"Error creating fallback HTML report: {str(e)}", exc_info=True)
            return f"<html><body><h1>UPS Report</h1><p>Error generating report: {str(e)}</p></body></html>"

    def send_report_email(self, from_date, to_date, recipients, report_type='daily', target_id=None):
        """Generate and send a report via email"""
        try:
            resolved_target_id = resolve_settings_target_id(target_id)

            def _scoped_mail_query(mail_model):
                query = mail_model.query
                if hasattr(mail_model, 'target_id'):
                    query = query.filter(mail_model.target_id.is_(None))
                return query

            # Get email configuration
            email_config = get_current_email_settings()
            
            # Check if email is configured by verifying email_config is a valid string (email address)
            if not email_config:
                logger.error("Email is not configured or is disabled")
                return {
                    'status': 'error',
                    'message': 'Email service is not configured or is disabled'
                }
            
            # Validate recipient emails
            if not recipients or not isinstance(recipients, list) or len(recipients) == 0:
                logger.error("No valid recipients provided for email report")
                return {
                    'status': 'error',
                    'message': 'No valid recipients provided'
                }
            
            # Validate email addresses
            validated_emails = validate_emails(recipients)
            if len(validated_emails) == 0:
                logger.error("All provided email addresses are invalid")
                return {
                    'status': 'error',
                    'message': 'All provided email addresses are invalid'
                }
            
            logger.info(f"Generating report for period {from_date} to {to_date} of type {report_type}")
            
            # Generate the report
            report_result = self.generate_report(
                from_date,
                to_date,
                report_type,
                target_id=resolved_target_id,
            )
            
            if report_result.get('status') != 'success':
                logger.error(f"Failed to generate report: {report_result.get('message')}")
                return report_result
            
            logger.info(f"Report generated successfully, preparing email for {len(validated_emails)} recipients")
            
            # Prepare subject based on report type
            period_str = f"{from_date.astimezone(self.tz).strftime('%Y-%m-%d')} to {to_date.astimezone(self.tz).strftime('%Y-%m-%d')}"
            if report_type == 'daily':
                subject = f"Daily UPS Report - {from_date.astimezone(self.tz).strftime('%Y-%m-%d')}"
            elif report_type == 'weekly':
                subject = f"Weekly UPS Report - {period_str}"
            elif report_type == 'monthly':
                subject = f"Monthly UPS Report - {from_date.astimezone(self.tz).strftime('%B %Y')}"
            else:
                subject = f"UPS Report - {period_str}"
            
            # Construct a meaningful subject
            subject = f"UPS {report_type.capitalize()} Report for {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}"
            
            # Add server name to subject if available
            server_name = self._get_server_name()
            if server_name:
                subject = f"{server_name} - {subject}"
            
            # Get mail configuration for SMTP settings
            MailConfig = get_mail_config_model()
            smtp_settings = {}
            
            if MailConfig:
                mail_config = _scoped_mail_query(MailConfig).order_by(MailConfig.id.asc()).first()
                if mail_config:
                    logger.info(f"Using mail configuration: SMTP={mail_config.smtp_server}:{mail_config.smtp_port}, Provider={mail_config.provider}")
                    
                    password = mail_config.password
                    if password is None:
                        if str(getattr(mail_config, 'username', '') or '').strip():
                            logger.error("❌ Mail config password is None or cannot be decrypted for authenticated SMTP")
                            return {
                                'status': 'error',
                                'message': 'Mail configuration password cannot be decrypted. Please update your mail settings with a new password.'
                            }
                        logger.info("Mail config has no password set; continuing with no-auth SMTP")
                        password = ''

                    logger.debug(f"✅ Successfully accessed mail config password (length: {len(password)})")

                    smtp_settings = {
                        'smtp_server': mail_config.smtp_server,  # Use smtp_server key for consistency
                        'smtp_port': mail_config.smtp_port,      # Use smtp_port key for consistency 
                        'username': mail_config.username,
                        'password': password,
                        'from_email': mail_config.from_email,    # Use from_email property
                        'provider': mail_config.provider,
                        'tls': mail_config.tls,                  # Use tls key for consistency
                        'tls_starttls': mail_config.tls_starttls, # Use tls_starttls key for consistency
                        # Add a longer timeout for report emails which may be larger
                        'timeout': 120  # 2 minute timeout for report sending
                    }
                else:
                    logger.error("No mail configuration found")
                    return {
                        'status': 'error',
                        'message': 'Mail configuration not found'
                    }
            else:
                logger.error("MailConfig model not available")
                return {
                    'status': 'error',
                    'message': 'Mail configuration model not available'
                }
                
            # Log report size to help diagnose potential issues
            report_size = len(report_result['html'])
            logger.info(f"Sending report email (size: {report_size} bytes) to: {', '.join(validated_emails)}")
            
            # Send the email with the report as HTML content
            to_addr = ", ".join(validated_emails) if len(validated_emails) > 1 else validated_emails[0]
            
            # Catch any exceptions during email sending for better diagnostics
            try:
                email_result = send_email(
                    to_addr=to_addr,
                    subject=subject,
                    html_content=report_result['html'],
                    smtp_settings=smtp_settings
                )
                
                success, message = email_result
                if not success:
                    logger.error(f"Failed to send email: {message}")
                    # Try to get more specific error information
                    from core.mail import interpret_email_error
                    error_diagnosis = interpret_email_error(message)
                    logger.error(f"Email error diagnosis: {error_diagnosis}")
                    
                    return {
                        'status': 'error',
                        'message': f"Failed to send email: {message}",
                        'diagnosis': error_diagnosis
                    }
                
                logger.info(f"Successfully sent {report_type} report email to {len(validated_emails)} recipients")
                return {
                    'status': 'success',
                    'message': f"Successfully sent report to {len(validated_emails)} recipients"
                }
            except Exception as email_err:
                logger.error(f"Exception during email sending: {str(email_err)}", exc_info=True)
                return {
                    'status': 'error',
                    'message': f"Exception during email sending: {str(email_err)}"
                }
            
        except Exception as e:
            logger.error(f"Error sending report email: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': f"Failed to send report email: {str(e)}"
            }

    def _normalize_report_template_data(self, report_data):
        """Ensure report template fields are always present with safe defaults."""
        self._ensure_timezone()
        normalized = dict(report_data or {})

        def _ensure_metric_block(container, key):
            value = container.get(key)
            if not isinstance(value, dict):
                container[key] = {'avg': 0, 'min': 0, 'max': 0, 'current': 0}
                return
            value.setdefault('avg', 0)
            value.setdefault('min', 0)
            value.setdefault('max', 0)
            value.setdefault('current', 0)

        energy_stats = normalized.get('energy_stats')
        if not isinstance(energy_stats, dict):
            energy_stats = {}
        energy_stats.setdefault('totalEnergy', 0)
        energy_stats.setdefault('totalCost', 0)
        energy_stats.setdefault('avgLoad', 0)
        energy_stats.setdefault('co2', 0)
        normalized['energy_stats'] = energy_stats
        normalized.setdefault('energy_chart_url', None)

        battery_stats = normalized.get('battery_stats')
        if not isinstance(battery_stats, dict):
            battery_stats = {}
        _ensure_metric_block(battery_stats, 'battery_charge')
        _ensure_metric_block(battery_stats, 'battery_runtime')
        _ensure_metric_block(battery_stats, 'battery_voltage')
        battery_stats.setdefault('health_score', 0)
        battery_stats.setdefault('health', 'Unknown')
        normalized['battery_stats'] = battery_stats
        normalized.setdefault('battery_chart_url', None)
        normalized.setdefault('show_voltage_section', False)
        normalized.setdefault('has_battery_voltage', False)
        normalized.setdefault('has_input_voltage', False)
        normalized.setdefault('has_output_voltage', False)
        normalized.setdefault('input_voltage_value', 0)
        normalized.setdefault('output_voltage_value', 0)

        power_stats = normalized.get('power_stats')
        if not isinstance(power_stats, dict):
            power_stats = {}
        power_stats.setdefault('total_consumption', 0)
        power_stats.setdefault('input_voltage', 0)
        power_stats.setdefault('output_voltage', 0)
        power_stats.setdefault('nominal_power', 0)
        power_stats.setdefault('load', 0)
        normalized['power_stats'] = power_stats
        normalized.setdefault('power_chart_url', None)

        voltage_stats = normalized.get('voltage_stats')
        if not isinstance(voltage_stats, dict):
            voltage_stats = {}
        voltage_stats.setdefault('input_voltage', 0)
        voltage_stats.setdefault('input_voltage_min', 0)
        voltage_stats.setdefault('input_voltage_max', 0)
        voltage_stats.setdefault('output_voltage', 0)
        voltage_stats.setdefault('output_voltage_min', 0)
        voltage_stats.setdefault('output_voltage_max', 0)
        voltage_stats.setdefault('input_transfer_low', 0)
        voltage_stats.setdefault('input_transfer_high', 0)
        normalized['voltage_stats'] = voltage_stats
        normalized.setdefault('voltage_chart_url', None)

        events = normalized.get('events')
        if not isinstance(events, list):
            normalized['events'] = []

        normalized.setdefault('currency', '€')
        normalized.setdefault('server_name', 'UPS')
        normalized.setdefault('report_period', '')
        normalized.setdefault('generation_date', datetime.now(self.tz).strftime('%Y-%m-%d %H:%M:%S'))
        normalized.setdefault('current_year', datetime.now(self.tz).year)
        normalized.setdefault('is_problematic_provider', False)

        normalized.setdefault('include_energy', False)
        normalized.setdefault('include_battery', False)
        normalized.setdefault('include_power', False)
        normalized.setdefault('include_voltage', False)
        normalized.setdefault('include_events', False)
        return normalized

    def generate_and_send_report(
        self,
        report_types,
        email,
        from_date,
        to_date,
        period_type='daily',
        id_email=None,
        target_id=None,
        scheduled=False,
        schedule_id=None,
    ):
        """
        Generate and send a report with the specified parameters.
        This method is used by the scheduler to send reports.
        
        Args:
            report_types: List of report types to include
            email: Email address to send the report to
            from_date: Start date for the report
            to_date: End date for the report
            period_type: Type of report period (daily, weekly, monthly, range)
            id_email: ID of the email configuration to use
            target_id: UPS target scope for multi-UPS shared database mode
            scheduled: Whether this is a scheduled report
            schedule_id: ID of the schedule if this is a scheduled report
            
        Returns:
            bool: True if the report was successfully sent, False otherwise
        """
        try:
            self._ensure_timezone()
            logger.info(f"Generating and sending report for {period_type} period from {from_date} to {to_date}")
            logger.info(f"Selected report types: {report_types}")
            
            # Make sure we have a Flask app - try to get it from current_app if self.app is not set
            app_is_available = False
            app_context = None
            
            if self.app:
                app_is_available = True
                app_context = self.app.app_context()
            else:
                try:
                    if has_app_context():
                        app_is_available = True
                    else:
                        # Try to get current_app
                        try:
                            app_is_available = current_app._get_current_object() is not None
                            logger.debug("Using Flask current_app for report generation")
                        except Exception:
                            app_is_available = False
                except Exception:
                    app_is_available = False
            
            if not app_is_available:
                logger.warning("Flask app not available for report generation - this is expected when run from scheduler")

            resolved_target_id = resolve_settings_target_id(target_id)

            def _scoped_mail_query(mail_model):
                query = mail_model.query
                if hasattr(mail_model, 'target_id'):
                    query = query.filter(mail_model.target_id.is_(None))
                return query
            
            # Initialize recipient list
            recipients = []
            
            # Get MailConfig if id_email is provided - this takes precedence
            if id_email:
                try:
                    MailConfig = get_mail_config_model()
                    if MailConfig:
                        logger.info(f"Looking up email configuration with ID {id_email}")
                        mail_query = _scoped_mail_query(MailConfig)
                        mail_config = mail_query.filter(MailConfig.id == int(id_email)).first()
                        if mail_config:
                            logger.info(f"Found mail configuration with ID {id_email}: {mail_config.username}")
                            # Use to_email from mail_config if available
                            if hasattr(mail_config, 'to_email') and mail_config.to_email:
                                recipients = [mail_config.to_email]
                                logger.info(f"Using to_email from email configuration: {recipients}")
                            else:
                                # If no to_email, use the username as email
                                recipients = [mail_config.username]
                                logger.info(f"No to_email in mail config, using username as email: {recipients}")
                        else:
                            logger.error(f"Email configuration with ID {id_email} not found")
                            return False
                except Exception as e:
                    logger.error(f"Error getting email configuration: {str(e)}")
                    return False
            
            # Only use the email parameter if recipients list is still empty (no valid id_email)
            if not recipients:
                # Check if email is a string, convert to list if needed
                if isinstance(email, str):
                    recipients = [email]
                    logger.debug(f"Converted email string '{email}' to list")
                elif isinstance(email, list):
                    recipients = email
                    logger.debug(f"Using email list with {len(recipients)} recipients")
                else:
                    logger.error(f"Invalid email format: {type(email)}")
                    return False
            
            # Log the final recipients
            logger.info(f"Sending report to: {recipients}")
            
            # Generate the report according to selected report types
            report_result = self.generate_report(
                from_date,
                to_date,
                period_type,
                target_id=resolved_target_id,
            )
            
            if report_result.get('status') != 'success':
                logger.error(f"Failed to generate report: {report_result.get('message')}")
                return False
            
            # Get report data
            report_data = report_result.get('data', {})
            
            # Modify the report data to include only selected report types
            # Convert report_types to a list if it's a string
            if isinstance(report_types, str):
                report_types = [type_name.strip() for type_name in report_types.split(',')]
            
            # Apply selections based on report types
            if report_types:
                selected = {str(item).strip().lower() for item in report_types if str(item).strip()}
                report_data['include_energy'] = (
                    'energy' in selected and bool(report_data.get('include_energy', False))
                )
                report_data['include_battery'] = (
                    'battery' in selected and bool(report_data.get('include_battery', False))
                )
                report_data['include_power'] = (
                    'power' in selected and bool(report_data.get('include_power', False))
                )
                report_data['include_voltage'] = (
                    'voltage' in selected and bool(report_data.get('include_voltage', False))
                )
                report_data['include_events'] = (
                    'events' in selected and bool(report_data.get('include_events', False))
                )
                
                logger.info(f"Filtered report sections based on selection: Energy={report_data.get('include_energy')}, Battery={report_data.get('include_battery')}, Power={report_data.get('include_power')}, Voltage={report_data.get('include_voltage')}, Events={report_data.get('include_events')}")

            report_data = self._normalize_report_template_data(report_data)
            
            # Re-generate the HTML with the filtered data
            try:
                # First try using self.app if available
                if app_is_available:
                    if app_context:
                        with app_context:
                            html_content = render_template('dashboard/mail/report.html', **report_data)
                    else:
                        # Already in an app context
                        html_content = render_template('dashboard/mail/report.html', **report_data)
                else:
                    # If we can't access the app context, create a dummy HTML report
                    logger.warning("Cannot access Flask app context, using fallback HTML report")
                    # Create a simple HTML report as fallback
                    html_content = self._create_fallback_html_report(report_data)
            except Exception as e:
                logger.error(f"Error rendering filtered HTML template: {str(e)}", exc_info=True)
                # Try fallback
                html_content = self._create_fallback_html_report(report_data)
            
            # Prepare subject based on report types and period
            period_str = f"{from_date.astimezone(self.tz).strftime('%Y-%m-%d')} to {to_date.astimezone(self.tz).strftime('%Y-%m-%d')}"
            if period_type == 'daily':
                subject = f"Daily UPS Report - {from_date.astimezone(self.tz).strftime('%Y-%m-%d')}"
            elif period_type == 'weekly':
                subject = f"Weekly UPS Report - {period_str}"
            elif period_type == 'monthly':
                # Format the month name properly for the subject
                month_name = from_date.astimezone(self.tz).strftime('%B %Y')
                subject = f"Monthly UPS Report - {month_name}"
            else:
                subject = f"UPS Report - {period_str}"
            
            # Add selected report types to the subject
            report_type_names = []
            for report_type in report_types:
                report_type_names.append(report_type.capitalize())
            
            if report_type_names:
                subject += f" ({', '.join(report_type_names)})"
            
            # Add server name to subject if available
            server_name = self._get_server_name()
            if server_name:
                subject = f"{server_name} - {subject}"
                
            # Note: report_period is now properly formatted in generate_report
            # and doesn't need to be overridden here.
            
            # Send the email with the report as HTML content
            MailConfig = get_mail_config_model()
            smtp_settings = {}
            
            if MailConfig:
                # If we have id_email, use that specific mail config
                if id_email:
                    mail_query = _scoped_mail_query(MailConfig)
                    mail_config = mail_query.filter(MailConfig.id == int(id_email)).first()
                    if mail_config:
                        logger.debug(f"Using mail configuration with ID {id_email} for SMTP settings")
                        smtp_settings = {
                            'host': mail_config.smtp_server,
                            'port': mail_config.smtp_port,
                            'username': mail_config.username,
                            'password': mail_config.password,
                            'from_email': mail_config.from_email or mail_config.username,
                            'from_name': 'UPS Monitor',
                            'tls': bool(mail_config.tls),
                            'tls_starttls': bool(mail_config.tls_starttls),
                            'provider': mail_config.provider
                        }
                    else:
                        logger.error(f"Mail configuration with ID {id_email} not found")
                        return False
                # No fallback to default mail config - require explicit selection
                elif recipients:
                    # Use the first mail config only for SMTP settings, not for recipient address
                    # We already have a recipient from the previous steps
                    mail_query = _scoped_mail_query(MailConfig)
                    mail_config = mail_query.order_by(MailConfig.is_default.desc(), MailConfig.id.asc()).first()
                    if mail_config:
                        logger.debug("Using mail configuration for SMTP settings only (not for recipient)")
                        smtp_settings = {
                            'host': mail_config.smtp_server,
                            'port': mail_config.smtp_port,
                            'username': mail_config.username,
                            'password': mail_config.password,
                            'from_email': mail_config.from_email or mail_config.username,
                            'from_name': 'UPS Monitor',
                            'tls': bool(mail_config.tls),
                            'tls_starttls': bool(mail_config.tls_starttls),
                            'provider': mail_config.provider
                        }
                    else:
                        logger.error("No mail configuration found for SMTP settings")
                        return False
                else:
                    logger.error("No mail configuration ID provided and no recipients set")
                    return False
            else:
                logger.error("MailConfig model not available")
                return False
            
            # Validate recipient emails
            validated_emails = validate_emails(recipients)
            if len(validated_emails) == 0:
                logger.error("All provided email addresses are invalid")
                return False
            
            # Send the email
            to_addr = ", ".join(validated_emails) if len(validated_emails) > 1 else validated_emails[0]
            email_result = send_email(
                to_addr=to_addr,
                subject=subject,
                html_content=html_content,
                smtp_settings=smtp_settings
            )
            
            success, message = email_result
            if not success:
                logger.error(f"Failed to send email: {message}")
                return False
            
            # Update schedule last_run if scheduled
            if scheduled and schedule_id:
                try:
                    with data_lock:
                        schedule = db.session.query(ReportSchedule).get(schedule_id)
                        if schedule:
                            schedule.last_run = datetime.now(self.tz)
                            db.session.commit()
                            logger.info(f"Updated last_run for schedule {schedule_id}")
                except Exception as e:
                    logger.error(f"Error updating schedule last_run: {str(e)}")
            
            logger.info(f"Successfully sent report email to {len(validated_emails)} recipients")
            return True
                
        except Exception as e:
            logger.error(f"Error generating and sending report: {str(e)}", exc_info=True)
            return False

    def scheduled_report_job(self, report_id):
        """Job function to run scheduled reports"""
        try:
            # Get the schedule configuration from the database
            with data_lock:
                schedule_config = db.session.query(ReportSchedule).filter_by(id=report_id).first()
                
                if not schedule_config:
                    scheduler_logger.error(f"Scheduled report with ID {report_id} not found")
                    return
                
                if not schedule_config.enabled:
                    scheduler_logger.info(f"Scheduled report {report_id} is disabled, skipping execution")
                    return
                
                # Check if recipients are valid
                recipients = schedule_config.recipients.split(',') if schedule_config.recipients else []
                recipients = [email.strip() for email in recipients]
                
                if not recipients:
                    scheduler_logger.error(f"No recipients defined for scheduled report {report_id}")
                    return
                
                # Calculate date range based on report type
                now = datetime.now(self.tz)
                
                if schedule_config.report_type == 'daily':
                    # For daily reports, use the previous day
                    yesterday = now - timedelta(days=1)
                    from_date = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0)
                    to_date = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59)
                    
                elif schedule_config.report_type == 'weekly':
                    # For weekly reports, use the previous week
                    # Calculate the start of last week (previous Monday)
                    days_since_monday = now.weekday()
                    start_of_this_week = now - timedelta(days=days_since_monday)
                    start_of_last_week = start_of_this_week - timedelta(days=7)
                    end_of_last_week = start_of_this_week - timedelta(seconds=1)
                    
                    from_date = datetime(start_of_last_week.year, start_of_last_week.month, start_of_last_week.day, 0, 0, 0)
                    to_date = datetime(end_of_last_week.year, end_of_last_week.month, end_of_last_week.day, 23, 59, 59)
                    
                elif schedule_config.report_type == 'monthly':
                    # For monthly reports, use the previous month
                    # Calculate first day of current month
                    first_day_of_this_month = datetime(now.year, now.month, 1)
                    # Calculate last day of previous month (day before first of this month)
                    last_day_of_last_month = first_day_of_this_month - timedelta(days=1)
                    # Calculate first day of last month
                    if last_day_of_last_month.month == 12:  # If previous month is December
                        first_day_of_last_month = datetime(last_day_of_last_month.year - 1, 12, 1)
                    else:
                        first_day_of_last_month = datetime(last_day_of_last_month.year, last_day_of_last_month.month, 1)
                    
                    from_date = datetime(first_day_of_last_month.year, first_day_of_last_month.month, first_day_of_last_month.day, 0, 0, 0)
                    to_date = datetime(last_day_of_last_month.year, last_day_of_last_month.month, last_day_of_last_month.day, 23, 59, 59)
                    
                else:
                    scheduler_logger.error(f"Unknown report type {schedule_config.report_type} for schedule {report_id}")
                    return
                
                # Ensure dates are timezone-aware
                from_date = self.tz.localize(from_date)
                to_date = self.tz.localize(to_date)
                
                # Send the report
                scheduler_logger.info(f"Running scheduled {schedule_config.report_type} report {report_id} from {from_date} to {to_date}")
                
                # Send report email
                result = self.send_report_email(
                    from_date=from_date,
                    to_date=to_date,
                    recipients=recipients,
                    report_type=schedule_config.report_type,
                    target_id=getattr(schedule_config, 'target_id', None),
                )
                
                if result.get('status') == 'success':
                    scheduler_logger.info(f"Successfully sent scheduled report {report_id}: {result.get('message')}")
                    
                    # Update last run time
                    schedule_config.last_run = datetime.now(self.tz)
                    db.session.commit()
                else:
                    scheduler_logger.error(f"Failed to send scheduled report {report_id}: {result.get('message')}")
                
        except Exception as e:
            scheduler_logger.error(f"Error executing scheduled report {report_id}: {str(e)}", exc_info=True)

    def save_schedule(self, schedule_config, target_id=None):
        """Save a report schedule configuration"""
        try:
            resolved_target_id = resolve_settings_target_id(
                schedule_config.get('target_id', target_id) if isinstance(schedule_config, dict) else target_id
            )

            # Extract values from the config
            schedule_id = schedule_config.get('id')
            enabled = schedule_config.get('enabled', True)
            report_type = schedule_config.get('report_type', 'daily')
            cron_expr = schedule_config.get('cron_expression')
            recipients = schedule_config.get('recipients', [])
            
            # Validate report type
            if report_type not in ['daily', 'weekly', 'monthly']:
                logger.error(f"Invalid report type: {report_type}")
                return {'success': False, 'error': 'Invalid report type'}
            
            # Validate recipients
            if not recipients or not isinstance(recipients, list) or len(recipients) == 0:
                logger.error("No valid recipients provided for report schedule")
                return {'success': False, 'error': 'No valid recipients provided'}
            
            # Validate email addresses
            validated_emails = []
            for email in recipients:
                try:
                    valid = validate_email(email)
                    validated_emails.append(valid.email)
                except EmailNotValidError as e:
                    logger.warning(f"Invalid email address in schedule: {email}")
            
            if len(validated_emails) == 0:
                logger.error("All provided email addresses are invalid")
                return {'success': False, 'error': 'All provided email addresses are invalid'}
            
            # Format recipients as comma-separated string
            recipients_str = ','.join(validated_emails)
            
            with data_lock:
                if schedule_id:
                    # Update existing schedule
                    schedule_query = db.session.query(ReportSchedule).filter_by(id=schedule_id)
                    if hasattr(ReportSchedule, 'target_id'):
                        if resolved_target_id is None:
                            schedule_query = schedule_query.filter(ReportSchedule.target_id.is_(None))
                        else:
                            schedule_query = schedule_query.filter(ReportSchedule.target_id == int(resolved_target_id))
                    existing_schedule = schedule_query.first()
                    
                    if existing_schedule:
                        existing_schedule.enabled = enabled
                        existing_schedule.report_type = report_type
                        existing_schedule.cron_expression = cron_expr
                        existing_schedule.recipients = recipients_str
                        existing_schedule.updated_at = datetime.now(self.tz)
                        
                        db.session.commit()
                        logger.info(f"Updated report schedule with ID {schedule_id}")
                        
                        # If this is a different ID than the last one, stop the old job
                        if self.last_schedule_id is not None and self.last_schedule_id != schedule_id:
                            try:
                                schedule.clear(f"report_{self.last_schedule_id}")
                                logger.info(f"Removed old schedule job report_{self.last_schedule_id}")
                            except Exception as e:
                                logger.warning(f"Error clearing old schedule: {str(e)}")
                                
                        # Update the scheduled job if enabled
                        if enabled and cron_expr:
                            self._schedule_report_job(schedule_id, cron_expr)
                            self.last_schedule_id = schedule_id
                        else:
                            # Remove from scheduler if disabled
                            try:
                                schedule.clear(f"report_{schedule_id}")
                                logger.info(f"Removed disabled schedule job report_{schedule_id}")
                            except Exception as e:
                                logger.warning(f"Error clearing disabled schedule: {str(e)}")
                        
                        return {'success': True, 'id': schedule_id}
                    else:
                        logger.error(f"Schedule with ID {schedule_id} not found")
                        return {'success': False, 'error': f"Schedule with ID {schedule_id} not found"}
                else:
                    # Create new schedule
                    schedule_kwargs = {
                        'enabled': enabled,
                        'report_type': report_type,
                        'cron_expression': cron_expr,
                        'recipients': recipients_str,
                        'created_at': datetime.now(self.tz),
                        'updated_at': datetime.now(self.tz),
                    }
                    if hasattr(ReportSchedule, 'target_id'):
                        schedule_kwargs['target_id'] = resolved_target_id

                    new_schedule = ReportSchedule(**schedule_kwargs)
                    
                    db.session.add(new_schedule)
                    db.session.commit()
                    
                    new_id = new_schedule.id
                    logger.info(f"Created new report schedule with ID {new_id}")
                    
                    # Schedule the job if enabled
                    if enabled and cron_expr:
                        self._schedule_report_job(new_id, cron_expr)
                        self.last_schedule_id = new_id
                    
                    return {'success': True, 'id': new_id}
                
        except Exception as e:
            logger.error(f"Error saving schedule: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def _schedule_report_job(self, schedule_id, cron_expr):
        """Schedule a report job using the scheduler"""
        try:
            # Parse the cron expression
            cron_parts = cron_expr.split()
            
            if len(cron_parts) != 5:
                logger.error(f"Invalid cron expression format: {cron_expr}")
                return False
            
            minute, hour, day, month, day_of_week = cron_parts
            
            # Clear any existing schedule with this ID
            try:
                schedule.clear(f"report_{schedule_id}")
                logger.debug(f"Cleared existing schedule job report_{schedule_id}")
            except Exception:
                pass
            
            # Register a new job with the parsed cron expression
            if minute != '*' and hour != '*':
                # Schedule at specific time
                schedule.every().day.at(f"{hour.zfill(2)}:{minute.zfill(2)}").do(
                    self.scheduled_report_job, schedule_id
                ).tag(f"report_{schedule_id}")
                logger.info(f"Scheduled report {schedule_id} to run at {hour.zfill(2)}:{minute.zfill(2)}")
            else:
                # More complex cron expressions - use best approximation with schedule library
                if day_of_week != '*':
                    # Schedule weekly
                    days = {
                        '0': schedule.every().sunday,
                        '1': schedule.every().monday,
                        '2': schedule.every().tuesday,
                        '3': schedule.every().wednesday,
                        '4': schedule.every().thursday,
                        '5': schedule.every().friday,
                        '6': schedule.every().saturday
                    }
                    
                    if day_of_week in days and hour != '*':
                        days[day_of_week].at(f"{hour.zfill(2)}:00").do(
                            self.scheduled_report_job, schedule_id
                        ).tag(f"report_{schedule_id}")
                        logger.info(f"Scheduled report {schedule_id} to run weekly on day {day_of_week} at {hour.zfill(2)}:00")
                    else:
                        # Fallback to daily at midnight
                        schedule.every().day.at("00:00").do(
                            self.scheduled_report_job, schedule_id
                        ).tag(f"report_{schedule_id}")
                        logger.info(f"Scheduled report {schedule_id} to run daily at midnight (cron fallback)")
                elif day != '*':
                    # Schedule monthly
                    if hour != '*':
                        # Run at specific hour on the specified day of month
                        schedule.every().day.at(f"{hour.zfill(2)}:00").do(
                            self._check_day_of_month, day, schedule_id
                        ).tag(f"report_{schedule_id}")
                        logger.info(f"Scheduled report {schedule_id} to run monthly on day {day} at {hour.zfill(2)}:00")
                    else:
                        # Run at midnight on the specified day of month
                        schedule.every().day.at("00:00").do(
                            self._check_day_of_month, day, schedule_id
                        ).tag(f"report_{schedule_id}")
                        logger.info(f"Scheduled report {schedule_id} to run monthly on day {day} at midnight")
                else:
                    # Daily at midnight fallback
                    schedule.every().day.at("00:00").do(
                        self.scheduled_report_job, schedule_id
                    ).tag(f"report_{schedule_id}")
                    logger.info(f"Scheduled report {schedule_id} to run daily at midnight (cron fallback)")
            
            return True
            
        except Exception as e:
            logger.error(f"Error scheduling report job: {str(e)}", exc_info=True)
            return False

    def _check_day_of_month(self, target_day, schedule_id):
        """Helper to check if today is the target day of month before running job"""
        # Always use timezone-aware datetime with self.tz from app.CACHE_TIMEZONE
        now = datetime.now(self.tz)
        if str(now.day) == str(target_day):
            self.scheduled_report_job(schedule_id)

    def get_schedules(self, target_id=None):
        """Get all report schedules"""
        try:
            resolved_target_id = resolve_settings_target_id(target_id)
            with data_lock:
                schedules_query = db.session.query(ReportSchedule)
                if hasattr(ReportSchedule, 'target_id'):
                    if resolved_target_id is None:
                        schedules_query = schedules_query.filter(ReportSchedule.target_id.is_(None))
                    else:
                        schedules_query = schedules_query.filter(ReportSchedule.target_id == int(resolved_target_id))
                schedules = schedules_query.all()
                
                result = []
                for schedule in schedules:
                    recipients = schedule.recipients.split(',') if schedule.recipients else []
                    
                    result.append({
                        'id': schedule.id,
                        'target_id': getattr(schedule, 'target_id', None),
                        'enabled': schedule.enabled,
                        'report_type': schedule.report_type,
                        'cron_expression': schedule.cron_expression,
                        'recipients': recipients,
                        'last_run': schedule.last_run.isoformat() if schedule.last_run else None,
                        'created_at': schedule.created_at.isoformat() if schedule.created_at else None,
                        'updated_at': schedule.updated_at.isoformat() if schedule.updated_at else None
                    })
                
                return result
                
        except Exception as e:
            logger.error(f"Error getting schedules: {str(e)}", exc_info=True)
            return []

    def delete_schedule(self, schedule_id, target_id=None):
        """Delete a report schedule"""
        try:
            resolved_target_id = resolve_settings_target_id(target_id)
            with data_lock:
                schedule_query = db.session.query(ReportSchedule).filter_by(id=schedule_id)
                if hasattr(ReportSchedule, 'target_id'):
                    if resolved_target_id is None:
                        schedule_query = schedule_query.filter(ReportSchedule.target_id.is_(None))
                    else:
                        schedule_query = schedule_query.filter(ReportSchedule.target_id == int(resolved_target_id))
                schedule_obj = schedule_query.first()
                
                if not schedule_obj:
                    logger.error(f"Schedule with ID {schedule_id} not found")
                    return {'success': False, 'error': f"Schedule with ID {schedule_id} not found"}
                
                # Remove from scheduler
                try:
                    schedule.clear(f"report_{schedule_id}")
                    logger.info(f"Cleared schedule job report_{schedule_id}")
                except Exception as e:
                    logger.warning(f"Error clearing schedule: {str(e)}")
                
                # Delete from database
                db.session.delete(schedule_obj)
                db.session.commit()
                
                logger.info(f"Deleted report schedule with ID {schedule_id}")
                return {'success': True}
                
        except Exception as e:
            logger.error(f"Error deleting schedule: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def start_scheduler(self):
        """Start the background scheduler thread"""
        try:
            # Create a daemon thread to run the scheduler
            scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            scheduler_thread.start()
            logger.info("Started report scheduler thread")
            
            # Load and schedule all enabled reports
            with data_lock:
                enabled_schedules = db.session.query(ReportSchedule).filter_by(enabled=True).all()
                
                for schedule_obj in enabled_schedules:
                    if schedule_obj.cron_expression:
                        self._schedule_report_job(schedule_obj.id, schedule_obj.cron_expression)
                
                logger.info(f"Loaded {len(enabled_schedules)} enabled report schedules")
                
        except Exception as e:
            logger.error(f"Error starting scheduler: {str(e)}", exc_info=True)

    def _run_scheduler(self):
        """Run the scheduler loop"""
        logger.info("Scheduler thread started")
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}", exc_info=True)
                time.sleep(5)  # Wait a bit longer after an error

# Initialize the manager
report_manager = ReportManager() 
