from flask import render_template, request, jsonify, redirect, url_for, make_response
from app import app, db
from models import Product, Version, Connector, VersionChange
from unified_scraper import UnifiedScraper
from sqlalchemy import cast, Integer, func
import logging
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import red, black, blue
import io
from datetime import datetime

logger = logging.getLogger(__name__)
scraper = UnifiedScraper()

def format_connector_name(name):
    """Helper function to consistently format connector names without duplicates"""
    if not name:
        return None
    
    import re
    # Remove any existing "connector" suffix (case insensitive)
    base_name = re.sub(r'\s*connector\s*$', '', name.strip(), flags=re.IGNORECASE).strip()
    # Always add "Connector" back properly
    return f"{base_name.title()} Connector"

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
        breaking_changes = []  # New: dedicated breaking changes section
        
        for change in changes:
            # For Starburst, parse section prefixes like [General#], [Delta Lake connector], etc.
            change_text = change.change_text
            connector_name = None
            
            # Check if this is a Starburst change with section prefix
            if change_text.startswith('[') and ']' in change_text:
                section_end = change_text.find(']')
                section_name = change_text[1:section_end].replace('#', '').strip()
                clean_text = change_text[section_end+1:].strip()
                
                # Skip version-based sections and analyze content for connector mentions
                import re
                version_pattern = r'^\d+-e(\.\d+)?\s+(initial\s+)?changes'
                
                if re.match(version_pattern, section_name.lower()):
                    # This is a version-based section, analyze the content for connector mentions
                    connector_name = None
                    known_connectors = ['delta lake', 'hive', 'iceberg', 'bigquery', 'oracle', 'opensearch', 
                                      'mysql', 'postgresql', 'mongodb', 'elasticsearch', 'databricks', 'redshift']
                    
                    # Check if the change content mentions any connectors
                    for conn in known_connectors:
                        variations = [conn, conn + ' connector', conn.replace(' ', ''), conn.replace(' ', '-')]
                        if any(var.lower() in clean_text.lower() for var in variations):
                            # Use consistent formatting function
                            connector_name = format_connector_name(conn)
                            break
                    
                    # If no connector found, it's a general change
                    if not connector_name:
                        connector_name = None  # Will go to general_changes
                        
                elif 'connector' in section_name.lower():
                    # Direct connector section - use consistent formatting
                    connector_name = format_connector_name(section_name)
                elif section_name.lower() in ['breaking change', 'security', 'general']:
                    # General category sections
                    connector_name = None  # Will go to general_changes
                else:
                    # Check if it's a known connector type mentioned in section name
                    known_connectors = ['delta lake', 'hive', 'iceberg', 'bigquery', 'oracle', 'opensearch', 
                                      'mysql', 'postgresql', 'mongodb', 'elasticsearch', 'databricks', 'redshift']
                    connector_name = None
                    for conn in known_connectors:
                        if conn.lower() in section_name.lower():
                            # Use consistent formatting function
                            connector_name = format_connector_name(conn)
                            break
                    
                    # If still no match, it's likely a general change
                    if not connector_name:
                        connector_name = None  # Will go to general_changes
                
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
            
            # Add to appropriate category - prioritize breaking changes
            if change_obj.get('is_breaking', False):
                # All breaking changes go to dedicated breaking changes section
                breaking_changes.append(change_obj)
            elif connector_name:
                if connector_name not in connector_changes:
                    connector_changes[connector_name] = []
                connector_changes[connector_name].append(change_obj)
            else:
                general_changes.append(change_obj)
        
        # Consolidate duplicate connector entries and deduplicate changes
        consolidated_connectors = {}
        for connector_name, changes_list in connector_changes.items():
            # Normalize connector name to title case
            normalized_name = connector_name.title()
            if normalized_name not in consolidated_connectors:
                consolidated_connectors[normalized_name] = []
            
            # Deduplicate changes based on text, version, and issue_number
            existing_changes = consolidated_connectors[normalized_name]
            for change in changes_list:
                # Create a unique key for this change
                change_key = (change['text'], change['version'], change.get('issue_number'))
                
                # Check if this change already exists
                is_duplicate = False
                for existing_change in existing_changes:
                    existing_key = (existing_change['text'], existing_change['version'], existing_change.get('issue_number'))
                    if change_key == existing_key:
                        is_duplicate = True
                        break
                
                # Only add if not a duplicate
                if not is_duplicate:
                    consolidated_connectors[normalized_name].append(change)
        
        # Deduplicate breaking changes
        deduplicated_breaking = []
        for change in breaking_changes:
            change_key = (change['text'], change['version'], change.get('issue_number'))
            is_duplicate = False
            for existing_change in deduplicated_breaking:
                existing_key = (existing_change['text'], existing_change['version'], existing_change.get('issue_number'))
                if change_key == existing_key:
                    is_duplicate = True
                    break
            if not is_duplicate:
                deduplicated_breaking.append(change)

        # Deduplicate general changes
        deduplicated_general = []
        for change in general_changes:
            change_key = (change['text'], change['version'], change.get('issue_number'))
            is_duplicate = False
            for existing_change in deduplicated_general:
                existing_key = (existing_change['text'], existing_change['version'], existing_change.get('issue_number'))
                if change_key == existing_key:
                    is_duplicate = True
                    break
            if not is_duplicate:
                deduplicated_general.append(change)

        # Create summary
        total_changes = len(changes)
        connector_count = len(consolidated_connectors)

        return {
            'connector_changes': consolidated_connectors,
            'general_changes': deduplicated_general,
            'breaking_changes': deduplicated_breaking,  # New: dedicated breaking changes section
            'summary': {
                'total_changes': total_changes,
                'connector_count': connector_count,
                'general_count': len(deduplicated_general),
                'breaking_count': len(deduplicated_breaking)  # New: breaking changes count
            }
        }
    
    except Exception as e:
        logger.error(f"Error comparing versions: {e}")
        return None

