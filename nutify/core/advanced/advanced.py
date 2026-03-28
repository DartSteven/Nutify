"""
Core functionality for the advanced NUT configuration module.
Provides functions to read and write NUT configuration files and restart NUT services.
"""

import os
import subprocess
import re
from typing import Dict, List, Tuple, Any, Optional
import shutil
from core.logger import system_logger as logger
from datetime import datetime
from core.settings import (
    NUT_CONF_DIR,
    UPSDRVCTL_BIN,
    UPSD_BIN,
    UPSMON_BIN,
    CERTFILE,
    KEYFILE,
    CERTPATH,
    CERTFILE_PATH,
    KEYFILE_PATH,
    CERTPATH_DIR,
    NUT_START_DRIVER_CMD, 
    NUT_START_SERVER_CMD, 
    NUT_START_MONITOR_CMD,
    NUT_STOP_DRIVER_CMD, 
    NUT_STOP_SERVER_CMD, 
    NUT_STOP_MONITOR_CMD,
    NUT_RUN_DIR,
    NUT_LOG_DIR,
    NUT_STATE_DIR
)
import time

# Define NUT configuration directory
# Use the configured path from settings instead of hardcoding
NUT_CONFIG_DIR = NUT_CONF_DIR

# Define known NUT files and their documentation
NUT_FILES = {
    "nut.conf": {
        "description": "Main NUT configuration file that determines the mode of operation of NUT. This file controls the global behavior of NUT services.",
        "documentation": {
            "MODE": "The mode of operation for NUT. Values: none, standalone, netserver, netclient"
        }
    },
    "ups.conf": {
        "description": "Configuration file for UPS devices. Defines UPS driver settings and connection parameters for each UPS device that NUT will monitor.",
        "documentation": {
            "driver": "Driver for the UPS. Example: usbhid-ups",
            "port": "Port or device name for the UPS. Example: auto",
            "desc": "Description of the UPS. Example: Server room UPS",
            "vendorid": "USB vendor ID for the UPS (for USB connections). Example: 051D",
            "productid": "USB product ID for the UPS (for USB connections). Example: 0002",
            "serial": "Serial number of the UPS. Example: ABC123456",
            "vendor": "Vendor name of the UPS. Example: APC",
            "product": "Product name of the UPS. Example: Smart-UPS 1500",
            "pollinterval": "Polling interval in seconds. Example: 2",
            "community": "SNMP community string (for SNMP UPS). Example: public",
            "snmp_version": "SNMP version to use (for SNMP UPS). Values: v1, v2c, v3",
            "mibs": "MIBs to use with SNMP UPS. Example: ietf",
            "notifyflag": "Notification flags for specific events. Format: event=action",
            "maxretry": "Maximum number of retries before failure. Example: 3",
            "retrydelay": "Delay between retries in seconds. Example: 5",
            "synchronous": "Enable/disable synchronous communication. Values: yes, no"
        }
    },
    "upsd.conf": {
        "description": "Configuration file for the NUT server daemon (upsd). Controls how the NUT server communicates with clients and provides access to UPS data.",
        "documentation": {
            "LISTEN": "Interface to listen on. Example: 127.0.0.1",
            "LISTEN_BACKLOG": "Maximum number of backlog connections. Example: 16",
            "MAXAGE": "Maximum age of data in seconds before being marked stale. Example: 15",
            "STATEPATH": "Path to the state file directory. Example: /var/run/nut",
            "MAXCONN": "Maximum number of connections. Example: 1024",
            "CERTFILE": f"Path to the SSL certificate file for encrypted connections. Example: {CERTFILE_PATH}",
            "KEYFILE": f"Path to the SSL key file for encrypted connections. Example: {KEYFILE_PATH}",
            "ALLOW_UNSIGNED_DATA": "Allow unsigned data for connections. Values: yes, no",
            "REJECT_UNKNOWN_CLIENTS": "Reject connections from unknown clients. Values: yes, no",
            "ACCEPT_COMMAND": "Commands to accept from clients. Example: ALL",
            "SERVERPATH": "Path for the socket file. Example: /var/run/nut"
        }
    },
    "upsd.users": {
        "description": "User access control for NUT server. Defines users that can connect to the NUT server and their permissions for various UPS devices.",
        "documentation": {
            "password": "User password for authentication. Example: mypassword",
            "actions": "Allowed actions for this user. Example: SET FSD",
            "instcmds": "Allowed instant commands for this user. Example: test.battery.start",
            "upsmon": "UPS monitoring capabilities for this user. Values: master, slave",
            "allowfrom": "IP addresses to accept connections from. Example: 192.168.1.0/24",
            "username": "Username for authentication (defined as a section). Example: [admin]",
            "passwordQuality": "Quality check for password. Values: disabled, weak, secure",
            "upsname": "UPS name for which permissions apply. Format: upsname.attribute"
        }
    },
    "upsmon.conf": {
        "description": "Configuration file for UPS monitoring daemon (upsmon). Controls how the system monitors UPS devices and reacts to changes in UPS status.",
        "documentation": {
            "MONITOR": "UPS to monitor with login information. Format: upsname@host username password type",
            "MINSUPPLIES": "Minimum number of power supplies required for system to stay up. Example: 1",
            "SHUTDOWNCMD": "Command to run for system shutdown. Example: /sbin/shutdown -h +0",
            "NOTIFYCMD": "Command to run for notifications. Example: /usr/local/bin/notify-script",
            "POLLFREQ": "Poll frequency in seconds. Example: 5",
            "POLLFREQALERT": "Poll frequency during alerts in seconds. Example: 1",
            "HOSTSYNC": "Time in seconds to wait for slave hosts to disconnect. Example: 15",
            "DEADTIME": "Time in seconds before declaring a UPS dead. Example: 15",
            "POWERDOWNFLAG": "File to indicate power down in progress. Example: /etc/killpower",
            "NOTIFYMSG": "Custom notification message. Format: type \"message\"",
            "NOTIFYFLAG": "Notification flags for specific events. Format: event action",
            "RBWARNTIME": "Warning time for remaining battery in seconds. Example: 300",
            "NOCOMMWARNTIME": "Warning time for no communication in seconds. Example: 300",
            "FINALDELAY": "Final delay before shutdown in seconds. Example: 5",
            "RUN_AS_USER": "User to run upsmon as. Example: nut",
            "CERTPATH": f"Path to SSL certificate for secure connections. Example: {CERTPATH_DIR}",
            "CERTIDENT": "Certificate identification string. Example: client",
            "CERTVERIFY": "Certificate verification depth. Example: 3"
        }
    }
}

