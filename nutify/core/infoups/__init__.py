#!/usr/bin/env python3
"""
InfoUPS Module - UPS Information Pages and API

This module provides pages and API endpoints for displaying
detailed information about the UPS device.
"""

from flask import Blueprint

# Create Blueprint for UPS info pages
routes_infoups = Blueprint('routes_infoups', __name__, url_prefix='')

# Import routes after creating blueprint to avoid circular imports
from .routes_infoups import register_routes

__all__ = ['routes_infoups', 'register_routes'] 
