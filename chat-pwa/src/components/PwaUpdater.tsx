import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MdClose } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';

interface PwaUpdaterProps {
  needsUpdate: boolean;
  onRefresh: () => void;
}

export default function PwaUpdater({ needsUpdate, onRefresh }: PwaUpdaterProps) {
  const { lang } = useI18n();
  const [dismissed, setDismissed] = useState(false);

  const label = lang === 'en' ? 'Update available' : 'Actualización disponible';
  const buttonText = lang === 'en' ? 'Update' : 'Actualizar';

  return (
    <AnimatePresence>
      {needsUpdate && !dismissed && (
        <motion.div
          initial={{ opacity: 0, y: 20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -10, scale: 0.95 }}
          className="fixed bottom-0 left-1/2 -translate-x-1/2 z-[101] flex items-center gap-3 px-4 py-3 rounded-xl border text-xs font-medium shadow-lg pointer-events-auto"
          style={{
            background: 'rgba(0,107,189,0.15)',
            borderColor: 'rgba(0,107,189,0.3)',
            color: '#5badf5',
            marginBottom: 'calc(env(safe-area-inset-bottom, 12px) + 12px)',
          }}
        >
          <span>{label}</span>
          <button
            onClick={onRefresh}
            className="px-3 py-1 bg-[#006bbd] text-white rounded-lg hover:bg-[#005299] transition-colors font-medium"
          >
            {buttonText}
          </button>
          <button
            onClick={() => setDismissed(true)}
            className="opacity-50 hover:opacity-100 transition-opacity"
          >
            <MdClose size={14} />
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
