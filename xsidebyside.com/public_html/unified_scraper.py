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
                    # Detect breaking changes
                    change_text = change['text']
                    is_breaking = ('breaking change' in change_text.lower() or 
                                 change_text.lower().startswith('breaking change:') or
                                 '⚠️ breaking change' in change_text.lower())
                    
                    # Detect general changes (non-connector specific)
                    is_general = ('[general' in change_text.lower() or 
                                change.get('connector') is None)
                    
                    version_change = VersionChange(
                        version_id=version.id,
                        change_text=change['text'],
                        issue_number=change.get('issue_number'),
                        is_breaking=is_breaking,
                        is_general=is_general
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
        # Trino format: "Release 478 (29 Oct 2025)"
        patterns = [
            r'\((\d{1,2} [A-Za-z]+ \d{4})\)',  # Date in parentheses
            r'Released[:\s]+(\d{1,2} [A-Za-z]+ \d{4})',  # Legacy format
        ]

        for pattern in patterns:
            match = re.search(pattern, notes_html)
            if match:
                date_str = match.group(1)
                try:
                    return datetime.strptime(date_str, '%d %B %Y')
                except ValueError:
                    try:
                        # Try abbreviated month format (Oct instead of October)
                        return datetime.strptime(date_str, '%d %b %Y')
                    except ValueError:
                        logger.warning(f"Failed to parse date: {date_str}")
        return None
    
    def extract_changes(self, version, notes_html):
        """Extract changes from release notes HTML for a specific version"""
        # Debug logging
        logger.info(f"🔍 TrinoScraper.extract_changes called for version: {version.get('version_number', 'UNKNOWN')}")
        logger.info(f"📄 HTML length: {len(notes_html)} characters")
        
        soup = BeautifulSoup(notes_html, 'html.parser')
        
        # Find the section for this version - updated patterns for current Trino structure
        version_patterns = [
            f'release-release-{version["version_number"]}--page-root',  # Current Trino heading format
            f'release-{version["version_number"]}',  # Legacy pattern
            f'Release {version["version_number"]}',  # Text-based pattern
        ]
        
        version_section = None
        for pattern in version_patterns:
            # Try to find heading with this ID
            version_section = soup.find(['h1', 'h2', 'h3'], {'id': pattern})
            if not version_section:
                # Try to find section with this pattern in ID
                section = soup.find('section', {'id': re.compile(f'release-{version["version_number"]}.*', re.IGNORECASE)})
                if section:
                    version_section = section.find(['h1', 'h2', 'h3'])
            if not version_section:
                # Try text-based matching
                version_section = soup.find(['h1', 'h2', 'h3'], string=re.compile(pattern, re.IGNORECASE))
            if version_section:
                break
        
        if not version_section:
            logger.warning(f"Could not find version section for Trino {version['version_number']}")
            return []
        
        changes = []
        
        # Trino has a structure with <section> elements containing connector sections
        next_element = version_section.find_next_sibling()
        while next_element and next_element.name not in ['h1']:  # Stop at next major heading
            if next_element.name == 'section':  # Section containing connector or topic changes
                # Find the heading within this section
                section_heading = next_element.find(['h1', 'h2', 'h3', 'h4'])
                section_title = section_heading.get_text(strip=True) if section_heading else "Unknown Section"
                
                # Find all lists within this section
                for ul in next_element.find_all('ul'):
                    # Skip nested lists (they are handled by their parent LI)
                    if ul.find_parent('li'):
                        continue
                        
                    for li in ul.find_all('li', recursive=False):
                        change_text = li.get_text(strip=True)
                        if change_text and len(change_text) > 10:  # Basic length filter
                            # Extract issue number if present
                            issue_match = re.search(r'\(#(\d+)\)', change_text)
                            issue_number = issue_match.group(1) if issue_match else None
                            
                            # Prefix with section name for context
                            full_text = f"[{section_title}] {change_text}"
                            changes.append({
                                'text': full_text,
                                'issue_number': issue_number
                            })
            elif next_element.name == 'h2':  # Direct connector/section heading (fallback)
                section_title = next_element.get_text(strip=True)
                
                # Find lists under this section
                section_next = next_element.find_next_sibling()
                while section_next and section_next.name not in ['h1', 'h2']:
                    if section_next.name == 'ul':
                        # Skip nested lists
                        if section_next.find_parent('li'):
                            section_next = section_next.find_next_sibling()
                            continue
                            
                        for li in section_next.find_all('li', recursive=False):
                            change_text = li.get_text(strip=True)
                            if change_text and len(change_text) > 10:
                                # Extract issue number if present
                                issue_match = re.search(r'\(#(\d+)\)', change_text)
                                issue_number = issue_match.group(1) if issue_match else None
                                
                                # Prefix with section name for context
                                full_text = f"[{section_title}] {change_text}"
                                changes.append({
                                    'text': full_text,
                                    'issue_number': issue_number
                                })
                    section_next = section_next.find_next_sibling()
            elif next_element.name == 'ul':  # Direct list under main heading (fallback)
                # Skip nested lists
                if next_element.find_parent('li'):
                    next_element = next_element.find_next_sibling()
                    continue
                    
                for li in next_element.find_all('li', recursive=False):
                    change_text = li.get_text(strip=True)
                    if change_text and len(change_text) > 10:
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
        # Starburst format: "Release 477-e STS (12 Nov 2025)"
        patterns = [
            r'\((\d{1,2} [A-Za-z]+ \d{4})\)',  # Date in parentheses (primary format)
            r'Released[:\s]+(\d{1,2} [A-Za-z]+ \d{4})',  # Legacy format
            r'Release date[:\s]+(\d{1,2} [A-Za-z]+ \d{4})',  # Alternative format
        ]

        for pattern in patterns:
            match = re.search(pattern, notes_html, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                # Try multiple date formats
                for date_format in ['%d %B %Y', '%d %b %Y', '%B %d, %Y']:
                    try:
                        return datetime.strptime(date_str, date_format)
                    except ValueError:
                        continue
                logger.warning(f"Failed to parse date: {date_str}")
        return None
    
    def _extract_structured_text(self, li_element):
        """Extract text from list item preserving nested bullet structure and order"""
        result_parts = []
        
        for child in li_element.children:
            if child.name in ['ul', 'ol']:
                # Handle nested lists
                nested_items = child.find_all('li', recursive=False)
                for nested_li in nested_items:
                    nested_text = self._extract_structured_text(nested_li)
                    if nested_text:
                        # Add newline before bullet if previous content exists
                        prefix = "\n" if result_parts else ""
                        result_parts.append(f"{prefix}• {nested_text}")
            elif child.name == 'p':
                # Handle paragraphs
                text = child.get_text(separator=' ', strip=True)
                if text:
                    # Add newline if previous content exists (unless it was a bullet)
                    prefix = " " if result_parts and not result_parts[-1].startswith('\n') else ""
                    if result_parts and result_parts[-1].startswith('\n'):
                         prefix = "\n"
                    result_parts.append(f"{prefix}{text}")
            elif isinstance(child, str):
                # Handle direct text
                text = child.strip()
                if text:
                    prefix = " " if result_parts and not result_parts[-1].startswith('\n') else ""
                    result_parts.append(f"{prefix}{text}")
            else:
                # Handle other tags (span, code, etc) - treat as inline text
                text = child.get_text(separator=' ', strip=True)
                if text:
                    prefix = " " if result_parts and not result_parts[-1].startswith('\n') else ""
                    result_parts.append(f"{prefix}{text}")
        
        return "".join(result_parts).strip()
    
    def _is_valid_change(self, text):
        """Validate if text represents a meaningful change description"""
        if not text or len(text.strip()) < 10:
            return False
        
        # Skip obvious non-changes
        skip_patterns = [
            r'^Trino \d+$',  # Just version references
            r'^Release \d+',  # Release headers
            r'^\d+-e(\.\d+)?\s+(initial\s+)?changes',  # Version change headers
            r'^\s*$',  # Empty or whitespace only
            r'^See\s+',  # See references
            r'^For\s+more\s+information',  # Info references
            r'^This\s+release',  # Release descriptions
        ]
        
        for pattern in skip_patterns:
            if re.match(pattern, text.strip(), re.IGNORECASE):
                return False
        
        # Must contain meaningful words (not just property names)
        meaningful_words = ['added', 'updated', 'fixed', 'removed', 'improved', 'changed', 'support', 'issue',
                          'feature', 'bug', 'performance', 'security', 'deprecated', 'enabled', 'disabled',
                          'introduced', 'enhanced', 'resolved', 'corrected', 'optimized']

        # Text should contain at least one meaningful action word or be descriptive
        text_lower = text.lower()
        has_meaningful_word = any(word in text_lower for word in meaningful_words)
        is_descriptive = len(text.split()) >= 4  # At least 4 words for descriptive content
        
        return has_meaningful_word or is_descriptive
    
    def _process_section_content(self, section_element, changes, seen_texts):
        """Process content of a section, handling nested sections recursively"""
        # Get section title
        section_heading = section_element.find(['h1', 'h2', 'h3', 'h4'])
        section_title = section_heading.get_text(strip=True) if section_heading else "Unknown Section"
        
        # Skip sections that are just references to Trino releases
        if any(word in section_title.lower() for word in ['trino', 'release']) and 'notes' not in section_title.lower():
            return

        # Find direct list items in this section
        for ul in section_element.find_all('ul', recursive=False):
            # Skip nested lists (handled by parent li)
            if ul.find_parent('li'):
                continue
                
            for li in ul.find_all('li', recursive=False):
                change_text = self._extract_structured_text(li)
                if self._is_valid_change(change_text):
                    # Prefix with section name for context
                    full_text = f"[{section_title}] {change_text}"
                    
                    # Deduplicate
                    if full_text not in seen_texts:
                        changes.append({
                            'text': full_text,
                            'issue_number': None
                        })
                        seen_texts.add(full_text)
        
        # Also look for paragraph changes in some sections
        for p in section_element.find_all('p', recursive=False):
            # Skip paragraphs inside list items
            if p.find_parent('li'):
                continue
                
            p_text = p.get_text(separator=' ', strip=True)
            if self._is_valid_change(p_text) and p_text not in ['', 'This release is a short term support (STS) release.']:
                full_text = f"[{section_title}] {p_text}"
                
                # Deduplicate
                if full_text not in seen_texts:
                    changes.append({
                        'text': full_text,
                        'issue_number': None
                    })
                    seen_texts.add(full_text)
        
        # Recursively process nested sections
        for nested_section in section_element.find_all('section', recursive=False):
            self._process_section_content(nested_section, changes, seen_texts)

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
        seen_texts = set()
        
        # Starburst pages have a different structure - look for changes in sections
        next_element = version_section.find_next_sibling()
        while next_element and next_element.name not in ['h1', 'h2']:
            if next_element.name == 'section':
                self._process_section_content(next_element, changes, seen_texts)
            elif next_element.name == 'ul':
                # Skip nested lists
                if next_element.find_parent('li'):
                    next_element = next_element.find_next_sibling()
                    continue

                # Handle ULs outside of sections (but skip Trino reference lists)
                for li in next_element.find_all('li', recursive=False):
                    change_text = li.get_text(separator=' ', strip=True)
                    # Skip Trino version references and low-quality changes
                    if self._is_valid_change(change_text) and not re.match(r'^Trino \d+$', change_text):
                        # Deduplicate (no section prefix here)
                        if change_text not in seen_texts:
                            changes.append({
                                'text': change_text,
                                'issue_number': None
                            })
                            seen_texts.add(change_text)
            
            next_element = next_element.find_next_sibling()
        
        return changes
