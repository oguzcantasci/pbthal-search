// DOM Elements
const searchForm = document.getElementById('searchForm');
const searchInput = document.getElementById('searchInput');
const searchButton = document.getElementById('searchButton');
const resultsDiv = document.getElementById('results');
const loadingDiv = document.getElementById('loading');
const errorDiv = document.getElementById('errorMessage');
const authStatusBar = document.getElementById('authStatusBar');
const authStatusValue = document.getElementById('authStatusValue');
const rdStatusBar = document.getElementById('rdStatusBar');
const rdStatusValue = document.getElementById('rdStatusValue');

// State
let realdebridConnected = false;

// Utility Functions
function showError(message) {
    errorDiv.textContent = message;
    errorDiv.classList.add('active');
    setTimeout(() => {
        errorDiv.classList.remove('active');
    }, 5000);
}

function showLoading() {
    loadingDiv.classList.add('active');
    searchButton.disabled = true;
    resultsDiv.innerHTML = '';
}

function hideLoading() {
    loadingDiv.classList.remove('active');
    searchButton.disabled = false;
}

function updateStatusBar(loggedIn, errorMessage = '') {
    authStatusBar.classList.toggle('logged-in', loggedIn);
    authStatusBar.classList.toggle('not-logged-in', !loggedIn);
    authStatusValue.textContent = loggedIn ? 'Logged in' : 'Not logged in';
    authStatusValue.title = errorMessage || (loggedIn ? 'Authenticated' : 'Not authenticated');
}

// Authentication Functions
async function checkAuthStatus(showPrompt = false) {
    try {
        const response = await fetch('/auth-status', {
            credentials: 'include'
        });
        const data = await response.json();
        updateStatusBar(data.loggedIn, data.error);
        if (!data.loggedIn && showPrompt) {
            displayLoginPrompt('You are not logged in. Use the instructions below to export cookies.');
        }
        return data.loggedIn;
    } catch (error) {
        updateStatusBar(false, error.message);
        if (showPrompt) {
            displayLoginPrompt('Unable to verify login state. Please log in and upload cookies.');
        }
        return false;
    }
}

