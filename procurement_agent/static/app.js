// Procurement Agent Chat Application

class ProcurementChat {
    constructor() {
        this.sessionId = this.generateSessionId();
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.messageHistory = new Map(); // Track message pairs (user + assistant)

        this.initializeElements();
        this.attachEventListeners();
        this.showWelcomeMessage();  // Show welcome message on initial load
        this.connectWebSocket();
    }

    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    initializeElements() {
        this.messagesContainer = document.getElementById('messages');
        this.messageInput = document.getElementById('messageInput');
        this.chatForm = document.getElementById('chatForm');
        this.sendBtn = document.getElementById('sendBtn');
        this.clearBtn = document.getElementById('clearBtn');
        this.sessionsBtn = document.getElementById('sessionsBtn');
        this.typingIndicator = document.getElementById('typingIndicator');
        this.sessionsModal = document.getElementById('sessionsModal');
        this.closeModalBtn = document.getElementById('closeModal');
        this.sessionsList = document.getElementById('sessionsList');
        this.newSessionBtn = document.getElementById('newSessionBtn');
        this.technicalModal = document.getElementById('technicalModal');
        this.closeTechnicalModalBtn = document.getElementById('closeTechnicalModal');
    }

    attachEventListeners() {
        this.chatForm.addEventListener('submit', (e) => this.handleSubmit(e));
        this.clearBtn.addEventListener('click', () => this.clearChat());
        this.sessionsBtn.addEventListener('click', () => this.openSessionsModal());
        this.closeModalBtn.addEventListener('click', () => this.closeSessionsModal());
        this.newSessionBtn.addEventListener('click', () => this.createNewSession());
        this.closeTechnicalModalBtn.addEventListener('click', () => this.closeTechnicalModal());
        this.sessionsModal.addEventListener('click', (e) => {
            if (e.target === this.sessionsModal) {
                this.closeSessionsModal();
            }
        });
        this.technicalModal.addEventListener('click', (e) => {
            if (e.target === this.technicalModal) {
                this.closeTechnicalModal();
            }
        });
        this.messageInput.addEventListener('input', () => this.autoResizeTextarea());
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.chatForm.dispatchEvent(new Event('submit'));
            }
        });
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${this.sessionId}`;

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.reconnectAttempts = 0;
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            this.ws.onclose = () => {
                console.log('WebSocket closed');
                this.attemptReconnect();
            };
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
            console.log(`Reconnecting in ${delay}ms... (attempt ${this.reconnectAttempts})`);
            setTimeout(() => this.connectWebSocket(), delay);
        } else {
            this.showSystemMessage('Connection lost. Please refresh the page.');
        }
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'system':
                console.log('System message:', data.message);
                break;

            case 'status':
                if (data.status === 'typing') {
                    this.showTypingIndicator();
                }
                break;

            case 'message':
                this.hideTypingIndicator();

                const isError = data.metadata && data.metadata.success === false;
                const userMessageId = data.messageId;

                // Generate assistant message ID
                const assistantMessageId = 'resp_' + Date.now();

                // Add message with error flag and metadata (always detailed)
                this.addMessage(data.message, data.role, isError, assistantMessageId, data.metadata);

                // Track assistant response in history
                if (userMessageId && this.messageHistory.has(userMessageId)) {
                    this.messageHistory.get(userMessageId).assistantMessageId = assistantMessageId;
                }
                break;

            case 'error':
                this.hideTypingIndicator();
                this.showSystemMessage(`Error: ${data.message}`);
                break;
        }
    }

    handleSubmit(e) {
        e.preventDefault();

        const message = this.messageInput.value.trim();
        if (!message) return;

        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            this.showSystemMessage('Not connected. Please wait...');
            return;
        }

        // Remove welcome message on first user message
        this.removeWelcomeMessage();

        // Generate message ID for tracking
        const messageId = 'msg_' + Date.now();

        // Add user message to UI
        this.addMessage(message, 'user', false, false, messageId);

        // Send message
        this.sendMessage(message, messageId);

        // Clear input
        this.messageInput.value = '';
        this.autoResizeTextarea();
        this.messageInput.focus();
    }

    sendMessage(message, messageId) {
        // Store in history
        this.messageHistory.set(messageId, {
            userMessage: message,
            assistantMessageId: null
        });

        // Send via WebSocket (always uses detailed explanations)
        this.ws.send(JSON.stringify({
            message,
            messageId: messageId
        }));
    }

    removeAllResendButtons() {
        // Remove all existing resend buttons from previous messages
        const allResendButtons = document.querySelectorAll('.resend-btn');
        console.log(`Removing ${allResendButtons.length} existing resend buttons`);
        allResendButtons.forEach(btn => {
            btn.remove();
        });
    }

    handleResend(message, messageId) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            this.showSystemMessage('Not connected. Please wait...');
            return;
        }

        // Remove the old assistant response if exists
        const historyEntry = this.messageHistory.get(messageId);
        if (historyEntry && historyEntry.assistantMessageId) {
            const oldResponse = document.querySelector(`[data-message-id="${historyEntry.assistantMessageId}"]`);
            if (oldResponse) {
                oldResponse.remove();
            }
        }

        // Show typing indicator
        this.showTypingIndicator();

        // Resend the message
        this.sendMessage(message, messageId);
    }

    addMessage(content, role, isError = false, messageId = null, metadata = null) {
        // Remove resend buttons from ALL previous user messages first
        if (role === 'user') {
            this.removeAllResendButtons();
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;

        if (messageId) {
            messageDiv.dataset.messageId = messageId;
        }

        if (role === 'user') {
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            contentDiv.innerHTML = this.formatMessage(content);

            // Create wrapper that contains content and button
            const wrapper = document.createElement('div');
            wrapper.className = 'message-wrapper';

            // Add resend button (only this message will have it)
            const resendBtn = document.createElement('button');
            resendBtn.className = 'resend-btn';
            resendBtn.title = 'Resend message';
            resendBtn.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 10c-1.5-4.5-5.5-8-10.5-8C5.5 2 1.5 6 1.5 11s4 9 9 9c4 0 7.5-2.5 9-6" />
                    <polyline points="17 10 21 10 21 6" />
                </svg>
            `;
            resendBtn.onclick = () => this.handleResend(content, messageId);

            wrapper.appendChild(contentDiv);
            wrapper.appendChild(resendBtn);
            messageDiv.appendChild(wrapper);
        } else {
            // Assistant or system message
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';

            // Add error badge if applicable
            if (isError) {
                const badge = document.createElement('span');
                badge.className = 'error-badge';
                badge.textContent = 'Error';
                contentDiv.appendChild(badge);
            }

            // Format content
            const textDiv = document.createElement('div');
            textDiv.innerHTML = this.formatMessage(content);
            contentDiv.appendChild(textDiv);

            // Add technical details button for assistant messages
            if (role === 'assistant' && metadata && metadata.technical_details) {
                const techBtn = document.createElement('button');
                techBtn.className = 'tech-details-btn';
                techBtn.innerHTML = `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="16" x2="12" y2="12"/>
                        <line x1="12" y1="8" x2="12.01" y2="8"/>
                    </svg>
                    Technical Details
                `;
                techBtn.onclick = () => this.showTechnicalDetails(metadata.technical_details);
                contentDiv.appendChild(techBtn);
            }

            messageDiv.appendChild(contentDiv);
        }

        this.messagesContainer.appendChild(messageDiv);

        // Scroll to bottom
        this.scrollToBottom();

        return messageDiv;
    }

    formatMessage(text) {
        // Simple formatting (can be enhanced with a markdown parser)
        let formatted = text
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>');

        return formatted;
    }

    showSystemMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message system';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = `<p>${message}</p>`;

        messageDiv.appendChild(contentDiv);
        this.messagesContainer.appendChild(messageDiv);

        this.scrollToBottom();
    }

    showWelcomeMessage() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message system welcome-message';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = `
            <p>Welcome! I'm your Procurement Data Assistant.</p>
            <p>I can analyze and answer questions about California state purchase orders over $5,000 from 2012-2015.</p>
                        
             <p class="hint"><strong>Note:</strong> I only answer questions using the procurement database. I cannot provide general knowledge or advice.</p>
                    
        `;

        messageDiv.appendChild(contentDiv);
        this.messagesContainer.appendChild(messageDiv);

        this.scrollToBottom();
    }

    removeWelcomeMessage() {
        const welcomeMessage = this.messagesContainer.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.remove();
        }
    }

    showTypingIndicator() {
        this.typingIndicator.style.display = 'flex';
        this.scrollToBottom();
    }

    hideTypingIndicator() {
        this.typingIndicator.style.display = 'none';
    }

    scrollToBottom() {
        setTimeout(() => {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }, 100);
    }

    autoResizeTextarea() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = this.messageInput.scrollHeight + 'px';
    }

    async clearChat() {
        if (!confirm('Are you sure you want to clear this chat?')) {
            return;
        }

        try {
            // Clear UI
            this.messagesContainer.innerHTML = '';

            // Show welcome message
            this.showWelcomeMessage();

            // Clear backend session
            const response = await fetch(`/sessions/${this.sessionId}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                console.error('Failed to clear session on backend');
            }
        } catch (error) {
            console.error('Error clearing chat:', error);
            this.showSystemMessage('Failed to clear chat history.');
        }
    }

    async openSessionsModal() {
        this.sessionsModal.style.display = 'flex';
        await this.loadSessions();
    }

    closeSessionsModal() {
        this.sessionsModal.style.display = 'none';
    }

    async loadSessions() {
        try {
            this.sessionsList.innerHTML = '<p class="loading">Loading sessions...</p>';

            const response = await fetch('/sessions');
            const data = await response.json();

            if (data.sessions.length === 0) {
                this.sessionsList.innerHTML = '<p class="loading">No sessions found. Start chatting to create one!</p>';
                return;
            }

            this.sessionsList.innerHTML = '';

            data.sessions.forEach(session => {
                const sessionItem = document.createElement('div');
                sessionItem.className = 'session-item';
                if (session.session_id === this.sessionId) {
                    sessionItem.classList.add('active');
                }

                // Parse the ISO date string properly
                const lastActivity = new Date(session.last_activity);
                console.log('Session:', session.session_id);
                console.log('  Raw last_activity:', session.last_activity);
                console.log('  Parsed date:', lastActivity.toISOString());
                console.log('  Current time:', new Date().toISOString());
                console.log('  Diff in seconds:', Math.floor((new Date() - lastActivity) / 1000));
                const timeAgo = this.getTimeAgo(lastActivity);

                sessionItem.innerHTML = `
                    <div class="session-info">
                        <div class="session-id">Session ${session.session_id.split('_')[1]}</div>
                        <div class="session-meta">${session.message_count} messages • ${timeAgo}</div>
                        <div class="session-meta">${session.preview}</div>
                    </div>
                    <div class="session-actions">
                        <button class="session-delete" data-session="${session.session_id}">Delete</button>
                    </div>
                `;

                sessionItem.addEventListener('click', (e) => {
                    if (!e.target.classList.contains('session-delete')) {
                        this.loadSession(session.session_id);
                    }
                });

                const deleteBtn = sessionItem.querySelector('.session-delete');
                deleteBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.deleteSession(session.session_id);
                });

                this.sessionsList.appendChild(sessionItem);
            });
        } catch (error) {
            console.error('Error loading sessions:', error);
            this.sessionsList.innerHTML = '<p class="loading">Failed to load sessions.</p>';
        }
    }

    async loadSession(sessionId) {
        if (sessionId === this.sessionId) {
            this.closeSessionsModal();
            return;
        }

        try {
            // Close current WebSocket
            if (this.ws) {
                this.ws.close();
            }

            // Update session ID
            this.sessionId = sessionId;

            // Clear UI
            this.messagesContainer.innerHTML = '';

            // Load session history
            const response = await fetch(`/sessions/${sessionId}/history`);
            const data = await response.json();

            // If session is empty, show welcome message
            if (data.messages.length === 0) {
                this.showWelcomeMessage();
            } else {
                // Display messages
                data.messages.forEach(msg => {
                    this.addMessage(msg.content, msg.role, false, null);
                });
            }

            // Reconnect WebSocket
            this.connectWebSocket();

            // Close modal
            this.closeSessionsModal();
        } catch (error) {
            console.error('Error loading session:', error);
            this.showSystemMessage('Failed to load session.');
        }
    }

    async deleteSession(sessionId) {
        if (!confirm('Are you sure you want to delete this session?')) {
            return;
        }

        try {
            const response = await fetch(`/sessions/${sessionId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                if (sessionId === this.sessionId) {
                    // If deleting current session, create new one
                    this.createNewSession();
                } else {
                    // Reload sessions list
                    await this.loadSessions();
                }
            }
        } catch (error) {
            console.error('Error deleting session:', error);
            this.showSystemMessage('Failed to delete session.');
        }
    }

    createNewSession() {
        // Close current WebSocket
        if (this.ws) {
            this.ws.close();
        }

        // Generate new session ID
        this.sessionId = this.generateSessionId();

        // Clear UI
        this.messagesContainer.innerHTML = '';

        // Show welcome message
        this.showWelcomeMessage();

        // Clear message history
        this.messageHistory.clear();

        // Reconnect WebSocket
        this.connectWebSocket();

        // Close modal
        this.closeSessionsModal();
    }

    getTimeAgo(date) {
        const seconds = Math.floor((new Date() - date) / 1000);

        if (seconds < 60) return 'Just now';
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
        if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;

        return date.toLocaleDateString();
    }

    showTechnicalDetails(technicalDetails) {
        // Display query
        const queryDisplay = document.getElementById('queryDisplay');
        queryDisplay.textContent = JSON.stringify(technicalDetails.query, null, 2);

        // Display result count
        const resultCount = document.getElementById('resultCount');
        resultCount.textContent = `Returned ${technicalDetails.result_count} result(s)`;

        // Display raw results (first 5)
        const resultsDisplay = document.getElementById('resultsDisplay');
        if (technicalDetails.raw_results && technicalDetails.raw_results.length > 0) {
            resultsDisplay.textContent = JSON.stringify(technicalDetails.raw_results, null, 2);
        } else {
            resultsDisplay.textContent = 'No results available';
        }

        // Show modal
        this.technicalModal.style.display = 'flex';
    }

    closeTechnicalModal() {
        this.technicalModal.style.display = 'none';
    }
}

// Initialize the chat application when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new ProcurementChat();
});
