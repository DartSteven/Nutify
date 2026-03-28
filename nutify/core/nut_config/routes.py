"""
NUT Configuration Routes.

This module provides Flask routes for managing NUT configuration.
"""

from flask import Blueprint, jsonify, request, redirect, url_for, current_app, send_file, session
from .config import is_nut_configured, check_nut_config_files
from core.settings import (
    INSTANCE_PATH, DB_NAME, NUT_CONF_DIR, UPSC_BIN, UPSC_CMD,
    UPSD_BIN, UPSDRVCTL_BIN, NUT_START_DRIVER_CMD, NUT_START_SERVER_CMD,
    NUT_STOP_DRIVER_CMD, NUT_STOP_SERVER_CMD, NUT_STOP_MONITOR_CMD, NUT_DRIVER_DIR,
    NUT_SCANNER_CMD
)
from core.logger import system_logger as logger
from core.react_frontend import serve_react_index
import os
import datetime
import re
import sys
import subprocess
import time
import shutil
import requests
from stat import S_IRWXU, S_IRWXG, S_IROTH, S_IXOTH
import platform
import tempfile
import os.path
import pytz
import json
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, Boolean, DateTime, Float, Text, ForeignKey, text, inspect
from sqlalchemy.sql import select, func

# Import configuration manager once
from .conf_manager import NUTConfManager
from .nut_scanner_parser import parse_nut_scanner_devices, combined_preview_config
from core.multi_nut.connection import test_target_connection
from core.events.notifier_path import get_ups_notifier_command_path

# Restore original blueprint setup with correct URL prefix
nut_config_bp = Blueprint('nut_config', __name__, url_prefix='/nut_config')

# Path to the timezone file
TIMEZONE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'TimeZone.readme')

# Global session key for collecting setup data
SETUP_DATA_KEY = 'setup_data'


def utc_now() -> datetime.datetime:
    """Return current UTC timestamp as timezone-aware datetime."""
    return datetime.datetime.now(pytz.UTC)


def normalize_monitoring_profile(value):
    """Normalize workspace monitoring profile to single or multi."""
    normalized = str(value or '').strip().lower()
    if normalized == 'multi':
        return 'multi'
    return 'single'


def normalize_target_mode(value):
    """Normalize per-target NUT mode."""
    normalized = str(value or '').strip().lower()
    if normalized in {'standalone', 'netserver', 'netclient'}:
        return normalized
    return 'netclient'


def normalize_db_strategy(value):
    """Normalize per-target storage strategy.

    Shared-only phase:
    setup currently enforces shared DB for all targets.
    """
    return 'shared'


def normalize_shard_granularity(value):
    """Normalize per-target shard granularity."""
    normalized = str(value or '').strip().lower()
    if normalized in {'day', 'month'}:
        return normalized
    return 'month'


def normalize_notify_scope(value):
    """Normalize per-target notify scope."""
    normalized = str(value or '').strip().lower()
    if normalized in {'global', 'mail', 'ntfy', 'webhook', 'none'}:
        return normalized
    return 'global'


def normalize_connection_type(value):
    """Normalize wizard target connection type."""
    normalized = str(value or '').strip().lower()
    if normalized in {'remote_nut', 'local_usb_serial', 'local_network_driver'}:
        return normalized
    return 'remote_nut'


def normalize_multi_topology(value):
    """Normalize wizard multi-monitor topology."""
    normalized = str(value or '').strip().lower()
    if normalized in {'remote_only', 'local_only', 'mixed'}:
        return normalized
    return ''


