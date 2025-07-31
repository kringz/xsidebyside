import requests
import logging
import re
import json
import random
from bs4 import BeautifulSoup
from datetime import datetime
from app import db
from models import Product, Version, Connector, VersionChange, ComparisonCache

logger = logging.getLogger(__name__)

class UnifiedScraper:
    """Unified scraper for multiple products (Trino, Starburst)"""
    
    def __init__(self):
        self.session = requests.Session()
        self.scrapers = {
            'trino': TrinoScraper(self.session),
            'starburst': StarburstScraper(self.session)
        }
    
    def get_scraper(self, product_name):
        """Get scraper for a specific product"""
        return self.scrapers.get(product_name.lower())
    
    def update_database(self, product_name=None):
        """Update database for specific product or all products"""
        if product_name:
            products = [product_name.lower()]
        else:
            products = list(self.scrapers.keys())
        
        for product in products:
            scraper = self.get_scraper(product)
            if scraper:
                logger.info(f"Updating {product} data...")
                scraper.update_database()
    
    def get_all_versions(self, product_name):
        """Get all versions for a specific product"""
        scraper = self.get_scraper(product_name)
        if scraper:
            return scraper.get_all_versions()
        return []

class BaseScraper:
    """Base scraper class with common functionality"""
    
    def __init__(self, session):
        self.session = session
    
    def fetch_page(self, url):
        """Fetch HTML content from a URL"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching page {url}: {e}")
            return None
    
    def get_or_create_product(self):
        """Get or create product entry in database"""
        product = db.session.query(Product).filter_by(name=self.product_name).first()
        if not product:
            product = Product(name=self.product_name, display_name=self.product_display_name)
            db.session.add(product)
            db.session.commit()
        return product
    
    def update_database(self):
        """Update database with latest version information"""
        product = self.get_or_create_product()
        versions = self.get_all_versions()
        
        for version_info in versions:
            # Check if version already exists for this product
            existing_version = db.session.query(Version).filter_by(
                product_id=product.id,
                version_number=version_info['version_number']
            ).first()
            
            if not existing_version:
                logger.info(f"Processing new {self.product_display_name} version: {version_info['version_number']}")
                
                # Fetch release notes
                notes_html = self.fetch_page(version_info['url'])
                if not notes_html:
                    continue
                
                # Extract release date
                release_date = self.extract_release_date(notes_html)
                
                # Create version record
                version = Version(
                    product_id=product.id,
                    version_number=version_info['version_number'],
                    release_date=release_date,
                    url=version_info['url']
                )
                
                db.session.add(version)
                db.session.flush()  # Get the version ID
                
                # Extract and save changes
                changes = self.extract_changes(version_info, notes_html)
                for change in changes:
                    version_change = VersionChange(
                        version_id=version.id,
                        change_text=change['text'],
                        issue_number=change.get('issue_number')
                    )
                    db.session.add(version_change)
                
                db.session.commit()
                logger.info(f"Added {len(changes)} changes for {self.product_display_name} version {version_info['version_number']}")

class TrinoScraper(BaseScraper):
    """Scraper for Trino release notes"""
    
    def __init__(self, session):
        super().__init__(session)
        self.product_name = 'trino'
        self.product_display_name = 'Trino'
        self.BASE_URL = "https://trino.io"
        self.RELEASE_INDEX_URL = "https://trino.io/docs/current/release.html"
        self.RELEASE_URL_TEMPLATE = "https://trino.io/docs/current/release/release-{}.html"
    
    def get_all_versions(self):
        """Get a list of all Trino versions from the release notes index page"""
        html = self.fetch_page(self.RELEASE_INDEX_URL)
        if not html:
            logger.error(f"Failed to fetch release index page: {self.RELEASE_INDEX_URL}")
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        versions = []
        
        # Look for links to version-specific pages in the release notes index
        version_links = soup.find_all('a', href=re.compile(r'release/release-\d+\.html'))
        
        if not version_links:
            # Try looking for any list of release versions
            version_blocks = soup.find_all(['div', 'ul'], class_=re.compile(r'.*release.*'))
            if version_blocks:
                for block in version_blocks:
                    version_links.extend(block.find_all('a', href=re.compile(r'release-\d+')))
            
        # If still not found, create sample versions for demonstration
        if not version_links:
            logger.warning("Could not find version links on the page, creating sample data")
            sample_versions = ["471", "470", "469", "468", "467", "466", "465"]
            return [{"version_number": v, "url": self.RELEASE_URL_TEMPLATE.format(v)} for v in sample_versions]
        
        # Extract version numbers from the links
        for link in version_links:
            href = link.get('href', '')
            version_match = re.search(r'release-(\d+)\.html', href)
            if version_match:
                version_number = version_match.group(1)
                # Get full URL, accounting for relative paths
                if href.startswith('http'):
                    url = href
                elif href.startswith('/'):
                    url = f"{self.BASE_URL}{href}"
                else:
                    url = f"{self.BASE_URL}/docs/current/{href}"
                
                versions.append({
                    'version_number': version_number,
                    'url': url
                })
        
        # Sort versions numerically, highest first
        versions.sort(key=lambda v: int(v['version_number']), reverse=True)
        
        logger.info(f"Found {len(versions)} Trino versions")
        return versions
    
    def extract_release_date(self, notes_html):
        """Extract release date from release notes HTML"""
        match = re.search(r'Released (\d{1,2} [A-Za-z]+ \d{4})', notes_html)
        if match:
            date_str = match.group(1)
            try:
                return datetime.strptime(date_str, '%d %B %Y')
            except ValueError:
                logger.warning(f"Failed to parse date: {date_str}")
        return None
    
    def extract_changes(self, version, notes_html):
        """Extract changes from release notes HTML for a specific version"""
        soup = BeautifulSoup(notes_html, 'html.parser')
        
        # Find the section for this version
        version_section = soup.find('h2', {'id': f'release-{version["version_number"]}'})
        if not version_section:
            # Try alternative patterns
            version_section = soup.find(['h1', 'h2', 'h3'], string=re.compile(f'Release {version["version_number"]}'))
        
        if not version_section:
            logger.warning(f"Could not find version section for {version['version_number']}")
            return []
        
        changes = []
        
        # Find all list items following the version header
        next_element = version_section.find_next_sibling()
        while next_element and next_element.name not in ['h1', 'h2']:
            if next_element.name == 'ul':
                for li in next_element.find_all('li'):
                    change_text = li.get_text(strip=True)
                    if change_text:
                        # Extract issue number if present
                        issue_match = re.search(r'\(#(\d+)\)', change_text)
                        issue_number = issue_match.group(1) if issue_match else None
                        
                        changes.append({
                            'text': change_text,
                            'issue_number': issue_number
                        })
            
            next_element = next_element.find_next_sibling()
        
        return changes

class StarburstScraper(BaseScraper):
    """Scraper for Starburst release notes"""
    
    def __init__(self, session):
        super().__init__(session)
        self.product_name = 'starburst'
        self.product_display_name = 'Starburst'
        self.BASE_URL = "https://docs.starburst.io"
        self.RELEASE_INDEX_URL = "https://docs.starburst.io/latest/release.html"
        self.RELEASE_URL_TEMPLATE = "https://docs.starburst.io/latest/release/release-{}.html"
    
    def get_all_versions(self):
        """Get a list of all Starburst versions from the release notes index page"""
        html = self.fetch_page(self.RELEASE_INDEX_URL)
        if not html:
            logger.error(f"Failed to fetch release index page: {self.RELEASE_INDEX_URL}")
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        versions = []
        
        # Look for links to version-specific pages in the release notes index
        # Starburst uses format like "release-475-e.html"
        version_links = soup.find_all('a', href=re.compile(r'release/release-\d+-[a-z]\.html'))
        
        if not version_links:
            # Try alternative patterns
            version_links = soup.find_all('a', href=re.compile(r'release-\d+'))
        
        # Extract version numbers from the links
        for link in version_links:
            href = link.get('href', '')
            # Match patterns like "release-475-e.html" or "release-475.html"
            version_match = re.search(r'release-(\d+-[a-z]|\d+)\.html', href)
            if version_match:
                version_number = version_match.group(1)
                # Get full URL, accounting for relative paths
                if href.startswith('http'):
                    url = href
                elif href.startswith('/'):
                    url = f"{self.BASE_URL}{href}"
                else:
                    url = f"{self.BASE_URL}/latest/{href}"
                
                versions.append({
                    'version_number': version_number,
                    'url': url
                })
        
        # Sort versions (handle complex version numbers)
        def version_sort_key(v):
            # Extract numeric part for sorting
            match = re.match(r'(\d+)', v['version_number'])
            return int(match.group(1)) if match else 0
        
        versions.sort(key=version_sort_key, reverse=True)
        
        logger.info(f"Found {len(versions)} Starburst versions")
        return versions
    
    def extract_release_date(self, notes_html):
        """Extract release date from Starburst release notes HTML"""
        # Look for common date patterns in Starburst release notes
        patterns = [
            r'Released[:\s]+(\d{1,2} [A-Za-z]+ \d{4})',
            r'Release date[:\s]+(\d{1,2} [A-Za-z]+ \d{4})',
            r'(\d{1,2} [A-Za-z]+ \d{4})'  # General date pattern
        ]
        
        for pattern in patterns:
            match = re.search(pattern, notes_html, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                try:
                    return datetime.strptime(date_str, '%d %B %Y')
                except ValueError:
                    try:
                        return datetime.strptime(date_str, '%B %d, %Y')
                    except ValueError:
                        logger.warning(f"Failed to parse date: {date_str}")
        return None
    
    def extract_changes(self, version, notes_html):
        """Extract changes from Starburst release notes HTML for a specific version"""
        soup = BeautifulSoup(notes_html, 'html.parser')
        
        # Find the section for this version
        version_patterns = [
            f'release-release-{version["version_number"]}--page-root',  # Starburst heading format
            f'release-{version["version_number"]}',  # Basic section pattern
            f'Release {version["version_number"]}',
            version["version_number"]
        ]
        
        version_section = None
        for pattern in version_patterns:
            # First try to find heading with this ID
            version_section = soup.find(['h1', 'h2', 'h3'], {'id': pattern})
            if not version_section:
                # Try to find section with this ID
                section = soup.find('section', {'id': pattern})
                if section:
                    version_section = section.find(['h1', 'h2', 'h3'])
            if not version_section:
                # Try pattern matching in section IDs with date
                section = soup.find('section', {'id': re.compile(f'release-{version["version_number"]}-.*', re.IGNORECASE)})
                if section:
                    version_section = section.find(['h1', 'h2', 'h3'])
            if not version_section:
                version_section = soup.find(['h1', 'h2', 'h3'], string=re.compile(pattern, re.IGNORECASE))
            if version_section:
                break
        
        if not version_section:
            logger.warning(f"Could not find version section for Starburst {version['version_number']}")
            return []
        
        changes = []
        
        # Starburst pages have a different structure - look for changes in sections
        next_element = version_section.find_next_sibling()
        while next_element and next_element.name not in ['h1', 'h2']:
            if next_element.name == 'section':
                # Get section title
                section_heading = next_element.find(['h1', 'h2', 'h3', 'h4'])
                section_title = section_heading.get_text(strip=True) if section_heading else "Unknown Section"
                
                # Skip sections that are just references to Trino releases
                if not any(word in section_title.lower() for word in ['trino', 'release']):
                    # Find all list items in this section
                    for ul in next_element.find_all('ul'):
                        for li in ul.find_all('li'):
                            change_text = li.get_text(strip=True)
                            if change_text and len(change_text) > 10:  # Skip very short items
                                # Prefix with section name for context
                                full_text = f"[{section_title}] {change_text}"
                                changes.append({
                                    'text': full_text,
                                    'issue_number': None
                                })
                    
                    # Also look for paragraph changes in some sections
                    for p in next_element.find_all('p'):
                        p_text = p.get_text(strip=True)
                        if p_text and len(p_text) > 20 and p_text not in ['', 'This release is a short term support (STS) release.']:
                            full_text = f"[{section_title}] {p_text}"
                            changes.append({
                                'text': full_text,
                                'issue_number': None
                            })
            elif next_element.name == 'ul':
                # Handle ULs outside of sections (but skip Trino reference lists)
                for li in next_element.find_all('li'):
                    change_text = li.get_text(strip=True)
                    # Skip Trino version references
                    if change_text and not re.match(r'^Trino \d+$', change_text):
                        changes.append({
                            'text': change_text,
                            'issue_number': None
                        })
            
            next_element = next_element.find_next_sibling()
        
        return changes
