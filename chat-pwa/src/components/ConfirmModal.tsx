import { useRef, useEffect, useCallback, useId } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useTheme } from '../theme/ThemeContext';
import { useI18n } from '../i18n/I18nContext';

interface ConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  showCancel?: boolean;
  children?: React.ReactNode;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmModal({
  open, title, message, confirmLabel, cancelLabel,
  danger = false, showCancel = true, children, onConfirm, onCancel,
}: ConfirmModalProps) {
  const { isDark } = useTheme();
  const { t } = useI18n();
  const confirmText = confirmLabel || t('confirmDefault');
  const cancelText = cancelLabel || t('cancelDefault');
  const confirmRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();

  // Focus trap: cycle focus within modal on Tab / Shift+Tab.
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      onCancel();
      return;
    }
    if (e.key !== 'Tab') return;
    const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    if (!focusable || focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }, [onCancel]);

  // Keep the background out of both pointer and accessibility navigation while
  // the portal is open, then return focus to the control that launched it.
  useEffect(() => {
    if (!open) return undefined;
    previousFocusRef.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const timer = window.setTimeout(() => (showCancel ? cancelRef.current : confirmRef.current)?.focus(), 50);
    const portalRoot = dialogRef.current?.closest('[data-confirm-modal-root]');
    const siblings = Array.from(document.body.children)
      .filter((element): element is HTMLElement => element instanceof HTMLElement && element !== portalRoot)
      .map((element) => ({
        element,
        inert: element.inert,
        ariaHidden: element.getAttribute('aria-hidden'),
      }));
    siblings.forEach(({ element }) => {
      element.inert = true;
      element.setAttribute('aria-hidden', 'true');
    });
    return () => {
      window.clearTimeout(timer);
      siblings.forEach(({ element, inert, ariaHidden }) => {
        element.inert = inert;
        if (ariaHidden === null) element.removeAttribute('aria-hidden');
        else element.setAttribute('aria-hidden', ariaHidden);
      });
      window.requestAnimationFrame(() => previousFocusRef.current?.focus());
    };
  }, [open]);

  if (typeof document === 'undefined') return null;

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          data-confirm-modal-root
          className="fixed inset-0 z-[90] flex items-center justify-center p-4"
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
            onKeyDown={handleKeyDown}
            initial={{ opacity: 0, scale: 0.92, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.92, y: 20 }}
          className={`relative w-[calc(100%_-_2rem)] max-w-sm max-h-[calc(100dvh_-_2rem)] overscroll-contain overflow-y-auto p-5 sm:p-6 rounded-2xl border shadow-2xl ${
              isDark ? 'bg-gray-900 border-white/[0.08]' : 'bg-white border-gray-200'
            }`}
          >
            <h3 id={titleId} className={`text-lg font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>{title}</h3>
            <p id={descriptionId} className={`text-sm mb-4 ${isDark ? 'text-white/60' : 'text-gray-600'}`}>{message}</p>
            {children && <div className="mb-4">{children}</div>}
            <div className="flex gap-3">
              {showCancel && (
                <button
                  ref={cancelRef}
                  onClick={onCancel}
                  className={`flex-1 py-2.5 rounded-xl text-sm font-medium transition-[background-color,color,transform] active:scale-95 ${
                    isDark ? 'bg-white/[0.06] text-white/70 hover:bg-white/[0.1]' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {cancelText}
                </button>
              )}
              <button
                ref={confirmRef}
                onClick={onConfirm}
                className={`${showCancel ? 'flex-1' : 'w-full'} py-2.5 rounded-xl text-sm font-medium transition-[background-color,color,transform] active:scale-95 ${
                  danger
                    ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                    : 'bg-[#006bbd] text-white hover:bg-[#0059a0]'
                }`}
              >
                {confirmText}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
