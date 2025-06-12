import { apiCall } from './utils.js';

// Handles chat UI, sending/receiving messages, rendering chat
// ...existing code...

export async function loadAvailableTools() {
    try {
        const tools = await apiCall('/tools');
        const toolsInfo = document.getElementById('tools-info');
        toolsInfo.textContent = `Available tools: ${tools.map(t => t.name).join(', ')}`;
    } catch (error) {
        console.error('Failed to load tools:', error);
        document.getElementById('tools-info').textContent = 'Tools: calculator, current_time';
    }
}

// Load and render messages for a conversation
export async function loadConversation(conversationId) {
    window.currentConversationId = conversationId;
    // Re-render conversations to update highlight
    if (window.loadConversations) {
        window.loadConversations();
    }
    try {
        const messages = await apiCall(`/conversations/${conversationId}/messages`);
        renderChatMessages(messages);
    } catch (error) {
        console.error('Failed to load conversation messages:', error);
        renderChatMessages([]);
    }
}

// Send a message in the current conversation
export async function sendMessage() {
    const input = document.getElementById('message-input');
    const message = input.value.trim();
    if (!message || !window.currentConversationId) return;
    input.value = '';
    // Optimistically render user message
    appendChatMessage({ role: 'user', content: message, timestamp: new Date().toISOString() });
    // Show thinking indicator
    appendChatMessage({ role: 'assistant', content: '' }, true);
    try {
        const response = await apiCall('/chat', {
            method: 'POST',
            body: JSON.stringify({
                message,
                conversation_id: window.currentConversationId,
                selected_documents: Array.from(window.selectedDocuments || [])
            })
        });
        // Remove the thinking indicator (safely)
        const chatContainer = document.getElementById('chat-container');
        if (chatContainer) {
            const indicators = chatContainer.querySelectorAll('.thinking-indicator');
            indicators.forEach(indicator => {
                const bubble = indicator.closest('.chat-bubble');
                if (bubble) bubble.remove();
            });
        }
        // Render assistant response with tools/actions if present
        appendChatMessage({
            role: 'assistant',
            content: response.response,
            agent_actions: response.agent_actions || [],
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        // Remove the thinking indicator (safely)
        const chatContainer = document.getElementById('chat-container');
        if (chatContainer) {
            const indicators = chatContainer.querySelectorAll('.thinking-indicator');
            indicators.forEach(indicator => {
                const bubble = indicator.closest('.chat-bubble');
                if (bubble) bubble.remove();
            });
        }
        appendChatMessage({ role: 'assistant', content: '[Error: Failed to send message]' });
        console.error('Failed to send message:', error);
    }
}

// Render all messages in the chat UI, with chat bubbles and agent actions
function renderChatMessages(messages) {
    const chatContainer = document.getElementById('chat-container');
    if (!messages.length) {
        chatContainer.innerHTML = '<div class="empty-state">No messages yet.</div>';
        return;
    }
    chatContainer.innerHTML = messages.map(msg => `
        <div class="chat-bubble ${msg.role}">
            <div class="bubble-content">
                <span class="chat-content">${msg.content}</span>
                ${msg.agent_actions && msg.agent_actions.length ? renderAgentActions(msg.agent_actions) : ''}
            </div>
            <div class="bubble-meta">${msg.role === 'user' ? 'You' : 'Agent'} • ${window.formatDate ? window.formatDate(msg.timestamp) : ''}</div>
        </div>
    `).join('');
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Render agent actions (tools used)
function renderAgentActions(actions) {
    return `<div class="agent-actions">
        ${actions.map(a => `
            <div class="agent-action">
                <span class="tool-name">🔧 ${a.tool}</span>
                <span class="tool-input">Input: <code>${a.input}</code></span>
                <span class="tool-output">Output: <code>${a.output}</code></span>
            </div>
        `).join('')}
    </div>`;
}

// Append a single message to the chat UI, with optional thinking indicator
function appendChatMessage(msg, isThinking = false) {
    const chatContainer = document.getElementById('chat-container');
    const div = document.createElement('div');
    div.className = `chat-bubble ${msg.role}`;
    div.innerHTML = `
        <div class="bubble-content">
            <span class="chat-content">${msg.content}</span>
            ${msg.agent_actions && msg.agent_actions.length ? renderAgentActions(msg.agent_actions) : ''}
        </div>
        <div class="bubble-meta">${msg.role === 'user' ? 'You' : 'Agent'}${msg.timestamp ? ' • ' + (window.formatDate ? window.formatDate(msg.timestamp) : '') : ''}</div>
        ${isThinking ? '<div class="thinking-indicator">🤔 Thinking...</div>' : ''}
    `;
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Handle Enter key to send message
export function handleKeyPress(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        window.sendMessage();
    }
}
window.handleKeyPress = handleKeyPress;

// Attach to window for global access
window.loadConversation = loadConversation;
window.sendMessage = sendMessage;
