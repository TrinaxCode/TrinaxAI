import { AnimatePresence, motion } from 'framer-motion';
import type { DisplayChip } from './types';

interface EmptyChatProps {
  isDark: boolean;
  motd: string;
  rotation: number;
  chips: DisplayChip[];
}

export default function EmptyChat({ isDark, motd, rotation, chips }: EmptyChatProps) {
  return (
    <motion.div className="empty-chat flex flex-1 flex-col items-center justify-center gap-6 px-6" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <motion.div className="empty-chat-visual animate-float">
        <div className={`flex h-20 w-20 items-center justify-center rounded-full p-1.5 md:h-24 md:w-24 ${isDark ? 'bg-black shadow-lg' : 'bg-white shadow-[0_0_14px_1px_rgba(15,23,42,0.14)]'}`}>
          <img src="/logo-for-ai.webp" alt="TrinaxAI" className={`${isDark ? 'animate-glow' : ''} h-full w-full rounded-full object-contain opacity-85`} width={80} height={80} draggable={false} />
        </div>
      </motion.div>
      <AnimatePresence mode="popLayout">
        <motion.p
          key={motd}
          className={`chat-empty-motd empty-chat-copy max-w-xs text-center text-sm font-light tracking-wide md:text-base ${isDark ? 'text-white/50' : 'text-gray-600'}`}
          initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.5, ease: 'easeInOut' }}
        >
          {motd}
        </motion.p>
      </AnimatePresence>
      <AnimatePresence mode="popLayout">
        <motion.div
          key={rotation}
          className="flex max-w-md flex-wrap items-center justify-center gap-1.5 sm:gap-2.5"
          initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }}
          transition={{ duration: 0.22, ease: 'easeOut' }}
        >
          {chips.map((chip) => (
            <motion.button
              key={`${chip.label}-${chip.idx}`}
              initial={{ opacity: 0, y: 8, scale: 0.94 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.32, delay: 0.06 + chip.idx * 0.07, ease: [0.16, 1, 0.3, 1] }}
              whileHover={{ scale: 1.05, y: -2 }} whileTap={{ scale: 0.96 }}
              onClick={chip.action}
              className={`chip-elegant relative flex items-center gap-1.5 overflow-hidden rounded-full border py-1 pl-1.5 pr-2.5 text-[11px] font-medium sm:gap-2 sm:px-3.5 sm:py-1.5 sm:text-xs ${isDark ? 'border-white/[0.09] bg-gradient-to-b from-white/[0.06] to-white/[0.015] text-white/70' : 'border-gray-200/80 bg-gradient-to-b from-white to-gray-50 text-gray-600'}`}
            >
              {chip.icon && <span className="chip-elegant-icon flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[11px] leading-none sm:h-5 sm:w-5 sm:text-[13px]">{chip.icon}</span>}
              <span className="relative z-[1] whitespace-nowrap">{chip.label}</span>
            </motion.button>
          ))}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}
