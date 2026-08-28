import { afterEach, describe, expect, it, vi } from 'vitest';
import { deviceSessionHasScope, setDeviceSessionScopes, setDeviceSessionToken, systemFetch, systemRequestHeaders } from './authHeaders';

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
    expect(fetchMock.mock.calls[0][1]?.credentials).toBe('include');
    expect(systemRequestHeaders({ Accept: 'application/json' }).get('Accept')).toBe('application/json');
  });

  it('does not add legacy device storage to ordinary requests', () => {
    localStorage.setItem('trinaxai-device-token', ' txd_device-secret ');
    sessionStorage.setItem('trinaxai-device-token', ' txd_session-secret ');
    const headers = systemRequestHeaders({ Accept: 'application/json' });
    expect(headers.get('X-TrinaxAI-Device-Token')).toBeNull();
    expect(headers.get('X-Admin-Token')).toBeNull();
  });

  it('does not persist a newly received device token in browser storage', () => {
    setDeviceSessionToken('txd_new-secret');

    expect(localStorage.getItem('trinaxai-device-token')).toBeNull();
    expect(sessionStorage.getItem('trinaxai-device-token')).toBeNull();
  });

  it('never sends two competing bearer credentials', () => {
    setDeviceSessionToken('device-secret');
    sessionStorage.setItem('trinaxai-admin-token', 'admin-secret');
    const headers = systemRequestHeaders();
    expect(headers.get('X-Admin-Token')).toBe('admin-secret');
    expect(headers.get('X-TrinaxAI-Device-Token')).toBeNull();
  });

  it('does not retain retired elevated scopes from an older pairing response', () => {
    setDeviceSessionScopes(['chat', 'read_private', 'web', 'system', 'index', 'agent', 'agent_yolo']);

    expect(JSON.parse(sessionStorage.getItem('trinaxai-device-scopes') || '[]')).toEqual([
      'chat', 'read_private', 'web',
    ]);
  });

  it('ignores retired scopes left in storage by an older PWA', () => {
    sessionStorage.setItem('trinaxai-device-scopes', JSON.stringify(['chat', 'system', 'agent']));
    vi.stubGlobal('window', { location: { hostname: '192.168.1.20' } });

    expect(deviceSessionHasScope('chat')).toBe(true);
    expect(deviceSessionHasScope('system')).toBe(false);
    expect(deviceSessionHasScope('agent')).toBe(false);
  });
});
