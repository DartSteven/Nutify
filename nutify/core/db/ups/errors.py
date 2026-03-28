"""
UPS Error Classes Module.
This module defines error classes for UPS operations.
"""

class UPSError(Exception):
    """Base class for UPS errors"""
    pass

class UPSConnectionError(UPSError):
    """Error raised when connection to the UPS fails"""
    pass

class UPSCommandError(UPSError):
    """Error raised when a UPS command execution fails"""
    pass

class UPSDataError(UPSError):
    """Error raised when processing UPS data fails"""
    pass 