def coerce_int(value, fallback, minimum, maximum):
    """Coerce integer value within bounds."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, parsed))


def coerce_optional_positive_int(value):
    """Return positive integer or None."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def coerce_optional_coordinate(value, minimum, maximum):
    """Return coordinate float when inside bounds, otherwise None."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < minimum or parsed > maximum:
        return None
    return round(parsed, 8)


def normalize_currency_code(value, fallback='EUR'):
    """Normalize ISO-like currency code."""
    normalized = str(value or '').strip().upper()
    if re.fullmatch(r'[A-Z]{3}', normalized):
        return normalized
    return fallback


def normalize_timezone_name(value, fallback='UTC'):
    """Normalize timezone string with pytz validation."""
    candidate = str(value or '').strip() or fallback
    try:
        pytz.timezone(candidate)
        return candidate
    except Exception:
        return fallback


def compose_location_string(address, city, region, postal_code, country):
    """Build one human-readable location label from structured fields."""
    return ', '.join(
        part for part in [
            str(address or '').strip(),
            str(city or '').strip(),
            str(region or '').strip(),
            str(postal_code or '').strip(),
            str(country or '').strip(),
        ]
        if part
    )


def sanitize_multi_targets(raw_targets):
    """Normalize target payload from setup wizard."""
    if not isinstance(raw_targets, list):
        return []

    targets = []
    for item in raw_targets:
        if not isinstance(item, dict):
            continue

        ups_name = str(item.get('ups_name') or '').strip()
        if not ups_name:
            continue

        connection_type = normalize_connection_type(item.get('connection_type'))
        if 'connection_type' not in item and 'nut_mode' in item:
            legacy_mode = normalize_target_mode(item.get('nut_mode'))
            connection_type = 'remote_nut' if legacy_mode == 'netclient' else 'local_usb_serial'

        host = str(item.get('host') or '').strip()
        if connection_type == 'remote_nut' and not host:
            continue

        monitor_username = str(
            item.get('monitor_username') or item.get('remote_user') or 'monuser'
        ).strip() or 'monuser'
        monitor_password = str(
            item.get('monitor_password') or item.get('remote_password') or 'monpass'
        ).strip() or 'monpass'

        local_driver = str(item.get('local_driver') or item.get('ups_driver') or '').strip()
        local_port = str(item.get('local_port') or item.get('ups_port') or '').strip()
        local_description = str(item.get('local_description') or item.get('ups_desc') or '').strip()
        snmp_version = str(item.get('snmp_version') or 'v1').strip() or 'v1'
        snmp_community = str(item.get('snmp_community') or '').strip()
        usb_vendorid = str(item.get('usb_vendorid') or '').strip()
        usb_productid = str(item.get('usb_productid') or '').strip()
        usb_serial = str(item.get('usb_serial') or '').strip()
        usb_vendor = str(item.get('usb_vendor') or '').strip()
        usb_product = str(item.get('usb_product') or '').strip()
        usb_bus = str(item.get('usb_bus') or '').strip()
        usb_device = str(item.get('usb_device') or '').strip()
        usb_busport = str(item.get('usb_busport') or '').strip()

        if connection_type != 'remote_nut':
            host = '127.0.0.1'
            local_driver = local_driver or ('snmp-ups' if connection_type == 'local_network_driver' else 'usbhid-ups')
            local_port = local_port or ('192.168.1.100' if connection_type == 'local_network_driver' else 'auto')
            monitor_password = monitor_password or 'monpass'

        if connection_type == 'local_network_driver' or 'snmp' in local_driver.lower():
            snmp_community = snmp_community or 'public'
        else:
            snmp_community = ''

        location_enabled = bool(item.get('location_enabled', False))
        location_country = str(item.get('location_country') or '').strip() if location_enabled else ''
        location_region = str(item.get('location_region') or '').strip() if location_enabled else ''
        location_city = str(item.get('location_city') or '').strip() if location_enabled else ''
        location_postal_code = str(item.get('location_postal_code') or '').strip() if location_enabled else ''
        location_address = (
            str(item.get('location_address') or item.get('location') or '').strip()
            if location_enabled
            else ''
        )
        location_latitude = (
            coerce_optional_coordinate(item.get('location_latitude'), -90.0, 90.0)
            if location_enabled
            else None
        )
        location_longitude = (
            coerce_optional_coordinate(item.get('location_longitude'), -180.0, 180.0)
            if location_enabled
            else None
        )
        location = (
            compose_location_string(
                location_address,
                location_city,
                location_region,
                location_postal_code,
                location_country,
            )
            if location_enabled
            else ''
        )
        timezone = normalize_timezone_name(item.get('timezone') or item.get('target_timezone') or 'UTC', fallback='UTC')
        currency = normalize_currency_code(item.get('currency'), fallback='EUR')
        ups_realpower_nominal = coerce_optional_positive_int(
            item.get('ups_realpower_nominal')
        )

        target = {
            'name': str(item.get('name') or '').strip() or f"{ups_name}@{host}",
            'ups_name': ups_name,
            'connection_type': connection_type,
            'host': host,
            'port': coerce_int(item.get('port'), 3493, 1, 65535),
            'nut_mode': normalize_target_mode(item.get('nut_mode')),
            'monitor_username': monitor_username,
            'monitor_password': monitor_password,
            'local_driver': local_driver,
            'local_port': local_port,
            'local_description': local_description or item.get('name') or ups_name,
            'snmp_version': snmp_version,
            'snmp_community': snmp_community,
            'usb_vendorid': usb_vendorid,
            'usb_productid': usb_productid,
            'usb_serial': usb_serial,
            'usb_vendor': usb_vendor,
            'usb_product': usb_product,
            'usb_bus': usb_bus,
            'usb_device': usb_device,
            'usb_busport': usb_busport,
            'timezone': timezone,
            'currency': currency,
            'ups_realpower_nominal': ups_realpower_nominal,
            'enabled': bool(item.get('enabled', True)),
            'is_primary': bool(item.get('is_primary', False)),
            # Shared-only phase (future sharded/separate kept disabled for now).
            'db_strategy': 'shared',
            'shard_granularity': 'month',
            'polling_interval': coerce_int(item.get('polling_interval'), 1, 1, 60),
            'retention_days': coerce_int(item.get('retention_days'), 0, 0, 3650),
            'notify_scope': normalize_notify_scope(item.get('notify_scope')),
            'separate_db_path': '',
            'location_enabled': location_enabled,
            'location': location,
            'location_country': location_country,
            'location_region': location_region,
            'location_city': location_city,
            'location_postal_code': location_postal_code,
            'location_address': location_address,
            'location_latitude': location_latitude,
            'location_longitude': location_longitude,
        }
        if target['connection_type'] == 'remote_nut':
            target['nut_mode'] = 'netclient'
        elif target['nut_mode'] not in {'standalone', 'netserver'}:
            target['nut_mode'] = 'standalone'

        targets.append(target)

    return targets


def validate_targets_for_topology(targets, topology):
    """Validate target connection types against selected topology."""
    normalized_topology = normalize_multi_topology(topology)
    if not normalized_topology or not targets:
        return

    if normalized_topology == 'remote_only':
        if any(target.get('connection_type') != 'remote_nut' for target in targets):
            raise ValueError('Remote-only topology accepts only remote NUT targets')

    if normalized_topology == 'local_only':
        if any(target.get('connection_type') == 'remote_nut' for target in targets):
            raise ValueError('Local-only topology accepts only local driver targets')

def get_timezones():
    """Read the list of timezones from the TimeZone.readme file"""
    timezones = []
    try:
        with open(TIMEZONE_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines, comments, and section headers
                if not line or line.startswith('#') or line.startswith('##'):
                    continue
                timezones.append(line)
        return timezones
    except Exception as e:
        logger.error(f"Error reading timezone file: {str(e)}")
        # Return a default list of common timezones
        return ['Europe/Rome', 'America/New_York', 'Asia/Tokyo', 'Australia/Sydney']

@nut_config_bp.route('/welcome')
def welcome():
    """
    Render the welcome page for initial NUT configuration.
    
    This page is shown when NUT configuration files are missing.
    """
    configured, missing_files = check_nut_config_files()
    
    # If files are now present, redirect to main page
    if configured:
        return redirect(url_for('dashboard_index'))
    
    return serve_react_index()

@nut_config_bp.route('/setup/wizard')
def setup_wizard():
    """
    Render the NUT configuration wizard.
    
    This page guides the user through setting up NUT configuration files.
    """
    configured, missing_files = check_nut_config_files()
    
    # If files are now present, redirect to main page
    if configured:
        return redirect(url_for('dashboard_index'))
    
    return serve_react_index()

@nut_config_bp.route('/api/nut/status', methods=['GET'])
def get_nut_status():
    """
    Get the current NUT configuration status.
    
    Returns:
        JSON: Status of NUT configuration.
    """
    configured, missing_files = check_nut_config_files()
    return jsonify({
        'configured': configured,
        'missing_files': missing_files
    })

@nut_config_bp.route('/api/nut/check', methods=['POST'])
def check_status():
    """
    Force a check of NUT configuration status.
    
    Returns:
        JSON: Updated status of NUT configuration.
    """
    configured, missing_files = check_nut_config_files()
    return jsonify({
        'configured': configured,
        'missing_files': missing_files
    })

@nut_config_bp.route('/api/setup/test-configuration', methods=['POST'])
def test_config():
    """
    Test the NUT configuration.
    
    This endpoint tests the NUT configuration by writing the configuration files
    directly to the NUT configuration directory (/etc/nut) and testing with upsc.
    
    Returns:
        JSON: Test results with status and errors if any.
    """
    try:
        data = request.json
        validation_errors = []
        
        # Check for required files
        required_files = ['nut_conf']
        for file in required_files:
            if file not in data or not data[file]:
                validation_errors.append(f"Missing {file} configuration")
        
        if validation_errors:
            return jsonify({
                'status': 'error',
                'errors': validation_errors
            }), 400
            
        # Use centralized config directory from settings
        config_dir = NUT_CONF_DIR
        
        # Log the request for debugging
        logger.info(f"Received test configuration request. Config directory: {config_dir}")
        
        # Extract NUT mode from config files
        nut_mode = None
        ups_name = "ups"  # Default
        ups_host = "localhost"  # Default
        connection_type = None  # Will hold the connection scenario
        is_remote_nut = False
        
        # Extract NUT mode
        if 'nut_conf' in data and data['nut_conf']:
            mode_match = re.search(r'MODE\s*=\s*(\w+)', data['nut_conf'])
            if mode_match:
                nut_mode = mode_match.group(1)
                logger.info(f"Detected NUT mode: {nut_mode}")
        
        # Determine connection type based on available config files
        if 'upsmon_conf' in data and data['upsmon_conf']:
            remote_monitor_match = re.search(r'MONITOR\s+([^@\s]+)@([^\s]+)\s+\d+', data['upsmon_conf'])
            if remote_monitor_match and (remote_monitor_match.group(2) != "localhost" and remote_monitor_match.group(2) != "127.0.0.1"):
                # This seems to be a remote NUT server configuration
                ups_name = remote_monitor_match.group(1)
                ups_host = remote_monitor_match.group(2)
                is_remote_nut = True
                connection_type = "remote_nut"
                logger.info(f"Detected remote NUT server configuration: {ups_name}@{ups_host}")
        
        # Extract UPS information from ups.conf if available and not already determined to be remote
        if not is_remote_nut and 'ups_conf' in data and data['ups_conf']:
            name_match = re.search(r'\[(.*?)\]', data['ups_conf'])
            if name_match:
                ups_name = name_match.group(1)
                logger.info(f"Detected UPS name from ups.conf: {ups_name}")
            
            # Try to determine if it's a network UPS (SNMP)
            snmp_match = re.search(r'driver\s*=\s*"snmp-ups".*?port\s*=\s*"([^"]*)"', data['ups_conf'], re.DOTALL)
            if snmp_match:
                connection_type = "remote_ups"
                # The port might contain just the IP or IP:port
                snmp_port = snmp_match.group(1)
                if ':' in snmp_port:
                    ups_host = snmp_port.split(':')[0]
                else:
                    ups_host = snmp_port
                logger.info(f"Detected network UPS (SNMP) at {ups_host}")
            elif re.search(r'driver\s*=\s*"usbhid-ups"', data['ups_conf']):
                connection_type = "local_usb"
                logger.info("Detected local USB UPS")
            elif re.search(r'driver\s*=.*?_ser"', data['ups_conf']):
                connection_type = "local_serial"
                logger.info("Detected local Serial UPS")
        
        logger.info(f"Determined configuration - Mode: {nut_mode}, Connection type: {connection_type}, UPS: {ups_name}@{ups_host}")
        
        # Check if directory exists and is writable
        if not os.path.exists(config_dir):
            try:
                os.makedirs(config_dir, mode=0o755, exist_ok=True)
                logger.info(f"Created NUT configuration directory: {config_dir}")
            except Exception as e:
                logger.error(f"Error creating NUT configuration directory: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'message': f"Cannot create NUT configuration directory: {str(e)}"
                }), 500
        else:
            # Check if directory is writable
            if not os.access(config_dir, os.W_OK):
                error_msg = f"Cannot write to NUT configuration directory {config_dir}. Permission denied."
                logger.error(error_msg)
                return jsonify({
                    'status': 'error',
                    'message': error_msg
                }), 403
                
        logger.info(f"Configuration directory {config_dir} exists and is writable")
        
        # Check if configuration contains template variables (like {{UPS_NAME}})
        contains_templates = False
        for file_content in data.values():
            if isinstance(file_content, str) and file_content and re.search(r'\{\{[A-Z_]+\}\}', file_content):
                contains_templates = True
                break
                
        if contains_templates:
            # This is just a preview with template variables, return a simulated success
            logger.info("Configuration contains template variables - returning simulated success for preview")
            return jsonify({
                'status': 'success',
                'message': "Configuration preview looks valid",
                'is_preview': True,
                'upsc_output': "This is a preview only. Actual testing will be performed when the configuration is applied."
            })
            
        def parse_monitor_targets(upsmon_content):
            targets = []
            if not upsmon_content:
                return targets

            monitor_pattern = re.compile(
                r'^\s*MONITOR\s+([^@\s]+)@([^\s:]+)(?::(\d+))?\s+\d+',
                re.IGNORECASE
            )

            for raw_line in upsmon_content.splitlines():
                line = raw_line.split('#', 1)[0].strip()
                if not line:
                    continue
                match = monitor_pattern.match(line)
                if not match:
                    continue
                parsed_ups_name = str(match.group(1) or '').strip()
                parsed_host = str(match.group(2) or '').strip()
                parsed_port = coerce_int(match.group(3), 3493, 1, 65535) if match.group(3) else 3493
                if not parsed_ups_name or not parsed_host:
                    continue
                targets.append({
                    'ups_name': parsed_ups_name,
                    'host': parsed_host,
                    'port': parsed_port,
                    'source': 'upsmon_conf',
                })

            return targets

        def build_targets_to_test():
            candidates = []
            candidates.extend(parse_monitor_targets(data.get('upsmon_conf', '')))

            for target in sanitize_multi_targets(data.get('multi_targets', [])):
                target_ups_name = str(target.get('ups_name') or '').strip()
                target_host = str(target.get('host') or '').strip()
                target_port = coerce_int(target.get('port'), 3493, 1, 65535)
                if not target_ups_name or not target_host:
                    continue
                candidates.append({
                    'ups_name': target_ups_name,
                    'host': target_host,
                    'port': target_port,
                    'source': 'multi_targets',
                })

            if not candidates:
                candidates.append({
                    'ups_name': ups_name,
                    'host': ups_host,
                    'port': 3493,
                    'source': 'fallback',
                })

            seen = set()
            unique_candidates = []
            for candidate in candidates:
                key = (
                    str(candidate.get('ups_name') or '').strip(),
                    str(candidate.get('host') or '').strip(),
                    coerce_int(candidate.get('port'), 3493, 1, 65535),
                )
                if not key[0] or not key[1] or key in seen:
                    continue
                seen.add(key)
                unique_candidates.append({
                    'ups_name': key[0],
                    'host': key[1],
                    'port': key[2],
                    'source': candidate.get('source') or 'unknown',
                })

            return unique_candidates

        def run_upsc_checks(target_candidates):
            failures = []
            summary_lines = []
            detail_blocks = []

            for candidate in target_candidates:
                host_with_port = (
                    candidate['host']
                    if candidate['port'] == 3493
                    else f"{candidate['host']}:{candidate['port']}"
                )
                ups_spec = f"{candidate['ups_name']}@{host_with_port}"
                logger.info(f"Testing UPS target with command: {UPSC_BIN} {ups_spec}")
                result = subprocess.run([UPSC_BIN, ups_spec], capture_output=True, text=True)
                if result.returncode != 0:
                    error_text = (result.stderr or result.stdout or 'Unknown error').strip()
                    failures.append(f"{ups_spec}: {error_text}")
                    summary_lines.append(f"❌ {ups_spec} - {error_text}")
                    continue

                summary_lines.append(f"✅ {ups_spec}")
                output_text = (result.stdout or '').strip()
                detail_blocks.append(
                    f"[{ups_spec}]\n{output_text if output_text else 'Connection successful'}"
                )

            return failures, summary_lines, detail_blocks

        targets_to_test = build_targets_to_test()
        all_remote_targets = bool(targets_to_test) and all(
            target['host'] not in {'localhost', '127.0.0.1'}
            for target in targets_to_test
        )

        # For remote-only scenarios, test directly without touching local NUT services.
        if all_remote_targets:
            logger.info(f"Testing remote NUT targets directly: {len(targets_to_test)} target(s)")
            failures, _, detail_blocks = run_upsc_checks(targets_to_test)
            if failures:
                logger.error(f"Remote NUT target validation failed: {failures}")
                return jsonify({
                    'status': 'error',
                    'errors': ['One or more remote targets failed validation:'] + failures
                }), 400

            return jsonify({
                'status': 'success',
                'message': f"Successfully connected to {len(targets_to_test)} remote NUT target(s).",
                'test_details': '\n\n'.join(detail_blocks),
            })
        
        # For local configurations, write files and start services
        backup_files = {}
        try:
            # Create backup of existing files
            for filename in ['nut.conf', 'ups.conf', 'upsd.conf', 'upsd.users', 'upsmon.conf']:
                file_path = os.path.join(config_dir, filename)
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r') as f:
                            backup_files[filename] = f.read()
                        logger.info(f"Created backup of {filename}")
                    except Exception as e:
                        logger.warning(f"Could not backup {filename}: {str(e)}")
            
            # Write configuration files
            for filename, key in [
                ('nut.conf', 'nut_conf'), 
                ('ups.conf', 'ups_conf'), 
                ('upsd.conf', 'upsd_conf'),
                ('upsd.users', 'upsd_users'), 
                ('upsmon.conf', 'upsmon_conf')
            ]:
                if key in data and data[key]:
                    file_path = os.path.join(config_dir, filename)
                    content = data[key]
                    if filename == 'upsmon.conf':
                        content = enforce_upsmon_notifycmd(content)
                        content = normalize_upsmon_conf_content(content)
                    with open(file_path, 'w') as f:
                        f.write(content)
                    # Set proper permissions
                    os.chmod(file_path, S_IRWXU | S_IRWXG | S_IROTH | S_IXOTH)  # 0775
                    logger.info(f"Wrote {filename} to {file_path}")
            
            # Stop any running services first
            try:
                subprocess.run(["pkill", "-9", "upsd"], stderr=subprocess.PIPE)
                subprocess.run([UPSDRVCTL_BIN, "stop"], stderr=subprocess.PIPE)
                logger.info("Stopped any running NUT services")
                time.sleep(2)  # Wait for services to stop completely
            except Exception as e:
                logger.warning(f"Error stopping NUT services: {str(e)}")
            
            # Start services in correct order
            logger.info("Starting NUT driver controller")
            # Parse the NUT_START_DRIVER_CMD to get the arguments
            driver_cmd_parts = NUT_START_DRIVER_CMD.split()
            # Make sure we use the correct binary path
            driver_args = driver_cmd_parts[1:] if len(driver_cmd_parts) > 1 else ["-u", "root", "start"]
            driver_result = subprocess.run([UPSDRVCTL_BIN] + driver_args, 
                                          capture_output=True, text=True)
            
            if driver_result.returncode != 0:
                logger.error(f"Failed to start NUT drivers: {driver_result.stderr}")
                # Restore files and return error
                restore_backup_files(backup_files, config_dir)
                return jsonify({
                    'status': 'error',
                    'errors': [f"Failed to start NUT drivers: {driver_result.stderr}"]
                }), 400
            
            logger.info("Starting NUT server (upsd)")
            # Parse the NUT_START_SERVER_CMD to get the arguments
            server_cmd_parts = NUT_START_SERVER_CMD.split()
            # Make sure we use the correct binary path
            server_args = server_cmd_parts[1:] if len(server_cmd_parts) > 1 else ["-u", "root"]
            upsd_result = subprocess.run([UPSD_BIN] + server_args, 
                                         capture_output=True, text=True)
            
            if upsd_result.returncode != 0:
                logger.error(f"Failed to start NUT server: {upsd_result.stderr}")
                # Stop drivers, restore files, and return error
                subprocess.run([UPSDRVCTL_BIN, "stop"], stderr=subprocess.PIPE)
                restore_backup_files(backup_files, config_dir)
                return jsonify({
                    'status': 'error',
                    'errors': [f"Failed to start NUT server: {upsd_result.stderr}"]
                }), 400
            
            # Wait for services to be fully operational
            time.sleep(3)
            
            # Test all target(s) with upsc
            failures, summary_lines, detail_blocks = run_upsc_checks(targets_to_test)

            if failures:
                logger.error(f"Failed to connect to one or more UPS targets: {failures}")
                # Stop services, restore files, and return error
                # Parse the NUT_STOP_SERVER_CMD to get the arguments
                stop_server_cmd_parts = NUT_STOP_SERVER_CMD.split()
                # Make sure we use the correct binary path with arguments
                if len(stop_server_cmd_parts) > 1:
                    stop_server_args = stop_server_cmd_parts[1:]
                    subprocess.run([UPSD_BIN] + stop_server_args, stderr=subprocess.PIPE)
                else:
                    subprocess.run([UPSD_BIN, "-c", "stop"], stderr=subprocess.PIPE)
                
                subprocess.run([UPSDRVCTL_BIN, "stop"], stderr=subprocess.PIPE)
                restore_backup_files(backup_files, config_dir)

                return jsonify({
                    'status': 'error',
                    'errors': ['One or more targets failed validation:'] + failures,
                    'command_output': '\n'.join(summary_lines),
                }), 400
            
            # Test passed - LEAVE the files but stop the services for now
            # (They will be properly started when the user saves the configuration)
            # Parse the NUT_STOP_SERVER_CMD to get the arguments
            stop_server_cmd_parts = NUT_STOP_SERVER_CMD.split()
            # Make sure we use the correct binary path with arguments
            if len(stop_server_cmd_parts) > 1:
                stop_server_args = stop_server_cmd_parts[1:]
                subprocess.run([UPSD_BIN] + stop_server_args, stderr=subprocess.PIPE)
            else:
                subprocess.run([UPSD_BIN, "-c", "stop"], stderr=subprocess.PIPE)
            
            subprocess.run([UPSDRVCTL_BIN, "stop"], stderr=subprocess.PIPE)
            
            logger.info("NUT configuration test completed successfully")
            return jsonify({
                'status': 'success',
                'message': f"Successfully connected to {len(targets_to_test)} UPS target(s).",
                'test_details': '\n\n'.join(detail_blocks),
            })
            
        except Exception as e:
            logger.error(f"Exception during NUT service testing: {str(e)}", exc_info=True)
            # Stop services and restore files
            try:
                # Parse the NUT_STOP_SERVER_CMD to get the arguments
                stop_server_cmd_parts = NUT_STOP_SERVER_CMD.split()
                # Make sure we use the correct binary path with arguments
                if len(stop_server_cmd_parts) > 1:
                    stop_server_args = stop_server_cmd_parts[1:]
                    subprocess.run([UPSD_BIN] + stop_server_args, stderr=subprocess.PIPE)
                else:
                    subprocess.run([UPSD_BIN, "-c", "stop"], stderr=subprocess.PIPE)
                
                subprocess.run([UPSDRVCTL_BIN, "stop"], stderr=subprocess.PIPE)
                restore_backup_files(backup_files, config_dir)
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {str(cleanup_error)}")
            
            return jsonify({
                'status': 'error',
                'errors': [f"Error testing NUT configuration: {str(e)}"],
                'exception': str(e)
            }), 500
            
    except Exception as e:
        logger.error(f"Error in test_config: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'errors': [f"Unexpected error: {str(e)}"],
            'exception': str(e)
        }), 500


@nut_config_bp.route('/api/setup/test-target', methods=['POST'])
def test_setup_target():
    """Test one setup wizard target before allowing add/update in fleet list."""
    try:
        payload = request.get_json(silent=True) or {}
        targets = sanitize_multi_targets([payload])
        if not targets:
            return jsonify({
                'success': False,
                'message': 'Invalid target payload. Please fill all required fields.',
                'metrics': {},
            }), 400

        target = targets[0]
        connection_type = target.get('connection_type')
        manual_nominal = coerce_optional_positive_int(payload.get('ups_realpower_nominal'))

        def with_nominal_metadata(response_payload, raw_payload=None):
            raw_values = raw_payload if isinstance(raw_payload, dict) else {}
            inspected_upsc = bool(raw_values)
            nominal_value = None
            source_key = None
            for candidate in ('ups.realpower.nominal', 'ups_realpower_nominal'):
                if candidate in raw_values and str(raw_values.get(candidate) or '').strip():
                    nominal_value = raw_values.get(candidate)
                    source_key = candidate
                    break
            if nominal_value is None and manual_nominal is not None:
                nominal_value = manual_nominal
                source_key = 'manual_input'

            nominal_found = nominal_value is not None
            response_payload['nominal_power'] = {
                'found': nominal_found,
                'value': nominal_value,
                'source': source_key,
                'requires_manual_input': bool(inspected_upsc and not nominal_found),
                'inspected_upsc': inspected_upsc,
            }
            return response_payload

        if connection_type == 'remote_nut':
            result = test_target_connection({
                'ups_name': target.get('ups_name'),
                'host': target.get('host'),
                'port': target.get('port', 3493),
                'timeout': 10,
                'command_path': UPSC_BIN,
            })
            status_code = 200 if result.get('success') else 400
            if result.get('success'):
                result = with_nominal_metadata(result, raw_payload=result.get('raw'))
            return jsonify(result), status_code

        local_driver = str(target.get('local_driver') or '').strip()
        local_port = str(target.get('local_port') or '').strip()
        if not local_driver or not local_port:
            return jsonify({
                'success': False,
                'message': 'Local target requires driver and port/device.',
                'metrics': {},
            }), 400

        if connection_type == 'local_network_driver' and local_port.lower() == 'auto':
            return jsonify({
                'success': False,
                'message': 'Local network driver target requires an explicit host/IP in Local Driver Port/Device.',
                'metrics': {},
            }), 400

        if 'snmp' in local_driver.lower():
            snmp_community = str(target.get('snmp_community') or '').strip()
            if not snmp_community:
                return jsonify({
                    'success': False,
                    'message': 'SNMP community string is required when using snmp-ups.',
                    'metrics': {},
                }), 400

        driver_validation = 'skipped'
        if NUT_DRIVER_DIR and os.path.isdir(NUT_DRIVER_DIR):
            driver_validation = 'passed' if os.path.exists(os.path.join(NUT_DRIVER_DIR, local_driver)) else 'failed'
            if driver_validation == 'failed':
                return jsonify({
                    'success': False,
                    'message': f"Driver '{local_driver}' was not found in {NUT_DRIVER_DIR}.",
                    'metrics': {},
                }), 400

        return jsonify(with_nominal_metadata({
            'success': True,
            'message': 'Local target validation successful.',
            'metrics': {
                'connection_type': connection_type,
                'local_driver': local_driver,
                'local_port': local_port,
                'driver_validation': driver_validation,
            },
        }))
    except Exception as exc:
        logger.error(f"Error testing setup target: {exc}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error testing target: {str(exc)}',
            'metrics': {},
        }), 500


@nut_config_bp.route('/api/setup/validate-location', methods=['POST'])
def validate_setup_location():
    """Validate structured location from wizard and return geocoded match if available."""
    try:
        payload = request.get_json(silent=True) or {}
        location_country = str(payload.get('location_country') or '').strip()
        location_region = str(payload.get('location_region') or '').strip()
        location_city = str(payload.get('location_city') or '').strip()
        location_postal_code = str(payload.get('location_postal_code') or '').strip()
        location_address = str(payload.get('location_address') or '').strip()
        computed_location = str(payload.get('location') or '').strip()

        query = computed_location or compose_location_string(
            location_address,
            location_city,
            location_region,
            location_postal_code,
            location_country,
        )
        query = query.strip()
        if not query:
            return jsonify({
                'success': False,
                'found': False,
                'message': 'Location query is empty.',
            }), 400

        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={
                'format': 'jsonv2',
                'limit': 1,
                'addressdetails': 1,
                'q': query,
            },
            headers={
                'Accept': 'application/json',
                'User-Agent': 'Nutify/0.2.0 (location-validation)',
            },
            timeout=6,
        )
        response.raise_for_status()

        candidates = response.json() if response.content else []
        if not isinstance(candidates, list) or not candidates:
            return jsonify({
                'success': True,
                'found': False,
                'message': 'Location not found in geocoding service.',
                'validated_query': query,
            })

        first = candidates[0] if isinstance(candidates[0], dict) else {}
        latitude = coerce_optional_coordinate(first.get('lat'), -90.0, 90.0)
        longitude = coerce_optional_coordinate(first.get('lon'), -180.0, 180.0)

        return jsonify({
            'success': True,
            'found': bool(latitude is not None and longitude is not None),
            'message': 'Location validated successfully.',
            'validated_query': query,
            'normalized_location': {
                'location': query,
                'location_country': location_country,
                'location_region': location_region,
                'location_city': location_city,
                'location_postal_code': location_postal_code,
                'location_address': location_address,
                'location_latitude': latitude,
                'location_longitude': longitude,
            },
            'match': {
                'display_name': str(first.get('display_name') or query),
                'latitude': latitude,
                'longitude': longitude,
            },
        })
    except Exception as exc:
        logger.warning(f"Location validation unavailable: {exc}")
        return jsonify({
            'success': False,
            'found': False,
            'validation_unavailable': True,
            'message': f'Location validation unavailable: {str(exc)}',
        }), 200


@nut_config_bp.route('/api/setup/location-suggestions', methods=['POST'])
def location_suggestions():
    """Return address suggestions for wizard location autocomplete."""
    try:
        payload = request.get_json(silent=True) or {}
        query = str(payload.get('query') or '').strip()
        if not query:
            query = compose_location_string(
                str(payload.get('location_address') or '').strip(),
                str(payload.get('location_city') or '').strip(),
                str(payload.get('location_region') or '').strip(),
                str(payload.get('location_postal_code') or '').strip(),
                str(payload.get('location_country') or '').strip(),
            )
        query = query.strip()
        if len(query) < 3:
            return jsonify({
                'success': True,
                'suggestions': [],
                'query': query,
                'message': 'Type at least 3 characters to get location suggestions.',
            })

        limit = coerce_int(payload.get('limit'), 6, 1, 10)
        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={
                'format': 'jsonv2',
                'limit': limit,
                'addressdetails': 1,
                'q': query,
            },
            headers={
                'Accept': 'application/json',
                'User-Agent': 'Nutify/0.2.0 (location-suggestions)',
            },
            timeout=6,
        )
        response.raise_for_status()

        raw_items = response.json() if response.content else []
        if not isinstance(raw_items, list):
            raw_items = []

        suggestions = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue

            address = item.get('address') if isinstance(item.get('address'), dict) else {}
            country = str(address.get('country') or '').strip()
            region = str(
                address.get('state')
                or address.get('region')
                or address.get('county')
                or address.get('state_district')
                or ''
            ).strip()
            city = str(
                address.get('city')
                or address.get('town')
                or address.get('village')
                or address.get('municipality')
                or address.get('hamlet')
                or ''
            ).strip()
            postal_code = str(address.get('postcode') or '').strip()

            road = str(address.get('road') or '').strip()
            house_number = str(address.get('house_number') or '').strip()
            location_address = ' '.join(part for part in [road, house_number] if part).strip()
            if not location_address:
                location_address = str(
                    address.get('house')
                    or address.get('building')
                    or address.get('neighbourhood')
                    or ''
                ).strip()

            latitude = coerce_optional_coordinate(item.get('lat'), -90.0, 90.0)
            longitude = coerce_optional_coordinate(item.get('lon'), -180.0, 180.0)
            location = compose_location_string(
                location_address,
                city,
                region,
                postal_code,
                country,
            ) or str(item.get('display_name') or '').strip()

            suggestions.append({
                'display_name': str(item.get('display_name') or location or query),
                'location': location,
                'location_country': country,
                'location_region': region,
                'location_city': city,
                'location_postal_code': postal_code,
                'location_address': location_address,
                'location_latitude': latitude,
                'location_longitude': longitude,
            })

        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'query': query,
        })
    except Exception as exc:
        logger.warning(f"Location suggestions unavailable: {exc}")
        return jsonify({
            'success': False,
            'suggestions': [],
            'validation_unavailable': True,
            'message': f'Location suggestions unavailable: {str(exc)}',
        }), 200


def restore_backup_files(backup_files, config_dir):
    """Restore backup files to their original location"""
    for filename, content in backup_files.items():
        file_path = os.path.join(config_dir, filename)
        try:
            with open(file_path, 'w') as f:
                f.write(content)
            logger.info(f"Restored backup for {filename}")
        except Exception as e:
            logger.error(f"Failed to restore backup for {filename}: {str(e)}")


def save_multi_nut_targets(engine, metadata, data, nut_mode, command_path, current_timestamp, raw_targets):
    """Persist Multi-NUT targets from setup wizard."""
    monitor_targets = Table(
        'ups_monitor_targets',
        metadata,
        Column('id', Integer, primary_key=True),
        Column('name', String(120), nullable=False, unique=True),
        Column('ups_name', String(120), nullable=False),
        Column('host', String(255), nullable=False),
        Column('port', Integer, nullable=False, default=3493),
        Column('nut_mode', String(20), nullable=False, default='netclient'),
        Column('command_path', String(255), nullable=False),
        Column('source', String(30), nullable=False, default='wizard'),
        Column('enabled', Boolean, nullable=False, default=True),
        Column('is_primary', Boolean, nullable=False, default=False),
        Column('location_enabled', Boolean, nullable=False, default=False),
        Column('location', String(255), nullable=False, default=''),
        Column('location_country', String(120), nullable=False, default=''),
        Column('location_region', String(120), nullable=False, default=''),
        Column('location_city', String(120), nullable=False, default=''),
        Column('location_postal_code', String(40), nullable=False, default=''),
        Column('location_address', String(255), nullable=False, default=''),
        Column('location_latitude', Float, nullable=True),
        Column('location_longitude', Float, nullable=True),
        Column('last_test_status', Boolean, nullable=True),
        Column('last_test_error', Text, nullable=True),
        Column('created_at', DateTime(timezone=True), default=utc_now),
        Column('updated_at', DateTime(timezone=True), default=utc_now, onupdate=utc_now),
    )
    monitor_policies = Table(
        'ups_monitor_policies',
        metadata,
        Column('id', Integer, primary_key=True),
        Column('target_id', Integer, ForeignKey('ups_monitor_targets.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
        Column('db_strategy', String(20), nullable=False, default='shared'),
        Column('shard_granularity', String(10), nullable=False, default='month'),
        Column('separate_db_path', String(255), nullable=True),
        Column('polling_interval', Integer, nullable=False, default=5),
        Column('retention_days', Integer, nullable=False, default=0),
        Column('notify_scope', String(20), nullable=False, default='global'),
        Column('last_polled_at', DateTime(timezone=True), nullable=True),
        Column('last_success_at', DateTime(timezone=True), nullable=True),
        Column('last_error', Text, nullable=True),
        Column('created_at', DateTime(timezone=True), default=utc_now),
        Column('updated_at', DateTime(timezone=True), default=utc_now, onupdate=utc_now),
    )

    monitor_targets.create(engine, checkfirst=True)
    monitor_policies.create(engine, checkfirst=True)

    inspector = inspect(engine)
    target_columns = {column['name'] for column in inspector.get_columns('ups_monitor_targets')}
    with engine.begin() as conn:
        if 'location_enabled' not in target_columns:
            logger.info("Adding missing location_enabled column to ups_monitor_targets")
            conn.execute(
                text(
                    "ALTER TABLE ups_monitor_targets "
                    "ADD COLUMN location_enabled BOOLEAN NOT NULL DEFAULT 0"
                )
            )
        if 'location' not in target_columns:
            logger.info("Adding missing location column to ups_monitor_targets")
            conn.execute(
                text(
                    "ALTER TABLE ups_monitor_targets "
                    "ADD COLUMN location VARCHAR(255) NOT NULL DEFAULT ''"
                )
            )
        if 'location_country' not in target_columns:
            logger.info("Adding missing location_country column to ups_monitor_targets")
            conn.execute(
                text(
                    "ALTER TABLE ups_monitor_targets "
                    "ADD COLUMN location_country VARCHAR(120) NOT NULL DEFAULT ''"
                )
            )
        if 'location_region' not in target_columns:
            logger.info("Adding missing location_region column to ups_monitor_targets")
            conn.execute(
                text(
                    "ALTER TABLE ups_monitor_targets "
                    "ADD COLUMN location_region VARCHAR(120) NOT NULL DEFAULT ''"
                )
            )
        if 'location_city' not in target_columns:
            logger.info("Adding missing location_city column to ups_monitor_targets")
            conn.execute(
                text(
                    "ALTER TABLE ups_monitor_targets "
                    "ADD COLUMN location_city VARCHAR(120) NOT NULL DEFAULT ''"
                )
            )
        if 'location_postal_code' not in target_columns:
            logger.info("Adding missing location_postal_code column to ups_monitor_targets")
            conn.execute(
                text(
                    "ALTER TABLE ups_monitor_targets "
                    "ADD COLUMN location_postal_code VARCHAR(40) NOT NULL DEFAULT ''"
                )
            )
        if 'location_address' not in target_columns:
            logger.info("Adding missing location_address column to ups_monitor_targets")
            conn.execute(
                text(
                    "ALTER TABLE ups_monitor_targets "
                    "ADD COLUMN location_address VARCHAR(255) NOT NULL DEFAULT ''"
                )
            )
        if 'location_latitude' not in target_columns:
            logger.info("Adding missing location_latitude column to ups_monitor_targets")
            conn.execute(
                text(
                    "ALTER TABLE ups_monitor_targets "
                    "ADD COLUMN location_latitude FLOAT"
                )
            )
        if 'location_longitude' not in target_columns:
            logger.info("Adding missing location_longitude column to ups_monitor_targets")
            conn.execute(
                text(
                    "ALTER TABLE ups_monitor_targets "
                    "ADD COLUMN location_longitude FLOAT"
                )
            )

    primary_ups_name = str(data.get('ups_name') or data.get('remote_ups_name') or 'ups').strip() or 'ups'
    primary_host = str(
        data.get('ups_host') or data.get('remote_host') or data.get('server_address') or '127.0.0.1'
    ).strip() or '127.0.0.1'
    primary_port = 3493
    if normalize_target_mode(nut_mode) == 'netclient':
        primary_port = coerce_int(data.get('remote_port'), 3493, 1, 65535)
    elif normalize_target_mode(nut_mode) == 'netserver':
        primary_port = coerce_int(data.get('listen_port'), 3493, 1, 65535)
    primary_name = str(
        data.get('target_display_name') or data.get('name') or data.get('server_name') or primary_ups_name or 'Primary UPS'
    ).strip() or primary_ups_name or 'Primary UPS'

    targets = sanitize_multi_targets(raw_targets)
    primary_policy = {
        'db_strategy': 'shared',
        'shard_granularity': 'month',
        'separate_db_path': None,
        'polling_interval': coerce_int(data.get('polling_interval'), 1, 1, 60),
        'retention_days': 0,
        'notify_scope': 'global',
    }
    primary_timezone = normalize_timezone_name(data.get('timezone') or 'UTC', fallback='UTC')
    primary_currency = normalize_currency_code(data.get('currency'), fallback='EUR')
    primary_nominal = coerce_optional_positive_int(data.get('ups_realpower_nominal'))
    primary_location_enabled = bool(data.get('location_enabled', False))
    primary_location_country = str(data.get('location_country') or '').strip() if primary_location_enabled else ''
    primary_location_region = str(data.get('location_region') or '').strip() if primary_location_enabled else ''
    primary_location_city = str(data.get('location_city') or '').strip() if primary_location_enabled else ''
    primary_location_postal_code = str(data.get('location_postal_code') or '').strip() if primary_location_enabled else ''
    primary_location_address = (
        str(data.get('location_address') or data.get('location') or '').strip()
        if primary_location_enabled
        else ''
    )
    primary_location_latitude = (
        coerce_optional_coordinate(data.get('location_latitude'), -90.0, 90.0)
        if primary_location_enabled
        else None
    )
    primary_location_longitude = (
        coerce_optional_coordinate(data.get('location_longitude'), -180.0, 180.0)
        if primary_location_enabled
        else None
    )
    primary_location = (
        compose_location_string(
            primary_location_address,
            primary_location_city,
            primary_location_region,
            primary_location_postal_code,
            primary_location_country,
        )
        if primary_location_enabled
        else ''
    )

    # Prefer the primary target from wizard payload when available.
    if targets:
        preferred_primary = next((target for target in targets if target.get('is_primary')), targets[0])
        preferred_ups_name = str(preferred_primary.get('ups_name') or '').strip()
        preferred_host = str(preferred_primary.get('host') or '').strip()
        if preferred_ups_name:
            primary_ups_name = preferred_ups_name
        if preferred_host:
            primary_host = preferred_host
        primary_port = coerce_int(preferred_primary.get('port'), primary_port, 1, 65535)
        primary_name = str(preferred_primary.get('name') or primary_name).strip() or primary_name
        primary_policy = {
            # Shared-only phase:
            # Future fields from preferred target can be restored when
            # sharded/separate strategies are re-enabled.
            'db_strategy': 'shared',
            'shard_granularity': 'month',
            'separate_db_path': None,
            'polling_interval': coerce_int(preferred_primary.get('polling_interval'), 1, 1, 60),
            'retention_days': coerce_int(preferred_primary.get('retention_days'), 0, 0, 3650),
            'notify_scope': preferred_primary.get('notify_scope', 'global'),
        }
        primary_timezone = normalize_timezone_name(preferred_primary.get('timezone') or primary_timezone, fallback=primary_timezone)
        primary_currency = normalize_currency_code(preferred_primary.get('currency'), fallback=primary_currency)
        primary_nominal = coerce_optional_positive_int(
            preferred_primary.get('ups_realpower_nominal')
        ) or primary_nominal
        primary_location_enabled = bool(preferred_primary.get('location_enabled', False))
        if primary_location_enabled:
            primary_location_country = str(preferred_primary.get('location_country') or '').strip()
            primary_location_region = str(preferred_primary.get('location_region') or '').strip()
            primary_location_city = str(preferred_primary.get('location_city') or '').strip()
            primary_location_postal_code = str(preferred_primary.get('location_postal_code') or '').strip()
            primary_location_address = str(
                preferred_primary.get('location_address') or preferred_primary.get('location') or ''
            ).strip()
            primary_location = compose_location_string(
                primary_location_address,
                primary_location_city,
                primary_location_region,
                primary_location_postal_code,
                primary_location_country,
            )
            primary_location_latitude = coerce_optional_coordinate(
                preferred_primary.get('location_latitude'),
                -90.0,
                90.0,
            )
            primary_location_longitude = coerce_optional_coordinate(
                preferred_primary.get('location_longitude'),
                -180.0,
                180.0,
            )
        else:
            primary_location = ''

    existing_names = set()

    def next_target_name(base_name):
        candidate = base_name
        suffix = 2
        while candidate.lower() in existing_names:
            candidate = f"{base_name} {suffix}"
            suffix += 1
        existing_names.add(candidate.lower())
        return candidate

    saved_targets = []

    with engine.begin() as conn:
        conn.execute(monitor_policies.delete())
        conn.execute(monitor_targets.delete())

        inserted_count = 0
        primary_insert = monitor_targets.insert().values(
            name=next_target_name(primary_name),
            ups_name=primary_ups_name,
            host=primary_host,
            port=primary_port,
            nut_mode=normalize_target_mode(nut_mode),
            command_path=command_path,
            source='wizard',
            enabled=True,
            is_primary=True,
            location_enabled=primary_location_enabled,
            location=primary_location,
            location_country=primary_location_country,
            location_region=primary_location_region,
            location_city=primary_location_city,
            location_postal_code=primary_location_postal_code,
            location_address=primary_location_address,
            location_latitude=primary_location_latitude,
            location_longitude=primary_location_longitude,
            last_test_status=None,
            last_test_error=None,
            created_at=current_timestamp,
            updated_at=current_timestamp,
        )
        primary_id = conn.execute(primary_insert).inserted_primary_key[0]
        inserted_count += 1
        saved_targets.append(
            {
                'id': primary_id,
                'is_primary': True,
                'timezone': primary_timezone,
                'currency': primary_currency,
                'polling_interval': primary_policy['polling_interval'],
                'ups_realpower_nominal': primary_nominal,
            }
        )
        conn.execute(
            monitor_policies.insert().values(
                target_id=primary_id,
                db_strategy=primary_policy['db_strategy'],
                shard_granularity=primary_policy['shard_granularity'],
                separate_db_path=primary_policy['separate_db_path'],
                polling_interval=primary_policy['polling_interval'],
                retention_days=primary_policy['retention_days'],
                notify_scope=primary_policy['notify_scope'],
                created_at=current_timestamp,
                updated_at=current_timestamp,
            )
        )

        desired_primary_id = primary_id
        for target in targets:
            connection_type = str(target.get('connection_type') or 'remote_nut')
            target_source = 'wizard_remote' if connection_type == 'remote_nut' else 'wizard_local'
            target_mode = 'netclient' if connection_type == 'remote_nut' else normalize_target_mode(nut_mode)
            target_host = str(target.get('host') or '').strip() or '127.0.0.1'
            target_port = coerce_int(target.get('port'), 3493, 1, 65535)
            if connection_type != 'remote_nut':
                target_host = '127.0.0.1'
                target_port = 3493

            if (
                target['ups_name'] == primary_ups_name and
                target_host == primary_host and
                target_port == primary_port
            ):
                continue

            target_insert = monitor_targets.insert().values(
                name=next_target_name(target['name']),
                ups_name=target['ups_name'],
                host=target_host,
                port=target_port,
                nut_mode=target_mode,
                command_path=command_path,
                source=target_source,
                enabled=target['enabled'],
                is_primary=target['is_primary'],
                location_enabled=bool(target.get('location_enabled', False)),
                location=str(target.get('location') or '').strip() if target.get('location_enabled') else '',
                location_country=str(target.get('location_country') or '').strip() if target.get('location_enabled') else '',
                location_region=str(target.get('location_region') or '').strip() if target.get('location_enabled') else '',
                location_city=str(target.get('location_city') or '').strip() if target.get('location_enabled') else '',
                location_postal_code=str(target.get('location_postal_code') or '').strip() if target.get('location_enabled') else '',
                location_address=str(target.get('location_address') or '').strip() if target.get('location_enabled') else '',
                location_latitude=(
                    coerce_optional_coordinate(target.get('location_latitude'), -90.0, 90.0)
                    if target.get('location_enabled')
                    else None
                ),
                location_longitude=(
                    coerce_optional_coordinate(target.get('location_longitude'), -180.0, 180.0)
                    if target.get('location_enabled')
                    else None
                ),
                last_test_status=None,
                last_test_error=None,
                created_at=current_timestamp,
                updated_at=current_timestamp,
            )
            target_id = conn.execute(target_insert).inserted_primary_key[0]
            inserted_count += 1
            saved_targets.append(
                {
                    'id': target_id,
                    'is_primary': bool(target.get('is_primary', False)),
                    'timezone': normalize_timezone_name(target.get('timezone') or primary_timezone, fallback=primary_timezone),
                    'currency': normalize_currency_code(target.get('currency'), fallback=primary_currency),
                    'polling_interval': target['polling_interval'],
                    'ups_realpower_nominal': coerce_optional_positive_int(target.get('ups_realpower_nominal')),
                }
            )

            separate_db_path = None
            conn.execute(
                monitor_policies.insert().values(
                    target_id=target_id,
                    db_strategy='shared',
                    shard_granularity='month',
                    separate_db_path=separate_db_path,
                    polling_interval=target['polling_interval'],
                    retention_days=target['retention_days'],
                    notify_scope=target['notify_scope'],
                    created_at=current_timestamp,
                    updated_at=current_timestamp,
                )
            )

            if target['is_primary']:
                desired_primary_id = target_id

        conn.execute(monitor_targets.update().values(is_primary=False))
        conn.execute(
            monitor_targets.update()
            .where(monitor_targets.c.id == desired_primary_id)
            .values(is_primary=True)
        )
        for item in saved_targets:
            item['is_primary'] = int(item.get('id')) == int(desired_primary_id)

    logger.info(
        f"Saved Multi-NUT setup targets: total={inserted_count}, primary_target_id={desired_primary_id}"
    )
    return saved_targets


def save_variable_options_from_setup(
    engine,
    metadata,
    current_timestamp,
    *,
    timezone='UTC',
    currency='EUR',
    polling_interval=1,
    ups_realpower_nominal=None,
    target_options=None,
    single_target_id=None,
):
    """Persist target-scoped variable options collected during setup."""
    variable_config = Table(
        'ups_opt_variable_config',
        metadata,
        Column('id', Integer, primary_key=True),
        Column('target_id', Integer, nullable=True, index=True),
        Column('timezone', String(64), nullable=True, default='UTC'),
        Column('ups_realpower_nominal', Integer, nullable=True),
        Column('currency', String(3), nullable=False, default='EUR'),
        Column('price_per_kwh', Float, nullable=False, default=0.25),
        Column('co2_factor', Float, nullable=False, default=0.4),
        Column('polling_interval', Integer, nullable=False, default=1),
        Column('measured_power_metric_key', String(120), nullable=False, default='ups_realpower'),
        Column('load_metric_key', String(120), nullable=False, default='ups_load'),
        Column('nominal_power_metric_key', String(120), nullable=False, default='ups_realpower_nominal'),
        Column('realpower_formula', String(260), nullable=False, default='(load_percent / 100.0) * nominal_power_w'),
        Column('power_calibration_factor', Float, nullable=False, default=1.0),
        Column('energy_formula', String(260), nullable=False, default='power_w * delta_hours'),
        Column('cost_formula', String(260), nullable=False, default='(energy_wh / 1000.0) * price_per_kwh'),
        Column('co2_formula', String(260), nullable=False, default='(energy_wh / 1000.0) * co2_factor'),
        Column('created_at', DateTime(timezone=True), default=utc_now),
        Column('updated_at', DateTime(timezone=True), default=utc_now, onupdate=utc_now),
    )
    variable_config.create(engine, checkfirst=True)

    inspector = inspect(engine)
    existing_columns = {column['name'] for column in inspector.get_columns('ups_opt_variable_config')}
    with engine.begin() as conn:
        if 'timezone' not in existing_columns:
            conn.execute(text("ALTER TABLE ups_opt_variable_config ADD COLUMN timezone VARCHAR(64)"))
        if 'ups_realpower_nominal' not in existing_columns:
            conn.execute(text("ALTER TABLE ups_opt_variable_config ADD COLUMN ups_realpower_nominal INTEGER"))

    default_timezone = normalize_timezone_name(timezone or 'UTC', fallback='UTC')
    default_currency = normalize_currency_code(currency, fallback='EUR')
    default_polling_interval = coerce_int(polling_interval, 1, 1, 60)
    default_nominal = coerce_optional_positive_int(ups_realpower_nominal)

    def _upsert_row(connection, scoped_target_id, row_timezone, row_currency, row_polling_interval, row_nominal):
        if scoped_target_id is None:
            scoped_filter = variable_config.c.target_id.is_(None)
        else:
            scoped_filter = variable_config.c.target_id == int(scoped_target_id)

        existing_row = connection.execute(
            select(variable_config.c.id)
            .where(scoped_filter)
            .order_by(variable_config.c.id.asc())
            .limit(1)
        ).fetchone()

        values = {
            'timezone': normalize_timezone_name(row_timezone or default_timezone, fallback=default_timezone),
            'currency': normalize_currency_code(row_currency, fallback=default_currency),
            'polling_interval': coerce_int(row_polling_interval, default_polling_interval, 1, 60),
            'ups_realpower_nominal': coerce_optional_positive_int(row_nominal),
            'updated_at': current_timestamp,
        }

        if existing_row:
            connection.execute(
                variable_config.update()
                .where(variable_config.c.id == existing_row[0])
                .values(**values)
            )
            return

        insert_values = {
            'target_id': scoped_target_id,
            'timezone': values['timezone'],
            'currency': values['currency'],
            'polling_interval': values['polling_interval'],
            'ups_realpower_nominal': values['ups_realpower_nominal'],
            'price_per_kwh': 0.25,
            'co2_factor': 0.4,
            'measured_power_metric_key': 'ups_realpower',
            'load_metric_key': 'ups_load',
            'nominal_power_metric_key': 'ups_realpower_nominal',
            'realpower_formula': '(load_percent / 100.0) * nominal_power_w',
            'power_calibration_factor': 1.0,
            'energy_formula': 'power_w * delta_hours',
            'cost_formula': '(energy_wh / 1000.0) * price_per_kwh',
            'co2_formula': '(energy_wh / 1000.0) * co2_factor',
            'created_at': current_timestamp,
            'updated_at': current_timestamp,
        }
        connection.execute(variable_config.insert().values(**insert_values))

    with engine.begin() as conn:
        normalized_targets = list(target_options or [])
        target_ids = [int(item.get('id')) for item in normalized_targets if item.get('id') is not None]
        unique_target_ids = sorted(set(target_ids))

        if unique_target_ids:
            conn.execute(
                variable_config.delete()
                .where(variable_config.c.target_id.is_(None))
            )
            conn.execute(
                variable_config.delete()
                .where(variable_config.c.target_id.isnot(None))
                .where(~variable_config.c.target_id.in_(unique_target_ids))
            )
            for item in normalized_targets:
                target_id = item.get('id')
                if target_id is None:
                    continue
                _upsert_row(
                    conn,
                    int(target_id),
                    item.get('timezone') or default_timezone,
                    item.get('currency') or default_currency,
                    item.get('polling_interval') or default_polling_interval,
                    item.get('ups_realpower_nominal'),
                )
            return

        resolved_target_id = None
        if single_target_id is not None:
            try:
                resolved_target_id = int(single_target_id)
            except (TypeError, ValueError):
                resolved_target_id = None

        if resolved_target_id is None:
            inspector = inspect(engine)
            table_names = set(inspector.get_table_names())
            if 'ups_monitor_targets' in table_names:
                try:
                    primary_row = conn.execute(
                        text(
                            "SELECT id FROM ups_monitor_targets "
                            "ORDER BY is_primary DESC, id ASC LIMIT 1"
                        )
                    ).fetchone()
                    if primary_row and primary_row[0] is not None:
                        resolved_target_id = int(primary_row[0])
                except Exception as lookup_error:
                    logger.debug(f"Unable to resolve primary target id while saving setup options: {lookup_error}")

        if resolved_target_id is None or resolved_target_id <= 0:
            resolved_target_id = 1

        conn.execute(
            variable_config.delete()
            .where(variable_config.c.target_id.is_(None))
        )
        conn.execute(
            variable_config.delete()
            .where(variable_config.c.target_id.isnot(None))
            .where(variable_config.c.target_id != resolved_target_id)
        )
        _upsert_row(
            conn,
            resolved_target_id,
            default_timezone,
            default_currency,
            default_polling_interval,
            default_nominal,
        )


def save_master_control_from_setup(
    engine,
    metadata,
    current_timestamp,
    *,
    server_name,
    monitoring_profile,
):
    """Persist setup metadata in nutify_master_control."""
    master_control = Table(
        'nutify_master_control',
        metadata,
        Column('id', Integer, primary_key=True),
        Column('server_name', String(100), nullable=False, default='Nutify'),
        Column('monitoring_profile', String(20), nullable=False, default='single'),
        Column('is_configured', Boolean, nullable=False, default=False),
        Column('created_at', DateTime(timezone=True), default=utc_now),
        Column('updated_at', DateTime(timezone=True), default=utc_now, onupdate=utc_now),
    )
    master_control.create(engine, checkfirst=True)

    inspector = inspect(engine)
    existing_columns = {column['name'] for column in inspector.get_columns('nutify_master_control')}
    with engine.begin() as conn:
        if 'monitoring_profile' not in existing_columns:
            conn.execute(text("ALTER TABLE nutify_master_control ADD COLUMN monitoring_profile VARCHAR(20) DEFAULT 'single'"))
        if 'is_configured' not in existing_columns:
            conn.execute(text("ALTER TABLE nutify_master_control ADD COLUMN is_configured BOOLEAN DEFAULT 0"))

        existing = conn.execute(
            select(master_control.c.id)
            .order_by(master_control.c.id.asc())
            .limit(1)
        ).fetchone()

        values = {
            'server_name': str(server_name or '').strip() or 'Nutify',
            'monitoring_profile': normalize_monitoring_profile(monitoring_profile),
            'is_configured': True,
            'updated_at': current_timestamp,
        }

        if existing:
            existing_id = int(existing[0])
            conn.execute(
                master_control.update()
                .where(master_control.c.id == existing_id)
                .values(**values)
            )
            conn.execute(
                master_control.delete()
                .where(master_control.c.id != existing_id)
            )
            return

        conn.execute(
            master_control.insert().values(
                **values,
                created_at=current_timestamp,
            )
        )


def quote_conf_value(value):
    """Escape and quote configuration value."""
    text_value = str(value or '').replace('"', '\\"')
    return f"\"{text_value}\""


def render_local_ups_section(target):
    """Render one additional local UPS section for ups.conf."""
    ups_name = str(target.get('ups_name') or '').strip()
    driver = str(target.get('local_driver') or '').strip()
    port = str(target.get('local_port') or '').strip()
    description = str(target.get('local_description') or target.get('name') or ups_name).strip()
    snmp_version = str(target.get('snmp_version') or 'v1').strip() or 'v1'
    snmp_community = str(target.get('snmp_community') or '').strip()
    usb_vendorid = str(target.get('usb_vendorid') or '').strip()
    usb_productid = str(target.get('usb_productid') or '').strip()
    usb_serial = str(target.get('usb_serial') or '').strip()
    usb_vendor = str(target.get('usb_vendor') or '').strip()
    usb_product = str(target.get('usb_product') or '').strip()
    usb_bus = str(target.get('usb_bus') or '').strip()
    usb_device = str(target.get('usb_device') or '').strip()
    usb_busport = str(target.get('usb_busport') or '').strip()
    if not ups_name or not driver or not port:
        return ''

    section = (
        f"\n[{ups_name}]\n"
        f"    driver = {quote_conf_value(driver)}\n"
        f"    port = {quote_conf_value(port)}\n"
        f"    desc = {quote_conf_value(description)}\n"
        "    pollinterval = 1\n"
        "    pollfreq = 1\n"
        "    user = nut\n"
        "    group = nut\n"
    )
    if 'snmp' in driver.lower():
        section += f"    snmp_version = {quote_conf_value(snmp_version)}\n"
        section += f"    community = {quote_conf_value(snmp_community or 'public')}\n"
    elif 'usbhid-ups' in driver.lower():
        if usb_vendorid:
            section += f"    vendorid = {quote_conf_value(usb_vendorid)}\n"
        if usb_productid:
            section += f"    productid = {quote_conf_value(usb_productid)}\n"
        if usb_product:
            section += f"    product = {quote_conf_value(usb_product)}\n"
        if usb_serial:
            section += f"    serial = {quote_conf_value(usb_serial)}\n"
        if usb_vendor:
            section += f"    vendor = {quote_conf_value(usb_vendor)}\n"
        # Fallback identity for identical USB UPS devices that do not expose serial.
        # Keep this only when serial is missing to avoid unnecessary fragility.
        if not usb_serial:
            if usb_busport:
                section += f"    busport = {quote_conf_value(usb_busport)}\n"
            else:
                if usb_bus:
                    section += f"    bus = {quote_conf_value(usb_bus)}\n"
                if usb_device:
                    section += f"    device = {quote_conf_value(usb_device)}\n"
    return section


def apply_primary_usb_identity_settings(conf_files, payload):
    """Inject USB identity values in primary ups.conf section when available."""
    driver = str(payload.get('ups_driver') or '').strip().lower()
    if 'usbhid-ups' not in driver:
        return conf_files

    usb_vendorid = str(payload.get('usb_vendorid') or '').strip()
    usb_productid = str(payload.get('usb_productid') or '').strip()
    usb_serial = str(payload.get('usb_serial') or '').strip()
    usb_vendor = str(payload.get('usb_vendor') or '').strip()
    usb_product = str(payload.get('usb_product') or '').strip()
    usb_bus = str(payload.get('usb_bus') or '').strip()
    usb_device = str(payload.get('usb_device') or '').strip()
    usb_busport = str(payload.get('usb_busport') or '').strip()

    if not any((usb_vendorid, usb_productid, usb_serial, usb_vendor, usb_product, usb_bus, usb_device, usb_busport)):
        return conf_files

    updated = dict(conf_files or {})
    ups_conf = str(updated.get('ups.conf') or '')
    if not ups_conf.strip():
        return updated

    def ensure_line(key_name, key_value):
        nonlocal ups_conf
        if not key_value:
            return
        if re.search(rf'^\s*{re.escape(key_name)}\s*=', ups_conf, re.IGNORECASE | re.MULTILINE):
            return
        if not ups_conf.endswith('\n'):
            ups_conf += '\n'
        ups_conf += f"    {key_name} = {quote_conf_value(key_value)}\n"

    ensure_line('vendorid', usb_vendorid)
    ensure_line('productid', usb_productid)
    ensure_line('product', usb_product)
    ensure_line('serial', usb_serial)
    ensure_line('vendor', usb_vendor)
    if not usb_serial:
        ensure_line('busport', usb_busport)
        if not usb_busport:
            ensure_line('bus', usb_bus)
            ensure_line('device', usb_device)

    updated['ups.conf'] = ups_conf
    return updated


def apply_primary_snmp_settings(conf_files, payload):
    """Inject SNMP settings in primary ups.conf section when driver is snmp-ups."""
    driver = str(payload.get('ups_driver') or '').strip().lower()
    if not driver or 'snmp' not in driver:
        return conf_files

    updated = dict(conf_files or {})
    ups_conf = str(updated.get('ups.conf') or '')
    if not ups_conf.strip():
        return updated

    snmp_version = str(payload.get('snmp_version') or 'v1').strip() or 'v1'
    snmp_community = str(payload.get('snmp_community') or 'public').strip() or 'public'

    if not re.search(r'^\s*snmp_version\s*=', ups_conf, re.IGNORECASE | re.MULTILINE):
        if not ups_conf.endswith('\n'):
            ups_conf += '\n'
        ups_conf += f"    snmp_version = {quote_conf_value(snmp_version)}\n"

    if not re.search(r'^\s*community\s*=', ups_conf, re.IGNORECASE | re.MULTILINE):
        if not ups_conf.endswith('\n'):
            ups_conf += '\n'
        ups_conf += f"    community = {quote_conf_value(snmp_community)}\n"

    updated['ups.conf'] = ups_conf
    return updated


def normalize_monitor_credential(value, default_value):
    """Normalize monitor credential and guarantee non-empty value."""
    normalized = str(value or '').strip()
    return normalized or default_value


def normalize_monitor_role(value, default_value='slave'):
    """Normalize monitor role and fallback to slave when invalid."""
    normalized = str(value or '').strip().lower()
    if normalized in {'master', 'slave'}:
        return normalized
    return default_value


def normalize_monitor_line(line, default_username='monuser', default_password='monpass'):
    """Normalize a MONITOR line to modern NUT format."""
    stripped = line.strip()
    if not stripped.startswith('MONITOR') or stripped.startswith('#'):
        return line

    leading_spaces = line[:len(line) - len(line.lstrip())]
    content, inline_comment = stripped, ''
    if '#' in stripped:
        content, inline_comment = stripped.split('#', 1)
        content = content.strip()
        inline_comment = inline_comment.strip()

    parts = content.split()
    if len(parts) < 2:
        return line

    ups_spec = parts[1]
    power_value = '1'
    username = normalize_monitor_credential(default_username, 'monuser')
    password = normalize_monitor_credential(default_password, 'monpass')
    role = 'slave'

    remaining = parts[2:]
    if remaining:
        if remaining[0].isdigit():
            power_value = str(max(1, int(remaining[0])))
            remaining = remaining[1:]

    if len(remaining) == 1:
        token = remaining[0]
        if token.lower() in {'master', 'slave'}:
            role = token.lower()
        else:
            username = normalize_monitor_credential(token, username)
    elif len(remaining) == 2:
        username = normalize_monitor_credential(remaining[0], username)
        if remaining[1].lower() in {'master', 'slave'}:
            role = remaining[1].lower()
        else:
            password = normalize_monitor_credential(remaining[1], password)
    elif len(remaining) >= 3:
        username = normalize_monitor_credential(remaining[0], username)
        password = normalize_monitor_credential(remaining[1], password)
        role = normalize_monitor_role(remaining[2], role)

    normalized = f"{leading_spaces}MONITOR {ups_spec} {power_value} {username} {password} {role}"
    if inline_comment:
        normalized += f"  # {inline_comment}"
    return normalized


def normalize_upsmon_conf_content(content, default_username='monuser', default_password='monpass'):
    """Normalize all MONITOR lines in upsmon.conf content."""
    if not content:
        return content

    lines = content.splitlines()
    normalized_lines = [
        normalize_monitor_line(
            line,
            default_username=default_username,
            default_password=default_password,
        )
        for line in lines
    ]
    normalized_content = '\n'.join(normalized_lines)
    if content.endswith('\n'):
        normalized_content += '\n'
    return normalized_content


def render_monitor_line(ups_name, host, username, password, role):
    """Render one MONITOR line for upsmon.conf."""
    safe_username = normalize_monitor_credential(username, 'monuser')
    safe_password = normalize_monitor_credential(password, 'monpass')
    safe_role = normalize_monitor_role(role, 'slave')
    return f"MONITOR {ups_name}@{host} 1 {safe_username} {safe_password} {safe_role}"


def enforce_upsmon_notifycmd(upsmon_conf_content):
    """Ensure upsmon.conf always points NOTIFYCMD to the active notifier script path."""
    notifycmd_path = get_ups_notifier_command_path()
    notifycmd_line = f"NOTIFYCMD {notifycmd_path}"
    content = str(upsmon_conf_content or "")

    if not content.strip():
        return notifycmd_line + "\n"

    notifycmd_pattern = re.compile(r"(?im)^\s*NOTIFYCMD\s+.+$")
    if notifycmd_pattern.search(content):
        return notifycmd_pattern.sub(notifycmd_line, content)

    shutdowncmd_pattern = re.compile(r"(?im)^\s*SHUTDOWNCMD\s+.+$")
    if shutdowncmd_pattern.search(content):
        return shutdowncmd_pattern.sub(lambda match: f"{match.group(0)}\n{notifycmd_line}", content, count=1)

    suffix = "" if content.endswith("\n") else "\n"
    return content + suffix + notifycmd_line + "\n"


def extend_upsd_users_monitor_permissions(
    upsd_users_content,
    primary_ups_name,
    additional_local_targets,
    monitor_username='monuser',
    monitor_password='monpass',
):
    """Ensure monitor user block contains upsmon permissions for all local UPS names."""
    target_names = []
    primary_name = str(primary_ups_name or '').strip()
    if primary_name:
        target_names.append(primary_name)

    for target in additional_local_targets or []:
        ups_name = str(target.get('ups_name') or '').strip()
        if ups_name and ups_name not in target_names:
            target_names.append(ups_name)

    if not target_names:
        return upsd_users_content

    username = str(monitor_username or '').strip() or 'monuser'
    password = str(monitor_password or '').strip() or 'monpass'
    content = str(upsd_users_content or '')
    normalized_target_lines = [f"    upsmon {ups_name} = master" for ups_name in target_names]

    if not content.strip():
        return (
            f"[{username}]\n"
            f"    password = \"{password}\"\n"
            + "\n".join(normalized_target_lines)
            + "\n"
        )

    block_pattern = re.compile(
        rf'(?ms)^(\s*\[{re.escape(username)}\]\s*\n)(.*?)(?=^\s*\[[^\]]+\]\s*$|\Z)'
    )
    match = block_pattern.search(content)
    if not match:
        suffix = '' if content.endswith('\n') else '\n'
        return (
            content
            + suffix
            + f"\n[{username}]\n"
            + f"    password = \"{password}\"\n"
            + "\n".join(normalized_target_lines)
            + "\n"
        )

    header = match.group(1)
    body = match.group(2) or ''
    existing_target_names = {
        str(item.group(1) or '').strip()
        for item in re.finditer(r'(?im)^\s*upsmon\s+([^\s=]+)\s*=\s*master\s*$', body)
        if str(item.group(1) or '').strip()
    }
    missing_lines = [
        f"    upsmon {ups_name} = master"
        for ups_name in target_names
        if ups_name not in existing_target_names
    ]

    if not missing_lines:
        return content

    body_has_content = bool(body.strip())
    updated_body = body
    if body_has_content and not updated_body.endswith('\n'):
        updated_body += '\n'
    updated_body += "\n".join(missing_lines) + "\n"

    start, end = match.span()
    replacement = header + updated_body
    return content[:start] + replacement + content[end:]


def apply_multi_target_config_extensions(conf_files, nut_mode, data, multi_targets):
    """Apply additional local/remote target configuration to generated files."""
    if not multi_targets:
        return conf_files

    local_targets = [t for t in multi_targets if t.get('connection_type') != 'remote_nut']
    remote_targets = [t for t in multi_targets if t.get('connection_type') == 'remote_nut']

    if nut_mode == 'netclient' and local_targets:
        raise ValueError(
            'Host mode netclient cannot define local UPS drivers. Choose standalone/netserver for local targets.'
        )

    updated = dict(conf_files)
    primary_ups_name = str(data.get('ups_name') or data.get('remote_ups_name') or 'ups').strip() or 'ups'
    primary_host = 'localhost'
    primary_port = 3493
    preferred_primary_target = next((item for item in multi_targets if bool(item.get('is_primary'))), None)
    if preferred_primary_target:
        preferred_primary_ups_name = str(preferred_primary_target.get('ups_name') or '').strip()
        if preferred_primary_ups_name:
            primary_ups_name = preferred_primary_ups_name
        if str(preferred_primary_target.get('connection_type') or '') == 'remote_nut':
            primary_host = str(preferred_primary_target.get('host') or 'localhost').strip() or 'localhost'
            primary_port = coerce_int(preferred_primary_target.get('port'), 3493, 1, 65535)
        else:
            primary_host = 'localhost'
            primary_port = 3493
    elif nut_mode == 'netclient':
        primary_host = str(data.get('remote_host') or 'localhost').strip() or 'localhost'
        primary_port = coerce_int(data.get('remote_port'), 3493, 1, 65535)
    seen_monitors = {f"{primary_ups_name}@{primary_host}:{primary_port}"}

    if local_targets:
        ups_conf = updated.get('ups.conf', '') or ''
        if not ups_conf.strip():
            raise ValueError('ups.conf is required when local targets are configured')

        existing_ups_sections = {
            str(match.group(1) or '').strip()
            for match in re.finditer(r'^\s*\[([^\]]+)\]', ups_conf, re.MULTILINE)
            if str(match.group(1) or '').strip()
        }

        for target in local_targets:
            target_ups_name = str(target.get('ups_name') or '').strip()
            if target_ups_name and target_ups_name in existing_ups_sections:
                if target.get('is_primary'):
                    continue
                raise ValueError(
                    f'Duplicate local UPS identifier "{target_ups_name}" detected. '
                    'Use a unique UPS Identifier (upsc key) for each local target.'
                )
            section = render_local_ups_section(target)
            if section:
                ups_conf += section
                if target_ups_name:
                    existing_ups_sections.add(target_ups_name)
        updated['ups.conf'] = ups_conf

        upsd_users = updated.get('upsd.users', '') or ''
        monitor_username = normalize_monitor_credential(
            data.get('monitor_username') or data.get('remote_user'),
            'monuser',
        )
        monitor_password = normalize_monitor_credential(
            data.get('monitor_password') or data.get('remote_password'),
            'monpass',
        )
        updated['upsd.users'] = extend_upsd_users_monitor_permissions(
            upsd_users,
            primary_ups_name=primary_ups_name,
            additional_local_targets=local_targets,
            monitor_username=monitor_username,
            monitor_password=monitor_password,
        )

    additional_monitor_lines = []
    for target in local_targets:
        ups_name = str(target.get('ups_name') or '').strip()
        if not ups_name or ups_name == primary_ups_name:
            continue
        monitor_key = f"{ups_name}@localhost:3493"
        if monitor_key in seen_monitors:
            continue
        seen_monitors.add(monitor_key)
        additional_monitor_lines.append(
            render_monitor_line(
                ups_name=ups_name,
                host='localhost',
                username='monuser',
                password='monpass',
                role='master',
            )
        )

    default_remote_user = str(data.get('remote_user') or 'monuser').strip() or 'monuser'
    default_remote_password = str(data.get('remote_password') or 'monpass').strip() or 'monpass'
    for target in remote_targets:
        ups_name = str(target.get('ups_name') or '').strip()
        host = str(target.get('host') or '').strip()
        if not ups_name or not host:
            continue
        port = coerce_int(target.get('port'), 3493, 1, 65535)
        monitor_key = f"{ups_name}@{host}:{port}"
        if monitor_key in seen_monitors:
            continue
        seen_monitors.add(monitor_key)
        host_with_port = host if port == 3493 else f"{host}:{port}"
        username = str(target.get('monitor_username') or default_remote_user).strip() or 'monuser'
        password = str(target.get('monitor_password') or default_remote_password).strip() or 'monpass'
        additional_monitor_lines.append(
            render_monitor_line(
                ups_name=ups_name,
                host=host_with_port,
                username=username,
                password=password,
                role='slave',
            )
        )

    if additional_monitor_lines:
        upsmon_conf = updated.get('upsmon.conf', '') or ''
        if not upsmon_conf.strip():
            raise ValueError('upsmon.conf is required for multi-target monitoring')
        upsmon_conf += "\n\n# Additional fleet monitor targets\n" + "\n".join(additional_monitor_lines) + "\n"
        updated['upsmon.conf'] = upsmon_conf

    return updated

@nut_config_bp.route('/api/setup/save-config', methods=['POST'])
def save_config():
    """
    Save NUT configuration to disk and database.
    
    This endpoint takes the configuration data from the wizard,
    generates the configuration files using templates,
    writes them to disk, and stores settings in the database.
    
    Returns:
        JSON: Status and message.
    """
    try:
        data = request.get_json()
        
        # Extract NUT mode and connection scenario from data
        nut_mode = data.get('nut_mode', 'standalone')
        connection_scenario = data.get('connection_scenario', 'local_usb')
        
        # Extract setup data with session fallback for legacy compatibility.
        # Modern setup flow is wizard-first, but we still honor existing session values when present.
        setup_session = session.get(SETUP_DATA_KEY, {}) if isinstance(session.get(SETUP_DATA_KEY), dict) else {}
        requested_server_name = str(data.get('server_name') or '').strip()
        session_server_name = str(setup_session.get('server_name') or '').strip()
        server_name = requested_server_name or session_server_name or 'Nutify'

        requested_timezone = str(data.get('timezone') or '').strip()
        session_timezone = str(setup_session.get('timezone') or '').strip()
        raw_timezone_explicit = data.get('timezone_explicit')
        timezone_explicit = bool(raw_timezone_explicit)
        if isinstance(raw_timezone_explicit, str):
            timezone_explicit = raw_timezone_explicit.strip().lower() in {'1', 'true', 'yes', 'on'}

        if requested_timezone:
            timezone = requested_timezone
            # Guard against frontend fallback payloads forcing UTC when setup session has
            # a real timezone selected in the dedicated timezone step.
            if (
                not timezone_explicit and
                requested_timezone.upper() == 'UTC' and
                session_timezone and
                session_timezone.upper() != 'UTC'
            ):
                timezone = session_timezone
        else:
            timezone = session_timezone or 'UTC'

        try:
            pytz.timezone(timezone)
        except Exception:
            logger.warning(f"Invalid timezone '{timezone}' in setup payload/session. Falling back to UTC.")
            timezone = 'UTC'

        monitoring_profile = normalize_monitoring_profile(
            data.get('monitoring_profile', session.get(SETUP_DATA_KEY, {}).get('monitoring_profile', 'single'))
        )
        multi_topology = normalize_multi_topology(data.get('multi_topology'))
        multi_targets = sanitize_multi_targets(data.get('multi_targets', []))
        if monitoring_profile == 'multi':
            try:
                validate_targets_for_topology(multi_targets, multi_topology)
            except ValueError as topology_error:
                return jsonify({
                    'status': 'error',
                    'message': str(topology_error),
                }), 400
        
        # Extract optional fallback nominal power if provided
        ups_realpower_nominal = coerce_optional_positive_int(data.get('ups_realpower_nominal'))
        
        # Use centralized config directory from settings
        config_dir = NUT_CONF_DIR
        
        # Create a template manager instance
        templates_dir = os.path.join(os.path.dirname(__file__), 'conf_templates')
        conf_manager = NUTConfManager(templates_dir)
        
        # Check for direct config file data
        has_direct_config = 'nut_conf' in data or 'nut.conf' in data

        # If direct config data is provided, keep exactly what the client sent.
        # This path is used by the setup wizard after preview/editor and must not
        # be overwritten by template regeneration.
        if has_direct_config:
            conf_files = {
                'nut.conf': data.get('nut_conf', data.get('nut.conf', '')),
                'ups.conf': data.get('ups_conf', data.get('ups.conf', '')),
                'upsd.conf': data.get('upsd_conf', data.get('upsd.conf', '')),
                'upsd.users': data.get('upsd_users', data.get('upsd.users', '')),
                'upsmon.conf': data.get('upsmon_conf', data.get('upsmon.conf', ''))
            }
            logger.info("Using provided configuration files directly")
        else:
            # Validate the mode
            if not conf_manager.validate_mode(nut_mode):
                return jsonify({
                    'status': 'error',
                    'message': f'Invalid NUT mode: {nut_mode}'
                })

            # Process mode-specific variables
            if nut_mode == 'standalone':
                variables = {
                    'UPS_NAME': conf_manager.clean_variable_name(data.get('ups_name', 'ups')),
                    'DRIVER': conf_manager.clean_variable_name(data.get('ups_driver', 'usbhid-ups')),
                    'PORT': conf_manager.clean_variable_name(data.get('ups_port', 'auto')),
                    'DESCRIPTION': conf_manager.clean_variable_name(data.get('ups_desc', 'Local UPS')),
                    'ADMIN_USERNAME': 'admin',
                    'ADMIN_PASSWORD': 'adminpass',
                    'MONITOR_USERNAME': 'monuser',
                    'MONITOR_PASSWORD': 'monpass',
                    'ADDITIONAL_USERS': '',
                    'UPS_HOST': 'localhost',
                    'SERVER_ADDRESS': conf_manager.clean_variable_name(data.get('server_address', '127.0.0.1'))
                }
            elif nut_mode == 'netserver':
                variables = {
                    'UPS_NAME': conf_manager.clean_variable_name(data.get('ups_name', 'ups')),
                    'DRIVER': conf_manager.clean_variable_name(data.get('ups_driver', 'usbhid-ups')),
                    'PORT': conf_manager.clean_variable_name(data.get('ups_port', 'auto')),
                    'DESCRIPTION': conf_manager.clean_variable_name(data.get('ups_desc', 'Network UPS')),
                    'LISTEN_ADDRESS': conf_manager.clean_variable_name(data.get('listen_address', '0.0.0.0')),
                    'LISTEN_PORT': conf_manager.clean_variable_name(data.get('listen_port', '3493')),
                    'ADMIN_USERNAME': conf_manager.clean_variable_name(data.get('admin_user', 'admin')),
                    'ADMIN_PASSWORD': conf_manager.clean_variable_name(data.get('admin_password', '')),
                    'MONITOR_USERNAME': 'monuser',
                    'MONITOR_PASSWORD': 'monpass',
                    'ADDITIONAL_USERS': '',
                    'UPS_HOST': 'localhost',
                    'SERVER_ADDRESS': conf_manager.clean_variable_name(data.get('server_address', '127.0.0.1'))
                }
            elif nut_mode == 'netclient':
                remote_username = conf_manager.clean_variable_name(data.get('remote_user', 'monuser')) or 'monuser'
                remote_password = conf_manager.clean_variable_name(data.get('remote_password', 'monpass')) or 'monpass'
                variables = {
                    'UPS_NAME': conf_manager.clean_variable_name(data.get('remote_ups_name', 'ups')),
                    'UPS_HOST': conf_manager.clean_variable_name(data.get('remote_host', 'localhost')),
                    'REMOTE_PORT': data.get('remote_port', '3493'),
                    'REMOTE_USERNAME': remote_username,
                    'REMOTE_PASSWORD': remote_password,
                    'MONITOR_USERNAME': remote_username,
                    'MONITOR_PASSWORD': remote_password,
                    'ADDITIONAL_USERS': ''
                }

            # Special handling for remote_nut scenario
            if connection_scenario == 'remote_nut':
                # For remote NUT, use the remote server UPS identity
                variables['UPS_NAME'] = data.get('ups_name', 'ups')
                variables['UPS_HOST'] = data.get('ups_host', 'localhost')
                # Keep template compatibility with REMOTE_USERNAME placeholders
                variables['REMOTE_USERNAME'] = variables['REMOTE_USERNAME'] or variables.get('MONITOR_USERNAME', 'monuser')
                # Force netclient mode
                nut_mode = 'netclient'

            # Process additional users if any
            additional_users = data.get('additional_users', [])
            additional_users_config = ""

            for user in additional_users:
                username = user.get('username', '')
                password = user.get('password', '')
                is_admin = user.get('is_admin', False)

                if username and password:
                    additional_users_config += f"\n[{username}]\n"
                    additional_users_config += f"    password = \"{password}\"\n"

                    if is_admin:
                        additional_users_config += "    actions = SET\n"
                        additional_users_config += "    instcmds = ALL\n"
                    else:
                        additional_users_config += f"    upsmon {variables['UPS_NAME']} = slave\n"

            variables['ADDITIONAL_USERS'] = additional_users_config

            # Handle specific variables for different connection scenarios
            if connection_scenario == 'local_usb':
                # For USB UPS, ensure correct driver and port
                variables['DRIVER'] = data.get('driver') or 'usbhid-ups'
                variables['PORT'] = 'auto'

                # Add vendor/product ID if provided
                vendor_id = data.get('usb_vendorid')
                product_id = data.get('usb_productid')
                if vendor_id:
                    variables['VENDORID'] = vendor_id
                if product_id:
                    variables['PRODUCTID'] = product_id

            elif connection_scenario == 'local_serial':
                # For serial UPS, ensure correct driver and port
                variables['DRIVER'] = data.get('driver') or 'apcsmart'
                variables['PORT'] = data.get('port') or '/dev/ttyS0'

                # Add baud rate if provided
                baud_rate = data.get('serial_baudrate')
                if baud_rate:
                    variables['BAUDRATE'] = baud_rate

            elif connection_scenario == 'remote_ups':
                # For network UPS (SNMP), ensure correct driver and port settings
                variables['DRIVER'] = 'snmp-ups'
                variables['PORT'] = data.get('port') or '127.0.0.1'
                variables['SNMP_VERSION'] = data.get('snmp_version', 'v1')
                variables['SNMP_COMMUNITY'] = data.get('snmp_community', 'public')

            # Generate configuration files using templates
            conf_files = conf_manager.get_conf_files(nut_mode, variables)

            # Special handling for netclient mode with remote_nut scenario
            if nut_mode == 'netclient' and connection_scenario == 'remote_nut':
                # netclient mode does not need local driver/server files
                conf_files['ups.conf'] = ''
                conf_files['upsd.conf'] = ''
                conf_files['upsd.users'] = ''

            # If raw UPS config was provided, use it
            if 'raw_ups_config' in data and data['raw_ups_config'] and connection_scenario in ['local_usb']:
                raw_config = data['raw_ups_config']
                conf_files['ups.conf'] = raw_config

            conf_files = apply_primary_usb_identity_settings(conf_files, data)
            conf_files = apply_primary_snmp_settings(conf_files, data)
        
        # Automatically correct nut_mode only when templates were generated in this request.
        # In direct-config flow the client already provides finalized files.
        if not has_direct_config:
            if connection_scenario == 'remote_nut' and nut_mode != 'netclient':
                nut_mode = 'netclient'
                logger.info(f"Automatically correcting NUT mode to 'netclient' for remote_nut scenario")
            elif connection_scenario in ['local_usb', 'local_serial'] and nut_mode not in ['standalone', 'netserver']:
                # For local connections, mode must be standalone or netserver
                if nut_mode == 'netclient':
                    nut_mode = 'standalone'
                    logger.info(f"Automatically correcting NUT mode to 'standalone' for local UPS scenario")

        if monitoring_profile == 'multi' and multi_targets and not has_direct_config:
            try:
                conf_files = apply_multi_target_config_extensions(
                    conf_files=conf_files,
                    nut_mode=nut_mode,
                    data=data,
                    multi_targets=multi_targets,
                )
            except ValueError as ext_error:
                return jsonify({
                    'status': 'error',
                    'message': str(ext_error),
                }), 400

        default_monitor_username = normalize_monitor_credential(
            data.get('monitor_username') or data.get('remote_user'),
            'monuser',
        )
        default_monitor_password = normalize_monitor_credential(
            data.get('monitor_password') or data.get('remote_password'),
            'monpass',
        )
        conf_files['upsmon.conf'] = enforce_upsmon_notifycmd(conf_files.get('upsmon.conf', ''))
        conf_files['upsmon.conf'] = normalize_upsmon_conf_content(
            conf_files.get('upsmon.conf', ''),
            default_username=default_monitor_username,
            default_password=default_monitor_password,
        )
        
        # Check if directory exists and is writable
        if not os.path.exists(config_dir):
            try:
                os.makedirs(config_dir, mode=0o755, exist_ok=True)
                logger.info(f"Created NUT configuration directory: {config_dir}")
            except Exception as e:
                logger.error(f"Error creating NUT configuration directory: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'message': f"Cannot create NUT configuration directory: {str(e)}"
                }), 500
        else:
            # Check if directory is writable
            if not os.access(config_dir, os.W_OK):
                error_msg = f"Cannot write to NUT configuration directory {config_dir}. Permission denied."
                logger.error(error_msg)
                return jsonify({
                    'status': 'error',
                    'message': error_msg
                }), 403
                
        logger.info(f"Configuration directory {config_dir} exists and is writable")
        
        # Save the configuration files to disk
        saved_files = []
        error_files = []
        
        try:
            # Function to save a configuration file
            def save_file(content, filename):
                if not content:
                    logger.info(f"Skipping empty configuration file: {filename}")
                    return True
                    
                file_path = os.path.join(config_dir, filename)
                try:
                    if filename == 'upsmon.conf':
                        content = enforce_upsmon_notifycmd(content)
                        content = normalize_upsmon_conf_content(content)
                    with open(file_path, 'w') as f:
                        f.write(content)
                    
                    # Set file permissions to ensure NUT can access it
                    os.chmod(file_path, S_IRWXU | S_IRWXG | S_IROTH | S_IXOTH)  # 0775
                    
                    logger.info(f"Saved configuration file: {file_path}")
                    saved_files.append(filename)
                    return True
                except Exception as e:
                    logger.error(f"Error saving configuration file {file_path}: {str(e)}")
                    error_files.append(filename)
                    return False
            
            # Save the configuration files
            for filename, content in conf_files.items():
                save_file(content, filename)
            
            # Check if any files failed
            if error_files:
                return jsonify({
                    'status': 'error',
                    'message': f"Failed to save configuration files: {', '.join(error_files)}"
                })
            
            # Initialize database and save configuration
            try:
                # Ensure the instance directory exists
                os.makedirs(os.path.dirname(os.path.join(INSTANCE_PATH, DB_NAME)), exist_ok=True)

                # Create engine and metadata
                engine = create_engine(f'sqlite:///{os.path.join(INSTANCE_PATH, DB_NAME)}')
                metadata = MetaData()
                current_timestamp = utc_now()

                save_master_control_from_setup(
                    engine=engine,
                    metadata=metadata,
                    current_timestamp=current_timestamp,
                    server_name=server_name,
                    monitoring_profile=monitoring_profile,
                )

                # Create dashboard admin account if credentials are provided.
                # This is intentionally separated from NUT admin credentials.
                admin_username = data.get('dashboard_admin_username')
                admin_password = data.get('dashboard_admin_password')
                from core.auth import is_auth_disabled

                if is_auth_disabled():
                    if not admin_username:
                        admin_username = 'admin'
                    if not admin_password:
                        import secrets
                        admin_password = secrets.token_urlsafe(32)

                if admin_username and admin_password:
                    try:
                        # Import necessary modules for creating admin account
                        from werkzeug.security import generate_password_hash

                        # Create orm_login table if it doesn't exist (matches LoginAuth model)
                        login_auth = Table('orm_login', metadata,
                            Column('id', Integer, primary_key=True),
                            Column('username', String(100), nullable=False, unique=True),
                            Column('password_hash', String(255), nullable=False),
                            Column('is_active', Boolean, default=True),
                            Column('is_admin', Boolean, default=False),
                            Column('role', String(20), default='user'),
                            Column('permissions', Text, nullable=True),
                            Column('options_tabs', Text, nullable=True),
                            Column('last_login', DateTime(timezone=True), nullable=True),
                            Column('created_at', DateTime(timezone=True), default=utc_now),
                            Column('updated_at', DateTime(timezone=True), default=utc_now, onupdate=utc_now)
                        )

                        # Create the table if it doesn't exist
                        login_auth.create(engine, checkfirst=True)

                        # Hash the password using pbkdf2:sha256 for compatibility
                        password_hash = generate_password_hash(admin_password, method='pbkdf2:sha256')

                        # Insert or update admin user
                        with engine.connect() as conn:
                            trans = conn.begin()
                            try:
                                # Check if admin user already exists
                                check_query = select(func.count()).select_from(login_auth).where(
                                    login_auth.c.username == admin_username
                                )
                                count = conn.execute(check_query).scalar()

                                if count == 0:
                                    # Insert new admin user (first user is admin)
                                    ins = login_auth.insert().values(
                                        username=admin_username,
                                        password_hash=password_hash,
                                        is_active=True,
                                        is_admin=True,  # First user is admin
                                        role='administrator',  # Admin role
                                        last_login=None,
                                        created_at=current_timestamp,
                                        updated_at=current_timestamp
                                    )
                                    conn.execute(ins)
                                    logger.info(f"✅ Created admin user: {admin_username}")
                                else:
                                    # Update existing admin user
                                    upd = login_auth.update().where(
                                        login_auth.c.username == admin_username
                                    ).values(
                                        password_hash=password_hash,
                                        is_active=True,
                                        is_admin=True,  # Keep admin status
                                        role='administrator',  # Admin role
                                        last_login=None,
                                        updated_at=current_timestamp
                                    )
                                    conn.execute(upd)
                                    logger.info(f"✅ Updated admin user: {admin_username}")

                                # Commit the transaction
                                trans.commit()
                                logger.info("✅ Admin account transaction committed successfully")

                            except Exception as e:
                                trans.rollback()
                                logger.error(f"❌ Admin account transaction rolled back due to error: {str(e)}")
                                raise

                    except Exception as e:
                        logger.error(f"❌ Error creating admin account: {str(e)}")
                        return jsonify({
                            'status': 'error',
                            'message': f"Failed to create admin account: {str(e)}"
                        }), 500

                saved_multi_targets = None
                try:
                    saved_multi_targets = save_multi_nut_targets(
                        engine=engine,
                        metadata=metadata,
                        data=data,
                        nut_mode=nut_mode,
                        command_path=UPSC_BIN,
                        current_timestamp=current_timestamp,
                        raw_targets=multi_targets if monitoring_profile == 'multi' else [],
                    )
                except Exception as e:
                    logger.error(f"❌ Error saving wizard targets: {str(e)}")
                    return jsonify({
                        'status': 'error',
                        'message': f"Failed to save wizard targets: {str(e)}"
                    }), 500

                setup_currency = normalize_currency_code(data.get('currency'), fallback='EUR')
                setup_timezone_for_options = timezone
                setup_polling_for_options = coerce_int(data.get('polling_interval'), 1, 1, 60)
                setup_nominal_for_options = ups_realpower_nominal

                if saved_multi_targets:
                    primary_target_options = next(
                        (item for item in saved_multi_targets if item.get('is_primary')),
                        saved_multi_targets[0],
                    )
                    setup_currency = normalize_currency_code(
                        primary_target_options.get('currency'),
                        fallback=setup_currency,
                    )
                    setup_timezone_for_options = normalize_timezone_name(
                        primary_target_options.get('timezone'),
                        fallback=setup_timezone_for_options,
                    )
                    setup_polling_for_options = coerce_int(
                        primary_target_options.get('polling_interval'),
                        setup_polling_for_options,
                        1,
                        60,
                    )
                    setup_nominal_for_options = (
                        coerce_optional_positive_int(primary_target_options.get('ups_realpower_nominal'))
                        or setup_nominal_for_options
                    )

                save_variable_options_from_setup(
                    engine=engine,
                    metadata=metadata,
                    current_timestamp=current_timestamp,
                    timezone=setup_timezone_for_options,
                    currency=setup_currency,
                    polling_interval=setup_polling_for_options,
                    ups_realpower_nominal=setup_nominal_for_options,
                    target_options=saved_multi_targets,
                )

                logger.info("✅ Setup metadata initialized in nutify_master_control + ups_opt_variable_config")

                if SETUP_DATA_KEY in session:
                    session.pop(SETUP_DATA_KEY, None)

                try:
                    runtime_timezone = pytz.timezone(timezone)
                    if hasattr(current_app, 'CACHE_TIMEZONE'):
                        current_app.CACHE_TIMEZONE = runtime_timezone
                    import app as app_module
                    app_module.CACHE_TIMEZONE = runtime_timezone
                    logger.info(f"Updated runtime CACHE_TIMEZONE from setup save-config to: {timezone}")
                except Exception as timezone_error:
                    logger.warning(f"Unable to refresh runtime CACHE_TIMEZONE after setup save: {timezone_error}")
            except Exception as orm_error:
                logger.error(f"❌ Error saving setup metadata: {str(orm_error)}")
                return jsonify({
                    'status': 'error',
                    'message': f"Failed to create database table: {str(orm_error)}"
                })
                
            except Exception as e:
                logger.error(f"Error saving configuration to database: {str(e)}")
                # We don't return an error here since the NUT config files were saved successfully
                # Just log the error and continue
            
            # Return success with list of saved files
            return jsonify({
                'status': 'success',
                'message': f"Configuration saved successfully. Saved files: {', '.join(saved_files)}"
            })
            
        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f"Error saving configuration: {str(e)}"
            })
    
    except Exception as e:
        logger.error(f"Error saving configuration: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error saving configuration: {str(e)}'
        })

@nut_config_bp.route('/api/setup/generate-preview', methods=['POST'])
def generate_config_preview():
    """
    Generate a preview of the NUT configuration files
    
    Returns:
        JSON: Configuration files with status
    """
    try:
        # Get data from request
        data = request.json
        mode = data.get('mode')
        monitoring_profile = normalize_monitoring_profile(data.get('monitoring_profile', 'single'))
        multi_topology = normalize_multi_topology(data.get('multi_topology'))
        multi_targets = sanitize_multi_targets(data.get('multi_targets', []))
        if monitoring_profile == 'multi':
            try:
                validate_targets_for_topology(multi_targets, multi_topology)
            except ValueError as topology_error:
                return jsonify({
                    'status': 'error',
                    'message': str(topology_error),
                }), 400
        
        # Simple validation
        if not mode:
            return jsonify({
                'status': 'error',
                'message': 'Missing required parameter: mode'
            }), 400
        
        # Get the configuration manager instance
        conf_manager = NUTConfManager(os.path.join(os.path.dirname(__file__), 'conf_templates'))
        
        # Validate mode
        if not conf_manager.validate_mode(mode):
            return jsonify({
                'status': 'error',
                'message': f"Invalid mode: {mode}. Valid modes are: standalone, netserver, netclient"
            }), 400
        
        # Prepare variables for template rendering
        variables = {}
        
        # Common variables
        if mode == 'standalone' or mode == 'netserver':
            variables['UPS_NAME'] = data.get('ups_name', 'ups')
            variables['DRIVER'] = data.get('ups_driver', 'usbhid-ups')
            variables['PORT'] = data.get('ups_port', 'auto')
            variables['DESCRIPTION'] = data.get('ups_desc', '')
            
        # Mode-specific variables
        if mode == 'standalone':
            variables['SERVER_ADDRESS'] = data.get('server_address', '127.0.0.1')
            variables['UPS_HOST'] = 'localhost'
            variables['MONITOR_USERNAME'] = data.get('monitor_username', 'monuser') or 'monuser'
            variables['MONITOR_PASSWORD'] = data.get('monitor_password', 'monpass') or 'monpass'
            
        elif mode == 'netserver':
            variables['SERVER_ADDRESS'] = data.get('server_address', '127.0.0.1')
            variables['UPS_HOST'] = 'localhost'
            variables['LISTEN_ADDRESS'] = data.get('listen_address', '0.0.0.0')
            variables['LISTEN_PORT'] = data.get('listen_port', '3493')
            variables['ADMIN_USERNAME'] = data.get('admin_user', 'admin')
            variables['ADMIN_PASSWORD'] = data.get('admin_password', 'adminpass')
            variables['MONITOR_USERNAME'] = data.get('monitor_username', 'monuser') or 'monuser'
            variables['MONITOR_PASSWORD'] = data.get('monitor_password', 'monpass') or 'monpass'
        
        elif mode == 'netclient':
            remote_username = data.get('remote_user', 'monuser') or 'monuser'
            remote_password = data.get('remote_password', 'monpass') or 'monpass'
            variables['UPS_NAME'] = data.get('remote_ups_name', 'ups')
            variables['UPS_HOST'] = data.get('remote_host', 'localhost')
            variables['REMOTE_PORT'] = data.get('remote_port', '3493')
            variables['REMOTE_USERNAME'] = remote_username
            variables['REMOTE_PASSWORD'] = remote_password
        
        # Get configuration files from templates with variables substituted
        config_files = conf_manager.get_conf_files(mode, variables)
        
        # Generate ups.conf
        if (mode == 'standalone' or mode == 'netserver') and 'raw_ups_config' in data and data['raw_ups_config']:
            # Use the raw config from auto-detect
            ups_name = data.get('ups_name', 'ups')
            raw_config = data['raw_ups_config']
            
            # Make sure the UPS name in the config matches the user-provided name
            if raw_config.startswith('['):
                line_end = raw_config.find(']')
                if line_end > 0:
                    # Replace the device name with the user-provided name
                    raw_config = f"[{ups_name}]" + raw_config[line_end+1:]
            
            # Update the template-generated ups.conf with our raw config
            config_files['ups.conf'] = raw_config

        config_files = apply_primary_usb_identity_settings(config_files, data)
        config_files = apply_primary_snmp_settings(config_files, data)

        if monitoring_profile == 'multi' and multi_targets:
            try:
                config_files = apply_multi_target_config_extensions(
                    conf_files=config_files,
                    nut_mode=mode,
                    data=data,
                    multi_targets=multi_targets,
                )
            except ValueError as ext_error:
                return jsonify({
                    'status': 'error',
                    'message': str(ext_error),
                }), 400

        default_monitor_username = normalize_monitor_credential(
            data.get('monitor_username') or data.get('remote_user'),
            'monuser',
        )
        default_monitor_password = normalize_monitor_credential(
            data.get('monitor_password') or data.get('remote_password'),
            'monpass',
        )
        config_files['upsmon.conf'] = enforce_upsmon_notifycmd(config_files.get('upsmon.conf', ''))
        config_files['upsmon.conf'] = normalize_upsmon_conf_content(
            config_files.get('upsmon.conf', ''),
            default_username=default_monitor_username,
            default_password=default_monitor_password,
        )
        
        return jsonify({
            'status': 'success',
            'config_files': config_files
        })
        
    except Exception as e:
        logger.error(f"Error generating config preview: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error generating config preview: {str(e)}"
        }), 500

@nut_config_bp.route('/setup/timezone_page')
def setup_timezone_page():
    """Render the timezone selection page."""
    return serve_react_index()

@nut_config_bp.route('/setup/server_name', methods=['POST'])
def setup_server_name():
    """Handle the server name form submission and redirect to timezone selection"""
    if request.method == 'POST':
        server_name = request.form.get('server_name', 'UPS')
        
        # Store in session
        if SETUP_DATA_KEY not in session:
            session[SETUP_DATA_KEY] = {}
        
        session[SETUP_DATA_KEY]['server_name'] = server_name
        session.modified = True
        
        # Redirect to timezone page with query parameters
        return redirect(url_for('nut_config.setup_timezone_page') + f'?server_name={server_name}')
    
    return redirect(url_for('nut_config.welcome'))

@nut_config_bp.route('/setup/timezone', methods=['POST'])
def setup_timezone():
    """Handle the timezone form submission and redirect directly to the NUT wizard"""
    if request.method == 'POST':
        server_name = request.form.get('server_name', 'UPS')
        timezone = request.form.get('timezone', 'UTC')
        
        # Store in session
        if SETUP_DATA_KEY not in session:
            session[SETUP_DATA_KEY] = {}
        session[SETUP_DATA_KEY]['server_name'] = server_name
        session[SETUP_DATA_KEY]['timezone'] = timezone
        session.modified = True
        
        # Go to wizard
        return redirect(url_for('nut_config.setup_wizard'))
    return redirect(url_for('nut_config.welcome'))

@nut_config_bp.route('/api/delete-config', methods=['POST'])
def delete_config():
    """
    Delete configuration files.
    
    This endpoint is called when a user navigates back from the completion
    step after saving configuration, to clean up the files.
    
    Returns:
        JSON: Status and message.
    """
    try:
        # Use centralized config directory from settings
        config_dir = NUT_CONF_DIR
        
        # Log the request
        logger.info(f"Deleting configuration files in {config_dir}")
        
        # First, stop all NUT services
        try:
            subprocess.run(["pkill", "-9", "upsd"], stderr=subprocess.PIPE)
            subprocess.run([UPSDRVCTL_BIN, "stop"], stderr=subprocess.PIPE)
            logger.info("Stopped NUT services before deleting configuration files")
        except Exception as e:
            logger.warning(f"Error stopping NUT services: {str(e)}")
            
        # Delete configuration files
        files_deleted = []
        for filename in ['nut.conf', 'ups.conf', 'upsd.conf', 'upsd.users', 'upsmon.conf']:
            file_path = os.path.join(config_dir, filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    files_deleted.append(filename)
                    logger.info(f"Deleted configuration file: {filename}")
                except Exception as e:
                    logger.error(f"Error deleting {filename}: {str(e)}")
                    
            return jsonify({
            'status': 'success',
            'message': 'Configuration files deleted',
            'files_deleted': files_deleted
        })
            
    except Exception as e:
        logger.error(f"Error deleting configuration files: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error deleting configuration files: {str(e)}'
        }), 500

@nut_config_bp.route('/api/setup/get-available-drivers', methods=['GET'])
def get_available_drivers():
    """
    Get list of available NUT drivers based on installed files
    
    Returns:
        JSON: List of available drivers with descriptions
    """
    try:
        # Find drivers in the driver directory from settings_path.txt only
        if NUT_DRIVER_DIR and os.path.exists(NUT_DRIVER_DIR):
            logger.info(f"Looking for drivers in: {NUT_DRIVER_DIR}")
            drivers = {}
            
            try:
                driver_files = os.listdir(NUT_DRIVER_DIR)
                for driver_file in driver_files:
                    # Skip non-files
                    file_path = os.path.join(NUT_DRIVER_DIR, driver_file)
                    if not os.path.isfile(file_path):
                        continue
                        
                    # Skip known non-driver files
                    if driver_file in ['cmdvartab', 'driver.list', 'skel']:
                        continue
                        
                    # Get the driver name from the file
                    name = driver_file
                    
                    # Create a readable description
                    desc = name.replace('_', ' ').replace('-', ' ').title() + ' Driver'
                    drivers[name] = desc
                
                logger.info(f"Found {len(drivers)} drivers in {NUT_DRIVER_DIR}")
                
                # Convert to list format for the API response
                driver_list = [{'name': driver, 'description': desc} for driver, desc in drivers.items()]
                
                # Sort the list alphabetically
                driver_list.sort(key=lambda x: x['name'])
                
                return jsonify({
                    'status': 'success',
                    'drivers': driver_list,
                    'directory': NUT_DRIVER_DIR
                })
                
            except (PermissionError, FileNotFoundError) as e:
                # Specific error for permission or file not found issues
                logger.error(f"Error accessing driver directory {NUT_DRIVER_DIR}: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'message': f"Cannot access driver directory: {NUT_DRIVER_DIR}. Error: {str(e)}"
                }), 500
                
        else:
            # Directory doesn't exist
            message = f"Driver directory not found: {NUT_DRIVER_DIR}"
            logger.error(message)
            return jsonify({
                'status': 'error',
                'message': message
            }), 404
            
    except Exception as e:
        logger.error(f"Error getting available drivers: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error getting available drivers: {str(e)}"
        }), 500

@nut_config_bp.route('/api/setup/run-nut-scanner', methods=['POST'])
def run_nut_scanner():
    """
    Run nut-scanner to detect UPS devices
    
    Returns:
        JSON: Detected UPS devices
    """
    try:
        # Get scan types from request, default to USB scan
        scan_types = request.json.get('scan_types', ['usb'])
        # Get the user-provided UPS name
        current_ups_name = request.json.get('current_ups_name', 'ups')
        
        # Build the command arguments
        cmd_args = [NUT_SCANNER_CMD]
        if 'usb' in scan_types:
            cmd_args.append('--usb_scan')
        if 'snmp' in scan_types:
            cmd_args.append('--snmp_scan')
        if 'xml' in scan_types:
            cmd_args.append('--xml_scan')
        if 'oldnut' in scan_types:
            cmd_args.append('--oldnut_scan')
        if 'avahi' in scan_types:
            cmd_args.append('--avahi_scan')
        if 'ipmi' in scan_types:
            cmd_args.append('--ipmi_scan')
        
        # Run nut-scanner
        logger.info(f"Running nut-scanner: {' '.join(cmd_args)}")
        result = subprocess.run(cmd_args, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.error(f"nut-scanner failed: {result.stderr}")
            return jsonify({
                'status': 'error',
                'message': f"nut-scanner failed: {result.stderr}"
                }), 500
        
        # Raw output for full configuration
        raw_output = result.stdout
        
        devices = parse_nut_scanner_devices(raw_output)
        combined_config = combined_preview_config(devices)
                    
        return jsonify({
            'status': 'success',
            'devices': devices,
            'raw_output': raw_output,
            'combined_config': combined_config,
            'ups_name': current_ups_name
        })
        
    except subprocess.TimeoutExpired:
        logger.error("nut-scanner command timed out")
        return jsonify({
            'status': 'error',
            'message': "nut-scanner command timed out"
        }), 500
    except Exception as e:
        logger.error(f"Error running nut-scanner: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f"Error running nut-scanner: {str(e)}"
        }), 500

def register_routes(app):
    """
    Register NUT configuration routes with the Flask app.
    
    Args:
        app: The Flask app
    """
    # Register the blueprint
    app.register_blueprint(nut_config_bp)
    
    @app.before_request
    def check_nut_config():
        # Skip check for welcome page, static resources, and API endpoints
        if request.path.startswith('/static/') or \
           request.path.startswith('/frontend-dist/') or \
           request.path.startswith('/favicon.ico') or \
           request.path.startswith('/nut_config/') or \
           request.path.startswith('/api/'):
            return
            
        # Only redirect to welcome page if not in debug mode and NUT is not configured
        if not is_nut_configured() and not app.debug:
            if request.endpoint != 'nut_config.welcome' and request.endpoint != 'nut_config.setup_wizard':
                return redirect(url_for('nut_config.welcome'))
    
    @app.route('/')
    @app.route('/index')
    def dashboard_index():
        """
        Render the dashboard index page.
        
        This route is registered in the main app to ensure it works properly
        with the NUT configuration check middleware.
        """
        if not is_nut_configured():
            return redirect(url_for('nut_config.welcome'))
            
        try:
            # Check authentication first
            from core.auth import is_login_configured, is_authenticated
            
            if not is_login_configured():
                return redirect(url_for('auth.setup'))
            if not is_authenticated():
                return redirect(url_for('auth.login'))
            return serve_react_index()
        except Exception as e:
            logger.error(f"Error in dashboard_index route: {str(e)}")
            return serve_react_index()
    
    logger.info("✅ Registered NUT Configuration routes")
    return app 
