"""
NUT Daemon Module.

This module provides functionality for:
- Starting NUT services (upsdrvctl, upsd, upsmon)
- Checking NUT service status
- Managing NUT services lifecycle
"""

import os
import re
import subprocess
import time
import logging
from pathlib import Path
from datetime import datetime

from core.settings import (
    UPSDRVCTL_BIN, UPSD_BIN, UPSMON_BIN, UPSC_BIN,
    NUT_CONF_PATH, UPS_CONF_PATH, UPSD_CONF_PATH, UPSD_USERS_PATH, UPSMON_CONF_PATH,
    NUT_RUN_DIR, NUT_LOG_DIR, NUT_STATE_DIR,
    # Add new path settings
    NUT_DRIVER_PID, NUT_UPSD_PID, NUT_UPSMON_PID,
    NUT_DRIVER_LOG, NUT_SERVER_LOG, NUT_UPSMON_LOG, NUT_NOTIFIER_LOG,
    NUT_SERVICE_WAIT_TIME, NUT_SERVICE_START_TIMEOUT,
    # Add full command constants
    NUT_START_DRIVER_CMD, NUT_START_SERVER_CMD, NUT_START_MONITOR_CMD,
    NUT_STOP_DRIVER_CMD, NUT_STOP_SERVER_CMD, NUT_STOP_MONITOR_CMD
)
from flask import current_app
from core.nut_config import check_nut_config_files
from core.logger import system_logger  # Import system_logger for main console output
from core.events.notifier_path import get_ups_notifier_command_path

# Set up logger
logger = logging.getLogger('nut_daemon')

class NUTDaemonError(Exception):
    """Base exception for NUT daemon errors"""
    pass

class NUTStartupError(NUTDaemonError):
    """Exception raised when NUT services fail to start"""
    pass

class NUTShutdownError(NUTDaemonError):
    """Exception raised when NUT services fail to stop"""
    pass

class NUTConfigError(NUTDaemonError):
    """Exception raised when NUT configuration is invalid or missing"""
    pass

def get_nut_mode():
    """
    Determine the NUT mode from nut.conf
    
    Returns:
        str: The NUT mode (standalone, netserver, netclient, none) or None if can't determine
    """
    try:
        if not os.path.exists(NUT_CONF_PATH):
            return None
            
        with open(NUT_CONF_PATH, 'r') as f:
            content = f.read()
            
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('MODE=') and not line.startswith('#'):
                mode = line.split('=', 1)[1].strip().strip('"\'')
                logger.info(f"Detected NUT mode: {mode}")
                return mode
        
        return None
    except Exception as e:
        logger.error(f"Error determining NUT mode: {str(e)}")
        return None

def check_service_status(service_name):
    """
    Check if a NUT service is running
    
    Args:
        service_name (str): Name of the service ('upsdrvctl', 'upsd', 'upsmon')
        
    Returns:
        bool: True if service is running, False otherwise
    """
    try:
        # Handle the case of upsdrvctl specially
        if service_name == 'upsdrvctl':
            # upsdrvctl isn't a daemon but starts drivers. Check for driver processes instead
            # Check for driver processes using different patterns for better detection
            cmd_list = [
                "ps aux | grep -v grep | grep -E 'nutdrv|[u]psdrvctl'",
                "ps aux | grep -v grep | grep -E 'usbhid-ups|[n]ut-driver'",
                "ps aux | grep -v grep | grep -E 'blazer|liebert|apcsmart'",  # Common driver names
            ]
            
            for cmd in cmd_list:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.stdout.strip():
                    logger.debug(f"Driver processes found via: {cmd}")
                    return True
            
            # If UPS is running on upsd, then the driver must be working
            # This is a fallback detection method
            if service_name == 'upsdrvctl':
                upsd_running = check_service_status('upsd')
                if upsd_running:
                    # Check if we can get UPS data, which means drivers are working
                    ups_name, ups_host = get_ups_monitor_config()
                    if ups_name and ups_host:
                        test_cmd = f"{UPSC_BIN} {ups_name}@{ups_host}"
                        try:
                            test_result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=3)
                            if test_result.returncode == 0 and test_result.stdout.strip():
                                logger.debug(f"upsdrvctl considered running because upsd is running and data is available")
                                return True
                        except Exception:
                            # If this fails, continue with other checks
                            pass
        elif service_name == 'upsd':
            # For upsd, check the server process
            cmd = "ps aux | grep -v grep | grep '[u]psd'"
            
            # Run the ps command to check for running processes
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.stdout.strip():
                logger.debug(f"Service {service_name} is running (via ps)")
                return True
                
            # Try to connect to upsd port as additional check
            try:
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                result = s.connect_ex(('127.0.0.1', 3493))
                s.close()
                if result == 0:
                    logger.debug(f"Service {service_name} is running (via socket)")
                    return True
            except Exception as e:
                logger.debug(f"Socket check failed: {str(e)}")
        elif service_name == 'upsmon':
            # For upsmon, check the monitor process
            cmd = "ps aux | grep -v grep | grep '[u]psmon'"
            
            # Run the ps command to check for running processes
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.stdout.strip():
                logger.debug(f"Service {service_name} is running (via ps)")
                return True
        else:
            logger.error(f"Unknown service: {service_name}")
            return False
        
        # As a backup, check PID files
        # Determine the pid file path based on service name
        if service_name == 'upsdrvctl':
            pid_file = os.path.join(NUT_RUN_DIR, NUT_DRIVER_PID)
        elif service_name == 'upsd':
            # Check multiple possible locations for upsd.pid
            upsd_pid_paths = [
                os.path.join(NUT_RUN_DIR, NUT_UPSD_PID),
                os.path.join(NUT_STATE_DIR, NUT_UPSD_PID)
            ]
            for pid_path in upsd_pid_paths:
                if os.path.exists(pid_path):
                    pid_file = pid_path
                    break
            else:
                logger.debug(f"No PID file found for {service_name}")
                return False
        elif service_name == 'upsmon':
            # Check multiple possible locations for upsmon.pid
            upsmon_pid_paths = [
                os.path.join('/run', NUT_UPSMON_PID),
                os.path.join('/var/run', NUT_UPSMON_PID),
                os.path.join(NUT_RUN_DIR, NUT_UPSMON_PID),
                os.path.join(NUT_STATE_DIR, NUT_UPSMON_PID)
            ]
            for pid_path in upsmon_pid_paths:
                if os.path.exists(pid_path):
                    pid_file = pid_path
                    break
            else:
                logger.debug(f"No PID file found for {service_name}")
                return False
        
        # Check if pid file exists
        if not os.path.exists(pid_file):
            logger.debug(f"PID file for {service_name} not found at {pid_file}")
            return False
            
        # Read the PID from the file
        with open(pid_file, 'r') as f:
            pid = f.read().strip()
            
        if not pid.isdigit():
            logger.warning(f"Invalid PID in {pid_file}: {pid}")
            return False
            
        # Check if process is running
        proc_path = f"/proc/{pid}"
        if os.path.exists(proc_path):
            logger.debug(f"Service {service_name} is running (via proc)")
            return True
            
        # On MacOS, use ps command to check if process is running
        if not os.path.exists('/proc'):
            result = subprocess.run(['ps', '-p', pid], capture_output=True, text=True)
            if result.returncode == 0:
                logger.debug(f"Service {service_name} is running (via ps -p)")
                return True
        
        return False
    except Exception as e:
        logger.error(f"Error checking status for {service_name}: {str(e)}")
        return False

