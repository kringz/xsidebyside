# Trino Version Comparison

A Flask-based web application for comparing versions of Trino and Starburst. It allows users to view changes between versions, filter by connectors, and identify breaking changes.

![Application Architecture](docs/images/app_flowchart.png)

## Features

-   **Version Comparison**: Compare any two versions of Trino or Starburst.
-   **Connector Filtering**: Filter changes by specific connectors (e.g., Hive, Delta Lake).
-   **Breaking Changes**: Dedicated section for breaking changes.
-   **Search**: Search for specific changes by keyword.
-   **PDF Export**: Export comparison results to PDF.
-   **Analytics**: Track popular searches and comparisons (requires authentication).

## Tech Stack

-   **Backend**: Python 3.11+, Flask, SQLAlchemy
-   **Database**: SQLite (default), PostgreSQL compatible
-   **Frontend**: HTML, Bootstrap 5, FontAwesome
-   **Server**: Apache2 with mod_wsgi

## Installation

### Quick Start

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/kringz/xsidebyside.com.git
    cd xsidebyside.com
    ```

2.  **Run the setup script**:
    ```bash
    ./setup_app.py
    ```
    This script will:
    - Check for Python 3.11+
    - Install dependencies
    - Generate a secure `.env` file
    - Initialize the database

3.  **Run the application**:
    ```bash
    python main.py
    ```

### Manual Installation

If you prefer to set up manually:

1.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    **Key Dependencies**:
    - Flask (Web Framework)
    - Flask-SQLAlchemy (ORM)
    - Requests (HTTP Client)
    - BeautifulSoup4 (HTML Parsing)
    - Gunicorn (Production Server)
    - Psycopg2-binary (PostgreSQL Support)

2.  **Configure Environment**:
    Create a `.env` file in `xsidebyside.com/public_html/`:
    ```ini
    ANALYTICS_ENABLED=true
    ANALYTICS_USERNAME=admin
    ANALYTICS_PASSWORD=your_secure_password
    SESSION_SECRET=your_flask_secret_key
    DATABASE_URL=sqlite:///trino_versions.db
    LOG_LEVEL=INFO
    ```

3.  **Initialize Database**:
    The database is automatically initialized when the app starts. You can trigger it manually by running:
    ```bash
    python -c "from xsidebyside.com.public_html.app import app, db; app.app_context().push(); db.create_all()"
    ```

## Deployment

The project includes a `deploy.sh` script for Ubuntu/Apache deployment.

```bash
sudo ./xsidebyside.com/public_html/deploy.sh
```

**Security Note**: Ensure you update `trino_sidebyside.conf` with your domain and enable SSL/TLS using Certbot.

## Security

-   **CSRF Protection**: Enabled via Flask-WTF.
-   **Security Headers**: HSTS, CSP, and others are configured in Apache.
-   **Authentication**: Basic Auth required for `/analytics`.

## License

[MIT License](LICENSE)