def get_available_nut_files() -> List[Dict[str, Any]]:
    """
    Get a list of available NUT configuration files.
    
    Returns:
        List of dictionaries with file information:
        - name: Filename
        - path: Full path to the file
        - size: File size in bytes
        - modified: Last modification time (ISO format)
        - description: Description of the file's purpose
    """
    available_files = []
    
    # Check if the NUT directory exists
    if not os.path.exists(NUT_CONFIG_DIR):
        logger.warning(f"NUT configuration directory {NUT_CONFIG_DIR} does not exist")
        return available_files
    
    # Get list of files in the NUT directory
    try:
        files = os.listdir(NUT_CONFIG_DIR)
        
        # Filter for known NUT configuration files
        for filename in files:
            if filename in NUT_FILES:
                file_path = os.path.join(NUT_CONFIG_DIR, filename)
                stat = os.stat(file_path)
                
                available_files.append({
                    "name": filename,
                    "path": file_path,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "description": NUT_FILES.get(filename, {}).get("description", "")
                })
    except Exception as e:
        logger.error(f"Error reading NUT configuration directory: {str(e)}")
    
    return available_files

def get_nut_file_documentation(filename: str) -> Dict[str, str]:
    """
    Get documentation for a specific NUT configuration file.
    
    This function returns a dictionary with parameter names as keys and 
    their descriptions as values. The documentation includes examples and
    possible values where applicable.
    
    Args:
        filename: Name of the NUT configuration file (e.g., "nut.conf")
        
    Returns:
        Dictionary with parameter documentation
    """
    if filename in NUT_FILES:
        return NUT_FILES[filename].get("documentation", {})
    return {}

def read_nut_config_file(filename: str) -> Dict[str, Any]:
    """
    Read a NUT configuration file and return its contents.
    
    This function reads the specified NUT configuration file and returns
    its contents along with metadata and documentation.
    
    Args:
        filename: Name of the NUT configuration file (e.g., "nut.conf")
        
    Returns:
        Dictionary with:
        - success: Boolean indicating success/failure
        - name: Filename
        - path: Full path to the file
        - content: File content as string
        - size: File size in bytes
        - modified: Last modification time (ISO format)
        - documentation: Dictionary with parameter documentation
        - message: Error message (if success is False)
    """
    file_path = os.path.join(NUT_CONFIG_DIR, filename)
    
    # Check if the file exists
    if not os.path.exists(file_path):
        logger.error(f"NUT configuration file {file_path} does not exist")
        return {
            "success": False,
            "message": f"Configuration file {filename} does not exist",
            "content": "",
            "documentation": get_nut_file_documentation(filename)
        }
    
    # Read the file content
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Get file metadata
        stat = os.stat(file_path)
        
        return {
            "success": True,
            "name": filename,
            "path": file_path,
            "content": content,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "documentation": get_nut_file_documentation(filename),
            "description": NUT_FILES.get(filename, {}).get("description", "")
        }
    except Exception as e:
        logger.error(f"Error reading NUT configuration file {file_path}: {str(e)}")
        return {
            "success": False,
            "message": f"Error reading configuration file: {str(e)}",
            "content": "",
            "documentation": get_nut_file_documentation(filename)
        }

