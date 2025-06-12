// Utility functions: date formatting, file size, etc.
// ...functions will be moved here...

export const API_BASE = 'http://127.0.0.1:8000/api/v1';

export async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

// Date formatting utility (shared by all modules)
export function formatDate(dateString) {
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
