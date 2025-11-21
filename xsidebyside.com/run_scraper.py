#!/usr/bin/env python3
"""
Script to manually run the scraper to update Trino and Starburst versions
"""
from app import app, db
from unified_scraper import UnifiedScraper
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_all():
    """Update both Trino and Starburst"""
    with app.app_context():
        scraper = UnifiedScraper()

        print("=" * 60)
        print("Updating Trino versions...")
        print("=" * 60)
        scraper.update_database('trino')

        print("\n" + "=" * 60)
        print("Updating Starburst versions...")
        print("=" * 60)
        scraper.update_database('starburst')

        print("\n" + "=" * 60)
        print("Update complete!")
        print("=" * 60)

def update_trino():
    """Update only Trino"""
    with app.app_context():
        scraper = UnifiedScraper()
        print("Updating Trino versions...")
        scraper.update_database('trino')
        print("Trino update complete!")

def update_starburst():
    """Update only Starburst"""
    with app.app_context():
        scraper = UnifiedScraper()
        print("Updating Starburst versions...")
        scraper.update_database('starburst')
        print("Starburst update complete!")

if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        product = sys.argv[1].lower()
        if product == 'trino':
            update_trino()
        elif product == 'starburst':
            update_starburst()
        else:
            print(f"Unknown product: {product}")
            print("Usage: python run_scraper.py [trino|starburst]")
            print("  Or run without arguments to update both")
    else:
        update_all()
