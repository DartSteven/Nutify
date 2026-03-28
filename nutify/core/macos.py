"""
MacOS Compatibility Module.

This module provides compatibility fixes for macOS development environments.
It handles issues with eventlet and multiprocessing that occur specifically on macOS.
This can be removed in production environments.
"""

import logging
import sys
import os

# Set up logger
logger = logging.getLogger('macos_compat')

def configure_macos_compatibility():
    """
    Configure macOS compatibility fixes for eventlet and multiprocessing.
    This function should be called early in the application startup.
    """
    if sys.platform != 'darwin':
        logger.debug("Not running on macOS, skipping compatibility fixes")
        return False
        
    logger.info("Configuring macOS compatibility fixes")
    
    # Fix eventlet multiple readers check issue
    try:
        import eventlet.debug
        eventlet.debug.hub_prevent_multiple_readers(False)
        logger.info("✅ Disabled eventlet multiple readers check")
    except ImportError:
        logger.warning("❌ Failed to import eventlet.debug, skipping multiple readers fix")
    except Exception as e:
        logger.warning(f"❌ Failed to disable eventlet multiple readers check: {e}")
    
    # Fix eventlet kqueue hub with a safer implementation
    try:
        import eventlet.hubs.kqueue
        import select
        
        # Check if kevent is available
        has_kevent = hasattr(select, 'kevent')
        
        # Save original _control method
        original_control = eventlet.hubs.kqueue.Hub._control
        
        # Create a patched version that handles errors
        def patched_control(self, events, max_events, timeout):
            try:
                # If there are no events, just return an empty list
                if not events:
                    return []
                    
                # If kevent is available, continue with normal processing
                if has_kevent:
                    # Make sure events is properly formatted
                    if not isinstance(events[0], select.kevent):
                        # Just return an empty list if events are not properly formatted
                        logger.debug("Events not properly formatted, returning empty list")
                        return []
                    return original_control(self, events, max_events, timeout)
                else:
                    # On macOS where kevent is not available, just return an empty list
                    logger.debug("select.kevent not available, returning empty list")
                    return []
            except Exception as e:
                # Log the error but don't crash
                logger.debug(f"Error in kqueue control: {e}, returning empty list")
                return []
        
        # Replace the original with our patched version
        eventlet.hubs.kqueue.Hub._control = patched_control
        logger.info("✅ Patched eventlet.hubs.kqueue.Hub._control for macOS compatibility")
        
        # Also patch the add method to be safe
        original_add = eventlet.hubs.kqueue.Hub.add
        
        def patched_add(self, event_type, fileno, cb, tb, mark_as_closed):
            try:
                return original_add(self, event_type, fileno, cb, tb, mark_as_closed)
            except Exception as e:
                logger.debug(f"Error in kqueue add: {e}")
                # Return a dummy listener that can be removed without crashing
                class DummyListener:
                    def __init__(self):
                        self.tb = tb
                        self.mark_as_closed = mark_as_closed
                    def __call__(self, *args, **kwargs):
                        return cb(*args, **kwargs)
                return DummyListener()
        
        # Replace the original add method
        eventlet.hubs.kqueue.Hub.add = patched_add
        logger.info("✅ Patched eventlet.hubs.kqueue.Hub.add for macOS compatibility")
        
    except ImportError:
        logger.warning("❌ Failed to import eventlet.hubs.kqueue, skipping kqueue patch")
    except Exception as e:
        logger.warning(f"❌ Failed to patch kqueue: {e}")
    
    # Replace the kqueue hub with the poll hub on macOS (more stable)
    try:
        import eventlet.hubs
        # Force the use of poll hub instead of kqueue
        eventlet.hubs.use_hub('poll')
        logger.info("✅ Forced eventlet to use poll hub instead of kqueue")
    except Exception as e:
        logger.warning(f"❌ Failed to force poll hub: {e}")
    
    # Fix multiprocessing Value issue with kqueue
    try:
        import multiprocessing
        import multiprocessing.synchronize
        
        # Save the original Value function
        original_Value = multiprocessing.Value
        
        # Create a patched version that doesn't use locks
        def patched_Value(*args, **kwargs):
            kwargs.pop('lock', None)  # Remove lock to avoid kqueue errors
            return original_Value(*args, lock=False, **kwargs)
        
        # Replace the original with our patched version
        multiprocessing.Value = patched_Value
        logger.info("✅ Patched multiprocessing.Value to avoid kqueue errors")
    except ImportError:
        logger.warning("❌ Failed to import multiprocessing, skipping Value patch")
    except Exception as e:
        logger.warning(f"❌ Failed to patch multiprocessing.Value: {e}")
    
    # Fix subprocess calls with eventlet on macOS
    try:
        import eventlet.green.subprocess
        import subprocess
        
        # Save the original Popen
        original_popen = eventlet.green.subprocess.Popen
        
        # Create a patched version that falls back to regular subprocess for shell commands
        def patched_popen(*args, **kwargs):
            # Avoid eventlet wrapping for subprocess on macOS with shell=True
            if 'shell' in kwargs and kwargs['shell']:
                return subprocess.Popen(*args, **kwargs)
            return original_popen(*args, **kwargs)
        
        # Replace with our patched version
        eventlet.green.subprocess.Popen = patched_popen
        logger.info("✅ Patched eventlet subprocess for macOS compatibility")
    except ImportError:
        logger.warning("❌ Failed to import eventlet.green.subprocess, skipping Popen patch")
    except Exception as e:
        logger.warning(f"❌ Failed to patch eventlet.green.subprocess.Popen: {e}")
    
    # Set environment variable to run in non-fork mode - critical for macOS
    os.environ['EVENTLET_MONKEY_PATCH'] = '1'  # Ensure monkey patching is enabled
    os.environ['MULTIPROCESSING_FORK_DISABLE'] = '1'  # Force non-fork mode
    
    logger.info("✅ macOS compatibility configuration completed")
    return True 