"""
NUT Configuration Routes.

This module provides Flask routes for managing NUT configuration.
"""

from flask import Blueprint, render_template, jsonify, request, redirect, url_for, current_app, send_file, abort, Response, session
from .config import is_nut_configured, check_nut_config_files
from core.settings import (
    INSTANCE_PATH, DB_NAME, NUT_CONF_DIR, UPSC_BIN, UPSC_CMD,
    UPSD_BIN, UPSDRVCTL_BIN, NUT_START_DRIVER_CMD, NUT_START_SERVER_CMD,
    NUT_STOP_DRIVER_CMD, NUT_STOP_SERVER_CMD, NUT_STOP_MONITOR_CMD, NUT_DRIVER_DIR,
    NUT_SCANNER_CMD
)
from core.logger import system_logger as logger
import os
import datetime
import re
import sys
import subprocess
import time
import shutil
from stat import S_IRWXU, S_IRWXG, S_IROTH, S_IXOTH
import platform
import tempfile
import importlib
import os.path
import pytz
import json
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, Boolean, DateTime, Text, text, inspect
from sqlalchemy.sql import select, func

# Import configuration manager once
from .conf_manager import NUTConfManager

# Restore original blueprint setup with correct URL prefix
nut_config_bp = Blueprint('nut_config', __name__, url_prefix='/nut_config')

# Path to the timezone file
TIMEZONE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'TimeZone.readme')

