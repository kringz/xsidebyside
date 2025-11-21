# Analytics Setup

## Configuration

Analytics settings are configured in the `.env` file located at:
```
/var/www/xsidebyside.com/xsidebyside.com/public_html/.env
```

### Current Settings

- **ANALYTICS_ENABLED**: `true` (set to `false` to disable logging)
- **ANALYTICS_USERNAME**: `admin` (username for HTTP Basic Auth)
- **ANALYTICS_PASSWORD**: Secure random password for accessing the analytics dashboard

## Accessing Analytics Dashboard

Visit the following URL to view analytics:
```
https://xsidebyside.com/analytics
```

You will be prompted for a username and password:
- **Username**: `admin`
- **Password**: `(Check your .env file)`

The credentials are sent using HTTP Basic Authentication, which is more secure than URL parameters.

## What Gets Logged

### Search Events
- Search keyword
- Product (trino/starburst)
- Connector filter
- Version range
- Number of results
- Anonymized IP hash
- Timestamp

### Comparison Events
- Product (trino/starburst)
- From/to versions
- Selected connectors
- Anonymized IP hash
- Timestamp

## Privacy

All IP addresses are hashed using SHA256 before storage. No personally identifiable information is stored.

## Database

Analytics data is stored in the main SQLite database at:
```
/var/www/xsidebyside.com/xsidebyside.com/public_html/instance/trino_versions.db
```

Tables:
- `search_events` - Search queries
- `comparison_events` - Version comparisons

## Changing the Analytics Credentials

1. Edit `.env` file
2. Change `ANALYTICS_USERNAME` and/or `ANALYTICS_PASSWORD`
3. Reload Apache: `sudo systemctl reload apache2` or `touch wsgi.py`

## Disabling Analytics

1. Edit `.env` file
2. Set `ANALYTICS_ENABLED=false`
3. Restart Apache: `sudo systemctl restart apache2`
