import sys
import os
from pathlib import Path

# Add the application directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables from .env file if it exists
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        # python-dotenv not installed, read .env manually
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

# Import the Flask application
from app import app as application

# Run the WSGI server when this script is executed directly
if __name__ == "__main__":
    application.run(host='0.0.0.0', port=5000)
