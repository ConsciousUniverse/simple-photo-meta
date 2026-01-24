/**
 * Simple Photo Meta - Main Application
 * Plain JavaScript - no framework dependencies
 */

// Debounce utility for real-time search
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Application State
const state = {
    currentFolder: null,
    images: [],
    selectedImage: null,
    page: 0,
    totalPages: 1,
    totalImages: 0,
    pageSize: 25,
    searchQuery: '',
    metadataType: 'iptc',
    tagType: '',
    currentTags: [],
    originalTags: [],
    hasUnsavedChanges: false,
    tagDefinitions: null,
    scanPollingInterval: null,
    previewRotation: 0,  // Current rotation angle (0, 90, 180, 270)
};

// DOM Elements cache
let elements = {};

// Initialize application
document.addEventListener('DOMContentLoaded', async function() {
    console.log('Simple Photo Meta initializing...');
    
    // Cache DOM elements
    cacheElements();
    
    // Load tag definitions
    await loadTagDefinitions();
    
    // Load preferences
    await loadPreferences();
    
    // Set up event listeners
    setupEventListeners();
    
    // Set up resizable panels
    setupResizeHandles();
    
    console.log('Simple Photo Meta ready.');
});

function cacheElements() {
    elements = {
        btnOpenFolder: document.getElementById('btn-open-folder'),
        btnPreferences: document.getElementById('btn-preferences'),
        btnAbout: document.getElementById('btn-about'),
        currentFolder: document.getElementById('current-folder'),
        imageCount: document.getElementById('image-count'),
        searchInput: document.getElementById('search-input'),
        btnSearch: document.getElementById('btn-search'),
        btnClearSearch: document.getElementById('btn-clear-search'),
        thumbnailGrid: document.getElementById('thumbnail-grid'),
        btnPrevPage: document.getElementById('btn-prev-page'),
        btnNextPage: document.getElementById('btn-next-page'),
        pageInfo: document.getElementById('page-info'),
        scanProgress: document.getElementById('scan-progress'),
        progressFill: document.getElementById('progress-fill'),
        scanStatus: document.getElementById('scan-status'),
        rescanContainer: document.getElementById('rescan-container'),
        btnRescan: document.getElementById('btn-rescan'),
        imagePreview: document.getElementById('image-preview'),
        imageInfo: document.getElementById('image-info'),
        imageFilename: document.getElementById('image-filename'),
        metadataType: document.getElementById('metadata-type'),
        tagType: document.getElementById('tag-type'),
        tagInput: document.getElementById('tag-input'),
        btnAddTag: document.getElementById('btn-add-tag'),
        tagSuggestions: document.getElementById('tag-suggestions'),
        tagList: document.getElementById('tag-list'),
        saveStatus: document.getElementById('save-status'),
        preferencesDialog: document.getElementById('preferences-dialog'),
        aboutDialog: document.getElementById('about-dialog'),
        prefFontSize: document.getElementById('pref-font-size'),
        btnSavePrefs: document.getElementById('btn-save-prefs'),
        btnClosePrefs: document.getElementById('btn-close-prefs'),
        btnCloseAbout: document.getElementById('btn-close-about'),
        // Folder browser dialog
        folderDialog: document.getElementById('folder-dialog'),
        folderList: document.getElementById('folder-list'),
        folderCurrentPath: document.getElementById('folder-current-path'),
        folderImageCount: document.getElementById('folder-image-count'),
        btnFolderUp: document.getElementById('btn-folder-up'),
        btnFolderHome: document.getElementById('btn-folder-home'),
        btnSelectFolder: document.getElementById('btn-select-folder'),
        btnCancelFolder: document.getElementById('btn-cancel-folder'),
        // Resize handles
        panelLeft: document.getElementById('panel-left'),
        panelRight: document.getElementById('panel-right'),
        previewContainer: document.getElementById('preview-container'),
        resizeHandleH: document.getElementById('resize-handle-h'),
        resizeHandleV: document.getElementById('resize-handle-v'),
        // Preview controls
        previewControls: document.getElementById('preview-controls'),
        btnRotateLeft: document.getElementById('btn-rotate-left'),
        btnRotateRight: document.getElementById('btn-rotate-right'),
    };
}

