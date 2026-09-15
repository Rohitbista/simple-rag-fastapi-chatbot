/**
 * conversations.js — Conversation sidebar management.
 *
 * Exposes a single namespace: Conversations
 *
 * Responsibilities:
 *   - Fetch and cache the user's conversation list from the server.
 *   - Render the sidebar list, including rename and delete controls.
 *   - Handle selecting a conversation: load its history into the chat panel.
 *   - Rename a conversation (PATCH /api/v1/session/conversations/{id}/rename).
 *   - Delete a conversation (DELETE /api/v1/session/conversations/{id}).
 *   - Expose setActiveInSidebar() so Chat can highlight the current entry
 *     after creating a new conversation.
 */

'use strict';

const Conversations = (() => {
  const conversationsList = document.getElementById('conversations-list');

  // ── Internal state ────────────────────────────────────────────────────────

  /** @type {Array<{conversation_id: string, title: string|null, created_at: string, message_count: number}>} */
  let _conversations = [];

  // ── Load & render ─────────────────────────────────────────────────────────

  /**
   * Fetch the full conversation list and re-render the sidebar.
   */
  async function load() {
    const res = await API.fetch('/api/v1/session/conversations');
    if (!res || !res.ok) return;

    const data = await res.json();
    _conversations = data.conversations || [];
    _render();
  }

  function _render() {
    conversationsList.innerHTML = '';
    const currentId = Chat.getCurrentConversationId();

    _conversations.forEach(conv => {
      const li = _buildListItem(conv, currentId);
      conversationsList.appendChild(li);
    });
  }

  /**
   * Build a single <li> for a conversation entry.
   * @param {object} conv
   * @param {string|null} currentId
   * @returns {HTMLLIElement}
   */
  function _buildListItem(conv, currentId) {
    const li = document.createElement('li');
    if (conv.conversation_id === currentId) {
      li.classList.add('active');
    }

    // Title
    const titleSpan = document.createElement('span');
    titleSpan.className = 'conv-title';
    titleSpan.textContent = conv.title || 'Untitled Conversation';

    // Action buttons
    const actionsDiv = document.createElement('div');
    actionsDiv.className = 'conv-actions';

    const renameBtn = _iconButton('fa-solid fa-pen', 'Rename', (e) => {
      e.stopPropagation();
      rename(conv.conversation_id, conv.title);
    });

    const deleteBtn = _iconButton('fa-solid fa-trash', 'Delete', (e) => {
      e.stopPropagation();
      deleteConversation(conv.conversation_id);
    });

    actionsDiv.appendChild(renameBtn);
    actionsDiv.appendChild(deleteBtn);

    li.appendChild(titleSpan);
    li.appendChild(actionsDiv);
    li.addEventListener('click', () => select(conv.conversation_id, conv.title));

    return li;
  }

  function _iconButton(iconClass, label, onClick) {
    const btn = document.createElement('button');
    btn.className = 'icon-btn';
    btn.setAttribute('aria-label', label);
    btn.innerHTML = `<i class="${iconClass}"></i>`;
    btn.addEventListener('click', onClick);
    return btn;
  }

  // ── Select ────────────────────────────────────────────────────────────────

  /**
   * Load a conversation's history into the chat panel and mark it active.
   * @param {string} convId
   * @param {string|null} title
   */
  async function select(convId, title) {
    Chat.setCurrentConversationId(convId);
    UI.setChatTitle(title);
    _render(); // update active highlight immediately

    const res = await API.fetch(`/api/v1/session/conversations/${convId}`);
    if (!res || !res.ok) return;

    const data = await res.json();
    UI.renderHistory(data.conversation_history);
  }

  // ── Rename ────────────────────────────────────────────────────────────────

  /**
   * Prompt for a new title and PATCH it to the server.
   * @param {string} convId
   * @param {string|null} currentTitle
   */
  async function rename(convId, currentTitle) {
    const newTitle = prompt('Rename conversation:', currentTitle || '');
    if (!newTitle || !newTitle.trim()) return;

    const res = await API.fetch(`/api/v1/session/conversations/${convId}/rename`, {
      method: 'PATCH',
      body: { title: newTitle.trim() },
    });

    if (!res || !res.ok) return;

    // Update the header if this is the active conversation
    if (Chat.getCurrentConversationId() === convId) {
      UI.setChatTitle(newTitle.trim());
    }

    await load();
  }

  // ── Delete ────────────────────────────────────────────────────────────────

  /**
   * Confirm and DELETE a conversation from the server.
   * @param {string} convId
   */
  async function deleteConversation(convId) {
    if (!confirm('Delete this conversation? This cannot be undone.')) return;

    const res = await API.fetch(`/api/v1/session/conversations/${convId}`, {
      method: 'DELETE',
    });

    if (!res || !res.ok) return;

    // If the deleted conversation was active, reset to new-chat state
    if (Chat.getCurrentConversationId() === convId) {
      Chat.resetConversation();
      UI.startNewChatState();
    }

    await load();
  }

  // ── Highlight helper ──────────────────────────────────────────────────────

  /**
   * Re-render the sidebar to highlight the given conversation_id.
   * Called by Chat after a new conversation is created.
   * @param {string} convId
   */
  function setActiveInSidebar(convId) {
    _render();
  }

  // ── Public interface ──────────────────────────────────────────────────────

  return {
    load,
    select,
    rename,
    deleteConversation,
    setActiveInSidebar,
  };
})();