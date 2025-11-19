#!/usr/bin/env python3
"""
Automated scraper for new Trino and Starburst releases.
This script checks for and imports new versions automatically.

Usage:
  - Run manually: python3 auto_scrape.py
  - Run as cron job: Add to crontab for scheduled execution
  - Run specific product: python3 auto_scrape.py --product trino
"""

import sys
import logging
from datetime import datetime
from app import app, db
from models import Product, Version
from unified_scraper import UnifiedScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_scrape.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def get_latest_version_in_db(product_name):
    """Get the latest version number currently in the database"""
    with app.app_context():
        product = db.session.query(Product).filter_by(name=product_name).first()
        if not product:
            return None

        latest = db.session.query(Version).filter_by(
            product_id=product.id
        ).order_by(Version.version_number.desc()).first()

        return latest.version_number if latest else None


def check_for_new_versions(product_name):
    """
    Check for new versions and import them if found.

    Returns:
        dict with 'new_versions' (list), 'count' (int), and 'latest' (str)
    """
    logger.info(f"Checking for new {product_name.title()} versions...")

    # Get current latest version in database
    current_latest = get_latest_version_in_db(product_name)
    logger.info(f"Current latest {product_name} version in database: {current_latest}")

    # Create scraper and get all available versions
    scraper = UnifiedScraper()
    product_scraper = scraper.get_scraper(product_name)

    if not product_scraper:
        logger.error(f"No scraper available for {product_name}")
        return {'new_versions': [], 'count': 0, 'latest': current_latest}

    # Get all versions from the website
    available_versions = product_scraper.get_all_versions()
    if not available_versions:
        logger.warning(f"No versions found for {product_name}")
        return {'new_versions': [], 'count': 0, 'latest': current_latest}

    # Check if the latest available version is newer than what we have
    latest_available = available_versions[0]['version_number']
    logger.info(f"Latest {product_name} version available: {latest_available}")

    if current_latest == latest_available:
        logger.info(f"✓ {product_name.title()} is up to date (version {current_latest})")
        return {'new_versions': [], 'count': 0, 'latest': current_latest}

    # New version(s) found - run the scraper
    logger.info(f"🔔 New {product_name.title()} version(s) detected!")
    logger.info(f"Running scraper to import new versions...")

    with app.app_context():
        scraper.update_database(product_name)

    # Get the new latest version
    new_latest = get_latest_version_in_db(product_name)

    # Determine which versions were added
    new_versions = []
    with app.app_context():
        product = db.session.query(Product).filter_by(name=product_name).first()
        if product:
            # Get all versions that were added (simplification: just show the newest ones)
            recent_versions = db.session.query(Version).filter_by(
                product_id=product.id
            ).order_by(Version.version_number.desc()).limit(5).all()

            new_versions = [v.version_number for v in recent_versions]

    result = {
        'new_versions': new_versions,
        'count': len(new_versions),
        'latest': new_latest
    }

    logger.info(f"✓ Successfully imported new {product_name.title()} versions: {', '.join(new_versions)}")
    return result


def run_auto_scrape(products=None):
    """
    Run auto-scraping for specified products or all products.

    Args:
        products: List of product names, or None for all products

    Returns:
        dict with results for each product
    """
    logger.info("=" * 70)
    logger.info("AUTO-SCRAPER STARTED")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 70)

    if products is None:
        products = ['trino', 'starburst']

    results = {}
    total_new_versions = 0

    for product in products:
        try:
            result = check_for_new_versions(product)
            results[product] = result
            total_new_versions += result['count']
        except Exception as e:
            logger.error(f"Error checking {product}: {e}", exc_info=True)
            results[product] = {'error': str(e), 'count': 0}

    logger.info("")
    logger.info("=" * 70)
    logger.info("AUTO-SCRAPER SUMMARY")
    logger.info("=" * 70)

    for product, result in results.items():
        if 'error' in result:
            logger.error(f"❌ {product.title()}: Error - {result['error']}")
        elif result['count'] > 0:
            logger.info(f"✓ {product.title()}: Found {result['count']} new version(s)")
            logger.info(f"  Latest version: {result['latest']}")
        else:
            logger.info(f"✓ {product.title()}: Already up to date (version {result['latest']})")

    logger.info("")
    logger.info(f"Total new versions imported: {total_new_versions}")
    logger.info("=" * 70)

    return results


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Auto-scrape for new Trino/Starburst releases')
    parser.add_argument('--product', '-p',
                       choices=['trino', 'starburst'],
                       help='Specific product to check (default: all)')
    parser.add_argument('--quiet', '-q',
                       action='store_true',
                       help='Reduce output verbosity')

    args = parser.parse_args()

    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    products = [args.product] if args.product else None
    results = run_auto_scrape(products)

    # Exit with non-zero code if there were errors
    if any('error' in r for r in results.values()):
        sys.exit(1)