function setupEventListeners() {
    // Header buttons
    elements.btnOpenFolder.addEventListener('click', handleOpenFolder);
    elements.btnPreferences.addEventListener('click', () => elements.preferencesDialog.showModal());
    elements.btnAbout.addEventListener('click', () => elements.aboutDialog.showModal());
    
    // Search - real-time with debounce (300ms delay)
    const debouncedSearch = debounce(handleSearch, 300);
    elements.searchInput.addEventListener('input', debouncedSearch);
    elements.btnSearch.addEventListener('click', handleSearch);
    elements.btnClearSearch.addEventListener('click', handleClearSearch);
    
    // Pagination
    elements.btnPrevPage.addEventListener('click', () => changePage(-1));
    elements.btnNextPage.addEventListener('click', () => changePage(1));
    
    // Metadata type selector
    elements.metadataType.addEventListener('change', handleMetadataTypeChange);
    elements.tagType.addEventListener('change', handleTagTypeChange);
    
    // Tag input
    elements.tagInput.addEventListener('input', handleTagInputChange);
    elements.tagInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleAddTag();
    });
    elements.btnAddTag.addEventListener('click', handleAddTag);
    
    // Dialog buttons
    elements.btnSavePrefs.addEventListener('click', handleSavePreferences);
    elements.btnClosePrefs.addEventListener('click', () => elements.preferencesDialog.close());
    elements.btnCloseAbout.addEventListener('click', () => elements.aboutDialog.close());
    
    // Folder browser dialog
    elements.btnFolderUp.addEventListener('click', handleFolderUp);
    elements.btnFolderHome.addEventListener('click', handleFolderHome);
    elements.btnSelectFolder.addEventListener('click', handleSelectFolder);
    elements.btnCancelFolder.addEventListener('click', () => elements.folderDialog.close());
    
    // Preview controls - rotation and click to open
    elements.btnRotateLeft.addEventListener('click', (e) => {
        e.stopPropagation();
        handleRotateLeft();
    });
    elements.btnRotateRight.addEventListener('click', (e) => {
        e.stopPropagation();
        handleRotateRight();
    });
    elements.imagePreview.addEventListener('click', handlePreviewClick);
    
    // Rescan button
    elements.btnRescan.addEventListener('click', handleRescan);
    
    // Close suggestions when clicking outside
    document.addEventListener('click', (e) => {
        if (!elements.tagSuggestions.contains(e.target) && e.target !== elements.tagInput) {
            elements.tagSuggestions.classList.add('hidden');
        }
    });
}

async function loadTagDefinitions() {
    const result = await getMetadataDefinitions();
    if (result.data) {
        state.tagDefinitions = result.data;
        updateTagTypeSelector();
    }
}

async function loadPreferences() {
    const result = await getPreference('font_size');
    if (result.data && result.data.value) {
        const fontSize = result.data.value;
        document.documentElement.style.setProperty('--font-size-base', `${fontSize}px`);
        elements.prefFontSize.value = fontSize;
    }
}

function updateTagTypeSelector() {
    if (!state.tagDefinitions) return;
    
    const definitions = state.metadataType === 'iptc' 
        ? state.tagDefinitions.iptc 
        : state.tagDefinitions.exif;
    
    elements.tagType.innerHTML = '<option value="">Select a field...</option>';
    
    for (const def of definitions) {
        const option = document.createElement('option');
        option.value = def.tag;
        option.textContent = def.name;
        option.title = def.description;
        elements.tagType.appendChild(option);
    }
}

// Folder operations
// Folder Browser State
const folderState = {
    currentPath: '',
    parentPath: '',
};

async function handleOpenFolder() {
    // Show folder browser dialog instead of prompt
    elements.folderDialog.showModal();
    await loadFolderBrowser('');  // Start at home directory
}

async function loadFolderBrowser(path) {
    elements.folderList.innerHTML = '<p class="loading">Loading...</p>';
    
    const result = await browseDirectory(path);
    
    if (result.error) {
        elements.folderList.innerHTML = `<p class="empty">Error: ${result.error}</p>`;
        return;
    }
    
    if (result.data) {
        folderState.currentPath = result.data.current;
        folderState.parentPath = result.data.parent;
        
        elements.folderCurrentPath.textContent = result.data.current;
        elements.folderImageCount.textContent = result.data.image_count > 0 
            ? `${result.data.image_count} image(s) in this folder`
            : 'No images in this folder';
        
        // Disable/enable up button
        elements.btnFolderUp.disabled = !result.data.parent;
        
        renderFolderList(result.data.directories);
    }
}

