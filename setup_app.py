#!/usr/bin/env python3
import os
import sys
import subprocess
import secrets
from pathlib import Path

def print_step(message):
    print(f"\n\033[1;34m==> {message}\033[0m")

def print_success(message):
    print(f"\033[1;32m✓ {message}\033[0m")

def print_error(message):
    print(f"\033[1;31m✗ {message}\033[0m")

def check_python_version():
    print_step("Checking Python version...")
    if sys.version_info < (3, 10):
        print_error("Python 3.10 or higher is required.")
        sys.exit(1)
    print_success(f"Python {sys.version_info.major}.{sys.version_info.minor} detected.")

def install_dependencies():
    print_step("Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print_success("Dependencies installed successfully.")
    except subprocess.CalledProcessError:
        print_error("Failed to install dependencies.")
        sys.exit(1)

def setup_env_file():
    print_step("Setting up environment variables...")
    env_path = Path("xsidebyside.com/public_html/.env")
    
    if env_path.exists():
        print_success(".env file already exists.")
        return

    print("Generating new .env file with secure secrets...")
    analytics_password = secrets.token_urlsafe(24)
    session_secret = secrets.token_hex(32)
    
    env_content = f"""# Analytics Configuration
ANALYTICS_ENABLED=true
ANALYTICS_USERNAME=admin
ANALYTICS_PASSWORD={analytics_password}

# Flask Session Secret
SESSION_SECRET={session_secret}

# Database URL (defaults to SQLite if not set)
# DATABASE_URL=sqlite:///trino_versions.db

# Logging level
LOG_LEVEL=INFO
"""
    
    try:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        with open(env_path, "w") as f:
            f.write(env_content)
        print_success(f".env file created at {env_path}")
        print(f"  - Analytics Password: {analytics_password}")
    except Exception as e:
        print_error(f"Failed to create .env file: {e}")
        sys.exit(1)

def init_database():
    print_step("Initializing database...")
    try:
        # Add the application directory to the Python path
        sys.path.insert(0, str(Path(__file__).parent / "xsidebyside.com" / "public_html"))
        
        # Import app to trigger db.create_all()
        from app import app, db
        
        with app.app_context():
            db.create_all()
            print_success("Database tables created successfully.")
            
            # Verify database file exists
            db_path = Path("xsidebyside.com/public_html/instance/trino_versions.db")
            if db_path.exists():
                print_success(f"Database file verified at {db_path}")
            else:
                print("Note: Database file might be in a different location depending on configuration.")
                
    except Exception as e:
        print_error(f"Failed to initialize database: {e}")
        sys.exit(1)

def main():
    print("\n\033[1;36mSide by Side - Application Setup\033[0m")
    print("================================")
    
    check_python_version()
    install_dependencies()
    setup_env_file()
    init_database()
    
    print("\n\033[1;32mSetup completed successfully!\033[0m")
    print("\nYou can now run the application with:")
    print("  python main.py")

if __name__ == "__main__":
    main()
