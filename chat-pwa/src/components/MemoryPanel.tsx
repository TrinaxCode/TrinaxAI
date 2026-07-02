import { useEffect, useRef, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { MdAdd, MdDelete, MdAutoFixHigh, MdRefresh } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { useToast } from './Toast';
import { listMemories, addMemory, deleteMemory, refreshMemorySummary, getMemorySummary, type MemoryEntry, type MemorySummary } from '../lib/api';

const PROJECT_MEMORY_KEY = 'tc-project-memory';

function loadProjectMemory(): string {
  try { return localStorage.getItem(PROJECT_MEMORY_KEY) || ''; } catch { return ''; }
}

export default function MemoryPanel() {
  const { t } = useI18n();
  const { isDark } = useTheme();
  const toast = useToast();
  const [mems, setMems] = useState<MemoryEntry[]>([]);
  const [summary, setSummary] = useState<MemorySummary>({ summary: '', count: 0, updated_at: 0 });
  const [newText, setNewText] = useState('');
  const [newTags, setNewTags] = useState('');
  const [projectNotes, setProjectNotes] = useState<string>(loadProjectMemory);
  const [refreshing, setRefreshing] = useState(false);
  const connectionToastShownRef = useRef(false);

  const showConnectionErrorOnce = useCallback((err: unknown) => {
    if (connectionToastShownRef.current) return;
    connectionToastShownRef.current = true;
    toast.toast(err instanceof Error ? err.message.slice(0, 180) : t('noConnection'), 'error');
  }, [toast, t]);

  const refresh = useCallback(async () => {
    try {
      const [list, sum] = await Promise.all([listMemories(), getMemorySummary()]);
      setMems(list);
      setSummary(sum);
      connectionToastShownRef.current = false;
    } catch (err) {
      showConnectionErrorOnce(err);
    }
  }, [showConnectionErrorOnce]);

  useEffect(() => { void refresh(); }, [refresh]);

  useEffect(() => {
    try { localStorage.setItem(PROJECT_MEMORY_KEY, projectNotes); } catch { /* ignore */ }
  }, [projectNotes]);

  // Notify other components (e.g. ChatInterface) to drop their cached summary.
  const invalidateCache = useCallback(() => {
    window.dispatchEvent(new CustomEvent('tc-memory-updated'));
  }, []);

  const add = useCallback(async () => {
    const text = newText.trim();
    if (!text) return;
    const tags = newTags.split(',').map((t) => t.trim()).filter(Boolean);
    try {
      await addMemory(text, tags);
      setNewText('');
      setNewTags('');
      toast.toast(t('memoryAdded'), 'success');
      invalidateCache();
      await refresh();
    } catch (err) {
      showConnectionErrorOnce(err);
    }
  }, [newText, newTags, toast, t, refresh, invalidateCache, showConnectionErrorOnce]);

  const del = useCallback(async (id: string) => {
    try {
      await deleteMemory(id);
      invalidateCache();
      await refresh();
    } catch (err) {
      showConnectionErrorOnce(err);
    }
  }, [refresh, invalidateCache, showConnectionErrorOnce]);

  const doRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refreshMemorySummary();
      await refresh();
      invalidateCache();
      toast.toast(t('memorySummaryRefreshed'), 'success');
    } catch (err) {
      showConnectionErrorOnce(err);
    } finally {
      setRefreshing(false);
    }
  }, [refresh, toast, t, invalidateCache, showConnectionErrorOnce]);

  const cardBg = isDark ? 'bg-white/[0.03] border-white/[0.06]' : 'bg-gray-50 border-gray-200';
  const muted = isDark ? 'text-white/45' : 'text-gray-500';
  const label = isDark ? 'text-white/80' : 'text-gray-800';
  const inputStyle = isDark
    ? 'bg-black/40 border-white/[0.06] text-white/80 placeholder-white/25'
    : 'bg-white border-gray-200 text-gray-800 placeholder-gray-400';

  return (
    <section className="space-y-4">
      {/* Project memory (free-form notes) */}
      <div className={`rounded-xl border p-4 space-y-2 ${cardBg}`}>
        <div className="flex items-center justify-between">
          <div>
            <div className={`text-sm font-medium ${label}`}>{t('projectMemoryTitle')}</div>
            <div className={`text-[11px] ${muted}`}>
              {t('projectMemoryDesc')}
            </div>
          </div>
        </div>
        <textarea
          value={projectNotes}
          onChange={(e) => setProjectNotes(e.target.value)}
          rows={4}
          placeholder={t('projectMemoryPlaceholder')}
          className={`w-full rounded-lg border px-3 py-2 text-xs outline-none focus:border-[#006bbd]/40 ${inputStyle}`}
        />
      </div>

      {/* Auto-summary */}
      <div className={`rounded-xl border p-4 space-y-2 ${cardBg}`}>
        <div className="flex items-center justify-between">
          <div>
            <div className={`text-sm font-medium ${label}`}>{t('memoryAutoSummaryTitle')}</div>
            <div className={`text-[11px] ${muted}`}>
              {t('memoryAutoSummaryDesc').replace('{count}', String(summary.count))}
            </div>
          </div>
          <button
            onClick={doRefresh}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#006bbd]/15 text-[#006bbd] text-xs font-medium hover:bg-[#006bbd]/25 disabled:opacity-50 transition-colors"
          >
            <MdAutoFixHigh size={14} /> {t('refresh')}
          </button>
        </div>
        <div className={`rounded-lg border p-3 text-xs ${isDark ? 'bg-black/30 border-white/[0.06] text-white/70' : 'bg-white border-gray-200 text-gray-700'}`}>
          {summary.summary
            ? summary.summary
            : <span className={muted}>{t('memoryNoSummary')}</span>}
        </div>
      </div>

      {/* Add new memory */}
      <div className={`rounded-xl border border-dashed p-4 space-y-2 ${cardBg}`}>
        <div className={`text-sm font-medium ${label}`}>{t('addMemoryTitle')}</div>
        <input
          value={newText}
          onChange={(e) => setNewText(e.target.value)}
          placeholder={t('memoryTextPlaceholder')}
          className={`w-full rounded-lg border px-3 py-2 text-xs outline-none focus:border-[#006bbd]/40 ${inputStyle}`}
        />
        <input
          value={newTags}
          onChange={(e) => setNewTags(e.target.value)}
          placeholder={t('memoryTagsPlaceholder')}
          className={`w-full rounded-lg border px-3 py-2 text-xs outline-none focus:border-[#006bbd]/40 ${inputStyle}`}
        />
        <button
          onClick={add}
          disabled={!newText.trim()}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#006bbd] text-white text-xs font-medium hover:bg-[#0059a0] disabled:opacity-30 transition-colors"
        >
          <MdAdd size={14} /> {t('add')}
        </button>
      </div>

      {/* Memory list */}
      <div className="space-y-2">
        {mems.length === 0 ? (
          <p className={`text-[11px] ${muted}`}>{t('memoryEmpty')}</p>
        ) : (
          mems.map((m) => (
            <motion.div
              key={m.id}
              initial={{ opacity: 0, y: 2 }}
              animate={{ opacity: 1, y: 0 }}
              className={`rounded-xl border p-3 flex items-start gap-2 ${cardBg}`}
            >
              <div className="flex-1 min-w-0">
                <p className={`text-xs ${isDark ? 'text-white/80' : 'text-gray-800'} break-words`}>{m.text}</p>
                <div className={`mt-1.5 flex flex-wrap items-center gap-2 text-[10px] ${muted}`}>
                  <span>{new Date(m.created_at * 1000).toLocaleString()}</span>
                  {m.tags?.length ? (
                    <span className="flex flex-wrap gap-1">
                      {m.tags.map((tag) => (
                        <span key={tag} className="px-1.5 py-0.5 rounded bg-[#006bbd]/10 text-[#006bbd]">{tag}</span>
                      ))}
                    </span>
                  ) : null}
                </div>
              </div>
              <button
                onClick={() => del(m.id)}
                className={`shrink-0 p-1.5 rounded-lg ${isDark ? 'text-white/25 hover:text-red-400 hover:bg-white/[0.05]' : 'text-gray-300 hover:text-red-500 hover:bg-gray-100'}`}
                aria-label={t('delete')}
              >
                <MdDelete size={14} />
              </button>
            </motion.div>
          ))
        )}
      </div>
    </section>
  );
}
