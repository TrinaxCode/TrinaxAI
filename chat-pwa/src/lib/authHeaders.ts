/**
 * Add the strongest available per-session credential without overriding
 * ordinary caller headers. Device tokens intentionally live in sessionStorage:
 * closing the browser removes the bearer credential from that browser session.
 */
export const DEVICE_TOKEN_STORAGE_KEY = 'trinaxai-device-token';
export const ADMIN_TOKEN_STORAGE_KEY = 'trinaxai-admin-token';
export const DEVICE_SCOPES_STORAGE_KEY = 'trinaxai-device-scopes';
export const DEVICE_ACCESS_REVOKED_EVENT = 'trinaxai-device-access-revoked';

export function isLocalHostBrowser(): boolean {
  try { return ['localhost', '127.0.0.1', '::1', '[::1]'].includes(window.location.hostname); }
  catch { return false; }
}

export function deviceSessionHasScope(scope: string): boolean {
  if (isLocalHostBrowser()) return true;
  try {
    const parsed = JSON.parse(sessionStorage.getItem(DEVICE_SCOPES_STORAGE_KEY) || '[]');
    return Array.isArray(parsed) && parsed.includes(scope);
  } catch { return false; }
}

export function setDeviceSessionScopes(scopes: string[] | null): void {
  try {
    if (scopes?.length) sessionStorage.setItem(DEVICE_SCOPES_STORAGE_KEY, JSON.stringify(scopes));
    else sessionStorage.removeItem(DEVICE_SCOPES_STORAGE_KEY);
  } catch { /* session storage unavailable */ }
}

export function systemRequestHeaders(headers?: HeadersInit): Headers {
  const result = new Headers(headers);
  try {
    const adminToken = sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY)?.trim();
    const deviceToken = (
      localStorage.getItem(DEVICE_TOKEN_STORAGE_KEY)
      || sessionStorage.getItem(DEVICE_TOKEN_STORAGE_KEY)
    )?.trim();
    if (adminToken) {
      result.set('X-Admin-Token', adminToken);
      result.delete('X-TrinaxAI-Device-Token');
    } else if (deviceToken) {
      result.set('X-TrinaxAI-Device-Token', deviceToken);
    }
  } catch { /* session storage unavailable */ }
  return result;
}

export function setDeviceSessionToken(token: string | null): void {
  try {
    const value = token?.trim();
    if (value) {
      // A paired device must retain its identity across browser/PWA restarts so
      // the host can later revoke and remotely wipe that specific device.
      localStorage.setItem(DEVICE_TOKEN_STORAGE_KEY, value);
      sessionStorage.removeItem(DEVICE_TOKEN_STORAGE_KEY);
    }
    else {
      localStorage.removeItem(DEVICE_TOKEN_STORAGE_KEY);
      sessionStorage.removeItem(DEVICE_TOKEN_STORAGE_KEY);
      sessionStorage.removeItem(DEVICE_SCOPES_STORAGE_KEY);
    }
    window.dispatchEvent(new CustomEvent('trinaxai-device-auth-changed'));
  } catch { /* session storage unavailable */ }
}

/** Clear a rejected device credential and return the UI to the authorization gate. */
export function clearRevokedDeviceSession(): void {
  try {
    if (!(localStorage.getItem(DEVICE_TOKEN_STORAGE_KEY) || sessionStorage.getItem(DEVICE_TOKEN_STORAGE_KEY))?.trim()) return;
  } catch { return; }
  setDeviceSessionToken(null);
  window.dispatchEvent(new CustomEvent(DEVICE_ACCESS_REVOKED_EVENT));
}

/** Fetch a protected same-origin system/proxy route with the session token. */
export function systemFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  return fetch(input, { ...init, headers: systemRequestHeaders(init.headers) });
}
