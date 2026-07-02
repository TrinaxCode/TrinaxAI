import { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { MdVisibility, MdVisibilityOff, MdRefresh, MdFolder } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { useToast } from './Toast';
import { startWatch, stopWatch, getWatchStatus, type WatchStatus } from '../lib/api';

const STORAGE_KEY = 'tc-watch-collections';

function loadWatched(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? arr.filter((x) => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

function saveWatched(cols: string[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cols));
  } catch { /* ignore */ }
}

interface Props {
  collections: Array<{ id: string; name: string }>;
}

export default function WatcherCard({ collections }: Props) {
  const { t } = useI18n();
  const { isDark } = useTheme();
  const toast = useToast();
  const [status, setStatus] = useState<WatchStatus>({ running: false, watching: [], events_seen: 0, started_at: null });
  const [watched, setWatched] = useState<string[]>(() => loadWatched());
  const [busy, setBusy] = useState(false);

  // Poll status while mounted
  useEffect(() => {
    const c = new AbortController();
    const tick = async () => {
      try {
        const s = await getWatchStatus(c.signal);
        setStatus(s);
      } catch { /* ignore */ }
    };
    tick();
    const id = window.setInterval(tick, 2000);
    return () => { c.abort(); window.clearInterval(id); };
  }, []);

  // Persist watched collections
  useEffect(() => { saveWatched(watched); }, [watched]);

  const toggleCollection = useCallback((id: string) => {
    setWatched((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);
  }, []);

  const applyWatch = useCallback(async () => {
    setBusy(true);
    try {
      const paths = watched.map((id) => `local_sources/collections/${id}`);
      const r = await startWatch({ paths });
      if (r.status === 'already_running') {
        toast.toast(t('watcherAlreadyRunning'), 'info');
      } else if (r.watching.length === 0) {
        toast.toast(t('watcherNoValidPaths'), 'warning');
      } else {
        toast.toast(t('watcherWatchingCount').replace('{count}', String(r.watching.length)), 'success');
      }
    } catch (err) {
      toast.toast(err instanceof Error ? err.message.slice(0, 180) : t('noConnection'), 'error');
    } finally {
      setBusy(false);
    }
  }, [watched, toast, t]);

  const stop = useCallback(async () => {
    setBusy(true);
    try {
      await stopWatch();
      toast.toast(t('watcherStopped'), 'info');
    } catch (err) {
      toast.toast(err instanceof Error ? err.message.slice(0, 180) : t('noConnection'), 'error');
    } finally {
      setBusy(false);
    }
  }, [toast, t]);

  const cardBg = isDark ? 'bg-white/[0.03] border-white/[0.06]' : 'bg-gray-50 border-gray-200';
  const muted = isDark ? 'text-white/45' : 'text-gray-500';
  const label = isDark ? 'text-white/80' : 'text-gray-800';

  return (
    <section className={`rounded-xl border p-4 space-y-3 ${cardBg}`}>
      <div className="flex items-center justify-between">
        <div>
          <div className={`text-sm font-medium ${label}`}>{t('watcherTitle')}</div>
          <div className={`text-[11px] ${muted} mt-0.5`}>
            {status.running
              ? t('watcherActive').replace('{count}', String(status.events_seen))
              : t('watcherInactive')}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {status.running ? (
            <button onClick={stop} disabled={busy} className="px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium hover:bg-red-500/20 disabled:opacity-50 transition-colors flex items-center gap-1.5">
              <MdVisibilityOff size={14} /> {t('stop')}
            </button>
          ) : (
            <button onClick={applyWatch} disabled={busy || watched.length === 0} className="px-3 py-1.5 rounded-lg bg-[#006bbd] text-white text-xs font-medium hover:bg-[#0059a0] disabled:opacity-30 transition-colors flex items-center gap-1.5">
              <MdVisibility size={14} /> {t('start')}
            </button>
          )}
        </div>
      </div>

      {/* Collection picker */}
      <div className="flex flex-wrap gap-1.5">
        {collections.map((col) => {
          const on = watched.includes(col.id);
          return (
            <button
              key={col.id}
              onClick={() => toggleCollection(col.id)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
                on
                  ? 'bg-[#006bbd]/15 border-[#006bbd]/40 text-[#006bbd]'
                  : isDark
                  ? 'bg-white/[0.03] border-white/[0.06] text-white/55 hover:text-white/80'
                  : 'bg-white border-gray-200 text-gray-600 hover:text-gray-800'
              }`}
            >
              <MdFolder size={12} className="opacity-70" />
              {col.name}
            </button>
          );
        })}
      </div>

      {status.watching.length > 0 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className={`text-[10px] font-mono ${muted} break-all`}>
          {t('watcherWatchingLabel')} {status.watching.join('  ·  ')}
        </motion.div>
      )}

      <p className={`text-[11px] ${muted} flex items-center gap-1.5`}>
        <MdRefresh size={12} className="opacity-60" />
        {t('watcherAutoReindexDesc')}
      </p>
    </section>
  );
}
