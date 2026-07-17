import { APP_CONFIG } from './config';
import {
  DEVICE_TOKEN_STORAGE_KEY,
  clearRevokedDeviceSession,
  setDeviceSessionToken,
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

function currentToken(): string {
  try {
    return (localStorage.getItem(DEVICE_TOKEN_STORAGE_KEY)
      || sessionStorage.getItem(DEVICE_TOKEN_STORAGE_KEY))?.trim() || '';
  }
  catch { return ''; }
}

let revocationMonitorStarted = false;
let revocationMonitorCleanup: (() => void) | null = null;

/** Check frequently enough that revoking an online phone feels immediate. */
export function startDeviceRevocationMonitor(): () => void {
  if (revocationMonitorStarted) return revocationMonitorCleanup ?? (() => undefined);
  revocationMonitorStarted = true;
  const check = () => {
    if (!document.hidden && currentToken()) void getCurrentPairedDevice().catch(() => undefined);
  };
  check();
  const interval = window.setInterval(check, 2000);
  document.addEventListener('visibilitychange', check);
  window.addEventListener('online', check);
  revocationMonitorCleanup = () => {
    window.clearInterval(interval);
    document.removeEventListener('visibilitychange', check);
    window.removeEventListener('online', check);
    revocationMonitorStarted = false;
    revocationMonitorCleanup = null;
  };
  return revocationMonitorCleanup;
}

/** Generate a one-time code from the local host PWA. */
export async function createPairingCode(): Promise<PairingCode> {
  const response = await fetch(`${APP_CONFIG.ragBase}/v1/pairing/start`, {
    method: 'POST',
    headers: systemRequestHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ scopes: ['chat', 'read_private', 'index', 'system', 'agent'], ttl_seconds: 300 }),
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
  const response = await fetch(`${APP_CONFIG.ragBase}/v1/pairing/devices`, {
    headers: systemRequestHeaders(),
  });
  const payload = await responseJson(response);
  return Array.isArray(payload.devices) ? payload.devices as PairedDevice[] : [];
}

export async function revokePairedDevice(deviceId: string): Promise<void> {
  const response = await fetch(`${APP_CONFIG.ragBase}/v1/pairing/devices/${encodeURIComponent(deviceId)}`, {
    method: 'DELETE',
    headers: systemRequestHeaders(),
  });
  await responseJson(response);
}

async function responseJson(response: Response): Promise<Record<string, unknown>> {
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
  if (!response.ok) {
    const en = typeof document !== 'undefined' && document.documentElement.lang.toLowerCase().startsWith('en');
    const detail = response.status === 401 || response.status === 403
      ? en ? 'This device does not have permission for that action. Pair it from your main device using a new code.' : 'Este dispositivo no tiene permiso para esta acción. Vincúlalo desde tu dispositivo principal usando un código nuevo.'
      : typeof payload.detail === 'string' ? payload.detail : en ? `The action could not be completed (code ${response.status}).` : `No se pudo completar la acción (código ${response.status}).`;
    throw new Error(detail);
  }
  return payload;
}

export async function claimDevice(code: string, deviceName: string): Promise<PairedDevice> {
  const response = await fetch(`${APP_CONFIG.ragBase}/v1/pairing/claim`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, device_name: deviceName }),
  });
  const payload = await responseJson(response);
  const token = typeof payload.token === 'string' ? payload.token : '';
  if (!token || !payload.device) throw new Error('Pairing response did not include a device token.');
  try {
    if (localStorage.getItem(DEVICE_TOKEN_STORAGE_KEY) !== token) setDeviceSessionToken(token);
  } catch { /* storage unavailable */ }
  const device = payload.device as PairedDevice;
  setDeviceSessionScopes(device.scopes);
  return device;
}

export async function getCurrentPairedDevice(): Promise<PairedDevice | null> {
  const token = currentToken();
  if (!token) return null;
  const response = await fetch(`${APP_CONFIG.ragBase}/v1/pairing/me`, {
    headers: { 'X-TrinaxAI-Device-Token': token },
  });
  if (response.status === 403) {
    clearRevokedDeviceSession();
    return null;
  }
  const payload = await responseJson(response);
  const device = payload.device as PairedDevice;
  // Transparently migrate devices paired by older builds from session-only
  // storage to the persistent per-device identity required for later wipe.
  try {
    if (localStorage.getItem(DEVICE_TOKEN_STORAGE_KEY) !== token) setDeviceSessionToken(token);
  } catch { /* storage unavailable */ }
  setDeviceSessionScopes(device.scopes);
  return device;
}

export async function revokeCurrentPairedDevice(): Promise<void> {
  const token = currentToken();
  if (!token) return;
  const response = await fetch(`${APP_CONFIG.ragBase}/v1/pairing/me`, {
    method: 'DELETE',
    headers: { 'X-TrinaxAI-Device-Token': token },
  });
  await responseJson(response);
  clearRevokedDeviceSession();
}
