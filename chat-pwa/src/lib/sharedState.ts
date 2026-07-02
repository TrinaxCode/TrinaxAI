import { APP_CONFIG } from './config';
import type { ChatSession } from './api';

const SYNC_EVENT = 'trinaxai:shared-state-updated';
const SYNC_INTERVAL_MS = 8000;
const SYNC_DEBOUNCE_MS = 350;
const STORAGE_PREFIX = 'tc-';
const META_KEY = 'tc-sync-meta';
const CHAT_SESSIONS_KEY = 'tc-chat-sessions';
const CHAT_DELETED_KEY = 'tc-chat-deleted-ids';
const EXCLUDED_KEYS = new Set(['tc-chat-sessions-backup']);
const CRITICAL_KEYS = new Set([
  'tc-onboarding-complete',
  'tc-user-nickname',
  'tc-user-name',
  'tc-lang',
  'tc-theme',
  'tc-models-chat',
  'tc-models-deep',
  'tc-models-vision',
  'tc-models-vision-quality',
  'tc-models-embed',
  'tc-models-code',
  'tc-models-fast',
  'tc-aggressive-quant',
  'tc-keep-alive',
]);
let syncStarted = false;
let storageHooksInstalled = false;
let syncInFlight = false;
let syncAgain = false;
let syncTimer: number | undefined;
let applyingRemote = false;
let syncBackoffUntil = 0;
let syncFailureCount = 0;

type SyncMeta = Record<string, { updatedAt: number; hash: string }>;
type ChatDeleted = Record<string, number>;

function localKeys(): string[] {
  try {
    return Object.keys(localStorage)
      .filter((key) => key.startsWith(STORAGE_PREFIX) && !EXCLUDED_KEYS.has(key));
  } catch {
    return [];
  }
}

function hashValue(value: string): string {
  let h = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return String(h >>> 0);
}

function readJsonObject<T extends Record<string, unknown>>(key: string): T {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || '{}');
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as T : {} as T;
  } catch {
    return {} as T;
  }
}

function parseMeta(raw: string | undefined): SyncMeta {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    const out: SyncMeta = {};
    for (const [key, value] of Object.entries(parsed)) {
      const item = value as { updatedAt?: unknown; hash?: unknown };
      if (
        key.startsWith(STORAGE_PREFIX)
        && typeof item?.updatedAt === 'number'
        && typeof item?.hash === 'string'
      ) {
        out[key] = { updatedAt: item.updatedAt, hash: item.hash };
      }
    }
    return out;
  } catch {
    return {};
  }
}

function readLocalMeta(): SyncMeta {
  return parseMeta(localStorage.getItem(META_KEY) ?? undefined);
}

function refreshLocalMeta(): SyncMeta {
  const now = Date.now();
  const meta = readLocalMeta();
  for (const key of localKeys()) {
    if (key === META_KEY) continue;
    const value = localStorage.getItem(key);
    if (typeof value !== 'string') continue;
    const hash = hashValue(value);
    if (meta[key]?.hash !== hash) {
      meta[key] = { updatedAt: now, hash };
    }
  }
  for (const key of Object.keys(meta)) {
    if (key === META_KEY || EXCLUDED_KEYS.has(key)) {
      delete meta[key];
      continue;
    }
    if (localStorage.getItem(key) === null) delete meta[key];
  }
  localStorage.setItem(META_KEY, JSON.stringify(meta));
  return meta;
}

function snapshotLocalState(): Record<string, string> {
  refreshLocalMeta();
  const out: Record<string, string> = {};
  for (const key of localKeys()) {
    const value = localStorage.getItem(key);
    if (typeof value === 'string') out[key] = value;
  }
  return out;
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
    const out: ChatDeleted = {};
    for (const [id, value] of Object.entries(parsed)) {
      if (typeof id === 'string' && typeof value === 'number') out[id] = value;
    }
    return out;
  } catch {
    return {};
  }
}

function parseResetTime(raw: string | undefined): number {
  const value = Number(raw || 0);
  if (!Number.isFinite(value) || value <= 0) return 0;
  return value > 100_000_000_000 ? value / 1000 : value;
}

function mergeDeleted(localRaw: string | undefined, remoteRaw: string | undefined): string | null {
  const merged: ChatDeleted = { ...parseDeleted(remoteRaw), ...parseDeleted(localRaw) };
  for (const [id, time] of Object.entries(parseDeleted(remoteRaw))) {
    merged[id] = Math.max(merged[id] ?? 0, time);
  }
  return Object.keys(merged).length ? JSON.stringify(merged) : null;
}

function mergeSessions(localRaw: string | undefined, remoteRaw: string | undefined, deletedRaw: string | undefined): string | null {
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
  if (byId.size === 0) return null;
  return JSON.stringify([...byId.values()].sort((a, b) => (b.updatedAt ?? 0) - (a.updatedAt ?? 0)));
}

async function fetchRemoteState(signal?: AbortSignal): Promise<Record<string, string>> {
  const response = await fetch(`${APP_CONFIG.ragBase}/app-state`, { signal });
  if (!response.ok) return {};
  const data = await response.json();
  return data?.values && typeof data.values === 'object' ? data.values : {};
}

async function pushRemoteState(values: Record<string, string>, signal?: AbortSignal): Promise<void> {
  const response = await fetch(`${APP_CONFIG.ragBase}/app-state`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values }),
    signal,
  });
  if (!response.ok) throw new Error(`Shared state sync failed: ${response.status}`);
}

