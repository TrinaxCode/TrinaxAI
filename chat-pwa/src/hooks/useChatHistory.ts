import { useState, useCallback, useEffect, useRef } from 'react';
import type { ChatSession, ChatMessage, ChatEngine } from '../lib/api';
import { uid, generateTitle } from '../lib/api';
import { markChatSessionDeleted, onSharedStateUpdated, scheduleSharedStateSync } from '../lib/sharedState';

const STORAGE_KEY = 'tc-chat-sessions';
const STORAGE_BACKUP_KEY = 'tc-chat-sessions-backup';
const MAX_STORED_SESSIONS = 80;
const MAX_STORED_IMAGE_CHARS = 180_000;
const DEFAULT_TITLES = new Set(['New Chat', 'Nuevo Chat']);

function defaultNewChatTitle(): string {
  try {
    return localStorage.getItem('tc-lang') === 'en' ? 'New Chat' : 'Nuevo Chat';
  } catch {
    return 'Nuevo Chat';
  }
}

function isDefaultTitle(title: string): boolean {
  return DEFAULT_TITLES.has(title.trim());
}

function isBlankDefaultSession(session: ChatSession): boolean {
  return session.messages.length === 0 && isDefaultTitle(session.title);
}
const MAX_TOTAL_BYTES = 4 * 1024 * 1024; // 4 MB safe localStorage limit
const SAVE_DEBOUNCE_MS = 500;
const IMAGE_OMITTED_ES = '[Imagen adjunta no guardada para proteger el historial]';
const IMAGE_OMITTED_EN = '[Attached image was not saved to protect chat history]';

function imageOmittedText(): string {
  try {
    return localStorage.getItem('tc-lang') === 'en' ? IMAGE_OMITTED_EN : IMAGE_OMITTED_ES;
  } catch {
    return IMAGE_OMITTED_ES;
  }
}

function loadDeletedSessions(): Record<string, number> {
  try {
    const parsed = JSON.parse(localStorage.getItem('tc-chat-deleted-ids') || '{}');
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function filterDeletedSessions(sessions: ChatSession[]): ChatSession[] {
  const deleted = loadDeletedSessions();
  return sessions.filter((session) => {
    const deletedAt = deleted[session.id] ?? 0;
    return !deletedAt || deletedAt < (session.updatedAt ?? 0);
  });
}

function loadSessions(): ChatSession[] {
  // Try primary first, then backup on corruption
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? filterDeletedSessions(parsed) : [];
    }
  } catch {
    // Primary corrupted — try backup
    try {
      const backup = localStorage.getItem(STORAGE_BACKUP_KEY);
      if (backup) {
        const restored = JSON.parse(backup);
        if (Array.isArray(restored)) {
          localStorage.setItem(STORAGE_KEY, backup);
          return filterDeletedSessions(restored);
        }
      }
    } catch { /* both corrupted */ }
  }
  return [];
}

function estimateSize(sessions: ChatSession[]): number {
  try {
    return new Blob([JSON.stringify(sessions)]).size;
  } catch {
    return 0;
  }
}

function compactForStorage(sessions: ChatSession[], stripAllImages = false): ChatSession[] {
  return sessions.slice(0, MAX_STORED_SESSIONS).map((session) => ({
    ...session,
    messages: session.messages.map((msg) => {
      if (!msg.image) return msg;
      if (!stripAllImages && msg.image.length <= MAX_STORED_IMAGE_CHARS) return msg;
      const { image: _image, ...rest } = msg;
      const notice = imageOmittedText();
      return {
        ...rest,
        content: rest.content ? `${rest.content}\n\n${notice}` : notice,
      };
    }),
  }));
}

function saveSessions(sessions: ChatSession[]): void {
  let compacted = sessions.filter(s => s.messages.length > 0);
  compacted = compactForStorage(compacted);
  // Progressive compaction: trim until under localStorage quota
  while (estimateSize(compacted) > MAX_TOTAL_BYTES && compacted.length > 5) {
    compacted = compactForStorage(compacted, true);
    if (estimateSize(compacted) > MAX_TOTAL_BYTES && compacted.length > 5) {
      compacted = compacted.slice(0, Math.floor(compacted.length * 0.8));
    }
  }
  try {
    const serialized = JSON.stringify(compacted);
    localStorage.setItem(STORAGE_KEY, serialized);
    try {
      localStorage.setItem(STORAGE_BACKUP_KEY, serialized);
    } catch {
      // The backup is best-effort; never shrink a successfully saved primary
      // just because localStorage cannot afford a duplicate copy.
      try { localStorage.removeItem(STORAGE_BACKUP_KEY); } catch { /* ignore */ }
    }
    scheduleSharedStateSync();
  } catch {
    const minimal = compactForStorage(compacted, true).slice(0, 25);
    try {
      const serialized = JSON.stringify(minimal);
      localStorage.setItem(STORAGE_KEY, serialized);
      try {
        localStorage.setItem(STORAGE_BACKUP_KEY, serialized);
      } catch {
        try { localStorage.removeItem(STORAGE_BACKUP_KEY); } catch { /* ignore */ }
      }
      scheduleSharedStateSync();
    } catch { /* localStorage completely full */ }
  }
}