# Global session key for collecting setup data
SETUP_DATA_KEY = 'setup_data'

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
    
    return render_template('dashboard/setup/welcome.html', 
                         missing_files=missing_files,
                         nut_config_dir=NUT_CONF_DIR,
                         current_year=datetime.datetime.now(pytz.UTC).year,
                         timezone=pytz.UTC)

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
    
    from core.auth import is_auth_disabled
    return render_template('dashboard/setup/wizard.html',
                         current_year=datetime.datetime.now(pytz.UTC).year,
                         timezone=pytz.UTC,
                         auth_disabled=is_auth_disabled())

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
            if file_content and re.search(r'\{\{[A-Z_]+\}\}', file_content):
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
            
        # For remote NUT server in netclient mode, test directly
        if is_remote_nut:
            logger.info(f"Testing remote NUT server connection to {ups_name}@{ups_host}")
            
            upsc_cmd = f"{UPSC_BIN} {ups_name}@{ups_host}"
            upsc_result = subprocess.run(upsc_cmd, shell=True, capture_output=True, text=True)
            
            if upsc_result.returncode != 0:
                error_msg = (
                    f"Failed to connect to REMOTE NUT SERVER at {ups_host}: Connection refused.\n\n"
                    f"REMOTE NUT SERVER TROUBLESHOOTING:\n"
                    f"1. Verify the NUT server at {ups_host} is online and running\n"
                    f"2. Check that the remote server's upsd.conf has 'LISTEN 0.0.0.0' to accept external connections\n"
                    f"3. Ensure the remote server's firewall allows connections to port 3493\n"
                    f"4. Verify the UPS name '{ups_name}' exists on the remote server (run '{UPSC_CMD} -l' there)\n"
                    f"5. Check if the remote server requires authentication\n\n"
                    f"Error details: {upsc_result.stderr}"
                )
                logger.error(error_msg)
                return jsonify({
                    'status': 'error',
                    'errors': [error_msg]
                }), 400
            else:
                logger.info(f"Successfully connected to remote NUT server {ups_name}@{ups_host}")
                return jsonify({
                    'status': 'success',
                    'message': f"Successfully connected to remote NUT server {ups_name}@{ups_host}",
                    'test_details': upsc_result.stdout if upsc_result.stdout else "Connection successful"
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
                    with open(file_path, 'w') as f:
                        f.write(data[key])
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
            
            # Test with upsc
            upsc_cmd = f"{UPSC_BIN} {ups_name}@{ups_host}"
            logger.info(f"Testing UPS with command: {upsc_cmd}")
            upsc_result = subprocess.run(upsc_cmd, shell=True, capture_output=True, text=True)
            
            if upsc_result.returncode != 0:
                logger.error(f"Failed to connect to UPS: {upsc_result.stderr}")
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
                
                # Determine if this is a remote or local connection for better error message
                is_remote_connection = ups_host != "localhost" and ups_host != "127.0.0.1"
                
                if "Connection refused" in upsc_result.stderr or "Connection failure" in upsc_result.stderr:
                    if is_remote_connection:
                        error_msg = (
                            f"Failed to connect to REMOTE UPS at {ups_host}: Connection refused.\n\n"
                            f"REMOTE SERVER CONFIGURATION CHECKLIST:\n"
                            f"1. Verify the UPS server at {ups_host} is online and running NUT\n"
                            f"2. Check that the remote server's upsd.conf has 'LISTEN 0.0.0.0' to accept external connections\n"
                            f"3. Ensure the remote server's firewall allows connections to port 3493\n"
                            f"4. Verify the UPS name '{ups_name}' on the remote server matches what you configured\n\n"
                            f"Command that failed: {upsc_cmd}"
                        )
                    else:
                        error_msg = (
                            f"Failed to connect to LOCAL UPS: Connection refused.\n\n"
                            f"LOCAL UPS CONFIGURATION CHECKLIST:\n"
                            f"1. Verify NUT service is running\n"
                            f"2. Check that the UPS is physically connected to this computer\n"
                            f"3. Verify the UPS name '{ups_name}' is correctly configured in ups.conf\n\n"
                            f"Command that failed: {upsc_cmd}"
                        )
                else:
                    error_msg = f"Failed to connect to UPS with upsc: {upsc_result.stderr}"
                
                return jsonify({
                    'status': 'error',
                    'errors': [error_msg],
                    'command_output': upsc_result.stderr
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
                'message': f"Successfully connected to UPS {ups_name}@{ups_host}",
                'test_details': upsc_result.stdout if upsc_result.stdout else "Connection successful"
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
        
        # Extract setup data from session or request
        server_name = data.get('server_name', session.get(SETUP_DATA_KEY, {}).get('server_name', 'UPS'))
        timezone = data.get('timezone', session.get(SETUP_DATA_KEY, {}).get('timezone', 'UTC'))
        
        # Extract ups.realpower.nominal if provided
        ups_realpower_nominal = data.get('ups_realpower_nominal', None)
        
        # Use centralized config directory from settings
        config_dir = NUT_CONF_DIR
        
        # Create a template manager instance
        templates_dir = os.path.join(os.path.dirname(__file__), 'conf_templates')
        conf_manager = NUTConfManager(templates_dir)
        
        # Check for direct config file data
        has_direct_config = 'nut_conf' in data or 'nut.conf' in data
        
        # If direct config data is provided, use it instead of generating from templates
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
            variables = {
                'UPS_NAME': conf_manager.clean_variable_name(data.get('remote_ups_name', 'ups')),
                'UPS_HOST': conf_manager.clean_variable_name(data.get('remote_host', 'localhost')),
                    'REMOTE_PORT': data.get('remote_port', '3493'),
                'REMOTE_USERNAME': conf_manager.clean_variable_name(data.get('remote_user', 'monuser')),
                    'REMOTE_PASSWORD': conf_manager.clean_variable_name(data.get('remote_password', 'monpass')),
                'MONITOR_USERNAME': conf_manager.clean_variable_name(data.get('remote_user', 'monuser')),
                'MONITOR_PASSWORD': conf_manager.clean_variable_name(data.get('remote_password', '')),
                'ADDITIONAL_USERS': ''
            }
        
        # Special handling for remote_nut scenario
        if connection_scenario == 'remote_nut':
            # For remote NUT, we use the remote server's UPS name
            variables['UPS_NAME'] = data.get('ups_name', 'ups')
            variables['UPS_HOST'] = data.get('ups_host', 'localhost')
            # Make sure REMOTE_USERNAME maps to the same as remote_username for template compatibility
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
            # For Serial UPS, ensure correct driver and port
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
            
        elif connection_scenario == 'remote_nut':
            # For remote NUT server, we don't need ups.conf
            pass
        
        # Generate configuration files using templates
            conf_files = conf_manager.get_conf_files(nut_mode, variables)
            
            # Special handling for netclient mode with remote_nut scenario
            if nut_mode == 'netclient' and connection_scenario == 'remote_nut':
                # netclient mode doesn't use ups.conf, upsd.conf or upsd.users
                conf_files['ups.conf'] = ''
                conf_files['upsd.conf'] = ''
                conf_files['upsd.users'] = ''
        
        # If raw UPS config was provided, use it 
        if 'raw_ups_config' in data and data['raw_ups_config'] and connection_scenario in ['local_usb']:
            ups_name = data.get('ups_name', 'ups')
            raw_config = data['raw_ups_config']
            conf_files['ups.conf'] = raw_config
        
        # Automatically correct nut_mode based on connection_scenario if needed
        if connection_scenario == 'remote_nut' and nut_mode != 'netclient':
            nut_mode = 'netclient'
            logger.info(f"Automatically correcting NUT mode to 'netclient' for remote_nut scenario")
        elif connection_scenario in ['local_usb', 'local_serial'] and nut_mode not in ['standalone', 'netserver']:
            # For local connections, mode must be standalone or netserver
            if nut_mode == 'netclient':
                nut_mode = 'standalone'
                logger.info(f"Automatically correcting NUT mode to 'standalone' for local UPS scenario")
        
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
                # 1. Create the ups_initial_setup table using SQLAlchemy ORM
                logger.info("Creating ups_initial_setup table using SQLAlchemy ORM...")
                
                try:
                    # Ensure the instance directory exists
                    os.makedirs(os.path.dirname(os.path.join(INSTANCE_PATH, DB_NAME)), exist_ok=True)
                    
                    # Create engine and metadata
                    engine = create_engine(f'sqlite:///{os.path.join(INSTANCE_PATH, DB_NAME)}')
                    metadata = MetaData()
                    
                    # Define the table
                    ups_initial_setup = Table(
                        'ups_initial_setup', 
                        metadata,
                        Column('id', Integer, primary_key=True),
                        Column('server_name', String(100), nullable=False, default='UPS'),
                        Column('timezone', String(50), nullable=False, default='UTC'),
                        Column('is_configured', Boolean, default=False),
                        Column('ups_realpower_nominal', Integer),
                        Column('created_at', DateTime, default=datetime.datetime.now()),
                        Column('updated_at', DateTime, default=datetime.datetime.now())
                    )
                    
                    # Create the table if it doesn't exist
                    ups_initial_setup.create(engine, checkfirst=True)
                    
                    # Current timestamp for database operations
                    current_timestamp = datetime.datetime.now()
                    
                    # Check if there's already data in the table
                    with engine.connect() as conn:
                        # Create a transaction that will be automatically committed when the connection is closed
                        trans = conn.begin()
                        try:
                            count_query = select(func.count()).select_from(ups_initial_setup)
                            count = conn.execute(count_query).scalar()
                            
                            # If no records exist, insert the configuration
                            if count == 0:
                                ins = ups_initial_setup.insert().values(
                                    server_name=server_name,
                                    timezone=timezone,
                                    is_configured=True,
                                    ups_realpower_nominal=ups_realpower_nominal,
                                    created_at=current_timestamp,
                                    updated_at=current_timestamp
                                )
                                conn.execute(ins)
                                logger.info("Inserted new configuration record")
                            else:
                                # Update existing record
                                min_id_query = select(func.min(ups_initial_setup.c.id))
                                min_id = conn.execute(min_id_query).scalar()
                                
                                upd = ups_initial_setup.update().where(
                                    ups_initial_setup.c.id == min_id
                                ).values(
                                    server_name=server_name,
                                    timezone=timezone,
                                    is_configured=True,
                                    ups_realpower_nominal=ups_realpower_nominal,
                                    updated_at=current_timestamp
                                )
                                conn.execute(upd)
                                logger.info("Updated existing configuration record")
                            
                            # Explicitly commit the transaction
                            trans.commit()
                            logger.info("✅ Transaction committed successfully")
                        except Exception as e:
                            # Roll back in case of error
                            trans.rollback()
                            logger.error(f"❌ Transaction rolled back due to error: {str(e)}")
                            raise
                        
                    # Add an additional explicit commit for older SQLAlchemy versions
                    try:
                        conn.commit()  # Some older versions of SQLAlchemy need this
                    except:
                        pass  # Ignore if not supported
                    
                    # Create admin account if credentials are provided
                    admin_username = data.get('admin_username')
                    admin_password = data.get('admin_password')
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
                                Column('created_at', DateTime(timezone=True), default=datetime.datetime.now),
                                Column('updated_at', DateTime(timezone=True), default=datetime.datetime.now, onupdate=datetime.datetime.now)
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
                    
                    logger.info("✅ ups_initial_setup table initialized successfully with SQLAlchemy ORM")
                except Exception as orm_error:
                    logger.error(f"❌ Error creating ups_initial_setup table with SQLAlchemy ORM: {str(orm_error)}")
                    return jsonify({
                        'status': 'error',
                        'message': f"Failed to create database table: {str(orm_error)}"
                    })
                
                # Clear the session data as we're done
                if SETUP_DATA_KEY in session:
                    session.pop(SETUP_DATA_KEY, None)
                
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
            variables['MONITOR_USERNAME'] = data.get('monitor_username', 'monuser')
            variables['MONITOR_PASSWORD'] = data.get('monitor_password', 'monpass')
            
        elif mode == 'netserver':
            variables['SERVER_ADDRESS'] = data.get('server_address', '127.0.0.1')
            variables['UPS_HOST'] = 'localhost'
            variables['LISTEN_ADDRESS'] = data.get('listen_address', '0.0.0.0')
            variables['LISTEN_PORT'] = data.get('listen_port', '3493')
            variables['ADMIN_USERNAME'] = data.get('admin_user', 'admin')
            variables['ADMIN_PASSWORD'] = data.get('admin_password', 'adminpass')
            variables['MONITOR_USERNAME'] = data.get('monitor_username', 'monuser')
            variables['MONITOR_PASSWORD'] = data.get('monitor_password', 'monpass')
        
        elif mode == 'netclient':
            variables['UPS_NAME'] = data.get('remote_ups_name', 'ups')
            variables['UPS_HOST'] = data.get('remote_host', 'localhost')
            variables['REMOTE_PORT'] = data.get('remote_port', '3493')
            variables['REMOTE_USERNAME'] = data.get('remote_user', 'monuser')
            variables['REMOTE_PASSWORD'] = data.get('remote_password', 'monpass')
        
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
    """Render the timezone selection page"""
    # Get server name from query params
    server_name = request.args.get('server_name', 'UPS')
    
    # Get list of timezones
    timezones = get_timezones()
    
    return render_template('dashboard/setup/timezone.html',
                          server_name=server_name,
                          timezones=timezones,
                          current_year=datetime.datetime.now(pytz.UTC).year,
                          timezone=pytz.UTC)

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

def save_database_config(server_name, timezone):
    """Save initial setup configuration to database"""
    try:
        # Import necessary modules
        from core.db.ups import db
        from core.db.initializer import init_database
        from flask import current_app
        import pytz
        
        logger.info(f"Saving initial setup configuration to database: server_name={server_name}, timezone={timezone}, cache_seconds=60 (fixed)")
        
        # Initialize database if needed
        with current_app.app_context():
            # First make sure the database is initialized with all tables
            init_result = init_database(current_app, db)
            if not init_result:
                logger.error("Failed to initialize database")
                raise Exception("Failed to initialize database")
                
            # Now import and use the InitialSetup model
            from core.db.orm.orm_ups_initial_setup import InitialSetup
            
            # Prepare configuration data
            config_data = {
                'server_name': server_name,
                'timezone': timezone,
                'cache_seconds': 60,  # Fixed value
                'is_configured': True
            }
            
            # Save to database using the ORM model
            InitialSetup.create_or_update(config_data)
            
            # Update the global CACHE_TIMEZONE
            try:
                from app import CACHE_TIMEZONE as app_cache_timezone
                # Need to use a reference to the global variable
                import app
                app.CACHE_TIMEZONE = pytz.timezone(timezone)
                # Also update the Flask app attribute
                if hasattr(current_app, 'CACHE_TIMEZONE'):
                    current_app.CACHE_TIMEZONE = pytz.timezone(timezone)
                logger.info(f"✅ Updated global CACHE_TIMEZONE to: {timezone}")
            except Exception as tz_error:
                logger.warning(f"⚠️ Could not update global CACHE_TIMEZONE: {str(tz_error)}")
            
            logger.info("Initial setup configuration saved successfully")
            return True
        
    except Exception as e:
        logger.error(f"Error saving database configuration: {str(e)}")
        raise

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
        
        # Parse the output to identify devices
        output = result.stdout
        devices = []
        current_device = None
        raw_device_configs = {}
        
        # First pass: collect complete device configurations
        device_config = []
        device_name = None
        
        for line in output.splitlines():
            line = line.strip()
            
            # New device section
            if line.startswith('[') and line.endswith(']'):
                # Save previous device if exists
                if device_name and device_config:
                    raw_device_configs[device_name] = "\n".join(device_config)
                
                # Start new device
                device_name = line[1:-1]
                device_config = [line]  # Include the header line
            elif device_name:
                # Add properties exactly as they are (preserve comments)
                device_config.append(line)
        
        # Save the last device
        if device_name and device_config:
            raw_device_configs[device_name] = "\n".join(device_config)
        
        # Second pass: extract key properties for the UI
        for line in output.splitlines():
            line = line.strip()
            
            # New device section
            if line.startswith('[') and line.endswith(']'):
                if current_device:
                    devices.append(current_device)
                
                device_name = line[1:-1]
                current_device = {
                    'name': device_name,
                    'driver': None,
                    'port': None,
                    'desc': f"Detected {device_name}",
                    'raw_config': None
                }
            
            # Driver line
            elif line.startswith('driver = '):
                if current_device:
                    driver = line[9:].strip(' "\'')
                    current_device['driver'] = driver
            
            # Port line
            elif line.startswith('port = '):
                if current_device:
                    port = line[7:].strip(' "\'')
                    current_device['port'] = port
            
            # Product line
            elif line.startswith('product = '):
                if current_device:
                    product = line[10:].strip(' "\'')
                    current_device['model'] = product
            
            # Vendor line
            elif line.startswith('vendor = '):
                if current_device:
                    vendor = line[9:].strip(' "\'')
                    current_device['vendor'] = vendor
            
            # Serial line
            elif line.startswith('serial = '):
                if current_device:
                    serial = line[9:].strip(' "\'')
                    current_device['serial'] = serial
        
        # Add the last device if it exists
        if current_device:
            devices.append(current_device)
        
        # Add raw config data to each device and ensure bus/device/busport are commented
        for device in devices:
            if device['name'] in raw_device_configs:
                # Get the original device config
                device_config = raw_device_configs[device['name']]
                
                # Replace the original device name with the user-provided name
                if device_config.startswith('['):
                    device_config = f"[{current_ups_name}]\n" + "\n".join(device_config.split('\n')[1:])
                
                # Ensure bus, device and busport are commented out
                lines = device_config.splitlines()
                for i in range(len(lines)):
                    line = lines[i].strip()
                    if line.startswith('bus = ') or line.startswith('device = ') or line.startswith('busport = '):
                        # Comment only if not already commented
                        if not lines[i].strip().startswith('#'):
                            lines[i] = '# ' + line
                
                # Add the warning comment at the end
                lines.append('# WARNING: The bus, device and busport parameters are commented out to prevent reconnection issues.')
                lines.append('# When USB devices are disconnected and reconnected, these values often change,')
                lines.append('# which can cause NUT to fail finding the UPS. Leave them commented for better reliability.')
                
                # Update the device config
                device['raw_config'] = "\n".join(lines)
        
        # Create a combined representative configuration string for preview
        combined_config = ""
        if devices:
            # Use the first detected device
            combined_config = devices[0].get('raw_config', "")
                    
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
            elif not is_authenticated():
                return redirect(url_for('auth.login'))
            
            # Check if UPS connection is available using the connection monitor
            from core.db.internal_checker import is_ups_connected, get_ups_connection_status
            from core.db.ups import get_ups_data
            
            connection_available = is_ups_connected()
            if not connection_available:
                # Get connection status for display
                connection_status = get_ups_connection_status()
                
                # Provide a graceful degraded view with connection status
                return render_template(
                    'dashboard/main.html',
                    data=None,
                    connection_error=True,
                    connection_status=connection_status,
                    recovery_mode=connection_status.get('in_recovery_mode', False),
                    recovery_attempts=connection_status.get('recovery_attempts', 0),
                    current_time=datetime.datetime.now(current_app.CACHE_TIMEZONE),
                    timezone=current_app.CACHE_TIMEZONE
                )
            
            # Normal processing when connection is available
            data = get_ups_data()
            return render_template(
                'dashboard/main.html',
                data=data,
                connection_error=False,
                current_time=datetime.datetime.now(current_app.CACHE_TIMEZONE),
                timezone=current_app.CACHE_TIMEZONE
            )
        except Exception as e:
            logger.error(f"Error in dashboard_index route: {str(e)}")
            from core.settings import NUT_CONF_DIR
            
            # Create a minimal data structure with enough information to render the page
            data = {'device_model': 'UPS Monitor', 'errors': [str(e)]}
            
            # Add the NUT configuration directory to the data dictionary for the template
            data['nut_conf_dir'] = NUT_CONF_DIR
            
            return render_template(
                'dashboard/main.html',
                data=data,
                connection_error=True,
                error=str(e),
                current_time=datetime.datetime.now(current_app.CACHE_TIMEZONE),
                timezone=current_app.CACHE_TIMEZONE
            )
    
    logger.info("✅ Registered NUT Configuration routes")
    return app 
