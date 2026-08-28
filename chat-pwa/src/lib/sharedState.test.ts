import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { syncSharedStateOnce } from './sharedState';

interface MockResponseOptions {
  status?: number;
  body?: Record<string, unknown>;
  etag?: string;
}

function mockResponse({ status = 200, body = {}, etag }: MockResponseOptions = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers(etag ? { ETag: etag } : undefined),
    json: async () => body,
  };
}

describe('versioned shared state synchronization', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
    sessionStorage.setItem('trinaxai-admin-token', 'sync-secret');
  });

  afterEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('syncs supported state keys without treating every tc-* value as shared state', async () => {
    localStorage.setItem('tc-theme', 'dark');
    localStorage.setItem('tc-models-vision-quality', 'balanced');
    localStorage.setItem('tc-private-extension-state', 'must stay local');
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit = {}) => {
      if (init.method === 'PUT') {
        return Promise.resolve(mockResponse({
          body: { ok: true, schema_version: 2, revision: 1, applied: true },
          etag: '"trinaxai-app-state-v2-1"',
        }));
      }
      return Promise.resolve(mockResponse({
        body: {
          ok: true,
          schema_version: 2,
          revision: 0,
          values: { 'tc-private-remote-state': 'must stay remote' },
        },
        etag: '"trinaxai-app-state-v2-0"',
      }));
    });
    vi.stubGlobal('fetch', fetchMock);

    await syncSharedStateOnce(1000, true);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const readHeaders = fetchMock.mock.calls[0][1]?.headers as Headers;
    const writeHeaders = fetchMock.mock.calls[1][1]?.headers as Headers;
    expect(readHeaders.get('X-Admin-Token')).toBe('sync-secret');
    expect(writeHeaders.get('X-Admin-Token')).toBe('sync-secret');
    expect(writeHeaders.get('Content-Type')).toBe('application/json');
    expect(writeHeaders.get('If-Match')).toBe('"trinaxai-app-state-v2-0"');
    expect(JSON.parse(fetchMock.mock.calls[1][1]?.body as string)).toMatchObject({
      schema_version: 2,
      base_revision: 0,
      operations: [
        { op: 'set', key: 'tc-models-vision-quality', value: 'balanced' },
        { op: 'set', key: 'tc-theme', value: 'dark' },
      ],
    });
    expect(JSON.stringify(fetchMock.mock.calls[1][1]?.body)).not.toContain('tc-private-extension-state');
    expect(localStorage.getItem('tc-private-remote-state')).toBeNull();

    sessionStorage.setItem('tc-session-only', 'secret');
    await syncSharedStateOnce(1000, true);
    expect(fetchMock.mock.calls.filter((call) => call[1]?.method === 'PUT')).toHaveLength(1);
  });

  it('detects local set/delete changes between syncs without patching Storage.prototype', async () => {
    const originalSetItem = Storage.prototype.setItem;
    const originalRemoveItem = Storage.prototype.removeItem;
    let readCount = 0;
    let writeCount = 0;
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit = {}) => {
      if (init.method === 'PUT') {
        writeCount += 1;
        return Promise.resolve(mockResponse({
          body: { ok: true, schema_version: 2, revision: writeCount, applied: true },
          etag: `"trinaxai-app-state-v2-${writeCount}"`,
        }));
      }
      readCount += 1;
      return Promise.resolve(readCount === 1
        ? mockResponse({ body: { ok: true, schema_version: 2, revision: 0, values: {} } })
        : mockResponse({ status: 304 }));
    });
    vi.stubGlobal('fetch', fetchMock);

    await syncSharedStateOnce(1000, true);
    sessionStorage.setItem('tc-theme', 'session-only');
    localStorage.setItem('tc-theme', 'dark');
    await syncSharedStateOnce(1000, true);
    localStorage.removeItem('tc-theme');
    await syncSharedStateOnce(1000, true);

    const puts = fetchMock.mock.calls.filter((call) => call[1]?.method === 'PUT');
    expect(puts).toHaveLength(2);
    expect(JSON.parse(puts[0][1]?.body as string).operations).toEqual([
      { op: 'set', key: 'tc-theme', value: 'dark' },
    ]);
    expect(JSON.parse(puts[1][1]?.body as string).operations).toEqual([
      { op: 'delete', key: 'tc-theme' },
    ]);
    expect(sessionStorage.getItem('tc-theme')).toBe('session-only');
    expect(Storage.prototype.setItem).toBe(originalSetItem);
    expect(Storage.prototype.removeItem).toBe(originalRemoveItem);
  });

  it('migrates legacy local preferences while removing timestamp metadata', async () => {
    localStorage.setItem('tc-user-name', 'Ada');
    localStorage.setItem('tc-sync-meta', JSON.stringify({ 'tc-user-name': { updatedAt: 1, hash: 'old' } }));
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit = {}) => init.method === 'PUT'
      ? Promise.resolve(mockResponse({
        body: { ok: true, schema_version: 2, revision: 1, applied: true },
        etag: '"trinaxai-app-state-v2-1"',
      }))
      : Promise.resolve(mockResponse({
        body: { ok: true, schema_version: 2, revision: 0, values: {} },
        etag: '"trinaxai-app-state-v2-0"',
      })));
    vi.stubGlobal('fetch', fetchMock);

    await syncSharedStateOnce(1000, true);

    expect(localStorage.getItem('tc-sync-meta')).toBeNull();
    const operations = JSON.parse(fetchMock.mock.calls.find((call) => call[1]?.method === 'PUT')?.[1]?.body as string).operations;
    expect(operations).toContainEqual({ op: 'set', key: 'tc-user-name', value: 'Ada' });
  });

  it('propagates a local removal as a delete operation', async () => {
    let getCount = 0;
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit = {}) => {
      if (init.method === 'PUT') {
        return Promise.resolve(mockResponse({
          body: { ok: true, schema_version: 2, revision: 2, applied: true },
          etag: '"trinaxai-app-state-v2-2"',
        }));
      }
      getCount += 1;
      if (getCount === 1) {
        return Promise.resolve(mockResponse({
          body: { ok: true, schema_version: 2, revision: 1, values: { 'tc-theme': 'dark' } },
          etag: '"trinaxai-app-state-v2-1"',
        }));
      }
      return Promise.resolve(mockResponse({ status: 304 }));
    });
    vi.stubGlobal('fetch', fetchMock);

    await syncSharedStateOnce(1000, true);
    expect(localStorage.getItem('tc-theme')).toBe('dark');
    localStorage.removeItem('tc-theme');
    await syncSharedStateOnce(1000, true);

    const putCall = fetchMock.mock.calls.find((call) => call[1]?.method === 'PUT');
    expect(putCall).toBeDefined();
    expect(JSON.parse(putCall?.[1]?.body as string).operations).toEqual([
      { op: 'delete', key: 'tc-theme' },
    ]);
  });

  it('deterministically rebases pending operations after a two-device conflict', async () => {
    localStorage.setItem('tc-lang', 'es');
    let putCount = 0;
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit = {}) => {
      if (init.method !== 'PUT') {
        return Promise.resolve(mockResponse({
          body: { ok: true, schema_version: 2, revision: 0, values: {} },
          etag: '"trinaxai-app-state-v2-0"',
        }));
      }
      putCount += 1;
      if (putCount === 1) {
        return Promise.resolve(mockResponse({
          status: 409,
          body: {
            ok: false,
            error: 'revision_conflict',
            schema_version: 2,
            revision: 1,
            values: { 'tc-theme': 'dark' },
          },
          etag: '"trinaxai-app-state-v2-1"',
        }));
      }
      return Promise.resolve(mockResponse({
        body: { ok: true, schema_version: 2, revision: 2, applied: true },
        etag: '"trinaxai-app-state-v2-2"',
      }));
    });
    vi.stubGlobal('fetch', fetchMock);

    await syncSharedStateOnce(1000, true);

    const puts = fetchMock.mock.calls.filter((call) => call[1]?.method === 'PUT');
    expect(puts).toHaveLength(2);
    expect(JSON.parse(puts[0][1]?.body as string).base_revision).toBe(0);
    expect(JSON.parse(puts[1][1]?.body as string).base_revision).toBe(1);
    expect(localStorage.getItem('tc-theme')).toBe('dark');
    expect(localStorage.getItem('tc-lang')).toBe('es');
  });

  it('applies a newer remote delete and never republishes the removed key', async () => {
    let getCount = 0;
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit = {}) => {
      if (init.method === 'PUT') {
        throw new Error('A remote delete must not be turned into a stale set.');
      }
      getCount += 1;
      if (getCount === 1) {
        return Promise.resolve(mockResponse({
          body: { ok: true, schema_version: 2, revision: 1, values: { 'tc-keep-alive': 'old' } },
          etag: '"trinaxai-app-state-v2-1"',
        }));
      }
      return Promise.resolve(mockResponse({
        body: { ok: true, schema_version: 2, revision: 2, values: {} },
        etag: '"trinaxai-app-state-v2-2"',
      }));
    });
    vi.stubGlobal('fetch', fetchMock);

    await syncSharedStateOnce(1000, true);
    expect(localStorage.getItem('tc-keep-alive')).toBe('old');
    await syncSharedStateOnce(1000, true);

    expect(localStorage.getItem('tc-keep-alive')).toBeNull();
    expect(fetchMock.mock.calls.every((call) => call[1]?.method !== 'PUT')).toBe(true);
  });

  it('polls with ETag but performs no full-state write when nothing changed', async () => {
    let getCount = 0;
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit = {}) => {
      expect(init.method).not.toBe('PUT');
      getCount += 1;
      return Promise.resolve(getCount === 1
        ? mockResponse({
          body: { ok: true, schema_version: 2, revision: 4, values: {} },
          etag: '"trinaxai-app-state-v2-4"',
        })
        : mockResponse({ status: 304 }));
    });
    vi.stubGlobal('fetch', fetchMock);

    await syncSharedStateOnce(1000, true);
    await syncSharedStateOnce(1000, true);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const headers = fetchMock.mock.calls[1][1]?.headers as Headers;
    expect(headers.get('If-None-Match')).toBe('"trinaxai-app-state-v2-4"');
  });

  it('stops polling after authorization is denied until credentials change', async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ status: 403 }));
    vi.stubGlobal('fetch', fetchMock);

    await syncSharedStateOnce(1000, true);
    await syncSharedStateOnce(1000, true);

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
