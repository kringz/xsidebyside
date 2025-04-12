from app import db
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship

class TrinoVersion(db.Model):
    """Model for Trino versions"""
    __tablename__ = 'trino_versions'
    
    id = Column(Integer, primary_key=True)
    version_number = Column(String(20), unique=True, nullable=False)
    release_date = Column(DateTime, nullable=True)
    url = Column(String(255), nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    changes = relationship("VersionChange", back_populates="version", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<TrinoVersion {self.version_number}>"

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
    version_id = Column(Integer, ForeignKey('trino_versions.id'), nullable=False)
    connector_id = Column(Integer, ForeignKey('connectors.id'), nullable=True)  # Nullable for general changes
    change_text = Column(Text, nullable=False)
    issue_number = Column(String(20), nullable=True)  # For tracking issue numbers like #24638
    is_breaking = Column(Boolean, default=False)  # Flag for breaking changes
    is_general = Column(Boolean, default=False)  # Flag for general (non-connector) changes
    
    # Relationships
    version = relationship("TrinoVersion", back_populates="changes")
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
