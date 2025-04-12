#!/usr/bin/env python3
import sys
import os

# Add the application directory to the Python path
sys.path.insert(0, os.path.dirname(__file__) + '/public_html')

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

# Import the Flask application
from app import app as application

if __name__ == '__main__':
    application.run()