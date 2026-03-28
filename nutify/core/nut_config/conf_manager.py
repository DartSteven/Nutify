"""Nut Config Module.

Implements core runtime logic and helpers used by this feature.
"""

import os
import re
from flask import current_app

class NUTConfManager:
    """
    Manager for NUT configuration files that uses template files
    to generate the appropriate configuration based on the NUT mode
    and user inputs.
    """
    
    def __init__(self, templates_dir):
        """
        Initialize the configuration manager.
        
        Args:
            templates_dir: Path to the directory containing template files
        """
        self.templates_dir = templates_dir
    
    def get_template_path(self, filename, mode):
        """
        Get the path to the appropriate template file based on the mode.
        
        Args:
            filename: Base filename (e.g., 'nut.conf', 'ups.conf')
            mode: NUT mode ('standalone', 'netserver', 'netclient')
            
        Returns:
            Path to the template file
        """
        # Try mode-specific template first
        template_path = os.path.join(self.templates_dir, f"{filename}.{mode}")
        
        # If it doesn't exist, fall back to the empty template for netclient mode
        if not os.path.exists(template_path) and mode == 'netclient':
            template_path = os.path.join(self.templates_dir, f"{filename}.empty")
            
            # If empty template doesn't exist, log an error
            if not os.path.exists(template_path):
                current_app.logger.error(f"No template found for {filename} in {mode} mode")
                return None
        
        # If file exists, return the path
        if os.path.exists(template_path):
            return template_path
        
        # If no template found, log error
        current_app.logger.error(f"No template found for {filename} in {mode} mode")
        return None
    
    def render_template(self, template_path, variables):
        """
        Render a template by replacing variables with their values.
        
        Args:
            template_path: Path to the template file
            variables: Dictionary of variables to replace
            
        Returns:
            Rendered template content
        """
        if not template_path or not os.path.exists(template_path):
            return ""
        
        try:
            with open(template_path, 'r') as f:
                content = f.read()
            
            # Log variables for debugging
            current_app.logger.debug(f"Rendering template {template_path}")
            current_app.logger.debug(f"Variables: {variables}")
            
            # Replace variables in the template
            for key, value in variables.items():
                placeholder = f"{{{{%s}}}}" % key
                if placeholder in content:
                    current_app.logger.debug(f"Replacing {placeholder} with {value}")
                    content = content.replace(placeholder, str(value))
                else:
                    current_app.logger.debug(f"Placeholder {placeholder} not found in template")
            
            # Check for any remaining unmatched placeholders
            remaining_placeholders = re.findall(r'{{([^}]+)}}', content)
            if remaining_placeholders:
                current_app.logger.warning(f"Unmatched placeholders in template {template_path}: {remaining_placeholders}")
                
                # Auto-replace common placeholders with sensible defaults
                common_defaults = {
                    'ADMIN_USERNAME': 'admin',
                    'ADMIN_PASSWORD': 'adminpass',
                    'MONITOR_USERNAME': 'monuser',
                    'MONITOR_PASSWORD': 'monpass',
                    'UPS_NAME': 'ups',
                    'DRIVER': 'usbhid-ups',
                    'PORT': 'auto',
                    'DESCRIPTION': 'UPS',
                    'ADDITIONAL_USERS': ''
                }
                
                for placeholder in remaining_placeholders:
                    if placeholder in common_defaults:
                        default_value = common_defaults[placeholder]
                        current_app.logger.warning(f"Auto-replacing {placeholder} with default: {default_value}")
                        content = content.replace(f"{{{{{placeholder}}}}}", default_value)
            
            return content
        except Exception as e:
            current_app.logger.error(f"Error rendering template {template_path}: {e}")
            return ""
    
    def get_conf_files(self, mode, variables):
        """
        Get all configuration files for the specified mode with variables replaced.
        
        Args:
            mode: NUT mode ('standalone', 'netserver', 'netclient')
            variables: Dictionary of variables to replace in templates
            
        Returns:
            Dictionary of configuration files with their content
        """
        conf_files = {
            'nut.conf': '',
            'ups.conf': '',
            'upsd.conf': '',
            'upsd.users': '',
            'upsmon.conf': ''
        }
        
        # For each configuration file, get the appropriate template and render it
        for filename in conf_files.keys():
            template_path = self.get_template_path(filename, mode)
            if template_path:
                conf_files[filename] = self.render_template(template_path, variables)
        
        return conf_files
    
    def validate_mode(self, mode):
        """
        Validate that the NUT mode is supported.
        
        Args:
            mode: NUT mode to validate
            
        Returns:
            True if valid, False otherwise
        """
        valid_modes = ['standalone', 'netserver', 'netclient']
        return mode in valid_modes
    
    def clean_variable_name(self, value):
        """
        Clean a value to be safe for use in a configuration file.
        
        Args:
            value: Value to clean
            
        Returns:
            Cleaned value
        """
        if value is None:
            return ""
        
        # Basic cleaning to prevent injection
        value = str(value)
        value = value.replace('"', '\\"')  # Escape double quotes
        return value 