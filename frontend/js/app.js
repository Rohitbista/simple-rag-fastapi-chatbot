/**
 * app.js — Main entry point.
 *
 * Responsibilities:
 *   - Boot sequence: check existing tokens → show auth or dashboard.
 *   - Fetch user profile and expose role-gated panels (admin / superadmin).
 *   - Wire up ALL global event listeners:
 *       auth form, new-chat, logout, chat form, keyboard shortcuts,
 *       password-visibility toggle, mobile sidebar, send-button guard,
 *       admin panel buttons, superadmin panel buttons, back-to-chat.
 *   - Coordinate between modules (Auth, API, UI, Chat, Conversations,
 *     Admin, SuperAdmin).
 *
 * Module dependency order (scripts loaded in index.html in this order):
 *   1. api.js
 *   2. auth.js
 *   3. ui.js
 *   4. chat.js
 *   5. conversations.js
 *   6. admin.js
 *   7. superadmin.js
 *   8. app.js  ← this file (must be last)
 */

'use strict';

// ─── Boot ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  if (Auth.hasSession()) {
    initDashboard();
  } else {
    UI.showAuthModal();
  }
});

// ─── Dashboard init ────────────────────────────────────────────────────────────

async function initDashboard() {
  UI.hideAuthModal();
  await fetchAndDisplayProfile();
  await Conversations.load();
  UI.showChatView();
}

/**
 * Fetch /api/v1/user/profile and update the sidebar user chip + role panels.
 * The profile response is expected to have: { username, email, role }
 * where role is one of: 'user' | 'admin' | 'superadmin'
 */
async function fetchAndDisplayProfile() {
  const res = await API.fetch('/api/v1/user/profile');
  if (!res || !res.ok) return;

  const profile = await res.json();
  const displayName = profile.username || profile.email || 'User';
  const role        = (profile.role || 'user').toLowerCase();

  UI.setUserDisplayName(displayName, role);

  // Show role-gated sidebar panels
  if (role === 'admin' || role === 'superadmin') {
    document.getElementById('admin-panel').classList.remove('hidden');
  }
  if (role === 'superadmin') {
    document.getElementById('superadmin-panel').classList.remove('hidden');
  }
}

// ─── Auth form ────────────────────────────────────────────────────────────────

document.getElementById('auth-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn      = document.getElementById('auth-submit-btn');
  const email    = document.getElementById('auth-email').value.trim();
  const password = document.getElementById('auth-password').value;

  btn.disabled = true;
  btn.querySelector('.btn-text').textContent = 'Signing in…';

  const ok = await Auth.login(email, password);

  btn.disabled = false;
  btn.querySelector('.btn-text').textContent = 'Sign in';

  if (ok) initDashboard();
});

// Password visibility toggle
document.querySelector('.toggle-password').addEventListener('click', () => {
  const input = document.getElementById('auth-password');
  const icon  = document.querySelector('.toggle-password i');
  const isHidden = input.type === 'password';
  input.type = isHidden ? 'text' : 'password';
  icon.className = isHidden ? 'fa-regular fa-eye-slash' : 'fa-regular fa-eye';
});

// ─── New chat ──────────────────────────────────────────────────────────────────

document.getElementById('new-chat-btn').addEventListener('click', () => {
  Chat.resetConversation();
  UI.showChatView();
  UI.startNewChatState();
  closeSidebar();
});

// ─── Logout ────────────────────────────────────────────────────────────────────

document.getElementById('logout-btn').addEventListener('click', async () => {
  await Auth.logout();
  // Hide role panels so they don't flash on next login
  document.getElementById('admin-panel').classList.add('hidden');
  document.getElementById('superadmin-panel').classList.add('hidden');
  UI.showAuthModal();
});

// ─── Chat form ────────────────────────────────────────────────────────────────

const chatInput = document.getElementById('chat-input');
const sendBtn   = document.getElementById('send-btn');

// Enable/disable send button based on input content
chatInput.addEventListener('input', () => {
  sendBtn.disabled = chatInput.value.trim() === '';
  // Auto-grow textarea
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + 'px';
});

// Enter sends, Shift+Enter adds a newline
chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled) document.getElementById('chat-form').requestSubmit();
  }
});