def check_all_services_status():
    """
    Check status of all NUT services
    
    Returns:
        dict: Dictionary with service status
    """
    # Add timestamp to debug the gap
    system_logger.info(f"⏱️ Checking status of all NUT services at {time.strftime('%H:%M:%S')}")
    result = {
        'upsdrvctl': check_service_status('upsdrvctl'),
        'upsd': check_service_status('upsd'),
        'upsmon': check_service_status('upsmon')
    }
    system_logger.info(f"⏱️ Service status check completed at {time.strftime('%H:%M:%S')}")
    return result

def get_ups_monitor_config():
    """
    Get UPS monitor configuration from upsmon.conf
    
    Returns:
        tuple: (ups_name, ups_host) or (None, None) if not found
    """
    try:
        if not os.path.exists(UPSMON_CONF_PATH):
            logger.error(f"upsmon.conf not found at {UPSMON_CONF_PATH}")
            return None, None
            
        with open(UPSMON_CONF_PATH, 'r') as f:
            content = f.read()
            
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('MONITOR') and not line.startswith('#'):
                parts = line.split()
                if len(parts) >= 2:
                    ups_spec = parts[1]  # Format should be ups@host
                    if '@' in ups_spec:
                        ups_name, ups_host = ups_spec.split('@', 1)
                        logger.info(f"Found UPS monitor configuration: {ups_name}@{ups_host}")
                        return ups_name, ups_host
        
        logger.warning("No MONITOR line found in upsmon.conf")
        return None, None
    except Exception as e:
        logger.error(f"Error reading UPS monitor configuration: {str(e)}")
        return None, None


def _normalize_monitor_line(line, default_username='monuser', default_password='monpass'):
    """Normalize MONITOR line to modern format with username and password."""
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
    username = str(default_username or 'monuser').strip() or 'monuser'
    password = str(default_password or 'monpass').strip() or 'monpass'
    role = 'slave'

    remaining = parts[2:]
    if remaining and remaining[0].isdigit():
        power_value = str(max(1, int(remaining[0])))
        remaining = remaining[1:]

    if len(remaining) == 1:
        token = remaining[0]
        if token.lower() in {'master', 'slave'}:
            role = token.lower()
        else:
            username = str(token).strip() or username
    elif len(remaining) == 2:
        username = str(remaining[0]).strip() or username
        if remaining[1].lower() in {'master', 'slave'}:
            role = remaining[1].lower()
        else:
            password = str(remaining[1]).strip() or password
    elif len(remaining) >= 3:
        username = str(remaining[0]).strip() or username
        password = str(remaining[1]).strip() or password
        candidate_role = str(remaining[2]).strip().lower()
        role = candidate_role if candidate_role in {'master', 'slave'} else role

    normalized = f"{leading_spaces}MONITOR {ups_spec} {power_value} {username} {password} {role}"
    if inline_comment:
        normalized += f"  # {inline_comment}"
    return normalized


