#!/bin/bash

# Trino Version Comparison App Deployment Script
# ----------------------------------------------
# This script deploys the Trino version comparison application to an Ubuntu server
# running Apache2. It sets up the necessary directories, installs dependencies,
# and configures Apache to serve the Flask application using WSGI.

set -e

# Configuration variables
APP_DIR="/xsidebyside.com/public_html"
VENV_DIR="/xsidebyside.com/venv"
APACHE_SITE_NAME="trino_sidebyside"
DOMAIN="xsidebyside.com"

# Function to display messages
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Check if running as root
if [ "$(id -u)" -ne 0 ]; then
    log "Error: This script must be run as root. Please use sudo."
    exit 1
fi

# Create directory structure if it doesn't exist
log "Creating directory structure..."
mkdir -p $APP_DIR
mkdir -p $APP_DIR/static/css
mkdir -p $APP_DIR/static/js
mkdir -p $APP_DIR/templates

# Install required system packages
log "Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3-venv apache2 libapache2-mod-wsgi-py3

# Create and activate virtual environment
log "Setting up Python virtual environment..."
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# Install Python dependencies
log "Installing Python dependencies..."
pip install Flask==2.3.3 
pip install Flask-SQLAlchemy==3.1.1
pip install requests==2.31.0
pip install beautifulsoup4==4.12.2
pip install Flask-WTF==1.2.1
pip install lxml==4.9.3
pip install mod_wsgi==4.9.4

# Set permissions
log "Setting file permissions..."
chown -R www-data:www-data /xsidebyside.com
chmod -R 755 /xsidebyside.com

# Configure Apache
log "Configuring Apache..."
cp $APP_DIR/trino_sidebyside.conf /etc/apache2/sites-available/$APACHE_SITE_NAME.conf

# Enable the site and required modules
a2ensite $APACHE_SITE_NAME
a2enmod wsgi
a2enmod rewrite

# Restart Apache to apply changes
log "Restarting Apache..."
systemctl restart apache2

# Initialize the database
log "Initializing the database..."
cd $APP_DIR
source $VENV_DIR/bin/activate
python -c "from app import app, db; from scraper import TrinoScraper; with app.app_context(): db.create_all(); scraper = TrinoScraper(); scraper.update_database()"

log "Deployment completed successfully!"
log "The application should now be available at http://$DOMAIN"
log "For HTTPS support, please consider configuring Let's Encrypt with Certbot."
