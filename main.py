import sys
import os
from pathlib import Path

# Add the project directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "xsidebyside.com" / "public_html"))

# Import the Flask application
from app import app

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)