/**
 * auth.js — Authentication state management.
 *
 * Exposes a single namespace: Auth
 *
 * Responsibilities:
 *   - Store and retrieve access/refresh tokens (localStorage).
 *   - POST /auth/login and handle errors.
 *   - POST /auth/logout (revoke refresh token) then clear local state.
 *   - Guard helpers used by other modules (hasSession, getAccessToken, etc.).
 *
 * Auth does NOT touch the DOM directly — it calls UI helpers for errors
 * and delegates page-state changes back to app.js via return values.
 */

'use strict';

const Auth = (() => {
  const ACCESS_KEY  = 'access_token';
  const REFRESH_KEY = 'refresh_token';

  // ── Token accessors ──────────────────────────────────────────────────────

  function getAccessToken()  { return localStorage.getItem(ACCESS_KEY);  }
  function getRefreshToken() { return localStorage.getItem(REFRESH_KEY); }
  function hasSession()      { return !!getAccessToken(); }

  function storeTokens(accessToken, refreshToken) {
    localStorage.setItem(ACCESS_KEY,  accessToken);
    localStorage.setItem(REFRESH_KEY, refreshToken);
  }

  function clearSession() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  }

  // ── Login ────────────────────────────────────────────────────────────────

  /**
   * Authenticate with the backend.
   * @param {string} email
   * @param {string} password
   * @returns {Promise<boolean>} — true on success, false on failure
   */
  async function login(email, password) {
    UI.clearAuthError();

    try {
      const res = await fetch(`${API.BASE_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        UI.showAuthError(err.detail || 'Login failed. Please check your credentials.');
        return false;
      }

      const data = await res.json();
      storeTokens(data.access_token, data.refresh_token);
      return true;
    } catch (err) {
      console.error('[Auth] Login error:', err);
      UI.showAuthError('Network error — could not reach the server.');
      return false;
    }
  }

  // ── Logout ───────────────────────────────────────────────────────────────

  /**
   * Revoke the refresh token on the server, then wipe local state.
   * Safe to call even if the server request fails.
   */
  async function logout() {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      // Best-effort server-side revocation — ignore failures
      await API.fetch('/auth/logout', {
        method: 'POST',
        body: { refresh_token: refreshToken },
      }).catch(() => {});
    }

    clearSession();
  }

  // ── Public interface ─────────────────────────────────────────────────────

  return {
    getAccessToken,
    getRefreshToken,
    hasSession,
    storeTokens,
    clearSession,
    login,
    logout,
  };
})();