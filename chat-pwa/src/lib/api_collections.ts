import { ApiError } from './api_errors';
import { apiJson, RAG_BASE, isRecord } from './api_http';
import type { Collection } from './api_documents';

export async function getCollections(signal?: AbortSignal): Promise<Collection[]> {
  const data = await apiJson<{ collections?: Collection[] }>(`${RAG_BASE}/collections`, { signal });
  return Array.isArray(data.collections) ? data.collections : [];
}

export async function createCollection(name: string): Promise<Collection> {
  const data = await apiJson<{ collection: Collection }>(`${RAG_BASE}/collections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  return data.collection;
}

export async function renameCollection(id: string, name: string): Promise<Collection> {
  const data = await apiJson<{ collection: Collection }>(`${RAG_BASE}/collections/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  return data.collection;
}

export async function deleteCollection(id: string): Promise<void> {
  await apiJson(`${RAG_BASE}/collections/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

// ── Knowledge Browser ──
export interface CollectionSourceRow {
  file: string;
  source_id: string | null;
  chunks: number;
  size: number;
  mtime: number;
  preview: string;
}
export interface FileChunk {
  id: string;
  text: string;
  metadata: Record<string, unknown>;
  score: number | null;
}
export interface DeleteIndexedImportResult {
  deleted: number;
  removed_path: boolean;
  path: string;
  collection: string;
}

export async function getCollectionSources(
  collection: string,
  signal?: AbortSignal,
): Promise<{ collection: string; sources: CollectionSourceRow[] }> {
  const url = `${RAG_BASE}/v1/sources?collection=${encodeURIComponent(collection)}`;
  return apiJson(url, { signal });
}

export async function getFileChunks(
  collection: string,
  file: string,
  opts: { limit?: number; offset?: number; q?: string; sourceId?: string | null; signal?: AbortSignal } = {},
): Promise<{ collection: string; file: string; source_id?: string | null; total: number; chunks: FileChunk[]; query?: string }> {
  const params = new URLSearchParams();
  if (opts.limit != null) params.set('limit', String(opts.limit));
  if (opts.offset != null) params.set('offset', String(opts.offset));
  if (opts.q) params.set('q', opts.q);
  if (opts.sourceId) params.set('source_id', opts.sourceId);
  const qs = params.toString();
  const encodedFile = file.split('/').map((part) => encodeURIComponent(part)).join('/');
  const url = `${RAG_BASE}/v1/sources/${encodeURIComponent(collection)}/${encodedFile}/chunks${qs ? `?${qs}` : ''}`;
  return apiJson(url, { signal: opts.signal });
}

/** Delete all indexed chunks for a single file within a collection. */
export async function deleteSource(
  collection: string,
  file: string,
  sourceId?: string | null,
): Promise<{ deleted: number; collection: string; file: string; source_id?: string | null }> {
  const encodedFile = file.split('/').map((part) => encodeURIComponent(part)).join('/');
  const params = new URLSearchParams();
  if (sourceId) params.set('source_id', sourceId);
  const qs = params.toString();
  const url = `${RAG_BASE}/v1/sources/${encodeURIComponent(collection)}/${encodedFile}${qs ? `?${qs}` : ''}`;
  return apiJson(url, { method: 'DELETE' });
}

/** Bulk-delete ALL indexed sources in a collection (keeps the collection itself). */
export async function deleteCollectionSources(
  collection: string,
): Promise<{ deleted: number; collection: string }> {
  const url = `${RAG_BASE}/v1/sources/${encodeURIComponent(collection)}`;
  return apiJson(url, { method: 'DELETE' });
}

/** Delete a browser-imported folder copy and its indexed chunks. */
export async function deleteIndexedImport(
  path: string,
  collectionId?: string,
): Promise<DeleteIndexedImportResult> {
  return apiJson(`${RAG_BASE}/system/index-imports`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, collection_id: collectionId || 'default' }),
  });
}

// ── File Watcher ──
export interface WatchJobStatus {
  status: 'idle' | 'queued' | 'running' | 'succeeded' | 'failed' | 'timed_out' | 'cancelled' | 'stopping' | string;
  pending_events: number;
  active_root: string | null;
  last_started_at: number | null;
  last_finished_at: number | null;
  last_duration_seconds: number | null;
  last_exit_code: number | null;
  last_error: string | null;
  last_stdout: string;
  last_stderr: string;
  runs_completed: number;
  runs_failed: number;
  runs_timed_out: number;
  runs_cancelled: number;
}

export interface WatchStatus {
  running: boolean;
  watching: string[];
  events_seen: number;
  started_at: number | null;
  job: WatchJobStatus;
}

export async function startWatch(opts: { paths?: string[]; collection?: string } = {}): Promise<{ status: string; watching: string[]; pid: number | null }> {
  return apiJson(`${RAG_BASE}/v1/watch/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ paths: opts.paths, collection: opts.collection }),
  });
}
export async function stopWatch(): Promise<{ status: string }> {
  return apiJson(`${RAG_BASE}/v1/watch/stop`, { method: 'POST' });
}
export async function getWatchStatus(signal?: AbortSignal): Promise<WatchStatus> {
  return apiJson(`${RAG_BASE}/v1/watch/status`, { signal });
}