function renderFolderList(directories) {
    if (directories.length === 0) {
        elements.folderList.innerHTML = '<p class="empty">No subfolders</p>';
        return;
    }
    
    elements.folderList.innerHTML = '';
    
    for (const dir of directories) {
        const item = document.createElement('div');
        item.className = 'folder-item';
        item.innerHTML = `
            <span class="folder-icon">📁</span>
            <span class="folder-name">${escapeHtml(dir.name)}</span>
        `;
        item.addEventListener('click', () => loadFolderBrowser(dir.path));
        elements.folderList.appendChild(item);
    }
}

function handleFolderUp() {
    if (folderState.parentPath) {
        loadFolderBrowser(folderState.parentPath);
    }
}

function handleFolderHome() {
    loadFolderBrowser('');  // Empty path = home directory
}

async function handleSelectFolder() {
    if (!folderState.currentPath) return;
    
    elements.folderDialog.close();
    await openFolder(folderState.currentPath);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function openFolder(path) {
    elements.currentFolder.textContent = 'Loading...';
    elements.rescanContainer.classList.add('hidden');
    
    const result = await openDirectory(path);
    
    if (result.error) {
        alert(`Error: ${result.error}`);
        elements.currentFolder.textContent = 'No folder selected';
        return;
    }
    
    if (result.data) {
        state.currentFolder = result.data.folder;
        state.images = result.data.images;
        state.page = result.data.page;
        state.totalPages = result.data.total_pages;
        state.totalImages = result.data.total_images;
        
        updateFolderDisplay();
        renderThumbnails();
        
        // Start scanning for metadata indexing (incremental - only new images)
        startScanProcess(path, false);
    }
}

function updateFolderDisplay() {
    elements.currentFolder.textContent = state.currentFolder || 'No folder selected';
    elements.imageCount.textContent = `${state.totalImages} images`;
    updatePaginationControls();
}

function updatePaginationControls() {
    elements.pageInfo.textContent = `Page ${state.page + 1} of ${state.totalPages}`;
    elements.btnPrevPage.disabled = state.page === 0;
    elements.btnNextPage.disabled = state.page >= state.totalPages - 1;
}

async function changePage(delta) {
    const newPage = state.page + delta;
    if (newPage < 0 || newPage >= state.totalPages) return;
    
    state.page = newPage;
    await loadCurrentPage();
}

async function loadCurrentPage() {
    if (!state.currentFolder) return;
    
    // Always read the current field dropdown value for filtering
    // When tag_type is selected:
    // - With search: filter by search term AND tag_type
    // - Without search: show images WITHOUT any tags of this type (untagged)
    const currentTagType = elements.tagType ? elements.tagType.value : '';
    
    const result = await getImages(
        state.currentFolder,
        state.page,
        state.pageSize,
        state.searchQuery || '',
        currentTagType
    );
    
    if (result.data) {
        state.images = result.data.images;
        state.totalImages = result.data.total_images;
        state.totalPages = result.data.total_pages;
        updatePaginationControls();
        renderThumbnails();
    }
}

// Scanning
async function startScanProcess(folder, force = false) {
    const result = await startScan(folder, force);
    
    if (result.data && result.data.started) {
        elements.scanProgress.classList.remove('hidden');
        elements.rescanContainer.classList.add('hidden');
        pollScanStatus();
    } else if (result.data && !result.data.started && result.data.status.total === 0) {
        // No new images to scan - show rescan button immediately
        elements.rescanContainer.classList.remove('hidden');
    }
}

async function handleRescan() {
    if (!state.currentFolder) return;
    await startScanProcess(state.currentFolder, true);
}

function pollScanStatus() {
    if (state.scanPollingInterval) {
        clearInterval(state.scanPollingInterval);
    }
    
    state.scanPollingInterval = setInterval(async () => {
        const result = await getScanStatus();
        
        if (result.data) {
            const { running, processed, total } = result.data;
            
            if (total > 0) {
                const percent = (processed / total) * 100;
                elements.progressFill.style.width = `${percent}%`;
                elements.scanStatus.textContent = `Scanning: ${processed} of ${total} images`;
            }
            
            if (!running) {
                clearInterval(state.scanPollingInterval);
                state.scanPollingInterval = null;
                elements.scanProgress.classList.add('hidden');
                elements.rescanContainer.classList.remove('hidden');
                
                // Refresh the current page
                await loadCurrentPage();
            }
        }
    }, 500);
}

// Thumbnails
function renderThumbnails() {
    if (state.images.length === 0) {
        elements.thumbnailGrid.innerHTML = '<p class="empty-state">No images found</p>';
        return;
    }
    
    elements.thumbnailGrid.innerHTML = '';
    
    for (const imagePath of state.images) {
        const item = createThumbnailElement(imagePath);
        elements.thumbnailGrid.appendChild(item);
    }
}

function createThumbnailElement(imagePath) {
    const item = document.createElement('div');
    item.className = 'thumbnail-item';
    if (imagePath === state.selectedImage) {
        item.classList.add('selected');
    }
    
    const img = document.createElement('img');
    img.src = getThumbnailUrl(imagePath);
    img.alt = getFilename(imagePath);
    img.loading = 'lazy';
    
    const name = document.createElement('span');
    name.className = 'thumbnail-name';
    name.textContent = getFilename(imagePath);
    
    item.appendChild(img);
    item.appendChild(name);
    
    item.addEventListener('click', () => selectImage(imagePath));
    
    return item;
}

function getFilename(path) {
    return path.split('/').pop() || path;
}

// Image selection
async function selectImage(imagePath) {
    // Check for unsaved changes
    if (state.hasUnsavedChanges) {
        const save = confirm('You have unsaved changes. Do you want to save them?');
        if (save) {
            await handleSave();
        }
    }
    
    state.selectedImage = imagePath;
    state.hasUnsavedChanges = false;
    
    // Update thumbnail selection
    document.querySelectorAll('.thumbnail-item').forEach(el => el.classList.remove('selected'));
    const items = document.querySelectorAll('.thumbnail-item');
    for (const item of items) {
        const img = item.querySelector('img');
        if (img && img.src === getThumbnailUrl(imagePath)) {
            item.classList.add('selected');
            break;
        }
    }
    
    // Load preview
    loadPreview(imagePath);
    
    // Load metadata
    await loadImageMetadata(imagePath);
    
    // Enable tag input
    elements.tagInput.disabled = !state.tagType;
    elements.btnAddTag.disabled = !state.tagType;
}

function loadPreview(imagePath) {
    // Clear existing content but keep the controls
    const existingImg = elements.imagePreview.querySelector('img');
    if (existingImg) {
        existingImg.remove();
    }
    const existingEmpty = elements.imagePreview.querySelector('.empty-state');
    if (existingEmpty) {
        existingEmpty.remove();
    }
    
    // Reset rotation for new image
    state.previewRotation = 0;
    
    const img = document.createElement('img');
    img.src = getPreviewUrl(imagePath, 1024);
    img.alt = getFilename(imagePath);
    img.style.transform = 'rotate(0deg)';
    
    // Insert before the controls
    elements.imagePreview.insertBefore(img, elements.previewControls);
    
    // Show the controls
    elements.previewControls.style.display = 'flex';
    
    elements.imageFilename.textContent = getFilename(imagePath);
    elements.imageInfo.classList.remove('hidden');
}

// Preview rotation handlers
function handleRotateLeft() {
    if (!state.selectedImage) return;
    state.previewRotation = (state.previewRotation - 90 + 360) % 360;
    applyRotation();
}

function handleRotateRight() {
    if (!state.selectedImage) return;
    state.previewRotation = (state.previewRotation + 90) % 360;
    applyRotation();
}

function applyRotation() {
    const img = elements.imagePreview.querySelector('img');
    if (img) {
        img.style.transform = `rotate(${state.previewRotation}deg)`;
    }
}

// Handle click on preview to open in system viewer
async function handlePreviewClick(e) {
    // Ignore clicks on the control buttons
    if (e.target.closest('.preview-controls')) {
        return;
    }
    
    if (!state.selectedImage) return;
    
    const result = await openInSystemViewer(state.selectedImage);
    if (result.error) {
        console.error('Failed to open image:', result.error);
    }
}

// Metadata operations
async function loadImageMetadata(imagePath) {
    if (!state.tagType) {
        renderTagList([]);
        return;
    }
    
    const result = await getMetadata(imagePath, state.tagType, state.metadataType);
    
    if (result.data && result.data.values) {
        state.currentTags = [...result.data.values];
        state.originalTags = [...result.data.values];
        renderTagList(state.currentTags);
    } else {
        state.currentTags = [];
        state.originalTags = [];
        renderTagList([]);
    }
    
    updateSaveState();
}

async function handleMetadataTypeChange() {
    state.metadataType = elements.metadataType.value;
    state.tagType = '';
    updateTagTypeSelector();
    elements.tagType.value = '';
    
    state.currentTags = [];
    renderTagList([]);
    
    elements.tagInput.disabled = true;
    elements.btnAddTag.disabled = true;
    
    // Always refresh thumbnail grid when type changes (to filter untagged)
    if (state.currentFolder) {
        state.page = 0;
        await loadCurrentPage();
    }
}

async function handleTagTypeChange() {
    state.tagType = elements.tagType.value;
    
    if (state.selectedImage && state.tagType) {
        await loadImageMetadata(state.selectedImage);
        elements.tagInput.disabled = false;
        elements.btnAddTag.disabled = false;
    } else {
        state.currentTags = [];
        renderTagList([]);
        elements.tagInput.disabled = true;
        elements.btnAddTag.disabled = true;
    }
    
    // Always refresh thumbnail grid when field changes (to filter untagged)
    if (state.currentFolder) {
        state.page = 0;
        await loadCurrentPage();
    }
}

// Tag management
function renderTagList(tags) {
    if (tags.length === 0) {
        elements.tagList.innerHTML = '<p class="empty-state">No tags</p>';
        return;
    }
    
    elements.tagList.innerHTML = '';
    
    for (const tag of tags) {
        const item = createTagElement(tag);
        elements.tagList.appendChild(item);
    }
}

function createTagElement(tag) {
    const item = document.createElement('div');
    item.className = 'tag-item';
    
    const text = document.createElement('span');
    text.textContent = tag;
    
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'tag-delete';
    deleteBtn.textContent = '×';
    deleteBtn.addEventListener('click', () => removeTag(tag));
    
    item.appendChild(text);
    item.appendChild(deleteBtn);
    
    return item;
}

async function removeTag(tag) {
    state.currentTags = state.currentTags.filter(t => t !== tag);
    renderTagList(state.currentTags);
    
    // Auto-save after removing tag
    await saveTagsImmediately();
}

async function handleAddTag() {
    const value = elements.tagInput.value.trim();
    if (!value) return;
    
    // Check if already exists
    if (state.currentTags.includes(value)) {
        elements.tagInput.value = '';
        return;
    }
    
    state.currentTags.push(value);
    renderTagList(state.currentTags);
    elements.tagInput.value = '';
    elements.tagSuggestions.classList.add('hidden');
    
    // Auto-save after adding tag
    await saveTagsImmediately();
}

// Autocomplete
let suggestionTimeout = null;

async function handleTagInputChange() {
    const query = elements.tagInput.value.trim();
    
    if (suggestionTimeout) {
        clearTimeout(suggestionTimeout);
    }
    
    if (query.length < 2) {
        elements.tagSuggestions.classList.add('hidden');
        return;
    }
    
    suggestionTimeout = setTimeout(async () => {
        const result = await searchTags(query, state.tagType, 10);
        
        if (result.data && result.data.tags && result.data.tags.length > 0) {
            renderSuggestions(result.data.tags);
        } else {
            elements.tagSuggestions.classList.add('hidden');
        }
    }, 200);
}

function renderSuggestions(tags) {
    elements.tagSuggestions.innerHTML = '';
    
    for (const tag of tags) {
        const item = document.createElement('div');
        item.className = 'tag-suggestion-item';
        item.textContent = tag;
        item.addEventListener('click', () => {
            elements.tagInput.value = tag;
            elements.tagSuggestions.classList.add('hidden');
            handleAddTag();
        });
        elements.tagSuggestions.appendChild(item);
    }
    
    elements.tagSuggestions.classList.remove('hidden');
}

// Save
function updateSaveState() {
    const sortedCurrent = [...state.currentTags].sort();
    const sortedOriginal = [...state.originalTags].sort();
    const tagsChanged = JSON.stringify(sortedCurrent) !== JSON.stringify(sortedOriginal);
    state.hasUnsavedChanges = tagsChanged;
}

async function saveTagsImmediately() {
    if (!state.selectedImage || !state.tagType) return;
    
    elements.saveStatus.textContent = 'Saving...';
    
    const result = await updateMetadata(
        state.selectedImage,
        state.tagType,
        state.metadataType,
        state.currentTags
    );
    
    if (result.data && result.data.success) {
        state.originalTags = [...state.currentTags];
        state.hasUnsavedChanges = false;
        elements.saveStatus.textContent = 'Saved!';
        setTimeout(() => {
            elements.saveStatus.textContent = '';
        }, 1500);
    } else {
        elements.saveStatus.textContent = `Error: ${result.error || 'Failed to save'}`;
    }
}

async function handleSave() {
    if (!state.selectedImage || !state.tagType) return;
    
    elements.saveStatus.textContent = 'Saving...';
    
    const result = await updateMetadata(
        state.selectedImage,
        state.tagType,
        state.metadataType,
        state.currentTags
    );
    
    if (result.data && result.data.success) {
        state.originalTags = [...state.currentTags];
        state.hasUnsavedChanges = false;
        elements.saveStatus.textContent = 'Saved!';
        setTimeout(() => {
            elements.saveStatus.textContent = '';
        }, 2000);
    } else {
        elements.saveStatus.textContent = `Error: ${result.error || 'Failed to save'}`;
    }
}

// Search
async function handleSearch() {
    state.searchQuery = elements.searchInput.value.trim();
    state.page = 0;
    await loadCurrentPage();
}

async function handleClearSearch() {
    state.searchQuery = '';
    elements.searchInput.value = '';
    state.page = 0;
    await loadCurrentPage();
}

// Preferences
async function handleSavePreferences() {
    const fontSize = elements.prefFontSize.value;
    
    await setPreference('font_size', fontSize);
    
    document.documentElement.style.setProperty('--font-size-base', `${fontSize}px`);
    
    elements.preferencesDialog.close();
}

// Panel Resizing
function setupResizeHandles() {
    // Horizontal resize (between left and right panels)
    if (elements.resizeHandleH) {
        let isResizingH = false;
        let startX = 0;
        let startWidthRight = 0;
        
        elements.resizeHandleH.addEventListener('mousedown', (e) => {
            isResizingH = true;
            startX = e.clientX;
            startWidthRight = elements.panelRight.offsetWidth;
            document.body.classList.add('resizing');
            elements.resizeHandleH.classList.add('active');
            e.preventDefault();
        });
        
        document.addEventListener('mousemove', (e) => {
            if (!isResizingH) return;
            
            const deltaX = startX - e.clientX;
            const newWidth = Math.max(300, Math.min(startWidthRight + deltaX, window.innerWidth - 400));
            elements.panelRight.style.width = `${newWidth}px`;
            elements.panelRight.style.flex = 'none';
        });
        
        document.addEventListener('mouseup', () => {
            if (isResizingH) {
                isResizingH = false;
                document.body.classList.remove('resizing');
                elements.resizeHandleH.classList.remove('active');
                saveLayoutPreferences();
            }
        });
    }
    
    // Vertical resize (between preview and metadata editor)
    if (elements.resizeHandleV) {
        let isResizingV = false;
        let startY = 0;
        let startHeightPreview = 0;
        
        elements.resizeHandleV.addEventListener('mousedown', (e) => {
            isResizingV = true;
            startY = e.clientY;
            startHeightPreview = elements.previewContainer.offsetHeight;
            document.body.classList.add('resizing-v');
            elements.resizeHandleV.classList.add('active');
            e.preventDefault();
        });
        
        document.addEventListener('mousemove', (e) => {
            if (!isResizingV) return;
            
            const deltaY = e.clientY - startY;
            const panelHeight = elements.panelRight.offsetHeight;
            const newHeight = Math.max(150, Math.min(startHeightPreview + deltaY, panelHeight - 200));
            elements.previewContainer.style.height = `${newHeight}px`;
            elements.previewContainer.style.flex = 'none';
        });
        
        document.addEventListener('mouseup', () => {
            if (isResizingV) {
                isResizingV = false;
                document.body.classList.remove('resizing-v');
                elements.resizeHandleV.classList.remove('active');
                saveLayoutPreferences();
            }
        });
    }
    
    // Load saved layout preferences
    loadLayoutPreferences();
}

async function saveLayoutPreferences() {
    const layout = {
        rightPanelWidth: elements.panelRight.style.width || null,
        previewHeight: elements.previewContainer.style.height || null,
    };
    await setPreference('layout', JSON.stringify(layout));
}

async function loadLayoutPreferences() {
    const result = await getPreference('layout');
    if (result.data && result.data.value) {
        try {
            const layout = JSON.parse(result.data.value);
            if (layout.rightPanelWidth) {
                elements.panelRight.style.width = layout.rightPanelWidth;
                elements.panelRight.style.flex = 'none';
            }
            if (layout.previewHeight) {
                elements.previewContainer.style.height = layout.previewHeight;
                elements.previewContainer.style.flex = 'none';
            }
        } catch (e) {
            console.warn('Failed to parse layout preferences:', e);
        }
    }
}
