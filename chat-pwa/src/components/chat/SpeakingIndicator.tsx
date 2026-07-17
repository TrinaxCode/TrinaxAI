import { AnimatePresence, motion } from 'framer-motion';
import { useI18n } from '../../i18n/I18nContext';

export default function SpeakingIndicator({ speaking }: { speaking: boolean }) {
  const { t } = useI18n();
  return (
    <AnimatePresence>
      {speaking && (
        <motion.div
          initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
          className="flex shrink-0 items-center justify-center gap-3 border-t border-[#006bbd]/20 bg-[#006bbd]/10 px-4 py-2.5"
          role="status"
        >
          <div className="flex h-6 items-center gap-0.5" aria-hidden="true">
            {[3, 12, 6, 16, 4, 10, 5].map((height, index) => (
              <motion.div
                key={index}
                className="w-1 rounded-full bg-[#006bbd]"
                animate={{ height: [Math.max(2, height - 6), height, Math.max(2, height - 4), height] }}
                transition={{ repeat: Infinity, repeatType: 'reverse', duration: 0.35 + index * 0.1, ease: 'easeInOut' }}
              />
            ))}
          </div>
          <span className="text-xs font-medium text-[#006bbd]">{t('speaking')}</span>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
