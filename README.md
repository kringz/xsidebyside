# Trino Version Comparison Application

A web application that compares different versions of Trino by scraping release notes from the Trino documentation website and organizing changes by connector type.

## Features

- Scrapes Trino release notes to extract version information and changes
- Allows users to compare any two Trino versions
- Organizes changes by connector type with a separate "general" category
- Caches search results in a PostgreSQL database to avoid redundant scraping
- Highlights breaking changes
- Links directly to specific sections in the official Trino documentation

## Deployment Instructions

### Automated Deployment

1. Copy the entire project directory to your Ubuntu server at `/var/www/xsidebyside.com`
2. Navigate to the project directory:
   ```
   cd /var/www/xsidebyside.com
   ```
3. Make the deployment script executable:
   ```
   chmod +x deploy.sh
   ```
4. Run the deployment script with sudo:
   ```
   sudo ./deploy.sh
   ```
5. Follow the prompts during installation

The deployment script will:
- Detect whether the application files are in the current directory or in a nested xsidebyside.com directory
- Install required system packages
- Set up a PostgreSQL database named `trino_sidebyside`
- Configure Apache with the necessary virtual host for the xsidebyside.com domain
- Set up a Python virtual environment with all dependencies
- Configure SSL with Let's Encrypt (optional)

### Manual Deployment

If you prefer to deploy manually, follow these steps:

1. Install required system packages:
   ```
   sudo apt-get update
   sudo apt-get install python3 python3-pip python3-venv postgresql postgresql-contrib libpq-dev apache2 libapache2-mod-wsgi-py3
   ```

2. Use the existing directory at `/var/www/xsidebyside.com`

3. Copy application files:
   ```
   sudo cp -r public_html/* /var/www/xsidebyside.com/
   sudo cp wsgi.py /var/www/xsidebyside.com/
   ```

4. Set up a Python virtual environment:
   ```
   sudo python3 -m venv /var/www/xsidebyside.com/venv
   sudo /var/www/xsidebyside.com/venv/bin/pip install --upgrade pip
   sudo /var/www/xsidebyside.com/venv/bin/pip install -r requirements.txt
   ```

5. Configure PostgreSQL:
   ```
   sudo -u postgres psql -c "CREATE DATABASE trino_sidebyside;"
   sudo -u postgres psql -c "CREATE USER trino_sidebyside WITH PASSWORD 'your_password';"
   sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE trino_sidebyside TO trino_sidebyside;"
   ```

6. Create a .env file:
   ```
   echo "DATABASE_URL=postgresql://trino_sidebyside:your_password@localhost/trino_sidebyside" | sudo tee /var/www/xsidebyside.com/.env
   echo "FLASK_SECRET_KEY=your_random_secret_key" | sudo tee -a /var/www/xsidebyside.com/.env
   ```

7. Copy the Apache configuration:
   ```
   sudo cp trino-sidebyside.conf /etc/apache2/sites-available/
   ```

8. Enable the site and necessary modules:
   ```
   sudo a2ensite trino-sidebyside
   sudo a2enmod wsgi
   sudo a2enmod rewrite
   ```

9. Restart Apache:
   ```
   sudo systemctl restart apache2
   ```

## Accessing the Application

After deployment, the application will be available at http://xsidebyside.com. 

If you enabled SSL during deployment, it will also be available securely at https://xsidebyside.com.

## Troubleshooting

- Check Apache error logs:
  ```
  sudo tail -f /var/log/apache2/trino-sidebyside_error.log
  ```

- Check PostgreSQL connection:
  ```
  sudo -u postgres psql -c "SELECT 1 FROM pg_database WHERE datname='trino_sidebyside';"
  ```

- Restart Apache after configuration changes:
  ```
  sudo systemctl restart apache2
  ```

## License

This project is licensed under the MIT License - see the LICENSE file for details.