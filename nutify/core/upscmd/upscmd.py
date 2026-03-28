"""Upscmd Module.

Implements core runtime logic and helpers used by this feature.
"""

import subprocess
from datetime import datetime
from ..db.ups import db, data_lock
from ..db.ups.utils import ups_config
from flask import current_app
from core.settings import (
    UPSCMD_BIN,
    UPSC_BIN
)
import time
from ..socket import notify_command_executed
from core.logger import ups_logger as logger
from core.multi_nut.target_scope import apply_target_scope, resolve_settings_target_id

logger.info("🌍 Initializing upscmd")

# Initialize UPSCommand from ModelClasses
UPSCommand = None

def _init_models_if_needed():
    """Initialize UPSCommand model from ModelClasses if needed"""
    global UPSCommand
    if UPSCommand is None:
        # Check if we can get the model from the db.ModelClasses namespace
        if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'UPSCommand'):
            UPSCommand = db.ModelClasses.UPSCommand
            logger.debug("📚 UPSCommand model initialized from db.ModelClasses")
        else:
            # Fall back to using core.db.models if ModelClasses isn't initialized
            from core.db.models import init_models
            # Use the CACHE_TIMEZONE from current_app
            init_models(db, lambda: current_app.CACHE_TIMEZONE)
            
            # Try again to get the model
            if hasattr(db, 'ModelClasses') and hasattr(db.ModelClasses, 'UPSCommand'):
                UPSCommand = db.ModelClasses.UPSCommand
                logger.debug("📚 UPSCommand model initialized after init_models")
            else:
                logger.error("❌ Failed to initialize UPSCommand model")


def _apply_command_scope(query, target_id=None):
    """Apply target scope when UPSCommand supports target_id."""
    _init_models_if_needed()
    scoped_target_id = resolve_settings_target_id(target_id)
    if UPSCommand is not None and hasattr(UPSCommand, 'target_id'):
        return apply_target_scope(UPSCommand, query, scoped_target_id), scoped_target_id
    return query, scoped_target_id

def get_ups_commands():
    """
    Retrieve the list of available commands for the UPS
    Returns:
        list: List of available commands
    """
    try:
        # Use UPS configuration from database
        if not ups_config.is_initialized():
            logger.error("UPS configuration not initialized")
            return []
            
        UPS_HOST = ups_config.host
        UPS_NAME = ups_config.name
        UPSCMD_USER = None
        UPSCMD_PASSWORD = None
        
        # Get authentication info from NUT config files
        try:
            from core.db.nut_parser import get_nut_configuration
            config = get_nut_configuration()
            if config:
                UPSCMD_USER = config.get('admin_user')
                UPSCMD_PASSWORD = config.get('admin_password')
        except Exception as e:
            logger.warning(f"Could not load UPS authentication from configuration files: {str(e)}")
        
        logger.info("Execution of the upscmd -l command to get the list of commands")
        # Execute the upscmd command to get the list of commands
        ups_target = f"{UPS_NAME}@{UPS_HOST}"
        
        # Build command based on available credentials
        if UPSCMD_USER and UPSCMD_PASSWORD:
            result = subprocess.run([UPSCMD_BIN, '-u', UPSCMD_USER, '-p', UPSCMD_PASSWORD, '-l', ups_target], 
                                  capture_output=True, 
                                  text=True)
        else:
            result = subprocess.run([UPSCMD_BIN, '-l', ups_target], 
                                  capture_output=True, 
                                  text=True)
        
        logger.debug(f"Command output: {result.stdout}")
        if result.stderr:
            logger.error(f"Command error: {result.stderr}")
        
        commands = []
        parsing_commands = False
        
        # Parsing of the output
        for line in result.stdout.splitlines():
            logger.debug(f"Parsing line: {line}")
            
            # Start parsing after the line "Instant commands supported on UPS [ups]:"
            if "Instant commands supported on UPS" in line:
                parsing_commands = True
                continue
                
            if parsing_commands and line.strip():  # If we are parsing and the line is not empty
                if ' - ' in line:  # Format: "command - description"
                    name, description = line.split(' - ', 1)
                    command = {
                        'name': name.strip(),
                        'description': description.strip(),
                        'type': 'command'
                    }
                    logger.debug(f"Command found: {command}")
                    commands.append(command)
        
        logger.info(f"Found {len(commands)} commands")
        return commands
        
    except Exception as e:
        logger.error(f"Error retrieving UPS commands: {str(e)}", exc_info=True)
        raise

