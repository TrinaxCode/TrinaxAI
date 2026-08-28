import { createContext, useContext, useState, useCallback, useRef, useEffect, type ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MdCheckCircleOutline, MdClose, MdErrorOutline, MdInfoOutline, MdWarningAmber } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { audioManager, type SoundEvent } from '../services/audioManager';

export interface ToastAction {
  label: string;
  pendingLabel?: string;
  onClick: () => Promise<void> | void;
}

export interface ToastOptions {
  durationMs?: number;
  action?: ToastAction;
}

interface Toast {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
  action?: ToastAction;
  actionPending?: boolean;
  exiting?: boolean;
}

interface ToastContextValue {
  toast: (message: string, type?: Toast['type'], options?: ToastOptions) => void;
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

const TOAST_SOUNDS: Record<Toast['type'], SoundEvent> = {
  success: 'notification-success',
  error: 'notification-error',
  warning: 'notification-warning',
  info: 'notification-info',
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextIdRef = useRef(0);
  const timersRef = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());
  const actionsRef = useRef<Map<number, ToastAction>>(new Map());
  const pendingActionsRef = useRef<Set<number>>(new Set());

  // Cancel any pending auto-dismiss timers when the provider unmounts so we
  // never call setState on an unmounted component.
  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      timers.forEach((handle) => clearTimeout(handle));
      timers.clear();
      actionsRef.current.clear();
      pendingActionsRef.current.clear();
    };
  }, []);

  const clearTimer = useCallback((id: number) => {
    const handle = timersRef.current.get(id);
    if (handle !== undefined) {
      clearTimeout(handle);
      timersRef.current.delete(id);
    }
  }, []);

  const requestDismiss = useCallback((id: number) => {
    // Mark as exiting so the exit animation plays, then remove after it ends
    clearTimer(id);
    setToasts((prev) => prev.map((t) => t.id === id ? { ...t, exiting: true } : t));
    const handle = setTimeout(() => {
      timersRef.current.delete(id);
      actionsRef.current.delete(id);
      pendingActionsRef.current.delete(id);
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 250);
    timersRef.current.set(id, handle);
  }, [clearTimer]);

  const runAction = useCallback(async (id: number) => {
    const action = actionsRef.current.get(id);
    if (!action || pendingActionsRef.current.has(id)) return;
    pendingActionsRef.current.add(id);
    setToasts((prev) => prev.map((item) => item.id === id ? { ...item, actionPending: true } : item));
    try {
      await action.onClick();
      requestDismiss(id);
    } catch {
      pendingActionsRef.current.delete(id);
      setToasts((prev) => prev.map((item) => item.id === id ? { ...item, actionPending: false } : item));
    }
  }, [requestDismiss]);

  const toast = useCallback((message: string, type: Toast['type'] = 'info', options?: ToastOptions) => {
    const id = ++nextIdRef.current;
    audioManager.play(TOAST_SOUNDS[type]);
    if (options?.action) actionsRef.current.set(id, options.action);
    setToasts((prev) => [...prev, { id, message, type, action: options?.action }]);
    const handle = setTimeout(() => {
      requestDismiss(id);
    }, options?.durationMs ?? TOAST_DURATION_MS[type]);
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
        role="region"
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
              <div className="min-w-0 text-center">
                <span className="block break-words">{notice.message}</span>
                {notice.action && (
                  <button
                    type="button"
                    onClick={() => void runAction(notice.id)}
                    disabled={notice.actionPending}
                    className="mt-2 inline-flex min-h-8 items-center justify-center rounded-lg border border-current/30 px-2.5 py-1 text-[11px] font-semibold transition-colors hover:bg-white/15 disabled:cursor-wait disabled:opacity-60"
                  >
                    {notice.actionPending ? (notice.action.pendingLabel || t('startingUp')) : notice.action.label}
                  </button>
                )}
              </div>
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
