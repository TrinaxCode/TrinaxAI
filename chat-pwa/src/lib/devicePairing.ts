import { APP_CONFIG } from './config';
import { apiErrorFromPayload } from './api';
import {
  DEVICE_TOKEN_STORAGE_KEY,
  clearRevokedDeviceSession,
  clearLegacyDeviceToken,
  deviceSessionHasScope,
  isLocalHostBrowser,
  setDeviceSessionScopes,
  systemRequestHeaders,
} from './authHeaders';

export type PairedDevice = {
  id: string;
  name: string;
  scopes: string[];
  created_at: number;
  last_seen_at: number | null;
  expires_at: number | null;
  revoked_at: number | null;
};

export type PairingCode = {
  code: string;
  expires_at: number;
  scopes: string[];
};

/** Read a pre-cookie bearer only for the explicit /me compatibility path. */
function legacyDeviceToken(): string {
  try {
    return (localStorage.getItem(DEVICE_TOKEN_STORAGE_KEY)
      || sessionStorage.getItem(DEVICE_TOKEN_STORAGE_KEY))?.trim() || '';
  }
  catch { return ''; }
}

function hasDeviceCredential(): boolean {
  return Boolean(legacyDeviceToken())
    || deviceSessionHasScope('chat')
    || deviceSessionHasScope('read_private')
    || deviceSessionHasScope('web');
}

function pairingFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  return fetch(input, { ...init, credentials: 'include' });
}

let revocationMonitorStarted = false;
let revocationMonitorCleanup: (() => void) | null = null;
const REVOCATION_RETRY_DELAY_MS = 30_000;
const REVOCATION_MAX_RETRY_DELAY_MS = 5 * 60_000;

/** Check on lifecycle events and retry slowly while the paired app is open. */
export function startDeviceRevocationMonitor(): () => void {
  if (revocationMonitorStarted) return revocationMonitorCleanup ?? (() => undefined);
  revocationMonitorStarted = true;
  let retryDelay = REVOCATION_RETRY_DELAY_MS;
  let retryTimer: number | undefined;
  let requestInFlight = false;
  let active = true;

  const scheduleRetry = () => {
    window.clearTimeout(retryTimer);
    retryTimer = undefined;
    if (active && !document.hidden && navigator.onLine !== false && hasDeviceCredential() && !isLocalHostBrowser()) {
      retryTimer = window.setTimeout(check, retryDelay);
    }
  };

  const check = () => {
    // The localhost origin is the privileged host UI, not a paired device.
    // Never send a stale device credential to its own pairing endpoint.
    if (!active || isLocalHostBrowser() || document.hidden || navigator.onLine === false || !hasDeviceCredential() || requestInFlight) return;
    requestInFlight = true;
    void getCurrentPairedDevice()
      .then(() => { retryDelay = REVOCATION_RETRY_DELAY_MS; })
      .catch(() => {
        retryDelay = Math.min(REVOCATION_MAX_RETRY_DELAY_MS, retryDelay * 2);
      })
      .finally(() => {
        requestInFlight = false;
        scheduleRetry();
      });
  };

  const onWake = () => {
    window.clearTimeout(retryTimer);
    retryTimer = undefined;
    if (document.hidden) return;
    retryDelay = REVOCATION_RETRY_DELAY_MS;
    check();
  };

  check();
  document.addEventListener('visibilitychange', onWake);
  window.addEventListener('focus', onWake);
  window.addEventListener('online', onWake);
  window.addEventListener('trinaxai-device-auth-changed', onWake);
  revocationMonitorCleanup = () => {
    active = false;
    window.clearTimeout(retryTimer);
    document.removeEventListener('visibilitychange', onWake);
    window.removeEventListener('focus', onWake);
    window.removeEventListener('online', onWake);
    window.removeEventListener('trinaxai-device-auth-changed', onWake);
    revocationMonitorStarted = false;
    revocationMonitorCleanup = null;
  };
  return revocationMonitorCleanup;
}

/** Generate a one-time code from the local host PWA. */
export async function createPairingCode(): Promise<PairingCode> {
  const response = await pairingFetch(`${APP_CONFIG.ragBase}/v1/pairing/start`, {
    method: 'POST',
    headers: systemRequestHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ scopes: ['chat', 'read_private', 'web'], ttl_seconds: 300 }),
  });
  const payload = await responseJson(response);
  if (typeof payload.code !== 'string') throw new Error('Pairing code was not generated.');
  return {
    code: payload.code,
    expires_at: Number(payload.expires_at || 0),
    scopes: Array.isArray(payload.scopes) ? payload.scopes.map(String) : [],
  };
}

/** The local host can inventory and revoke every authorized device. */
export async function listPairedDevices(): Promise<PairedDevice[]> {
  const response = await pairingFetch(`${APP_CONFIG.ragBase}/v1/pairing/devices`, {
    headers: systemRequestHeaders(),
  });
  const payload = await responseJson(response);
  return Array.isArray(payload.devices) ? payload.devices as PairedDevice[] : [];
}

export async function revokePairedDevice(deviceId: string): Promise<void> {
  const response = await pairingFetch(`${APP_CONFIG.ragBase}/v1/pairing/devices/${encodeURIComponent(deviceId)}`, {
    method: 'DELETE',
    headers: systemRequestHeaders(),
  });
  await responseJson(response);
}

async function responseJson(response: Response): Promise<Record<string, unknown>> {
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
  if (!response.ok) throw apiErrorFromPayload(response.status, payload);
  return payload;
}

export async function claimDevice(code: string, deviceName: string): Promise<PairedDevice> {
  const response = await pairingFetch(`${APP_CONFIG.ragBase}/v1/pairing/claim`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, device_name: deviceName }),
  });
  const payload = await responseJson(response);
  if (!payload.device) throw new Error('Pairing response did not include device metadata.');
  const device = payload.device as PairedDevice;
  clearLegacyDeviceToken();
  setDeviceSessionScopes(device.scopes);
  window.dispatchEvent(new Event('trinaxai-device-auth-changed'));
  return device;
}

export async function getCurrentPairedDevice(): Promise<PairedDevice | null> {
  const token = legacyDeviceToken();
  const hadSession = hasDeviceCredential();
  const response = await pairingFetch(`${APP_CONFIG.ragBase}/v1/pairing/me`, {
    headers: token ? { 'X-TrinaxAI-Device-Token': token } : undefined,
  });
  if (response.status === 403) {
    clearRevokedDeviceSession(Boolean(token) || hadSession);
    return null;
  }
  const payload = await responseJson(response);
  const device = payload.device as PairedDevice;
  // Transparently migrate a legacy header into the HttpOnly cookie set by /me.
  if (token) clearLegacyDeviceToken();
  setDeviceSessionScopes(device.scopes);
  window.dispatchEvent(new Event('trinaxai-device-auth-changed'));
  return device;
}

export async function revokeCurrentPairedDevice(): Promise<void> {
  const token = legacyDeviceToken();
  const hadSession = hasDeviceCredential();
  const response = await pairingFetch(`${APP_CONFIG.ragBase}/v1/pairing/me`, {
    method: 'DELETE',
    headers: token ? { 'X-TrinaxAI-Device-Token': token } : undefined,
  });
  if (response.status === 403) {
    clearRevokedDeviceSession(Boolean(token) || hadSession);
    throw apiErrorFromPayload(response.status, await response.json().catch(() => ({})));
  }
  await responseJson(response);
  clearRevokedDeviceSession(true);
}
