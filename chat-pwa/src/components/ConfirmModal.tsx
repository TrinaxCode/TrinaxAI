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
  confirmDisabled?: boolean;
  showCancel?: boolean;
  children?: React.ReactNode;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmModal({
  open, title, message, confirmLabel, cancelLabel,
  danger = false, confirmDisabled = false, showCancel = true, children, onConfirm, onCancel,
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
    if (e.key !== 'Tab') return;
    const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
      ':is(button, [href], input, select, textarea, [tabindex]):not([disabled]):not([tabindex="-1"])'
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
  }, []);

  // Keep the background out of both pointer and accessibility navigation while
  // the portal is open, then return focus to the control that launched it.
  useEffect(() => {
    if (!open) return undefined;
    previousFocusRef.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const timer = window.setTimeout(() => {
      if (dialogRef.current?.contains(document.activeElement)) return;
      (showCancel ? cancelRef.current : confirmRef.current)?.focus();
    }, 50);
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      onCancel();
    };
    document.addEventListener('keydown', handleEscape);
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
      document.removeEventListener('keydown', handleEscape);
      siblings.forEach(({ element, inert, ariaHidden }) => {
        element.inert = inert;
        if (ariaHidden === null) element.removeAttribute('aria-hidden');
        else element.setAttribute('aria-hidden', ariaHidden);
      });
      window.requestAnimationFrame(() => previousFocusRef.current?.focus());
    };
  }, [open, onCancel, showCancel]);

  if (typeof document === 'undefined') return null;

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          data-confirm-modal-root
          className="fixed inset-0 z-[90] flex items-center justify-center p-3 sm:p-4"
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
            onKeyDown={handleKeyDown}
            initial={{ opacity: 0, scale: 0.92, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.92, y: 20 }}
            className={`relative max-h-[calc(100dvh_-_1.5rem)] w-full max-w-sm overscroll-contain overflow-y-auto rounded-2xl border p-5 shadow-2xl sm:max-h-[calc(100dvh_-_2rem)] sm:p-6 ${
              isDark ? 'border-white/15 bg-[#111c29]' : 'border-gray-200 bg-white'
            }`}
          >
            <h3 id={titleId} className={`mb-2 text-lg font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>{title}</h3>
            <p id={descriptionId} className={`mb-5 text-sm leading-relaxed ${isDark ? 'text-white/75' : 'text-gray-600'}`}>{message}</p>
            {children && <div className="mb-4">{children}</div>}
            <div className="flex flex-col gap-3 sm:flex-row">
              {showCancel && (
                <button
                  ref={cancelRef}
                  type="button"
                  onClick={onCancel}
                  className={`min-h-11 min-w-0 flex-1 rounded-xl px-3 py-2 text-sm font-medium transition-[background-color,color,transform] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] active:scale-95 ${
                    isDark ? 'bg-white/[0.08] text-white/85 hover:bg-white/[0.14]' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {cancelText}
                </button>
              )}
              <button
                ref={confirmRef}
                type="button"
                onClick={onConfirm}
                disabled={confirmDisabled}
                className={`${showCancel ? 'min-w-0 flex-1' : 'w-full'} min-h-11 rounded-xl px-3 py-2 text-sm font-medium transition-[background-color,color,transform] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] active:scale-95 disabled:opacity-40 ${
                  danger
                    ? isDark ? 'bg-red-500/20 text-red-300 hover:bg-red-500/30' : 'bg-red-600 text-white hover:bg-red-700'
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
