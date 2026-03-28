"""
UPS Utility Functions Module.
This module provides utility functions for UPS operations.
"""

import logging
import subprocess
import threading
import pytz
from datetime import datetime
from flask import current_app

from core.settings import UPSC_BIN
from core.logger import database_logger as logger
# Import nut_parser for configuration file access
from core.db.nut_parser import get_ups_connection_params, get_nut_configuration

# UPS Configuration class (singleton)
# NOTE: We use a singleton pattern here to ensure that UPS configuration remains
# consistent across all parts of the application, avoiding issues with module-level
# variables being reset between different modules or during import.
class UPSConfig:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UPSConfig, cls).__new__(cls)
            cls._instance.host = None
            cls._instance.name = None
            cls._instance.command = None
            cls._instance.timeout = None
            cls._instance.initialized = False
            cls._instance.db_config = None
            cls._instance.config_files_checked = False
            cls._instance.config_source = "uninitialized"
        return cls._instance
    
    def configure(self, host, name, command, timeout):
        """Configure the UPS connection parameters"""
        self.host = host
        self.name = name
        self.command = command
        self.timeout = timeout
        self.initialized = bool(host and name and command)
        # Don't override config_source here as it's set by configure_ups function
        logger.debug(f"🔌 UPS configuration updated in singleton: host={self.host}, name={self.name}, command={self.command}, timeout={self.timeout}, initialized={self.initialized}, source={getattr(self, 'config_source', 'unknown')}")
        return self.initialized
    
    def load_from_config_files(self):
        """
        Load UPS configuration from NUT configuration files
        
        Returns:
            bool: True if configuration loaded successfully, False otherwise
        """
        try:
            # Import get_ups_connection_params here to avoid circular imports
            from core.db.nut_parser import get_ups_connection_params
            
            # Mark that we've checked the config files
            self.config_files_checked = True
            
            # Get UPS connection parameters from NUT config files
            params = get_ups_connection_params()
            
            logger.debug("🔍 DEBUG - Attempting to load config from NUT files")
            if params:
                host = params.get('host')
                name = params.get('name')
                logger.debug(f"🔍 DEBUG - Found in NUT files: host={host}, name={name}")
            else:
                logger.debug("🔍 DEBUG - No params returned from get_ups_connection_params()")
                
            if params and 'host' in params and 'name' in params:
                host = params['host']
                name = params['name']
                self.host = host
                self.name = name
                self.command = UPSC_BIN
                self.timeout = 10  # Default timeout
                self.initialized = True
                self.config_source = "nut_files"  # Track the source of configuration
                
                logger.info(f"✅ UPS configuration loaded from NUT config files: host={self.host}, name={self.name}, command={self.command}, timeout={self.timeout}")
                return True
            else:
                logger.warning("⚠️ No UPS configuration found in NUT config files")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error loading UPS configuration from NUT config files: {str(e)}")
            return False
    
    def is_initialized(self):
        """Check if UPS configuration is initialized"""
        # Already initialized, return True
        if self.initialized:
            logger.debug(f"🔍 DEBUG - UPS config already initialized: source={getattr(self, 'config_source', 'unknown')}, host={self.host}, name={self.name}")
            return True
            
        # Try to load from configuration files
        if not self.config_files_checked:
            logger.debug("🔍 DEBUG - Checking UPS config files...")
            if self.load_from_config_files():
                logger.debug("🔍 DEBUG - Successfully loaded from NUT config files")
                return True
            else:
                logger.debug("🔍 DEBUG - Failed to load configuration from NUT files")
            
        return self.initialized and bool(self.host and self.name and self.command)
    
    def __str__(self):
        source = getattr(self, 'config_source', 'unknown')
        return f"UPSConfig(host={self.host}, name={self.name}, command={self.command}, timeout={self.timeout}, initialized={self.initialized}, source={source})"

# Global instance
ups_config = UPSConfig()

# Locks for synchronization
ups_lock = threading.Lock()
data_lock = threading.Lock()

class DotDict:
    """
    Utility class to access dictionaries as objects
    Example: instead of dict['key'] allows dict.key
    
    This implementation supports both attribute access (obj.key)
    and dictionary-style item assignment (obj['key'] = value)
    """
    def __init__(self, dictionary):
        self._data = {}
        for key, value in dictionary.items():
            setattr(self, key, value)
            self._data[key] = value
    
    def __getitem__(self, key):
        return self._data[key]
    
    def __setitem__(self, key, value):
        setattr(self, key, value)
        self._data[key] = value
        
    def __contains__(self, key):
        return key in self._data

# Alias DotDict as UPSData for better semantics
UPSData = DotDict

def configure_ups(host, name, command, timeout, source="api_call"):
    """
    Configure the UPS connection parameters
    
    Args:
        host: Hostname or IP of the UPS
        name: Name of the UPS in the NUT system
        command: Command to use (e.g. 'upsc')
        timeout: Timeout in seconds for commands
        source: Source of the configuration (nut_files, database, api_call, etc.)
    """
    # Debug logs to verify parameter values
    logger.debug(f"🔌 Setting UPS configuration: host={host}, name={name}, command={command}, timeout={timeout}, source={source}")
    
    # Set the source in the singleton class
    ups_config.config_source = source
    
    # Configure the singleton instance
    success = ups_config.configure(host, name, command, timeout)
    
    # Skip database update - this is now disabled as requested
    logger.info(f"⏩ Skipping UPS configuration save to database, using configuration files instead: host={host}, name={name}")
    
    # Verify the configuration was set properly
    logger.debug(f"🔌 UPS configuration after setting: {ups_config}")
    logger.info(f"UPS configuration updated: host={host}, name={name}, source={source}")
    return success

