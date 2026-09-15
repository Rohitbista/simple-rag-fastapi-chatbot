/**
 * api.js — Authenticated fetch wrapper.
 *
 * Exposes a single namespace: API
 *
 * API.fetch(endpoint, options)
 *   - Attaches the current access token as a Bearer header.
 *   - On 401, attempts one silent token refresh via /auth/refresh.
 *   - If refresh fails, calls Auth.logout() and returns null.
 *   - Automatically serialises plain objects as JSON and sets Content-Type.
 *
 * API.BASE_URL
 *   - Adjust to point at your backend (default: http://localhost:8000).
 */

'use strict';

const API = (() => {
  const BASE_URL = 'http://localhost:8000'; // Change to your backend URL

  /**
   * Core fetch wrapper.
   * @param {string} endpoint  — path relative to BASE_URL, e.g. '/auth/login'
   * @param {RequestInit} [options]
   * @returns {Promise<Response|null>}
   */
  async function apiFetch(endpoint, options = {}) {
    options.headers = options.headers || {};

    const token = Auth.getAccessToken();
    if (token) {
      options.headers['Authorization'] = `Bearer ${token}`;
    }

    // Auto-serialise plain-object bodies
    if (
      options.body &&
      typeof options.body === 'object' &&
      !(options.body instanceof FormData)
    ) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }

    let response = await fetch(`${BASE_URL}${endpoint}`, options);

    // Silent token refresh on 401
    if (response.status === 401 && Auth.getRefreshToken()) {
      const refreshed = await _tryRefresh();
      if (refreshed) {
        options.headers['Authorization'] = `Bearer ${Auth.getAccessToken()}`;
        response = await fetch(`${BASE_URL}${endpoint}`, options);
      } else {
        Auth.clearSession();
        UI.showAuthModal();
        return null;
      }
    }

    return response;
  }

  /**
   * Attempt to exchange the stored refresh token for a new token pair.
   * Updates Auth storage on success.
   * @returns {Promise<boolean>}
   */
  async function _tryRefresh() {
    try {
      const res = await fetch(`${BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: Auth.getRefreshToken() }),
      });

      if (res.ok) {
        const data = await res.json();
        Auth.storeTokens(data.access_token, data.refresh_token);
        return true;
      }
    } catch (err) {
      console.error('[API] Token refresh failed:', err);
    }
    return false;
  }

  return {
    BASE_URL,
    fetch: apiFetch,
  };
})();