"""
Handles the central instance of SocketIO
"""
from flask_socketio import SocketIO

# Remove the configuration from here, it will be done in app.py
socketio = SocketIO()

def init_socketio(app):
    """Initialize socketio with the Flask app"""
    socketio.init_app(app) 