// ── Memory ──
export interface MemoryEntry {
  id: string;
  text: string;
  created_at: number;
  updated_at?: number;
  tags: string[];
  kind: 'fact' | 'preference' | 'decision' | 'note';
  provenance: 'manual' | 'inferred';
  expires_at?: number | null;
}
export interface MemorySummary {
  summary: string;
  count: number;
  updated_at: number;
}

function validateMemoryEntries(value: unknown): MemoryEntry[] {
  if (
    !Array.isArray(value)
    || value.some((entry) => {
      if (!isRecord(entry) || typeof entry.id !== 'string' || typeof entry.text !== 'string') return true;
      return entry.tags !== undefined
        && (!Array.isArray(entry.tags) || entry.tags.some((tag) => typeof tag !== 'string'));
    })
  ) {
    throw new ApiError('', 502, 'invalid_response');
  }
  return value as MemoryEntry[];
}

export async function listMemories(signal?: AbortSignal): Promise<MemoryEntry[]> {
  const data = await apiJson<unknown>(`${RAG_BASE}/v1/memory`, { signal });
  return validateMemoryEntries(isRecord(data) ? data.memories : undefined);
}
export async function addMemory(
  text: string,
  tags?: string[],
  options: { kind?: MemoryEntry['kind']; expiresAt?: number } = {},
): Promise<MemoryEntry> {
  return apiJson(`${RAG_BASE}/v1/memory`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text,
      tags,
      kind: options.kind ?? 'note',
      provenance: 'manual',
      expires_at: options.expiresAt,
    }),
  });
}
export async function updateMemory(
  id: string,
  change: Partial<Pick<MemoryEntry, 'text' | 'tags' | 'kind' | 'expires_at'>>,
): Promise<MemoryEntry> {
  return apiJson(`${RAG_BASE}/v1/memory/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(change),
  });
}
export async function getRelevantMemoryContext(
  query: string,
  signal?: AbortSignal,
): Promise<MemoryEntry[]> {
  const data = await apiJson<unknown>(`${RAG_BASE}/v1/memory/context`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, max_entries: 8 }),
    signal,
  });
  return validateMemoryEntries(isRecord(data) ? data.memories : undefined);
}
export async function deleteMemory(id: string): Promise<{ deleted: boolean }> {
  return apiJson(`${RAG_BASE}/v1/memory/${encodeURIComponent(id)}`, { method: 'DELETE' });
}
export async function refreshMemorySummary(): Promise<{ status: string; summary: string; count: number }> {
  return apiJson(`${RAG_BASE}/v1/memory/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
}
export async function getMemorySummary(signal?: AbortSignal): Promise<MemorySummary> {
  return apiJson<MemorySummary>(`${RAG_BASE}/v1/memory/summary`, { signal });
}
