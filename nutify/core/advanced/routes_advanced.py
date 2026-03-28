"""
HTML routes for the advanced NUT configuration section.
Currently, all UI functionality is handled via the options_page.js and the options.html template.
This file is primarily used to register the blueprint and maintain consistency with the module structure.
"""

from flask import render_template
from core.logger import system_logger as logger

def register_routes(app):
    """Register all HTML routes for the advanced NUT Configuration section"""
    
    # No specific routes needed for the advanced section
    # All UI functionality is handled via JavaScript and the options.html template
    
    logger.info("✅ Registered Advanced NUT Configuration UI routes")
    return app 