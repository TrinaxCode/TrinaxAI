import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import type { DisplayChip } from './types';

interface EmptyChatProps {
  isDark: boolean;
  motd: string;
  rotation: number;
  chips: DisplayChip[];
  /** Optional supporting line under the rotating headline (used by the agent). */
  hint?: string;
  /** The agent page already owns an h1 in its header. */
  headingAs?: 'h1' | 'h2';
  /** Max width of the chip row; the default keeps chat chips compact, the agent widens it to fit three per row. */
  chipsMaxWidth?: string;
}

export default function EmptyChat({ isDark, motd, rotation, chips, hint, headingAs = 'h1', chipsMaxWidth = 'max-w-md' }: EmptyChatProps) {
  const prefersReducedMotion = useReducedMotion();
  const Heading = headingAs === 'h2' ? motion.h2 : motion.h1;
  return (
    <div className="empty-chat flex flex-1 flex-col items-center justify-center gap-6 px-6 pb-12 pt-6">
      <div className="empty-chat-visual animate-float">
        <div className={`flex h-20 w-20 items-center justify-center rounded-full p-1.5 md:h-24 md:w-24 ${isDark ? 'bg-black shadow-lg' : 'bg-white shadow-[0_0_14px_1px_rgba(15,23,42,0.14)]'}`}>
          <img src="/logo-for-ai.webp" alt="TrinaxAI" className={`${isDark ? 'animate-glow' : ''} h-full w-full rounded-full object-contain opacity-85`} width={80} height={80} draggable={false} />
        </div>
      </div>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={motd}
          className="flex max-w-2xl flex-col items-center gap-2"
          initial={{ opacity: prefersReducedMotion ? 1 : 0, y: prefersReducedMotion ? 0 : 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: prefersReducedMotion ? 0 : -6 }}
          transition={{ duration: prefersReducedMotion ? 0 : 0.25, ease: 'easeOut' }}
        >
          <Heading
            className={`chat-empty-motd empty-chat-copy max-w-2xl text-center text-[clamp(1.5rem,3vw,2.25rem)] font-semibold leading-tight tracking-tight ${isDark ? 'text-white/90' : 'text-slate-800'}`}
          >
            {motd}
          </Heading>
          {hint && <p className={`text-center text-[15px] leading-relaxed ${isDark ? 'text-white/70' : 'text-gray-600'}`}>{hint}</p>}
        </motion.div>
      </AnimatePresence>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={rotation}
          className={`flex ${chipsMaxWidth} flex-wrap items-center justify-center gap-1.5 sm:gap-2.5`}
          initial={{ opacity: prefersReducedMotion ? 1 : 0, y: prefersReducedMotion ? 0 : 5 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: prefersReducedMotion ? 0 : -5 }}
          transition={{ duration: prefersReducedMotion ? 0 : 0.22, ease: 'easeOut' }}
        >
          {chips.map((chip) => (
            <button
              key={`${chip.label}-${chip.idx}`}
              onClick={chip.action}
              className={`chip-elegant relative flex min-h-11 max-w-full items-center gap-2 overflow-hidden rounded-xl border px-3 py-2 text-sm font-medium focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${isDark ? 'border-white/[0.12] bg-white/[0.05] text-slate-200' : 'border-slate-200 bg-white text-slate-700'}`}
            >
              {chip.icon && <span className="chip-elegant-icon flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-sm leading-none">{chip.icon}</span>}
              <span className="relative z-[1] min-w-0 break-words text-left">{chip.label}</span>
            </button>
          ))}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
