// =============================================================================
// 🤖 CHATBASE CLONE — SHARED APP UTILITIES
// =============================================================================

/**
 * Get the configured API URL from localStorage.
 * @returns {string} The backend API URL
 */
function getApiUrl() {
    return (localStorage.getItem('chatbase_api_url') || '').replace(/\/+$/, '');
}

/**
 * Escape HTML entities to prevent XSS.
 * @param {string} text
 * @returns {string}
 */
function escapeHtml(text) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}

/**
 * Show a toast notification.
 * @param {string} message
 * @param {'success'|'error'} type
 * @param {number} duration - ms to show (default 4000)
 */
function showToast(message, type = 'success', duration = 4000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icon = type === 'success' ? '✅' : '❌';
    toast.innerHTML = `<span>${icon}</span><span>${escapeHtml(message)}</span>`;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/**
 * Make an API request with error handling.
 * @param {string} endpoint - relative path like /api/chatbots
 * @param {object} options - fetch options
 * @returns {Promise<any>}
 */
async function apiRequest(endpoint, options = {}) {
    const url = getApiUrl();
    if (!url) {
        throw new Error('API URL not configured. Go to Dashboard → API Settings.');
    }

    const response = await fetch(`${url}${endpoint}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
        signal: options.signal || AbortSignal.timeout(30000),
    });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || `Request failed (${response.status})`);
    }

    return response.json();
}

/**
 * Format a date string to a readable format.
 * @param {string} dateStr
 * @returns {string}
 */
function formatDate(dateStr) {
    try {
        return new Date(dateStr).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
        });
    } catch {
        return dateStr;
    }
}

/**
 * Debounce a function.
 * @param {Function} fn
 * @param {number} ms
 * @returns {Function}
 */
function debounce(fn, ms = 300) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), ms);
    };
}

// =============================================================================
// Service worker registration (optional PWA support)
// =============================================================================
if ('serviceWorker' in navigator) {
    // Can be implemented later for offline support
}

console.log('⚡ Chatbase Clone initialized');
