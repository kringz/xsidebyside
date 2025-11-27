#!/usr/bin/env python3
"""
Script to update release dates for existing versions in the database.
This is useful after fixing the date extraction logic.
"""

import logging
from app import app, db
from models import Product, Version
from unified_scraper import UnifiedScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def update_release_dates(product_name=None, limit=None):
    """
    Update release dates for existing versions by re-fetching and parsing them.

    Args:
        product_name: Specific product to update ('trino' or 'starburst'), or None for all
        limit: Maximum number of versions to update (for testing), or None for all
    """
    scraper = UnifiedScraper()

    with app.app_context():
        # Get products to process
        if product_name:
            products = db.session.query(Product).filter_by(name=product_name).all()
        else:
            products = db.session.query(Product).order_by(Product.name).all()
            # Sort to put Starburst first
            products = sorted(products, key=lambda p: (0 if p.name == 'starburst' else 1, p.name))

        for product in products:
            logger.info(f"\n{'='*60}")
            logger.info(f"Updating release dates for {product.display_name}")
            logger.info(f"{'='*60}")

            # Get versions without release dates
            versions_query = db.session.query(Version).filter_by(
                product_id=product.id,
                release_date=None
            ).order_by(Version.version_number.desc())

            if limit:
                versions_query = versions_query.limit(limit)

            versions = versions_query.all()

            logger.info(f"Found {len(versions)} versions without release dates")

            # Get the appropriate scraper
            product_scraper = scraper.get_scraper(product.name)
            if not product_scraper:
                logger.error(f"No scraper found for {product.name}")
                continue

            # Update each version
            updated_count = 0
            for version in versions:
                logger.info(f"Processing {product.display_name} version {version.version_number}...")

                # Fetch the release notes page
                html = product_scraper.fetch_page(version.url)
                if not html:
                    logger.warning(f"Failed to fetch page for version {version.version_number}")
                    continue

                # Extract release date
                release_date = product_scraper.extract_release_date(html)
                if release_date:
                    version.release_date = release_date
                    updated_count += 1
                    logger.info(f"  ✓ Updated: {version.version_number} -> {release_date.strftime('%Y-%m-%d')}")
                else:
                    logger.warning(f"  ✗ Could not extract date for version {version.version_number}")

            # Commit changes for this product
            if updated_count > 0:
                db.session.commit()
                logger.info(f"\n✓ Successfully updated {updated_count}/{len(versions)} versions for {product.display_name}")
            else:
                logger.info(f"\n✗ No dates could be extracted for {product.display_name}")


if __name__ == '__main__':
    import sys

    # Parse command line arguments
    product_arg = sys.argv[1] if len(sys.argv) > 1 else None
    limit_arg = int(sys.argv[2]) if len(sys.argv) > 2 else None

    print("\nRelease Date Update Script")
    print("=" * 60)

    if product_arg:
        print(f"Product: {product_arg}")
    else:
        print("Product: All products")

    if limit_arg:
        print(f"Limit: {limit_arg} versions per product (testing mode)")
    else:
        print("Limit: All versions")

    print("=" * 60)

    # Confirm before proceeding
    if limit_arg is None:
        response = input("\nThis will update ALL versions. Continue? [y/N]: ")
        if response.lower() != 'y':
            print("Aborted.")
            sys.exit(0)

    # Run the update
    update_release_dates(product_arg, limit_arg)

    print("\n" + "=" * 60)
    print("Update complete!")
    print("=" * 60)
