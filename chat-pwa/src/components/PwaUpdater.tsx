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
        <div
          className="pointer-events-none fixed inset-x-0 bottom-0 z-[101] flex justify-center px-3"
          style={{
            marginBottom: 'calc(env(safe-area-inset-bottom, 12px) + 12px)',
          }}
        >
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.96 }}
            role="status"
            aria-live="polite"
            className="pointer-events-auto flex w-fit max-w-full items-center gap-2 overflow-hidden rounded-lg border px-2.5 py-2 text-center text-[11px] font-medium shadow-lg"
            style={{
              background: 'rgba(0,107,189,0.15)',
              borderColor: 'rgba(0,107,189,0.3)',
              color: '#5badf5',
            }}
          >
            <span className="min-w-0 break-words">{t('pwaUpdateAvailable')}</span>
            <button
              type="button"
              onClick={onRefresh}
              className="min-h-8 shrink-0 rounded-md bg-[#006bbd] px-2.5 py-1 text-[11px] text-white hover:bg-[#005299] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
            >
              {t('pwaUpdate')}
            </button>
            <button
              type="button"
              onClick={() => setDismissed(true)}
              className="grid min-h-8 min-w-8 shrink-0 place-items-center rounded-md opacity-60 hover:bg-white/10 hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
              aria-label={t('close')}
            >
              <MdClose size={15} aria-hidden="true" />
            </button>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
