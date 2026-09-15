const API_BASE_URL = 'http://localhost:8000'; // Adjust as needed to match your backend target

// State Management
let accessToken = localStorage.getItem('access_token');
let refreshToken = localStorage.getItem('refresh_token');
let currentConversationId = null;
let conversations = [];

// DOM Elements
const authModal = document.getElementById('auth-modal');
const authForm = document.getElementById('auth-form');
const authEmail = document.getElementById('auth-email');
const authPassword = document.getElementById('auth-password');
const authError = document.getElementById('auth-error');
const appContainer = document.getElementById('app');

const conversationsList = document.getElementById('conversations-list');
const newChatBtn = document.getElementById('new-chat-btn');
const logoutBtn = document.getElementById('logout-btn');
const userDisplayName = document.getElementById('user-display-name');

const chatHeaderTitle = document.getElementById('current-chat-title');
const messagesContainer = document.getElementById('messages-container');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
  if (accessToken) {
    initDashboard();
  } else {
    showAuthModal();
  }
});

// Helper: Authenticated Fetch Wrapper
async function apiFetch(endpoint, options = {}) {
  options.headers = options.headers || {};
  if (accessToken) {
    options.headers['Authorization'] = `Bearer ${accessToken}`;
  }
  if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }

  let response = await fetch(`${API_BASE_URL}${endpoint}`, options);

  // Attempt Token Refresh on 401 Unauthenticated
  if (response.status === 401 && refreshToken) {
    const refreshed = await tryTokenRefresh();
    if (refreshed) {
      options.headers['Authorization'] = `Bearer ${accessToken}`;
      response = await fetch(`${API_BASE_URL}${endpoint}`, options);
    } else {
      logout();
      return null;
    }
  }

  return response;
}

async function tryTokenRefresh() {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken })
    });
    if (res.ok) {
      const data = await res.json();
      accessToken = data.access_token;
      refreshToken = data.refresh_token;
      localStorage.setItem('access_token', accessToken);
      localStorage.setItem('refresh_token', refreshToken);
      return true;
    }
  } catch (err) {
    console.error('Refresh token failed:', err);
  }
  return false;
}

// Auth Handlers
function showAuthModal() {
  authModal.classList.remove('hidden');
  appContainer.classList.add('hidden');
}

function hideAuthModal() {
  authModal.classList.add('hidden');
  appContainer.classList.remove('hidden');
}

authForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  authError.classList.add('hidden');

  try {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: authEmail.value,
        password: authPassword.value
      })
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Login failed');
    }

    const data = await response.json();
    accessToken = data.access_token;
    refreshToken = data.refresh_token;

    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);

    hideAuthModal();
    initDashboard();
  } catch (err) {
    authError.textContent = err.message;
    authError.classList.remove('hidden');
  }
});

logoutBtn.addEventListener('click', async () => {
  if (refreshToken) {
    await apiFetch('/auth/logout', {
      method: 'POST',
      body: { refresh_token: refreshToken }
    });
  }
  logout();
});

function logout() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  accessToken = null;
  refreshToken = null;
  currentConversationId = null;
  showAuthModal();
}

// Dashboard Initialization
async function initDashboard() {
  hideAuthModal();
  fetchUserProfile();
  await loadConversations();
  startNewChatUI();
}

async function fetchUserProfile() {
  const res = await apiFetch('/api/v1/user/profile');
  if (res && res.ok) {
    const profile = await res.json();
    userDisplayName.textContent = profile.username || profile.email;
  }
}

// Conversation Sidebar Operations
async function loadConversations() {
  const res = await apiFetch('/api/v1/session/conversations');
  if (res && res.ok) {
    const data = await res.json();
    conversations = data.conversations;
    renderConversationsList();
  }
}

