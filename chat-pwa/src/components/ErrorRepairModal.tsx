import { useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { useDialogAccessibility } from '../hooks/useDialogAccessibility';

interface ErrorRepairModalProps {
  open: boolean;
  dark: boolean;
  title: string;
  message: string;
  details: string;
  confirmLabel: string;
  cancelLabel?: string;
  confirmDisabled?: boolean;
  showCancel?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ErrorRepairModal({
  open,
  dark,
  title,
  message,
  details,
  confirmLabel,
  cancelLabel,
  confirmDisabled = false,
  showCancel = true,
  onConfirm,
  onCancel,
}: ErrorRepairModalProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const { dialogRef, onKeyDown } = useDialogAccessibility(open, onCancel, showCancel ? cancelRef : confirmRef);
  const titleId = useId();
  const descriptionId = useId();

  if (typeof document === 'undefined') return null;

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          data-modal-root
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <div aria-hidden="true" className="absolute inset-0 bg-black/60" onClick={onCancel} />
          <motion.div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            aria-describedby={descriptionId}
            onKeyDown={onKeyDown}
            initial={{ opacity: 0, scale: 0.92, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.92, y: 20 }}
            className={`relative w-[calc(100%_-_2rem)] max-w-sm max-h-[calc(100dvh_-_2rem)] overflow-y-auto rounded-2xl border p-5 shadow-2xl sm:p-6 ${
              dark ? 'border-white/[0.08] bg-gray-900' : 'border-gray-200 bg-white'
            }`}
          >
            <h3 id={titleId} className={`mb-2 text-lg font-semibold ${dark ? 'text-white' : 'text-gray-900'}`}>{title}</h3>
            <p className={`mb-3 text-sm ${dark ? 'text-white/60' : 'text-gray-600'}`}>{message}</p>
            <p id={descriptionId} className={`mb-5 whitespace-pre-line text-sm ${dark ? 'text-white/75' : 'text-gray-700'}`}>{details}</p>
            <div className="flex gap-3">
              {showCancel && (
                <button
                  ref={cancelRef}
                  type="button"
                  onClick={onCancel}
                  className={`flex-1 rounded-xl py-2.5 text-sm font-medium transition-colors ${dark ? 'bg-white/[0.06] text-white/70 hover:bg-white/[0.1]' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
                >
                  {cancelLabel}
                </button>
              )}
              <button
                ref={confirmRef}
                type="button"
                onClick={onConfirm}
                disabled={confirmDisabled}
                className={`${showCancel ? 'flex-1' : 'w-full'} rounded-xl bg-[#006bbd] py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#0059a0] disabled:cursor-wait disabled:opacity-40`}
              >
                {confirmLabel}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
