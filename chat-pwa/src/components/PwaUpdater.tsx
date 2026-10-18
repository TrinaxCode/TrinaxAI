import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MdClose } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';

interface PwaUpdaterProps {
  needsUpdate: boolean;
  onRefresh: () => void;
}

export default function PwaUpdater({ needsUpdate, onRefresh }: PwaUpdaterProps) {
  const { t } = useI18n();
  const [dismissed, setDismissed] = useState(false);

  // A dismissal belongs to the current version only. Surface a later update.
  useEffect(() => {
    if (needsUpdate) setDismissed(false);
  }, [needsUpdate]);

  return (
    <AnimatePresence>
      {needsUpdate && !dismissed && (
        <div className="pointer-events-none fixed inset-x-0 bottom-[calc(env(safe-area-inset-bottom,0px)+6.5rem)] z-[80] flex justify-center px-3 sm:inset-x-auto sm:bottom-4 sm:right-4 sm:px-0">
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.96 }}
            role="status"
            aria-live="polite"
            className="pointer-events-auto grid w-full max-w-md grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-2 rounded-2xl border border-[#006bbd]/20 bg-white/95 p-2.5 text-left text-sm font-medium text-slate-800 shadow-[0_16px_40px_rgba(15,42,70,0.2)] backdrop-blur-xl dark:border-[#4aa7ed]/30 dark:bg-[#111c29]/95 dark:text-white/90"
          >
            <span className="min-w-0 break-words pl-1">{t('pwaUpdateAvailable')}</span>
            <button
              type="button"
              onClick={onRefresh}
              className="min-h-11 shrink-0 rounded-xl bg-[#006bbd] px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-[#0059a0] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed]"
            >
              {t('pwaUpdate')}
            </button>
            <button
              type="button"
              onClick={() => setDismissed(true)}
              className="grid h-11 w-11 shrink-0 place-items-center rounded-xl text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] dark:text-white/70 dark:hover:bg-white/10 dark:hover:text-white"
              aria-label={t('close')}
            >
              <MdClose size={18} aria-hidden="true" />
            </button>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
