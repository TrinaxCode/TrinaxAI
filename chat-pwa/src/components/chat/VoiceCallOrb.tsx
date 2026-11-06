import { AnimatePresence, motion } from 'framer-motion';
import './chat-modern.css';

/** What the call is doing right now; each state has its own emblem and motion. */
export type CallState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'ending';

interface VoiceCallOrbProps {
  state: CallState;
  isDark: boolean;
  reduceMotion: boolean;
}

const BAR_COUNT = 40;

// Deterministic spread so the equalizer looks organic but renders the same every time.
const BARS = Array.from({ length: BAR_COUNT }, (_, index) => ({
  angle: (360 / BAR_COUNT) * index,
  duration: 0.7 + ((index * 37) % 11) * 0.055,
  delay: -(((index * 53) % 17) * 0.07),
  peak: 0.55 + ((index * 29) % 7) * 0.075,
}));

const EASE = [0.16, 1, 0.3, 1] as const;

/** The TrinaxAI mark in its own colours; the disc behind it flips with the theme. */
function BrandMark() {
  return <span aria-hidden="true" className="vc-mark" />;
}

/** A microphone for the moments TrinaxAI is the one listening. */
function MicEmblem({ reduceMotion, isDark }: { reduceMotion: boolean; isDark: boolean }) {
  const wave = (side: 'left' | 'right') => (
    <motion.path
      d={side === 'left' ? 'M6 18c-3 5-3 9 0 14' : 'M42 18c3 5 3 9 0 14'}
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      animate={reduceMotion ? { opacity: 0.7 } : { opacity: [0.2, 1, 0.2] }}
      transition={{ duration: 1.6, repeat: reduceMotion ? 0 : Infinity, ease: 'easeInOut', delay: side === 'left' ? 0 : 0.4 }}
    />
  );
  return (
    <svg viewBox="0 0 48 48" className={`h-14 w-14 ${isDark ? 'text-white' : 'text-[#006bbd]'}`} aria-hidden="true">
      <rect x="17" y="5" width="14" height="25" rx="7" fill="currentColor" />
      <path d="M11 23v1.5a13 13 0 0 0 26 0V23" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" />
      <path d="M24 38v6M17.5 44h13" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" />
      {wave('left')}
      {wave('right')}
    </svg>
  );
}

function ListeningRings({ active, reduceMotion, isDark }: { active: boolean; reduceMotion: boolean; isDark: boolean }) {
  const border = isDark ? 'border-[#4ea3e0]' : 'border-[#006bbd]';
  return (
    <>
      {[0, 1, 2].map((index) => (
        <motion.span
          key={index}
          className={`absolute inset-0 rounded-full border ${border}`}
          initial={{ opacity: 0, scale: 1.2 }}
          // Rings travel inward: sound is being drawn in, as opposed to the outward bars of speech.
          animate={active && !reduceMotion ? { opacity: [0, 0.6, 0], scale: [1.2, 0.74] } : { opacity: 0.25, scale: 1 - index * 0.14 }}
          exit={{ opacity: 0, scale: 0.6, transition: { duration: 0.25 } }}
          transition={{ duration: 2.4, delay: index * 0.8, repeat: active && !reduceMotion ? Infinity : 0, ease: 'easeOut' }}
        />
      ))}
    </>
  );
}

function ThinkingOrbit({ isDark }: { isDark: boolean }) {
  const stroke = isDark ? '#4ea3e0' : '#006bbd';
  return (
    <motion.svg
      viewBox="0 0 100 100"
      className="absolute inset-0 h-full w-full"
      aria-hidden="true"
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9, transition: { duration: 0.2 } }}
    >
      <circle cx="50" cy="50" r="47" fill="none" stroke={stroke} strokeOpacity="0.15" strokeWidth="0.8" />
      <g className="vc-spin" style={{ transformOrigin: '50px 50px' }}>
        <circle cx="50" cy="50" r="47" fill="none" stroke={stroke} strokeWidth="1.8" strokeLinecap="round" strokeDasharray="70 226" />
      </g>
      <g className="vc-spin-reverse" style={{ transformOrigin: '50px 50px' }}>
        <circle cx="50" cy="50" r="41" fill="none" stroke="#4ea3e0" strokeOpacity="0.7" strokeWidth="1.2" strokeLinecap="round" strokeDasharray="28 230" />
      </g>
    </motion.svg>
  );
}

function SpeakingBars() {
  return (
    <motion.div
      aria-hidden="true"
      className="vc-bars absolute inset-0"
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.85, transition: { duration: 0.2 } }}
      transition={{ duration: 0.35, ease: EASE }}
    >
      {BARS.map((bar) => (
        <span key={bar.angle} className="vc-bar" style={{ transform: `rotate(${bar.angle}deg) translateY(calc(var(--vc-radius) * -1))` }}>
          <span
            className="vc-bar-fill"
            style={{ '--vc-dur': `${bar.duration}s`, '--vc-delay': `${bar.delay}s`, '--vc-peak': bar.peak } as React.CSSProperties}
          />
        </span>
      ))}
    </motion.div>
  );
}

