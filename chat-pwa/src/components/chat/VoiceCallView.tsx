import { motion } from 'framer-motion';
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
  const status = speaking ? t('speaking') : thinking ? t('thinking') : listening ? t('listening') : t('voiceMode');
  const active = speaking || listening || thinking;

  return (
    <section className={`relative flex min-h-0 flex-1 flex-col items-center justify-center overflow-hidden px-6 ${isDark ? 'bg-[#080b10]' : 'bg-slate-50'}`} aria-label={t('voiceMode')}>
      <div className={`pointer-events-none absolute inset-0 opacity-70 ${isDark ? 'bg-[radial-gradient(circle_at_50%_42%,rgba(0,107,189,0.20),transparent_42%)]' : 'bg-[radial-gradient(circle_at_50%_42%,rgba(0,107,189,0.12),transparent_42%)]'}`} />
      <div className="relative flex flex-col items-center">
        <motion.div
          className="relative grid h-40 w-40 place-items-center rounded-full bg-gradient-to-br from-[#39a8ef] via-[#006bbd] to-[#063b72] shadow-[0_0_70px_rgba(0,107,189,0.45)] sm:h-48 sm:w-48"
          animate={active ? { scale: [1, 1.045, 1], boxShadow: ['0 0 55px rgba(0,107,189,.35)', '0 0 90px rgba(0,143,230,.62)', '0 0 55px rgba(0,107,189,.35)'] } : { scale: 1 }}
          transition={{ duration: speaking ? 1.05 : 1.8, repeat: active ? Infinity : 0, ease: 'easeInOut' }}
        >
          <div className="absolute inset-3 rounded-full border border-white/25" />
          <div className="absolute inset-8 rounded-full bg-white/10 blur-xl" />
          {speaking ? <MdVolumeUp size={42} className="relative text-white" /> : <MdMic size={42} className="relative text-white" />}
        </motion.div>
        <motion.p key={status} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className={`mt-8 text-sm font-medium ${isDark ? 'text-white/75' : 'text-slate-600'}`} role="status">
          {status}
        </motion.p>
      </div>
      <button type="button" onClick={onEnd} className="absolute bottom-8 grid h-14 w-14 place-items-center rounded-full bg-red-500 text-white shadow-lg shadow-red-500/25 transition hover:bg-red-600 active:scale-95" aria-label={t('exitVoiceMode')} title={t('exitVoiceMode')}>
        <MdCallEnd size={25} />
      </button>
    </section>
  );
}