function highlightMatch(text, query) {
    if (!query) return text;
    const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(${escapedQuery})`, 'gi');
    return text.replace(regex, '<strong>$1</strong>');
}

function formatResult(result, query) {
    const highlightedAlbum = highlightMatch(result.album, query);
    const datePart = result.postDate ? result.postDate : '';
    const seriesLink = result.postUrl 
        ? `<a href="${result.postUrl}" target="_blank" rel="noopener noreferrer" class="series-link">${result.postTitle}</a>`
        : result.postTitle;
    // Escape quotes for data attributes
    const escapedUrl = result.url.replace(/"/g, '&quot;');
    const escapedAlbum = result.album.replace(/"/g, '&quot;');
    const realdebridButton = realdebridConnected 
        ? `<button class="rd-button" data-url="${escapedUrl}" data-album="${escapedAlbum}">Unrestrict via Real-Debrid</button>`
        : '';
    return `
        <div class="result-content">
            <a href="${result.url}" target="_blank" rel="noopener noreferrer" class="album-link">
                <div class="result-album">${highlightedAlbum}</div>
            </a>
            <div class="result-meta-line">
                <div class="result-meta">${seriesLink}</div>
                ${datePart ? `<div class="result-date">${datePart}</div>` : ''}
            </div>
            ${realdebridButton}
        </div>
    `;
}

// Real-Debrid Functions
async function checkRealDebridStatus() {
    try {
        const response = await fetch('/realdebrid/status', {
            credentials: 'include'
        });
        const data = await response.json();
        realdebridConnected = !!data.connected;
        
        rdStatusBar.classList.toggle('logged-in', realdebridConnected);
        rdStatusBar.classList.toggle('not-logged-in', !realdebridConnected);
        rdStatusValue.textContent = realdebridConnected ? 'Connected' : 'Not connected';
        
        // Show token input if not connected
        if (!realdebridConnected) {
            showRealDebridTokenInput();
        } else {
            hideRealDebridTokenInput();
        }
        
        return realdebridConnected;
    } catch (error) {
        console.error('Error checking Real-Debrid status:', error);
        realdebridConnected = false;
        rdStatusValue.textContent = 'Error';
        showRealDebridTokenInput();
        return false;
    }
}

function showRealDebridTokenInput() {
    // Check if already shown
    if (document.getElementById('realdebridTokenInput')) {
        return;
    }
    
    const tokenHTML = `
        <div class="realdebrid-token-input" id="realdebridTokenInput">
            <h3>Connect Real-Debrid</h3>
            <p>Enter your Real-Debrid API token to unrestrict and download links.</p>
            <p class="small-text">
                Get your token from: <a href="https://real-debrid.com/apitoken" target="_blank" rel="noopener noreferrer">real-debrid.com/apitoken</a>
            </p>
            <input 
                type="text" 
                id="rdTokenInput" 
                placeholder="Paste your Real-Debrid API token here"
            />
            <button id="saveRdTokenBtn">Save Token</button>
        </div>
    `;
    
    // Insert after status bars
    const statusContainer = rdStatusBar.parentElement;
    statusContainer.insertAdjacentHTML('afterend', tokenHTML);
    
    // Add event listener
    document.getElementById('saveRdTokenBtn').addEventListener('click', async () => {
        const token = document.getElementById('rdTokenInput').value.trim();
        if (!token) {
            showError('Please enter your Real-Debrid API token');
            return;
        }
        
        try {
            const response = await fetch('/realdebrid/set-token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({ token: token })
            });
            const data = await response.json();
            
            if (data.success) {
                showError(`Real-Debrid connected successfully! (${data.username})`);
                await checkRealDebridStatus();
                // Refresh results to show Real-Debrid buttons
                if (resultsDiv.innerHTML && !resultsDiv.innerHTML.includes('no-results')) {
                    const currentQuery = searchInput.value;
                    if (currentQuery) {
                        searchForm.dispatchEvent(new Event('submit'));
                    }
                }
            } else {
                showError(`Real-Debrid error: ${data.error}`);
            }
        } catch (error) {
            showError(`Error: ${error.message}`);
        }
    });
}

function hideRealDebridTokenInput() {
    const tokenInput = document.getElementById('realdebridTokenInput');
    if (tokenInput) {
        tokenInput.remove();
    }
}

async function handleRealDebridUnrestrict(link, albumName) {
    const confirmed = confirm(`Do you want to unrestrict this link and start downloading using Real-Debrid?\n\nAlbum: ${albumName}`);
    if (!confirmed) {
        return;
    }
    
    try {
        showError('Unrestricting link via Real-Debrid...');
        const response = await fetch('/realdebrid/unrestrict', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify({ link: link })
        });
        
        const data = await response.json();
        if (data.error) {
            if (data.error.includes('not connected') || data.error.includes('expired') || data.error.includes('invalid')) {
                showError('Real-Debrid connection expired. Please reconnect your account.');
                realdebridConnected = false;
                await checkRealDebridStatus();
            } else {
                showError(`Real-Debrid error: ${data.error}`);
            }
            return;
        }
        
        // Open unrestricted link to start download
        window.open(data.download, '_blank');
        showError('Unrestricted link generated! Download started in new tab.');
    } catch (error) {
        showError(`Error: ${error.message}`);
    }
}

// Display Functions
function displayLoginPrompt(message = '') {
    resultsDiv.innerHTML = `
        <div class="login-prompt">
            <h3>Login Required</h3>
            <p>You need to be logged in to tonepoet.fans to search.</p>
            ${message ? `<p style="font-weight:600;color:#ffffff;">${message}</p>` : ''}
            <p style="margin-top:0;">
                Install one of these extensions to export your cookies as a Netscape cookie file:
            </p>
            <ul style="text-align: left; margin: 0 0 15px 20px;">
                <li><a href="https://addons.mozilla.org/en-CA/firefox/addon/cookies-txt/" target="_blank" rel="noopener noreferrer">cookies.txt (Firefox)</a></li>
                <li><a href="https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc?pli=1" target="_blank" rel="noopener noreferrer">Get cookies.txt LOCALLY (Chrome)</a></li>
            </ul>
            <div style="margin-top: 10px;">
                <label for="cookieFileInput" style="display:block; margin-bottom: 8px; font-weight:600;">Upload the exported .txt file:</label>
                <input 
                    type="file" 
                    id="cookieFileInput" 
                    accept=".txt"
                    class="file-input"
                />
                <button 
                    id="saveCookiesBtn" 
                    class="upload-button"
                >
                    Upload Cookies File
                </button>
            </div>
            <p style="margin-top: 15px; font-size: 14px; color: #f0f0f0;">Open <a href="https://tonepoet.fans/wp-login.php" target="_blank" rel="noopener noreferrer" style="color: #ffffff; text-decoration: underline;">tonepoet.fans login</a> in a new tab, install the extension, export cookies, then upload.</p>
        </div>
    `;
    document.getElementById('saveCookiesBtn').addEventListener('click', async () => {
        const fileInput = document.getElementById('cookieFileInput');
        if (!fileInput.files || !fileInput.files[0]) {
            showError('Please select a cookies.txt file exported by the extension.');
            return;
        }
        try {
            const content = await fileInput.files[0].text();
            const response = await fetch('/set-cookies', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({ cookieFile: content })
            });
            const data = await response.json();
            if (data.success) {
                showError('Cookies uploaded and validated! Trying search again...');
                checkAuthStatus();
                setTimeout(() => searchForm.dispatchEvent(new Event('submit')), 1000);
            } else {
                showError(data.error || 'Failed to validate cookies. Please try again.');
            }
        } catch (error) {
            showError(`Error: ${error.message}`);
        }
    });
}

function displayResults(results, query = '') {
    if (results.length === 0) {
        resultsDiv.innerHTML = '<div class="no-results">No results found. Try a different search query.</div>';
        return;
    }
    
    resultsDiv.innerHTML = results.map(result => {
        const formattedText = formatResult(result, query);
        return `
            <div class="result-item">
                ${formattedText}
            </div>
        `;
    }).join('');
    
    // Attach event listeners to Real-Debrid buttons
    if (realdebridConnected) {
        document.querySelectorAll('.rd-button').forEach(button => {
            button.addEventListener('click', () => {
                const url = button.getAttribute('data-url');
                const album = button.getAttribute('data-album');
                handleRealDebridUnrestrict(url, album);
            });
        });
    }
}

// Event Listeners
searchForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = searchInput.value.trim();
    if (!query) {
        showError('Please enter a search query');
        return;
    }
    showLoading();
    try {
        const response = await fetch(`/search?q=${encodeURIComponent(query)}`, {
            credentials: 'include'
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Search failed');
        }
        if (data.requiresAuth) {
            displayLoginPrompt();
        } else {
            displayResults(data.results || [], query);
        }
    } catch (error) {
        showError(`Error: ${error.message}`);
        resultsDiv.innerHTML = '';
    } finally {
        hideLoading();
    }
});

// Initialize on page load
window.addEventListener('load', async () => {
    checkAuthStatus(true);
    await checkRealDebridStatus();
});

