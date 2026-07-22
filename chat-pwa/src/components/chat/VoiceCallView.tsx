import { motion, useReducedMotion } from 'framer-motion';
import { MdCallEnd, MdMic, MdVolumeUp } from 'react-icons/md';
import { useI18n } from '../../i18n/I18nContext';

interface VoiceCallViewProps {
  isDark: boolean;
  listening: boolean;
  speaking: boolean;
  thinking: boolean;
  onEnd: () => void;
}

export default function VoiceCallView({ isDark, listening, speaking, thinking, onEnd }: VoiceCallViewProps) {
  const { t } = useI18n();
  const reduceMotion = useReducedMotion();
  const status = speaking ? t('speaking') : thinking ? t('thinking') : listening ? t('listening') : t('voiceMode');
  const active = speaking || listening || thinking;
  const foreground = isDark ? 'text-white' : 'text-slate-900';

  return (
    <section className={`relative flex min-h-0 flex-1 flex-col items-center justify-center overflow-hidden px-6 pb-28 pt-12 ${isDark ? 'bg-[#05080d]' : 'bg-[#f4f9fd]'}`} aria-label={t('voiceMode')}>
      <div className={`pointer-events-none absolute inset-0 ${isDark ? 'bg-[radial-gradient(circle_at_50%_38%,rgba(14,165,233,0.23),transparent_38%),radial-gradient(circle_at_18%_82%,rgba(0,107,189,0.13),transparent_26%)]' : 'bg-[radial-gradient(circle_at_50%_38%,rgba(14,165,233,0.18),transparent_38%),radial-gradient(circle_at_18%_82%,rgba(0,107,189,0.10),transparent_26%)]'}`} />
      <div className={`pointer-events-none absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t ${isDark ? 'from-black/50' : 'from-white/70'} to-transparent`} />

      <div className="relative flex flex-col items-center text-center">
        <div className="relative grid h-52 w-52 place-items-center sm:h-60 sm:w-60">
          {[1, 0.78, 0.58].map((scale, index) => (
            <motion.span
              key={scale}
              className={`absolute inset-0 rounded-full border ${isDark ? 'border-sky-300/10' : 'border-sky-700/10'}`}
              style={{ scale }}
              animate={active && !reduceMotion ? { opacity: [0.2, 0.65, 0.2], scale: [scale, scale + 0.035, scale] } : { opacity: 0.35, scale }}
              transition={{ duration: 2.5, delay: index * 0.25, repeat: active && !reduceMotion ? Infinity : 0, ease: 'easeInOut' }}
            />
          ))}
          <motion.div
            className="relative grid h-28 w-28 place-items-center rounded-full border border-white/30 bg-gradient-to-br from-[#4fc3f7] via-[#087dc4] to-[#06467e] shadow-[0_20px_65px_rgba(0,107,189,0.42)] sm:h-32 sm:w-32"
            animate={active && !reduceMotion ? { scale: [1, 1.055, 1], boxShadow: ['0 20px 55px rgba(0,107,189,.34)', '0 20px 80px rgba(14,165,233,.55)', '0 20px 55px rgba(0,107,189,.34)'] } : { scale: 1 }}
            transition={{ duration: speaking ? 1.05 : 1.8, repeat: active && !reduceMotion ? Infinity : 0, ease: 'easeInOut' }}
          >
            <div className="absolute inset-2 rounded-full border border-white/20" />
            <div className="absolute inset-7 rounded-full bg-white/20 blur-xl" />
            {speaking ? <MdVolumeUp size={38} className="relative text-white" /> : <MdMic size={38} className="relative text-white" />}
          </motion.div>
        </div>
        <motion.p key={status} initial={reduceMotion ? false : { opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className={`mt-6 text-lg font-semibold ${foreground}`} role="status" aria-live="polite">
          {status}
        </motion.p>
        <div className="mt-4 flex h-6 items-center justify-center gap-1" aria-hidden="true">
          {[0, 1, 2, 3, 4].map((bar) => (
            <motion.span
              key={bar}
              className={`w-1 rounded-full ${active ? 'bg-sky-400' : isDark ? 'bg-white/20' : 'bg-slate-300'}`}
              animate={active && !reduceMotion ? { height: [5, 20 - Math.abs(2 - bar) * 4, 5] } : { height: 5 }}
              transition={{ duration: 0.8, delay: bar * 0.1, repeat: active && !reduceMotion ? Infinity : 0, ease: 'easeInOut' }}
            />
          ))}
        </div>
      </div>
      <button type="button" onClick={onEnd} className="absolute bottom-[max(2rem,env(safe-area-inset-bottom))] flex min-h-14 items-center gap-3 rounded-full bg-red-500 px-6 font-semibold text-white shadow-lg shadow-red-500/25 transition hover:bg-red-600 active:scale-95" aria-label={t('exitVoiceMode')} title={t('exitVoiceMode')}>
        <MdCallEnd size={24} />
        <span>{t('exitVoiceMode')}</span>
      </button>
    </section>
  );
}
