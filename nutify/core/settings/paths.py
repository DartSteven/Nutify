"""
NUT Paths Module

This module provides centralized access to NUT configuration paths and commands.
The paths are loaded from the runtime-appropriate configuration file.
"""

import os
from pathlib import Path
import logging

# Set up logger
logger = logging.getLogger('system')

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def resolve_config_path():
    """Select an explicit override, Docker paths, or local development paths."""
    override = str(os.environ.get('NUTIFY_PATH_SETTINGS_FILE') or '').strip()
    if override:
        return Path(override).expanduser().resolve()
    docker_path = BASE_DIR / 'config' / 'settings_path_Docker.txt'
    if Path('/.dockerenv').exists() and docker_path.exists():
        return docker_path
    return BASE_DIR / 'config' / 'settings_path.txt'


CONFIG_PATH = resolve_config_path()

# Dictionary to store all path settings
_PATH_SETTINGS = {}

def parse_value(value):
    """Parse string value into appropriate type"""
    value = value.strip()
    
    # Remove comments
    if '#' in value:
        value = value.split('#')[0].strip()
    
    # Handle integer values
    try:
        if value.isdigit():
            return int(value)
    except ValueError:
        pass
    
    # Return as string for path values
    return value

def load_path_settings():
    """Load path settings from the selected runtime configuration file."""
    settings = {}
    
    if not CONFIG_PATH.exists():
        logger.warning(f"Path configuration file not found: {CONFIG_PATH}. Using default paths.")
        # These default settings will be used only if settings_path.txt is missing
        # And typically assume a standard Linux file layout with NUT in /etc/nut
        settings['NUT_CONF_DIR'] = '/etc/nut'  # Default NUT directory on Linux systems
        settings['NUT_DRIVER_DIR'] = '/usr/lib/nut'  # Default NUT driver directory
        settings['NUT_CONF_FILE'] = 'nut.conf'
        settings['UPS_CONF_FILE'] = 'ups.conf'
        settings['UPSD_CONF_FILE'] = 'upsd.conf'
        settings['UPSD_USERS_FILE'] = 'upsd.users'
        settings['UPSMON_CONF_FILE'] = 'upsmon.conf'
        # Default certificate settings
        settings['CERTFILE'] = 'upsd.cert'
        settings['KEYFILE'] = 'upsd.key'
        settings['CERTPATH'] = 'cert'
        settings['UPSC_BIN'] = '/usr/bin/upsc'
        settings['UPSCMD_BIN'] = '/usr/bin/upscmd'
        settings['UPSRW_BIN'] = '/usr/bin/upsrw'
        settings['UPSD_BIN'] = '/usr/sbin/upsd'
        settings['UPSMON_BIN'] = '/usr/sbin/upsmon'
        settings['UPSDRVCTL_BIN'] = '/usr/sbin/upsdrvctl'
        settings['UPSC_CMD'] = 'upsc'
        settings['UPSCMD_CMD'] = 'upscmd'
        settings['UPSRW_CMD'] = 'upsrw'
        settings['UPSD_CMD'] = 'upsd'
        settings['UPSMON_CMD'] = 'upsmon'
        settings['NUT_SCANNER_CMD'] = 'nut-scanner'
        settings['UPSDRVCTL_CMD'] = 'upsdrvctl'
        settings['NUT_RUN_DIR'] = '/var/run/nut'
        settings['NUT_LOG_DIR'] = '/var/log/nut'
        settings['NUT_PORT'] = 3493
        # Default mail path settings
        settings['MSMTP_PATH'] = '/usr/bin/msmtp'
        settings['TLS_CERT_PATH'] = '/etc/ssl/certs/ca-certificates.crt'
        # Default SSL certificate paths
        settings['SSL_CERT'] = '/app/ssl/cert.pem'
        settings['SSL_KEY'] = '/app/ssl/key.pem'
    else:
        with open(CONFIG_PATH) as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                    
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    settings[key] = parse_value(value)
    
    # If NUT_DRIVER_DIR is not set, use a default value
    if not settings.get('NUT_DRIVER_DIR'):
        settings['NUT_DRIVER_DIR'] = '/usr/lib/nut'  # Default NUT driver directory
        logger.debug(f"NUT_DRIVER_DIR not set, using default: {settings['NUT_DRIVER_DIR']}")
    
    # Create convenience properties for full paths to config files
    # These combine the directory path with the file names
    if 'NUT_CONF_DIR' in settings:
        # Full paths to configuration files
        settings['NUT_CONF_PATH'] = os.path.join(settings['NUT_CONF_DIR'], settings.get('NUT_CONF_FILE', 'nut.conf'))
        settings['UPS_CONF_PATH'] = os.path.join(settings['NUT_CONF_DIR'], settings.get('UPS_CONF_FILE', 'ups.conf'))
        settings['UPSD_CONF_PATH'] = os.path.join(settings['NUT_CONF_DIR'], settings.get('UPSD_CONF_FILE', 'upsd.conf'))
        settings['UPSD_USERS_PATH'] = os.path.join(settings['NUT_CONF_DIR'], settings.get('UPSD_USERS_FILE', 'upsd.users'))
        settings['UPSMON_CONF_PATH'] = os.path.join(settings['NUT_CONF_DIR'], settings.get('UPSMON_CONF_FILE', 'upsmon.conf'))
        
        # Full paths to certificate files
        settings['CERTFILE_PATH'] = os.path.join(settings['NUT_CONF_DIR'], settings.get('CERTFILE', 'upsd.cert'))
        settings['KEYFILE_PATH'] = os.path.join(settings['NUT_CONF_DIR'], settings.get('KEYFILE', 'upsd.key'))
        settings['CERTPATH_DIR'] = os.path.join(settings['NUT_CONF_DIR'], settings.get('CERTPATH', 'cert'))
    
    # Log what we loaded
    logger.debug(f"Loaded NUT path settings from {CONFIG_PATH}")
    logger.debug(f"NUT configuration directory: {settings.get('NUT_CONF_DIR')}")
    logger.debug(f"NUT driver directory: {settings.get('NUT_DRIVER_DIR')}")
    logger.debug(f"NUT binary paths: UPSC_BIN={settings.get('UPSC_BIN')}")
    
    return settings

