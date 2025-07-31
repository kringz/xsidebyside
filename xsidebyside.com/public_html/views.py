from flask import render_template, request, jsonify, redirect, url_for
import logging
import json
from app import app, db
from models import Product, Version, Connector, VersionChange
from unified_scraper import UnifiedScraper

logger = logging.getLogger(__name__)
scraper = UnifiedScraper()

def compare_versions(product_name, from_version, to_version):
    """Compare two versions of a product"""
    try:
        # Get product
        product = db.session.query(Product).filter_by(name=product_name).first()
        if not product:
            return None
        
        # Get version objects
        from_ver = db.session.query(Version).filter_by(
            product_id=product.id, 
            version_number=from_version
        ).first()
        
        to_ver = db.session.query(Version).filter_by(
            product_id=product.id, 
            version_number=to_version
        ).first()
        
        if not from_ver or not to_ver:
            return None
        
        # Get changes for the version range
        changes = db.session.query(VersionChange).join(Version).filter(
            Version.product_id == product.id,
            Version.version_number.between(min(from_version, to_version), max(from_version, to_version))
        ).all()
        
        # Process changes by connector
        connector_changes = {}
        general_changes = []
        
        for change in changes:
            # For Starburst, parse section prefixes like [General#], [Delta Lake connector], etc.
            change_text = change.change_text
            connector_name = None
            
            # Check if this is a Starburst change with section prefix
            if change_text.startswith('[') and ']' in change_text:
                section_end = change_text.find(']')
                section_name = change_text[1:section_end].replace('#', '').strip()
                clean_text = change_text[section_end+1:].strip()
                
                # Map section names to connector categories
                if 'connector' in section_name.lower():
                    connector_name = section_name
                elif section_name.lower() in ['breaking change', 'security', 'general']:
                    connector_name = section_name
                else:
                    # Check if it's a known connector type
                    known_connectors = ['delta lake', 'hive', 'iceberg', 'bigquery', 'oracle', 'opensearch']
                    for conn in known_connectors:
                        if conn in section_name.lower():
                            connector_name = f"{conn.title()} Connector"
                            break
                    
                    if not connector_name:
                        connector_name = section_name
                
                # Create change object with cleaned text
                change_obj = {
                    'text': clean_text,
                    'version': change.version.version_number,
                    'is_breaking': 'breaking' in section_name.lower(),
                    'issue_number': change.issue_number
                }
            else:
                # Original logic for non-Starburst changes
                if change.connector:
                    connector_name = change.connector.name
                
                change_obj = {
                    'text': change_text,
                    'version': change.version.version_number,
                    'is_breaking': change.is_breaking,
                    'issue_number': change.issue_number
                }
            
            # Add to appropriate category
            if connector_name:
                if connector_name not in connector_changes:
                    connector_changes[connector_name] = []
                connector_changes[connector_name].append(change_obj)
            else:
                general_changes.append(change_obj)
        
        # Create summary
        total_changes = len(changes)
        connector_count = len(connector_changes)
        
        return {
            'connector_changes': connector_changes,
            'general_changes': general_changes,
            'summary': {
                'total_changes': total_changes,
                'connector_count': connector_count,
                'general_count': len(general_changes)
            }
        }
    
    except Exception as e:
        logger.error(f"Error comparing versions: {e}")
        return None

@app.route('/')
def index():
    """Home page with product and version selection form"""
    # Get all available products
    products = db.session.query(Product).all()
    
    # Default to first product or create default products
    if not products:
        try:
            with app.app_context():
                # Initialize default products
                trino_product = Product(name='trino', display_name='Trino')
                starburst_product = Product(name='starburst', display_name='Starburst')
                db.session.add(trino_product)
                db.session.add(starburst_product)
                db.session.commit()
                products = [trino_product, starburst_product]
        except Exception as e:
            logger.error(f"Error creating products: {e}")
            products = []
    
    # Get selected product from request
    default_product = products[0].name if products else 'trino'
    selected_product = request.args.get('product', default_product)
    
    # Get versions for selected product
    versions = []
    if products:
        product = db.session.query(Product).filter_by(name=selected_product).first()
        if product:
            version_query = db.session.query(Version).filter_by(product_id=product.id).order_by(
                Version.version_number.desc()
            ).all()
            versions = [v.version_number for v in version_query]
        
        # If no versions are available, scrape them
        if not versions:
            try:
                with app.app_context():
                    scraper.update_database(selected_product)
                
                # Query again after update
                if product:
                    version_query = db.session.query(Version).filter_by(product_id=product.id).order_by(
                        Version.version_number.desc()
                    ).all()
                    versions = [v.version_number for v in version_query]
            except Exception as e:
                logger.error(f"Error updating database: {e}")
    
    return render_template('index.html', 
                         products=products, 
                         selected_product=selected_product,
                         versions=versions)

@app.route('/compare', methods=['GET', 'POST'])
def compare():
    """Compare two versions of a product"""
    if request.method == 'POST':
        product = request.form.get('product', 'trino')
        from_version = request.form.get('from_version')
        to_version = request.form.get('to_version')
        
        # Redirect to GET endpoint with query parameters
        return redirect(url_for('compare', product=product, from_version=from_version, to_version=to_version))
    
    # Handle GET request with query parameters
    product = request.args.get('product', 'trino')
    from_version = request.args.get('from_version')
    to_version = request.args.get('to_version')
    
    if not from_version or not to_version:
        return redirect(url_for('index', product=product))
    
    # Get comparison data
    try:
        comparison = compare_versions(product, from_version, to_version)
        
        if not comparison:
            logger.error(f"Failed to generate comparison between {from_version} and {to_version}")
            return render_template('index.html', error="Failed to generate comparison. Please try again.")
        
        # Sort connectors alphabetically
        connector_changes = {k: comparison['connector_changes'][k] for k in 
                            sorted(comparison['connector_changes'].keys())}
        
        return render_template('comparison.html', 
                               product=product,
                               from_version=from_version, 
                               to_version=to_version,
                               connector_changes=connector_changes,
                               general_changes=comparison['general_changes'],
                               summary=comparison['summary'])
    
    except Exception as e:
        logger.error(f"Error generating comparison: {e}")
        return redirect(url_for('index', product=product, error=f"Error: {str(e)}"))

@app.route('/refresh')
def refresh_data():
    """Force refresh of versions data for a specific product or all products"""
    product = request.args.get('product')
    try:
        with app.app_context():
            scraper.update_database(product)
        return redirect(url_for('index', product=product, refresh_status="success"))
    except Exception as e:
        logger.error(f"Error refreshing data: {e}")
        return redirect(url_for('index', product=product, refresh_status="error", error=str(e)))

@app.route('/api/versions')
def api_versions():
    """API endpoint to get all available versions for a product"""
    product_name = request.args.get('product', 'trino')
    product = db.session.query(Product).filter_by(name=product_name).first()
    
    if not product:
        return jsonify([])
    
    versions = db.session.query(Version.version_number).filter_by(
        product_id=product.id
    ).order_by(Version.version_number.desc()).all()
    
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
