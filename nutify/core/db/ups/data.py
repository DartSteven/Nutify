"""
UPS Data Operations Module.
This module provides functions for retrieving and processing UPS data.
"""

import subprocess
import logging
import json
from datetime import datetime, timedelta
from sqlalchemy import func, text
from flask import current_app

from core.logger import database_logger as logger
from core.db.ups.errors import UPSDataError, UPSConnectionError
from core.db.ups.utils import UPSData, ups_lock, ups_config, calculate_realpower
from core.settings import UPSC_BIN

def get_available_variables():
    """
    Recover all available variables from the UPS
    
    Returns:
        dict: Dictionary of all UPS variables and their values
        
    Raises:
        Exception: If communication with the UPS fails
    """
    try:
        # Ensure configuration is loaded from database if available
        if not ups_config.is_initialized():
            ups_config.load_from_database()
        
        if not ups_config.is_initialized():
            logger.error(f"UPS configuration not initialized: {ups_config}")
            raise ValueError("UPS configuration not initialized. Make sure configure_ups() is called before using this function.")
            
        with ups_lock:
            result = subprocess.run(
                [ups_config.command, f'{ups_config.name}@{ups_config.host}'],
                capture_output=True,
                text=True,
                timeout=ups_config.timeout
            )

            variables = {}
            for line in result.stdout.splitlines():
                if ':' in line:
                    key, value = line.split(':', 1)
                    variables[key.strip()] = value.strip()
            
            return variables

    except Exception as e:
        logger.error(f"Error in get_available_variables: {str(e)}")
        raise