def write_nut_config_file(filename: str, content: str) -> Dict[str, Any]:
    """
    Write content to a NUT configuration file.
    
    This function writes the provided content to the specified NUT configuration
    file. It creates a backup of the original file before making changes.
    
    Args:
        filename: Name of the NUT configuration file (e.g., "nut.conf")
        content: Content to write to the file
        
    Returns:
        Dictionary with:
        - success: Boolean indicating success/failure
        - message: Success or error message
        - backup: Path to the backup file (if successful)
    """
    file_path = os.path.join(NUT_CONFIG_DIR, filename)
    backup_path = f"{file_path}.bak"
    
    # Check if the file exists
    if not os.path.exists(file_path):
        logger.error(f"NUT configuration file {file_path} does not exist")
        return {
            "success": False,
            "message": f"Configuration file {filename} does not exist"
        }
    
    # Create a backup of the file
    try:
        shutil.copy2(file_path, backup_path)
        logger.info(f"Created backup of {file_path} at {backup_path}")
    except Exception as e:
        logger.error(f"Error creating backup of {file_path}: {str(e)}")
        return {
            "success": False,
            "message": f"Error creating backup: {str(e)}"
        }
    
    # Write the file content
    try:
        with open(file_path, 'w') as f:
            f.write(content)

        if filename == 'upsmon.conf':
            try:
                from core.nut.nut_daemon import normalize_upsmon_configuration_file
                normalize_upsmon_configuration_file()
            except Exception as normalize_error:
                logger.warning(f"Could not normalize upsmon.conf after save: {normalize_error}")
        
        logger.info(f"Successfully wrote {file_path}")
        return {
            "success": True,
            "message": f"Successfully updated {filename}",
            "backup": backup_path
        }
    except Exception as e:
        logger.error(f"Error writing NUT configuration file {file_path}: {str(e)}")
        
        # Try to restore from backup
        try:
            shutil.copy2(backup_path, file_path)
            logger.info(f"Restored {file_path} from backup after write error")
        except Exception as restore_error:
            logger.error(f"Error restoring {file_path} from backup: {str(restore_error)}")
        
        return {
            "success": False,
            "message": f"Error writing configuration file: {str(e)}"
        }

