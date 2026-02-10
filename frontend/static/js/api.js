/**
 * API Client for Simple Photo Meta
 * Plain JavaScript - no dependencies
 */

const API_BASE = '/api';

/**
 * Make an API request
 * @param {string} endpoint 
 * @param {RequestInit} options 
 * @returns {Promise<{data?: any, error?: string}>}
 */
async function apiRequest(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            ...options,
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            return { error: errorData.error || `HTTP ${response.status}` };
        }

        const data = await response.json();
        return { data };
    } catch (err) {
        return { error: err.message || 'Network error' };
    }
}

// Directory operations
async function browseDirectory(path = '') {
    const params = new URLSearchParams();
    if (path) params.set('path', path);
    const query = params.toString();
    return apiRequest(`/directories/browse${query ? `?${query}` : ''}`);
}

async function openDirectory(path) {
    return apiRequest('/directories/open', {
        method: 'POST',
        body: JSON.stringify({ path }),
    });
}

async function startScan(path, force = false) {
    return apiRequest('/directories/scan', {
        method: 'POST',
        body: JSON.stringify({ path, force }),
    });
}

async function getScanStatus() {
    return apiRequest('/directories/scan/status');
}

async function cancelScan() {
    return apiRequest('/directories/scan', { method: 'DELETE' });
}

// Image operations
async function getImages(folder, page = 0, pageSize = 25, search = '', tagType = '') {
    const params = new URLSearchParams({
        folder,
        page: String(page),
        page_size: String(pageSize),
    });
    if (search) params.set('search', search);
    if (tagType) params.set('tag_type', tagType);

    return apiRequest(`/images?${params}`);
}

function getThumbnailUrl(imagePath) {
    return `${API_BASE}/images/thumbnail?path=${encodeURIComponent(imagePath)}`;
}

function getPreviewUrl(imagePath, edge) {
    let url = `${API_BASE}/images/preview?path=${encodeURIComponent(imagePath)}`;
    if (edge) url += `&edge=${edge}`;
    return url;
}

async function openInSystemViewer(imagePath) {
    return apiRequest('/images/open-in-viewer', {
        method: 'POST',
        body: JSON.stringify({ path: imagePath }),
    });
}

// Metadata operations
async function getMetadata(path, tagType, metadataType) {
    const params = new URLSearchParams({ path });
    if (tagType) params.set('tag_type', tagType);
    if (metadataType) params.set('metadata_type', metadataType);

    return apiRequest(`/metadata?${params}`);
}

async function updateMetadata(path, tagType, metadataType, values) {
    return apiRequest('/metadata', {
        method: 'PUT',
        body: JSON.stringify({
            path,
            tag_type: tagType,
            metadata_type: metadataType,
            values,
        }),
    });
}

async function getMetadataDefinitions() {
    return apiRequest('/metadata/definitions');
}

// Tag operations
async function getTags(tagType) {
    const params = new URLSearchParams();
    if (tagType) params.set('tag_type', tagType);
    const query = params.toString();
    return apiRequest(`/tags${query ? `?${query}` : ''}`);
}

async function searchTags(query, tagType, limit = 20) {
    const params = new URLSearchParams({
        q: query,
        limit: String(limit),
    });
    if (tagType) params.set('tag_type', tagType);

    return apiRequest(`/tags/search?${params}`);
}

// Preferences
async function getPreferences() {
    return apiRequest('/preferences');
}

async function getPreference(key) {
    return apiRequest(`/preferences/${key}`);
}

async function setPreference(key, value) {
    return apiRequest(`/preferences/${key}`, {
        method: 'PUT',
        body: JSON.stringify({ value }),
    });
}

// Image overlay info
async function getImageOverlayInfo(path) {
    const params = new URLSearchParams({ path });
    return apiRequest(`/images/overlay-info?${params}`);
}
