// Main entry point for Personal Agent frontend
// Handles app initialization and imports other modules

// Example: Initialize the application
import { loadConversations } from './conversations.js';
import { loadAvailableTools } from './chat.js';
import { loadDocuments } from './documents.js';

document.addEventListener('DOMContentLoaded', function() {
    loadConversations();
    loadAvailableTools();
    loadDocuments();
});

// ...other global state and initialization logic...