document.getElementById('chat-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (chatInput.value.trim() === '') return;
  sendBtn.disabled = true;
  await Chat.handleSubmit();
  // handleSubmit clears the input; reset height
  chatInput.style.height = 'auto';
  sendBtn.disabled = true; // keep disabled until user types again
});

// ─── Back to chat (from panel view) ──────────────────────────────────────────

document.getElementById('back-to-chat-btn').addEventListener('click', () => {
  UI.showChatView();
});

// ─── Mobile sidebar ────────────────────────────────────────────────────────────

document.getElementById('sidebar-toggle').addEventListener('click', toggleSidebar);

// Close sidebar when clicking the backdrop (the shadow overlay)
document.addEventListener('click', (e) => {
  const sidebar = document.getElementById('sidebar');
  const toggle  = document.getElementById('sidebar-toggle');
  if (
    sidebar.classList.contains('open') &&
    !sidebar.contains(e.target) &&
    !toggle.contains(e.target)
  ) {
    closeSidebar();
  }
});

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
}

function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
}

// ─── Admin panel: Manage Users ────────────────────────────────────────────────

document.getElementById('admin-users-btn').addEventListener('click', async () => {
  closeSidebar();
  UI.showPanelView('Users');
  UI.showDataTable();
  UI.setPanelStatus('Loading users…');

  try {
    const data = await Admin.listUsers();
    const users = data.users || [];

    UI.renderTable(
      ['Username', 'Email', 'Status', 'Actions'],
      users,
      (u) => [
        u.username || '—',
        u.email,
        UI.chip(u.is_active ? 'active' : 'inactive', u.is_active ? 'Active' : 'Inactive'),
        UI.tableActions([
          {
            label: 'Deactivate',
            cls: 'danger',
            hidden: !u.is_active,
            onClick: () => adminDeactivate(u.user_id),
          },
          {
            label: 'Delete',
            cls: 'danger',
            onClick: () => adminDelete(u.user_id),
          },
        ]),
      ]
    );

    UI.setPanelStatus(`${users.length} user${users.length !== 1 ? 's' : ''}`);
  } catch (err) {
    UI.setPanelStatus(`Error: ${err.message}`, true);
  }
});

async function adminDeactivate(userId) {
  if (!confirm('Deactivate this user?')) return;
  try {
    await Admin.deactivateUser(userId);
    UI.showToast('User deactivated.');
    document.getElementById('admin-users-btn').click();
  } catch (err) {
    UI.showToast(err.message, 'error');
  }
}

async function adminDelete(userId) {
  if (!confirm('Permanently delete this user? This cannot be undone.')) return;
  try {
    await Admin.deleteUser(userId);
    UI.showToast('User deleted.');
    document.getElementById('admin-users-btn').click();
  } catch (err) {
    UI.showToast(err.message, 'error');
  }
}

// ─── Admin panel: Create User ─────────────────────────────────────────────────

document.getElementById('admin-create-user-btn').addEventListener('click', () => {
  closeSidebar();
  UI.showPanelView('Create User');
  UI.showCreateUserForm();
});

document.getElementById('create-user-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const errEl     = document.getElementById('create-user-error');
  const successEl = document.getElementById('create-user-success');
  errEl.classList.add('hidden');
  successEl.classList.add('hidden');

  const payload = {
    email:    document.getElementById('new-user-email').value.trim(),
    username: document.getElementById('new-user-username').value.trim(),
    password: document.getElementById('new-user-password').value,
  };

  try {
    const user = await Admin.createUser(payload);
    successEl.textContent = `User "${user.username || user.email}" created successfully.`;
    successEl.classList.remove('hidden');
    document.getElementById('create-user-form').reset();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
  }
});

// ─── SuperAdmin panel: All Admins ─────────────────────────────────────────────

document.getElementById('sa-admins-btn').addEventListener('click', async () => {
  closeSidebar();
  UI.showPanelView('All Admins');
  UI.showDataTable();
  UI.setPanelStatus('Loading admins…');

  try {
    const data   = await SuperAdmin.listAdmins();
    const admins = data.admins || [];

    UI.renderTable(
      ['Username', 'Email', 'Status', 'Actions'],
      admins,
      (a) => [
        a.username || '—',
        a.email,
        UI.chip(a.is_active ? 'active' : 'inactive', a.is_active ? 'Active' : 'Inactive'),
        UI.tableActions([
          {
            label: 'Deactivate',
            cls: 'danger',
            hidden: !a.is_active,
            onClick: () => saDeactivateAdmin(a.admin_id),
          },
          {
            label: 'Delete',
            cls: 'danger',
            onClick: () => saDeleteAdmin(a.admin_id),
          },
        ]),
      ]
    );

    UI.setPanelStatus(`${admins.length} admin${admins.length !== 1 ? 's' : ''}`);
  } catch (err) {
    UI.setPanelStatus(`Error: ${err.message}`, true);
  }
});

