/**
 * chat.js — Chat sending logic.
 *
 * Exposes a single namespace: Chat
 *
 * Responsibilities:
 *   - Read the query from the chat input.
 *   - Decide between POST /api/v1/session/new-chat (first message)
 *     and POST /api/v1/session/continue-chat (subsequent messages).
 *   - Store the active conversation_id in module state.
 *   - Delegate rendering to UI and sidebar refresh to Conversations.
 *
 * Chat does NOT own the conversation list — Conversations.js does.
 * Chat owns only the "what is the current conversation" piece of state.
 */

'use strict';

const Chat = (() => {
  const chatInput = document.getElementById('chat-input');

  // ── Internal state ────────────────────────────────────────────────────────

  /** UUID string of the currently active conversation, or null for a new one. */
  let _currentConversationId = null;

  // ── Accessors used by other modules ──────────────────────────────────────

  function getCurrentConversationId() {
    return _currentConversationId;
  }

  /**
   * Switch the active conversation (called by Conversations when user clicks
   * a sidebar entry).
   * @param {string|null} id
   */
  function setCurrentConversationId(id) {
    _currentConversationId = id;
  }

  /** Reset to the "new chat" state — clears the active conversation. */
  function resetConversation() {
    _currentConversationId = null;
  }

  // ── Send pipeline ─────────────────────────────────────────────────────────

  /**
   * Main submit handler — called by the chat-form submit listener in app.js.
   */
  async function handleSubmit() {
    const query = chatInput.value.trim();
    if (!query) return;

    UI.clearEmptyState();
    UI.appendMessage('user', query);
    chatInput.value = '';
    chatInput.focus();

    UI.showTypingIndicator();

    try {
      if (!_currentConversationId) {
        await _startNewChat(query);
      } else {
        await _continueChat(query);
      }
    } finally {
      UI.hideTypingIndicator();
    }
  }

  // ── New chat ──────────────────────────────────────────────────────────────

  /**
   * POST /api/v1/session/new-chat
   * Sets _currentConversationId on success and refreshes the sidebar.
   * @param {string} query
   */
  async function _startNewChat(query) {
    const res = await API.fetch('/api/v1/session/new-chat', {
      method: 'POST',
      body: { query },
    });

    if (!res || !res.ok) {
      _handleError(res, 'Failed to start a new conversation.');
      return;
    }

    const data = await res.json();
    _currentConversationId = data.conversation_id;
    UI.appendMessage('assistant', data.reply);

    // Refresh sidebar so the new conversation appears
    await Conversations.load();
    Conversations.setActiveInSidebar(_currentConversationId);
  }

  // ── Continue chat ─────────────────────────────────────────────────────────

  /**
   * POST /api/v1/session/continue-chat
   * @param {string} query
   */
  async function _continueChat(query) {
    const res = await API.fetch('/api/v1/session/continue-chat', {
      method: 'POST',
      body: {
        conversation_id: _currentConversationId,
        query,
      },
    });

    if (!res || !res.ok) {
      _handleError(res, 'Failed to send message.');
      return;
    }

    const data = await res.json();
    UI.appendMessage('assistant', data.reply);
  }

  // ── Error helper ──────────────────────────────────────────────────────────

  async function _handleError(res, fallback) {
    let detail = fallback;
    if (res) {
      try {
        const body = await res.json();
        detail = body.detail || fallback;
      } catch (_) { /* ignore */ }
    }
    UI.appendMessage('assistant', `⚠ ${detail}`);
    console.error('[Chat]', detail);
  }

  // ── Public interface ──────────────────────────────────────────────────────

  return {
    handleSubmit,
    getCurrentConversationId,
    setCurrentConversationId,
    resetConversation,
  };
})();