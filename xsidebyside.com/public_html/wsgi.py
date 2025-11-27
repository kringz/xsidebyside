import sys
import os
from pathlib import Path

# Add the application directory to the Python path
# Add the application directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

# Add virtual environment site-packages
venv_site_packages = "/xsidebyside.com/venv/lib/python3.10/site-packages"
if os.path.exists(venv_site_packages):
    sys.path.insert(0, venv_site_packages)

# Debug logging
print(f"DEBUG: sys.executable: {sys.executable}", file=sys.stderr)
print(f"DEBUG: sys.path: {sys.path}", file=sys.stderr)
try:
    import flask_wtf
    print(f"DEBUG: flask_wtf file: {flask_wtf.__file__}", file=sys.stderr)
except ImportError as e:
    print(f"DEBUG: Failed to import flask_wtf: {e}", file=sys.stderr)


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
# Reloaded at 2024-11-26 6:29 PM
from app import app as application

# Run the WSGI server when this script is executed directly
if __name__ == "__main__":
    application.run(host='0.0.0.0', port=5000)
