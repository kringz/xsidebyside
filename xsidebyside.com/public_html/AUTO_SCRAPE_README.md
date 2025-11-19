# Auto-Scraping Feature

This directory contains automated scraping functionality to keep your Trino and Starburst version database up-to-date automatically.

## Files

- **`auto_scrape.py`** - Main auto-scraping script
- **`setup_cron.sh`** - Interactive cron job setup script
- **`auto_scrape.log`** - Log file for scraping activity (created automatically)

## Quick Start

### 1. Setup Automatic Scraping

Run the interactive setup script:

```bash
./setup_cron.sh
```

This will:
- Ask you to choose a scraping frequency (hourly, daily, etc.)
- Create a cron job to run automatically
- Test the script to ensure it works

### 2. Manual Usage

You can also run the scraper manually:

```bash
# Check both Trino and Starburst for new versions
python3 auto_scrape.py

# Check only Trino
python3 auto_scrape.py --product trino

# Check only Starburst
python3 auto_scrape.py --product starburst

# Quiet mode (less verbose)
python3 auto_scrape.py --quiet
```

## How It Works

The auto-scraper:

1. **Checks** the latest version in your database
2. **Queries** the official documentation sites for the latest available version
3. **Compares** the two versions
4. **Imports** new versions automatically if found
5. **Logs** all activity to `auto_scrape.log`

## Cron Schedule Options

When setting up the cron job, you can choose from:

- **Daily at 2:00 AM** (recommended) - `0 2 * * *`
- **Every 12 hours** - `0 */12 * * *`
- **Every 6 hours** - `0 */6 * * *`
- **Every hour** - `0 * * * *`
- **Custom** - Edit crontab manually

## Monitoring

### View Logs

```bash
# View recent log entries
tail -f auto_scrape.log

# View all logs
cat auto_scrape.log
```

### Check Cron Jobs

```bash
# List all cron jobs
crontab -l

# Edit cron jobs
crontab -e
```

## Example Output

When new versions are found:

```
======================================================================
AUTO-SCRAPER STARTED
Time: 2025-11-18 21:12:33
======================================================================
Checking for new Trino versions...
Current latest trino version in database: 477
Latest trino version available: 478
🔔 New Trino version(s) detected!
Running scraper to import new versions...
✓ Successfully imported new Trino versions: 478

======================================================================
AUTO-SCRAPER SUMMARY
======================================================================
✓ Trino: Found 1 new version(s)
  Latest version: 478
✓ Starburst: Already up to date (version 477-e)

Total new versions imported: 1
======================================================================
```

When already up-to-date:

```
======================================================================
AUTO-SCRAPER SUMMARY
======================================================================
✓ Trino: Already up to date (version 478)
✓ Starburst: Already up to date (version 477-e)

Total new versions imported: 0
======================================================================
```

## Troubleshooting

### Cron job not running

1. Check if cron service is running:
   ```bash
   sudo systemctl status cron
   ```

2. Verify your cron job exists:
   ```bash
   crontab -l
   ```

3. Check for errors in system logs:
   ```bash
   grep CRON /var/log/syslog
   ```

### Script errors

1. Test the script manually:
   ```bash
   python3 auto_scrape.py
   ```

2. Check permissions:
   ```bash
   chmod +x auto_scrape.py
   ```

3. Verify Python dependencies:
   ```bash
   pip3 list | grep -E "Flask|requests|beautifulsoup4|SQLAlchemy"
   ```

## Disabling Auto-Scraping

To remove the cron job:

```bash
crontab -e
# Delete the line containing "auto_scrape.py"
# Save and exit
```

Or use this one-liner:

```bash
crontab -l | grep -v "auto_scrape.py" | crontab -
```

## Integration with Web App

The auto-scraper integrates seamlessly with your web application:

- Uses the same database (`instance/trino_versions.db`)
- Uses the same scraper classes (`UnifiedScraper`)
- No configuration changes needed
- Changes are immediately visible on the website

## Performance Notes

- Scraping typically takes 5-30 seconds depending on network speed
- Only new versions are processed (skips existing versions)
- Minimal resource usage (only runs when scheduled)
- Logs are automatically rotated if they grow too large

## Advanced Usage

### Email Notifications

To get email notifications when new versions are found, modify the cron job:

```bash
0 2 * * * cd /var/www/xsidebyside.com/xsidebyside.com/public_html && python3 auto_scrape.py 2>&1 | mail -s "Trino/Starburst Update" your@email.com
```

### Custom Schedules

Edit crontab manually for custom schedules:

```bash
# Run every Monday at 9 AM
0 9 * * 1 cd /path/to/script && python3 auto_scrape.py

# Run on the 1st and 15th of each month
0 2 1,15 * * cd /path/to/script && python3 auto_scrape.py
```

## Support

For issues or questions, check:
- `auto_scrape.log` for script errors
- `/var/log/syslog` for cron errors
- Database at `instance/trino_versions.db`