function criticalLocalState(): Record<string, string> {
  refreshLocalMeta();
  const out: Record<string, string> = {};
  for (const key of localKeys()) {
    if (!CRITICAL_KEYS.has(key) && key !== META_KEY) continue;
    const value = localStorage.getItem(key);
    if (typeof value === 'string') out[key] = value;
  }
  const meta = readLocalMeta();
  const criticalMeta: SyncMeta = {};
  for (const key of Object.keys(out)) {
    if (meta[key]) criticalMeta[key] = meta[key];
  }
  if (Object.keys(criticalMeta).length) out[META_KEY] = JSON.stringify(criticalMeta);
  return out;
}

function applyRemoteState(remote: Record<string, string>): boolean {
  let changed = false;
  const local = snapshotLocalState();
  const localMeta = readLocalMeta();
  const remoteMeta = parseMeta(remote[META_KEY]);
  const remoteReset = parseResetTime(remote['tc-reset-at']);
  const localReset = parseResetTime(local['tc-reset-at']);
  if (localReset && localReset > remoteReset) {
    return false;
  }
  if (remoteReset && remoteReset > localReset) {
    applyingRemote = true;
    for (const key of localKeys()) {
      localStorage.removeItem(key);
    }
    localStorage.setItem('tc-reset-at', String(remoteReset));
    applyingRemote = false;
    window.dispatchEvent(new Event(SYNC_EVENT));
    return true;
  }
  const mergedDeleted = mergeDeleted(local[CHAT_DELETED_KEY], remote[CHAT_DELETED_KEY]);
  const mergedSessions = mergeSessions(local[CHAT_SESSIONS_KEY], remote[CHAT_SESSIONS_KEY], mergedDeleted ?? local[CHAT_DELETED_KEY]);
  applyingRemote = true;
  if (mergedDeleted && mergedDeleted !== local[CHAT_DELETED_KEY]) {
    localStorage.setItem(CHAT_DELETED_KEY, mergedDeleted);
    changed = true;
  }
  if (mergedSessions && mergedSessions !== local[CHAT_SESSIONS_KEY]) {
    localStorage.setItem(CHAT_SESSIONS_KEY, mergedSessions);
    changed = true;
  }
  for (const [key, value] of Object.entries(remote)) {
    if (key === CHAT_SESSIONS_KEY || key === CHAT_DELETED_KEY || key === META_KEY || EXCLUDED_KEYS.has(key)) continue;
    const remoteTime = remoteMeta[key]?.updatedAt ?? 0;
    const localTime = localMeta[key]?.updatedAt ?? 0;
    if (local[key] === undefined || remoteTime > localTime) {
      localStorage.setItem(key, value);
      changed = true;
    }
  }
  if (remote[META_KEY]) {
    const nextMeta = { ...localMeta, ...remoteMeta };
    refreshLocalMeta();
    const refreshed = readLocalMeta();
    localStorage.setItem(META_KEY, JSON.stringify({ ...nextMeta, ...refreshed }));
  }
  applyingRemote = false;
  if (changed) window.dispatchEvent(new Event(SYNC_EVENT));
  return changed;
}

export async function syncSharedStateOnce(timeoutMs = 1800, force = false): Promise<void> {
  if (!force && Date.now() < syncBackoffUntil) return;
  if (syncInFlight) {
    syncAgain = true;
    return;
  }
  syncInFlight = true;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const remote = await fetchRemoteState(controller.signal);
    applyRemoteState(remote);
    try {
      await pushRemoteState(snapshotLocalState(), controller.signal);
    } catch {
      await pushRemoteState(criticalLocalState(), controller.signal);
    }
    syncFailureCount = 0;
    syncBackoffUntil = 0;
  } catch {
    // Offline or RAG API down: localStorage remains the source of truth.
    syncFailureCount += 1;
    syncBackoffUntil = Date.now() + Math.min(60_000, 2_000 * syncFailureCount);
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
    if (!applyingRemote && key.startsWith(STORAGE_PREFIX) && !EXCLUDED_KEYS.has(key) && key !== META_KEY && before !== value) {
      scheduleSharedStateSync();
    }
  };
  Storage.prototype.removeItem = function patchedRemoveItem(key: string) {
    const hadValue = this.getItem(key) !== null;
    removeItem.call(this, key);
    if (!applyingRemote && key.startsWith(STORAGE_PREFIX) && !EXCLUDED_KEYS.has(key) && key !== META_KEY && hadValue) {
      scheduleSharedStateSync();
    }
  };
}

export function markChatSessionDeleted(id: string): void {
  if (!id) return;
  const deleted = readJsonObject<ChatDeleted>(CHAT_DELETED_KEY);
  deleted[id] = Date.now();
  localStorage.setItem(CHAT_DELETED_KEY, JSON.stringify(deleted));
  scheduleSharedStateSync();
}

export function startSharedStateSync(): void {
  if (syncStarted) return;
  syncStarted = true;
  installLocalStorageSyncHooks();
  void syncSharedStateOnce();
  window.setInterval(() => {
    void syncSharedStateOnce();
  }, SYNC_INTERVAL_MS);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) void syncSharedStateOnce();
  });
}

export function onSharedStateUpdated(callback: () => void): () => void {
  window.addEventListener(SYNC_EVENT, callback);
  return () => window.removeEventListener(SYNC_EVENT, callback);
}
