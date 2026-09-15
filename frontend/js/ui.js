/**
 * ui.js — DOM helpers and rendering primitives.
 *
 * Exposes a single namespace: UI
 *
 * Responsibilities:
 *   - Show/hide auth modal vs app shell.
 *   - Display and clear auth error messages.
 *   - Switch between chat view and panel view (admin/superadmin).
 *   - Render individual chat messages into the messages container.
 *   - Set the active conversation title in the header.
 *   - Render the empty "start a new conversation" state.
 *   - Show/hide a typing indicator while awaiting an LLM response.
 *   - Update the user display name and role badge in the sidebar.
 *   - Render data tables and the create-user form for admin panels.
 *   - Show toast notifications.
 *
 * UI never makes network calls — it only reads/writes the DOM.
 */

'use strict';

const UI = (() => {

  // ── Element refs ──────────────────────────────────────────────────────────
  const authModal           = document.getElementById('auth-modal');
  const appContainer        = document.getElementById('app');
  const authError           = document.getElementById('auth-error');
  const messagesContainer   = document.getElementById('messages-container');
  const chatHeaderTitle     = document.getElementById('current-chat-title');
  const userDisplayName     = document.getElementById('user-display-name');
  const userRoleBadge       = document.getElementById('user-role-badge');
  const userAvatarInitials  = document.getElementById('user-avatar-initials');
  const chatView            = document.getElementById('chat-view');
  const panelView           = document.getElementById('panel-view');
  const panelTitle          = document.getElementById('panel-title');
  const panelStatus         = document.getElementById('panel-status');
  const dataTableSection    = document.getElementById('data-table-section');
  const createUserSection   = document.getElementById('create-user-form-section');
  const dataTableHead       = document.getElementById('data-table-head');
  const dataTableBody       = document.getElementById('data-table-body');
  const tableEmpty          = document.getElementById('table-empty');
  const toast               = document.getElementById('toast');

  // ── Auth modal ────────────────────────────────────────────────────────────

  function showAuthModal() {
    authModal.classList.remove('hidden');
    appContainer.classList.add('hidden');
    document.getElementById('auth-email').focus();
  }

  function hideAuthModal() {
    authModal.classList.add('hidden');
    appContainer.classList.remove('hidden');
  }

  function showAuthError(message) {
    authError.textContent = message;
    authError.classList.remove('hidden');
  }

  function clearAuthError() {
    authError.textContent = '';
    authError.classList.add('hidden');
  }

  // ── Sidebar user chip ─────────────────────────────────────────────────────

  function setUserDisplayName(name, role) {
    userDisplayName.textContent = name;
    if (role) userRoleBadge.textContent = role;
    // Set avatar to first initial
    userAvatarInitials.textContent = (name || 'U')[0].toUpperCase();
  }

  // ── View switching ────────────────────────────────────────────────────────

  /** Show the main chat view, hiding the panel view. */
  function showChatView() {
    chatView.classList.remove('hidden');
    panelView.classList.add('hidden');
  }

  /**
   * Show the panel view (admin/superadmin) with a given title.
   * Hides both inner sections until the caller explicitly shows one.
   * @param {string} title
   */
  function showPanelView(title) {
    chatView.classList.add('hidden');
    panelView.classList.remove('hidden');
    panelTitle.textContent = title || 'Panel';
    // Reset inner sections
    dataTableSection.classList.add('hidden');
    createUserSection.classList.add('hidden');
  }

  /** Reveal the data table section inside the panel view. */
  function showDataTable() {
    dataTableSection.classList.remove('hidden');
    createUserSection.classList.add('hidden');
  }

  /** Reveal the create-user form section inside the panel view. */
  function showCreateUserForm() {
    createUserSection.classList.remove('hidden');
    dataTableSection.classList.add('hidden');
    document.getElementById('create-user-error').classList.add('hidden');
    document.getElementById('create-user-success').classList.add('hidden');
    document.getElementById('new-user-email').focus();
  }

  // ── Panel status bar ──────────────────────────────────────────────────────

  /**
   * Update the status line above the data table.
   * @param {string} message
   * @param {boolean} [isError=false]
   */
  function setPanelStatus(message, isError = false) {
    panelStatus.textContent = message;
    panelStatus.classList.remove('hidden');
    panelStatus.style.color = isError ? 'var(--danger)' : '';
  }

  // ── Chat header ───────────────────────────────────────────────────────────

  function setChatTitle(title) {
    chatHeaderTitle.textContent = title || 'Conversation';
  }

  // ── Empty / new-chat state ────────────────────────────────────────────────

  function startNewChatState() {
    chatHeaderTitle.textContent = 'New Conversation';
    messagesContainer.innerHTML = `
      <div class="empty-state" id="empty-state">
        <div class="empty-icon"><i class="fa-regular fa-comments"></i></div>
        <h2>Start a conversation</h2>
        <p>Ask anything — your history stays in the sidebar.</p>
      </div>
    `;
  }

  function clearEmptyState() {
    const emptyState = messagesContainer.querySelector('.empty-state');
    if (emptyState) emptyState.remove();
  }

  // ── Message rendering ─────────────────────────────────────────────────────

  /**
   * Append a single chat message bubble.
   * @param {'user'|'assistant'|'system'|string} role
   * @param {string} content
   */
  function appendMessage(role, content) {
    const rawRole   = (role || 'assistant').toLowerCase();
    const isUser    = rawRole === 'user' || rawRole === 'human';
    const roleClass = isUser ? 'user' : 'assistant';
    const roleLabel = isUser ? 'You' : 'Assistant';

    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${roleClass}`;

    const tagDiv = document.createElement('div');
    tagDiv.className = 'message-role-tag';
    tagDiv.textContent = roleLabel;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-text';
    contentDiv.textContent = content;

    msgDiv.appendChild(tagDiv);
    msgDiv.appendChild(contentDiv);
    messagesContainer.appendChild(msgDiv);
    _scrollToBottom();
  }

  /**
   * Replace the messages container with a full conversation history.
   * @param {Array<{role: string, content: string}>} messages
   */
  function renderHistory(messages) {
    messagesContainer.innerHTML = '';
    (messages || []).forEach(msg => appendMessage(msg.role, msg.content));
  }

  // ── Typing indicator ──────────────────────────────────────────────────────

  const TYPING_ID = 'typing-indicator';

  function showTypingIndicator() {
    if (document.getElementById(TYPING_ID)) return;
    const el = document.createElement('div');
    el.id = TYPING_ID;
    el.className = 'message assistant typing';
    el.innerHTML = `
      <div class="message-role-tag">Assistant</div>
      <div class="message-text">
        <span class="dot"></span><span class="dot"></span><span class="dot"></span>
      </div>
    `;
    messagesContainer.appendChild(el);
    _scrollToBottom();
  }

  function hideTypingIndicator() {
    const el = document.getElementById(TYPING_ID);
    if (el) el.remove();
  }

  // ── Data table helpers ────────────────────────────────────────────────────

  /**
   * Render a data table.
   * @param {string[]} headers - Column header labels
   * @param {object[]} rows    - Array of data objects
   * @param {function} rowFn  - Maps a row object to an array of cell values
   *                            (strings, HTMLElements, or DocumentFragments)
   */
  function renderTable(headers, rows, rowFn) {
    // Head
    dataTableHead.innerHTML = '';
    const tr = document.createElement('tr');
    headers.forEach(h => {
      const th = document.createElement('th');
      th.textContent = h;
      tr.appendChild(th);
    });
    dataTableHead.appendChild(tr);

    // Body
    dataTableBody.innerHTML = '';

    if (!rows || rows.length === 0) {
      tableEmpty.classList.remove('hidden');
      return;
    }
    tableEmpty.classList.add('hidden');

    rows.forEach(row => {
      const tr = document.createElement('tr');
      const cells = rowFn(row);
      cells.forEach(cellVal => {
        const td = document.createElement('td');
        if (cellVal instanceof HTMLElement || cellVal instanceof DocumentFragment) {
          td.appendChild(cellVal);
        } else {
          td.innerHTML = cellVal; // allows chip HTML strings
        }
        tr.appendChild(td);
      });
      dataTableBody.appendChild(tr);
    });
  }

  /**
   * Build a status chip HTML string.
   * @param {'active'|'inactive'|'pending'|'admin'} type
   * @param {string} label
   * @returns {string}
   */
  function chip(type, label) {
    return `<span class="chip chip-${type}">${_escHtml(label)}</span>`;
  }

  /**
   * Build a div of table action buttons.
   * @param {Array<{label: string, cls?: string, hidden?: boolean, onClick: function}>} actions
   * @returns {HTMLDivElement}
   */
  function tableActions(actions) {
    const wrap = document.createElement('div');
    wrap.className = 'tbl-actions';
    actions.forEach(({ label, cls, hidden, onClick }) => {
      if (hidden) return;
      const btn = document.createElement('button');
      btn.className = `tbl-btn${cls ? ' ' + cls : ''}`;
      btn.textContent = label;
      btn.addEventListener('click', onClick);
      wrap.appendChild(btn);
    });
    return wrap;
  }

  // ── Toast notifications ───────────────────────────────────────────────────

  let _toastTimer = null;

  /**
   * Show a brief toast message.
   * @param {string} message
   * @param {'default'|'success'|'error'} [type='default']
   * @param {number} [duration=3000]
   */
  function showToast(message, type = 'default', duration = 3000) {
    clearTimeout(_toastTimer);
    toast.textContent = message;
    toast.className = 'toast';
    if (type === 'error')   toast.classList.add('toast-error');
    if (type === 'success') toast.classList.add('toast-success');
    // Force reflow so the transition fires even if it was already visible
    void toast.offsetWidth;
    toast.classList.add('show');
    _toastTimer = setTimeout(() => toast.classList.remove('show'), duration);
  }

  // ── Internal helpers ──────────────────────────────────────────────────────

  function _scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  function _escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Public interface ──────────────────────────────────────────────────────

  return {
    // Auth
    showAuthModal,
    hideAuthModal,
    showAuthError,
    clearAuthError,
    // User chip
    setUserDisplayName,
    // View switching
    showChatView,
    showPanelView,
    showDataTable,
    showCreateUserForm,
    // Panel
    setPanelStatus,
    // Chat
    setChatTitle,
    startNewChatState,
    clearEmptyState,
    appendMessage,
    renderHistory,
    showTypingIndicator,
    hideTypingIndicator,
    // Table helpers
    renderTable,
    chip,
    tableActions,
    // Toast
    showToast,
  };
})();