export function useChatHistory() {
  const [initialState] = useState(() => {
    const list = loadSessions();
    return { sessions: list, activeId: list.length > 0 ? list[0].id : null };
  });
  const [sessions, setSessions] = useState<ChatSession[]>(initialState.sessions);
  const [activeId, setActiveId] = useState<string | null>(initialState.activeId);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const latestSessionsRef = useRef<ChatSession[]>(initialState.sessions);

  const flushPendingSave = useCallback(() => {
    clearTimeout(debounceRef.current);
    saveSessions(latestSessionsRef.current);
  }, []);

  const persist = useCallback((updater: ChatSession[] | ((prev: ChatSession[]) => ChatSession[])) => {
    let next: ChatSession[] = [];
    setSessions((prev) => {
      const updated = typeof updater === 'function' ? updater(prev) : updater;
      latestSessionsRef.current = updated;
      // Debounce writes: save at most once per SAVE_DEBOUNCE_MS
      clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => saveSessions(updated), SAVE_DEBOUNCE_MS);
      next = updated;
      return updated;
    });
    return next;
  }, []);

  const activeSession = sessions.find((s) => s.id === activeId) ?? null;

  const lastSyncRawRef = useRef<string | null>(null);

  useEffect(() => onSharedStateUpdated(() => {
    const raw = localStorage.getItem('tc-chat-sessions');
    if (raw === lastSyncRawRef.current) return;
    lastSyncRawRef.current = raw;
    const list = loadSessions();
    setSessions(list);
    setActiveId((current) => current && list.some((s) => s.id === current) ? current : list[0]?.id ?? null);
  }), []);

  const createSession = useCallback(
    (engine: ChatEngine = 'ollama', title = defaultNewChatTitle()) => {
      const session: ChatSession = {
        id: uid(),
        title,
        messages: [],
        engine,
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      persist((prev) => [session, ...prev.filter((s) => s.id !== session.id && !isBlankDefaultSession(s))]);
      setActiveId(session.id);
      return session;
    },
    [persist],
  );

  useEffect(() => {
    latestSessionsRef.current = sessions;
  }, [sessions]);

  useEffect(() => {
    const flush = () => flushPendingSave();
    const flushIfHidden = () => {
      if (document.hidden) flushPendingSave();
    };
    window.addEventListener('beforeunload', flush);
    window.addEventListener('pagehide', flush);
    document.addEventListener('visibilitychange', flushIfHidden);
    return () => {
      window.removeEventListener('beforeunload', flush);
      window.removeEventListener('pagehide', flush);
      document.removeEventListener('visibilitychange', flushIfHidden);
      clearTimeout(debounceRef.current);
      saveSessions(latestSessionsRef.current);
    };
  }, [flushPendingSave]);

  const deleteSession = useCallback(
    (id: string) => {
      markChatSessionDeleted(id);
      const updated = sessions.filter((s) => s.id !== id);
      persist(updated);
      if (activeId === id) {
        setActiveId(updated.length > 0 ? updated[0].id : null);
      }
    },
    [sessions, activeId, persist],
  );

  const selectSession = useCallback((id: string) => {
    setActiveId(id);
  }, []);

  const updateSession = useCallback(
    (messages: ChatMessage[]) => {
      persist((prev) => prev.map((s) => {
        if (s.id !== activeId) return s;
        // If the chat is empty and has no messages, skip creating title from empty string
        const title =
          isDefaultTitle(s.title) && messages.length > 0
            ? generateTitle(messages[0].content)
            : s.title;
        return { ...s, messages, title, updatedAt: Date.now() };
      }));
    },
    [activeId, persist],
  );

  const setEngine = useCallback(
    (engine: ChatEngine) => {
      persist((prev) => prev.map((s) =>
        s.id === activeId ? { ...s, engine, updatedAt: Date.now() } : s,
      ));
    },
    [activeId, persist],
  );

  return {
    sessions,
    activeSession,
    activeId,
    createSession,
    deleteSession,
    selectSession,
    updateSession,
    setEngine,
  };
}
