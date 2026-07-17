import { afterEach, describe, expect, it, vi } from 'vitest';
import { setDeviceSessionToken, systemFetch, systemRequestHeaders } from './authHeaders';

describe('protected proxy request helpers', () => {
  afterEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it('merges caller headers with the current session credential', async () => {
    sessionStorage.setItem('trinaxai-admin-token', ' proxy-secret ');
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await systemFetch('/api/ollama/api/pull', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    const headers = fetchMock.mock.calls[0][1]?.headers as Headers;
    expect(headers.get('X-Admin-Token')).toBe('proxy-secret');
    expect(headers.get('Content-Type')).toBe('application/json');
    expect(systemRequestHeaders({ Accept: 'application/json' }).get('Accept')).toBe('application/json');
  });

  it('uses a paired-device credential when no administrator token is present', () => {
    setDeviceSessionToken(' txd_device-secret ');
    const headers = systemRequestHeaders({ Accept: 'application/json' });
    expect(headers.get('X-TrinaxAI-Device-Token')).toBe('txd_device-secret');
    expect(headers.get('X-Admin-Token')).toBeNull();
  });

  it('never sends two competing bearer credentials', () => {
    setDeviceSessionToken('device-secret');
    sessionStorage.setItem('trinaxai-admin-token', 'admin-secret');
    const headers = systemRequestHeaders();
    expect(headers.get('X-Admin-Token')).toBe('admin-secret');
    expect(headers.get('X-TrinaxAI-Device-Token')).toBeNull();
  });
});