def restart_nut_services() -> Dict[str, Any]:
    """
    Restart all NUT services in the correct order.
    First stop services in reverse order, then start them in forward order.
    
    Returns:
        Dict[str, Any]: Success status and message
    """
    logger.info("Restarting NUT services...")
    
    try:
        # Create necessary directories
        try:
            os.makedirs(NUT_RUN_DIR, exist_ok=True)
            os.makedirs(NUT_LOG_DIR, exist_ok=True)
            os.makedirs(NUT_STATE_DIR, exist_ok=True)
            
            # Set permissions
            os.chmod(NUT_RUN_DIR, 0o755)
            os.chmod(NUT_LOG_DIR, 0o755)
            os.chmod(NUT_STATE_DIR, 0o755)
        except Exception as e:
            logger.warning(f"Error setting up NUT directories: {str(e)}")
            
        # Check NUT mode
        nut_mode = None
        try:
            with open(os.path.join(NUT_CONF_DIR, 'nut.conf'), 'r') as f:
                for line in f:
                    if line.startswith('MODE='):
                        nut_mode = line.split('=', 1)[1].strip().strip('"\'')
                        logger.info(f"Detected NUT mode: {nut_mode}")
                        break
        except Exception as e:
            logger.warning(f"Error detecting NUT mode: {str(e)}")
            
        is_netclient = nut_mode == 'netclient'

        try:
            from core.nut.nut_daemon import normalize_upsmon_configuration_file
            normalize_upsmon_configuration_file()
        except Exception as normalize_error:
            logger.warning(f"Could not normalize upsmon.conf before restart: {normalize_error}")
            
        # Always use direct commands which are most reliable
        logger.info("Using direct commands to restart services...")
        
        # Try to stop services gracefully
        try:
            logger.info("Stopping UPS monitor...")
            subprocess.run(NUT_STOP_MONITOR_CMD, shell=True, check=False, capture_output=True, timeout=10)
            
            # Wait a moment
            time.sleep(1)
            
            logger.info("Stopping UPS daemon...")
            subprocess.run(NUT_STOP_SERVER_CMD, shell=True, check=False, capture_output=True, timeout=10)
            
            # Wait a moment
            time.sleep(1)
            
            logger.info("Stopping UPS drivers...")
            subprocess.run(NUT_STOP_DRIVER_CMD, shell=True, check=False, capture_output=True, timeout=10)
        except subprocess.SubprocessError as e:
            logger.warning(f"Some services didn't stop cleanly: {str(e)}")
        except subprocess.TimeoutExpired:
            logger.warning("Timeout while stopping services")
        
        # Small delay to ensure services have time to stop
        time.sleep(2)
        
        # Start services
        try:
            # In netclient mode, we only need upsmon
            if not is_netclient:
                logger.info("Starting UPS drivers...")
                driver_result = subprocess.run(NUT_START_DRIVER_CMD, shell=True, capture_output=True, text=True, timeout=20)
                if driver_result.returncode != 0:
                    logger.warning(f"Driver start warning: {driver_result.stdout} {driver_result.stderr}")
                else:
                    logger.info("UPS drivers started")
                
                # Wait a moment
                time.sleep(2)
                
                logger.info("Starting UPS daemon...")
                server_result = subprocess.run(NUT_START_SERVER_CMD, shell=True, capture_output=True, text=True, timeout=10)
                if server_result.returncode != 0:
                    logger.warning(f"Server start warning: {server_result.stdout} {server_result.stderr}")
                else:
                    logger.info("UPS server started")
                
                # Wait a moment
                time.sleep(2)
            else:
                logger.info("Skipping driver and server startup in netclient mode")
            
            logger.info("Starting UPS monitor...")
            monitor_result = subprocess.run(NUT_START_MONITOR_CMD, shell=True, capture_output=True, text=True, timeout=10)
            if monitor_result.returncode != 0:
                logger.warning(f"Monitor start warning: {monitor_result.stdout} {monitor_result.stderr}")
            else:
                logger.info("UPS monitor started")
            
            # Wait for services to start and become stable
            time.sleep(3)
            
            # Import the check function to verify services are running
            from core.nut.nut_daemon import check_all_services_status, get_ups_monitor_config, test_ups_connection
            
            # Check the status after restart
            status = check_all_services_status()
            logger.info(f"Service status after restart: {status}")
            
            # Test UPS connection with upsc
            ups_data = {}
            ups_connection_ok = False
            
            if is_netclient:
                # Get UPS monitor config from upsmon.conf
                ups_name, ups_host = get_ups_monitor_config()
                
                if ups_name and ups_host:
                    # Test connection to UPS
                    connection_success, connection_output = test_ups_connection(ups_name, ups_host)
                    if connection_success:
                        logger.info(f"Successfully connected to UPS {ups_name}@{ups_host}")
                        ups_connection_ok = True
                        ups_data = {
                            'ups': f"{ups_name}@{ups_host}",
                            'data': connection_output
                        }
                    else:
                        logger.warning(f"Failed to connect to UPS {ups_name}@{ups_host}: {connection_output}")
                else:
                    logger.warning("Could not determine UPS configuration for testing")
            
            # Consider success based on mode
            if is_netclient:
                # For netclient, success if upsmon is running or UPS connection works
                is_success = status['upsmon'] or ups_connection_ok
            else:
                # For other modes, at least one service should be running
                is_success = any(status.values())
            
            if is_success:
                logger.info("Successfully restarted NUT services")
                return {
                    "success": True,
                    "message": "Successfully restarted NUT services",
                    "status": status,
                    "ups_connection": ups_connection_ok,
                    "ups_data": ups_data
                }
            else:
                logger.error("Failed to restart NUT services")
                return {
                    "success": False,
                    "message": "Failed to restart any NUT services",
                    "status": status
                }
        except subprocess.SubprocessError as e:
            logger.error(f"Error starting services: {str(e)}")
            return {
                "success": False,
                "message": f"Error starting NUT services: {str(e)}"
            }
    except Exception as e:
        logger.error(f"Error restarting NUT services: {str(e)}")
        return {
            "success": False,
            "message": f"Error restarting NUT services: {str(e)}"
        } 
