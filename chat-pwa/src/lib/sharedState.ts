import { APP_CONFIG } from './config';
import type { ChatSession } from './api';
import { clearRevokedDeviceSession, systemRequestHeaders } from './authHeaders';

const SYNC_EVENT = 'trinaxai:shared-state-updated';
const SYNC_INTERVAL_MS = 8000;
const SYNC_DEBOUNCE_MS = 350;
const STORAGE_PREFIX = 'tc-';
const LEGACY_META_KEY = 'tc-sync-meta';
const CLIENT_META_KEY = 'trinaxai-sync-client-v2';
const DEVICE_ID_KEY = 'trinaxai-sync-device-id';
const CHAT_SESSIONS_KEY = 'tc-chat-sessions';
const CHAT_DELETED_KEY = 'tc-chat-deleted-ids';
const EXCLUDED_KEYS = new Set(['tc-chat-sessions-backup', LEGACY_META_KEY]);

type SetOperation = { op: 'set'; key: string; value: string };
type DeleteOperation = { op: 'delete'; key: string };
type StateOperation = SetOperation | DeleteOperation;
type PendingOperations = Record<string, StateOperation>;
type ChatDeleted = Record<string, number>;

interface ClientSyncMeta {
  schemaVersion: 2;
  initialized: boolean;
  serverRevision: number;
  knownKeys: string[];
  pending: PendingOperations;
}

interface RemoteState {
  values: Record<string, string>;
  revision: number;
}

interface PushSuccess {
  kind: 'success';
  revision: number;
}

interface PushConflict {
  kind: 'conflict';
  remote: RemoteState;
}

class SharedStateAuthorizationError extends Error {}

let syncStarted = false;
let syncRuntimeCleanup: (() => void) | null = null;
let storageHooksInstalled = false;
let syncInFlight = false;
let syncAgain = false;
let syncTimer: number | undefined;
let applyingRemote = false;
let syncBackoffUntil = 0;
let syncFailureCount = 0;
let syncAuthorizationBlocked = false;
let remoteStateEtag: string | null = null;
let cachedMeta: ClientSyncMeta | null = null;

function emptyMeta(): ClientSyncMeta {
  return {
    schemaVersion: 2,
    initialized: false,
    serverRevision: 0,
    knownKeys: [],
    pending: {},
  };
}

function isSyncableKey(key: string): boolean {
  return key.startsWith(STORAGE_PREFIX) && !EXCLUDED_KEYS.has(key);
}

function localKeys(): string[] {
  try {
    return Object.keys(localStorage).filter(isSyncableKey);
  } catch {
    return [];
  }
}

function snapshotLocalState(): Record<string, string> {
  const values: Record<string, string> = {};
  for (const key of localKeys()) {
    const value = localStorage.getItem(key);
    if (value !== null) values[key] = value;
  }
  return values;
}

function parsePending(value: unknown): PendingOperations {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const pending: PendingOperations = {};
  for (const [key, candidate] of Object.entries(value)) {
    if (!isSyncableKey(key) || !candidate || typeof candidate !== 'object') continue;
    const operation = candidate as { op?: unknown; key?: unknown; value?: unknown };
    if (operation.key !== key) continue;
    if (operation.op === 'delete') pending[key] = { op: 'delete', key };
    if (operation.op === 'set' && typeof operation.value === 'string') {
      pending[key] = { op: 'set', key, value: operation.value };
    }
  }
  return pending;
}

