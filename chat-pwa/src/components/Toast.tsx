import { createContext, useContext, useState, useCallback, useRef, useEffect, type ReactNode } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { MdCheckCircleOutline, MdClose, MdErrorOutline, MdInfoOutline, MdWarningAmber } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import type { TranslationKey } from '../i18n/translations';
import { audioManager, type SoundEvent } from '../services/audioManager';
import ErrorRepairModal from './ErrorRepairModal';

export interface ToastAction {
  label: string;
  pendingLabel?: string;
  onClick: () => Promise<void> | void;
}

export interface ToastOptions {
  durationMs?: number;
  action?: ToastAction;
}

type ToastType = 'success' | 'error' | 'info' | 'warning';

interface ToastItem {
  id: number;
  revision: number;
  message: string;
  type: ToastType;
  action?: ToastAction;
  actionPending?: boolean;
  exiting?: boolean;
  paused?: boolean;
  durationMs: number;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType, options?: ToastOptions) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const TOAST_DURATION_MS: Record<ToastType, number> = {
  success: 3500,
  info: 3500,
  warning: 4500,
  // Error messages often include an actionable backend detail, so leave them
  // visible long enough to read on a small screen.
  error: 6000,
};

const TOAST_SOUNDS: Record<ToastType, SoundEvent> = {
  success: 'notification-success',
  error: 'notification-error',
  warning: 'notification-warning',
  info: 'notification-info',
};

const TOAST_LABEL_KEY: Record<ToastType, TranslationKey> = {
  success: 'toastSuccess',
  error: 'toastError',
  warning: 'toastWarning',
  info: 'toastInfo',
};

/** Errors that carry a recovery action never expire on their own: the reader
 *  decides when the problem has been acknowledged. */
const STICKY = 0;

/** Older notices step aside once the stack reaches this size, so a burst of
 *  indexing or polling messages can never bury the screen. */
const MAX_VISIBLE = 4;

/* The notice fades out first and is unmounted by this timer, so the DOM never
   waits on an animation frame to finish. */
const EXIT_MS = 200;

interface NoticeStyle {
  frame: string;
  rail: string;
  chip: string;
  label: string;
}

/* Severity lives in the accent (icon chip, label and countdown), never in
   the surface: every notice keeps the same TrinaxAI glass frame in both themes. */
const NOTICE_STYLES: Record<ToastType, NoticeStyle> = {
  success: {
    frame: 'border-[#008f83]/25 shadow-[0_16px_34px_rgba(13,58,54,0.16)] dark:border-[#2ac9b6]/30 dark:shadow-[0_18px_40px_rgba(0,0,0,0.5)]',
    rail: 'bg-[#008f83] dark:bg-[#2ac9b6]',
    chip: 'bg-[#008f83]/10 text-[#00756b] dark:bg-[#2ac9b6]/15 dark:text-[#2ac9b6]',
    label: 'text-[#00756b] dark:text-[#2ac9b6]',
  },
  error: {
    frame: 'border-[#d92d20]/25 shadow-[0_16px_34px_rgba(80,15,10,0.18)] dark:border-[#f97066]/35 dark:shadow-[0_18px_40px_rgba(0,0,0,0.5)]',
    rail: 'bg-[#d92d20] dark:bg-[#f97066]',
    chip: 'bg-[#d92d20]/10 text-[#c0271c] dark:bg-[#f97066]/15 dark:text-[#f97066]',
    label: 'text-[#c0271c] dark:text-[#f97066]',
  },
  warning: {
    frame: 'border-[#b45309]/25 shadow-[0_16px_34px_rgba(76,44,6,0.16)] dark:border-[#fbbf24]/30 dark:shadow-[0_18px_40px_rgba(0,0,0,0.5)]',
    rail: 'bg-[#b45309] dark:bg-[#fbbf24]',
    chip: 'bg-[#b45309]/10 text-[#a3540a] dark:bg-[#fbbf24]/15 dark:text-[#fbbf24]',
    label: 'text-[#a3540a] dark:text-[#fbbf24]',
  },
  info: {
    frame: 'border-[#006bbd]/20 shadow-[0_16px_34px_rgba(15,42,70,0.14)] dark:border-[#168de2]/30 dark:shadow-[0_18px_40px_rgba(0,0,0,0.5)]',
    rail: 'bg-[#006bbd] dark:bg-[#168de2]',
    chip: 'bg-[#006bbd]/10 text-[#006bbd] dark:bg-[#168de2]/15 dark:text-[#4ea3e0]',
    label: 'text-[#006bbd] dark:text-[#4ea3e0]',
  },
};

