#!/bin/bash
# Deployment script for Trino Version Comparison app
# Run this script on your Ubuntu server as a user with sudo privileges

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting deployment of Trino Version Comparison application...${NC}"

# Check if running as root/sudo
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Please run this script with sudo or as root${NC}"
  exit 1
fi

# Get the directory of this script
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
APP_NAME="trino-sidebyside"
APP_PATH="/var/www/xsidebyside.com"  # Use the existing directory
DOMAIN="xsidebyside.com"
VENV_PATH="${APP_PATH}/venv"

# Remove the nested xsidebyside.com directory reference
CONTENT_DIR="${SCRIPT_DIR}"
if [[ "${SCRIPT_DIR}" == *"/xsidebyside.com/xsidebyside.com" ]]; then
  # We're in a nested directory structure from git clone
  CONTENT_DIR="${SCRIPT_DIR}"
elif [[ "${SCRIPT_DIR}" == *"/xsidebyside.com" ]]; then
  # We're already in the correct directory
  CONTENT_DIR="${SCRIPT_DIR}"
else
  # We might be in the parent directory of xsidebyside.com
  if [ -d "${SCRIPT_DIR}/xsidebyside.com" ]; then
    CONTENT_DIR="${SCRIPT_DIR}/xsidebyside.com"
  fi
fi

echo -e "${YELLOW}Installing required packages...${NC}"
apt-get update
apt-get install -y python3 python3-pip python3-venv postgresql postgresql-contrib libpq-dev apache2 libapache2-mod-wsgi-py3

echo -e "${YELLOW}Creating application directory at ${APP_PATH}...${NC}"
mkdir -p ${APP_PATH}

