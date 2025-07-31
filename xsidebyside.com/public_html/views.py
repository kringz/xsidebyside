from flask import render_template, request, jsonify, redirect, url_for
import logging
import json
from app import app, db
from models import TrinoVersion, Connector, VersionChange
from scraper import TrinoScraper

logger = logging.getLogger(__name__)
scraper = TrinoScraper()

@app.route('/')
def index():
    """Home page with version selection form"""
    # Get all available versions for the dropdown
    versions = db.session.query(TrinoVersion.version_number).order_by(
        TrinoVersion.version_number.desc()
    ).all()
    
    versions = [v[0] for v in versions]
    
    # If no versions are available, scrape them
    if not versions:
        try:
            with app.app_context():
                scraper.update_database()
            
            # Query again after update
            versions = db.session.query(TrinoVersion.version_number).order_by(
                TrinoVersion.version_number.desc()
            ).all()
            versions = [v[0] for v in versions]
        except Exception as e:
            logger.error(f"Error updating database: {e}")
            versions = []
    
    return render_template('index.html', versions=versions)

@app.route('/compare', methods=['GET', 'POST'])
def compare():
    """Compare two Trino versions"""
    if request.method == 'POST':
        from_version = request.form.get('from_version')
        to_version = request.form.get('to_version')
        
        # Redirect to GET endpoint with query parameters
        return redirect(url_for('compare', from_version=from_version, to_version=to_version))
    
    # Handle GET request with query parameters
    from_version = request.args.get('from_version')
    to_version = request.args.get('to_version')
    
    if not from_version or not to_version:
        return redirect(url_for('index'))
    
    # Get comparison data
    try:
        comparison = scraper.compare_versions(from_version, to_version)
        
        if not comparison:
            logger.error(f"Failed to generate comparison between {from_version} and {to_version}")
            return render_template('index.html', error="Failed to generate comparison. Please try again.")
        
        # Sort connectors alphabetically
        connector_changes = {k: comparison['connector_changes'][k] for k in 
                            sorted(comparison['connector_changes'].keys())}
        
        return render_template('comparison.html', 
                               from_version=from_version, 
                               to_version=to_version,
                               connector_changes=connector_changes,
                               general_changes=comparison['general_changes'],
                               summary=comparison['summary'])
    
    except Exception as e:
        logger.error(f"Error generating comparison: {e}")
        return render_template('index.html', error=f"Error: {str(e)}")

@app.route('/refresh')
def refresh_data():
    """Force refresh of all versions data"""
    try:
        with app.app_context():
            scraper.update_database()
        return redirect(url_for('index', refresh_status="success"))
    except Exception as e:
        logger.error(f"Error refreshing data: {e}")
        return redirect(url_for('index', refresh_status="error", error=str(e)))

@app.route('/api/versions')
def api_versions():
    """API endpoint to get all available versions"""
    versions = db.session.query(TrinoVersion.version_number).order_by(
        TrinoVersion.version_number.desc()
    ).all()
    return jsonify([v[0] for v in versions])

@app.route('/api/search')
def api_search():
    """API endpoint to search for changes by keyword"""
    keyword = request.args.get('keyword', '')
    
    if not keyword or len(keyword) < 3:
        return jsonify({"error": "Search term must be at least 3 characters"})
    
    changes = db.session.query(VersionChange).filter(
        VersionChange.change_text.ilike(f'%{keyword}%')
    ).all()
    
    results = []
    for change in changes:
        connector_name = change.connector.name if change.connector else "General"
        
        results.append({
            "version": change.version.version_number,
            "connector": connector_name,
            "text": change.change_text,
            "is_breaking": change.is_breaking
        })
    
    return jsonify({"results": results, "count": len(results)})
