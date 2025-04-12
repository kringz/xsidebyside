import sys
import os

# Add the application directory to the Python path
sys.path.insert(0, '/xsidebyside.com/public_html')

# Import the Flask application
from app import app as application

# Run the WSGI server when this script is executed directly
if __name__ == "__main__":
    application.run(host='0.0.0.0', port=5000)
