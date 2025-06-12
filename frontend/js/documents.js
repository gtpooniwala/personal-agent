import { apiCall } from './utils.js';

// Handles document upload, selection, deletion, and RAG controls
// ...functions will be moved here...

// Export and attach to window any functions referenced in HTML
export async function loadDocuments() {
    try {
        const response = await apiCall('/documents');
        const documents = response.documents || [];
        const listElement = document.getElementById('documents-list');
        if (documents.length === 0) {
            listElement.innerHTML = '<div style="color: #bdc3c7; font-style: italic; padding: 8px; text-align: center; font-size: 12px;">No documents uploaded</div>';
            updateRagStatus();
            return;
        }
        listElement.innerHTML = documents.map(doc => `
            <div class="document-item ${window.selectedDocuments && window.selectedDocuments.has(doc.id) ? 'selected' : ''}" data-doc-id="${doc.id}">
                <div style="display: flex; align-items: center; flex: 1;">
                    <input type="checkbox" 
                           class="document-checkbox" 
                           id="doc-${doc.id}" 
                           ${window.selectedDocuments && window.selectedDocuments.has(doc.id) ? 'checked' : ''}
                           onchange="toggleDocumentSelection('${doc.id}')">
                    <div class="document-info">
                        <div class="document-name" title="${doc.filename}">
                            📄 ${doc.filename.length > 20 ? doc.filename.substring(0, 17) + '...' : doc.filename}
                        </div>
                        <div class="document-meta">
                            ${formatFileSize(doc.file_size)} • ${formatDate(doc.uploaded_at)}
                        </div>
                        <div class="document-summary" style="color:#b2d7ff; font-size:11px; margin-top:2px;">
                            ${doc.summary ? doc.summary : 'No summary available.'}
                        </div>
                    </div>
                </div>
                <div class="document-actions">
                    <button class="doc-btn delete" onclick="deleteDocument('${doc.id}')" title="Delete document">
                        🗑️
                    </button>
                </div>
            </div>
        `).join('');
        updateRagStatus();
    } catch (error) {
        console.error('Failed to load documents:', error);
        document.getElementById('documents-list').innerHTML = 
            '<div style="color: #e74c3c; font-size: 12px; padding: 8px; text-align: center;">Failed to load documents</div>';
    }
}

export async function handleFileSelect(event) {
    const files = Array.from(event.target.files);
    await uploadFiles(files);
}

export async function handleFileDrop(event) {
    event.preventDefault();
    const uploadArea = event.currentTarget;
    uploadArea.classList.remove('dragover');
    const files = Array.from(event.dataTransfer.files).filter(file => file.type === 'application/pdf');
    if (files.length > 0) {
        await uploadFiles(files);
    }
}

export function handleDragOver(event) {
    event.preventDefault();
}

export function handleDragEnter(event) {
    event.preventDefault();
    event.currentTarget.classList.add('dragover');
}

export function handleDragLeave(event) {
    event.preventDefault();
    if (!event.currentTarget.contains(event.relatedTarget)) {
        event.currentTarget.classList.remove('dragover');
    }
}

async function uploadFiles(files) {
    const progressContainer = document.getElementById('upload-progress');
    const progressBar = document.getElementById('upload-progress-bar');
    progressContainer.style.display = 'block';
    progressBar.style.width = '0%';
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        if (file.type !== 'application/pdf') {
            alert(`${file.name} is not a PDF file and will be skipped.`);
            continue;
        }
        try {
            const formData = new FormData();
            formData.append('file', file);
            const response = await fetch('http://127.0.0.1:8000/api/v1/documents/upload', {
                method: 'POST',
                body: formData
            });
            if (!response.ok) {
                throw new Error(`Failed to upload ${file.name}`);
            }
            // Update progress
            const progress = ((i + 1) / files.length) * 100;
            progressBar.style.width = `${progress}%`;
        } catch (error) {
            console.error(`Failed to upload ${file.name}:`, error);
            alert(`Failed to upload ${file.name}. Please try again.`);
        }
    }
    setTimeout(() => {
        progressContainer.style.display = 'none';
        progressBar.style.width = '0%';
    }, 1000);
    await loadDocuments();
    document.getElementById('file-input').value = '';
}

export function toggleDocumentSelection(documentId) {
    if (!window.selectedDocuments) window.selectedDocuments = new Set();
    const checkbox = document.getElementById(`doc-${documentId}`);
    const documentItem = document.querySelector(`[data-doc-id="${documentId}"]`);
    if (checkbox.checked) {
        window.selectedDocuments.add(documentId);
        documentItem.classList.add('selected');
    } else {
        window.selectedDocuments.delete(documentId);
        documentItem.classList.remove('selected');
    }
    updateRagStatus();
}

export function updateRagStatus() {
    const ragEnabled = document.getElementById('rag-enabled').checked;
    const statusElement = document.getElementById('rag-status');
    const selectedCount = window.selectedDocuments ? window.selectedDocuments.size : 0;
    if (!ragEnabled) {
        statusElement.textContent = 'Document search disabled';
        statusElement.style.color = '#e74c3c';
    } else if (selectedCount === 0) {
        statusElement.textContent = 'Document search enabled • No files selected';
        statusElement.style.color = '#f39c12';
    } else {
        statusElement.textContent = `Document search enabled • ${selectedCount} file${selectedCount > 1 ? 's' : ''} selected`;
        statusElement.style.color = '#27ae60';
    }
}

export async function deleteDocument(documentId) {
    if (!confirm('Are you sure you want to delete this document?')) {
        return;
    }
    try {
        await apiCall(`/documents/${documentId}`, {
            method: 'DELETE'
        });
        if (window.selectedDocuments) window.selectedDocuments.delete(documentId);
        await loadDocuments();
        console.log('Document deleted successfully');
    } catch (error) {
        console.error('Failed to delete document:', error);
        alert('Failed to delete document. Please try again.');
    }
}

// Utility functions for formatting
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatDate(dateString) {
    if (!dateString) return 'Unknown time';
    let date;
    if (dateString.includes('Z') || dateString.includes('+')) {
        date = new Date(dateString);
    } else {
        date = new Date(dateString + 'Z');
    }
    if (isNaN(date.getTime())) return 'Invalid date';
    const now = new Date();
    const diff = now - date;
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    const weeks = Math.floor(days / 7);
    const months = Math.floor(days / 30);
    const years = Math.floor(days / 365);
    if (seconds < 30) return 'Just now';
    if (seconds < 60) return `${seconds}s ago`;
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days} day${days === 1 ? '' : 's'} ago`;
    if (weeks < 4) return `${weeks} week${weeks === 1 ? '' : 's'} ago`;
    if (months < 12) return `${months} month${months === 1 ? '' : 's'} ago`;
    if (years >= 1) return `${years} year${years === 1 ? '' : 's'} ago`;
    return date.toLocaleDateString();
}

window.handleFileSelect = handleFileSelect;
window.handleFileDrop = handleFileDrop;
window.handleDragOver = handleDragOver;
window.handleDragEnter = handleDragEnter;
window.handleDragLeave = handleDragLeave;
window.toggleDocumentSelection = toggleDocumentSelection;
window.updateRagStatus = updateRagStatus;
window.deleteDocument = deleteDocument;
