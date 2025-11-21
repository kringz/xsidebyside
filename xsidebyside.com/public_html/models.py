from app import db
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship

class Product(db.Model):
    """Model for products (Trino, Starburst, etc.)"""
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)  # 'trino' or 'starburst'
    display_name = Column(String(100), nullable=False)  # 'Trino' or 'Starburst'
    
    # Relationships
    versions = relationship("Version", back_populates="product", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Product {self.display_name}>"

class Version(db.Model):
    """Model for product versions (formerly TrinoVersion)"""
    __tablename__ = 'versions'
    
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    version_number = Column(String(20), nullable=False)
    release_date = Column(DateTime, nullable=True)
    url = Column(String(255), nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    product = relationship("Product", back_populates="versions")
    changes = relationship("VersionChange", back_populates="version", cascade="all, delete-orphan")
    
    # Add unique constraint for product_id + version_number
    __table_args__ = (db.UniqueConstraint('product_id', 'version_number', name='_product_version_uc'),)
    
    def __repr__(self):
        return f"<Version {self.product.display_name if self.product else 'Unknown'} {self.version_number}>"

class Connector(db.Model):
    """Model for Trino connectors"""
    __tablename__ = 'connectors'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    
    # Relationships
    changes = relationship("VersionChange", back_populates="connector")
    
    def __repr__(self):
        return f"<Connector {self.name}>"

class VersionChange(db.Model):
    """Model for changes in Trino versions"""
    __tablename__ = 'version_changes'
    
    id = Column(Integer, primary_key=True)
    version_id = Column(Integer, ForeignKey('versions.id'), nullable=False)
    connector_id = Column(Integer, ForeignKey('connectors.id'), nullable=True)  # Nullable for general changes
    change_text = Column(Text, nullable=False)
    issue_number = Column(String(20), nullable=True)  # For tracking issue numbers like #24638
    is_breaking = Column(Boolean, default=False)  # Flag for breaking changes
    is_general = Column(Boolean, default=False)  # Flag for general (non-connector) changes
    
    # Relationships
    version = relationship("Version", back_populates="changes")
    connector = relationship("Connector", back_populates="changes")
    
    def __repr__(self):
        return f"<VersionChange {self.id} for version {self.version.version_number}>"

class ComparisonCache(db.Model):
    """Cache for version comparisons to avoid redundant scraping"""
    __tablename__ = 'comparison_cache'

    id = Column(Integer, primary_key=True)
    from_version = Column(String(20), nullable=False)
    to_version = Column(String(20), nullable=False)
    cache_data = Column(Text, nullable=False)  # JSON data of the comparison
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ComparisonCache {self.from_version} to {self.to_version}>"

class SearchEvent(db.Model):
    """Model for tracking search queries (anonymous analytics)"""
    __tablename__ = 'search_events'

    id = Column(Integer, primary_key=True)
    keyword = Column(String(255), nullable=False)
    product = Column(String(50), nullable=True)
    connector = Column(String(100), nullable=True)
    from_version = Column(String(20), nullable=True)
    to_version = Column(String(20), nullable=True)
    result_count = Column(Integer, nullable=True)
    ip_hash = Column(String(64), nullable=True)  # SHA256 hash for estimating unique users
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<SearchEvent '{self.keyword}' at {self.timestamp}>"

class ComparisonEvent(db.Model):
    """Model for tracking version comparisons (anonymous analytics)"""
    __tablename__ = 'comparison_events'

    id = Column(Integer, primary_key=True)
    product = Column(String(50), nullable=False)
    from_version = Column(String(20), nullable=False)
    to_version = Column(String(20), nullable=False)
    selected_connectors = Column(Text, nullable=True)  # Comma-separated list
    ip_hash = Column(String(64), nullable=True)  # SHA256 hash for estimating unique users
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ComparisonEvent {self.product} {self.from_version}-{self.to_version} at {self.timestamp}>"