def _enforce_notifycmd_line(content):
    """Ensure upsmon.conf content contains one valid NOTIFYCMD line."""
    notifycmd_line = f"NOTIFYCMD {get_ups_notifier_command_path()}"
    safe_content = str(content or "")

    if not safe_content.strip():
        return notifycmd_line + '\n'

    notifycmd_pattern = re.compile(r"(?im)^\s*NOTIFYCMD\s+.+$")
    if notifycmd_pattern.search(safe_content):
        return notifycmd_pattern.sub(notifycmd_line, safe_content)

    shutdowncmd_pattern = re.compile(r"(?im)^\s*SHUTDOWNCMD\s+.+$")
    if shutdowncmd_pattern.search(safe_content):
        return shutdowncmd_pattern.sub(lambda match: f"{match.group(0)}\n{notifycmd_line}", safe_content, count=1)

    suffix = '' if safe_content.endswith('\n') else '\n'
    return safe_content + suffix + notifycmd_line + '\n'


def normalize_upsmon_configuration_file(default_username='monuser', default_password='monpass'):
    """Normalize MONITOR lines and enforce NOTIFYCMD inside upsmon.conf."""
    if not os.path.exists(UPSMON_CONF_PATH):
        return False

    with open(UPSMON_CONF_PATH, 'r') as file_handle:
        original_content = file_handle.read()

    normalized_lines = [
        _normalize_monitor_line(
            line,
            default_username=default_username,
            default_password=default_password,
        )
        for line in original_content.splitlines()
    ]
    normalized_content = '\n'.join(normalized_lines)
    if original_content.endswith('\n'):
        normalized_content += '\n'
    normalized_content = _enforce_notifycmd_line(normalized_content)

    if normalized_content == original_content:
        return False

    with open(UPSMON_CONF_PATH, 'w') as file_handle:
        file_handle.write(normalized_content)

    logger.warning("Normalized upsmon.conf MONITOR/NOTIFYCMD entries before startup")
    system_logger.warning("Normalized upsmon.conf MONITOR/NOTIFYCMD entries before startup")
    return True

def test_ups_connection(ups_name, ups_host):
    """
    Test connection to UPS using upsc command
    
    Args:
        ups_name (str): UPS name
        ups_host (str): UPS host
        
    Returns:
        tuple: (success, output) where success is boolean and output is command output
    """
    try:
        if not ups_name or not ups_host:
            logger.error("❌ Missing UPS name or host for testing connection")
            return False, "Missing UPS name or host"
            
        ups_spec = f"{ups_name}@{ups_host}"
        logger.info(f"🔌 Testing UPS connection to {ups_spec}")
        system_logger.info(f"🔌 Testing UPS connection to {ups_spec}")
        
        command = f"{UPSC_BIN} {ups_spec}"
        system_logger.info(f"📋 Executing command: {command}")
        logger.info(f"⏱️ Waiting for response from UPS at {ups_host}...")
        
        start_time = time.time()
        system_logger.info(f"⏱️ Starting upsc test at {time.strftime('%H:%M:%S')}")
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True,
            text=True,
            timeout=10
        )
        elapsed_time = time.time() - start_time
        system_logger.info(f"⏱️ upsc test completed in {elapsed_time:.2f}s")
        
        if result.returncode != 0:
            error_msg = f"❌ Error connecting to UPS {ups_spec}: {result.stderr.strip()}"
            logger.error(error_msg)
            system_logger.error(error_msg)
            return False, error_msg
            
        output = result.stdout.strip()
        logger.info(f"✅ Successfully connected to UPS {ups_spec} in {elapsed_time:.2f} seconds")
        system_logger.info(f"✅ Successfully connected to UPS {ups_spec}")
                
        return True, output
    except subprocess.TimeoutExpired:
        error_msg = f"⏱️ Timeout connecting to UPS {ups_name}@{ups_host} after 10 seconds"
        logger.error(error_msg)
        system_logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"❌ Error testing UPS connection: {str(e)}"
        logger.error(error_msg)
        system_logger.error(error_msg)
        return False, error_msg

def start_nut_services(wait_time=None):
    """
    Start all NUT services in the correct order
    
    Args:
        wait_time (int): Time to wait between starting services in seconds
        
    Returns:
        dict: Dictionary with start status for each service
        
    Raises:
        NUTConfigError: If NUT configuration is missing or invalid
        NUTStartupError: If services fail to start
    """

####### FROM HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######
####### FROM HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######
####### FROM HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######
####### FROM HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######
####### FROM HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######    
    # Check for macOS and apply compatibility fixes if needed
    try:
        import sys
        if sys.platform == 'darwin':
            logger.info("Running on macOS, applying additional compatibility settings")
            import eventlet.debug
            eventlet.debug.hub_prevent_multiple_readers(False)
    except Exception as e:
        logger.debug(f"Could not apply macOS compatibility settings: {e}")