# generate_connector_report function removed - functionality integrated into main comparison page

@app.route('/export-comparison-pdf')
def export_comparison_pdf():
    """Export comparison results to PDF"""
    product = request.args.get('product', 'trino')
    from_version = request.args.get('from_version')
    to_version = request.args.get('to_version')
    selected_connectors = request.args.getlist('connectors')
    
    if not from_version or not to_version:
        return "Missing required parameters", 400
    
    # Get comparison data using the same logic as the compare route
    comparison = compare_versions(product, from_version, to_version)
    if not comparison:
        return "Failed to generate comparison", 500
    
    # Filter by selected connectors if any are specified
    connector_changes = comparison['connector_changes']
    if selected_connectors:
        # Filter to only show selected connectors
        filtered_connector_changes = {}
        for connector_name, changes in connector_changes.items():
            # Check if this connector matches any of the selected ones
            for selected in selected_connectors:
                if selected.lower() in connector_name.lower():
                    filtered_connector_changes[connector_name] = changes
                    break
        connector_changes = filtered_connector_changes
    
    # Sort connectors alphabetically
    connector_changes = {k: connector_changes[k] for k in sorted(connector_changes.keys())}
    
    # Get breaking changes for dedicated section
    breaking_changes = comparison.get('breaking_changes', [])
    
    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=inch, bottomMargin=inch)
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        textColor=blue
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        spaceBefore=20
    )
    
    breaking_style = ParagraphStyle(
        'BreakingChange',
        parent=styles['Normal'],
        fontSize=10,
        textColor=red,
        leftIndent=20,
        spaceAfter=6
    )
    
    normal_change_style = ParagraphStyle(
        'NormalChange',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=20,
        spaceAfter=6
    )
    
    # Build PDF content
    story = []
    
    # Title
    title = f"{product.title()} Release Notes Comparison"
    story.append(Paragraph(title, title_style))
    
    # Summary
    total_changes = sum(len(changes) for changes in connector_changes.values()) + len(comparison['general_changes']) + len(breaking_changes)
    connector_filter_text = f" (Filtered by: {', '.join(selected_connectors)})" if selected_connectors else ""
    summary_text = f"""<b>Version Range:</b> {from_version} to {to_version}<br/>
    <b>Total Changes:</b> {total_changes}{connector_filter_text}<br/>
    <b>Breaking Changes:</b> {len(breaking_changes)}<br/>
    <b>Connector Changes:</b> {len(connector_changes)}<br/>
    <b>General Changes:</b> {len(comparison['general_changes'])}<br/>
    <b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    story.append(Paragraph(summary_text, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Breaking Changes Section
    if breaking_changes:
        story.append(Paragraph(f"⚠️ Breaking Changes ({len(breaking_changes)})", heading_style))
        for change in breaking_changes:
            version_text = f"<b>v{change['version']}</b>"
            change_text = f"{version_text} [BREAKING CHANGE] {change['text']}"
            story.append(Paragraph(change_text, breaking_style))
        story.append(Spacer(1, 20))
    
    # Connector changes
    if connector_changes:
        for connector_name, changes in connector_changes.items():
            # Connector heading
            connector_title = f"{connector_name} ({len(changes)} changes)"
            story.append(Paragraph(connector_title, heading_style))
            
            # Changes (excluding breaking changes as they have their own section)
            for change in changes:
                if not change.get('is_breaking', False):  # Only show non-breaking changes here
                    version_text = f"<b>v{change['version']}</b>"
                    change_text = f"{version_text} {change['text']}"
                    story.append(Paragraph(change_text, normal_change_style))
    
    # General changes (excluding breaking changes as they have their own section)
    if comparison['general_changes']:
        story.append(Paragraph("General Changes", heading_style))
        for change in comparison['general_changes']:
            if not change.get('is_breaking', False):  # Only show non-breaking changes here
                version_text = f"<b>v{change['version']}</b>"
                change_text = f"{version_text} {change['text']}"
                story.append(Paragraph(change_text, normal_change_style))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    
    # Create response
    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    connector_filter_suffix = f"_{'_'.join(selected_connectors)}" if selected_connectors else ""
    response.headers['Content-Disposition'] = f'attachment; filename="{product}_comparison_{from_version}_to_{to_version}{connector_filter_suffix}.pdf"'
    
    return response

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

    # Get all connectors
    connectors = db.session.query(Connector).order_by(Connector.name).all()

    return render_template('index.html',
                         products=products,
                         selected_product=selected_product,
                         versions=versions,
                         connectors=connectors)

@app.route('/compare', methods=['GET', 'POST'])
def compare():
    """Compare two versions of a product"""
    if request.method == 'POST':
        product = request.form.get('product', 'trino')
        from_version = request.form.get('from_version')
        to_version = request.form.get('to_version')
        selected_connectors = request.form.getlist('connectors')
        
        # Redirect to GET endpoint with query parameters
        redirect_url = url_for('compare', product=product, from_version=from_version, to_version=to_version)
        if selected_connectors:
            # Add connector parameters to URL
            connector_params = '&'.join([f'connectors={connector}' for connector in selected_connectors])
            redirect_url += f'&{connector_params}'
        return redirect(redirect_url)
    
    # Handle GET request with query parameters
    product = request.args.get('product', 'trino')
    from_version = request.args.get('from_version')
    to_version = request.args.get('to_version')
    selected_connectors = request.args.getlist('connectors')
    
    if not from_version or not to_version:
        return redirect(url_for('index', product=product))
    
    # Get comparison data
    try:
        comparison = compare_versions(product, from_version, to_version)
        
        if not comparison:
            logger.error(f"Failed to generate comparison between {from_version} and {to_version}")
            return render_template('index.html', error="Failed to generate comparison. Please try again.")
        
        # Filter by selected connectors if any are specified
        connector_changes = comparison['connector_changes']
        if selected_connectors:
            # Filter to only show selected connectors
            filtered_connector_changes = {}
            for connector_name, changes in connector_changes.items():
                # Check if this connector matches any of the selected ones
                for selected in selected_connectors:
                    if selected.lower() in connector_name.lower():
                        filtered_connector_changes[connector_name] = changes
                        break
            connector_changes = filtered_connector_changes
        
        # Sort connectors alphabetically
        connector_changes = {k: connector_changes[k] for k in 
                            sorted(connector_changes.keys())}
        
        # Update summary counts based on filtered results
        breaking_changes = comparison.get('breaking_changes', [])
        filtered_summary = {
            'total_changes': sum(len(changes) for changes in connector_changes.values()) + len(comparison['general_changes']) + len(breaking_changes),
            'connector_count': len(connector_changes),
            'general_count': len(comparison['general_changes']),
            'breaking_count': len(breaking_changes)
        }
        
        return render_template('comparison.html', 
                               product=product,
                               from_version=from_version, 
                               to_version=to_version,
                               connector_changes=connector_changes,
                               general_changes=comparison['general_changes'],
                               breaking_changes=breaking_changes,
                               summary=filtered_summary,
                               selected_connectors=selected_connectors)
    
    except Exception as e:
        logger.error(f"Error generating comparison: {e}")
        return redirect(url_for('index', product=product, error=f"Error: {str(e)}"))

# Refresh endpoint removed - scraper now runs via cron job
# Connector report functionality removed - integrated into main comparison page

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

    return jsonify({'versions': [v[0] for v in versions]})

@app.route('/api/connectors')
def api_connectors():
    """API endpoint to get all available connectors"""
    connectors = db.session.query(Connector).order_by(Connector.name).all()
    return jsonify({'connectors': [c.name for c in connectors]})

@app.route('/api/search')
def api_search():
    """API endpoint to search for changes by keyword"""
    keyword = request.args.get('keyword', '')
    product_name = request.args.get('product', '')
    from_version = request.args.get('from_version', '')
    to_version = request.args.get('to_version', '')
    connector_name = request.args.get('connector', '')

    if not keyword or len(keyword) < 3:
        return jsonify({"error": "Search term must be at least 3 characters"})

    # Start with base query
    query = db.session.query(VersionChange).join(Version).join(Product)

    # Filter by keyword
    query = query.filter(VersionChange.change_text.ilike(f'%{keyword}%'))

    # Filter by product if specified
    if product_name:
        query = query.filter(Product.name == product_name)

    # Get all matching changes (will filter by version in Python)
    changes = query.all()

    # Helper function to extract numeric version
    def get_version_number(version_str):
        """Extract numeric part from version string (e.g., '478' from '478' or '477-e')"""
        try:
            return int(version_str.split('-')[0])
        except (ValueError, AttributeError):
            return 0

    # Filter by version range if specified
    if from_version and to_version:
        from_num = get_version_number(from_version)
        to_num = get_version_number(to_version)
        min_ver = min(from_num, to_num)
        max_ver = max(from_num, to_num)
        changes = [c for c in changes if min_ver <= get_version_number(c.version.version_number) <= max_ver]
    elif from_version:
        from_num = get_version_number(from_version)
        changes = [c for c in changes if get_version_number(c.version.version_number) >= from_num]
    elif to_version:
        to_num = get_version_number(to_version)
        changes = [c for c in changes if get_version_number(c.version.version_number) <= to_num]

    results = []
    seen = set()  # Track unique combinations to avoid duplicates

    for change in changes:
        # Extract connector name from change text (since it's not linked in DB)
        connector_name_display = "General"
        if change.change_text.startswith('[') and ']' in change.change_text:
            section_end = change.change_text.find(']')
            section_name = change.change_text[1:section_end].replace('#', '').strip()

            # Check if it's a connector section
            import re
            if 'connector' in section_name.lower() or any(conn.lower() in section_name.lower() for conn in [
                'delta lake', 'hive', 'iceberg', 'bigquery', 'oracle', 'opensearch',
                'mysql', 'postgresql', 'mongodb', 'elasticsearch', 'databricks', 'redshift',
                'kafka', 'cassandra', 'clickhouse'
            ]):
                connector_name_display = section_name

        # Filter by connector name if specified (text-based filtering)
        if connector_name:
            if connector_name.lower() not in connector_name_display.lower():
                continue

        # Create unique key to detect duplicates
        unique_key = (change.change_text, change.version.version_number)
        if unique_key in seen:
            continue
        seen.add(unique_key)

        results.append({
            "version": change.version.version_number,
            "connector": connector_name_display,
            "text": change.change_text,
            "is_breaking": change.is_breaking,
            "product": change.version.product.name
        })

    return jsonify({"results": results, "count": len(results)})
