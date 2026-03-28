"""Email provider presets used by Settings -> Provider -> Mail."""

email_providers = {
    "gmail": {
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "tls": True,
        "tls_starttls": True,
        "auth": True,
        "notes": "Google SMTP: use STARTTLS on 587 (or SSL on 465). Use an App Password with 2-Step Verification.",
        "displayName": "Gmail",
    },
    "outlook": {
        "smtp_server": "smtp.office365.com",
        "smtp_port": 587,
        "tls": True,
        "tls_starttls": True,
        "auth": True,
        "notes": "Microsoft 365 SMTP client submission uses smtp.office365.com on port 587 with STARTTLS.",
        "displayName": "Outlook (Microsoft 365)",
    },
    "icloud": {
        "smtp_server": "smtp.mail.me.com",
        "smtp_port": 587,
        "tls": True,
        "tls_starttls": True,
        "auth": True,
        "notes": "Apple iCloud Mail requires SSL/TLS and app-specific password when 2FA is enabled.",
        "displayName": "Apple iCloud Mail",
    },
    "yahoo": {
        "smtp_server": "smtp.mail.yahoo.com",
        "smtp_port": 587,
        "tls": True,
        "tls_starttls": True,
        "auth": True,
        "notes": "Yahoo SMTP supports 465 (SSL) and 587 (TLS/STARTTLS). Use an app password.",
        "displayName": "Yahoo Mail",
    },
    "aol": {
        "smtp_server": "smtp.aol.com",
        "smtp_port": 465,
        "tls": True,
        "tls_starttls": False,
        "auth": True,
        "notes": "AOL SMTP commonly uses port 465 with SSL/TLS. Use an app password if required.",
        "displayName": "AOL Mail",
    },
    "gmx": {
        "smtp_server": "mail.gmx.com",
        "smtp_port": 587,
        "tls": True,
        "tls_starttls": True,
        "auth": True,
        "notes": "GMX SMTP: mail.gmx.com using 587 STARTTLS (or 465 SSL).",
        "displayName": "GMX Mail",
    },
    "protonmail": {
        "smtp_server": "smtp.protonmail.ch",
        "smtp_port": 587,
        "tls": True,
        "tls_starttls": True,
        "auth": True,
        "notes": "Proton SMTP submission uses SMTP token credentials (not your account password).",
        "displayName": "Proton Mail",
    },
    "amazon": {
        "smtp_server": "email-smtp.us-east-1.amazonaws.com",
        "smtp_port": 587,
        "tls": True,
        "tls_starttls": True,
        "auth": True,
        "notes": "AWS SES SMTP uses region endpoint + SMTP credentials. Sender address/domain must be verified.",
        "displayName": "Amazon SES",
        "requires_sender_email": True,
    },
    "sendgrid": {
        "smtp_server": "smtp.sendgrid.net",
        "smtp_port": 587,
        "tls": True,
        "tls_starttls": True,
        "auth": True,
        "notes": "SendGrid SMTP: username is 'apikey', password is your API key.",
        "displayName": "SendGrid",
    },
    "mailgun": {
        "smtp_server": "smtp.mailgun.org",
        "smtp_port": 587,
        "tls": True,
        "tls_starttls": True,
        "auth": True,
        "notes": "Mailgun SMTP relay supports STARTTLS on 587 with domain SMTP credentials.",
        "displayName": "Mailgun",
    },
    "postmark": {
        "smtp_server": "smtp.postmarkapp.com",
        "smtp_port": 587,
        "tls": True,
        "tls_starttls": True,
        "auth": True,
        "notes": "Postmark SMTP server is smtp.postmarkapp.com; use your Server Token as SMTP password.",
        "displayName": "Postmark",
    },
    "zoho": {
        "smtp_server": "smtp.zoho.com",
        "smtp_port": 587,
        "tls": True,
        "tls_starttls": True,
        "auth": True,
        "notes": "Zoho Mail SMTP uses 587 STARTTLS (or 465 SSL). Use app-specific password with 2FA.",
        "displayName": "Zoho Mail",
    },
}

def get_provider_config(provider_name):
    """
    Get the configuration for a specific email provider.
    
    Args:
        provider_name (str): The name of the provider
        
    Returns:
        dict: The provider configuration or None if not found
    """
    if not provider_name:
        return None
    return email_providers.get(str(provider_name).lower())

def get_all_providers():
    """
    Get all available email providers.
    
    Returns:
        dict: All email providers configurations
    """
    return email_providers

def get_provider_list():
    """
    Get a list of all available provider names.
    
    Returns:
        list: List of provider names
    """
    return list(email_providers.keys())

def add_provider(name, config):
    """
    Add a new email provider configuration.
    
    Args:
        name (str): The name of the provider
        config (dict): The provider configuration
        
    Returns:
        bool: True if added successfully, False otherwise
    """
    if name.lower() in email_providers:
        return False
    
    # Validate required fields
    required_fields = ['smtp_server', 'smtp_port', 'tls', 'tls_starttls']
    if not all(field in config for field in required_fields):
        return False
    
    email_providers[name.lower()] = config
    return True

def update_provider(name, config):
    """
    Update an existing email provider configuration.
    
    Args:
        name (str): The name of the provider
        config (dict): The provider configuration
        
    Returns:
        bool: True if updated successfully, False otherwise
    """
    if name.lower() not in email_providers:
        return False
    
    email_providers[name.lower()].update(config)
    return True

def remove_provider(name):
    """
    Remove an email provider configuration.
    
    Args:
        name (str): The name of the provider
        
    Returns:
        bool: True if removed successfully, False otherwise
    """
    if name.lower() not in email_providers:
        return False
    
    del email_providers[name.lower()]
    return True 