const NOTICE_ICONS: Record<ToastType, ReactNode> = {
  success: <MdCheckCircleOutline size={17} />,
  error: <MdErrorOutline size={18} />,
  info: <MdInfoOutline size={17} />,
  warning: <MdWarningAmber size={18} />,
};

const CARD_CLASS = 'pointer-events-auto relative w-full overflow-hidden rounded-2xl border bg-white/95 px-4 py-3.5 text-left backdrop-blur-2xl dark:bg-[#0a1018]/90';
const PRIMARY_BUTTON_CLASS = 'inline-flex min-h-10 items-center justify-center rounded-xl bg-[#006bbd] px-3.5 py-2 text-xs font-semibold text-white transition-[background-color,box-shadow,transform] hover:bg-[#0059a0] active:scale-[0.98] disabled:cursor-wait disabled:opacity-60';
const SECONDARY_BUTTON_CLASS = 'inline-flex min-h-10 items-center justify-center rounded-xl border border-black/10 px-3.5 py-2 text-xs font-semibold text-[#0f1c28]/75 transition-[background-color,border-color,transform] hover:border-black/20 hover:bg-black/[0.04] active:scale-[0.98] dark:border-white/15 dark:text-white/80 dark:hover:bg-white/[0.07]';

export function ToastProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [repairId, setRepairId] = useState<number | null>(null);
  const nextIdRef = useRef(0);
  const toastsRef = useRef<ToastItem[]>([]);
  const timersRef = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());
  const deadlinesRef = useRef<Map<number, number>>(new Map());
  const remainingRef = useRef<Map<number, number>>(new Map());
  const actionsRef = useRef<Map<number, ToastAction>>(new Map());
  const pendingActionsRef = useRef<Set<number>>(new Set());
  const prefersReducedMotion = useReducedMotion();

  // Cancel any pending auto-dismiss timers when the provider unmounts so we
  // never call setState on an unmounted component.
  useEffect(() => {
    const timers = timersRef.current;
    const deadlines = deadlinesRef.current;
    const remaining = remainingRef.current;
    const actions = actionsRef.current;
    const pending = pendingActionsRef.current;
    return () => {
      timers.forEach((handle) => clearTimeout(handle));
      timers.clear();
      deadlines.clear();
      remaining.clear();
      actions.clear();
      pending.clear();
    };
  }, []);

  // The mirror keeps the newest list readable from event handlers, where React
  // state has not committed yet.
  const commit = useCallback((update: (prev: ToastItem[]) => ToastItem[]) => {
    setToasts((prev) => {
      const next = update(prev);
      toastsRef.current = next;
      return next;
    });
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
    deadlinesRef.current.delete(id);
    remainingRef.current.delete(id);
    commit((prev) => prev.map((item) => (item.id === id ? { ...item, exiting: true, paused: false } : item)));
    const handle = setTimeout(() => {
      timersRef.current.delete(id);
      actionsRef.current.delete(id);
      pendingActionsRef.current.delete(id);
      commit((prev) => prev.filter((item) => item.id !== id));
    }, EXIT_MS);
    timersRef.current.set(id, handle);
  }, [clearTimer, commit]);

  const startTimer = useCallback((id: number, ms: number) => {
    clearTimer(id);
    deadlinesRef.current.delete(id);
    remainingRef.current.delete(id);
    if (ms <= 0) return;
    deadlinesRef.current.set(id, Date.now() + ms);
    timersRef.current.set(id, setTimeout(() => requestDismiss(id), ms));
  }, [clearTimer, requestDismiss]);

  // Holding a notice — pointer over it or keyboard focus inside it — freezes
  // its countdown and the strip that shows it.
  const pauseTimer = useCallback((id: number) => {
    const deadline = deadlinesRef.current.get(id);
    const handle = timersRef.current.get(id);
    if (deadline === undefined || handle === undefined) return;
    clearTimeout(handle);
    timersRef.current.delete(id);
    deadlinesRef.current.delete(id);
    remainingRef.current.set(id, Math.max(1, deadline - Date.now()));
    commit((prev) => prev.map((item) => (item.id === id ? { ...item, paused: true } : item)));
  }, [commit]);

  const resumeTimer = useCallback((id: number) => {
    const remaining = remainingRef.current.get(id);
    if (remaining === undefined) return;
    commit((prev) => prev.map((item) => (item.id === id ? { ...item, paused: false } : item)));
    startTimer(id, remaining);
  }, [commit, startTimer]);

  const runAction = useCallback(async (id: number): Promise<boolean> => {
    const action = actionsRef.current.get(id);
    if (!action || pendingActionsRef.current.has(id)) return false;
    pendingActionsRef.current.add(id);
    pauseTimer(id);
    commit((prev) => prev.map((item) => (item.id === id ? { ...item, actionPending: true, paused: true } : item)));
    try {
      await action.onClick();
      requestDismiss(id);
      return true;
    } catch {
      pendingActionsRef.current.delete(id);
      commit((prev) => prev.map((item) => (item.id === id ? { ...item, actionPending: false } : item)));
      resumeTimer(id);
      return false;
    }
  }, [commit, pauseTimer, requestDismiss, resumeTimer]);

  const repairNotice = repairId === null ? undefined : toasts.find((notice) => notice.id === repairId);
  const openRepair = useCallback((id: number) => {
    pauseTimer(id);
    setRepairId(id);
  }, [pauseTimer]);
  const confirmRepair = useCallback(async () => {
    if (!repairNotice) return;
    if (!repairNotice.action) {
      setRepairId(null);
      requestDismiss(repairNotice.id);
      return;
    }
    if (await runAction(repairNotice.id)) setRepairId(null);
  }, [repairNotice, requestDismiss, runAction]);
  const cancelRepair = useCallback(() => {
    // Closing the guidance is not the same as dismissing the problem: the
    // notice stays and its countdown resumes where it stopped.
    if (repairNotice) resumeTimer(repairNotice.id);
    setRepairId(null);
  }, [repairNotice, resumeTimer]);

  const toast = useCallback((message: string, type: ToastType = 'info', options?: ToastOptions) => {
    const text = message.trim() || t(TOAST_LABEL_KEY[type]);
    const durationMs = options?.durationMs
      ?? (type === 'error' && options?.action ? STICKY : TOAST_DURATION_MS[type]);
    const duplicate = toastsRef.current.find(
      (item) => !item.exiting && item.type === type && item.message === text,
    );

    // Repeating a notice refreshes the one on screen instead of stacking a
    // second copy of the same message.
    if (duplicate) {
      if (options?.action) actionsRef.current.set(duplicate.id, options.action);
      commit((prev) => prev.map((item) => (item.id === duplicate.id
        ? {
            ...item,
            revision: item.revision + 1,
            action: options?.action ?? item.action,
            actionPending: false,
            paused: false,
            durationMs,
          }
        : item)));
      startTimer(duplicate.id, durationMs);
      return;
    }

    const id = ++nextIdRef.current;
    audioManager.play(TOAST_SOUNDS[type]);
    if (options?.action) actionsRef.current.set(id, options.action);
    commit((prev) => {
      const next = [...prev, { id, revision: 0, message: text, type, action: options?.action, durationMs }];
      while (next.length > MAX_VISIBLE) {
        const oldest = next.findIndex((item) => !item.exiting && !pendingActionsRef.current.has(item.id));
        if (oldest === -1) break;
        const [removed] = next.splice(oldest, 1);
        actionsRef.current.delete(removed.id);
        clearTimer(removed.id);
        deadlinesRef.current.delete(removed.id);
        remainingRef.current.delete(removed.id);
      }
      return next;
    });
    startTimer(id, durationMs);
  }, [clearTimer, commit, startTimer, t]);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {/* A single top stack keeps errors close to the app header on every
          viewport and clear of the mobile composer/keyboard. */}
      <div
        className="pointer-events-none fixed inset-x-0 top-0 z-[100] mx-auto flex w-full max-w-[28rem] flex-col items-center gap-2.5 px-3"
        style={{ paddingTop: 'calc(env(safe-area-inset-top, 0px) + 12px)' }}
        role="region"
        aria-label={t('notifications')}
      >
        {toasts.map((notice) => {
          const style = NOTICE_STYLES[notice.type];
          const counting = notice.durationMs !== STICKY;
          return (
            <motion.div
              key={notice.id}
              initial={prefersReducedMotion ? { opacity: 0 } : { opacity: 0, y: -16, scale: 0.97 }}
              animate={notice.exiting
                ? prefersReducedMotion ? { opacity: 0 } : { opacity: 0, y: -10, scale: 0.98 }
                : { opacity: 1, y: 0, scale: 1 }}
              transition={notice.exiting
                ? { duration: prefersReducedMotion ? 0 : 0.17, ease: [0.4, 0, 1, 1] }
                : { duration: prefersReducedMotion ? 0 : 0.26, ease: [0.16, 1, 0.3, 1] }}
              role={notice.type === 'error' ? 'alert' : 'status'}
              aria-live={notice.type === 'error' ? 'assertive' : 'polite'}
              aria-atomic="true"
              onMouseEnter={() => pauseTimer(notice.id)}
              onMouseLeave={() => resumeTimer(notice.id)}
              onFocusCapture={() => pauseTimer(notice.id)}
              onBlurCapture={(event) => {
                if (!event.currentTarget.contains(event.relatedTarget as Node | null)) resumeTimer(notice.id);
              }}
              className={`${CARD_CLASS} ${style.frame}`}
            >
              <div className="flex items-start gap-3">
                <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg ${style.chip}`} aria-hidden="true">
                  {NOTICE_ICONS[notice.type]}
                </span>
                <div className="min-w-0 flex-1">
                  <p className={`text-[10px] font-semibold uppercase tracking-[0.16em] ${style.label}`}>
                    {t(TOAST_LABEL_KEY[notice.type])}
                  </p>
                  <p className="mt-1 break-words text-pretty text-[13px] font-medium leading-5 text-[#0f1c28] dark:text-white/90">
                    {notice.message}
                  </p>
                  {(notice.action || notice.type === 'error') && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {notice.action && (
                        <button
                          type="button"
                          onClick={() => void runAction(notice.id)}
                          disabled={notice.actionPending}
                          className={PRIMARY_BUTTON_CLASS}
                        >
                          {notice.actionPending ? (notice.action.pendingLabel || t('startingUp')) : notice.action.label}
                        </button>
                      )}
                      {notice.type === 'error' && (
                        <button
                          type="button"
                          onClick={() => openRepair(notice.id)}
                          className={SECONDARY_BUTTON_CLASS}
                        >
                          {t('fixError')}
                        </button>
                      )}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => requestDismiss(notice.id)}
                  className="-mr-1 -mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-lg text-[#0f1c28]/40 transition-[background-color,color,transform] hover:bg-black/[0.05] hover:text-[#0f1c28] active:scale-95 dark:text-white/40 dark:hover:bg-white/[0.08] dark:hover:text-white"
                  aria-label={t('close')}
                >
                  <MdClose size={15} />
                </button>
              </div>
              {counting && !prefersReducedMotion && (
                <span
                  key={notice.revision}
                  aria-hidden="true"
                  className={`toast-countdown absolute inset-x-0 bottom-0 h-[2px] opacity-50 ${style.rail}`}
                  style={{
                    animationDuration: `${notice.durationMs}ms`,
                    animationPlayState: notice.paused ? 'paused' : 'running',
                  }}
                />
              )}
            </motion.div>
          );
        })}
      </div>
      <ErrorRepairModal
        open={Boolean(repairNotice)}
        dark={document.documentElement.classList.contains('dark')}
        title={t('errorRepairTitle')}
        message={t('errorRepairMessage')}
        details={repairNotice ? `${repairNotice.message}\n\n${t('errorRepairHint')}` : ''}
        confirmLabel={repairNotice?.action?.label || t('close')}
        cancelLabel={t('cancel')}
        confirmDisabled={repairNotice?.actionPending}
        showCancel={Boolean(repairNotice?.action)}
        onConfirm={() => void confirmRepair()}
        onCancel={cancelRepair}
      />
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}