def execute_command(command, target_id=None):
    """
    Execute a command on the UPS and monitor the result
    Args:
        command (str): Command to execute
    Returns:
        tuple: (success, output)
    """
    try:
        # Use UPS configuration from database
        if not ups_config.is_initialized():
            logger.error("UPS configuration not initialized")
            return False, ["UPS configuration not initialized"]
            
        UPS_HOST = ups_config.host
        UPS_NAME = ups_config.name
        UPSCMD_USER = None
        UPSCMD_PASSWORD = None
        
        # Get authentication info from NUT config files
        try:
            from core.db.nut_parser import get_nut_configuration
            config = get_nut_configuration()
            if config:
                UPSCMD_USER = config.get('admin_user')
                UPSCMD_PASSWORD = config.get('admin_password')
        except Exception as e:
            logger.warning(f"Could not load UPS authentication from configuration files: {str(e)}")
            
        logger.info(f"Execution of the command: {command}")
        ups_target = f"{UPS_NAME}@{UPS_HOST}"
        
        # Execute the command
        if UPSCMD_USER and UPSCMD_PASSWORD:
            cmd = [UPSCMD_BIN, '-u', UPSCMD_USER, '-p', UPSCMD_PASSWORD, ups_target, command]
        else:
            cmd = [UPSCMD_BIN, ups_target, command]
            
        logger.debug(f"Complete command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        success = result.returncode == 0
        
        output = []
        if result.stdout:
            output.append(f"Output command: {str(result.stdout.strip())}")
        if result.stderr and result.stderr.strip() != "OK":
            output.append(f"Errors: {str(result.stderr.strip())}")
            
        # Wait a moment to allow the UPS to update its status
        time.sleep(1)
        
        # Read the new status after the command
        current_status = get_ups_status(ups_target)
        
        # Output management based on the type of command
        if command.startswith('beeper.'):
            # For the beeper commands
            output.append("\nBeeper status:")
            if 'ups.beeper.status' in current_status:
                output.append(f"ups.beeper.status: {current_status['ups.beeper.status']}")
            else:
                output.append("The device does not support reading the beeper status")
                output.append("Check manually if the command has had an effect")
                
        elif command.startswith('test.panel.'):
            # Test of the LED/display panel
            output.append("\nTest of the LED/display panel:")
            if 'ups.test.result' in current_status:
                test_result = current_status['ups.test.result']
                output.append(f"ups.test.result: {test_result}")
                
                # Interpret the result correctly
                if test_result == 'No test initiated':
                    output.append("Test panel started")
                    output.append("Check visually that all LEDs/displays turn on correctly")
                    output.append("The test will automatically end after a few seconds")
                elif 'Done' in test_result:
                    output.append("Test panel completed")
                elif 'In progress' in test_result:
                    output.append("Test panel in progress...")
                    output.append("Check visually that all LEDs/displays turn on correctly")
            else:
                output.append("Test panel in progress...")
                output.append("Check visually that all LEDs/displays turn on correctly")
                
        elif command.startswith('test.failure.'):
            # Test simulation failure
            output.append("\nTest simulation failure:")
            output.append("ups.status: " + current_status.get('ups.status', 'N/A'))
            output.append("ups.test.result: " + current_status.get('ups.test.result', 'N/A'))
            
        elif command.startswith('test.battery.'):
            # Test battery (various types)
            output.append("\nBattery test monitoring:")
            prev_status = current_status
            
            for _ in range(30):
                time.sleep(2)
                current_status = get_ups_status(ups_target)
                
                # Relevant parameters for battery test
                relevant_params = {
                    'ups.status': 'UPS status',
                    'ups.test.result': 'Test result',
                    'battery.charge': 'Battery charge',
                    'battery.voltage': 'Battery voltage',
                    'battery.runtime': 'Estimated runtime'
                }
                
                for key, label in relevant_params.items():
                    if key in current_status and (key not in prev_status or prev_status[key] != current_status[key]):
                        output.append(f"{key}: {current_status[key]}")
                
                prev_status = current_status
                if 'ups.test.result' in current_status and 'Done' in current_status['ups.test.result']:
                    break
                    
        elif command.startswith('calibrate.'):
            # Calibration commands
            output.append("\nBattery calibration:")
            output.append("ups.status: " + current_status.get('ups.status', 'N/A'))
            output.append("battery.charge: " + current_status.get('battery.charge', 'N/A'))
            output.append("battery.runtime: " + current_status.get('battery.runtime', 'N/A'))
            
        elif command.startswith('load.'):
            # Management load commands
            output.append("\nLoad status:")
            for key in ['ups.status', 'output.voltage', 'ups.load', 'output.current']:
                if key in current_status:
                    output.append(f"{key}: {current_status[key]}")
                    
        elif command.startswith('outlet.'):
            # Specific outlet commands
            outlet_num = command.split('.')[1]
            output.append(f"\nOutlet {outlet_num} status:")
            for key in current_status:
                if key.startswith(f"outlet.{outlet_num}."):
                    output.append(f"{key}: {current_status[key]}")
                    
        elif command.startswith('shutdown.'):
            # Shutdown commands
            output.append("\nShutdown status:")
            output.append("ups.status: " + current_status.get('ups.status', 'N/A'))
            if 'ups.shutdown.return' in current_status:
                output.append("ups.shutdown.return: " + current_status['ups.shutdown.return'])
                
        elif command.startswith('bypass.'):
            # Bypass commands
            output.append("\nBypass status:")
            for key in ['ups.status', 'input.bypass.voltage', 'input.bypass.frequency']:
                if key in current_status:
                    output.append(f"{key}: {current_status[key]}")
        
        else:
            # Other commands
            output.append("\nUPS status:")
            output.append("ups.status: " + current_status.get('ups.status', 'N/A'))
            
        final_output = '\n'.join(output)
        # Ensure that the output is a valid string
        final_output = str(final_output) if final_output else "No output available"
        
        # Ensure UPSCommand model is initialized
        _init_models_if_needed()
        
        # Save in the database
        resolved_target_id = resolve_settings_target_id(target_id)
        with data_lock:
            cmd_log = UPSCommand(
                command=command,
                success=success,
                output=final_output
            )
            if hasattr(cmd_log, 'target_id'):
                cmd_log.target_id = resolved_target_id
            db.session.add(cmd_log)
            db.session.commit()
            
        # Notify the result via socket
        notify_command_executed(command, success, final_output)
        
        return success, final_output
        
    except Exception as e:
        logger.error(f"Error in the execution of the command {command}: {str(e)}", exc_info=True)
        
        # Ensure UPSCommand model is initialized
        _init_models_if_needed()
        
        resolved_target_id = resolve_settings_target_id(target_id)
        with data_lock:
            cmd_log = UPSCommand(
                command=command,
                success=False,
                output=str(e)
            )
            if hasattr(cmd_log, 'target_id'):
                cmd_log.target_id = resolved_target_id
            db.session.add(cmd_log)
            db.session.commit()
        notify_command_executed(command, False, str(e))
        raise

def get_ups_status(ups_target):
    """Get the current status of the UPS"""
    try:
        logger.debug(f"Getting UPS status for {ups_target}")
        result = subprocess.run([UPSC_BIN, ups_target], capture_output=True, text=True)
        
        if result.returncode == 0:
            status = {}
            for line in result.stdout.splitlines():
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    if any(k in key.lower() for k in ['ups.status', 'ups.test.result', 'battery.charge', 
                                                    'battery.voltage', 'input.voltage', 'output.voltage']):
                        status[key] = value
            return status
        else:
            logger.error(f"Error getting UPS status: {result.stderr}")
            return {}
    except Exception as e:
        logger.error(f"Error getting UPS status: {str(e)}")
        return {}

def get_status_changes(old_status, new_status):
    """
    Compare two UPS states and returns the differences
    """
    changes = []
    for key in new_status:
        if key not in old_status or old_status[key] != new_status[key]:
            changes.append(f"{key}: {new_status[key]}")
    return changes

def get_command_stats(target_id=None):
    """
    Retrieve the command statistics
    Returns:
        dict: Command statistics
    """
    try:
        # Ensure UPSCommand model is initialized
        _init_models_if_needed()
        
        with data_lock:
            scoped_query, _ = _apply_command_scope(UPSCommand.query, target_id)
            # Total commands
            total_commands = scoped_query.count()
            
            # Commands with success/failure
            successful_commands = scoped_query.filter_by(success=True).count()
            failed_commands = scoped_query.filter_by(success=False).count()
            
            # Last 5 commands
            recent_commands = scoped_query.order_by(
                UPSCommand.timestamp.desc()
            ).limit(5).all()
            
            return {
                'total': total_commands,
                'successful': successful_commands,
                'failed': failed_commands,
                'recent': [cmd.to_dict() for cmd in recent_commands]
            }
            
    except Exception as e:
        logger.error(f"Error in the recovery of the statistics: {str(e)}")
        raise 
