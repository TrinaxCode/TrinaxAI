import { createContext, useContext, useState, useCallback, useRef, useEffect, type ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MdCheckCircleOutline, MdClose, MdErrorOutline, MdInfoOutline, MdWarningAmber } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';

interface Toast {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
  exiting?: boolean;
}

interface ToastContextValue {
  toast: (message: string, type?: Toast['type']) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const TOAST_DURATION_MS: Record<Toast['type'], number> = {
  success: 3500,
  info: 3500,
  warning: 4500,
  // Error messages often include an actionable backend detail, so leave them
  // visible long enough to read on a small screen.
  error: 6000,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextIdRef = useRef(0);
  const timersRef = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  // Cancel any pending auto-dismiss timers when the provider unmounts so we
  // never call setState on an unmounted component.
  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      timers.forEach((handle) => clearTimeout(handle));
      timers.clear();
    };
  }, []);

  const clearTimer = useCallback((id: number) => {
    const handle = timersRef.current.get(id);
    if (handle !== undefined) {
      clearTimeout(handle);
      timersRef.current.delete(id);
    }
  }, []);

  const dismiss = useCallback((id: number) => {
    clearTimer(id);
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, [clearTimer]);

  const requestDismiss = useCallback((id: number) => {
    // Mark as exiting so the exit animation plays, then remove after it ends
    clearTimer(id);
    setToasts((prev) => prev.map((t) => t.id === id ? { ...t, exiting: true } : t));
    const handle = setTimeout(() => {
      timersRef.current.delete(id);
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 250);
    timersRef.current.set(id, handle);
  }, [clearTimer]);

  const toast = useCallback((message: string, type: Toast['type'] = 'info') => {
    const id = ++nextIdRef.current;
    setToasts((prev) => [...prev, { id, message, type }]);
    const handle = setTimeout(() => {
      requestDismiss(id);
    }, TOAST_DURATION_MS[type]);
    timersRef.current.set(id, handle);
  }, [requestDismiss]);

  const typeStyles: Record<Toast['type'], string> = {
    success: 'border-emerald-400/35 bg-emerald-950/95 text-emerald-100 shadow-emerald-950/30',
    error: 'border-red-400/45 bg-red-950/95 text-red-50 shadow-red-950/40',
    info: 'border-[#2588d4]/45 bg-[#062b4b]/95 text-blue-50 shadow-[#021629]/40',
    warning: 'border-amber-400/45 bg-amber-950/95 text-amber-50 shadow-amber-950/40',
  };
  const typeIcon: Record<Toast['type'], ReactNode> = {
    success: <MdCheckCircleOutline size={18} />,
    error: <MdErrorOutline size={19} />,
    info: <MdInfoOutline size={18} />,
    warning: <MdWarningAmber size={19} />,
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {/* A single top stack keeps errors close to the app header on every
          viewport and clear of the mobile composer/keyboard. */}
      <div
        className="fixed top-0 left-1/2 z-[100] flex w-[calc(100%_-_2rem)] max-w-[260px] -translate-x-1/2 flex-col items-center gap-1 pointer-events-none"
        style={{ paddingTop: 'calc(env(safe-area-inset-top, 0px) + 12px)' }}
        aria-label={t('notifications')}
      >
        <AnimatePresence>
          {toasts.map((notice) => (
            <motion.div
              key={notice.id}
              initial={{ opacity: 0, y: -14, scale: 0.97 }}
              animate={notice.exiting ? { opacity: 0, y: -10, scale: 0.97 } : { opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              role={notice.type === 'error' ? 'alert' : 'status'}
              aria-live={notice.type === 'error' ? 'assertive' : 'polite'}
              className={`pointer-events-auto grid w-full grid-cols-[1.25rem_minmax(0,1fr)_1.25rem] items-center gap-1 rounded-xl border px-2.5 py-2 text-[11px] font-medium leading-4 shadow-xl backdrop-blur-xl ${typeStyles[notice.type]}`}
            >
              <span className="grid h-5 w-5 place-items-center" aria-hidden="true">{typeIcon[notice.type]}</span>
              <span className="min-w-0 break-words text-center">{notice.message}</span>
              <button
                type="button"
                onClick={() => requestDismiss(notice.id)}
                className="grid h-5 w-5 place-items-center rounded-full text-current/70 transition-colors hover:bg-white/15 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
                aria-label={t('close')}
              >
                <MdClose size={14} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}