// ─── SuperAdmin panel: Pending Admins ────────────────────────────────────────

document.getElementById('sa-pending-btn').addEventListener('click', async () => {
  closeSidebar();
  UI.showPanelView('Pending Admins');
  UI.showDataTable();
  UI.setPanelStatus('Loading pending approvals…');

  try {
    const pending = await SuperAdmin.listPendingAdmins();
    const list    = Array.isArray(pending) ? pending : (pending.admins || []);

    UI.renderTable(
      ['Username', 'Email', 'Registered', 'Actions'],
      list,
      (a) => [
        a.username || '—',
        a.email,
        a.created_at ? new Date(a.created_at).toLocaleDateString() : '—',
        UI.tableActions([
          {
            label: 'Approve',
            cls: 'success',
            onClick: () => saApproveAdmin(a.admin_id),
          },
          {
            label: 'Delete',
            cls: 'danger',
            onClick: () => saDeleteAdmin(a.admin_id),
          },
        ]),
      ]
    );

    UI.setPanelStatus(`${list.length} pending`);
  } catch (err) {
    UI.setPanelStatus(`Error: ${err.message}`, true);
  }
});

// ─── SuperAdmin panel: All Users ─────────────────────────────────────────────

document.getElementById('sa-all-users-btn').addEventListener('click', async () => {
  closeSidebar();
  UI.showPanelView('All Users');
  UI.showDataTable();
  UI.setPanelStatus('Loading users…');

  try {
    const data  = await SuperAdmin.listAllUsers();
    const users = data.users || [];

    UI.renderTable(
      ['Username', 'Email', 'Admin', 'Status'],
      users,
      (u) => [
        u.username || '—',
        u.email,
        u.admin_email || u.admin_id || '—',
        UI.chip(u.is_active ? 'active' : 'inactive', u.is_active ? 'Active' : 'Inactive'),
      ]
    );

    UI.setPanelStatus(`${users.length} user${users.length !== 1 ? 's' : ''} system-wide`);
  } catch (err) {
    UI.setPanelStatus(`Error: ${err.message}`, true);
  }
});

// ─── SuperAdmin panel: Re-index ───────────────────────────────────────────────

document.getElementById('sa-reindex-btn').addEventListener('click', async () => {
  if (!confirm('Trigger a full vector store re-index? This may take a while.')) return;
  closeSidebar();

  const btn = document.getElementById('sa-reindex-btn');
  btn.disabled = true;
  UI.showToast('Re-index started…');

  try {
    const result = await SuperAdmin.reindexVectorStore();
    UI.showToast(result.message || 'Re-index triggered successfully.', 'success');
  } catch (err) {
    UI.showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
  }
});

// ─── SuperAdmin helpers ───────────────────────────────────────────────────────

async function saApproveAdmin(adminId) {
  try {
    await SuperAdmin.approveAdmin(adminId);
    UI.showToast('Admin approved.', 'success');
    document.getElementById('sa-pending-btn').click();
  } catch (err) {
    UI.showToast(err.message, 'error');
  }
}

async function saDeactivateAdmin(adminId) {
  if (!confirm('Deactivate this admin?')) return;
  try {
    await SuperAdmin.deactivateAdmin(adminId);
    UI.showToast('Admin deactivated.');
    document.getElementById('sa-admins-btn').click();
  } catch (err) {
    UI.showToast(err.message, 'error');
  }
}

async function saDeleteAdmin(adminId) {
  if (!confirm('Permanently delete this admin? This cannot be undone.')) return;
  try {
    await SuperAdmin.deleteAdmin(adminId);
    UI.showToast('Admin deleted.');
    document.getElementById('sa-admins-btn').click();
  } catch (err) {
    UI.showToast(err.message, 'error');
  }
}