####### FROM HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######
####### FROM HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######
####### FROM HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######
####### FROM HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######
####### FROM HERE - MACOS DEVELOPMENT COMPATIBILITY - REMOVE IN PRODUCTION #######   
    
    start_timestamp = time.time()
    logger.info("============================================================")
    logger.info("=====               STARTING NUT SERVICES              =====")
    logger.info("============================================================")
    
    # Use configured wait time if not specified
    if wait_time is None:
        wait_time = NUT_SERVICE_WAIT_TIME
        
    # Check if all configuration files exist
    system_logger.info(f"NUT startup - Checking configuration files at {time.strftime('%H:%M:%S')}")
    is_configured, missing_files = check_nut_config_files()
    if not is_configured:
        error_msg = f"Required NUT configuration files are missing: {', '.join(missing_files)}"
        logger.error(error_msg)
        raise NUTConfigError(error_msg)

    try:
        normalize_upsmon_configuration_file()
    except Exception as normalize_error:
        logger.warning(f"Could not normalize upsmon.conf before startup: {normalize_error}")
        
    # Check execution permissions on the binary files
    logger.debug("🔍 DEBUG - Checking execution permissions on NUT binaries")
    if not os.access(UPSDRVCTL_BIN, os.X_OK):
        logger.warning(f"⚠️ {UPSDRVCTL_BIN} is not executable")
    else:
        logger.debug(f"✅ {UPSDRVCTL_BIN} is executable")
        
    if not os.access(UPSD_BIN, os.X_OK):
        logger.warning(f"⚠️ {UPSD_BIN} is not executable")
    else:
        logger.debug(f"✅ {UPSD_BIN} is executable")
        
    if not os.access(UPSMON_BIN, os.X_OK):
        logger.warning(f"⚠️ {UPSMON_BIN} is not executable")
    else:
        logger.debug(f"✅ {UPSMON_BIN} is executable")
        
    # Ensure directories exist
    os.makedirs(NUT_RUN_DIR, exist_ok=True)
    os.makedirs(NUT_LOG_DIR, exist_ok=True)
    os.makedirs(NUT_STATE_DIR, exist_ok=True)
    
    # Set permissions
    try:
        os.chmod(NUT_RUN_DIR, 0o755)
        os.chmod(NUT_LOG_DIR, 0o755)
        os.chmod(NUT_STATE_DIR, 0o755)
    except Exception as e:
        logger.warning(f"Could not set permissions on NUT directories: {str(e)}")
    
    # Try direct access to check permissions on critical directories
    for dir_path in [NUT_RUN_DIR, NUT_LOG_DIR, NUT_STATE_DIR]:
        if not os.access(dir_path, os.W_OK):
            logger.warning(f"⚠️ Directory {dir_path} is not writable")
        else:
            logger.debug(f"✅ Directory {dir_path} is writable")
            
    # Check read permissions on config files
    for conf_file in [NUT_CONF_PATH, UPS_CONF_PATH, UPSD_CONF_PATH, UPSD_USERS_PATH, UPSMON_CONF_PATH]:
        if os.path.exists(conf_file):
            if not os.access(conf_file, os.R_OK):
                logger.warning(f"⚠️ File {conf_file} is not readable")
            else:
                logger.debug(f"✅ File {conf_file} is readable")
                
    # Determine NUT mode to adjust startup behavior
    nut_mode = get_nut_mode()
    is_netclient = nut_mode == 'netclient'
    
    logger.info(f"🔍 Detected NUT mode: {nut_mode}")
    if is_netclient:
        logger.info("📡 Operating in NETCLIENT mode - will connect to a remote NUT server")
        logger.info("🔧 Services that will be started: upsmon (monitor only)")
    else:
        if nut_mode == 'standalone':
            logger.info("💻 Operating in STANDALONE mode - UPS connected to this machine")
        elif nut_mode == 'netserver':
            logger.info("🖥️ Operating in NETSERVER mode - serving UPS data to network clients")
        logger.info("🔧 Services that will be started: upsdrvctl (drivers), upsd (server), upsmon (monitor)")
    
    results = {
        'upsdrvctl': {'success': False, 'error': None},
        'upsd': {'success': False, 'error': None},
        'upsmon': {'success': False, 'error': None}
    }
    
    # Start services in the correct order
    logger.info("🚀 Starting NUT services (this may take several seconds)...")
    try:
        # Stop any running services first to avoid conflicts
        try:
            logger.info("Stopping any running NUT services first...")
            system_logger.info(f"NUT startup - Stopping any running services at {time.strftime('%H:%M:%S')}")
            
            # Explicitly log the commands being executed (like in wizard mode)
            logger.debug(f"🔍 DEBUG - Running stop monitor command: {NUT_STOP_MONITOR_CMD}")
            stop_monitor_result = subprocess.run(NUT_STOP_MONITOR_CMD, shell=True, check=False, capture_output=True, text=True, timeout=5)
            if stop_monitor_result.stdout.strip():
                logger.debug(f"Monitor stop stdout: {stop_monitor_result.stdout.strip()}")
            if stop_monitor_result.stderr.strip():
                logger.debug(f"Monitor stop stderr: {stop_monitor_result.stderr.strip()}")
            
            time.sleep(1)
            
            logger.debug(f"🔍 DEBUG - Running stop server command: {NUT_STOP_SERVER_CMD}")
            stop_server_result = subprocess.run(NUT_STOP_SERVER_CMD, shell=True, check=False, capture_output=True, text=True, timeout=5)
            if stop_server_result.stdout.strip():
                logger.debug(f"Server stop stdout: {stop_server_result.stdout.strip()}")
            if stop_server_result.stderr.strip():
                logger.debug(f"Server stop stderr: {stop_server_result.stderr.strip()}")
            
            time.sleep(1)
            
            logger.debug(f"🔍 DEBUG - Running stop driver command: {NUT_STOP_DRIVER_CMD}")
            stop_driver_result = subprocess.run(NUT_STOP_DRIVER_CMD, shell=True, check=False, capture_output=True, text=True, timeout=5)
            if stop_driver_result.stdout.strip():
                logger.debug(f"Driver stop stdout: {stop_driver_result.stdout.strip()}")
            if stop_driver_result.stderr.strip():
                logger.debug(f"Driver stop stderr: {stop_driver_result.stderr.strip()}")
            
            time.sleep(wait_time)
            logger.info("✅ Successfully stopped any previously running NUT services")
        except Exception as e:
            logger.warning(f"Error stopping existing services (this is usually fine): {str(e)}")
        
        # In netclient mode, we only need upsmon, not drivers or server
        if is_netclient:
            logger.info("Running in netclient mode, skipping driver and server startup")
            system_logger.info(f"NUT startup - Netclient mode, skipping driver and server startup at {time.strftime('%H:%M:%S')}")
            results['upsdrvctl']['success'] = True
            results['upsd']['success'] = True
            
            # Start UPS monitor directly
            system_logger.info(f"NUT startup - Starting UPS monitor at {time.strftime('%H:%M:%S')}")
        else:
            # 1. Start UPS drivers - Use direct command execution like in wizard for better logging
            logger.info("Starting NUT driver controller")
            
            # Try the direct command approach first (like in wizard)
            direct_driver_cmd = [UPSDRVCTL_BIN, "-u", "root", "start"]
            logger.debug(f"🔍 DEBUG - Running direct driver command: {' '.join(direct_driver_cmd)}")
            
            driver_result = subprocess.run(
                direct_driver_cmd, 
                capture_output=True, 
                text=True,
                timeout=NUT_SERVICE_START_TIMEOUT
            )
            
            # Log full command output regardless of success
            if driver_result.stdout.strip():
                logger.info(f"Driver command stdout: {driver_result.stdout.strip()}")
            if driver_result.stderr.strip():
                logger.info(f"Driver command stderr: {driver_result.stderr.strip()}")
            
            # Check if drivers started successfully
            if driver_result.returncode != 0:
                logger.warning(f"Failed to start UPS drivers with direct command: {driver_result.stderr.strip()}")
                
                # Try again with the original command
                logger.info("Trying fallback with original upsdrvctl command...")
                logger.debug(f"🔍 DEBUG - Fallback driver command: {NUT_START_DRIVER_CMD}")
                
                fallback_start = time.time()
                fallback_result = subprocess.run(
                    NUT_START_DRIVER_CMD, 
                    shell=True,
                    capture_output=True, 
                    text=True,
                    timeout=NUT_SERVICE_START_TIMEOUT
                )
                
                fallback_elapsed = time.time() - fallback_start
                system_logger.info(f"NUT startup - Fallback driver command completed in {fallback_elapsed:.2f}s")
                
                if fallback_result.stdout.strip():
                    logger.info(f"Fallback driver command stdout: {fallback_result.stdout.strip()}")
                if fallback_result.stderr.strip():
                    logger.info(f"Fallback driver command stderr: {fallback_result.stderr.strip()}")
                
                if fallback_result.returncode == 0:
                    logger.info("✅ Fallback UPS drivers started successfully")
                    results['upsdrvctl']['success'] = True
                    # Clear error since fallback succeeded
                    results['upsdrvctl']['error'] = None
                else:
                    error_msg = f"Failed to start UPS drivers: {fallback_result.stderr.strip()}"
                    logger.warning(error_msg)
                    results['upsdrvctl']['error'] = error_msg
            else:
                logger.info("✅ UPS drivers started successfully")
                results['upsdrvctl']['success'] = True
                
            # Wait for drivers to initialize
            time.sleep(wait_time)
            
            # 2. Start UPS server - Use direct command execution like in wizard
            logger.info("Starting NUT server (upsd)")
            
            # Try direct command first (like in wizard)
            direct_server_cmd = [UPSD_BIN, "-u", "root"]
            logger.debug(f"🔍 DEBUG - Running direct server command: {' '.join(direct_server_cmd)}")
            
            server_result = subprocess.run(
                direct_server_cmd, 
                capture_output=True, 
                text=True,
                timeout=10
            )
            
            # Log full command output regardless of success
            if server_result.stdout.strip():
                logger.info(f"Server command stdout: {server_result.stdout.strip()}")
            if server_result.stderr.strip():
                logger.info(f"Server command stderr: {server_result.stderr.strip()}")
                
            # Check if server started successfully
            if server_result.returncode != 0:
                logger.warning(f"Failed to start UPS server with direct command: {server_result.stderr.strip()}")
                
                # Try again with the original command
                logger.info("Trying fallback with original upsd command...")
                logger.debug(f"🔍 DEBUG - Fallback server command: {NUT_START_SERVER_CMD}")
                
                fallback_start = time.time()
                fallback_result = subprocess.run(
                    NUT_START_SERVER_CMD, 
                    shell=True,
                    capture_output=True, 
                    text=True,
                    timeout=10
                )
                
                fallback_elapsed = time.time() - fallback_start
                system_logger.info(f"NUT startup - Fallback server command completed in {fallback_elapsed:.2f}s")
                
                if fallback_result.stdout.strip():
                    logger.info(f"Fallback server command stdout: {fallback_result.stdout.strip()}")
                if fallback_result.stderr.strip():
                    logger.info(f"Fallback server command stderr: {fallback_result.stderr.strip()}")
                
                if fallback_result.returncode == 0:
                    logger.info("✅ Fallback UPS server started successfully")
                    results['upsd']['success'] = True
                    # Clear error since fallback succeeded
                    results['upsd']['error'] = None
                else:
                    error_msg = f"Failed to start UPS server: {fallback_result.stderr.strip()}"
                    logger.warning(error_msg)
                    results['upsd']['error'] = error_msg
            else:
                logger.info("✅ UPS server started successfully")
                results['upsd']['success'] = True
                
            # Wait for server to initialize
            time.sleep(wait_time)
        
        # 3. Start UPS monitor - Use direct command execution like in wizard
        logger.info("Starting UPS monitor")
        
        # Add timing info for monitor startup - this is often where the delay happens
        monitor_start_time = time.time()
        system_logger.info(f"NUT startup - Executing monitor command at {time.strftime('%H:%M:%S')}")
        
        # Try direct command first (like in wizard)
        direct_monitor_cmd = [UPSMON_BIN, "-u", "root"]
        logger.debug(f"🔍 DEBUG - Running direct monitor command: {' '.join(direct_monitor_cmd)}")
        
        monitor_result = subprocess.run(
            direct_monitor_cmd, 
            capture_output=True, 
            text=True,
            timeout=10
        )
        
        monitor_elapsed = time.time() - monitor_start_time
        system_logger.info(f"NUT startup - Monitor command completed in {monitor_elapsed:.2f}s at {time.strftime('%H:%M:%S')}")
        
        # Log full command output regardless of success
        if monitor_result.stdout.strip():
            logger.info(f"Monitor command stdout: {monitor_result.stdout.strip()}")
        if monitor_result.stderr.strip():
            logger.info(f"Monitor command stderr: {monitor_result.stderr.strip()}")
            system_logger.info(f"NUT monitor stderr: {monitor_result.stderr.strip()}")
            
        # Check if monitor started successfully
        if monitor_result.returncode != 0:
            logger.warning(f"Failed to start UPS monitor with direct command: {monitor_result.stderr.strip()}")
            system_logger.warning(f"NUT startup - Failed to start UPS monitor with direct command")
            
            # Try again with the original command
            logger.info("Trying fallback with original upsmon command...")
            system_logger.info(f"NUT startup - Trying fallback upsmon command at {time.strftime('%H:%M:%S')}")
            
            fallback_start = time.time()
            fallback_result = subprocess.run(
                NUT_START_MONITOR_CMD, 
                shell=True,
                capture_output=True, 
                text=True,
                timeout=10
            )
            
            fallback_elapsed = time.time() - fallback_start
            system_logger.info(f"NUT startup - Fallback monitor command completed in {fallback_elapsed:.2f}s")
            
            if fallback_result.stdout.strip():
                logger.info(f"Fallback monitor command stdout: {fallback_result.stdout.strip()}")
            if fallback_result.stderr.strip():
                logger.info(f"Fallback monitor command stderr: {fallback_result.stderr.strip()}")
            
            if fallback_result.returncode == 0:
                logger.info("✅ Fallback UPS monitor started successfully")
                results['upsmon']['success'] = True
                # Clear error since fallback succeeded
                results['upsmon']['error'] = None
            else:
                error_msg = f"Failed to start UPS monitor: {fallback_result.stderr.strip()}"
                logger.warning(error_msg)
                results['upsmon']['error'] = error_msg
        else:
            logger.info("✅ UPS monitor started successfully")
            system_logger.info(f"NUT startup - UPS monitor started successfully")
            results['upsmon']['success'] = True
        
        # Verify the status of each service after waiting
        wait_start = time.time()
        logger.info(f"⏱️ Waiting {wait_time * 2}s for services to fully initialize...")
        system_logger.info(f"NUT startup - Waiting {wait_time * 2}s for services to fully initialize...")
        
        # Split the wait into smaller chunks with status updates
        chunk_size = 1
        for i in range(wait_time * 2):
            time.sleep(chunk_size)
            if i % 2 == 0:  # Log every 2 seconds
                elapsed = i + 1
                system_logger.info(f"NUT startup - Initialization wait: {elapsed}/{wait_time * 2}s")
        
        system_logger.info(f"NUT startup - Completed initialization wait in {time.time() - wait_start:.2f}s")
        
        # Check the status of services quietly (without logging each check)
        status_start = time.time()
        system_logger.info(f"NUT startup - Checking service status at {time.strftime('%H:%M:%S')}")
        status = check_all_services_status()
        system_logger.info(f"NUT startup - Service status check completed in {time.time() - status_start:.2f}s")
        
        # Test UPS connection if needed
        if 'upsd' in status and status['upsd'] and nut_mode != 'netclient':
            try:
                logger.debug("Testing UPS connection...")
                
                # Get UPS name and host from monitor config instead of using undefined driver_config
                ups_name, ups_host = get_ups_monitor_config()
                
                if ups_name and ups_host:
                    upsc_cmd = [UPSC_BIN, f"{ups_name}@{ups_host}"]
                    
                    ups_result = subprocess.run(upsc_cmd, capture_output=True, text=True, timeout=5)
                    
                    if ups_result.returncode == 0:
                        logger.debug(f"UPS connection successful: {ups_result.stdout.strip()}")
                    else:
                        logger.warning(f"UPS connection test failed: {ups_result.stderr.strip()}")
                else:
                    logger.warning("Cannot test UPS connection: missing UPS name or host")
            except Exception as e:
                logger.warning(f"Error testing UPS connection: {str(e)}")
        
        # Summarize the results - This is the only place we'll log service status
        summary = ["NUT services status:"]
        all_success = True
        
        # Create a list of critical services based on the mode
        critical_services = []
        if nut_mode == 'netclient':
            critical_services = ['upsmon']
        elif nut_mode == 'standalone':
            critical_services = ['upsdrvctl', 'upsd', 'upsmon']
        elif nut_mode == 'netserver':
            critical_services = ['upsdrvctl', 'upsd']
        
        # Check if critical services are running
        critical_failures = []
        for service in critical_services:
            if service in status and not status[service]:
                critical_failures.append(service)
                all_success = False
        
        # Log status of all services we checked
        for service, is_running in status.items():
            status_icon = "✅" if is_running else "❌"
            status_text = "running" if is_running else "NOT running"
            summary.append(f"  {status_icon} Service {service} is {status_text}")
        
        # For netclient mode, check if upsc works even if upsmon failed
        upsc_works = False
        if nut_mode == 'netclient' and not all_success:
            logger.info("Netclient mode: upsmon failed, but checking if upsc works directly...")
            system_logger.info("Netclient mode: checking if upsc command works directly...")
            ups_name, ups_host = get_ups_monitor_config()
            if ups_name and ups_host:
                success, output = test_ups_connection(ups_name, ups_host)
                system_logger.info(f"upsc connection test result: {'Success' if success else 'Failed'}")
                if success:
                    logger.info("✅ upsc command works successfully even though upsmon failed")
                    upsc_works = True
                    logger.info(f"  ✅ upsc {ups_name}@{ups_host} works successfully")
                    system_logger.warning(f"⚠️ upsmon failed but upsc works in {nut_mode} mode, continuing anyway")
                else:
                    logger.warning(f"❌ upsc command also failed: {output}")
                    system_logger.warning(f"❌ upsc command also failed")
        
        # Log final status based on critical services
        if all_success:
            if nut_mode == 'netclient':
                # Log each line separately instead of joining with newlines
                logger.info("NUT services status:")
                for service, is_running in status.items():
                    status_icon = "✅" if is_running else "❌"
                    status_text = "running" if is_running else "NOT running"
                    logger.info(f"  {status_icon} Service {service} is {status_text}")
                logger.info(f"✅ Successfully started NUT in {nut_mode} mode")
            elif nut_mode == 'standalone':
                # Log each line separately instead of joining with newlines
                logger.info("NUT services status:")
                for service, is_running in status.items():
                    status_icon = "✅" if is_running else "❌"
                    status_text = "running" if is_running else "NOT running"
                    logger.info(f"  {status_icon} Service {service} is {status_text}")
                logger.info(f"✅ Successfully started NUT in {nut_mode} mode")
            elif nut_mode == 'netserver':
                # Log each line separately instead of joining with newlines
                logger.info("NUT services status:")
                for service, is_running in status.items():
                    status_icon = "✅" if is_running else "❌"
                    status_text = "running" if is_running else "NOT running"
                    logger.info(f"  {status_icon} Service {service} is {status_text}")
                logger.info(f"✅ Successfully started NUT in {nut_mode} mode")
        else:
            # For netclient mode, consider it a success if upsc works even if upsmon failed
            if nut_mode == 'netclient' and upsc_works:
                # Log each line separately with proper logger
                logger.info("NUT services status:")
                for service, is_running in status.items():
                    status_icon = "✅" if is_running else "❌"
                    status_text = "running" if is_running else "NOT running"
                    logger.info(f"  {status_icon} Service {service} is {status_text}")
                # Use system_logger instead of logger for the warning message to ensure consistent formatting
                system_logger.warning(f"⚠️ upsmon failed but upsc works in {nut_mode} mode, continuing anyway")
                return results
            else:
                # Log error status
                logger.error("NUT services status:")
                for service, is_running in status.items():
                    status_icon = "✅" if is_running else "❌"
                    status_text = "running" if is_running else "NOT running"
                    logger.error(f"  {status_icon} Service {service} is {status_text}")
                err_msg = f"Failed to start critical services for {nut_mode} mode: {', '.join(critical_failures)}"
                logger.error(f"❌ {err_msg}")
                raise NUTStartupError(err_msg)
        
        return results
    
    except subprocess.TimeoutExpired as e:
        error_msg = f"Timeout starting NUT services: {str(e)}"
        logger.error(error_msg)
        raise NUTStartupError(error_msg)
    except Exception as e:
        error_msg = f"Error starting NUT services: {str(e)}"
        logger.error(error_msg)
        raise NUTStartupError(error_msg)