function renderConversationsList() {
  conversationsList.innerHTML = '';
  conversations.forEach(conv => {
    const li = document.createElement('li');
    if (conv.conversation_id === currentConversationId) {
      li.classList.add('active');
    }
    
    const titleSpan = document.createElement('span');
    titleSpan.className = 'conv-title';
    titleSpan.textContent = conv.title || 'Untitled Conversation';
    
    const actionsDiv = document.createElement('div');
    actionsDiv.className = 'conv-actions';

    const renameBtn = document.createElement('button');
    renameBtn.className = 'icon-btn';
    renameBtn.innerHTML = '<i class="fa-solid fa-pen"></i>';
    renameBtn.onclick = (e) => {
      e.stopPropagation();
      renameConversation(conv.conversation_id, conv.title);
    };

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'icon-btn';
    deleteBtn.innerHTML = '<i class="fa-solid fa-trash"></i>';
    deleteBtn.onclick = (e) => {
      e.stopPropagation();
      deleteConversation(conv.conversation_id);
    };

    actionsDiv.appendChild(renameBtn);
    actionsDiv.appendChild(deleteBtn);

    li.appendChild(titleSpan);
    li.appendChild(actionsDiv);

    li.onclick = () => selectConversation(conv.conversation_id, conv.title);
    conversationsList.appendChild(li);
  });
}

async function selectConversation(convId, title) {
  currentConversationId = convId;
  chatHeaderTitle.textContent = title || 'Conversation';
  renderConversationsList();

  const res = await apiFetch(`/api/v1/session/conversations/${convId}`);
  if (res && res.ok) {
    const data = await res.json();
    messagesContainer.innerHTML = '';
    data.conversation_history.forEach(msg => {
      appendMessage(msg.role, msg.content);
    });
  }
}

function startNewChatUI() {
  currentConversationId = null;
  chatHeaderTitle.textContent = 'New Conversation';
  messagesContainer.innerHTML = `
    <div class="empty-state">
      <i class="fa-regular fa-comments"></i>
      <h2>Start a new conversation</h2>
      <p>Send a message below to get started.</p>
    </div>
  `;
  renderConversationsList();
}

newChatBtn.addEventListener('click', startNewChatUI);

async function renameConversation(convId, oldTitle) {
  const newTitle = prompt('Enter new conversation title:', oldTitle || '');
  if (!newTitle || newTitle.trim() === '') return;

  const res = await apiFetch(`/api/v1/session/conversations/${convId}/rename`, {
    method: 'PATCH',
    body: { title: newTitle.trim() }
  });

  if (res && res.ok) {
    if (currentConversationId === convId) {
      chatHeaderTitle.textContent = newTitle.trim();
    }
    await loadConversations();
  }
}

async function deleteConversation(convId) {
  if (!confirm('Are you sure you want to delete this conversation?')) return;

  const res = await apiFetch(`/api/v1/session/conversations/${convId}`, {
    method: 'DELETE'
  });

  if (res && res.ok) {
    if (currentConversationId === convId) {
      startNewChatUI();
    }
    await loadConversations();
  }
}

// Chat Sending Pipeline
chatForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const query = chatInput.value.trim();
  if (!query) return;

  // Clear Empty State if Present
  const emptyState = messagesContainer.querySelector('.empty-state');
  if (emptyState) emptyState.remove();

  // Render User Message
  appendMessage('user', query);
  chatInput.value = '';

  if (!currentConversationId) {
    // Brand New Chat: use POST /api/v1/session/new-chat
    const res = await apiFetch('/api/v1/session/new-chat', {
      method: 'POST',
      body: { query: query }
    });

    if (res && res.ok) {
      const data = await res.json();
      currentConversationId = data.conversation_id;
      appendMessage('assistant', data.reply);
      await loadConversations();
    }
  } else {
    // Existing Chat: use POST /api/v1/session/continue-chat
    const res = await apiFetch('/api/v1/session/continue-chat', {
      method: 'POST',
      body: {
        conversation_id: currentConversationId,
        query: query
      }
    });

    if (res && res.ok) {
      const data = await res.json();
      appendMessage('assistant', data.reply);
    }
  }
});

function appendMessage(role, content) {
  // Normalize role string (handles "User", "USER", "human", "assistant", "ai", etc.)
  const rawRole = (role || 'assistant').toLowerCase();
  const isUser = rawRole === 'user' || rawRole === 'human';
  const roleClass = isUser ? 'user' : 'assistant';
  const roleLabel = isUser ? 'User' : 'Assistant';

  const msgDiv = document.createElement('div');
  msgDiv.className = `message ${roleClass}`;

  // Role tag label
  const tagDiv = document.createElement('div');
  tagDiv.className = 'message-role-tag';
  tagDiv.textContent = roleLabel;

  // Message content
  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-text';
  contentDiv.textContent = content;

  msgDiv.appendChild(tagDiv);
  msgDiv.appendChild(contentDiv);

  messagesContainer.appendChild(msgDiv);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}