echo -e "${YELLOW}Copying application files...${NC}"
if [ -d "${CONTENT_DIR}/public_html" ]; then
  # Copy files from the public_html directory
  cp -r ${CONTENT_DIR}/public_html/* ${APP_PATH}/
else
  echo -e "${YELLOW}public_html directory not found, looking for application files directly...${NC}"
  # Look for application files directly in the current directory
  for file in app.py main.py models.py scraper.py views.py; do
    if [ -f "${CONTENT_DIR}/$file" ]; then
      cp ${CONTENT_DIR}/$file ${APP_PATH}/
    fi
  done
  
  # Copy templates and static directories if they exist
  for dir in templates static; do
    if [ -d "${CONTENT_DIR}/$dir" ]; then
      mkdir -p ${APP_PATH}/$dir
      cp -r ${CONTENT_DIR}/$dir/* ${APP_PATH}/$dir/
    fi
  done
fi

# Copy wsgi.py if it exists
if [ -f "${CONTENT_DIR}/wsgi.py" ]; then
  cp ${CONTENT_DIR}/wsgi.py ${APP_PATH}/
fi

# Create a Python virtual environment
echo -e "${YELLOW}Setting up Python virtual environment...${NC}"
python3 -m venv ${VENV_PATH}
${VENV_PATH}/bin/pip install --upgrade pip

# Install requirements from the appropriate location
if [ -f "${CONTENT_DIR}/requirements.txt" ]; then
  ${VENV_PATH}/bin/pip install -r ${CONTENT_DIR}/requirements.txt
elif [ -f "${SCRIPT_DIR}/requirements.txt" ]; then
  ${VENV_PATH}/bin/pip install -r ${SCRIPT_DIR}/requirements.txt
else
  # If requirements.txt doesn't exist, install required packages directly
  echo -e "${YELLOW}Installing required Python packages...${NC}"
  ${VENV_PATH}/bin/pip install flask flask-sqlalchemy gunicorn psycopg2-binary requests beautifulsoup4 trafilatura email-validator
fi

# Setup proper permissions
echo -e "${YELLOW}Setting correct permissions...${NC}"
chown -R www-data:www-data ${APP_PATH}
chmod -R 755 ${APP_PATH}

# Configure PostgreSQL (if not already configured)
echo -e "${YELLOW}Setting up PostgreSQL database...${NC}"
if ! sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw "${APP_NAME//-/_}"; then
  # Create database and user
  sudo -u postgres psql -c "CREATE DATABASE ${APP_NAME//-/_};"
  # Generate a random password for the database user
  DB_PASSWORD=$(tr -dc 'a-zA-Z0-9' < /dev/urandom | fold -w 16 | head -n 1)
  sudo -u postgres psql -c "CREATE USER ${APP_NAME//-/_} WITH PASSWORD '${DB_PASSWORD}';"
  sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${APP_NAME//-/_} TO ${APP_NAME//-/_};"
  
  # Create a .env file with database configuration
  cat > ${APP_PATH}/.env << EOF
DATABASE_URL=postgresql://${APP_NAME//-/_}:${DB_PASSWORD}@localhost/${APP_NAME//-/_}
FLASK_SECRET_KEY=$(tr -dc 'a-zA-Z0-9' < /dev/urandom | fold -w 32 | head -n 1)
EOF

  # Ensure the file is readable by the web server
  chown www-data:www-data ${APP_PATH}/.env
  chmod 600 ${APP_PATH}/.env
fi

# Create Apache WSGI configuration
echo -e "${YELLOW}Creating Apache WSGI configuration...${NC}"
cat > /etc/apache2/sites-available/${APP_NAME}.conf << EOF
<VirtualHost *:80>
    ServerName ${DOMAIN}
    ServerAdmin webmaster@${DOMAIN}
    
    DocumentRoot ${APP_PATH}
    
    <Directory ${APP_PATH}>
        Require all granted
        Options -Indexes +FollowSymLinks
        AllowOverride All
    </Directory>
    
    WSGIDaemonProcess ${APP_NAME} python-home=${VENV_PATH} python-path=${APP_PATH}
    WSGIProcessGroup ${APP_NAME}
    WSGIScriptAlias / ${APP_PATH}/wsgi.py
    
    ErrorLog \${APACHE_LOG_DIR}/${APP_NAME}_error.log
    CustomLog \${APACHE_LOG_DIR}/${APP_NAME}_access.log combined
</VirtualHost>
EOF

# Create WSGI file if it doesn't exist
if [ ! -f "${APP_PATH}/wsgi.py" ]; then
  echo -e "${YELLOW}Creating WSGI file...${NC}"
  cat > ${APP_PATH}/wsgi.py << EOF
#!/usr/bin/env python3
import sys
import os

# Add the application directory to the Python path
sys.path.insert(0, '${APP_PATH}')

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv('${APP_PATH}/.env')

# Import the Flask application
from app import app as application
EOF
  chown www-data:www-data ${APP_PATH}/wsgi.py
  chmod 755 ${APP_PATH}/wsgi.py
fi

# Enable the site and necessary modules
echo -e "${YELLOW}Enabling Apache site and modules...${NC}"
a2ensite ${APP_NAME}
a2enmod wsgi
a2enmod rewrite

# Configure SSL with Let's Encrypt (optional)
echo -e "${YELLOW}Would you like to configure SSL with Let's Encrypt? (y/n)${NC}"
read -p "" setup_ssl

if [ "$setup_ssl" = "y" ] || [ "$setup_ssl" = "Y" ]; then
  echo -e "${YELLOW}Installing certbot for Let's Encrypt...${NC}"
  apt-get install -y certbot python3-certbot-apache
  
  echo -e "${YELLOW}Obtaining SSL certificate...${NC}"
  certbot --apache -d ${DOMAIN} --non-interactive --agree-tos --email webmaster@${DOMAIN}
fi

# Restart Apache
echo -e "${YELLOW}Restarting Apache...${NC}"
systemctl restart apache2

echo -e "${GREEN}Deployment completed!${NC}"
echo -e "${GREEN}Your Trino Version Comparison application should now be available at: http://${DOMAIN}${NC}"
if [ "$setup_ssl" = "y" ] || [ "$setup_ssl" = "Y" ]; then
  echo -e "${GREEN}Secure access is available at: https://${DOMAIN}${NC}"
fi

# Installation summary
echo -e "\n${YELLOW}===================== INSTALLATION SUMMARY =====================${NC}"
echo -e "${YELLOW}Application installed at:${NC} ${APP_PATH}"
echo -e "${YELLOW}Virtual environment:${NC} ${VENV_PATH}"
echo -e "${YELLOW}Apache config:${NC} /etc/apache2/sites-available/${APP_NAME}.conf"
echo -e "${YELLOW}Database name:${NC} ${APP_NAME//-/_}"
echo -e "${YELLOW}Database user:${NC} ${APP_NAME//-/_}"
if [ -f "${APP_PATH}/.env" ]; then
  echo -e "${YELLOW}Database password:${NC} Stored in ${APP_PATH}/.env"
fi
echo -e "${YELLOW}Logs:${NC} /var/log/apache2/${APP_NAME}_*.log"
echo -e "${YELLOW}=================================================================${NC}"

# Notes for manual steps
echo -e "\n${YELLOW}IMPORTANT NOTES:${NC}"
echo -e "1. Make sure your domain ${DOMAIN} is pointed to this server's IP address"
echo -e "2. If you need to modify Apache configuration, edit: /etc/apache2/sites-available/${APP_NAME}.conf"
echo -e "3. To view application logs: tail -f /var/log/apache2/${APP_NAME}_*.log"
echo -e "4. To manually restart Apache: sudo systemctl restart apache2"