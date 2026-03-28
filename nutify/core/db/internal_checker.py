"""
UPS Connection Monitor Module.

This module provides a system to monitor the connection to the UPS/NUT server
and handle connection failures gracefully with smart retry logic.
"""

import logging
import subprocess
import threading
import time
from datetime import datetime, timedelta
from flask import current_app
import pytz
import re
import os
import json
import socket

from core.logger import system_logger as logger
from core.settings import UPSC_BIN, UPSDRVCTL_BIN, UPSD_BIN, UPSMON_BIN, NUT_SCANNER_CMD, SERVER_HOST, SERVER_PORT, NUT_STOP_MONITOR_CMD, NUT_STOP_SERVER_CMD, NUT_STOP_DRIVER_CMD, NUT_START_DRIVER_CMD, NUT_START_SERVER_CMD, NUT_START_MONITOR_CMD, NUT_SERVICE_WAIT_TIME
from core.db.ups.utils import ups_config
from core.events.notifier_path import get_ups_notifier_command_path

class ConnectionMonitor:
    """
    UPS Connection Monitor that checks connection health and handles recovery.
    
    This class provides:
    - Active monitoring of connection to UPS/NUT server
    - Smart retry logic with configurable parameters
    - Automatic recovery when connection is restored
    - Connection state tracking and statistics
    - USB disconnect detection and automatic recovery
    """
    
    # Class-level singleton instance
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation to ensure only one instance exists"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ConnectionMonitor, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the connection monitor with default settings"""
        # Skip initialization if already done (singleton pattern)
        if self._initialized:
            return
            
        # Connection state
        self._connected = True  # Assume connected initially
        self._connection_lost_time = None
        self._last_successful_check = None
        self._in_recovery_mode = False
        self._recovery_attempts = 0
        
        # USB specific state
        self._is_usb_disconnect = False
        self._usb_vendor_id = None
        self._usb_product_id = None
        self._usb_serial = None
        
        # Retry configuration
        self._initial_retry_count = 5  # Initial number of quick retries
        self._initial_retry_interval = 5  # Seconds between initial retries
        self._extended_retry_interval = 60  # Seconds between extended retries
        self._usb_scan_interval = 10  # Seconds between USB scans
        
        # Statistics
        self._total_failures = 0
        self._total_recoveries = 0
        self._total_usb_disconnects = 0
        self._total_usb_reconnects = 0
        self._last_state_change = self._get_current_time_with_timezone()
        
        # Thread control
        self._stop_requested = False
        self._check_thread = None
        
        # Lock for thread-safe operations
        self._state_lock = threading.Lock()
        
        # Mark as initialized (singleton pattern)
        self._initialized = True
        logger.info("🔌 UPS Connection Monitor initialized")
    
    def _get_current_time_with_timezone(self):
        """Get current time with the application timezone"""
        try:
            if current_app and hasattr(current_app, 'CACHE_TIMEZONE'):
                return datetime.now(current_app.CACHE_TIMEZONE)
            else:
                # Fallback to UTC if app context not available
                return datetime.now(pytz.UTC)
        except Exception:
            # Fallback to UTC in case of any errors
            return datetime.now(pytz.UTC)
    
    def start_monitoring(self):
        """Start the connection monitoring thread"""
        if self._check_thread is not None and self._check_thread.is_alive():
            logger.warning("⚠️ Connection monitoring thread already running")
            return False
            
        self._stop_requested = False
        self._check_thread = threading.Thread(
            target=self._monitoring_thread,
            daemon=True,
            name="UPS-Connection-Monitor"
        )
        self._check_thread.start()
        logger.info("🔌 UPS Connection monitoring thread started")
        return True
    
    def stop_monitoring(self):
        """Stop the connection monitoring thread"""
        self._stop_requested = True
        if self._check_thread and self._check_thread.is_alive():
            self._check_thread.join(timeout=5)
            logger.info("🔌 UPS Connection monitoring thread stopped")
            return True
        return False
    
    def _monitoring_thread(self):
        """Main monitoring thread function"""
        logger.info("🔄 UPS Connection monitoring thread running")
        
        while not self._stop_requested:
            # Run connection check
            self.check_connection()
            
            # If in USB disconnect mode, use special recovery
            if self._is_usb_disconnect:
                self._usb_recovery_process()
                sleep_time = self._usb_scan_interval
            else:
                # Determine sleep time based on current state
                if self._in_recovery_mode:
                    if self._recovery_attempts < self._initial_retry_count:
                        sleep_time = self._initial_retry_interval
                    else:
                        sleep_time = self._extended_retry_interval
                else:
                    # When connected, check less frequently
                    sleep_time = 30
                
            # Sleep until next check
            for _ in range(int(sleep_time)):
                if self._stop_requested:
                    break
                time.sleep(1)
    
    def check_connection(self):
        """
        Check the connection to the UPS/NUT server
        
        Returns:
            bool: True if connected, False otherwise
        """
        with self._state_lock:
            # Ensure UPS configuration is available
            if not ups_config.is_initialized():
                ups_config.load_from_database()
                if not ups_config.is_initialized():
                    logger.error("❌ UPS configuration not initialized, cannot check connection")
                    return False
            
            # Get connection parameters
            upsc_command = UPSC_BIN
            ups_name = ups_config.name
            ups_host = ups_config.host
            
            if not ups_name or not ups_host:
                logger.error(f"❌ Missing UPS parameters: name={ups_name}, host={ups_host}")
                return False
            
            # Construct the UPS target identifier
            ups_target = f"{ups_name}@{ups_host}"
            
            try:
                # Run upsc command to test connection
                result = subprocess.run(
                    [upsc_command, ups_target, "ups.status"],  # Just get one value as a quick test
                    capture_output=True,
                    text=True,
                    timeout=5  # Shorter timeout for connection check
                )
                
                # Check result
                if result.returncode == 0:
                    # Connection successful
                    self._handle_successful_connection()
                    return True
                else:
                    # Connection failed - check if it's a USB disconnect
                    stderr = result.stderr.strip()
                    if self._is_usb_disconnect_error(stderr):
                        self._handle_usb_disconnect(stderr)
                    else:
                        # Handle as a regular connection failure
                        self._handle_failed_connection(f"UPS command failed: {stderr}")
                    return False
                    
            except subprocess.TimeoutExpired:
                # Timeout indicates connection problems
                self._handle_failed_connection("UPS command timed out")
                return False
                
            except Exception as e:
                # Any other error indicates connection problems
                self._handle_failed_connection(f"Error checking UPS connection: {str(e)}")
                return False
    
    def _is_usb_disconnect_error(self, error_message):
        """
        Check if the error message indicates a USB disconnect
        
        Args:
            error_message: Error message from upsc command
            
        Returns:
            bool: True if the error indicates a USB disconnect
        """
        # Common messages indicating USB disconnect
        usb_disconnect_indicators = [
            "No such file or directory",
            "Connection failure",
            "Data stale",
            "Driver not connected",
            "USB communication driver failed",
            "Communication with UPS lost"
        ]
        
        for indicator in usb_disconnect_indicators:
            if indicator in error_message:
                return True
                
        return False
    
    def _handle_successful_connection(self):
        """Handle successful connection check"""
        now = self._get_current_time_with_timezone()
        self._last_successful_check = now
        
        # If we were in recovery mode, log the recovery
        if self._in_recovery_mode:
            self._in_recovery_mode = False
            self._recovery_attempts = 0
            self._total_recoveries += 1
            self._last_state_change = now
            
            # If it was a USB disconnect that was resolved
            if self._is_usb_disconnect:
                self._is_usb_disconnect = False
                self._total_usb_reconnects += 1
                logger.info("✅ USB connection to UPS restored")
                
                # Trigger COMMOK notification when USB connection is restored
                self._trigger_commok_notification()
            
            # Calculate downtime
            if self._connection_lost_time:
                downtime = now - self._connection_lost_time
                downtime_seconds = downtime.total_seconds()
                downtime_str = str(timedelta(seconds=int(downtime_seconds)))
                logger.info(f"✅ UPS Connection restored after {downtime_str} of downtime")
            else:
                logger.info("✅ UPS Connection restored")
            
            self._connection_lost_time = None
            self._connected = True
        
        # If already connected, just update the timestamp silently
        elif not self._connected:
            self._connected = True
            self._last_state_change = now
            logger.info("✅ UPS Connection is active")
    
    def _handle_failed_connection(self, error_message):
        """Handle failed connection check"""
        now = self._get_current_time_with_timezone()
        
        # If this is the first failure, record the time
        if self._connected:
            self._connected = False
            self._connection_lost_time = now
            self._last_state_change = now
            self._in_recovery_mode = True
            self._recovery_attempts = 0
            self._total_failures += 1
            logger.warning(f"⚠️ UPS Connection lost: {error_message}")
        
        # If already in recovery mode, update attempt counter
        if self._in_recovery_mode:
            self._recovery_attempts += 1
            
            # Log attempts with different detail levels
            if self._recovery_attempts <= self._initial_retry_count:
                logger.info(f"🔄 UPS Connection recovery attempt {self._recovery_attempts}/{self._initial_retry_count}")
            elif self._recovery_attempts % 5 == 0:  # Log extended recovery less frequently
                minutes = self._recovery_attempts * self._extended_retry_interval // 60
                logger.info(f"🔄 UPS Connection still down after {minutes} minutes, continuing recovery")
    
    def _handle_usb_disconnect(self, error_message):
        """
        Handle USB disconnect specifically
        
        Args:
            error_message: Error message from upsc command
        """
        now = self._get_current_time_with_timezone()
        
        # If this is the first failure or not already in USB disconnect mode
        if self._connected or not self._is_usb_disconnect:
            self._connected = False
            self._connection_lost_time = now
            self._last_state_change = now
            self._in_recovery_mode = True
            self._recovery_attempts = 0
            self._total_failures += 1
            self._is_usb_disconnect = True
            self._total_usb_disconnects += 1
            
            # Attempt to get USB information
            self._store_usb_device_info()
            
            logger.warning(f"⚠️ USB Connection to UPS lost: {error_message}")
            logger.info("🔍 Starting USB device scanning to detect when UPS is reconnected")
            
            # Send USB disconnect event to frontend via WebSocket
            self._send_usb_disconnect_event()
        
        # Update recovery attempts counter
        self._recovery_attempts += 1
        
        # Log less frequently during extended recovery
        if self._recovery_attempts % 6 == 0:  # Every ~1 minute with 10-second interval
            logger.info(f"🔄 Scanning for reconnected USB UPS device (attempt {self._recovery_attempts})")
            
            # Periodically resend the USB disconnect event
            if self._recovery_attempts % 30 == 0:  # Roughly every 5 minutes
                self._send_usb_disconnect_event()
    
    def _store_usb_device_info(self):
        """
        Try to extract and store USB device information from the configuration
        """
        try:
            # Fix the error with ups_config.get by using direct attribute access
            # instead of trying to use a get method that doesn't exist
            self._usb_vendor_id = getattr(ups_config, 'vendorid', None)
            self._usb_product_id = getattr(ups_config, 'productid', None)
            self._usb_serial = getattr(ups_config, 'serial', None)
            
            logger.debug(f"📋 USB device info - Vendor ID: {self._usb_vendor_id}, Product ID: {self._usb_product_id}, Serial: {self._usb_serial}")
        except Exception as e:
            logger.error(f"❌ Error storing USB device info: {str(e)}")
    
    def _usb_recovery_process(self):
        """
        Special recovery process for USB disconnects using nut-scanner
        """
        # First try lsusb, which works even when nut-scanner fails
        try:
            logger.info("🔍 Checking for USB devices using lsusb...")
            lsusb_result = subprocess.run(
                ["lsusb"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            
            if lsusb_result.returncode == 0:
                output = lsusb_result.stdout.strip()
                logger.debug(f"🔍 lsusb output: {output}")
                
                # If USB devices are found, check if there might be a UPS
                # This is more generic and works with any UPS, not just specific models
                if output and len(output.split('\n')) > 1:
                    # Try to verify if any of the devices might be a UPS
                    # by checking /dev/bus/usb
                    if os.path.exists('/dev/bus/usb'):
                        logger.info("✅ Found USB devices via lsusb, USB bus exists")
                        # If there are USB devices and the bus is available, try restarting services
                        self._restart_nut_services()
                        return True
            else:
                logger.warning(f"⚠️ lsusb command failed: {lsusb_result.stderr.strip()}")
        except Exception as e:
            logger.warning(f"⚠️ Error running lsusb: {str(e)}")
        
        # Fallback to nut-scanner
        try:
            # Run nut-scanner to look for USB devices
            logger.debug("🔍 Running nut-scanner to scan for USB devices")
            result = subprocess.run(
                [NUT_SCANNER_CMD, "--usb_scan"],
                capture_output=True,
                text=True,
                timeout=30  # Allow more time for the scan
            )
            
            if result.returncode == 0:
                # Check if our device is in the output
                if self._is_device_in_nut_scanner_output(result.stdout):
                    logger.info("🔍 USB UPS device detected! Restarting NUT services")
                    self._restart_nut_services()
                    return True
            else:
                logger.debug(f"🔍 nut-scanner scan failed: {result.stderr.strip()}")
            
            return False
            
        except subprocess.TimeoutExpired:
            logger.warning("⚠️ nut-scanner command timed out")
            return False
        except Exception as e:
            logger.error(f"❌ Error in USB recovery process: {str(e)}")
            return False
    
    def _is_device_in_nut_scanner_output(self, output):
        """
        Check if our UPS device is in the nut-scanner output
        
        Args:
            output: stdout from nut-scanner
            
        Returns:
            bool: True if the device is found
        """
        # Log the complete output for debugging
        logger.debug(f"nut-scanner output: {output}")
        
        # If we have vendor and product IDs, look for them in the output
        if self._usb_vendor_id and self._usb_product_id:
            vendor_pattern = f"vendorid.*?{self._usb_vendor_id}"
            product_pattern = f"productid.*?{self._usb_product_id}"
            
            if re.search(vendor_pattern, output, re.IGNORECASE) and re.search(product_pattern, output, re.IGNORECASE):
                logger.info(f"🔍 Found exact USB device match: Vendor={self._usb_vendor_id}, Product={self._usb_product_id}")
                return True
        
        # If we don't have specific IDs or didn't find a match, check if any UPS is found
        if "driver = " in output and "port = " in output:
            logger.info("🔍 Found USB UPS device in scanner output")
            return True
        
        # If nut-scanner finds nothing, try manually checking
        # USB devices available, regardless of manufacturer
        try:
            # Check if USB devices are available
            if os.path.exists('/dev/bus/usb'):
                # Look for USB device directories
                usb_dirs = []
                for bus_dir in os.listdir('/dev/bus/usb'):
                    bus_path = os.path.join('/dev/bus/usb', bus_dir)
                    if os.path.isdir(bus_path):
                        usb_dirs.append(bus_path)
                
                if usb_dirs:
                    logger.info(f"🔍 Found USB directories: {usb_dirs}")
                    # Consider this a success if USB devices are available
                    return True
        except Exception as e:
            logger.debug(f"🔍 Error checking USB paths: {str(e)}")
        
        return False
    
    def _restart_nut_services(self):
        """
        Restart the NUT services to reconnect to the USB device directly.
        Uses direct command execution instead of relying on external scripts.
        """
        try:
            logger.info("🔄 Handling USB reconnection with direct service restart...")
            
            # Log current USB devices to help with diagnosis
            try:
                result = subprocess.run(
                    ["lsusb"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    devices = result.stdout.strip()
                    logger.info(f"🔍 Current USB devices:\n{devices}")
                    # Check if we can see an APC or other UPS device
                    if "051d" in devices.lower() or "apc" in devices.lower() or "ups" in devices.lower():
                        logger.info("✅ UPS device detected in USB devices list")
                    else:
                        logger.info("⚠️ No UPS device found in USB devices list")
            except Exception as e:
                logger.warning(f"⚠️ Failed to list USB devices: {str(e)}")

            # First, properly stop all services (if they exist)
            logger.info("🔄 Stopping NUT services...")
            
            # Try to stop in the correct order: first upsmon, then upsd, then drivers
            self._run_shell_command(NUT_STOP_MONITOR_CMD, "Stop upsmon", ignore_errors=True)
            self._run_shell_command(NUT_STOP_SERVER_CMD, "Stop upsd", ignore_errors=True)
            self._run_shell_command(NUT_STOP_DRIVER_CMD, "Stop drivers", ignore_errors=True)
            
            # Wait for everything to stop
            logger.info("⏱️ Waiting for services to stop...")
            time.sleep(NUT_SERVICE_WAIT_TIME or 3)
            
            # Fix USB permissions
            logger.info("🔄 Updating USB permissions...")
            try:
                subprocess.run(
                    ["chmod", "-R", "777", "/dev/bus/usb/"],
                    check=False,
                    timeout=5
                )
            except Exception as e:
                logger.warning(f"⚠️ Failed to update USB permissions: {str(e)}")
            
            # Now start everything in the correct order using commands that work
            logger.info("🔄 Starting NUT services...")
            
            # Start the driver first using the correct start command from settings
            success_driver = self._run_shell_command(NUT_START_DRIVER_CMD, "Start drivers")
            
            # If driver started successfully, start upsd
            if success_driver:
                # Start upsd using the correct command from settings
                success_upsd = self._run_shell_command(NUT_START_SERVER_CMD, "Start upsd")
                
                # If upsd started successfully, start upsmon
                if success_upsd:
                    # Start upsmon using the correct command from settings
                    success_upsmon = self._run_shell_command(NUT_START_MONITOR_CMD, "Start upsmon")
                    
                    if success_upsmon:
                        logger.info("✅ All NUT services restarted successfully")
                    else:
                        logger.warning("⚠️ Failed to start upsmon after USB reconnection")
                else:
                    logger.warning("⚠️ Failed to start upsd after USB reconnection")
            else:
                logger.warning("⚠️ Failed to start UPS drivers after USB reconnection")
            
            # Reset the recovery mode flags but keep the connected=False
            # This will be updated on the next successful connection check
            self._is_usb_disconnect = False
            self._recovery_attempts = 0
            
            # Notify the frontend about reconnection attempt
            try:
                # Save the status to a temporary file that can be read by the frontend
                status_file = os.path.join('/tmp', 'ups_usb_status.json')
                status_data = {
                    "event": "usb_reconnect_attempt",
                    "timestamp": datetime.now().isoformat(),
                    "status": "RECONNECT_ATTEMPT"
                }
                
                with open(status_file, 'w') as f:
                    json.dump(status_data, f)
                logger.info(f"✅ Saved USB reconnect attempt status to {status_file}")
                
                # Also try to notify via HTTP socket
                try:
                    msg_data = json.dumps(status_data)
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)  # 1 second timeout
                    
                    # Use the SERVER_HOST and SERVER_PORT from settings
                    sock.connect((SERVER_HOST, SERVER_PORT))
                    
                    http_msg = (
                        f"POST /internal/ws_event HTTP/1.1\r\n"
                        f"Host: {SERVER_HOST}:{SERVER_PORT}\r\n"
                        f"Content-Type: application/json\r\n"
                        f"Content-Length: {len(msg_data)}\r\n"
                        f"\r\n"
                        f"{msg_data}"
                    )
                    
                    sock.sendall(http_msg.encode())
                    sock.close()
                    logger.info("✅ Sent USB reconnect attempt event to server")
                except Exception as socket_err:
                    logger.warning(f"⚠️ Could not send WebSocket event: {str(socket_err)}")
            except Exception as notify_err:
                logger.warning(f"⚠️ Error notifying about USB reconnection attempt: {str(notify_err)}")
            
            # Run an additional check to confirm services are running properly
            self._verify_nut_services()
            
            return True
        except Exception as e:
            logger.error(f"❌ Error handling USB reconnection: {str(e)}")
            return False
    
    def _run_shell_command(self, command, description, ignore_errors=False):
        """
        Execute a shell command directly
        
        Args:
            command: The shell command to run
            description: Description for logging
            ignore_errors: Whether to ignore errors
            
        Returns:
            bool: True on success, False on error
        """
        try:
            # Execute command with shell=True to use the exact command from settings
            logger.debug(f"🔄 Executing {description}: {command}")
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Check results
            if result.returncode == 0:
                logger.info(f"✅ {description} succeeded")
                return True
            else:
                stderr = result.stderr.strip()
                stdout = result.stdout.strip()
                
                # Log it as a warning or error based on ignore_errors flag
                if ignore_errors:
                    logger.debug(f"⚠️ {description} exited with code {result.returncode}: {stderr or stdout}")
                else:
                    logger.warning(f"⚠️ {description} failed with code {result.returncode}: {stderr or stdout}")
                
                return False
        except Exception as e:
            if ignore_errors:
                logger.debug(f"⚠️ Error executing {description}: {str(e)}")
            else:
                logger.error(f"❌ Error executing {description}: {str(e)}")
            return False
            
    def _verify_nut_services(self):
        """
        Verify the NUT services are running properly after restart
        """
        try:
            logger.info("🔍 Verifying NUT services status...")
            
            # Track if a COMMOK notification has been sent
            commok_sent = False
            
            # Check if the UPS driver is running
            driver_running = False
            ps_result = subprocess.run(
                ["ps", "aux"], 
                capture_output=True, 
                text=True,
                timeout=10
            )
            
            if ps_result.returncode == 0:
                ps_output = ps_result.stdout
                if "usbhid-ups" in ps_output:
                    logger.info("✅ UPS driver is running")
                    driver_running = True
                else:
                    logger.warning("⚠️ UPS driver does not appear to be running")
            
            # Try to run nut-scanner to check if we can detect our UPS
            scanner_result = subprocess.run(
                ["nut-scanner", "--usb_scan"], 
                capture_output=True, 
                text=True,
                timeout=30
            )
            
            if scanner_result.returncode == 0:
                scanner_output = scanner_result.stdout
                if "driver =" in scanner_output:
                    logger.info(f"✅ nut-scanner detected a UPS: {scanner_output}")
                    # If we successfully detect the UPS, trigger a COMMOK event
                    if not commok_sent:
                        self._trigger_commok_notification()
                        commok_sent = True
                else:
                    logger.warning("⚠️ nut-scanner did not detect any UPS devices")
            else:
                logger.warning(f"⚠️ nut-scanner failed: {scanner_result.stderr}")
                
            # Try a simple upsc command to verify full connectivity
            upsc_result = subprocess.run(
                ["upsc", "ups@localhost"], 
                capture_output=True, 
                text=True,
                timeout=10
            )
            
            if upsc_result.returncode == 0:
                logger.info("✅ upsc connected to UPS successfully")
                # If upsc succeeds and we haven't sent a notification yet, send one
                if not commok_sent:
                    self._trigger_commok_notification()
                    commok_sent = True
            else:
                logger.warning(f"⚠️ upsc could not connect to UPS: {upsc_result.stderr}")
                
        except Exception as e:
            logger.error(f"❌ Error verifying NUT services: {str(e)}")
    
    def _trigger_commok_notification(self):
        """
        Trigger a COMMOK notification by calling ups_notifier.py directly
        """
        try:
            # Get UPS name from configuration
            ups_name = None
            if ups_config.is_initialized():
                ups_name = f"{ups_config.name}@{ups_config.host}"
            
            if not ups_name:
                logger.warning("⚠️ Cannot trigger COMMOK notification: UPS name unknown")
                return
            
            logger.info(f"🔔 Triggering COMMOK notification for {ups_name}")
            
            # Path to the notifier script
            notifier_script = get_ups_notifier_command_path()
            
            if not os.path.exists(notifier_script):
                logger.warning(f"⚠️ Notifier script not found at {notifier_script}")
                return
            
            # Call the script with the UPS name and COMMOK event
            result = subprocess.run(
                ["python3", notifier_script, ups_name, "COMMOK"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info("✅ Successfully triggered COMMOK notification")
            else:
                logger.warning(f"⚠️ Failed to trigger COMMOK notification: {result.stderr}")
                
        except Exception as e:
            logger.error(f"❌ Error triggering COMMOK notification: {str(e)}")
    
    def _notify_container_restart_needed(self):
        """
        Notify the frontend that a container restart is needed for full USB reconnection
        """
        try:
            restart_message = {
                "event": "container_restart_needed",
                "timestamp": datetime.now().isoformat(),
                "message": "USB reconnection requires container restart",
                "status": "RESTART_NEEDED"
            }
            
            # Convert to JSON
            json_message = json.dumps(restart_message)
            
            # Try to send to the local Socket.IO server
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)  # 1 second timeout
                
                # Use the SERVER_HOST and SERVER_PORT from settings
                sock.connect((SERVER_HOST, SERVER_PORT))
                
                http_msg = (
                    f"POST /internal/ws_event HTTP/1.1\r\n"
                    f"Host: {SERVER_HOST}:{SERVER_PORT}\r\n"
                    f"Content-Type: application/json\r\n"
                    f"Content-Length: {len(json_message)}\r\n"
                    f"\r\n"
                    f"{json_message}"
                )
                
                sock.sendall(http_msg.encode())
                sock.close()
                logger.info("✅ Sent container restart needed notification to server")
            except Exception as e:
                logger.warning(f"⚠️ Could not send container restart WebSocket event: {str(e)}")
                
            # Also save to a status file that can be polled by the frontend
            try:
                status_path = os.path.join('/tmp', 'container_restart_needed.json')
                with open(status_path, 'w') as f:
                    json.dump(restart_message, f)
                logger.debug(f"📄 Saved container restart notification to {status_path}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to save container restart status file: {str(e)}")
                
        except Exception as e:
            logger.error(f"❌ Error sending container restart notification: {str(e)}")
    
    def is_connected(self):
        """
        Check if the connection is currently active
        
        Returns:
            bool: True if connected, False otherwise
        """
        with self._state_lock:
            return self._connected
    
    def get_status(self):
        """
        Get detailed status information about the connection
        
        Returns:
            dict: Status information
        """
        with self._state_lock:
            now = self._get_current_time_with_timezone()
            
            # Calculate current downtime if disconnected
            current_downtime = None
            if not self._connected and self._connection_lost_time:
                current_downtime = now - self._connection_lost_time
            
            return {
                "connected": self._connected,
                "in_recovery_mode": self._in_recovery_mode,
                "is_usb_disconnect": self._is_usb_disconnect,
                "recovery_attempts": self._recovery_attempts,
                "total_failures": self._total_failures,
                "total_recoveries": self._total_recoveries,
                "total_usb_disconnects": self._total_usb_disconnects,
                "total_usb_reconnects": self._total_usb_reconnects,
                "last_successful_check": self._last_successful_check,
                "connection_lost_time": self._connection_lost_time,
                "current_downtime": current_downtime,
                "last_state_change": self._last_state_change,
            }
    
    def get_recovery_status(self):
        """
        Get a short status string for recovery mode
        
        Returns:
            str: Status message
        """
        with self._state_lock:
            if self._connected:
                return "Connected"
                
            if self._is_usb_disconnect:
                return f"USB Disconnected (scanning for device)"
                
            if not self._in_recovery_mode:
                return "Disconnected"
                
            if self._recovery_attempts < self._initial_retry_count:
                return f"Initial recovery ({self._recovery_attempts}/{self._initial_retry_count})"
            else:
                minutes = (self._recovery_attempts - self._initial_retry_count) * self._extended_retry_interval // 60
                return f"Extended recovery ({minutes} minutes)"

    def _send_usb_disconnect_event(self):
        """
        Send a WebSocket message to notify the frontend about USB disconnection
        """
        try:
            # Create a message with USB disconnect info
            message = {
                "event": "usb_disconnect",
                "timestamp": datetime.now().isoformat(),
                "status": "NOCOMM",
                "is_usb_disconnect": True,
                "recovery_attempts": self._recovery_attempts,
                "vendor_id": self._usb_vendor_id,
                "product_id": self._usb_product_id,
                "serial": self._usb_serial
            }
            
            # Convert to JSON
            json_message = json.dumps(message)
            
            # Try to send to the local Socket.IO server
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)  # 1 second timeout
                
                # Use SERVER_HOST and SERVER_PORT from settings
                sock.connect((SERVER_HOST, SERVER_PORT))
                http_message = (
                    f"POST /internal/ws_event HTTP/1.1\r\n"
                    f"Host: {SERVER_HOST}:{SERVER_PORT}\r\n"
                    f"Content-Type: application/json\r\n"
                    f"Content-Length: {len(json_message)}\r\n"
                    f"\r\n"
                    f"{json_message}"
                )
                sock.sendall(http_message.encode())
                sock.close()
                logger.debug("📤 Sent USB disconnect event to WebSocket server")
            except Exception as e:
                logger.warning(f"⚠️ Failed to send USB disconnect event: {str(e)}")
            
            # As a fallback, also save to a status file that can be polled by the frontend
            try:
                status_path = os.path.join('/tmp', 'ups_usb_status.json')
                with open(status_path, 'w') as f:
                    json.dump(message, f)
                logger.debug(f"📄 Saved USB disconnect status to {status_path}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to save USB status file: {str(e)}")
            
        except Exception as e:
            logger.error(f"❌ Error sending USB disconnect event: {str(e)}")


# Singleton instance
connection_monitor = ConnectionMonitor()

def check_ups_connection():
    """
    Standalone function to check UPS connection
    
    Returns:
        bool: True if connected, False otherwise
    """
    return connection_monitor.check_connection()

def is_ups_connected():
    """
    Standalone function to check if UPS is connected
    
    Returns:
        bool: True if connected, False otherwise
    """
    return connection_monitor.is_connected()

def start_connection_monitoring():
    """
    Start the UPS connection monitoring
    
    Returns:
        bool: True if started, False otherwise
    """
    return connection_monitor.start_monitoring()

def stop_connection_monitoring():
    """
    Stop the UPS connection monitoring
    
    Returns:
        bool: True if stopped, False otherwise
    """
    return connection_monitor.stop_monitoring()

def get_ups_connection_status():
    """
    Get detailed status of UPS connection
    
    Returns:
        dict: Status information
    """
    return connection_monitor.get_status() 
