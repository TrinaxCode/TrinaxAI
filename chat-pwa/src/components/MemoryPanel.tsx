import { useEffect, useRef, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { MdAdd, MdAutoFixHigh, MdClose, MdDelete, MdEdit, MdSave } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { useToast } from './Toast';
import { listMemories, addMemory, deleteMemory, refreshMemorySummary, getMemorySummary, updateMemory, type MemoryEntry, type MemorySummary } from '../lib/api';
import ConfirmModal from './ConfirmModal';

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
  const [newKind, setNewKind] = useState<MemoryEntry['kind']>('note');
  const [newExpiry, setNewExpiry] = useState('');
  const [projectNotes, setProjectNotes] = useState<string>(loadProjectMemory);
  const [refreshing, setRefreshing] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const [editKind, setEditKind] = useState<MemoryEntry['kind']>('note');
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
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
      toast.toast(t('memoryAdded'), 'success');
      invalidateCache();
      await refresh();
    } catch (err) {
      showConnectionErrorOnce(err);
    }
  }, [newText, newTags, newKind, newExpiry, toast, t, refresh, invalidateCache, showConnectionErrorOnce]);

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
      toast.toast(t('memoryUpdated'), 'success');
    } catch (err) {
      showConnectionErrorOnce(err);
    }
  }, [editKind, editText, editingId, invalidateCache, refresh, showConnectionErrorOnce, t, toast]);

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
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <select
            aria-label={t('memoryKindLabel')}
            value={newKind}
            onChange={(event) => setNewKind(event.target.value as MemoryEntry['kind'])}
            className={`w-full rounded-lg border px-3 py-2 text-xs focus:border-[#006bbd]/40 ${inputStyle}`}
          >
            {(['fact', 'preference', 'decision', 'note'] as const).map((kind) => (
              <option key={kind} value={kind}>{t(`memoryKind_${kind}`)}</option>
            ))}
          </select>
          <label className={`flex items-center gap-2 rounded-lg border px-3 text-xs ${inputStyle}`}>
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
                {editingId === m.id ? (
                  <div className="space-y-2">
                    <input
                      aria-label={t('memoryTextPlaceholder')}
                      value={editText}
                      onChange={(event) => setEditText(event.target.value)}
                      className={`w-full rounded-lg border px-3 py-2 text-xs ${inputStyle}`}
                    />
                    <select
                      aria-label={t('memoryKindLabel')}
                      value={editKind}
                      onChange={(event) => setEditKind(event.target.value as MemoryEntry['kind'])}
                      className={`w-full rounded-lg border px-3 py-2 text-xs ${inputStyle}`}
                    >
                      {(['fact', 'preference', 'decision', 'note'] as const).map((kind) => (
                        <option key={kind} value={kind}>{t(`memoryKind_${kind}`)}</option>
                      ))}
                    </select>
                  </div>
                ) : (
                  <p className={`text-xs ${isDark ? 'text-white/80' : 'text-gray-800'} break-words`}>{m.text}</p>
                )}
                <div className={`mt-1.5 flex flex-wrap items-center gap-2 text-[10px] ${muted}`}>
                  <span>{new Date(m.created_at * 1000).toLocaleString()}</span>
                  <span title={t('memoryWhyHint')}>
                    {t(`memoryKind_${m.kind ?? 'note'}`)} · {t(`memoryProvenance_${m.provenance ?? 'manual'}`)}
                  </span>
                  {m.expires_at ? <span>{t('memoryExpires')}: {new Date(m.expires_at * 1000).toLocaleDateString()}</span> : null}
                  {m.tags?.length ? (
                    <span className="flex flex-wrap gap-1">
                      {m.tags.map((tag) => (
                        <span key={tag} className="px-1.5 py-0.5 rounded bg-[#006bbd]/10 text-[#006bbd]">{tag}</span>
                      ))}
                    </span>
                  ) : null}
                </div>
              </div>
              {editingId === m.id ? (
                <div className="flex shrink-0 gap-1">
                  <button onClick={() => void saveEdit()} className="rounded-lg p-1.5 text-emerald-500" aria-label={t('save')}>
                    <MdSave size={14} />
                  </button>
                  <button onClick={() => setEditingId(null)} className={`rounded-lg p-1.5 ${muted}`} aria-label={t('cancel')}>
                    <MdClose size={14} />
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => beginEdit(m)}
                  className={`shrink-0 p-1.5 rounded-lg ${isDark ? 'text-white/25 hover:text-white/70 hover:bg-white/[0.05]' : 'text-gray-300 hover:text-gray-700 hover:bg-gray-100'}`}
                  aria-label={t('edit')}
                >
                  <MdEdit size={14} />
                </button>
              )}
              <button
                onClick={() => setPendingDelete(m.id)}
                className={`shrink-0 p-1.5 rounded-lg ${isDark ? 'text-white/25 hover:text-red-400 hover:bg-white/[0.05]' : 'text-gray-300 hover:text-red-500 hover:bg-gray-100'}`}
                aria-label={t('delete')}
              >
                <MdDelete size={14} />
              </button>
            </motion.div>
          ))
        )}
      </div>
      <ConfirmModal
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
      />
    </section>
  );
}
