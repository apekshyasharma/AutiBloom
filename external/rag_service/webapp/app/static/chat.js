document.addEventListener('DOMContentLoaded', () => {
  const htmlElement = document.documentElement;
  const chatForm = document.getElementById('chatForm');
  const messageInput = document.getElementById('messageInput');
  const chatArea = document.getElementById('chatArea');
  const themeBtns = document.querySelectorAll('[data-set-theme]');

  let currentTheme = localStorage.getItem('theme') || 'dark';
  let isSending = false;

  const SESSION_KEY = "rag_session_id";
  let sessionId = localStorage.getItem(SESSION_KEY);
  if (!sessionId) {
    sessionId = (crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`).toString();
    localStorage.setItem(SESSION_KEY, sessionId);
  }

  // pending query waiting for mode selection
  let pendingQuery = null;

  // Track current active SSE stream (so we can stop/cleanup if needed)
  let activeEventSource = null;

  setTheme(currentTheme);

  themeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const newTheme = btn.getAttribute('data-set-theme');
      setTheme(newTheme);
    });
  });

  function setTheme(theme) {
    htmlElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    currentTheme = theme;
  }

  // ---------- SUBMIT HANDLER ----------
  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = messageInput.value.trim();
    if (!text || isSending) return;

    // Add user message immediately
    addMessage(text, 'user');
    messageInput.value = '';

    // Get selected mode from UI (default to auto if not found)
    const modeSelect = document.getElementById('modeSelect');
    const mode = modeSelect ? modeSelect.value : 'auto';

    // Show persistent typing indicator
    const typingMsgDiv = addTypingMessage();
    setSendingState(true);

    try {
      // 1) Get request_id from backend
      const data = await callBackendForRequestId(text, mode);

      // 2) Open SSE stream (typing indicator remains until first token)
      await openSSEStream(data.request_id, typingMsgDiv);

    } catch (err) {
      replaceTypingWithError(typingMsgDiv, err);
    } finally {
      setSendingState(false);
    }
  });

  // ---------- BACKEND CALL ----------
  // POST /api/message now returns { session_id, request_id }
  async function callBackendForRequestId(message, mode) {
    const res = await fetch("/api/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message, mode })
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`HTTP ${res.status}: ${errText}`);
    }
    return await res.json(); // { session_id, request_id }
  }

  // ---------- SSE STREAM ----------
  // GET /api/stream?session_id=...&request_id=...
  function openSSEStream(requestId, typingMessageDiv) {
    return new Promise((resolve, reject) => {
      // Close any existing stream
      if (activeEventSource) {
        try { activeEventSource.close(); } catch {}
        activeEventSource = null;
      }

      const url =
        `/api/stream?session_id=${encodeURIComponent(sessionId)}` +
        `&request_id=${encodeURIComponent(requestId)}`;

      const es = new EventSource(url);
      activeEventSource = es;

      const bubble = typingMessageDiv.querySelector('.bubble');
      // It will represent the loading state until the first token overwrites it.
      
      let acc = "";

      const closeStream = () => {
        try { es.close(); } catch {}
        if (activeEventSource === es) activeEventSource = null;
      };

      es.addEventListener("token", (ev) => {
        try {
          const data = JSON.parse(ev.data);
          const piece = data.text || "";
          acc += piece;
          // Use textContent for instant rendering.
          // This naturally overwrites the "Thinking..." HTML on the first chunk.
          bubble.textContent = acc;
          scrollToBottom();
        } catch {
          // ignore malformed event chunk
        }
      });

      es.addEventListener("done", (ev) => {
        closeStream();
        // After done, apply markdown formatting once
        bubble.innerHTML = parseMarkdown(acc);
        try {
          const data = JSON.parse(ev.data);
          if (data?.mode_used) appendModeUsed(typingMessageDiv, data.mode_used);
        } catch {}
        scrollToBottom();
        resolve();
      });

      // EventSource "error" sometimes fires on disconnect. Treat as failure.
      es.addEventListener("error", () => {
        closeStream();
        reject(new Error("Streaming failed or connection dropped."));
      });
    });
  }

  // ---------- MODE CHOICE UI ----------
  function addChunkingChoiceMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', 'bot');

    const bubble = document.createElement('div');
    bubble.classList.add('bubble');

    bubble.innerHTML = `
      <div style="font-weight:600; margin-bottom:8px;">Choose a chunking strategy for retrieval:</div>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        <button class="mode-btn" data-mode="fixed" type="button">Fixed-size (overlap)</button>
        <button class="mode-btn" data-mode="semantic" type="button">Semantic (sections + overlap)</button>
        <button class="mode-btn" data-mode="auto" type="button">Auto (system decides)</button>
      </div>
      <div style="opacity:.75; margin-top:8px; font-size:12px;">
        Fixed is best for exact quotes/formulas, Semantic is best for sections/ideas.
      </div>
    `;

    messageDiv.appendChild(bubble);
    chatArea.appendChild(messageDiv);
    scrollToBottom();

    bubble.querySelectorAll(".mode-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const mode = btn.dataset.mode;
        await handleModeSelection(mode, messageDiv);
      });
    });
  }

  // ---------- UPDATED for Step 3 Streaming ----------
  async function handleModeSelection(mode, choiceMessageDiv) {
    if (!pendingQuery) return;

    // Disable buttons to prevent double click
    choiceMessageDiv.querySelectorAll(".mode-btn").forEach(b => b.disabled = true);

    const bubble = choiceMessageDiv.querySelector(".bubble");
    const confirm = document.createElement("div");
    confirm.style.marginTop = "10px";
    confirm.style.opacity = "0.85";
    confirm.innerHTML = `Selected: <b>${escapeHtml(mode)}</b>. Streaming response...`;
    bubble.appendChild(confirm);

    // Assistant typing placeholder
    const typingEl = addTypingMessage();
    setSendingState(true);

    try {
      // 1) Get request_id from backend
      const data = await callBackendForRequestId(pendingQuery, mode);

      // 2) Open SSE stream and render tokens into the same assistant bubble
      await openSSEStream(data.request_id, typingEl);

    } catch (err) {
      replaceTypingWithError(typingEl, err);
    } finally {
      setSendingState(false);
      pendingQuery = null;
    }
  }

  function setSendingState(on) {
    isSending = on;
    messageInput.disabled = on;
    const submitBtn = chatForm.querySelector("button[type='submit']");
    if (submitBtn) submitBtn.disabled = on;
    if (!on) messageInput.focus();
  }

  // ---------- UI HELPERS ----------
  function addMessage(text, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', sender);

    const bubble = document.createElement('div');
    bubble.classList.add('bubble');
    bubble.innerHTML = parseMarkdown(text);

    messageDiv.appendChild(bubble);
    chatArea.appendChild(messageDiv);
    scrollToBottom();
    return messageDiv;
  }

  function addTypingMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', 'bot');

    const bubble = document.createElement('div');
    bubble.classList.add('bubble');
    bubble.innerHTML = `
      <span style="opacity:.8">Retrieving & generating</span>
      <span class="typing-dots" aria-label="typing">
        <span>.</span><span>.</span><span>.</span>
      </span>
    `;
    messageDiv.appendChild(bubble);
    chatArea.appendChild(messageDiv);
    scrollToBottom();
    return messageDiv;
  }

  function appendModeUsed(typingMessageDiv, modeUsed) {
    if (!modeUsed) return;
    const bubble = typingMessageDiv.querySelector('.bubble');
    const meta = document.createElement("div");
    meta.style.opacity = "0.7";
    meta.style.fontSize = "12px";
    meta.style.marginTop = "8px";
    meta.textContent = `Mode used: ${modeUsed}`;
    bubble.appendChild(meta);
  }

  function replaceTypingWithError(typingMessageDiv, err) {
    const bubble = typingMessageDiv.querySelector('.bubble');
    bubble.innerHTML = `
      <b style="color:#ff8080">Error:</b>
      <span style="color:#ffb3b3">${escapeHtml(String(err?.message || err))}</span>
    `;
    scrollToBottom();
  }

  function scrollToBottom() {
    chatArea.scrollTop = chatArea.scrollHeight;
  }

  // ---------- MARKDOWN + XSS SAFETY ----------
  function parseMarkdown(text) {
    let safeText = escapeHtml(text);
    safeText = safeText.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
    safeText = safeText.replace(/`(.*?)`/g, '<code>$1</code>');
    return safeText;
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
