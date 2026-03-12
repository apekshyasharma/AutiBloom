document.addEventListener('DOMContentLoaded', () => {
    const launcher = document.getElementById('autibloom-chat-launcher');
    const panel = document.getElementById('autibloom-chat-panel');
    const input = document.getElementById('chat-input-box');
    const sendBtn = document.getElementById('chat-send-btn');
    const messagesBox = document.getElementById('chat-messages-box');
    const typingInd = document.getElementById('chat-typing-indicator');
    const skipWrapper = document.getElementById('chat-skip-wrapper');
    const skipBtn = document.getElementById('chat-skip-btn');
    const charCount = document.getElementById('chat-char-count');
    const errorMsg = document.getElementById('chat-error-msg');
    
    // Typewriter state
    let typeInterval = null;
    let isTyping = false;
    let fullTypingText = '';
    let currentTypingElement = null;
    
    // Config
    const MAX_CHARS = 800;
    
    // Check if session ID exists
    let sessionId = localStorage.getItem('autibloom_chat_session') || '';

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Toggle Panel
    launcher.addEventListener('click', () => {
        launcher.classList.toggle('open');
        panel.classList.toggle('open');
        if (panel.classList.contains('open')) {
            input.focus();
        }
    });

    // Auto-resize textarea
    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = (input.scrollHeight < 100 ? input.scrollHeight : 100) + 'px';
        
        const len = input.value.length;
        charCount.innerText = `${len}/${MAX_CHARS}`;
        
        if (len > MAX_CHARS) {
            charCount.style.color = '#e11d48';
            sendBtn.disabled = true;
        } else {
            charCount.style.color = '';
            sendBtn.disabled = len === 0;
        }
    });

    // Enter to send (Shift+Enter for new line)
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendBtn.disabled) {
                sendMessage();
            }
        }
    });

    sendBtn.addEventListener('click', sendMessage);

    // Quick prompts — use the data-prompt attribute for the real question,
    // falling back to the chip label so old chips still work.
    document.querySelectorAll('.chat-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            input.value = chip.dataset.prompt || chip.innerText;
            input.dispatchEvent(new Event('input'));
            sendMessage();
        });
    });

    function escapeHtml(unsafe) {
        return unsafe
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }

    function formatResponseBlock(text) {
        // Simple markdown-ish bold and line breaks
        text = escapeHtml(text);
        text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
        text = text.replace(/\n/g, '<br/>');
        return text;
    }

    function markConversationStarted() {
        // Mark both the panel and the messages box so the starter chips
        // are collapsed regardless of which CSS version has loaded.
        panel.classList.add('has-conversation');
        if (messagesBox) messagesBox.classList.add('has-conversation');
        // Hard fallback: hide the chip row directly in case CSS is cached.
        const chipRow = panel.querySelector('.chat-quick-prompts');
        if (chipRow) chipRow.style.display = 'none';
    }

    function appendUserMessage(text) {
        const div = document.createElement('div');
        div.className = 'chat-message user';
        div.innerHTML = `<div class="chat-bubble">${escapeHtml(text)}</div>`;
        messagesBox.insertBefore(div, typingInd);
        // Hide the starter chips once the conversation has begun.
        markConversationStarted();
        scrollToBottom();
    }

    function appendAssistantMessage(text, _unusedSources, isStreaming = false) {
        // `_unusedSources` is kept in the signature for call-site compatibility
        // but is intentionally ignored — the API no longer exposes sources.
        const div = document.createElement('div');
        div.className = 'chat-message assistant';
        div.innerHTML = `<div class="chat-bubble chat-bubble-content">${isStreaming ? '' : formatResponseBlock(text)}</div>`;
        if (skipWrapper.parentNode === messagesBox) {
            messagesBox.insertBefore(div, typingInd);
        } else {
            messagesBox.appendChild(div);
        }
        scrollToBottom();
        return div;
    }

    function scrollToBottom() {
        messagesBox.scrollTop = messagesBox.scrollHeight;
    }

    function setSendingState(sending) {
        input.disabled = sending;
        sendBtn.disabled = sending;
        typingInd.style.display = sending ? 'block' : 'none';
        errorMsg.style.display = 'none';
        if (sending) {
            skipWrapper.style.display = 'none';
            scrollToBottom();
        } else {
            if (!isTyping) {
                input.focus();
            }
        }
    }
    
    // Skip Button Handler
    skipBtn.addEventListener('click', () => {
        if (isTyping && currentTypingElement) {
            clearInterval(typeInterval);
            isTyping = false;
            skipWrapper.style.display = 'none';
            
            const contentDiv = currentTypingElement.querySelector('.chat-bubble-content');
            if (contentDiv) {
                contentDiv.innerHTML = formatResponseBlock(fullTypingText);
            }
            input.disabled = false;
            sendBtn.disabled = input.value.trim().length === 0;
            input.focus();
            scrollToBottom();
        }
    });

    async function sendMessage() {
        const text = input.value.trim();
        if (!text || text.length > MAX_CHARS) return;

        appendUserMessage(text);
        
        input.value = '';
        input.style.height = 'auto';
        input.dispatchEvent(new Event('input')); // reset counter
        
        setSendingState(true);

        try {
            const res = await fetch('/chat/api/ask/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({
                    message: text,
                    session_id: sessionId || null
                })
            });

            const data = await res.json();
            
            if (!res.ok) {
                throw new Error(data.error || 'Failed to get answer');
            }

            if (data.session_id) {
                sessionId = data.session_id;
                localStorage.setItem('autibloom_chat_session', sessionId);
            }

            if (data.error) {
                throw new Error(data.error);
            }

            // Start typing effect
            typingInd.style.display = 'none';
            skipWrapper.style.display = 'block';
            isTyping = true;
            fullTypingText = data.answer;
            
            currentTypingElement = appendAssistantMessage('', data.sources, true);
            const contentDiv = currentTypingElement.querySelector('.chat-bubble-content');
            
            const words = fullTypingText.split(' ');
            let wordIndex = 0;
            let currentText = '';
            
            typeInterval = setInterval(() => {
                if (!isTyping) return; // In case it was skipped
                
                // Append 1-3 words randomly for a more natural feel
                const wordsToAppend = Math.floor(Math.random() * 2) + 1;
                for (let i = 0; i < wordsToAppend; i++) {
                    if (wordIndex < words.length) {
                        currentText += (wordIndex > 0 ? ' ' : '') + words[wordIndex];
                        wordIndex++;
                    }
                }
                
                contentDiv.innerHTML = formatResponseBlock(currentText);
                scrollToBottom();
                
                if (wordIndex >= words.length) {
                    clearInterval(typeInterval);
                    isTyping = false;
                    skipWrapper.style.display = 'none';
                    
                    // Show sources button if it exists
                    const sourcesBtn = currentTypingElement.querySelector('.chat-sources-btn');
                    if (sourcesBtn) {
                        sourcesBtn.style.display = 'flex';
                    }
                    
                    input.disabled = false;
                    sendBtn.disabled = input.value.trim().length === 0;
                    input.focus();
                    scrollToBottom();
                }
            }, 45); // ~45ms per 1-2 words means roughly ~10-20 words per second

        } catch (err) {
            errorMsg.innerText = err.message || 'An error occurred. Please try again.';
            errorMsg.style.display = 'block';
            skipWrapper.style.display = 'none';
            
            // Put text back so user doesn't lose it
            input.value = text;
            input.dispatchEvent(new Event('input'));
            
            input.disabled = false;
            sendBtn.disabled = false;
        }
    }
});