def stop_nut_services(wait_time=None):
    """
    Stop all NUT services in the correct order
    
    Args:
        wait_time (int): Time to wait between stopping services in seconds
        
    Returns:
        dict: Dictionary with stop status for each service
    """
    # Use configured wait time if not specified
    if wait_time is None:
        wait_time = NUT_SERVICE_WAIT_TIME
        
    results = {
        'upsmon': {'success': False, 'error': None},
        'upsd': {'success': False, 'error': None},
        'upsdrvctl': {'success': False, 'error': None}
    }
    
    # Stop in reverse order of starting
    try:
        # 1. Stop UPS monitor
        logger.info("Stopping UPS monitor...")
        result = subprocess.run(
            NUT_STOP_MONITOR_CMD,
            shell=True,
            capture_output=True, 
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            error_msg = f"Failed to stop UPS monitor: {result.stderr.strip()}"
            logger.error(error_msg)
            results['upsmon']['error'] = error_msg
        else:
            logger.info("UPS monitor stopped successfully")
            results['upsmon']['success'] = True
            
        # Wait for monitor to stop
        time.sleep(wait_time)
        
        # 2. Stop UPS server
        logger.info("Stopping UPS server...")
        result = subprocess.run(
            NUT_STOP_SERVER_CMD,
            shell=True,
            capture_output=True, 
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            error_msg = f"Failed to stop UPS server: {result.stderr.strip()}"
            logger.error(error_msg)
            results['upsd']['error'] = error_msg
        else:
            logger.info("UPS server stopped successfully")
            results['upsd']['success'] = True
            
        # Wait for server to stop
        time.sleep(wait_time)
        
        # 3. Stop UPS drivers
        logger.info("Stopping UPS drivers...")
        result = subprocess.run(
            NUT_STOP_DRIVER_CMD,
            shell=True,
            capture_output=True, 
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            error_msg = f"Failed to stop UPS drivers: {result.stderr.strip()}"
            logger.error(error_msg)
            results['upsdrvctl']['error'] = error_msg
        else:
            logger.info("UPS drivers stopped successfully")
            results['upsdrvctl']['success'] = True
            
        return results
    
    except subprocess.TimeoutExpired as e:
        error_msg = f"Timeout stopping NUT services: {str(e)}"
        logger.error(error_msg)
        
        # Attempt to forcefully stop any running services
        try:
            logger.warning("Attempting to forcefully stop any running services...")
            # Don't really need to check results here, just best effort
            subprocess.run(NUT_STOP_MONITOR_CMD, shell=True, timeout=5, check=False)
            subprocess.run(NUT_STOP_SERVER_CMD, shell=True, timeout=5, check=False)
            subprocess.run(NUT_STOP_DRIVER_CMD, shell=True, timeout=5, check=False)
        except Exception as inner_e:
            logger.error(f"Error in cleanup: {str(inner_e)}")
            
        raise NUTShutdownError(error_msg)
    except Exception as e:
        error_msg = f"Error stopping NUT services: {str(e)}"
        logger.error(error_msg)
        raise NUTShutdownError(error_msg)

def restart_nut_services(wait_time=None):
    """
    Restart all NUT services
    
    Args:
        wait_time (int): Time to wait between stopping and starting services in seconds
        
    Returns:
        dict: Dictionary with restart status
    """
    logger.info("Restarting NUT services...")
    
    # Use configured wait time if not specified
    if wait_time is None:
        wait_time = NUT_SERVICE_WAIT_TIME
        
    results = {
        'stop': {},
        'start': {},
        'success': False
    }
    
    try:
        # Stop services
        logger.info("Stopping services...")
        results['stop'] = stop_nut_services(wait_time)
        
        # Wait before starting
        time.sleep(wait_time)
        
        # Start services
        logger.info("Starting services...")
        results['start'] = start_nut_services(wait_time)
        
        # Check final status
        final_status = check_all_services_status()
        logger.info(f"Final status after restart: {final_status}")
        
        # Consider success only if all services are running
        results['success'] = all(final_status.values())
        
        return results
    except Exception as e:
        logger.error(f"Error restarting NUT services: {str(e)}")
        results['success'] = False
        results['error'] = str(e)
        return results

def get_service_logs(service_name, lines=50):
    """
    Get logs for a specific NUT service
    
    Args:
        service_name (str): Name of the service ('upsdrvctl', 'upsd', 'upsmon')
        lines (int): Number of lines to return
        
    Returns:
        str: Service logs
    """
    try:
        # Determine the log file path based on service name
        if service_name == 'upsdrvctl':
            log_file = os.path.join(NUT_LOG_DIR, NUT_DRIVER_LOG)
        elif service_name == 'upsd':
            log_file = os.path.join(NUT_LOG_DIR, NUT_SERVER_LOG)
        elif service_name == 'upsmon':
            log_file = os.path.join(NUT_LOG_DIR, NUT_UPSMON_LOG)
        elif service_name == 'notifier':
            log_file = os.path.join(NUT_LOG_DIR, NUT_NOTIFIER_LOG)
        else:
            return f"Unknown service: {service_name}"
            
        # Check if log file exists
        if not os.path.exists(log_file):
            return f"Log file not found: {log_file}"
            
        # Get the last N lines of the log file
        result = subprocess.run(['tail', '-n', str(lines), log_file], capture_output=True, text=True)
        
        if result.returncode != 0:
            return f"Error getting logs: {result.stderr}"
            
        return result.stdout
    except Exception as e:
        logger.error(f"Error getting logs for {service_name}: {str(e)}")
        return f"Error getting logs: {str(e)}" 