def get_ups_data():
    """
    Get the current UPS data
    
    Returns:
        UPSData: UPS data object with current readings
        
    Raises:
        UPSDataError: If retrieving UPS data fails
    """
    try:
        # Check connection status first using the connection monitor
        from core.db.internal_checker import is_ups_connected, get_ups_connection_status
        
        if not is_ups_connected():
            # Get connection status for more detailed error
            status = get_ups_connection_status()
            recovery_status = "Initial recovery" if status.get('recovery_attempts', 0) < 5 else "Extended recovery"
            error_msg = f"UPS connection unavailable ({recovery_status})"
            
            # Return a valid UPSData object with error status
            data = UPSData({
                'ups_status': 'NOCOMM',  # Use NOCOMM as standard for no communication
                'battery_charge': 0.0,
                'battery_runtime': 0,
                'input_voltage': 0.0,
                'output_voltage': 0.0,
                'error': error_msg
            })
            logger.warning(f"⚠️ {error_msg}")
            return data
        
        with ups_lock:
            # Ensure configuration is loaded from database if available
            if not ups_config.is_initialized():
                ups_config.load_from_database()
            
            # Always use upsc command directly from settings
            upsc_command = UPSC_BIN
            
            # Check if we have the required parameters
            if not ups_config.name or not ups_config.host:
                msg = f"Missing UPS parameters: name={ups_config.name}, host={ups_config.host}"
                logger.error(msg)
                data = UPSData({
                    'ups_status': 'ERROR',
                    'battery_charge': 0.0,
                    'battery_runtime': 0,
                    'input_voltage': 0.0,
                    'output_voltage': 0.0,
                    'error': msg
                })
                return data
            
            # Construct the UPS target identifier
            ups_target = f"{ups_config.name}@{ups_config.host}"
            logger.debug(f"Running UPS command: {upsc_command} {ups_target}")
            
            try:
                # Run the command
                result = subprocess.run(
                    [upsc_command, ups_target], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                
                # Check if command failed
                if result.returncode != 0:
                    error_msg = f"UPS command failed: {result.stderr.strip()}"
                    logger.error(error_msg)
                    data = UPSData({
                        'ups_status': 'ERROR',
                        'battery_charge': 0.0,
                        'battery_runtime': 0,
                        'input_voltage': 0.0,
                        'output_voltage': 0.0,
                        'error': error_msg
                    })
                    return data
                
                # Process the command output
                raw_data = {}
                for line in result.stdout.splitlines():
                    if ':' in line:
                        key, value = line.split(':', 1)
                        raw_data[key.strip()] = value.strip()
                
                if not raw_data:
                    logger.warning("No data returned from UPS command")
                    data = UPSData({
                        'ups_status': 'NO_DATA',
                        'battery_charge': 0.0,
                        'battery_runtime': 0,
                        'input_voltage': 0.0,
                        'output_voltage': 0.0,
                        'error': 'No data returned from UPS'
                    })
                    return data
                
                # Calculate real power if needed
                raw_data = calculate_realpower(raw_data)
                
                # Transform NUT format keys to database format (from dot notation to underscore)
                transformed_data = {}
                for key, value in raw_data.items():
                    db_key = key.replace('.', '_')
                    try:
                        float_value = float(value)
                        transformed_data[db_key] = float_value
                    except ValueError:
                        transformed_data[db_key] = value
                
                # Create and return the data object
                data = UPSData(transformed_data)
                return data
                
            except subprocess.TimeoutExpired:
                error_msg = "UPS command timed out after 10 seconds"
                logger.error(error_msg)
                data = UPSData({
                    'ups_status': 'TIMEOUT',
                    'battery_charge': 0.0,
                    'battery_runtime': 0,
                    'input_voltage': 0.0,
                    'output_voltage': 0.0,
                    'error': error_msg
                })
                return data
                
            except Exception as e:
                error_msg = f"Error executing UPS command: {str(e)}"
                logger.error(error_msg)
                data = UPSData({
                    'ups_status': 'ERROR',
                    'battery_charge': 0.0,
                    'battery_runtime': 0,
                    'input_voltage': 0.0,
                    'output_voltage': 0.0,
                    'error': error_msg
                })
                return data
    
    except Exception as e:
        error_msg = f"Error getting UPS data: {str(e)}"
        logger.error(error_msg)
        data = UPSData({
            'ups_status': 'ERROR',
            'battery_charge': 0.0,
            'battery_runtime': 0,
            'input_voltage': 0.0,
            'output_voltage': 0.0,
            'error': error_msg
        })
        return data

def get_historical_data(db, UPSData, start_time, end_time):
    """
    Get the historical data of the UPS in a time range
    
    Args:
        db: Database instance
        UPSData: UPS data model class
        start_time: Start of the time range
        end_time: End of the time range
        
    Returns:
        list: List of dictionaries with historical data
    """
    try:
        data = UPSData.query.filter(
            UPSData.timestamp_utc.between(start_time, end_time)
        ).order_by(UPSData.timestamp_utc.asc())
        
        result = []
        for entry in data.all():
            record = {'timestamp': entry.timestamp_utc.isoformat()}
            
            # Convert all fields to float where possible
            for column in UPSData.__table__.columns:
                if column.name not in ['id', 'timestamp']:
                    try:
                        value = getattr(entry, column.name)
                        if value is not None:
                            if isinstance(value, (int, float)):
                                record[column.name] = float(value)
                            elif isinstance(value, str):
                                try:
                                    record[column.name] = float(value)
                                except ValueError:
                                    record[column.name] = value
                            else:
                                record[column.name] = value
                    except (ValueError, TypeError, AttributeError) as e:
                        logger.debug(f"Skipping field {column.name}: {e}")
                        continue
            
            result.append(record)
        
        return result
    except Exception as e:
        logger.error(f"Error retrieving historical data: {e}")
        return []
    finally:
        db.session.close()

def calculate_daily_power(db, UPSDynamicData):
    """
    Calculate and save the daily average power
    
    Args:
        db: Database instance
        UPSDynamicData: UPS dynamic data model class
    """
    try:
        tz = current_app.CACHE_TIMEZONE
        now = datetime.now(tz)
        
        # Calculate the previous day
        previous_day = now - timedelta(days=1)
        start_date = previous_day.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        
        # Get all hourly data of the previous day
        hourly_data = UPSDynamicData.query.filter(
            UPSDynamicData.timestamp_utc >= start_date,
            UPSDynamicData.timestamp_utc < end_date,
            UPSDynamicData.ups_realpower_hrs.isnot(None)
        ).all()
        
        if not hourly_data:
            logger.warning("No hourly data available for daily aggregation")
            return
        
        # Calculate the daily average power
        daily_power = sum([d.ups_realpower_hrs for d in hourly_data]) / len(hourly_data)
        
        # Create or update the daily record
        daily_record = UPSDynamicData(
            timestamp_utc=start_date,
            ups_realpower_days=round(daily_power, 2)
        )
        
        with db.session.begin():
            db.session.add(daily_record)
            logger.info(f"💾 Saved daily power average: {daily_power:.2f}W for {start_date.date()}")
            
    except Exception as e:
        logger.error(f"Error in daily power calculation: {str(e)}")
        db.session.rollback()

def get_hourly_power(UPSDynamicData, hour_start):
    """
    Get all data of the specific hour from the database
    
    Args:
        UPSDynamicData: UPS dynamic data model class
        hour_start: Start of the hour
        
    Returns:
        list: List of UPSDynamicData objects for the given hour
    """
    try:
        tz = current_app.CACHE_TIMEZONE
        hour_start = hour_start.astimezone(tz).replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)
        
        return UPSDynamicData.query.filter(
            UPSDynamicData.timestamp_utc >= hour_start,
            UPSDynamicData.timestamp_utc < hour_end
        ).all()
    except Exception as e:
        logger.error(f"Error querying hourly data: {str(e)}")
        return [] 