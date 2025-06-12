import { apiCall, formatDate } from './utils.js';
import { loadConversation } from './chat.js';

// Handles conversation sidebar logic: load, create, switch conversations
// ...functions will be moved here...

// Exported for use in main.js and for global access
export async function loadConversations() {
    try {
        const conversations = await apiCall('/conversations');
        const listElement = document.getElementById('conversations-list');
        if (conversations.length === 0) {
            listElement.innerHTML = '<div style="color: #bdc3c7; font-style: italic;">No conversations yet</div>';
            return;
        }
        // Only set currentConversationId if not set at all (first load)
        if (typeof window.currentConversationId === 'undefined' || window.currentConversationId === null) {
            if (conversations.length > 0) {
                window.currentConversationId = conversations[0].id;
            }
        }
        listElement.innerHTML = conversations.map(conv => `
            <div class="conversation-item${window.currentConversationId === conv.id ? ' active' : ''}" onclick="window.loadConversation && window.loadConversation('${conv.id}')">
                <div class="conversation-title">${conv.title}</div>
                <div class="conversation-date">${formatDate(conv.updated_at)}</div>
            </div>
        `).join('');
        // Remove auto-select logic after rendering (fixes highlight bug)
    } catch (error) {
        console.error('Failed to load conversations:', error);
    }
}

export async function createNewConversation() {
    try {
        const conversation = await apiCall('/conversations', {
            method: 'POST',
            body: JSON.stringify({})
        });
        await loadConversations();
        window.loadConversation && window.loadConversation(conversation.id);
    } catch (error) {
        console.error('Failed to create conversation:', error);
        alert('Failed to create new conversation');
    }
}

// Make createNewConversation and loadConversation available globally for HTML onclick
window.createNewConversation = createNewConversation;
window.loadConversation = loadConversation;
