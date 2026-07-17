import { afterEach, describe, expect, it, vi } from 'vitest';

import { DEVICE_TOKEN_STORAGE_KEY } from './authHeaders';
import { claimDevice, getCurrentPairedDevice, revokeCurrentPairedDevice } from './devicePairing';

const device = {
  id: '0123456789abcdef01234567',
  name: 'Tablet',
  scopes: ['chat', 'read_private'],
  created_at: 1,
  last_seen_at: null,
  expires_at: null,
  revoked_at: null,
};

describe('device pairing client', () => {
  afterEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it('stores the device bearer persistently so revocation survives a PWA restart', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ok: true,
      token: 'txd_token',
      device,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);

    expect(await claimDevice('ABCD-EFGH', 'Tablet')).toEqual(device);
    expect(localStorage.getItem(DEVICE_TOKEN_STORAGE_KEY)).toBe('txd_token');
    expect(sessionStorage.getItem(DEVICE_TOKEN_STORAGE_KEY)).toBeNull();
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      code: 'ABCD-EFGH',
      device_name: 'Tablet',
    });
  });

  it('removes revoked or rejected credentials from the session', async () => {
    const revoked = vi.fn();
    window.addEventListener('trinaxai-device-access-revoked', revoked, { once: true });
    localStorage.setItem(DEVICE_TOKEN_STORAGE_KEY, 'expired');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 403 })));
    expect(await getCurrentPairedDevice()).toBeNull();
    expect(sessionStorage.getItem(DEVICE_TOKEN_STORAGE_KEY)).toBeNull();
    expect(localStorage.getItem(DEVICE_TOKEN_STORAGE_KEY)).toBeNull();
    expect(revoked).toHaveBeenCalledOnce();
  });

  it('revokes itself with the device credential and then erases it', async () => {
    const revoked = vi.fn();
    window.addEventListener('trinaxai-device-access-revoked', revoked, { once: true });
    localStorage.setItem(DEVICE_TOKEN_STORAGE_KEY, 'txd_token');
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true, device }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);
    await revokeCurrentPairedDevice();
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      method: 'DELETE',
      headers: { 'X-TrinaxAI-Device-Token': 'txd_token' },
    });
    expect(sessionStorage.getItem(DEVICE_TOKEN_STORAGE_KEY)).toBeNull();
    expect(localStorage.getItem(DEVICE_TOKEN_STORAGE_KEY)).toBeNull();
    expect(revoked).toHaveBeenCalledOnce();
  });
});
