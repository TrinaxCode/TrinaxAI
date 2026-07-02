import { createContext, useContext, useState, useCallback, useRef, type ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MdClose } from 'react-icons/md';

interface Toast {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
}

interface ToastContextValue {
  toast: (message: string, type?: Toast['type']) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextIdRef = useRef(0);

  const toast = useCallback((message: string, type: Toast['type'] = 'info') => {
    const id = ++nextIdRef.current;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3500);
  }, []);

  const dismiss = (id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const typeStyles: Record<Toast['type'], string> = {
    success: 'border-green-500/30 bg-green-500/10 text-green-400',
    error: 'border-red-500/30 bg-red-500/10 text-red-400',
    info: 'border-[#006bbd]/30 bg-[#006bbd]/10 text-[#006bbd]',
    warning: 'border-amber-500/30 bg-amber-500/10 text-amber-400',
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {/* Desktop: top-center toasts */}
      <div className="hidden sm:flex fixed top-0 left-1/2 -translate-x-1/2 z-[100] flex-col items-center gap-2 pointer-events-none"
           style={{ paddingTop: 'calc(env(safe-area-inset-top, 0px) + 12px)' }}
           role="alert"
           aria-live="polite">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10, scale: 0.95 }}
              className={`pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-xl border text-xs font-medium shadow-lg ${typeStyles[t.type]}`}
            >
              <span>{t.message}</span>
              <button onClick={() => dismiss(t.id)} className="opacity-50 hover:opacity-100 transition-opacity">
                <MdClose size={14} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
      {/* Mobile: bottom toasts (avoids notch overlap) */}
      <div className="flex sm:hidden fixed bottom-0 left-1/2 -translate-x-1/2 z-[100] flex-col-reverse items-center gap-2 pointer-events-none"
           style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 16px)' }}
           role="alert"
           aria-live="polite">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: -20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.95 }}
              className={`pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-xl border text-xs font-medium shadow-lg ${typeStyles[t.type]}`}
            >
              <span>{t.message}</span>
              <button onClick={() => dismiss(t.id)} className="opacity-50 hover:opacity-100 transition-opacity">
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