# Load settings into module namespace and global dictionary
_PATH_SETTINGS.update(load_path_settings())
globals().update(_PATH_SETTINGS)

def __getattr__(name):
    """Enable access to settings as attributes of the module"""
    if name in _PATH_SETTINGS:
        return _PATH_SETTINGS[name]
    raise AttributeError(f"Module {__name__} has no attribute {name}")

def get_all_path_settings():
    """Return all path settings as a dictionary"""
    return _PATH_SETTINGS.copy()

def get_debug_constants_log():
    """
    Get a debug log message for all NUT command constants.
    This helps troubleshoot command execution issues.
    """
    logger = logging.getLogger('system')
    logger.debug("🔍 DEBUG - NUT command constants:")
    logger.debug(f"🔍 DEBUG - UPSDRVCTL_BIN = {UPSDRVCTL_BIN}")
    logger.debug(f"🔍 DEBUG - UPSD_BIN = {UPSD_BIN}")
    logger.debug(f"🔍 DEBUG - UPSMON_BIN = {UPSMON_BIN}")
    logger.debug(f"🔍 DEBUG - NUT_START_DRIVER_CMD = {NUT_START_DRIVER_CMD}")
    logger.debug(f"🔍 DEBUG - NUT_START_SERVER_CMD = {NUT_START_SERVER_CMD}")
    logger.debug(f"🔍 DEBUG - NUT_START_MONITOR_CMD = {NUT_START_MONITOR_CMD}")
    logger.debug(f"🔍 DEBUG - NUT_STOP_DRIVER_CMD = {NUT_STOP_DRIVER_CMD}")
    logger.debug(f"🔍 DEBUG - NUT_STOP_SERVER_CMD = {NUT_STOP_SERVER_CMD}")
    logger.debug(f"🔍 DEBUG - NUT_STOP_MONITOR_CMD = {NUT_STOP_MONITOR_CMD}")
    logger.debug(f"🔍 DEBUG - NUT_SCANNER_CMD = {NUT_SCANNER_CMD}")
    logger.debug(f"🔍 DEBUG - NUT_DRIVER_DIR = {NUT_DRIVER_DIR}")

# Call debug logger when module is imported
get_debug_constants_log() 
