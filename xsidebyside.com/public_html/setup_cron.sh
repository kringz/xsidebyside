#!/bin/bash
# Setup script for auto-scraping cron job
# This creates a cron job to automatically check for new releases

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH=$(which python3)
AUTO_SCRAPE_SCRIPT="$SCRIPT_DIR/auto_scrape.py"

echo "================================"
echo "Auto-Scrape Cron Setup"
echo "================================"
echo ""
echo "Script location: $AUTO_SCRAPE_SCRIPT"
echo "Python path: $PYTHON_PATH"
echo ""

# Make the script executable
chmod +x "$AUTO_SCRAPE_SCRIPT"

echo "Choose scraping frequency:"
echo "  1) Every day at 2:00 AM"
echo "  2) Every 12 hours"
echo "  3) Every 6 hours"
echo "  4) Every hour"
echo "  5) Custom (you'll edit crontab manually)"
echo ""
read -p "Select option [1-5]: " choice

case $choice in
    1)
        CRON_SCHEDULE="0 2 * * *"
        DESCRIPTION="daily at 2:00 AM"
        ;;
    2)
        CRON_SCHEDULE="0 */12 * * *"
        DESCRIPTION="every 12 hours"
        ;;
    3)
        CRON_SCHEDULE="0 */6 * * *"
        DESCRIPTION="every 6 hours"
        ;;
    4)
        CRON_SCHEDULE="0 * * * *"
        DESCRIPTION="every hour"
        ;;
    5)
        echo ""
        echo "Opening crontab editor..."
        echo "Add this line manually:"
        echo "  0 2 * * * cd $SCRIPT_DIR && $PYTHON_PATH auto_scrape.py >> auto_scrape.log 2>&1"
        sleep 3
        crontab -e
        exit 0
        ;;
    *)
        echo "Invalid option. Exiting."
        exit 1
        ;;
esac

# Create the cron job entry
CRON_JOB="$CRON_SCHEDULE cd $SCRIPT_DIR && $PYTHON_PATH auto_scrape.py >> auto_scrape.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "auto_scrape.py"; then
    echo ""
    echo "⚠️  An auto_scrape cron job already exists!"
    read -p "Replace it? [y/N]: " replace
    if [[ ! $replace =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
    # Remove old entry
    crontab -l 2>/dev/null | grep -v "auto_scrape.py" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo ""
echo "✓ Cron job added successfully!"
echo ""
echo "Schedule: $DESCRIPTION"
echo "Command: $CRON_JOB"
echo ""
echo "To view all cron jobs: crontab -l"
echo "To remove this job: crontab -e (then delete the line)"
echo "To view logs: tail -f $SCRIPT_DIR/auto_scrape.log"
echo ""
echo "Testing the script now..."
cd "$SCRIPT_DIR" && $PYTHON_PATH auto_scrape.py

echo ""
echo "Done! The auto-scraper will now run $DESCRIPTION."
