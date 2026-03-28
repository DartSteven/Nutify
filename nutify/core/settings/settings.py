"""Runtime settings loader and compatibility accessors."""

import os
from pathlib import Path
import pytz
from datetime import datetime
import logging
from sqlalchemy import create_engine, inspect, text

import os as _os
__path__ = [_os.path.dirname(_os.path.abspath(__file__))]

BASE_DIR = Path(__file__).resolve().parent.parent.parent

LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, 'system.log')

if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, 'w') as f:
        f.write(f"Log file created on {datetime.now().isoformat()}\n")

logger = logging.getLogger('system')

_ALL_SETTINGS = {}

SECRET_KEY = None

def get_logger(category, name=None):
    """
    Return a logger for the given category.
    
    Args:
        category (str): The category of the logger.
        name (str, optional): If specified, a child logger will be created.
    
    Returns:
        logging.Logger: The configured logger for the category.
    """
    base_logger = logging.getLogger(category)
    if name:
        return base_logger.getChild(name)
    return base_logger

def parse_value(value):
    """Parse string value into appropriate type"""
    value = value.strip()
    
    if '#' in value:
        value = value.split('#')[0].strip()
    
    if value.startswith('"""'):
        end_pos = value.find('"""', 3)
        if end_pos != -1:
            return value[3:end_pos]
        return value.strip('"')
        
    if value.lower() in ('true', 'false'):
        return value.lower() == 'true'
        
    try:
        if value.isdigit():
            return int(value)
    except ValueError:
        pass
        
    try:
        if '.' in value:
            return float(value)
    except ValueError:
        pass
        
    return value.strip('"\'')