const CORE_MOTION: Record<CallState, { scale: number | number[]; duration: number }> = {
  idle: { scale: 1, duration: 1 },
  listening: { scale: [1, 1.045, 1], duration: 2.6 },
  thinking: { scale: [1, 0.96, 1], duration: 1.5 },
  speaking: { scale: [1, 1.07, 1], duration: 0.9 },
  ending: { scale: 1, duration: 1 },
};

/**
 * The call's visual centre. Listening shows a microphone with rings drawn
 * inward, thinking shows the TrinaxAI mark inside an orbit, speaking shows the
 * mark with an outward equalizer, and ending collapses everything to a point.
 */
export default function VoiceCallOrb({ state, isDark, reduceMotion }: VoiceCallOrbProps) {
  const live = state !== 'idle' && state !== 'ending';
  const emblem = state === 'thinking' || state === 'speaking' ? 'mark' : 'mic';
  const core = CORE_MOTION[state];
  const animateCore = !reduceMotion && Array.isArray(core.scale);

  return (
    <div className="voice-call-orb relative grid h-56 w-56 place-items-center sm:h-64 sm:w-64" data-call-state={state} data-emblem={emblem}>
      <motion.div
        aria-hidden="true"
        className={`pointer-events-none absolute -inset-6 rounded-full blur-3xl ${isDark ? 'bg-[#4ea3e0]' : 'bg-[#4ea3e0]'}`}
        animate={{ opacity: state === 'ending' ? 0 : state === 'speaking' ? 0.34 : live ? 0.22 : 0.12, scale: state === 'speaking' && !reduceMotion ? [1, 1.08, 1] : 1 }}
        transition={{ duration: state === 'ending' ? 0.45 : 1.2, repeat: state === 'speaking' && !reduceMotion ? Infinity : 0, ease: 'easeInOut' }}
      />

      <AnimatePresence>
        {(state === 'listening' || state === 'idle') && <ListeningRings key="listening" active={state === 'listening'} reduceMotion={reduceMotion} isDark={isDark} />}
        {state === 'thinking' && <ThinkingOrbit key="thinking" isDark={isDark} />}
        {state === 'speaking' && <SpeakingBars key="speaking" />}
      </AnimatePresence>

      {state === 'ending' && (
        <>
          {[0, 1].map((index) => (
            <motion.span
              key={index}
              aria-hidden="true"
              className={`absolute inset-0 rounded-full border ${isDark ? 'border-[#4ea3e0]' : 'border-[#006bbd]'}`}
              initial={{ opacity: 0.6, scale: 1 }}
              animate={{ opacity: 0, scale: 0.15 }}
              transition={{ duration: 0.55, delay: index * 0.08, ease: [0.5, 0, 0.75, 0] }}
            />
          ))}
          <motion.span
            aria-hidden="true"
            className={`absolute h-32 w-32 rounded-full border-2 ${isDark ? 'border-white/70' : 'border-[#006bbd]/60'}`}
            initial={{ opacity: 0.8, scale: 0.4 }}
            animate={{ opacity: 0, scale: 1.7 }}
            transition={{ duration: 0.6, delay: 0.38, ease: 'easeOut' }}
          />
        </>
      )}

      <motion.div
        className={`voice-call-core relative grid h-32 w-32 place-items-center rounded-full border sm:h-36 sm:w-36 ${isDark ? 'border-white/15 bg-black shadow-[0_20px_65px_rgba(78,163,224,0.35)]' : 'border-slate-200 bg-white shadow-[0_20px_65px_rgba(0,107,189,0.28)]'}`}
        animate={
          state === 'ending'
            ? { scale: [1, 1.1, 0], opacity: [1, 1, 0] }
            : animateCore
              ? { scale: core.scale }
              : { scale: 1 }
        }
        transition={
          state === 'ending'
            ? { duration: 0.6, times: [0, 0.35, 1], ease: 'easeInOut' }
            : { duration: core.duration, repeat: animateCore ? Infinity : 0, ease: 'easeInOut' }
        }
      >
        <div className={`absolute inset-2 rounded-full border ${isDark ? 'border-white/10' : 'border-[#006bbd]/15'}`} />
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={emblem}
            className="relative grid place-items-center"
            initial={reduceMotion ? false : { opacity: 0, scale: 0.6, rotate: emblem === 'mark' ? -12 : 12 }}
            animate={{ opacity: 1, scale: 1, rotate: 0 }}
            exit={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.6, rotate: emblem === 'mark' ? 12 : -12 }}
            transition={{ duration: 0.24, ease: EASE }}
          >
            {emblem === 'mark' ? <BrandMark /> : <MicEmblem reduceMotion={reduceMotion} isDark={isDark} />}
          </motion.div>
        </AnimatePresence>
      </motion.div>
    </div>
  );
}
