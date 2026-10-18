import { useEffect, useRef, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { MdAdd, MdAutoFixHigh, MdClose, MdDelete, MdEdit, MdSave } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { useToast } from './Toast';
import { listMemories, addMemory, deleteMemory, refreshMemorySummary, getMemorySummary, updateMemory, userFacingError, type MemoryEntry, type MemorySummary } from '../lib/api';
import ConfirmModal from './ConfirmModal';

const PROJECT_MEMORY_KEY = 'tc-project-memory';

function loadProjectMemory(): string {
  try { return localStorage.getItem(PROJECT_MEMORY_KEY) || ''; } catch { return ''; }
}

export default function MemoryPanel({ canManageSystem = false }: { canManageSystem?: boolean }) {
  const { t, lang } = useI18n();
  const { isDark } = useTheme();
  const { toast: showToast } = useToast();
  const [mems, setMems] = useState<MemoryEntry[]>([]);
  const [summary, setSummary] = useState<MemorySummary>({ summary: '', count: 0, updated_at: 0 });
  const [loadError, setLoadError] = useState<string | null>(null);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [newText, setNewText] = useState('');
  const [newTags, setNewTags] = useState('');
  const [newKind, setNewKind] = useState<MemoryEntry['kind']>('note');
  const [newExpiry, setNewExpiry] = useState('');
  const [projectNotes, setProjectNotes] = useState<string>(loadProjectMemory);
  const [refreshing, setRefreshing] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const [editKind, setEditKind] = useState<MemoryEntry['kind']>('note');
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const connectionToastShownRef = useRef(false);
  const refreshRunRef = useRef(0);

  const showConnectionErrorOnce = useCallback((err: unknown) => {
    const message = userFacingError(err, 'external_service_unavailable');
    if (!connectionToastShownRef.current) {
      connectionToastShownRef.current = true;
      showToast(message, 'error');
    }
    return message;
  }, [showToast]);

  const refresh = useCallback(async () => {
    const runId = ++refreshRunRef.current;
    try {
      const [list, sum] = await Promise.all([listMemories(), getMemorySummary()]);
      if (runId !== refreshRunRef.current) return;
      setMems(list);
      setSummary(sum);
      setLoadError(null);
      connectionToastShownRef.current = false;
    } catch (err) {
      if (runId !== refreshRunRef.current) return;
      setLoadError(showConnectionErrorOnce(err));
    } finally {
      if (runId === refreshRunRef.current) setHasLoaded(true);
    }
  }, [showConnectionErrorOnce]);

  useEffect(() => {
    void refresh();
    return () => { refreshRunRef.current += 1; };
  }, [refresh]);

  useEffect(() => {
    try {
      localStorage.setItem(PROJECT_MEMORY_KEY, projectNotes);
    } catch {
      showConnectionErrorOnce(new Error(t('memoryProjectSaveFailed')));
    }
  }, [projectNotes, showConnectionErrorOnce, t]);

  // Notify other components (e.g. ChatInterface) to drop their cached summary.
  const invalidateCache = useCallback(() => {
    window.dispatchEvent(new CustomEvent('tc-memory-updated'));
  }, []);

  const add = useCallback(async () => {
    const text = newText.trim();
    if (!text) return;
    const tags = newTags.split(',').map((t) => t.trim()).filter(Boolean);
    try {
      const expiresAt = newExpiry
        ? new Date(`${newExpiry}T23:59:59`).getTime() / 1000
        : undefined;
      await addMemory(text, tags, { kind: newKind, expiresAt });
      setNewText('');
      setNewTags('');
      setNewKind('note');
      setNewExpiry('');
      showToast(t('memoryAdded'), 'success');
      invalidateCache();
      await refresh();
    } catch (err) {
      showConnectionErrorOnce(err);
    }
  }, [newText, newTags, newKind, newExpiry, showToast, t, refresh, invalidateCache, showConnectionErrorOnce]);

  const del = useCallback(async (id: string) => {
    try {
      await deleteMemory(id);
      invalidateCache();
      await refresh();
    } catch (err) {
      showConnectionErrorOnce(err);
    }
  }, [refresh, invalidateCache, showConnectionErrorOnce]);

  const beginEdit = useCallback((memory: MemoryEntry) => {
    setEditingId(memory.id);
    setEditText(memory.text);
    setEditKind(memory.kind ?? 'note');
  }, []);

  const saveEdit = useCallback(async () => {
    if (!editingId || !editText.trim()) return;
    try {
      await updateMemory(editingId, { text: editText.trim(), kind: editKind });
      setEditingId(null);
      invalidateCache();
      await refresh();
      showToast(t('memoryUpdated'), 'success');
    } catch (err) {
      showConnectionErrorOnce(err);
    }
  }, [editKind, editText, editingId, invalidateCache, refresh, showConnectionErrorOnce, t, showToast]);

  const doRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refreshMemorySummary();
      await refresh();
      invalidateCache();
      showToast(t('memorySummaryRefreshed'), 'success');
    } catch (err) {
      showConnectionErrorOnce(err);
    } finally {
      setRefreshing(false);
    }
  }, [refresh, showToast, t, invalidateCache, showConnectionErrorOnce]);

  const cardBg = isDark ? 'bg-white/[0.03] border-white/[0.06]' : 'bg-gray-50 border-gray-200';
  const muted = isDark ? 'text-white/65' : 'text-gray-600';
  const label = isDark ? 'text-white/80' : 'text-gray-800';
  const inputStyle = isDark
    ? 'bg-black/40 border-white/[0.06] text-white/90 placeholder-white/55'
    : 'bg-white border-gray-200 text-gray-800 placeholder-gray-600';

  return (
    <section className="space-y-4">
      {loadError && (
        <div role="alert" className={`flex flex-wrap items-center justify-between gap-2 rounded-xl border p-4 text-sm ${cardBg}`}>
          <p className={label}>{loadError}</p>
          <button type="button" onClick={() => void refresh()} className={`min-h-11 rounded-lg px-3 font-medium hover:bg-[#006bbd]/10 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${isDark ? 'text-[#4aa7ed]' : 'text-[#005a9e]'}`}>
            {t('retry')}
          </button>
        </div>
      )}
      {/* Project memory (free-form notes) */}
      <div className={`rounded-xl border p-4 space-y-2 ${cardBg}`}>
        <div className="flex items-center justify-between">
          <div>
            <h2 className={`text-sm font-medium ${label}`}>{t('projectMemoryTitle')}</h2>
            <div className={`text-sm ${muted}`}>
              {t('projectMemoryDesc')}
            </div>
          </div>
        </div>
        <textarea
          aria-label={t('projectMemoryTitle')}
          value={projectNotes}
          onChange={(e) => setProjectNotes(e.target.value)}
          rows={4}
          placeholder={t('projectMemoryPlaceholder')}
          className={`w-full rounded-lg border px-3 py-2 text-base sm:text-sm outline-hidden focus:border-[#006bbd]/40 ${inputStyle}`}
        />
      </div>

      {/* Auto-summary */}
      <div className={`rounded-xl border p-4 space-y-2 ${cardBg}`}>
        <div className="flex items-center justify-between">
          <div>
            <h2 className={`text-sm font-medium ${label}`}>{t('memoryAutoSummaryTitle')}</h2>
            {!loadError && <div className={`text-sm ${muted}`}>
              {hasLoaded ? t('memoryAutoSummaryDesc').replace('{count}', String(summary.count)) : t('loading')}
            </div>}
          </div>
          {canManageSystem && <button
            onClick={doRefresh}
            disabled={refreshing}
            className={`flex min-h-11 shrink-0 items-center gap-1.5 px-3 rounded-lg bg-[#006bbd]/15 text-sm font-medium hover:bg-[#006bbd]/25 disabled:opacity-50 transition-colors ${isDark ? 'text-[#4aa7ed]' : 'text-[#005a9e]'}`}
          >
            <MdAutoFixHigh size={14} /> {t('refresh')}
          </button>}
        </div>
        <div className={`rounded-lg border p-3 text-sm leading-relaxed ${isDark ? 'bg-black/30 border-white/[0.06] text-white/70' : 'bg-white border-gray-200 text-gray-700'}`}>
          {summary.summary
            ? summary.summary
            : <span className={muted}>{!hasLoaded ? t('loading') : loadError || t('memoryNoSummary')}</span>}
        </div>
      </div>

      {/* Add new memory */}
      {canManageSystem ? <div className={`rounded-xl border border-dashed p-4 space-y-2 ${cardBg}`}>
        <h2 className={`text-sm font-medium ${label}`}>{t('addMemoryTitle')}</h2>
        <input
          aria-label={t('addMemoryTitle')}
          value={newText}
          onChange={(e) => setNewText(e.target.value)}
          placeholder={t('memoryTextPlaceholder')}
          className={`w-full rounded-lg border px-3 py-2 text-base sm:text-sm outline-hidden focus:border-[#006bbd]/40 ${inputStyle}`}
        />
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <select
            aria-label={t('memoryKindLabel')}
            value={newKind}
            onChange={(event) => setNewKind(event.target.value as MemoryEntry['kind'])}
            className={`w-full rounded-lg border px-3 py-2 text-base sm:text-sm focus:border-[#006bbd]/40 ${inputStyle}`}
          >
            {(['fact', 'preference', 'decision', 'note'] as const).map((kind) => (
              <option key={kind} value={kind}>{t(`memoryKind_${kind}`)}</option>
            ))}
          </select>
          <label className={`flex items-center gap-2 rounded-lg border px-3 text-base sm:text-sm ${inputStyle}`}>
            <span>{t('memoryExpiryLabel')}</span>
            <input
              type="date"
              value={newExpiry}
              min={new Date().toISOString().slice(0, 10)}
              onChange={(event) => setNewExpiry(event.target.value)}
              className="min-w-0 flex-1 bg-transparent py-2"
            />
          </label>
        </div>
        <input
          aria-label={t('memoryTagsPlaceholder')}
          value={newTags}
          onChange={(e) => setNewTags(e.target.value)}
          placeholder={t('memoryTagsPlaceholder')}
          className={`w-full rounded-lg border px-3 py-2 text-base sm:text-sm outline-hidden focus:border-[#006bbd]/40 ${inputStyle}`}
        />
        <button
          onClick={add}
          disabled={!newText.trim()}
          className="flex min-h-11 items-center gap-1.5 px-3 rounded-lg bg-[#006bbd] text-white text-sm font-medium hover:bg-[#0059a0] disabled:opacity-30 transition-colors"
        >
          <MdAdd size={14} /> {t('add')}
        </button>
      </div> : <p role="note" className={`rounded-xl border p-3 text-sm ${cardBg} ${muted}`}>{t('deviceSystemScopeHint')}</p>}

      {/* Memory list */}
      <div className="space-y-2">
        {mems.length === 0 ? (
          !loadError && <p className={`rounded-xl border p-4 text-sm ${cardBg} ${muted}`}>{hasLoaded ? t('memoryEmpty') : t('loading')}</p>
        ) : (
          mems.map((m) => (
            <motion.div
              key={m.id}
              initial={{ opacity: 0, y: 2 }}
              animate={{ opacity: 1, y: 0 }}
              className={`rounded-xl border p-3 flex items-start gap-2 ${cardBg}`}
            >
              <div className="flex-1 min-w-0">
                {editingId === m.id ? (
                  <div className="space-y-2">
                    <input
                      aria-label={t('memoryTextPlaceholder')}
                      value={editText}
                      onChange={(event) => setEditText(event.target.value)}
                      className={`w-full rounded-lg border px-3 py-2 text-base sm:text-sm ${inputStyle}`}
                    />
                    <select
                      aria-label={t('memoryKindLabel')}
                      value={editKind}
                      onChange={(event) => setEditKind(event.target.value as MemoryEntry['kind'])}
                      className={`w-full rounded-lg border px-3 py-2 text-base sm:text-sm ${inputStyle}`}
                    >
                      {(['fact', 'preference', 'decision', 'note'] as const).map((kind) => (
                        <option key={kind} value={kind}>{t(`memoryKind_${kind}`)}</option>
                      ))}
                    </select>
                  </div>
                ) : (
                  <p className={`break-words text-sm ${isDark ? 'text-white/85' : 'text-gray-800'}`}>{m.text}</p>
                )}
                <div className={`mt-1.5 flex flex-wrap items-center gap-2 text-xs ${muted}`}>
                  <span>{new Date(m.created_at * 1000).toLocaleString(lang)}</span>
                  <span title={t('memoryWhyHint')}>
                    {t(`memoryKind_${m.kind ?? 'note'}`)} | {t(`memoryProvenance_${m.provenance ?? 'manual'}`)}
                  </span>
                  {m.expires_at ? <span>{t('memoryExpires')}: {new Date(m.expires_at * 1000).toLocaleDateString(lang)}</span> : null}
                  {m.tags?.length ? (
                    <span className="flex flex-wrap gap-1">
                      {m.tags.map((tag) => (
                        <span key={tag} className={`rounded bg-[#006bbd]/10 px-1.5 py-0.5 ${isDark ? 'text-[#4aa7ed]' : 'text-[#005a9e]'}`}>{tag}</span>
                      ))}
                    </span>
                  ) : null}
                </div>
              </div>
              {canManageSystem && (editingId === m.id ? (
                <div className="flex shrink-0 gap-1">
                  <button onClick={() => void saveEdit()} className={`grid h-11 w-11 place-items-center rounded-lg ${isDark ? 'text-emerald-400' : 'text-emerald-700'}`} aria-label={t('save')}>
                    <MdSave size={14} />
                  </button>
                  <button onClick={() => setEditingId(null)} className={`grid h-11 w-11 place-items-center rounded-lg ${muted}`} aria-label={t('cancel')}>
                    <MdClose size={14} />
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => beginEdit(m)}
                  className={`grid h-11 w-11 shrink-0 place-items-center rounded-lg ${isDark ? 'text-white/65 hover:text-white hover:bg-white/[0.05]' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'}`}
                  aria-label={t('edit')}
                >
                  <MdEdit size={14} />
                </button>
              ))}
              {canManageSystem && <button
                onClick={() => setPendingDelete(m.id)}
                className={`grid h-11 w-11 shrink-0 place-items-center rounded-lg ${isDark ? 'text-white/65 hover:text-red-400 hover:bg-white/[0.05]' : 'text-gray-600 hover:text-red-700 hover:bg-gray-100'}`}
                aria-label={t('delete')}
              >
                <MdDelete size={14} />
              </button>}
            </motion.div>
          ))
        )}
      </div>
      {canManageSystem && <ConfirmModal
        open={pendingDelete !== null}
        title={t('delete')}
        message={t('memoryDeleteConfirm')}
        confirmLabel={t('delete')}
        cancelLabel={t('cancel')}
        danger
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => {
          const id = pendingDelete;
          setPendingDelete(null);
          if (id) void del(id);
        }}
      />}
    </section>
  );
}
