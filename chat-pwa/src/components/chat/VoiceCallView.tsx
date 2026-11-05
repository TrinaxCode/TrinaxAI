import { useEffect } from 'react';
import { motion, useReducedMotion, usePresence, type Variants } from 'framer-motion';
import { MdCallEnd } from 'react-icons/md';
import { useI18n } from '../../i18n/I18nContext';
import VoiceCallOrb, { type CallState } from './VoiceCallOrb';

interface VoiceCallViewProps {
  isDark: boolean;
  listening: boolean;
  speaking: boolean;
  thinking: boolean;
  /** What the user is saying right now (interim speech recognition), if the browser reports it. */
  heard?: string;
  /** The reply being written or spoken. */
  reply?: string;
  onEnd: () => void;
}

const CAPTION_CHARS = 200;
const CLOSING_MS = 750;
const CLOSING_REDUCED_MS = 120;

// Captions show the tail of long text so the newest words stay visible without scrolling.
function captionTail(text: string): string {
  const flat = text.replace(/\s+/g, ' ').trim();
  return flat.length > CAPTION_CHARS ? `…${flat.slice(-CAPTION_CHARS).trimStart()}` : flat;
}

export default function VoiceCallView({ isDark, listening, speaking, thinking, heard = '', reply = '', onEnd }: VoiceCallViewProps) {
  const { t } = useI18n();
  const reduceMotion = useReducedMotion();
  // The parent keeps this view mounted while it leaves, so the hang-up plays
  // out here: the orb collapses and the surface is only released afterwards.
  const [isPresent, safeToRemove] = usePresence();
  const ending = !isPresent;
  useEffect(() => {
    if (isPresent) return undefined;
    const timer = window.setTimeout(() => safeToRemove?.(), reduceMotion ? CLOSING_REDUCED_MS : CLOSING_MS);
    return () => window.clearTimeout(timer);
  }, [isPresent, reduceMotion, safeToRemove]);

  const state: CallState = ending ? 'ending' : speaking ? 'speaking' : thinking ? 'thinking' : listening ? 'listening' : 'idle';
  const status = ending ? t('callEnded') : speaking ? t('speaking') : thinking ? t('thinking') : listening ? t('listening') : t('voiceMode');
  const foreground = isDark ? 'text-white' : 'text-slate-900';
  const caption = ending ? '' : captionTail(speaking || thinking ? reply : listening ? heard : '');

  // The call surface mounts as one unit, so the workspace, status copy and the
  // hang-up control settle in sequence instead of appearing all at once.
  const container: Variants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: reduceMotion ? 0 : 0.08, delayChildren: reduceMotion ? 0 : 0.05 },
    },
  };
  const item: Variants = {
    hidden: { opacity: 0, y: reduceMotion ? 0 : 18, scale: reduceMotion ? 1 : 0.985 },
    show: {
      opacity: 1,
      y: 0,
      scale: 1,
      transition: { duration: reduceMotion ? 0 : 0.36, ease: [0.16, 1, 0.3, 1] },
    },
  };
  const fade: Variants = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { duration: reduceMotion ? 0 : 0.5, ease: 'easeOut' } },
  };

  return (
    <motion.section
      variants={container}
      initial={reduceMotion ? false : 'hidden'}
      animate="show"
      exit={{ opacity: 0, transition: { duration: reduceMotion ? 0.1 : 0.3, delay: reduceMotion ? 0 : 0.42 } }}
      data-call-state={state}
      className={`voice-call-surface relative flex min-h-0 flex-1 flex-col items-center justify-center overflow-hidden px-6 pb-28 pt-12 ${isDark ? 'bg-[#05080d]/70' : 'bg-[#f4f9fd]/70'}`}
      aria-label={t('voiceMode')}
    >
      <h1 className="sr-only">{t('voiceMode')}</h1>
      {/* Subtle radial overlay for depth */}
      <motion.div variants={fade} className={`pointer-events-none absolute inset-0 ${isDark ? 'bg-[radial-gradient(circle_at_50%_38%,rgba(78,163,224,0.14),transparent_50%),radial-gradient(circle_at_18%_82%,rgba(0,107,189,0.10),transparent_35%)]' : 'bg-[radial-gradient(circle_at_50%_38%,rgba(78,163,224,0.12),transparent_50%),radial-gradient(circle_at_18%_82%,rgba(0,107,189,0.08),transparent_35%)]'}`} />
      <motion.div variants={fade} className={`pointer-events-none absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t ${isDark ? 'from-black/50' : 'from-white/70'} to-transparent`} />

      <motion.div variants={item} className="relative z-10 flex flex-col items-center text-center">
        <VoiceCallOrb state={state} isDark={isDark} reduceMotion={Boolean(reduceMotion)} />
        <motion.p key={status} initial={reduceMotion ? false : { opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className={`voice-call-status mt-6 text-lg font-semibold ${foreground}`} role="status" aria-live="polite">
          {status}
        </motion.p>
        {/* Decorative: screen readers already get the status line and the spoken reply. */}
        <p
          aria-hidden="true"
          className={`voice-call-caption mt-4 min-h-[3.75rem] max-w-md text-balance break-words text-base leading-relaxed ${isDark ? 'text-white/70' : 'text-slate-600'}`}
        >
          {caption}
        </p>
      </motion.div>
      <motion.button
        variants={item}
        exit={{ opacity: 0, y: 16, transition: { duration: 0.2 } }}
        autoFocus
        type="button"
        onClick={onEnd}
        disabled={ending}
        className="absolute bottom-[max(2rem,env(safe-area-inset-bottom))] z-10 flex min-h-14 items-center gap-3 rounded-full bg-red-600 px-6 font-semibold text-white shadow-lg shadow-red-500/25 transition hover:bg-red-700 active:scale-95"
        aria-label={t('exitVoiceMode')}
        title={t('exitVoiceMode')}
      >
        <MdCallEnd size={24} />
        <span>{t('exitVoiceMode')}</span>
      </motion.button>
    </motion.section>
  );
}
