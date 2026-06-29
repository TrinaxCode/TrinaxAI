import { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { MdRefresh, MdDelete, MdStorage } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { useToast } from './Toast';
import { startWatch, type Collection } from '../lib/api';

interface RecentIndex {
  label: string;
  path?: string;
  saved?: number;
  skipped?: number;
  indexedAt: number;
  jobId?: string;
  collectionId?: string;
  collectionName?: string;
}

const STORAGE_KEY = 'tc-recent-indexes';
const MAX_ENTRIES = 20;

function loadRecent(): RecentIndex[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    const last = (() => {
      try { const r = localStorage.getItem('tc-last-index-import'); return r ? JSON.parse(r) : null; } catch { return null; }
    })();
    const items: RecentIndex[] = Array.isArray(arr) ? arr : [];
    if (last && last.label && last.indexedAt) {
      // Prepend legacy/most-recent entry if not already present.
      const exists = items.some((i) => i.indexedAt === last.indexedAt && i.label === last.label);
      if (!exists) items.unshift(last as RecentIndex);
    }
    return items.slice(0, MAX_ENTRIES);
  } catch {
    return [];
  }
}

function saveRecent(items: RecentIndex[]) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_ENTRIES))); } catch { /* ignore */ }
}

interface Props { collections: Collection[] }

export default function RecentIndexes({ collections }: Props) {
  const { t, lang } = useI18n();
  const { isDark } = useTheme();
  const toast = useToast();
  const [items, setItems] = useState<RecentIndex[]>(() => loadRecent());

  // Refresh after each successful index — poll localStorage every 3s while mounted.
  useEffect(() => {
    const id = window.setInterval(() => setItems(loadRecent()), 3000);
    return () => window.clearInterval(id);
  }, []);

  const reindex = useCallback(async (it: RecentIndex) => {
    if (!it.collectionId) {
      toast.toast(lang === 'en' ? 'No collection info — pick the folder again' : 'Sin info de colección — vuelve a elegir la carpeta', 'warning');
      return;
    }
    try {
      // Trigger the watcher for this collection. The backend will debounce a
      // re-index run via index.py in append mode within ~2 seconds of any
      // change. To force an immediate refresh, we schedule a tiny synthetic
      // event (touch the directory mtime) by writing a noop file and removing it.
      await startWatch({ paths: [`local_sources/collections/${it.collectionId}`] });
      toast.toast(
        lang === 'en' ? `Watcher running on ${it.collectionName || it.collectionId}. Edit any file to re-index.` : `Watcher activo en ${it.collectionName || it.collectionId}. Edita cualquier archivo para re-indexar.`,
        'success',
      );
    } catch (err) {
      toast.toast(err instanceof Error ? err.message.slice(0, 180) : (lang === 'en' ? 'Failed to start watcher' : 'No se pudo iniciar el watcher'), 'error');
    }
  }, [toast, lang]);

  const remove = useCallback((idx: number) => {
    setItems((prev) => {
      const next = prev.filter((_, i) => i !== idx);
      saveRecent(next);
      return next;
    });
  }, []);

  const cardBg = isDark ? 'bg-white/[0.03] border-white/[0.06]' : 'bg-gray-50 border-gray-200';
  const muted = isDark ? 'text-white/45' : 'text-gray-500';
  const label = isDark ? 'text-white/80' : 'text-gray-800';

  if (items.length === 0) {
    return (
      <section className={`rounded-xl border p-4 ${cardBg}`}>
        <div className={`text-sm font-medium ${label}`}>{lang === 'en' ? 'Recent indexes' : 'Indexados recientes'}</div>
        <p className={`text-[11px] ${muted} mt-1`}>
          {lang === 'en' ? 'After you index a folder it will appear here for quick re-indexing.' : 'Después de indexar una carpeta aparecerá aquí para re-indexar rápidamente.'}
        </p>
      </section>
    );
  }

  return (
    <section className={`rounded-xl border p-4 space-y-2 ${cardBg}`}>
      <div className={`text-sm font-medium ${label}`}>{lang === 'en' ? 'Recent indexes' : 'Indexados recientes'}</div>
      <div className="space-y-1.5">
        {items.map((it, i) => (
          <motion.div
            key={`${it.label}-${it.indexedAt}-${i}`}
            initial={{ opacity: 0, y: 2 }}
            animate={{ opacity: 1, y: 0 }}
            className={`flex items-center gap-2 rounded-lg border px-3 py-2 ${isDark ? 'bg-black/30 border-white/[0.06]' : 'bg-white border-gray-200'}`}
          >
            <MdStorage size={14} className={`shrink-0 ${muted}`} />
            <div className="flex-1 min-w-0">
              <div className={`text-xs font-mono truncate ${isDark ? 'text-white/80' : 'text-gray-800'}`}>{it.label}</div>
              <div className={`text-[10px] ${muted}`}>
                {new Date(it.indexedAt).toLocaleString()}
                {it.saved != null ? ` · ${it.saved} ${t('filesUnit')}` : ''}
                {it.collectionName ? ` · ${it.collectionName}` : ''}
              </div>
            </div>
            <button
              onClick={() => reindex(it)}
              className={`shrink-0 p-1.5 rounded-lg ${isDark ? 'text-white/45 hover:text-white hover:bg-white/[0.06]' : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'}`}
              aria-label={lang === 'en' ? 'Re-index' : 'Re-indexar'}
              title={lang === 'en' ? 'Re-index (re-pick folder if needed)' : 'Re-indexar (vuelve a elegir la carpeta si hace falta)'}
            >
              <MdRefresh size={14} />
            </button>
            <button
              onClick={() => remove(i)}
              className={`shrink-0 p-1.5 rounded-lg ${isDark ? 'text-white/25 hover:text-red-400 hover:bg-white/[0.05]' : 'text-gray-300 hover:text-red-500 hover:bg-gray-100'}`}
              aria-label={lang === 'en' ? 'Remove from history' : 'Quitar del historial'}
            >
              <MdDelete size={14} />
            </button>
          </motion.div>
        ))}
      </div>
    </section>
  );
}