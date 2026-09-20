import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  WEB_SEARCH_SETTINGS_EVENT,
  apiJson,
  deleteWebSearchCredential,
  getWebSearchSettings,
  notifyWebSearchSettingsUpdated,
  resetWebSearchSettings,
  saveWebSearchSettings,
  startLocalAi,
  testWebSearchProvider,
  validateIndexJobStatus,
} from './api_http';

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe('HTTP API helpers', () => {
  it('returns JSON and adds system headers without replacing caller headers', async () => {
    sessionStorage.setItem('trinaxai-admin-token', 'admin-token');
    const fetchMock = vi.fn().mockResolvedValue(Response.json({ ok: true }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiJson('/endpoint', { headers: { 'X-Custom': 'yes' } })).resolves.toEqual({ ok: true });

    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get('X-Custom')).toBe('yes');
    expect(headers.get('X-Admin-Token')).toBe('admin-token');
    expect(headers.get('Accept-Language')).toBeTruthy();
    expect(fetchMock.mock.calls[0][1].credentials).toBe('include');
  });

  it('retries a safe network failure once', async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new TypeError('offline'))
      .mockResolvedValueOnce(Response.json({ ok: true }));
    vi.stubGlobal('fetch', fetchMock);

    const pending = apiJson('/endpoint');
    await vi.advanceTimersByTimeAsync(250);

    await expect(pending).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('does not retry unsafe or aborted requests', async () => {
    const abort = new DOMException('cancelled', 'AbortError');
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError('offline')).mockRejectedValueOnce(abort);
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiJson('/endpoint', { method: 'POST' })).rejects.toMatchObject({ status: 0 });
    await expect(apiJson('/endpoint', { signal: new AbortController().signal })).rejects.toBe(abort);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('normalizes HTTP failures and invalid JSON', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: { code: 'invalid_credential' } }), { status: 401 }))
      .mockResolvedValueOnce(new Response('not-json', { status: 200 })));

    await expect(apiJson('/endpoint', { method: 'POST' })).rejects.toMatchObject({
      status: 401, category: 'authentication_failed',
    });
    await expect(apiJson('/endpoint', { method: 'POST' })).rejects.toMatchObject({
      status: 200, category: 'internal_server_error',
    });
  });

  it('starts local AI only for an explicit successful payload', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(Response.json({ ok: true }))
      .mockResolvedValueOnce(new Response('not-json', { status: 200 }))
      .mockRejectedValueOnce(new TypeError('offline'));
    vi.stubGlobal('fetch', fetchMock);

    await expect(startLocalAi()).resolves.toBeUndefined();
    await expect(startLocalAi()).rejects.toMatchObject({ errorCode: 'ERR_EXTERNAL_SERVICE_UNAVAILABLE' });
    await expect(startLocalAi()).rejects.toMatchObject({ status: 0, errorCode: 'ERR_EXTERNAL_SERVICE_UNAVAILABLE' });
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'POST', credentials: 'include' });
  });

  it('wraps web-search settings endpoints and emits updates', async () => {
    const settings = { enabled: true, preferred_provider: 'duckduckgo' };
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(Response.json(settings)));
    vi.stubGlobal('fetch', fetchMock);
    const listener = vi.fn();
    window.addEventListener(WEB_SEARCH_SETTINGS_EVENT, listener);

    await getWebSearchSettings();
    await saveWebSearchSettings({ enabled: false, preferred_provider: 'brave', brave_api_key: 'key' });
    await testWebSearchProvider('searxng');
    await deleteWebSearchCredential('brave');
    await resetWebSearchSettings();
    notifyWebSearchSettingsUpdated(settings as never);

    expect(fetchMock.mock.calls.map((call) => call[1]?.method || 'GET')).toEqual(['GET', 'PUT', 'POST', 'DELETE', 'DELETE']);
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({ enabled: false, preferred_provider: 'brave' });
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({ provider: 'searxng' });
    expect(listener).toHaveBeenCalledOnce();
    expect((listener.mock.calls[0][0] as CustomEvent).detail).toEqual(settings);
    window.removeEventListener(WEB_SEARCH_SETTINGS_EVENT, listener);
  });

  it('validates and normalizes index job status fields', () => {
    expect(() => validateIndexJobStatus(null)).toThrow();
    expect(() => validateIndexJobStatus({ id: 1, status: 'running' })).toThrow();

    expect(validateIndexJobStatus({
      id: 'job', status: 'running', projects: [1, 'two'], indexed: 1,
      failures: [{ path: 'bad.pdf', reason: 'broken' }, { path: 1, reason: 'ignored' }],
      progress: 50, pages_total: 4, recent_activity: 'chunking', retry_recommended: true,
    })).toMatchObject({
      id: 'job', status: 'running', label: '', projects: ['1', 'two'], indexed: true,
      progress: 50, pages_total: 4, pages_processed: 0, recent_activity: 'chunking',
      failures: [{ path: 'bad.pdf', reason: 'broken' }], retry_recommended: true,
    });
  });
});
