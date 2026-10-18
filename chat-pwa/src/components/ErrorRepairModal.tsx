import { useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { MdErrorOutline } from 'react-icons/md';
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
          <div aria-hidden="true" className="absolute inset-0 bg-[#07111e]/70 backdrop-blur-sm" onClick={onCancel} />
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
            className={`relative max-h-[calc(100dvh_-_2rem)] w-full max-w-sm overscroll-contain overflow-y-auto rounded-2xl border p-5 shadow-[0_24px_80px_rgba(4,19,35,0.28)] sm:p-6 ${
              dark ? 'border-white/15 bg-[#111c29] shadow-[0_24px_80px_rgba(0,0,0,0.55)]' : 'border-slate-200 bg-white'
            }`}
          >
            <span className={`mb-4 grid h-11 w-11 place-items-center rounded-xl ${dark ? 'bg-red-400/10 text-red-300' : 'bg-red-50 text-red-700'}`} aria-hidden="true"><MdErrorOutline size={24} /></span>
            <h3 id={titleId} className={`mb-2 text-lg font-semibold ${dark ? 'text-white' : 'text-slate-900'}`}>{title}</h3>
            <p className={`mb-3 text-sm leading-relaxed ${dark ? 'text-white/75' : 'text-slate-600'}`}>{message}</p>
            <p id={descriptionId} className={`mb-5 whitespace-pre-line rounded-xl border p-3 text-sm leading-relaxed ${dark ? 'border-white/10 bg-white/[0.04] text-white/80' : 'border-slate-200 bg-slate-50 text-slate-700'}`}>{details}</p>
            <div className="flex flex-wrap gap-3">
              {showCancel && (
                <button
                  ref={cancelRef}
                  type="button"
                  onClick={onCancel}
                  className={`min-h-11 min-w-0 flex-1 rounded-xl px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${dark ? 'bg-white/[0.08] text-white/85 hover:bg-white/[0.14]' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}
                >
                  {cancelLabel}
                </button>
              )}
              <button
                ref={confirmRef}
                type="button"
                onClick={onConfirm}
                disabled={confirmDisabled}
                className={`${showCancel ? 'min-w-0 flex-1' : 'w-full'} min-h-11 rounded-xl bg-[#006bbd] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[#0059a0] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] disabled:cursor-wait disabled:opacity-40`}
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
