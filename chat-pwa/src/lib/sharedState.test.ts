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

  it('authenticates reads and sends a versioned operation instead of a snapshot', async () => {
    localStorage.setItem('tc-theme', 'dark');
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit = {}) => {
      if (init.method === 'PUT') {
        return Promise.resolve(mockResponse({
          body: { ok: true, schema_version: 2, revision: 1, applied: true },
          etag: '"trinaxai-app-state-v2-1"',
        }));
      }
      return Promise.resolve(mockResponse({
        body: { ok: true, schema_version: 2, revision: 0, values: {} },
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
      operations: [{ op: 'set', key: 'tc-theme', value: 'dark' }],
    });
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
          body: { ok: true, schema_version: 2, revision: 1, values: { 'tc-obsolete': 'old' } },
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
    expect(localStorage.getItem('tc-obsolete')).toBe('old');
    await syncSharedStateOnce(1000, true);

    expect(localStorage.getItem('tc-obsolete')).toBeNull();
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
