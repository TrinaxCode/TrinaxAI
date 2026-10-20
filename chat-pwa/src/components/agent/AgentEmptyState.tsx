import { useEffect, useMemo, useState } from 'react';
import type { Translate } from '../chat/types';
import EmptyChat from '../chat/EmptyChat';
import { AGENT_SUGGESTIONS, AGENT_WELCOME_MESSAGES } from './agentWelcome';

interface AgentEmptyStateProps {
  isDark: boolean;
  t: Translate;
  paused: boolean;
  onSelect: (prompt: string) => void;
  /** Changes whenever a new session starts, so the welcome copy and chips reshuffle like a new chat. */
  resetKey?: number;
}

const SUGGESTION_COUNT = 3;

function shuffled<T>(items: readonly T[]): T[] {
  const next = [...items];
  for (let index = next.length - 1; index > 0; index -= 1) {
    const swap = Math.floor(Math.random() * (index + 1));
    [next[index], next[swap]] = [next[swap], next[index]];
  }
  return next;
}

/** Same welcome surface as a new chat: rotating headline plus rotating quick-start chips. */
export default function AgentEmptyState({ isDark, t, paused, onSelect, resetKey = 0 }: AgentEmptyStateProps) {
  const order = useMemo(() => shuffled(AGENT_SUGGESTIONS), [resetKey]);
  const [messageIndex, setMessageIndex] = useState(() => Math.floor(Math.random() * AGENT_WELCOME_MESSAGES.length));
  const [suggestionIndex, setSuggestionIndex] = useState(0);
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    setMessageIndex(Math.floor(Math.random() * AGENT_WELCOME_MESSAGES.length));
    setSuggestionIndex(0);
  }, [resetKey]);

  useEffect(() => {
    if (paused || focused) return undefined;
    const messages = window.setInterval(() => {
      if (!document.hidden) setMessageIndex((current) => (current + 1) % AGENT_WELCOME_MESSAGES.length);
    }, 4_000);
    const suggestions = window.setInterval(() => {
      if (!document.hidden) setSuggestionIndex((current) => current + 1);
    }, 15_000);
    return () => {
      window.clearInterval(messages);
      window.clearInterval(suggestions);
    };
  }, [paused, focused]);

  const [title, hint] = AGENT_WELCOME_MESSAGES[messageIndex];
  const chips = Array.from({ length: SUGGESTION_COUNT }, (_, index) => {
    const label = order[(suggestionIndex * SUGGESTION_COUNT + index) % order.length];
    return {
      label: t(label),
      icon: '',
      idx: index,
      action: () => onSelect(t(`${label}Prompt`)),
    };
  });

  return (
    <div
      className="agent-empty-state flex min-h-0 flex-1 flex-col"
      onFocusCapture={() => setFocused(true)}
      onBlurCapture={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false); }}
    >
      <EmptyChat isDark={isDark} motd={t(title)} hint={t(hint)} rotation={suggestionIndex} chips={chips} headingAs="h2" chipsMaxWidth="max-w-4xl" />
    </div>
  );
}
