"""Settings Package.

Defines package exports and module-level initialization helpers.
"""

from .settings import (
    # Base path settings
    BASE_DIR,
    LOG_DIR,
    LOG_FILE,

    # Configuration functions
    load_settings,
    parse_value,
    get_ups_realpower_nominal,
    parse_time_format,
    get_logger,
    get_server_name,
    get_workspace_monitoring_profile,
    get_target_timezone,
    get_encryption_key,
    init_application_timezone,
    
    # Settings variables (added from load_settings)
    DB_NAME,
    CACHE_SECONDS,
    LOG_LEVEL,
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_INFO,
    LOG,
    LOG_WERKZEUG,
    SERVER_HOST,
    SERVER_PORT,
    SSL_ENABLED,
    INSTANCE_PATH,
    DB_URI,
)

# Import NUT path settings
from .paths import (
    # Configuration directory
    NUT_CONF_DIR,
    
    # Configuration files
    NUT_CONF_FILE,
    UPS_CONF_FILE,
    UPSD_CONF_FILE,
    UPSD_USERS_FILE,
    UPSMON_CONF_FILE,
    
    # Full paths to configuration files
    NUT_CONF_PATH,
    UPS_CONF_PATH,
    UPSD_CONF_PATH,
    UPSD_USERS_PATH,
    UPSMON_CONF_PATH,
    
    # Certificate files
    CERTFILE,
    KEYFILE,
    CERTPATH,
    CERTFILE_PATH,
    KEYFILE_PATH,
    CERTPATH_DIR,
    
    # Binary paths
    UPSC_BIN,
    UPSCMD_BIN,
    UPSRW_BIN,
    UPSD_BIN,
    UPSMON_BIN,
    UPSDRVCTL_BIN,
    
    # Command names
    UPSC_CMD,
    UPSCMD_CMD,
    UPSRW_CMD,
    UPSD_CMD,
    UPSMON_CMD,
    UPSDRVCTL_CMD,
    
    # Full commands with options
    NUT_START_DRIVER_CMD,
    NUT_START_SERVER_CMD,
    NUT_START_MONITOR_CMD,
    NUT_STOP_DRIVER_CMD,
    NUT_STOP_SERVER_CMD,
    NUT_STOP_MONITOR_CMD,
    NUT_SCANNER_CMD,
    
    # Runtime directories
    NUT_RUN_DIR,
    NUT_LOG_DIR,
    NUT_STATE_DIR,
    NUT_DRIVER_DIR,
    
    # Network port
    NUT_PORT,
    
    # NUT PID files
    NUT_DRIVER_PID,
    NUT_UPSD_PID,
    NUT_UPSMON_PID,
    
    # NUT Log files
    NUT_DRIVER_LOG,
    NUT_SERVER_LOG,
    NUT_UPSMON_LOG,
    NUT_NOTIFIER_LOG,
    
    # NUT Service settings
    NUT_SERVICE_WAIT_TIME,
    NUT_SERVICE_START_TIMEOUT,
    
    # Mail path settings
    MSMTP_PATH,
    TLS_CERT_PATH,
    
    # SSL Certificate paths
    SSL_CERT,
    SSL_KEY,
    
    # Utility functions
    load_path_settings,
    get_all_path_settings,
)

# Import __getattr__ directly from settings
from .settings import __getattr__

# Export all imported settings
__all__ = [
    'BASE_DIR',
    'LOG_DIR',
    'LOG_FILE',
    'load_settings',
    'parse_value',
    'get_ups_realpower_nominal',
    'parse_time_format',
    'get_logger',
    'get_server_name',
    'get_workspace_monitoring_profile',
    'get_target_timezone',
    'get_encryption_key',
    'init_application_timezone',
    'DB_NAME',
    'CACHE_SECONDS',
    'LOG_LEVEL',
    'LOG_LEVEL_DEBUG',
    'LOG_LEVEL_INFO',
    'LOG',
    'LOG_WERKZEUG',
    'SERVER_HOST',
    'SERVER_PORT',
    'SSL_ENABLED',
    'SSL_CERT',
    'SSL_KEY',
    'INSTANCE_PATH',
    'DB_URI',
    'MSMTP_PATH',
    'TLS_CERT_PATH',
    
    # NUT path settings
    'NUT_CONF_DIR',
    'NUT_CONF_FILE',
    'UPS_CONF_FILE',
    'UPSD_CONF_FILE',
    'UPSD_USERS_FILE',
    'UPSMON_CONF_FILE',
    'NUT_CONF_PATH',
    'UPS_CONF_PATH',
    'UPSD_CONF_PATH',
    'UPSD_USERS_PATH', 
    'UPSMON_CONF_PATH',
    'CERTFILE',
    'KEYFILE',
    'CERTPATH',
    'CERTFILE_PATH',
    'KEYFILE_PATH',
    'CERTPATH_DIR',
    'UPSC_BIN',
    'UPSCMD_BIN',
    'UPSRW_BIN',
    'UPSD_BIN',
    'UPSMON_BIN',
    'UPSDRVCTL_BIN',
    'UPSC_CMD',
    'UPSCMD_CMD',
    'UPSRW_CMD',
    'UPSD_CMD',
    'UPSMON_CMD',
    'UPSDRVCTL_CMD',
    'NUT_START_DRIVER_CMD',
    'NUT_START_SERVER_CMD',
    'NUT_START_MONITOR_CMD',
    'NUT_STOP_DRIVER_CMD',
    'NUT_STOP_SERVER_CMD',
    'NUT_STOP_MONITOR_CMD',
    'NUT_SCANNER_CMD',
    'NUT_RUN_DIR',
    'NUT_LOG_DIR',
    'NUT_STATE_DIR',
    'NUT_DRIVER_DIR',
    'NUT_PORT',
    'NUT_DRIVER_PID',
    'NUT_UPSD_PID',
    'NUT_UPSMON_PID',
    'NUT_DRIVER_LOG',
    'NUT_SERVER_LOG',
    'NUT_UPSMON_LOG',
    'NUT_NOTIFIER_LOG',
    'NUT_SERVICE_WAIT_TIME',
    'NUT_SERVICE_START_TIMEOUT',
    'load_path_settings',
    'get_all_path_settings',
] 
