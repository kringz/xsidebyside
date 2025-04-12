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
    
    if (searchForm && searchResults) {
        searchForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const keyword = document.getElementById('search-keyword').value;
            if (!keyword || keyword.length < 3) {
                alert('Please enter at least 3 characters for search');
                return false;
            }
            
            // Show loading spinner
            const spinner = document.getElementById('search-spinner');
            if (spinner) spinner.style.display = 'block';
            
            // Perform AJAX search
            fetch(`/api/search?keyword=${encodeURIComponent(keyword)}`)
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
                            ${data.results.map(result => `
                                <div class="list-group-item ${result.is_breaking ? 'breaking-change' : ''}">
                                    <div class="d-flex justify-content-between align-items-center">
                                        <span class="version-badge">${result.version}</span>
                                        <span class="connector-badge">${result.connector}</span>
                                    </div>
                                    <div class="mt-2">${result.text}</div>
                                </div>
                            `).join('')}
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
