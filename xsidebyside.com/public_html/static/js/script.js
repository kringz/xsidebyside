document.addEventListener('DOMContentLoaded', function() {
    // Handle collapsible sections
    document.querySelectorAll('.connector-header').forEach(header => {
        header.addEventListener('click', function() {
            const content = this.nextElementSibling;
            const icon = this.querySelector('.collapse-icon');
            
            // Toggle the collapse state
            if (content.style.display === 'none' || !content.style.display) {
                content.style.display = 'block';
                if (icon) icon.innerHTML = '&#9650;'; // Up arrow
            } else {
                content.style.display = 'none';
                if (icon) icon.innerHTML = '&#9660;'; // Down arrow
            }
        });
    });
    
    // Expand/Collapse All buttons
    const expandAllBtn = document.getElementById('expand-all');
    const collapseAllBtn = document.getElementById('collapse-all');
    
    if (expandAllBtn) {
        expandAllBtn.addEventListener('click', function(e) {
            e.preventDefault();
            document.querySelectorAll('.connector-content').forEach(content => {
                content.style.display = 'block';
            });
            document.querySelectorAll('.collapse-icon').forEach(icon => {
                icon.innerHTML = '&#9650;'; // Up arrow
            });
        });
    }
    
    if (collapseAllBtn) {
        collapseAllBtn.addEventListener('click', function(e) {
            e.preventDefault();
            document.querySelectorAll('.connector-content').forEach(content => {
                content.style.display = 'none';
            });
            document.querySelectorAll('.collapse-icon').forEach(icon => {
                icon.innerHTML = '&#9660;'; // Down arrow
            });
        });
    }
    
    // Version selection form
    const versionForm = document.getElementById('version-form');
    const fromVersion = document.getElementById('from-version');
    const toVersion = document.getElementById('to-version');
    
    if (versionForm && fromVersion && toVersion) {
        versionForm.addEventListener('submit', function(e) {
            if (!fromVersion.value || !toVersion.value) {
                e.preventDefault();
                alert('Please select both versions for comparison');
                return false;
            }
            
            // Show loading spinner
            document.getElementById('loading-spinner').style.display = 'block';
            return true;
        });
    }
    
    // Search functionality
    const searchForm = document.getElementById('search-form');
    const searchResults = document.getElementById('search-results');
    const searchProduct = document.getElementById('search-product');
    const searchConnector = document.getElementById('search-connector');
    const searchFromVersion = document.getElementById('search-from-version');
    const searchToVersion = document.getElementById('search-to-version');

    // Load connectors on page load (only if not already populated server-side)
    if (searchConnector) {
        const currentOptions = searchConnector.options.length;
        console.log(`Connector dropdown has ${currentOptions} options`);

        // Only fetch if dropdown is empty (besides the default option)
        if (currentOptions <= 1) {
            console.log('Loading connectors from API...');
            fetch('/api/connectors')
                .then(response => {
                    console.log('Connectors API response received:', response.status);
                    return response.json();
                })
                .then(data => {
                    const connectors = data.connectors || [];
                    console.log(`Found ${connectors.length} connectors`);

                    // Build options HTML
                    let optionsHTML = '<option value="">All Connectors</option>';
                    connectors.forEach(connector => {
                        optionsHTML += `<option value="${connector}">${connector}</option>`;
                    });

                    // Set all options at once
                    searchConnector.innerHTML = optionsHTML;
                    console.log('Connectors loaded successfully');
                })
                .catch(error => {
                    console.error('Error fetching connectors:', error);
                });
        } else {
            console.log('Connectors already populated server-side');
        }
    } else {
        console.warn('search-connector element not found');
    }

    // Update search version dropdowns when product changes
    if (searchProduct) {
        searchProduct.addEventListener('change', function() {
            const product = this.value;
            if (!product) {
                // Reset to show all versions
                return;
            }

            // Fetch versions for selected product
            fetch(`/api/versions?product=${encodeURIComponent(product)}`)
                .then(response => response.json())
                .then(data => {
                    const versions = data.versions || [];

                    // Update from version dropdown
                    if (searchFromVersion) {
                        searchFromVersion.innerHTML = '<option value="">Any Version</option>';
                        versions.forEach(version => {
                            searchFromVersion.innerHTML += `<option value="${version}">${version}</option>`;
                        });
                    }

                    // Update to version dropdown
                    if (searchToVersion) {
                        searchToVersion.innerHTML = '<option value="">Any Version</option>';
                        versions.forEach(version => {
                            searchToVersion.innerHTML += `<option value="${version}">${version}</option>`;
                        });
                    }
                })
                .catch(error => {
                    console.error('Error fetching versions:', error);
                });
        });
    }

    if (searchForm && searchResults) {
        searchForm.addEventListener('submit', function(e) {
            e.preventDefault();

            const keyword = document.getElementById('search-keyword').value;
            if (!keyword || keyword.length < 3) {
                alert('Please enter at least 3 characters for search');
                return false;
            }

            // Build query parameters
            let queryParams = `keyword=${encodeURIComponent(keyword)}`;

            if (searchProduct && searchProduct.value) {
                queryParams += `&product=${encodeURIComponent(searchProduct.value)}`;
            }

            if (searchConnector && searchConnector.value) {
                queryParams += `&connector=${encodeURIComponent(searchConnector.value)}`;
            }

            if (searchFromVersion && searchFromVersion.value) {
                queryParams += `&from_version=${encodeURIComponent(searchFromVersion.value)}`;
            }

            if (searchToVersion && searchToVersion.value) {
                queryParams += `&to_version=${encodeURIComponent(searchToVersion.value)}`;
            }

            console.log('Search query params:', queryParams);

            // Show loading spinner
            const spinner = document.getElementById('search-spinner');
            if (spinner) spinner.style.display = 'block';

            // Perform AJAX search
            fetch(`/api/search?${queryParams}`)
                .then(response => response.json())
                .then(data => {
                    if (spinner) spinner.style.display = 'none';

                    // Clear previous results
                    searchResults.innerHTML = '';

                    if (data.error) {
                        searchResults.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
                        return;
                    }

                    if (data.count === 0) {
                        searchResults.innerHTML = '<div class="alert alert-info">No results found</div>';
                        return;
                    }

                    // Display results
                    const resultHTML = `
                        <div class="alert alert-success">${data.count} results found</div>
                        <div class="list-group">
                            ${data.results.map(result => {
                                // Build release notes URL based on product
                                const releaseUrl = result.product === 'starburst'
                                    ? `https://docs.starburst.io/latest/release/release-${result.version}.html`
                                    : `https://trino.io/docs/current/release/release-${result.version}.html`;

                                return `
                                <div class="list-group-item ${result.is_breaking ? 'breaking-change' : ''}">
                                    <div class="d-flex justify-content-between align-items-center">
                                        <span class="version-badge">v${result.version}</span>
                                        <span class="connector-badge">${result.connector}</span>
                                    </div>
                                    ${result.is_breaking ? '<span class="badge bg-danger">Breaking Change</span>' : ''}
                                    <div class="mt-2">${result.text}</div>
                                    <a href="${releaseUrl}" target="_blank" class="release-notes-link">
                                        <i class="fa-solid fa-external-link-alt"></i> View in release notes
                                    </a>
                                </div>
                                `;
                            }).join('')}
                        </div>
                    `;

                    searchResults.innerHTML = resultHTML;
                })
                .catch(error => {
                    if (spinner) spinner.style.display = 'none';
                    searchResults.innerHTML = `<div class="alert alert-danger">Error: ${error}</div>`;
                });
        });
    }
    
    // Swap versions button
    const swapBtn = document.getElementById('swap-versions');
    
    if (swapBtn && fromVersion && toVersion) {
        swapBtn.addEventListener('click', function(e) {
            e.preventDefault();
            const temp = fromVersion.value;
            fromVersion.value = toVersion.value;
            toVersion.value = temp;
        });
    }
    
    // Initialize any tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    if (typeof bootstrap !== 'undefined') {
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
});