def load_settings():
    """Load settings from config file"""
    global _ALL_SETTINGS
    
    default_settings = {
        'DEBUG_MODE': 'development',
        'SERVER_PORT': 5050,
        'SERVER_HOST': '0.0.0.0',
        'CACHE_SECONDS': 60,
        'LOG_LEVEL': 'DEBUG',
        'LOG_FILE_ENABLED': True,
        'LOG_FORMAT': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'LOG_LEVEL_DEBUG': 'DEBUG, %(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'LOG_LEVEL_INFO': 'INFO, %(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'COMMAND_TIMEOUT': 10,
        'SSL_ENABLED': False,
    }
    
    settings = default_settings.copy()
    config_path = Path(__file__).parent.parent.parent / 'config' / 'settings.txt'
    base_path = Path(__file__).parent.parent.parent
    
    if not config_path.exists():
        logger.warning(f"Configuration file not found: {config_path}. Using default settings.")
    else:
        with open(config_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    settings[key] = parse_value(value)
    
    required_vars = [
        'DB_NAME', 'INSTANCE_PATH',
    ]
    
    missing_vars = [var for var in required_vars if var not in settings]
    if missing_vars:
        if 'DB_NAME' in missing_vars:
            settings['DB_NAME'] = 'nutify.db.sqlite'
            logger.warning(f"Using default DB_NAME: {settings['DB_NAME']}")
        
        if 'INSTANCE_PATH' in missing_vars:
            settings['INSTANCE_PATH'] = 'instance'
            logger.warning(f"Using default INSTANCE_PATH: {settings['INSTANCE_PATH']}")
        
        missing_vars = [var for var in required_vars if var not in settings]
        if missing_vars:
            raise ValueError(f"Missing required configuration variables: {', '.join(missing_vars)}")
    
    settings['INSTANCE_PATH'] = str(base_path / settings['INSTANCE_PATH'])
    settings['DB_PATH'] = str(base_path / settings['INSTANCE_PATH'] / settings['DB_NAME'])
    
    settings['DB_URI'] = f"sqlite:///{settings['DB_PATH']}"
    
    instance_path = Path(settings['INSTANCE_PATH'])
    if not instance_path.exists():
        instance_path.mkdir(parents=True)
    
    _ALL_SETTINGS = settings.copy()
    
    _ALL_SETTINGS['SECRET_KEY'] = SECRET_KEY
    
    return settings

globals().update(load_settings())

_ALL_SETTINGS['SECRET_KEY'] = SECRET_KEY

def init_application_timezone():
    """Return UTC DB timezone and app display timezone from CACHE_TIMEZONE."""
    from flask import current_app
    
    db_timezone = pytz.UTC
    
    if not (current_app and hasattr(current_app, 'CACHE_TIMEZONE')):
        raise RuntimeError("CACHE_TIMEZONE not available. Application not properly initialized.")
        
    display_timezone = current_app.CACHE_TIMEZONE
    logger.info(f"🌏 Using display timezone from app.CACHE_TIMEZONE: {display_timezone.zone}")
    return (db_timezone, display_timezone)


def _normalize_monitoring_profile(value):
    """Normalize workspace monitoring profile."""
    normalized = str(value or '').strip().lower()
    if normalized in {'single', 'multi'}:
        return normalized
    return 'single'


def _normalize_timezone(value, fallback='UTC'):
    """Normalize timezone string to a valid IANA timezone."""
    candidate = str(value or '').strip()
    if not candidate:
        return fallback
    try:
        pytz.timezone(candidate)
        return candidate
    except Exception:
        return fallback


def _table_exists(inspector, table_name):
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def _fetch_master_control_row(*columns):
    """Read one row from nutify_master_control using DB_URI directly."""
    engine = create_engine(DB_URI)
    inspector = inspect(engine)
    if not _table_exists(inspector, 'nutify_master_control'):
        return None

    selected_columns = ", ".join(columns)
    configured_query = text(
        f"""
        SELECT {selected_columns}
        FROM nutify_master_control
        WHERE is_configured = 1
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """
    )
    fallback_query = text(
        f"""
        SELECT {selected_columns}
        FROM nutify_master_control
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """
    )

    with engine.connect() as connection:
        row = connection.execute(configured_query).fetchone()
        if row is not None:
            return row
        return connection.execute(fallback_query).fetchone()


def _fetch_primary_target_id(connection, inspector):
    """Return primary target id when available."""
    if not _table_exists(inspector, 'ups_monitor_targets'):
        return None

    row = connection.execute(
        text(
            """
            SELECT id
            FROM ups_monitor_targets
            WHERE is_primary = 1
            ORDER BY id ASC
            LIMIT 1
            """
        )
    ).fetchone()
    if row is None:
        return None
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return None


def _fetch_variable_config_row(*columns, target_id=None):
    """
    Read one scoped row from ups_opt_variable_config.

    Resolution order:
    1) Explicit target_id (if provided)
    2) Primary target row
    3) Any target-scoped row (target_id IS NOT NULL)
    4) Legacy global row (target_id IS NULL)
    """
    engine = create_engine(DB_URI)
    inspector = inspect(engine)
    if not _table_exists(inspector, 'ups_opt_variable_config'):
        return None

    selected_columns = ", ".join(columns)
    with engine.connect() as connection:
        resolved_target_id = None
        if target_id is not None:
            try:
                resolved_target_id = int(target_id)
            except (TypeError, ValueError):
                resolved_target_id = None

        if resolved_target_id is None:
            resolved_target_id = _fetch_primary_target_id(connection, inspector)

        if resolved_target_id is not None:
            scoped_row = connection.execute(
                text(
                    f"""
                    SELECT {selected_columns}
                    FROM ups_opt_variable_config
                    WHERE target_id = :target_id
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 1
                    """
                ),
                {'target_id': resolved_target_id},
            ).fetchone()
            if scoped_row is not None:
                return scoped_row

        any_row = connection.execute(
            text(
                f"""
                SELECT {selected_columns}
                FROM ups_opt_variable_config
                WHERE target_id IS NOT NULL
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """
            )
        ).fetchone()
        if any_row is not None:
            return any_row

        return connection.execute(
            text(
                f"""
                SELECT {selected_columns}
                FROM ups_opt_variable_config
                WHERE target_id IS NULL
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """
            )
        ).fetchone()

def get_server_name():
    """
    Get the server name ONLY from the database with NO fallbacks
    
    Returns:
        str: The server name from the database
        
    Raises:
        Exception: If the server name cannot be retrieved from the database
    """
    global DB_URI
    
    try:
        row = _fetch_master_control_row('server_name')
        if row is None:
            raise Exception("No server_name found in database")

        server_name = str(row[0] or '').strip()
        if not server_name:
            raise Exception("No server_name found in database")

        logger.debug(f"📋 Server name from database: {server_name}")
        return server_name
    except Exception as e:
        logger.error(f"Error getting server name from database: {str(e)}")
        raise

def get_secret_key():
    """
    Get the secret key directly from app config, not from the database
    
    Returns:
        str: The secret key from app config
        
    Raises:
        RuntimeError: If no secret key is found
    """
    try:
        from flask import current_app
        
        if current_app and current_app.config.get('SECRET_KEY'):
            return current_app.config.get('SECRET_KEY')
        else:
            raise RuntimeError("SECRET_KEY is not available in Flask app config")
    except Exception as e:
        logger.error(f"Error getting secret key: {str(e)}")
        raise RuntimeError(f"SECRET_KEY is not available. Make sure it is set in environment variables.")

def get_encryption_key():
    """
    Legacy function that now calls get_secret_key()
    
    Returns:
        str: The secret key from app config
        
    Raises:
        RuntimeError: If no secret key is found
    """
    return get_secret_key()

def get_ups_realpower_nominal(target_id=None):
    """
    Get UPS nominal power from database if possible
    
    Returns:
        int: The UPS nominal power value or None if not set
    """
    global DB_URI
    
    try:
        row = _fetch_variable_config_row('ups_realpower_nominal', target_id=target_id)
        if row is not None and row[0] is not None:
            nominal_power = int(row[0])
            logger.debug(f"⚡ Using UPS nominal power from database: {nominal_power}")
            return nominal_power
    except Exception as e:
        logger.debug(f"Error getting UPS nominal power from database: {str(e)}")
    
    logger.debug(f"⚡ No UPS nominal power in database, returning None")
    return None


def get_workspace_monitoring_profile():
    """Get workspace monitoring profile from nutify_master_control."""
    try:
        row = _fetch_master_control_row('monitoring_profile')
        if row is not None:
            return _normalize_monitoring_profile(row[0])
    except Exception as e:
        logger.debug(f"Error getting monitoring profile from master control: {str(e)}")

    try:
        engine = create_engine(DB_URI)
        inspector = inspect(engine)
        if not _table_exists(inspector, 'ups_monitor_targets'):
            return 'single'
        with engine.connect() as connection:
            enabled_targets = connection.execute(
                text("SELECT COUNT(*) FROM ups_monitor_targets WHERE enabled = 1")
            ).scalar()
            return 'multi' if int(enabled_targets or 0) > 1 else 'single'
    except Exception:
        return 'single'


def get_target_timezone(target_id=None):
    """Get display timezone from target-scoped variable config."""
    try:
        row = _fetch_variable_config_row('timezone', target_id=target_id)
        if row is not None and row[0]:
            return _normalize_timezone(row[0], fallback='UTC')
    except Exception as e:
        logger.debug(f"Error getting timezone from variable config: {str(e)}")
    return 'UTC'

def parse_time_format(time_str, default_time=None):
    """
    Parse a time string in various formats and return a time object.
    
    Args:
        time_str: String representing time in various formats
        default_time: Default time to return if parsing fails (None for current time)
    
    Returns:
        time object
    """
    if not time_str:
        if default_time is None:
            return datetime.now().time()
        return default_time
        
    formats = [
        '%H:%M',       # 24-hour format (13:30)
        '%I:%M %p',    # 12-hour format with AM/PM (1:30 PM)
        '%I:%M%p',     # 12-hour without space (1:30PM)
        '%H.%M',       # 24-hour with dot (13.30)
        '%I.%M %p',    # 12-hour with dot (1.30 PM)
        '%I:%M %P',    # 12-hour with lowercase am/pm (1:30 pm)
        '%I.%M%p',     # 12-hour with dot without space (1.30PM)
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt).time()
        except ValueError:
            continue
    
    logger.error(f"Could not parse time string: {time_str}")
    
    if default_time is None:
        return datetime.now().time()
    return default_time

def __getattr__(name):
    """
    Fallback for getting attributes that aren't directly defined.
    This allows accessing any setting without explicitly defining it.
    """
    global _ALL_SETTINGS
    
    if name in (
        'get_server_name',
        'get_ups_realpower_nominal',
        'get_workspace_monitoring_profile',
        'get_target_timezone',
        'get_encryption_key',
    ):
        logger.error(f"Attempted to access function '{name}' via __getattr__. This should be imported directly.")
        return lambda: None  # Return a no-op function
        
    if name in _ALL_SETTINGS:
        return _ALL_SETTINGS[name]
    
    if name.startswith('__') and name.endswith('__'):
        return None
    
    critical_db_settings = ['SERVER_NAME', 'UPS_REALPOWER_NOMINAL']
    if name in critical_db_settings:
        logger.error(f"Critical setting '{name}' must be retrieved from database using the appropriate function")
        raise Exception(f"Setting '{name}' must be retrieved from database, not from settings.txt")
    
    logger.error(f"Requested setting '{name}' not found in configuration")
    return None 
