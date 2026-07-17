import { useCallback, useEffect, useRef, useState } from 'react';
import { uid } from '../lib/chatUtils';
import type { AgentTurn } from '../components/AgentInterface';
import { LOCAL_DEVICE_WIPE_EVENT } from '../lib/deviceWipe';

/**
 * Persistent history for TrinaxAI Agent, independent of the chat history.
 * Sessions live in localStorage under `tc-agent-sessions` (own store, own
 * search), mirroring the chat sidebar but scoped to agent runs.
 */
export interface AgentSession {
  id: string;
  title: string;
  turns: AgentTurn[];
  workspace: string;
  createdAt: number;
  updatedAt: number;
}

const STORAGE_KEY = 'tc-agent-sessions';
const MAX_SESSIONS = 60;
const SAVE_DEBOUNCE_MS = 400;

function loadSessions(): AgentSession[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    return Array.isArray(parsed) ? parsed.filter((s) => s?.id && Array.isArray(s.turns)) : [];
  } catch {
    return [];
  }
}

function titleFrom(turns: AgentTurn[]): string {
  const firstUser = turns.find((turn) => turn.role === 'user');
  const text = (firstUser?.content ?? '').trim().replace(/\s+/g, ' ');
  if (!text) return '';
  return text.length > 48 ? `${text.slice(0, 48)}…` : text;
}

export function useAgentHistory() {
  const [sessions, setSessions] = useState<AgentSession[]>(() => loadSessions());
  const [activeId, setActiveId] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const latestRef = useRef<AgentSession[]>(sessions);
  const wipedRef = useRef(false);

  const persist = useCallback((next: AgentSession[]) => {
    if (wipedRef.current) return;
    latestRef.current = next;
    setSessions(next);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      // Only sessions with real turns are worth keeping.
      const keep = next.filter((s) => s.turns.length > 0).slice(0, MAX_SESSIONS);
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(keep)); } catch { /* quota */ }
    }, SAVE_DEBOUNCE_MS);
  }, []);

  useEffect(() => {
    const wipe = () => {
      wipedRef.current = true;
      clearTimeout(debounceRef.current);
      latestRef.current = [];
      setSessions([]);
      setActiveId(null);
    };
    window.addEventListener(LOCAL_DEVICE_WIPE_EVENT, wipe);
    return () => {
      clearTimeout(debounceRef.current);
      window.removeEventListener(LOCAL_DEVICE_WIPE_EVENT, wipe);
    };
  }, []);

  const newSession = useCallback((workspace: string): string => {
    const session: AgentSession = {
      id: uid(),
      title: '',
      turns: [],
      workspace,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    persist([session, ...latestRef.current.filter((s) => s.turns.length > 0)]);
    setActiveId(session.id);
    return session.id;
  }, [persist]);

  const saveTurns = useCallback((id: string, turns: AgentTurn[], workspace: string) => {
    const existing = latestRef.current.find((s) => s.id === id);
    const updated: AgentSession = existing
      ? { ...existing, turns, workspace, title: existing.title || titleFrom(turns), updatedAt: Date.now() }
      : { id, title: titleFrom(turns), turns, workspace, createdAt: Date.now(), updatedAt: Date.now() };
    persist([updated, ...latestRef.current.filter((s) => s.id !== id)]);
  }, [persist]);

  const deleteSession = useCallback((id: string) => {
    persist(latestRef.current.filter((s) => s.id !== id));
    setActiveId((current) => (current === id ? null : current));
  }, [persist]);

  const selectSession = useCallback((id: string) => setActiveId(id), []);

  const activeSession = sessions.find((s) => s.id === activeId) ?? null;

  return { sessions, activeSession, activeId, newSession, saveTurns, deleteSession, selectSession, setActiveId };
}
