import os
import re
import logging

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_wtf.csrf import CSRFProtect

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the base class
db = SQLAlchemy(model_class=Base)

# Create the Flask application
app = Flask(__name__)
csrf = CSRFProtect(app)

# Configure the application
app.secret_key = os.environ.get("SESSION_SECRET", "trino_version_comparison_secret")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # Needed for url_for to generate with https

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///trino_versions.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the app with the extension
db.init_app(app)

# Initialize database schema
with app.app_context():
    # Import models here to avoid circular imports
    import models  # noqa: F401
    
    try:
        db.create_all()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")

# Custom Jinja filter to normalize text for URL text fragments
# Uses first ~60 chars for reliable matching
def text_fragment_encode(text):
    """Normalize text for use in URL text fragments (#:~:text=...)"""
    if not text:
        return ''
    # Replace newlines and multiple spaces with single space
    normalized = re.sub(r'\s+', ' ', text).strip()
    
    # Remove bullet points and other special chars that cause matching issues
    normalized = re.sub(r'[•·]', '', normalized)
    
    # Limit to first ~60 chars at word boundary for reliable matching
    if len(normalized) > 60:
        normalized = normalized[:60].rsplit(' ', 1)[0]
    
    # URL encode for use in text fragment
    from urllib.parse import quote
    return quote(normalized)

app.jinja_env.filters['text_fragment'] = text_fragment_encode

# Filter to convert connector name to anchor slug (e.g., "Alteryx Connector" -> "alteryx-connector")
def connector_anchor(name):
    """Convert connector name to URL anchor slug"""
    if not name:
        return ''
    # Remove "Connector" suffix if present, lowercase, replace spaces with hyphens
    slug = name.lower().strip()
    if not slug.endswith('connector'):
        slug = slug + '-connector'
    else:
        slug = slug.replace(' ', '-')
    return slug

app.jinja_env.filters['connector_anchor'] = connector_anchor

# Import views after initializing the app and database
from views import *  # noqa: F401, E402