def utc_to_local(utc_dt):
    """
    Convert UTC datetime to local timezone.
    
    Args:
        utc_dt: UTC datetime object
        
    Returns:
        datetime: Local timezone datetime object
    """
    if utc_dt is None:
        return None
        
    # Ensure datetime has UTC timezone
    if utc_dt.tzinfo is None:
        utc_dt = pytz.UTC.localize(utc_dt)
    elif utc_dt.tzinfo != pytz.UTC:
        utc_dt = utc_dt.astimezone(pytz.UTC)
        
    # Convert to local timezone using CACHE_TIMEZONE
    return utc_dt.astimezone(current_app.CACHE_TIMEZONE)

def local_to_utc(local_dt):
    """
    Convert local timezone datetime to UTC.
    
    Args:
        local_dt: Local timezone datetime object
        
    Returns:
        datetime: UTC datetime object
    """
    if local_dt is None:
        return None
        
    # If datetime has no timezone, assume it's in local timezone from CACHE_TIMEZONE
    if local_dt.tzinfo is None:
        local_dt = current_app.CACHE_TIMEZONE.localize(local_dt)
        
    # Convert to UTC
    return local_dt.astimezone(pytz.UTC)

def get_supported_value(data, field, default='N/A'):
    """
    Get a value from the UPS data with missing value handling
    
    Args:
        data: Object containing the UPS data
        field: Name of the field to retrieve
        default: Default value if the field doesn't exist
    
    Returns:
        The value of the field or the default value
    """
    try:
        value = getattr(data, field, None)
        if value is not None and value != '':
            return value
        return default
    except AttributeError:
        return default

def calculate_realpower(data, target_id=None):
    """
    Calculate ups_realpower (real power) using scoped operation formulas.
    
    Priority for nominal power:
    1. First use the value directly from UPS (ups.realpower.nominal/ups_realpower_nominal)
    2. If not available from UPS, try from database
    3. Only use default value (1000W) as last resort
    
    Cases handled:
    1. Key doesn't exist (ups.realpower or ups_realpower) -> Calculate value
    2. Key exists but value is 0 -> Calculate value
    3. Key exists with non-zero value -> Keep existing value
    
    Args:
        data: Dictionary containing UPS data
        
    Returns:
        Updated data dictionary with calculated realpower
    """
    try:
        dot_key = 'ups.realpower'
        underscore_key = 'ups_realpower'

        current_value = None
        if dot_key in data:
            current_value = data[dot_key]
        elif underscore_key in data:
            current_value = data[underscore_key]

        if current_value is not None:
            try:
                if float(current_value) > 0:
                    return data
            except (TypeError, ValueError):
                pass

        nominal_value = None
        if 'ups.realpower.nominal' in data:
            nominal_value = data['ups.realpower.nominal']
            logger.debug(f"⚡ Using nominal power from UPS data (ups.realpower.nominal): {nominal_value}W")
        elif 'ups_realpower_nominal' in data:
            nominal_value = data['ups_realpower_nominal']
            logger.debug(f"⚡ Using nominal power from UPS data (ups_realpower_nominal): {nominal_value}W")

        if nominal_value is None:
            try:
                from core.options.options import get_variable_config

                scoped_config = get_variable_config(target_id=target_id)
                scoped_nominal = scoped_config.get('ups_realpower_nominal') if isinstance(scoped_config, dict) else None
                if scoped_nominal is not None:
                    nominal_value = scoped_nominal
                    logger.debug(
                        "⚡ Using nominal power from scoped variable config (target_id=%s): %sW",
                        target_id,
                        nominal_value,
                    )
            except Exception as scoped_error:
                logger.debug(f"⚠️ Could not read scoped nominal power from VariableConfig: {scoped_error}")

        if nominal_value is None:
            try:
                from core.settings import get_ups_realpower_nominal

                db_value = get_ups_realpower_nominal(target_id=target_id)
                if db_value is not None:
                    nominal_value = db_value
                    logger.debug(f"⚡ Using nominal power from database: {nominal_value}W")
            except (ImportError, AttributeError) as e:
                logger.warning(f"⚠️ Could not get UPS nominal power from database: {str(e)}")

        if nominal_value is None:
            nominal_value = 1000
            logger.warning(f"⚠️ No nominal power found in UPS data or database. Using default: {nominal_value}W")

        from core.options.operations_runtime import compute_realpower_watts

        realpower = compute_realpower_watts(
            data,
            target_id=target_id,
            nominal_default=float(nominal_value),
        )
        data[dot_key] = str(round(realpower, 2))
        data[underscore_key] = str(round(realpower, 2))
        logger.debug(f"Calculated realpower: {realpower:.2f}W (target_id={target_id})")
    except Exception as e:
        logger.error(f"Error calculating realpower: {str(e)}", exc_info=True)
    
    return data 
