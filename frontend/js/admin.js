/**
 * admin.js — Admin-role user management.
 *
 * Exposes a single namespace: Admin
 *
 * Only called when the authenticated user's role is ADMIN or SUPERADMIN.
 * All functions hit /api/v1/admin/* endpoints.
 *
 * Responsibilities:
 *   - Create a new user under the current admin.
 *   - List users belonging to this admin.
 *   - Fetch a single user's profile.
 *   - Deactivate a user (blocks login without deleting).
 *   - Soft-delete a user.
 *
 * None of these functions render UI directly — they return data or throw,
 * and the caller is responsible for updating the DOM.
 */

'use strict';

const Admin = (() => {

  // ── User creation ─────────────────────────────────────────────────────────

  /**
   * Create a new user under the current admin.
   * POST /api/v1/admin/users
   *
   * @param {{ email: string, username: string, password: string }} payload
   * @returns {Promise<object>} UserProfileResponse
   */
  async function createUser(payload) {
    const res = await API.fetch('/api/v1/admin/users', {
      method: 'POST',
      body: payload,
    });
    return _handleResponse(res, 'Failed to create user.');
  }

  // ── User listing ──────────────────────────────────────────────────────────

  /**
   * Fetch all users created by the current admin.
   * GET /api/v1/admin/users
   *
   * @returns {Promise<{ users: object[], total: number }>}
   */
  async function listUsers() {
    const res = await API.fetch('/api/v1/admin/users');
    return _handleResponse(res, 'Failed to fetch users.');
  }

  // ── Single user ───────────────────────────────────────────────────────────

  /**
   * Fetch a single user's profile (must belong to this admin).
   * GET /api/v1/admin/users/{user_id}
   *
   * @param {string} userId — UUID string
   * @returns {Promise<object>} UserProfileResponse
   */
  async function getUser(userId) {
    const res = await API.fetch(`/api/v1/admin/users/${userId}`);
    return _handleResponse(res, 'Failed to fetch user profile.');
  }

  // ── Deactivate ────────────────────────────────────────────────────────────

  /**
   * Deactivate a user (blocks login without deleting the account).
   * PATCH /api/v1/admin/users/{user_id}/deactivate
   *
   * @param {string} userId
   * @returns {Promise<{ message: string }>}
   */
  async function deactivateUser(userId) {
    const res = await API.fetch(`/api/v1/admin/users/${userId}/deactivate`, {
      method: 'PATCH',
    });
    return _handleResponse(res, 'Failed to deactivate user.');
  }

  // ── Delete ────────────────────────────────────────────────────────────────

  /**
   * Soft-delete a user.
   * DELETE /api/v1/admin/users/{user_id}
   *
   * @param {string} userId
   * @returns {Promise<{ message: string }>}
   */
  async function deleteUser(userId) {
    const res = await API.fetch(`/api/v1/admin/users/${userId}`, {
      method: 'DELETE',
    });
    return _handleResponse(res, 'Failed to delete user.');
  }

  // ── Response helper ───────────────────────────────────────────────────────

  /**
   * Parse a response or throw a descriptive error.
   * @param {Response|null} res
   * @param {string} fallback
   */
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
    createUser,
    listUsers,
    getUser,
    deactivateUser,
    deleteUser,
  };
})();