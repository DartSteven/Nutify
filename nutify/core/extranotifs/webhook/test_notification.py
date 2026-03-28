"""
Test script for Discord webhook notifications
"""
import sys
import os
import json
import datetime
from core.extranotifs.webhook.webhook import WebhookNotifier

def test_discord_webhook(webhook_url, test_message="Test notification from Nutify"):
    """
    Test sending a notification to a Discord webhook
    
    Args:
        webhook_url (str): Discord webhook URL
        test_message (str): Test message to send
        
    Returns:
        dict: Response from the webhook
    """
    # Create a test configuration for Discord
    config = {
        'name': 'Discord Test',
        'url': webhook_url,
        'server_type': 'discord',
        'content_type': 'application/json',
        'auth_type': 'none',
        'include_ups_data': True,
        'verify_ssl': True,
        'discord': {
            'content': test_message,
            'username': 'Nutify UPS Monitor',
            'avatar_url': 'https://github.com/nutify/nutify/raw/main/static/img/logo.png'
        }
    }
    
    # Create a test event
    event_type = 'TEST'
    
    # Mock UPS data for the test
    test_data = {
        'ups_info': {
            'ups_model': 'Test UPS Model',
            'device_serial': 'SERIAL123456',
            'battery_charge': '80',
            'ups_status': 'OL',
            'input_voltage': '230V'
        }
    }
    
    # Create webhook notifier
    notifier = WebhookNotifier(config)
    
    # Send the test notification
    result = notifier.send_notification(event_type, test_data)
    
    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_discord.py <discord_webhook_url> [test_message]")
        sys.exit(1)
        
    webhook_url = sys.argv[1]
    test_message = sys.argv[2] if len(sys.argv) > 2 else "Test notification from Nutify"
    
    print(f"Testing Discord webhook: {webhook_url}")
    result = test_discord_webhook(webhook_url, test_message)
    
    if result.get('success'):
        print("✅ Discord webhook test successful!")
    else:
        print(f"❌ Discord webhook test failed: {result.get('message')}")
        
    print(json.dumps(result, indent=2)) 