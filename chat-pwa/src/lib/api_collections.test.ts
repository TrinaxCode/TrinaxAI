import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  addMemory,
  createCollection,
  deleteCollection,
  deleteCollectionSources,
  deleteIndexedImport,
  deleteMemory,
  deleteSource,
  getCollections,
  getCollectionSources,
  getFileChunks,
  getMemorySummary,
  getRelevantMemoryContext,
  getWatchStatus,
  listMemories,
  refreshMemorySummary,
  renameCollection,
  startWatch,
  stopWatch,
  updateMemory,
} from './api_collections';

afterEach(() => vi.unstubAllGlobals());

describe('collections API', () => {
  it('manages collections and falls back to an empty list', async () => {
    const collection = { id: 'c/1', name: 'Docs', created_at: 1, updated_at: 2 };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(Response.json({ collections: [collection] }))
      .mockResolvedValueOnce(Response.json({}))
      .mockResolvedValueOnce(Response.json({ collection }))
      .mockResolvedValueOnce(Response.json({ collection: { ...collection, name: 'New' } }))
      .mockResolvedValueOnce(Response.json({ ok: true }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(getCollections()).resolves.toEqual([collection]);
    await expect(getCollections()).resolves.toEqual([]);
    await expect(createCollection('Docs')).resolves.toEqual(collection);
    await expect(renameCollection('c/1', 'New')).resolves.toMatchObject({ name: 'New' });
    await expect(deleteCollection('c/1')).resolves.toBeUndefined();

    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({ name: 'Docs' });
    expect(fetchMock.mock.calls[3][0]).toMatch(/\/collections\/c%2F1$/);
    expect(fetchMock.mock.calls[3][1].method).toBe('PATCH');
    expect(fetchMock.mock.calls[4][1].method).toBe('DELETE');
  });

  it('builds encoded knowledge-browser requests', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(Response.json({ deleted: 1 })));
    vi.stubGlobal('fetch', fetchMock);
    const signal = new AbortController().signal;

    await getCollectionSources('team docs', signal);
    await getFileChunks('team docs', 'folder/a b.md', {
      limit: 10, offset: 0, q: 'needle here', sourceId: 'source/1', signal,
    });
    await deleteSource('team docs', 'folder/a b.md', 'source/1');
    await deleteCollectionSources('team docs');
    await deleteIndexedImport('/tmp/docs', 'team docs');

    expect(fetchMock.mock.calls[0][0]).toContain('/v1/sources?collection=team%20docs');
    expect(fetchMock.mock.calls[0][1].signal).toBe(signal);
    expect(fetchMock.mock.calls[1][0]).toContain('/team%20docs/folder/a%20b.md/chunks?limit=10&offset=0&q=needle+here&source_id=source%2F1');
    expect(fetchMock.mock.calls[2][0]).toContain('/folder/a%20b.md?source_id=source%2F1');
    expect(fetchMock.mock.calls[2][1].method).toBe('DELETE');
    expect(fetchMock.mock.calls[3][0]).toMatch(/\/v1\/sources\/team%20docs$/);
    expect(JSON.parse(fetchMock.mock.calls[4][1].body)).toEqual({ path: '/tmp/docs', collection_id: 'team docs' });
  });

  it('starts, stops, and reads watcher state', async () => {
    const status = { running: true, watching: ['/tmp'], events_seen: 1, started_at: 2, job: {} };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(Response.json({ status: 'started', watching: ['/tmp'], pid: 2 }))
      .mockResolvedValueOnce(Response.json({ status: 'stopped' }))
      .mockResolvedValueOnce(Response.json(status));
    vi.stubGlobal('fetch', fetchMock);
    const signal = new AbortController().signal;

    await startWatch({ paths: ['/tmp'], collection: 'docs' });
    await stopWatch();
    await expect(getWatchStatus(signal)).resolves.toEqual(status);

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ paths: ['/tmp'], collection: 'docs' });
    expect(fetchMock.mock.calls[1][1].method).toBe('POST');
    expect(fetchMock.mock.calls[2][1].signal).toBe(signal);
  });

  it('validates memory lists and sends memory mutations', async () => {
    const memory = { id: 'm/1', text: 'remember', tags: ['tag'], kind: 'note', provenance: 'manual', created_at: 1 };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(Response.json({ memories: [memory] }))
      .mockResolvedValueOnce(Response.json({ memories: [memory] }))
      .mockResolvedValueOnce(Response.json(memory))
      .mockResolvedValueOnce(Response.json(memory))
      .mockResolvedValueOnce(Response.json({ deleted: true }))
      .mockResolvedValueOnce(Response.json({ status: 'ok', summary: 'one', count: 1 }))
      .mockResolvedValueOnce(Response.json({ summary: 'one', count: 1, updated_at: 2 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(listMemories()).resolves.toEqual([memory]);
    await expect(getRelevantMemoryContext('query')).resolves.toEqual([memory]);
    await addMemory('remember', ['tag'], { kind: 'fact', expiresAt: 5 });
    await updateMemory('m/1', { text: 'updated' });
    await deleteMemory('m/1');
    await refreshMemorySummary();
    await getMemorySummary();

    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ query: 'query', max_entries: 8 });
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({
      text: 'remember', tags: ['tag'], kind: 'fact', provenance: 'manual', expires_at: 5,
    });
    expect(fetchMock.mock.calls[3][0]).toMatch(/\/v1\/memory\/m%2F1$/);
    expect(JSON.parse(fetchMock.mock.calls[5][1].body)).toEqual({});
  });

  it('rejects malformed memory payloads', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(Response.json({ memories: [{ id: 'm', text: 'x', tags: [1] }] }))
      .mockResolvedValueOnce(Response.json({ memories: null })));

    await expect(listMemories()).rejects.toMatchObject({ status: 502, category: 'internal_server_error' });
    await expect(getRelevantMemoryContext('query')).rejects.toMatchObject({ status: 502 });
  });
});
