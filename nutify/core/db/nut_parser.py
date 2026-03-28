"""
NUT Configuration Parser Module.

This module reads NUT configuration files and provides globally accessible
variables and functions for UPS connection parameters.
"""

import os
import re
import logging
import threading
from typing import Tuple, Dict, Optional, Any, List

from core.settings import (
    NUT_CONF_PATH, UPS_CONF_PATH, UPSD_CONF_PATH, 
    UPSD_USERS_PATH, UPSMON_CONF_PATH
)
from core.logger import system_logger as logger

# Thread safety lock
config_lock = threading.Lock()

# Global variables for parsed configuration
ups_name = None
ups_host = None
nut_mode = None
monitor_user = None
monitor_password = None
admin_user = None
admin_password = None

# NUT mode operational details
NUT_MODE_DETAILS = {
    'standalone': {
        'description': 'Everything runs locally: you have a physical UPS connected to this machine.',
        'start_services': ['upsdrvctl', 'upsd', 'upsmon'],
        'required_files': ['nut.conf', 'ups.conf', 'upsd.conf', 'upsd.users', 'upsmon.conf']
    },
    'netserver': {
        'description': 'Like standalone, but you also accept network clients that read the UPS status.',
        'start_services': ['upsdrvctl', 'upsd', 'upsmon'],
        'required_files': ['nut.conf', 'ups.conf', 'upsd.conf', 'upsd.users', 'upsmon.conf']
    },
    'netclient': {
        'description': 'You connect to a remote NUT server to read its UPS status.',
        'start_services': ['upsmon'],
        'required_files': ['nut.conf', 'upsmon.conf']
    },
    'unknown': {
        'description': 'Unrecognized or unconfigured NUT mode.',
        'start_services': [],
        'required_files': []
    }
}

# Last updated timestamp
last_refresh = 0

def get_nut_mode() -> str:
    """
    Read the NUT mode from nut.conf
    
    Returns:
        str: The NUT mode (standalone, netserver, netclient) or 'unknown' if not found
    """
    try:
        if not os.path.exists(NUT_CONF_PATH):
            logger.warning(f"NUT configuration file not found: {NUT_CONF_PATH}")
            return "unknown"
            
        with open(NUT_CONF_PATH, 'r') as f:
            content = f.read()
            
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('MODE=') and not line.startswith('#'):
                mode = line.split('=', 1)[1].strip().strip('"\'')
                logger.debug(f"Detected NUT mode: {mode}")
                return mode.lower()
                
        logger.warning("No MODE setting found in nut.conf")
        return "unknown"
    except Exception as e:
        logger.error(f"Error reading NUT mode: {str(e)}")
        return "unknown"

def get_ups_monitor_config() -> Tuple[str, str]:
    """
    Read UPS name and host from upsmon.conf
    
    Returns:
        tuple: (ups_name, ups_host) or (None, None) if not found
    """
    try:
        if not os.path.exists(UPSMON_CONF_PATH):
            logger.warning(f"upsmon.conf not found at {UPSMON_CONF_PATH}")
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
                        logger.debug(f"Found UPS monitor configuration: {ups_name}@{ups_host}")
                        return ups_name, ups_host
        
        logger.warning("No MONITOR line found in upsmon.conf")
        return None, None
    except Exception as e:
        logger.error(f"Error reading UPS monitor configuration: {str(e)}")
        return None, None

def get_upsd_users() -> Dict[str, Dict[str, Any]]:
    """
    Read users from upsd.users file
    
    Returns:
        dict: Dictionary of users with their roles and passwords
    """
    users = {}
    try:
        if not os.path.exists(UPSD_USERS_PATH):
            logger.warning(f"upsd.users not found at {UPSD_USERS_PATH}")
            return users
            
        with open(UPSD_USERS_PATH, 'r') as f:
            content = f.read()
            
        # Extract user blocks
        user_blocks = re.findall(r'\[(.*?)\](.*?)(?=\[|$)', content, re.DOTALL)
        
        for username, config_block in user_blocks:
            username = username.strip()
            users[username] = {
                'password': None,
                'is_admin': False,
                'is_monitor': False
            }
            
            # Extract password
            password_match = re.search(r'password\s*=\s*"([^"]*)"', config_block)
            if password_match:
                users[username]['password'] = password_match.group(1)
                
            # Check if admin user (has SET action)
            if re.search(r'actions\s*=.*?SET', config_block):
                users[username]['is_admin'] = True
                
            # Check if monitor user (has upsmon)
            if re.search(r'upsmon', config_block):
                users[username]['is_monitor'] = True
                
            # Determine role (master/slave)
            master_match = re.search(r'upsmon.*?=\s*master', config_block)
            if master_match:
                users[username]['role'] = 'master'
            else:
                slave_match = re.search(r'upsmon.*?=\s*slave', config_block)
                if slave_match:
                    users[username]['role'] = 'slave'
                else:
                    users[username]['role'] = None
                    
        return users
    except Exception as e:
        logger.error(f"Error reading upsd.users: {str(e)}")
        return users

