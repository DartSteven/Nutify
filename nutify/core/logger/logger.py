"""Logger Module.

Implements core runtime logic and helpers used by this feature.
"""

# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL

import os
import logging
import logging.config
import re
from core.settings import LOG, LOG_LEVEL, LOG_FILE

class SensitiveDataFilter(logging.Filter):
    """Filter to mask sensitive data in log messages"""
    
    def __init__(self):
        super().__init__()
        self.sensitive_patterns = [
            (r'"smtp_password":\s*"([^"]*)"', '"smtp_password": "********"'),
            (r'"password":\s*"([^"]*)"', '"password": "********"'),
            (r"'smtp_password':\s*'([^']*)'", "'smtp_password': '********'"),
            (r"'password':\s*'([^']*)'", "'password': '********'")
        ]
    
    def filter(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            msg = record.msg
            for pattern, replacement in self.sensitive_patterns:
                msg = re.sub(pattern, replacement, msg)
            record.msg = msg
        return True

# Flexible handling of the LOG variable: if it's of type bool, use it directly, otherwise convert to lowercase for comparison.
if isinstance(LOG, bool):
    use_log = LOG
else:
    use_log = LOG.lower() == 'true'

if use_log:
    effective_level = LOG_LEVEL.upper()
else:
    # Disable logs by setting the level to CRITICAL
    effective_level = "CRITICAL"

# Determine the directory where logs will be stored based on LOG_FILE
LOG_DIR = os.path.dirname(LOG_FILE)

# Define the logging configuration with categories for logging.
# We dynamically set the level using effective_level.
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'sensitive_data': {
            '()': SensitiveDataFilter,
        },
    },
    'formatters': {
         'standard': {
             'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
         },
         'database_formatter': {
             'format': '%(asctime)s - [DATABASE] - %(levelname)s - %(message)s'
         },
    },
    'handlers': {
         'system_handler': {
              'class': 'logging.handlers.TimedRotatingFileHandler',
              'filename': os.path.join(LOG_DIR, 'system.log'),
              'when': 'midnight',
              'backupCount': 7,
              'formatter': 'standard',
              'filters': ['sensitive_data']
         },
         'database_handler': {
              'class': 'logging.handlers.TimedRotatingFileHandler',
              'filename': os.path.join(LOG_DIR, 'database.log'),
              'when': 'midnight',
              'backupCount': 7,
              'formatter': 'database_formatter',
              'filters': ['sensitive_data']
         },
         'database_console': {
              'class': 'logging.StreamHandler',
              'formatter': 'database_formatter',
              'filters': ['sensitive_data']
         },
         'ups_handler': {
              'class': 'logging.handlers.TimedRotatingFileHandler',
              'filename': os.path.join(LOG_DIR, 'ups.log'),
              'when': 'midnight',
              'backupCount': 7,
              'formatter': 'standard',
              'filters': ['sensitive_data']
         },
         'energy_handler': {
              'class': 'logging.handlers.TimedRotatingFileHandler',
              'filename': os.path.join(LOG_DIR, 'energy.log'),
              'when': 'midnight',
              'backupCount': 7,
              'formatter': 'standard',
              'filters': ['sensitive_data']
         },
         'web_handler': {
              'class': 'logging.handlers.TimedRotatingFileHandler',
              'filename': os.path.join(LOG_DIR, 'web.log'),
              'when': 'midnight',
              'backupCount': 7,
              'formatter': 'standard',
              'filters': ['sensitive_data']
         },
         'mail_handler': {
              'class': 'logging.handlers.TimedRotatingFileHandler',
              'filename': os.path.join(LOG_DIR, 'mail.log'),
              'when': 'midnight',
              'backupCount': 7,
              'formatter': 'standard',
              'filters': ['sensitive_data']
         },
         'options_handler': {
              'class': 'logging.handlers.TimedRotatingFileHandler',
              'filename': os.path.join(LOG_DIR, 'options.log'),
              'when': 'midnight',
              'backupCount': 7,
              'formatter': 'standard',
              'filters': ['sensitive_data']
         },
         # Handler for battery logs
         'battery_handler': {
              'class': 'logging.handlers.TimedRotatingFileHandler',
              'filename': os.path.join(LOG_DIR, 'battery.log'),
              'when': 'midnight',
              'backupCount': 7,
              'formatter': 'standard',
              'filters': ['sensitive_data']
         },
         # Handler for upsmon logs
         'upsmon_handler': {
              'class': 'logging.handlers.TimedRotatingFileHandler',
              'filename': os.path.join(LOG_DIR, 'upsmon.log'),
              'when': 'midnight',
              'backupCount': 7,
              'formatter': 'standard',
              'filters': ['sensitive_data']
         },
         'socket_handler': {
              'class': 'logging.handlers.TimedRotatingFileHandler',
              'filename': os.path.join(LOG_DIR, 'socket.log'),
              'when': 'midnight',
              'backupCount': 7,
              'formatter': 'standard',
              'filters': ['sensitive_data']
         },
         # Handler for voltage logs
         'voltage_handler': {
              'class': 'logging.handlers.TimedRotatingFileHandler',
              'filename': os.path.join(LOG_DIR, 'voltage.log'),
              'when': 'midnight',
              'backupCount': 7,
              'formatter': 'standard',
              'filters': ['sensitive_data']
         },
         # Handler for power logs
         'power_handler': {
              'class': 'logging.handlers.TimedRotatingFileHandler',
              'filename': os.path.join(LOG_DIR, 'power.log'),
              'when': 'midnight',
              'backupCount': 7,
              'formatter': 'standard',
              'filters': ['sensitive_data']
         },
         # Handler for scheduler logs
         'scheduler_handler': {
              'class': 'logging.handlers.TimedRotatingFileHandler',
              'filename': os.path.join(LOG_DIR, 'scheduler.log'),
              'when': 'midnight',
              'backupCount': 7,
              'formatter': 'standard',
              'filters': ['sensitive_data']
         },
         # Handler for webhook logs
         'webhook_handler': {
              'class': 'logging.handlers.TimedRotatingFileHandler',
              'filename': os.path.join(LOG_DIR, 'webhook.log'),
              'when': 'midnight',
              'backupCount': 7,
              'formatter': 'standard',
              'filters': ['sensitive_data']
         },
         # Console handler for real-time output
         'console': {
              'class': 'logging.StreamHandler',
              'formatter': 'standard',
              'filters': ['sensitive_data']
         },
         'report_handler': {
              'class': 'logging.handlers.TimedRotatingFileHandler',
              'filename': os.path.join(LOG_DIR, 'report.log'),
              'when': 'midnight',
              'backupCount': 7,
              'formatter': 'standard',
              'filters': ['sensitive_data']
         },
         'events_handler': {
              'class': 'logging.handlers.TimedRotatingFileHandler',
              'filename': os.path.join(LOG_DIR, 'events.log'),
              'when': 'midnight',
              'backupCount': 7,
              'formatter': 'standard',
              'filters': ['sensitive_data']
         },
    },
    'loggers': {
         'system': {
              'handlers': ['system_handler', 'console'],
              'level': effective_level,
              'propagate': False
         },
         'database': {
              'handlers': ['database_handler', 'database_console'],
              'level': effective_level,
              'propagate': False
         },
         'ups': {
              'handlers': ['ups_handler', 'console'],
              'level': effective_level,
              'propagate': False
         },
         'energy': {
              'handlers': ['energy_handler', 'console'],
              'level': effective_level,
              'propagate': False
         },
         'web': {
              'handlers': ['web_handler', 'console'],
              'level': effective_level,
              'propagate': False
         },
         'mail': {
              'handlers': ['mail_handler', 'console'],
              'level': effective_level,
              'propagate': False
         },
         'options': {
              'handlers': ['options_handler', 'console'],
              'level': effective_level,
              'propagate': False
         },
         # Logger for battery related messages
         'battery': {
              'handlers': ['battery_handler', 'console'],
              'level': effective_level,
              'propagate': False
         },
         # Logger for upsmon messages
         'upsmon': {
              'handlers': ['upsmon_handler', 'console'],
              'level': effective_level,
              'propagate': False
         },
         # Logger for voltage related messages
         'voltage': {
              'handlers': ['voltage_handler', 'console'],
              'level': effective_level,
              'propagate': False
         },
         # Logger for power related messages
         'power': {
              'handlers': ['power_handler', 'console'],
              'level': effective_level,
              'propagate': False
         },
         # Logger for socket related messages
         'socket': {
              'handlers': ['socket_handler', 'console'],
              'level': effective_level,
              'propagate': False
         },
         # Logger for webhook related messages
         'webhook': {
              'handlers': ['webhook_handler', 'console'],
              'level': effective_level,
              'propagate': False
         },
         'report': {
              'handlers': ['report_handler', 'console'],
              'level': effective_level,
              'propagate': False
         },
         'scheduler': {
              'handlers': ['scheduler_handler', 'console'],
              'level': effective_level,
              'propagate': False
         },
         'events': {
              'handlers': ['events_handler', 'console'],
              'level': effective_level,
              'propagate': False
         },
    }
}

def setup_logging():
    """Initialize logging configuration using dictConfig."""
    logging.config.dictConfig(LOGGING_CONFIG)

def get_logger(category, name=None):
    """
    Return a logger for the given category.
    
    Args:
        category (str): One of the valid categories: 'system', 'database', 'ups',
                        'energy', 'web', 'mail', 'options'.
        name (str, optional): If specified, a child logger will be created.
    
    Returns:
        logging.Logger: The configured logger for the category.
    """
    base_logger = logging.getLogger(category)
    if name:
        return base_logger.getChild(name)
    return base_logger

# Initialize logging when module is loaded
setup_logging()

# Helper loggers for convenience
system_logger = get_logger('system')
database_logger = get_logger('database')
ups_logger = get_logger('ups')
energy_logger = get_logger('energy')
web_logger = get_logger('web')
mail_logger = get_logger('mail')
options_logger = get_logger('options')
battery_logger = get_logger('battery')
upsmon_logger = get_logger('upsmon')
socket_logger = get_logger('socket')
voltage_logger = get_logger('voltage')
power_logger = get_logger('power')
report_logger = get_logger('report')
scheduler_logger = get_logger('scheduler')
events_logger = get_logger('events')
webhook_logger = get_logger('webhook') 