function readClientMeta(): ClientSyncMeta {
  const raw = localStorage.getItem(CLIENT_META_KEY);
  if (!raw) {
    cachedMeta = emptyMeta();
    remoteStateEtag = null;
    return cachedMeta;
  }
  if (cachedMeta) return cachedMeta;
  try {
    const parsed = JSON.parse(raw) as Partial<ClientSyncMeta>;
    const revision = Number(parsed.serverRevision);
    cachedMeta = {
      schemaVersion: 2,
      initialized: parsed.schemaVersion === 2 && parsed.initialized === true,
      serverRevision: Number.isSafeInteger(revision) && revision >= 0 ? revision : 0,
      knownKeys: Array.isArray(parsed.knownKeys)
        ? [...new Set(parsed.knownKeys.filter((key): key is string => typeof key === 'string' && isSyncableKey(key)))]
        : [],
      pending: parsePending(parsed.pending),
    };
  } catch {
    cachedMeta = emptyMeta();
  }
  if (cachedMeta.initialized) remoteStateEtag = etagForRevision(cachedMeta.serverRevision);
  return cachedMeta;
}

function persistClientMeta(meta: ClientSyncMeta): void {
  cachedMeta = meta;
  localStorage.setItem(CLIENT_META_KEY, JSON.stringify(meta));
}