def check_required_files(mode: str) -> Tuple[bool, List[str]]:
    """
    Check if all required configuration files for a given mode exist
    
    Args:
        mode: NUT mode (standalone, netserver, netclient)
        
    Returns:
        tuple: (all_exist, missing_files)
    """
    required_files = NUT_MODE_DETAILS.get(mode, {}).get('required_files', [])
    missing = []
    
    file_paths = {
        'nut.conf': NUT_CONF_PATH,
        'ups.conf': UPS_CONF_PATH,
        'upsd.conf': UPSD_CONF_PATH,
        'upsd.users': UPSD_USERS_PATH,
        'upsmon.conf': UPSMON_CONF_PATH
    }
    
    for file_name in required_files:
        if file_name in file_paths and not os.path.exists(file_paths[file_name]):
            missing.append(file_name)
    
    return len(missing) == 0, missing

def get_services_to_start(mode: str) -> List[str]:
    """
    Get list of services that should be started for a given NUT mode
    
    Args:
        mode: NUT mode (standalone, netserver, netclient)
        
    Returns:
        list: List of service names to start
    """
    return NUT_MODE_DETAILS.get(mode, {}).get('start_services', [])

def refresh_config() -> bool:
    """
    Refresh all configuration variables from NUT configuration files
    
    Returns:
        bool: True if successfully refreshed, False otherwise
    """
    global ups_name, ups_host, nut_mode, monitor_user, monitor_password, admin_user, admin_password, last_refresh
    
    with config_lock:
        try:
            # Read NUT mode
            nut_mode = get_nut_mode()
            
            # Read UPS monitor configuration
            name, host = get_ups_monitor_config()
            if name and host:
                ups_name = name
                ups_host = host
            else:
                logger.warning("Could not determine UPS name and host from configuration files")
                
            # Read users
            users = get_upsd_users()
            
            # Find admin and monitor users
            admin_found = False
            monitor_found = False
            
            for username, user_info in users.items():
                if user_info['is_admin'] and not admin_found:
                    admin_user = username
                    admin_password = user_info['password']
                    admin_found = True
                    
                if user_info['is_monitor'] and not monitor_found:
                    monitor_user = username
                    monitor_password = user_info['password']
                    monitor_found = True
                    
                if admin_found and monitor_found:
                    break
                    
            # Update timestamp
            import time
            last_refresh = time.time()
            
            logger.info(f"NUT configuration refreshed: mode={nut_mode}, ups={ups_name}@{ups_host}")
            return True
            
        except Exception as e:
            logger.error(f"Error refreshing NUT configuration: {str(e)}")
            return False

def get_ups_connection_params():
    """
    Get connection parameters for the UPS monitor from NUT configuration files.
    
    Returns:
        dict: Dictionary with 'name' and 'host' keys if successful, otherwise an empty dict
              Example: {'name': 'ups', 'host': '192.168.1.100'}
    """
    global ups_name, ups_host
    logger.debug("🔍 DEBUG - Parsing UPS connection parameters from NUT files")
    
    # Log all NUT configuration files paths
    logger.debug(f"🔍 DEBUG - NUT configuration files paths:")
    logger.debug(f"🔍 DEBUG - nut.conf: {NUT_CONF_PATH} (exists: {os.path.exists(NUT_CONF_PATH)})")
    logger.debug(f"🔍 DEBUG - ups.conf: {UPS_CONF_PATH} (exists: {os.path.exists(UPS_CONF_PATH)})")
    logger.debug(f"🔍 DEBUG - upsd.conf: {UPSD_CONF_PATH} (exists: {os.path.exists(UPSD_CONF_PATH)})")
    logger.debug(f"🔍 DEBUG - upsd.users: {UPSD_USERS_PATH} (exists: {os.path.exists(UPSD_USERS_PATH)})")
    logger.debug(f"🔍 DEBUG - upsmon.conf: {UPSMON_CONF_PATH} (exists: {os.path.exists(UPSMON_CONF_PATH)})")
    
    # Refresh the config if needed
    if not refresh_config():
        logger.warning("Failed to refresh NUT configuration")
        logger.debug("🔍 DEBUG - get_ups_connection_params: return empty dict due to refresh failure")
        return {}
    
    if ups_name and ups_host:
        logger.debug(f"🔍 DEBUG - Parsed UPS parameters from global variables: name={ups_name}, host={ups_host}")
        return {'name': ups_name, 'host': ups_host}
    else:
        logger.debug("🔍 DEBUG - ups_name or ups_host not set in global variables")
        return {}

def get_nut_configuration() -> Dict[str, Any]:
    """
    Get all NUT configuration values
    
    Returns:
        dict: Dictionary with all configuration values
    """
    # Ensure configuration is refreshed
    refresh_config()
    
    # Get mode details
    mode = nut_mode or "unknown"
    required_files_exist, missing_files = check_required_files(mode)
    services_to_start = get_services_to_start(mode)
    mode_description = NUT_MODE_DETAILS.get(mode, {}).get('description', 'Modalità sconosciuta')
    
    return {
        # Basic configuration
        'nut_mode': mode,
        'ups_name': ups_name,
        'ups_host': ups_host,
        'admin_user': admin_user,
        'admin_password': admin_password,  
        'monitor_user': monitor_user,
        'monitor_password': monitor_password,
        
        # Mode details
        'mode_description': mode_description,
        'services_to_start': services_to_start,
        'required_files_exist': required_files_exist,
        'missing_files': missing_files,
        
        # Configuration status
        'is_configured': bool(mode != 'unknown' and required_files_exist and ups_name and ups_host)
    }

def get_nut_mode_details() -> Dict[str, Dict[str, Any]]:
    """
    Get details for all NUT operating modes
    
    Returns:
        dict: Dictionary with details for each mode
    """
    return NUT_MODE_DETAILS

# Initialize configuration when module is loaded
refresh_config() 