import { useEffect, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import type { Translate } from '../chat/types';
import { AGENT_SUGGESTIONS, AGENT_WELCOME_MESSAGES } from './agentWelcome';

interface AgentEmptyStateProps {
  isDark: boolean;
  t: Translate;
  paused: boolean;
  onSelect: (prompt: string) => void;
}

export default function AgentEmptyState({ isDark, t, paused, onSelect }: AgentEmptyStateProps) {
  const [messageIndex, setMessageIndex] = useState(0);
  const [suggestionIndex, setSuggestionIndex] = useState(0);
  const [focused, setFocused] = useState(false);
  const prefersReducedMotion = useReducedMotion();

  useEffect(() => {
    if (paused || focused) return;
    const messages = window.setInterval(() => {
      if (!document.hidden) setMessageIndex((current) => (current + 1) % AGENT_WELCOME_MESSAGES.length);
    }, 4_000);
    const suggestions = window.setInterval(() => {
      if (!document.hidden) setSuggestionIndex((current) => (current + 3) % AGENT_SUGGESTIONS.length);
    }, 15_000);
    return () => {
      window.clearInterval(messages);
      window.clearInterval(suggestions);
    };
  }, [paused, focused]);

  const [title, hint] = AGENT_WELCOME_MESSAGES[messageIndex];
  const chips = Array.from({ length: 3 }, (_, index) => AGENT_SUGGESTIONS[(suggestionIndex + index) % AGENT_SUGGESTIONS.length]);
  const entrance = {
    initial: { opacity: prefersReducedMotion ? 1 : 0, y: prefersReducedMotion ? 0 : 5 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: prefersReducedMotion ? 0 : 0.22, ease: 'easeOut' as const },
  };

  return (
    <div
      className="agent-empty-state flex min-h-full flex-col items-center justify-center gap-6 px-6 pb-12 pt-6 text-center"
      onFocusCapture={() => setFocused(true)}
      onBlurCapture={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false); }}
    >
      <div className="empty-chat-visual animate-float">
        <div className={`flex h-20 w-20 items-center justify-center rounded-full p-1.5 md:h-24 md:w-24 ${isDark ? 'bg-black shadow-lg' : 'bg-white shadow-[0_0_14px_1px_rgba(15,23,42,0.14)]'}`}>
          <img src="/logo-for-ai.webp" alt="TrinaxAI" className={`${isDark ? 'animate-glow' : ''} h-full w-full rounded-full object-contain opacity-85`} width={80} height={80} draggable={false} />
        </div>
      </div>
      <motion.div key={title} className="max-w-2xl space-y-2" {...entrance} initial={messageIndex === 0 ? false : entrance.initial}>
        <h2 className={`chat-empty-motd empty-chat-copy mx-auto text-[clamp(1.5rem,3vw,2.25rem)] font-semibold leading-tight tracking-tight ${isDark ? 'text-white/90' : 'text-slate-800'}`}>{t(title)}</h2>
        <p className={`text-[15px] leading-relaxed ${isDark ? 'text-white/70' : 'text-gray-600'}`}>{t(hint)}</p>
      </motion.div>
      <motion.div key={suggestionIndex} className="flex max-w-md flex-wrap items-center justify-center gap-1.5 sm:gap-2.5" {...entrance} initial={suggestionIndex === 0 ? false : entrance.initial}>
        {chips.map((label) => (
          <button
            key={label}
            type="button"
            onClick={() => onSelect(t(`${label}Prompt`))}
            className={`agent-suggestion chip-elegant relative flex min-h-11 max-w-full items-center gap-2 overflow-hidden rounded-xl border px-3 py-2 text-sm font-medium focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${isDark ? 'border-white/[0.12] bg-white/[0.05] text-slate-200' : 'border-slate-200 bg-white text-slate-700'}`}
          >
            <span className="relative z-[1] min-w-0 break-words text-left">{t(label)}</span>
          </button>
        ))}
      </motion.div>
    </div>
  );
}
