/**
 * Add the administrator credential without overriding ordinary caller
 * headers. Device credentials live in the HttpOnly pairing cookie; the
 * pairing module adds a legacy bearer only for its explicit /me migration.
 */
export const DEVICE_TOKEN_STORAGE_KEY = 'trinaxai-device-token';
const ADMIN_TOKEN_STORAGE_KEY = 'trinaxai-admin-token';
const DEVICE_SCOPES_STORAGE_KEY = 'trinaxai-device-scopes';
const REMOTE_DEVICE_SCOPES = new Set(['chat', 'read_private', 'web']);
export const DEVICE_ACCESS_REVOKED_EVENT = 'trinaxai-device-access-revoked';

export function isLocalHostBrowser(): boolean {
  try { return ['localhost', '127.0.0.1', '::1', '[::1]'].includes(window.location.hostname); }
  catch { return false; }
}

export function isLocalAuthority(): boolean {
  return isLocalHostBrowser();
}

export function deviceSessionHasScope(scope: string): boolean {
  if (isLocalHostBrowser()) return true;
  if (!REMOTE_DEVICE_SCOPES.has(scope)) return false;
  try {
    const parsed = JSON.parse(sessionStorage.getItem(DEVICE_SCOPES_STORAGE_KEY) || '[]');
    return Array.isArray(parsed) && parsed.includes(scope);
  } catch { return false; }
}

export function setDeviceSessionScopes(scopes: string[] | null): void {
  try {
    const safeScopes = [...new Set((scopes || []).filter((scope) => REMOTE_DEVICE_SCOPES.has(scope)))];
    if (safeScopes.length) sessionStorage.setItem(DEVICE_SCOPES_STORAGE_KEY, JSON.stringify(safeScopes));
    else sessionStorage.removeItem(DEVICE_SCOPES_STORAGE_KEY);
  } catch { /* session storage unavailable */ }
}

export function systemRequestHeaders(headers?: HeadersInit): Headers {
  const result = new Headers(headers);
  try {
    const stored = localStorage.getItem('tc-lang');
    const language = stored === 'es' || stored === 'en'
      ? stored
      : document.documentElement.lang.toLowerCase().startsWith('es') ? 'es' : 'en';
    if (!result.has('Accept-Language')) result.set('Accept-Language', language);
  } catch { /* document unavailable */ }
  try {
    const adminToken = sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY)?.trim();
    if (adminToken) {
      result.set('X-Admin-Token', adminToken);
      result.delete('X-TrinaxAI-Device-Token');
    }
  } catch { /* session storage unavailable */ }
  return result;
}

/** Compatibility hook: new device bearers are cookie-only and never stored. */
export function setDeviceSessionToken(token: string | null): void {
  try {
    if (!token?.trim()) {
      localStorage.removeItem(DEVICE_TOKEN_STORAGE_KEY);
      sessionStorage.removeItem(DEVICE_TOKEN_STORAGE_KEY);
      sessionStorage.removeItem(DEVICE_SCOPES_STORAGE_KEY);
    }
    window.dispatchEvent(new CustomEvent('trinaxai-device-auth-changed'));
  } catch { /* session storage unavailable */ }
}

/** Remove a legacy bearer after the backend has migrated it into a cookie. */
export function clearLegacyDeviceToken(): void {
  try {
    localStorage.removeItem(DEVICE_TOKEN_STORAGE_KEY);
    sessionStorage.removeItem(DEVICE_TOKEN_STORAGE_KEY);
  } catch { /* storage unavailable */ }
}

/** Clear a rejected device credential and return the UI to the authorization gate. */
export function clearRevokedDeviceSession(force = false): void {
  let hadCredential = false;
  try {
    hadCredential = Boolean(
      (localStorage.getItem(DEVICE_TOKEN_STORAGE_KEY) || sessionStorage.getItem(DEVICE_TOKEN_STORAGE_KEY))?.trim()
      || sessionStorage.getItem(DEVICE_SCOPES_STORAGE_KEY),
    );
    clearLegacyDeviceToken();
    sessionStorage.removeItem(DEVICE_SCOPES_STORAGE_KEY);
  } catch {
    if (!force) return;
  }
  if (hadCredential || force) window.dispatchEvent(new CustomEvent(DEVICE_ACCESS_REVOKED_EVENT));
}

/** Fetch a protected same-origin system/proxy route with browser credentials. */
export function systemFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  return fetch(input, { ...init, credentials: 'include', headers: systemRequestHeaders(init.headers) });
}