function deviceId(): string {
  const existing = localStorage.getItem(DEVICE_ID_KEY);
  if (existing && existing.length >= 8) return existing;
  const generated = typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `device-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  localStorage.setItem(DEVICE_ID_KEY, generated);
  return generated;
}

function etagForRevision(revision: number): string {
  return `"trinaxai-app-state-v2-${revision}"`;
}

function queueOperation(operation: StateOperation, schedule = true): void {
  const meta = readClientMeta();
  meta.pending[operation.key] = operation;
  persistClientMeta(meta);
  if (schedule) scheduleSharedStateSync();
}

function operationsEqual(left: StateOperation | undefined, right: StateOperation): boolean {
  return left?.op === right.op
    && left.key === right.key
    && (left.op !== 'set' || (right.op === 'set' && left.value === right.value));
}

function readJsonObject<T extends Record<string, unknown>>(key: string): T {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || '{}');
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as T : {} as T;
  } catch {
    return {} as T;
  }
}

function parseSessions(raw: string | undefined): ChatSession[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter((session) => {
        const title = String(session?.title ?? '').trim();
        const messages = Array.isArray(session?.messages) ? session.messages : [];
        return messages.length > 0 || !['New Chat', 'Nuevo Chat'].includes(title);
      })
      : [];
  } catch {
    return [];
  }
}

function parseDeleted(raw: string | undefined): ChatDeleted {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    const deleted: ChatDeleted = {};
    for (const [id, value] of Object.entries(parsed)) {
      if (typeof id === 'string' && typeof value === 'number') deleted[id] = value;
    }
    return deleted;
  } catch {
    return {};
  }
}

function mergeDeleted(localRaw: string | undefined, remoteRaw: string | undefined): string | null {
  const merged: ChatDeleted = { ...parseDeleted(remoteRaw) };
  for (const [id, time] of Object.entries(parseDeleted(localRaw))) {
    merged[id] = Math.max(merged[id] ?? 0, time);
  }
  return Object.keys(merged).length ? JSON.stringify(merged) : null;
}

function mergeSessions(
  localRaw: string | undefined,
  remoteRaw: string | undefined,
  deletedRaw: string | undefined,
): string | null {
  const deleted = parseDeleted(deletedRaw);
  const byId = new Map<string, ChatSession>();
  for (const session of [...parseSessions(remoteRaw), ...parseSessions(localRaw)]) {
    const deletedAt = deleted[session.id] ?? 0;
    if (deletedAt && deletedAt >= (session.updatedAt ?? 0)) continue;
    const existing = byId.get(session.id);
    if (!existing || (session.updatedAt ?? 0) >= (existing.updatedAt ?? 0)) {
      byId.set(session.id, session);
    }
  }
  return byId.size
    ? JSON.stringify([...byId.values()].sort((a, b) => (b.updatedAt ?? 0) - (a.updatedAt ?? 0)))
    : null;
}

function parseResetTime(raw: string | undefined): number {
  const value = Number(raw || 0);
  if (!Number.isFinite(value) || value <= 0) return 0;
  return value > 100_000_000_000 ? value / 1000 : value;
}

async function fetchRemoteState(signal?: AbortSignal): Promise<RemoteState | null> {
  const headers = systemRequestHeaders(remoteStateEtag ? { 'If-None-Match': remoteStateEtag } : undefined);
  const response = await fetch(`${APP_CONFIG.ragBase}/app-state`, { signal, headers });
  if (response.status === 304) return null;
  if (response.status === 401 || response.status === 403) {
    clearRevokedDeviceSession();
    throw new SharedStateAuthorizationError(`Shared state read denied: ${response.status}`);
  }
  if (!response.ok) throw new Error(`Shared state read failed: ${response.status}`);
  const data = await response.json();
  const revision = Number(data?.revision);
  if (!Number.isSafeInteger(revision) || revision < 0) {
    throw new Error('Shared state response has no valid server revision.');
  }
  remoteStateEtag = response.headers.get('ETag') || etagForRevision(revision);
  return {
    revision,
    values: data?.values && typeof data.values === 'object' ? data.values : {},
  };
}

function setLocalValue(key: string, value: string | null): boolean {
  const before = localStorage.getItem(key);
  if (value === null) {
    if (before === null) return false;
    localStorage.removeItem(key);
    return true;
  }
  if (before === value) return false;
  localStorage.setItem(key, value);
  return true;
}

/** Apply one authoritative server revision while preserving explicit local ops. */
function applyRemoteState(remote: RemoteState): boolean {
  const meta = readClientMeta();
  const local = snapshotLocalState();
  const remoteValues = Object.fromEntries(
    Object.entries(remote.values).filter(([key, value]) => isSyncableKey(key) && typeof value === 'string'),
  );
  const knownBefore = new Set(meta.knownKeys);
  let changed = false;

  const remoteReset = parseResetTime(remoteValues['tc-reset-at']);
  const localReset = parseResetTime(local['tc-reset-at']);
  applyingRemote = true;
  try {
    if (remoteReset && remoteReset > localReset) {
      for (const key of localKeys()) changed = setLocalValue(key, null) || changed;
      for (const [key, value] of Object.entries(remoteValues)) {
        changed = setLocalValue(key, value) || changed;
      }
      meta.pending = {};
    } else {
      const mergedDeleted = mergeDeleted(local[CHAT_DELETED_KEY], remoteValues[CHAT_DELETED_KEY]);
      const mergedSessions = mergeSessions(
        local[CHAT_SESSIONS_KEY],
        remoteValues[CHAT_SESSIONS_KEY],
        mergedDeleted ?? undefined,
      );

      for (const [key, merged] of [
        [CHAT_DELETED_KEY, mergedDeleted],
        [CHAT_SESSIONS_KEY, mergedSessions],
      ] as const) {
        changed = setLocalValue(key, merged) || changed;
        if (merged === null) {
          if (remoteValues[key] !== undefined) meta.pending[key] = { op: 'delete', key };
        } else if (merged !== remoteValues[key]) {
          meta.pending[key] = { op: 'set', key, value: merged };
        } else {
          delete meta.pending[key];
        }
      }

      const allKeys = new Set([
        ...Object.keys(local),
        ...Object.keys(remoteValues),
        ...knownBefore,
      ]);
      allKeys.delete(CHAT_SESSIONS_KEY);
      allKeys.delete(CHAT_DELETED_KEY);
      for (const key of allKeys) {
        const pending = meta.pending[key];
        if (pending) continue;
        const remoteValue = remoteValues[key];
        if (remoteValue !== undefined) {
          changed = setLocalValue(key, remoteValue) || changed;
        } else if (knownBefore.has(key)) {
          // An absent key in a newer server revision is an authoritative delete.
          changed = setLocalValue(key, null) || changed;
        } else if (!meta.initialized && local[key] !== undefined) {
          // One-time migration of values created before operation tracking.
          meta.pending[key] = { op: 'set', key, value: local[key] };
        }
      }
    }

    // Remove the old timestamp metadata from both client and server.
    if (remote.values[LEGACY_META_KEY] !== undefined) {
      meta.pending[LEGACY_META_KEY] = { op: 'delete', key: LEGACY_META_KEY };
    }
    localStorage.removeItem(LEGACY_META_KEY);
  } finally {
    applyingRemote = false;
  }

  meta.initialized = true;
  meta.serverRevision = remote.revision;
  meta.knownKeys = Object.keys(remoteValues);
  persistClientMeta(meta);
  remoteStateEtag = etagForRevision(remote.revision);
  if (changed) window.dispatchEvent(new Event(SYNC_EVENT));
  return changed;
}

async function pushOperations(
  operations: StateOperation[],
  baseRevision: number,
  signal?: AbortSignal,
): Promise<PushSuccess | PushConflict> {
  const response = await fetch(`${APP_CONFIG.ragBase}/app-state`, {
    method: 'PUT',
    headers: systemRequestHeaders({
      'Content-Type': 'application/json',
      'If-Match': etagForRevision(baseRevision),
    }),
    body: JSON.stringify({
      schema_version: 2,
      device_id: deviceId(),
      base_revision: baseRevision,
      operations,
    }),
    signal,
  });
  const data = await response.json().catch(() => ({}));
  if (response.status === 401 || response.status === 403) {
    clearRevokedDeviceSession();
    throw new SharedStateAuthorizationError(`Shared state write denied: ${response.status}`);
  }
  if (response.status === 409) {
    const revision = Number(data?.revision);
    if (!Number.isSafeInteger(revision) || revision < 0 || !data?.values || typeof data.values !== 'object') {
      throw new Error('Invalid shared-state conflict response.');
    }
    remoteStateEtag = response.headers.get('ETag') || etagForRevision(revision);
    return { kind: 'conflict', remote: { revision, values: data.values } };
  }
  if (!response.ok) throw new Error(`Shared state sync failed: ${response.status}`);
  const revision = Number(data?.revision);
  if (!Number.isSafeInteger(revision) || revision < 0) {
    throw new Error('Shared state write has no valid server revision.');
  }
  remoteStateEtag = response.headers.get('ETag') || etagForRevision(revision);
  return { kind: 'success', revision };
}

function acknowledgeOperations(operations: StateOperation[], revision: number): void {
  const meta = readClientMeta();
  const known = new Set(meta.knownKeys);
  for (const operation of operations) {
    if (operationsEqual(meta.pending[operation.key], operation)) delete meta.pending[operation.key];
    if (operation.op === 'set') known.add(operation.key);
    else known.delete(operation.key);
  }
  meta.serverRevision = revision;
  meta.knownKeys = [...known];
  meta.initialized = true;
  persistClientMeta(meta);
  remoteStateEtag = etagForRevision(revision);
}

export async function syncSharedStateOnce(timeoutMs = 1800, force = false): Promise<void> {
  if (syncAuthorizationBlocked) return;
  if (!force && Date.now() < syncBackoffUntil) return;
  if (syncInFlight) {
    syncAgain = true;
    return;
  }
  syncInFlight = true;
  installLocalStorageSyncHooks();
  // Also resets cached revision/ETag after an explicit browser-storage clear.
  readClientMeta();
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const remote = await fetchRemoteState(controller.signal);
    if (remote) applyRemoteState(remote);

    // CAS conflicts are rebased on the returned authoritative revision. Local
    // pending operations are retained, so no wall-clock comparison is needed.
    for (let attempt = 0; attempt < 3; attempt += 1) {
      const meta = readClientMeta();
      const operations = Object.values(meta.pending).sort((a, b) => a.key.localeCompare(b.key));
      if (operations.length === 0) break;
      const result = await pushOperations(operations, meta.serverRevision, controller.signal);
      if (result.kind === 'conflict') {
        applyRemoteState(result.remote);
        continue;
      }
      acknowledgeOperations(operations, result.revision);
    }
    syncFailureCount = 0;
    syncBackoffUntil = 0;
  } catch (error) {
    // Offline or backend down: persisted pending operations remain retryable.
    if (error instanceof SharedStateAuthorizationError) {
      // Invalid/revoked credentials do not heal with polling. Pause until the
      // pairing flow explicitly announces new credentials.
      syncAuthorizationBlocked = true;
      syncBackoffUntil = Number.POSITIVE_INFINITY;
    } else {
      syncFailureCount += 1;
      syncBackoffUntil = Date.now() + Math.min(60_000, 2_000 * syncFailureCount);
    }
  } finally {
    window.clearTimeout(timeout);
    syncInFlight = false;
    if (syncAgain) {
      syncAgain = false;
      scheduleSharedStateSync(timeoutMs);
    }
  }
}

export function scheduleSharedStateSync(timeoutMs = 1800): void {
  if (syncAuthorizationBlocked) return;
  window.clearTimeout(syncTimer);
  syncTimer = window.setTimeout(() => {
    void syncSharedStateOnce(timeoutMs);
  }, SYNC_DEBOUNCE_MS);
}

function installLocalStorageSyncHooks(): void {
  if (storageHooksInstalled) return;
  storageHooksInstalled = true;
  const setItem = Storage.prototype.setItem;
  const removeItem = Storage.prototype.removeItem;
  Storage.prototype.setItem = function patchedSetItem(key: string, value: string) {
    const before = this.getItem(key);
    setItem.call(this, key, value);
    if (!applyingRemote && isSyncableKey(key) && before !== value) {
      queueOperation({ op: 'set', key, value });
    }
  };
  Storage.prototype.removeItem = function patchedRemoveItem(key: string) {
    const hadValue = this.getItem(key) !== null;
    removeItem.call(this, key);
    if (!applyingRemote && isSyncableKey(key) && hadValue) {
      queueOperation({ op: 'delete', key });
    }
  };
  window.addEventListener('storage', (event) => {
    if (!event.key || !isSyncableKey(event.key)) return;
    queueOperation(event.newValue === null
      ? { op: 'delete', key: event.key }
      : { op: 'set', key: event.key, value: event.newValue });
  });
}

export function markChatSessionDeleted(id: string): void {
  if (!id) return;
  const deleted = readJsonObject<ChatDeleted>(CHAT_DELETED_KEY);
  deleted[id] = Date.now();
  localStorage.setItem(CHAT_DELETED_KEY, JSON.stringify(deleted));
  scheduleSharedStateSync();
}

export function startSharedStateSync(): () => void {
  if (syncStarted) return syncRuntimeCleanup ?? (() => undefined);
  syncStarted = true;
  installLocalStorageSyncHooks();
  void syncSharedStateOnce();
  const interval = window.setInterval(() => {
    if (!document.hidden) void syncSharedStateOnce();
  }, SYNC_INTERVAL_MS);
  const onVisibilityChange = () => {
    if (!document.hidden) void syncSharedStateOnce();
  };
  document.addEventListener('visibilitychange', onVisibilityChange);
  // Pairing changes the credentials available to this browser. Retry
  // immediately so a newly linked phone restores chats/preferences instead of
  // waiting for the next periodic sync.
  const onDeviceAuthChanged = () => {
    syncAuthorizationBlocked = false;
    syncFailureCount = 0;
    syncBackoffUntil = 0;
    void syncSharedStateOnce(3000, true);
  };
  window.addEventListener('trinaxai-device-auth-changed', onDeviceAuthChanged);
  syncRuntimeCleanup = () => {
    window.clearInterval(interval);
    window.clearTimeout(syncTimer);
    syncTimer = undefined;
    document.removeEventListener('visibilitychange', onVisibilityChange);
    window.removeEventListener('trinaxai-device-auth-changed', onDeviceAuthChanged);
    syncStarted = false;
    syncRuntimeCleanup = null;
  };
  return syncRuntimeCleanup;
}

export function onSharedStateUpdated(callback: () => void): () => void {
  window.addEventListener(SYNC_EVENT, callback);
  return () => window.removeEventListener(SYNC_EVENT, callback);
}
