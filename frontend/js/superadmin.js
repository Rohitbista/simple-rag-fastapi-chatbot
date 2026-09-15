/**
 * superadmin.js — SuperAdmin-only operations.
 *
 * Exposes a single namespace: SuperAdmin
 *
 * Only called when the authenticated user's role is SUPERADMIN.
 * All functions hit /api/v1/superadmin/* endpoints.
 *
 * Responsibilities:
 *   Admin management:
 *     - List all admins (active + inactive).
 *     - List pending (unapproved) admins.
 *     - Approve a pending admin.
 *     - Deactivate an active admin.
 *     - Soft-delete an admin.
 *
 *   System-wide user visibility:
 *     - List every user across all admins.
 *     - Get a specific user's profile.
 *
 *   Data ingestion:
 *     - Trigger a full vector store re-index.
 *
 * None of these functions render UI directly — they return data or throw,
 * and the caller is responsible for updating the DOM.
 */

'use strict';

const SuperAdmin = (() => {

  // ── Admin management ──────────────────────────────────────────────────────

  /**
   * List all admins (active and inactive).
   * GET /api/v1/superadmin/admins
   * @returns {Promise<{ admins: object[], total: number }>}
   */
  async function listAdmins() {
    const res = await API.fetch('/api/v1/superadmin/admins');
    return _handleResponse(res, 'Failed to fetch admins.');
  }

  /**
   * List admins whose registration is pending approval.
   * GET /api/v1/superadmin/admins/pending
   * @returns {Promise<object[]>} Array of PendingAdminResponse
   */
  async function listPendingAdmins() {
    const res = await API.fetch('/api/v1/superadmin/admins/pending');
    return _handleResponse(res, 'Failed to fetch pending admins.');
  }

  /**
   * Approve a pending admin registration.
   * PATCH /api/v1/superadmin/admins/{admin_id}/approve
   * @param {string} adminId — UUID string
   * @returns {Promise<object>} ApproveAdminResponse
   */
  async function approveAdmin(adminId) {
    const res = await API.fetch(`/api/v1/superadmin/admins/${adminId}/approve`, {
      method: 'PATCH',
    });
    return _handleResponse(res, 'Failed to approve admin.');
  }

  /**
   * Deactivate an active admin (blocks login without deleting).
   * PATCH /api/v1/superadmin/admins/{admin_id}/deactivate
   * @param {string} adminId
   * @returns {Promise<{ message: string }>}
   */
  async function deactivateAdmin(adminId) {
    const res = await API.fetch(`/api/v1/superadmin/admins/${adminId}/deactivate`, {
      method: 'PATCH',
    });
    return _handleResponse(res, 'Failed to deactivate admin.');
  }

  /**
   * Soft-delete an admin account.
   * DELETE /api/v1/superadmin/admins/{admin_id}
   * @param {string} adminId
   * @returns {Promise<{ message: string }>}
   */
  async function deleteAdmin(adminId) {
    const res = await API.fetch(`/api/v1/superadmin/admins/${adminId}`, {
      method: 'DELETE',
    });
    return _handleResponse(res, 'Failed to delete admin.');
  }

  // ── System-wide user visibility ───────────────────────────────────────────

  /**
   * List every user in the system across all admins.
   * GET /api/v1/superadmin/users
   * @returns {Promise<{ users: object[], total: number }>}
   */
  async function listAllUsers() {
    const res = await API.fetch('/api/v1/superadmin/users');
    return _handleResponse(res, 'Failed to fetch users.');
  }

  /**
   * Get a specific user's profile (system-wide, not scoped to one admin).
   * GET /api/v1/superadmin/users/{user_id}
   * @param {string} userId — UUID string
   * @returns {Promise<object>} UserProfileResponse
   */
  async function getUser(userId) {
    const res = await API.fetch(`/api/v1/superadmin/users/${userId}`);
    return _handleResponse(res, 'Failed to fetch user profile.');
  }

  // ── Data ingestion ────────────────────────────────────────────────────────

  /**
   * Trigger a full re-ingestion of source data into the vector store.
   * POST /api/v1/superadmin/ingest
   * @returns {Promise<{ message: string }>}
   */
  async function reindexVectorStore() {
    const res = await API.fetch('/api/v1/superadmin/ingest', {
      method: 'POST',
    });
    return _handleResponse(res, 'Failed to trigger re-index.');
  }

  // ── Response helper ───────────────────────────────────────────────────────

  async function _handleResponse(res, fallback) {
    if (!res) throw new Error('No response — network error or session expired.');

    if (!res.ok) {
      let detail = fallback;
      try {
        const body = await res.json();
        detail = body.detail || fallback;
      } catch (_) { /* ignore */ }
      throw new Error(detail);
    }

    return res.json();
  }

  // ── Public interface ──────────────────────────────────────────────────────

  return {
    listAdmins,
    listPendingAdmins,
    approveAdmin,
    deactivateAdmin,
    deleteAdmin,
    listAllUsers,
    getUser,
    reindexVectorStore,
  };
})();