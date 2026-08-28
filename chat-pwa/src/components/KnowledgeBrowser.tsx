import { useEffect, useMemo, useState, useCallback, useRef } from 'react';
import { motion } from 'framer-motion';
import { MdSearch, MdFolder, MdDescription, MdContentCopy, MdCheck, MdClose, MdFolderOpen, MdDelete, MdDeleteSweep, MdChevronRight } from 'react-icons/md';
import { useTheme } from '../theme/ThemeContext';
import { useI18n } from '../i18n/I18nContext';
import { useToast } from './Toast';
import { escapeRegExp } from '../utils/str';
import { getCollections, getCollectionSources, getFileChunks, deleteCollectionSources, deleteSource, userFacingError, type Collection, type CollectionSourceRow, type FileChunk } from '../lib/api';
import BackButton from './BackButton';
import ConfirmModal from './ConfirmModal';

interface Props {
  onBack: () => void;
  canManageSystem?: boolean;
  /** Optional: open straight to a specific (collection, file) pair. */
  initialCollection?: string;
  initialFile?: string;
}

interface PendingBrowserTarget {
  collection?: unknown;
  file?: unknown;
  source_id?: unknown;
}

function sourceIdentity(file: string, sourceId?: string | null): string {
  return `${sourceId || 'legacy'}\u0000${file}`;
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function KnowledgeBrowser({ onBack, canManageSystem = false, initialCollection, initialFile }: Props) {
  const { isDark } = useTheme();
  const { t } = useI18n();
  const toast = useToast();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [loadingCollections, setLoadingCollections] = useState(false);
  const [collectionsError, setCollectionsError] = useState<string | null>(null);
  const [activeCollectionId, setActiveCollectionId] = useState<string>(initialCollection || 'default');
  const [sources, setSources] = useState<CollectionSourceRow[]>([]);
  const [loadingSources, setLoadingSources] = useState(false);
  const [sourcesError, setSourcesError] = useState<string | null>(null);
  const [fileQuery, setFileQuery] = useState('');
  const [activeFile, setActiveFile] = useState<string | null>(initialFile || null);
  const [activeSourceId, setActiveSourceId] = useState<string | null>(null);
  const [chunks, setChunks] = useState<FileChunk[]>([]);
  const [chunkTotal, setChunkTotal] = useState(0);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [chunksError, setChunksError] = useState<string | null>(null);
  const [chunkRetry, setChunkRetry] = useState(0);
  const [chunkQuery, setChunkQuery] = useState('');
  const [copiedChunkId, setCopiedChunkId] = useState<string | null>(null);
  const [deletingFile, setDeletingFile] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<{ file: string; name: string; sourceId: string | null } | null>(null);
  // Mobile: which panel is visible ('collections' | 'files' | 'chunks')
  const [mobileView, setMobileView] = useState<'collections' | 'files' | 'chunks'>(initialFile ? 'chunks' : 'collections');
  const collectionsRequestRef = useRef(0);
  const sourcesRequestRef = useRef(0);
  const chunksRequestRef = useRef(0);

  const loadCollections = useCallback((signal?: AbortSignal) => {
    const requestId = ++collectionsRequestRef.current;
    setLoadingCollections(true);
    setCollectionsError(null);
    getCollections(signal)
      .then((items) => {
        if (requestId !== collectionsRequestRef.current || signal?.aborted) return;
        setCollections(items);
        setActiveCollectionId((current) => items.length && !items.some((x) => x.id === current) ? items[0].id : current);
      })
      .catch((err) => {
        if (requestId !== collectionsRequestRef.current || signal?.aborted) return;
        setCollectionsError(userFacingError(err, 'external_service_unavailable'));
      })
      .finally(() => {
        if (requestId === collectionsRequestRef.current && !signal?.aborted) setLoadingCollections(false);
      });
  }, []);

  // Load collections on mount
  useEffect(() => {
    const c = new AbortController();
    loadCollections(c.signal);
    return () => c.abort();
  }, [loadCollections]);

  // Consume any pending open-in-browser target on first render.
  useEffect(() => {
    const target = (window as any).__tc_browser_open as PendingBrowserTarget | undefined;
    if (target) {
      (window as any).__tc_browser_open = null;
      const collection = typeof target.collection === 'string' && target.collection.trim()
        ? target.collection.trim()
        : 'default';
      const file = typeof target.file === 'string' && target.file.trim()
        ? target.file.trim()
        : '';
      const sourceId = typeof target.source_id === 'string' && target.source_id.trim()
        ? target.source_id.trim()
        : null;
      setActiveCollectionId(collection);
      if (file) {
        setActiveFile(file);
        setActiveSourceId(sourceId);
        setFileQuery(file.split('/').pop() || file);
        setMobileView('chunks');
      }
    }
  }, []);

  // Load sources when collection changes
  useEffect(() => {
    if (!activeCollectionId) return;
    const requestId = ++sourcesRequestRef.current;
    const c = new AbortController();
    setLoadingSources(true);
    setSourcesError(null);
    getCollectionSources(activeCollectionId, c.signal)
      .then((res) => {
        if (requestId !== sourcesRequestRef.current || c.signal.aborted) return;
        setSources(res.sources || []);
      })
      .catch((err) => {
        if (requestId !== sourcesRequestRef.current || c.signal.aborted) return;
        setSourcesError(userFacingError(err, 'external_service_unavailable'));
      })
      .finally(() => {
        if (requestId === sourcesRequestRef.current) setLoadingSources(false);
      });
    return () => c.abort();
  }, [activeCollectionId]);

  // Load chunks when active file changes (or when chunk query changes).
  useEffect(() => {
    const requestId = ++chunksRequestRef.current;
    if (!activeCollectionId || !activeFile) {
      setChunks([]);
      setChunkTotal(0);
      setLoadingChunks(false);
      setChunksError(null);
      return;
    }
    const c = new AbortController();
    setLoadingChunks(true);
    setChunksError(null);
    const q = chunkQuery.trim();
    // Server-side search when the user has typed a query; otherwise fetch all.
    const opts: Parameters<typeof getFileChunks>[2] = {
      limit: 100,
      sourceId: activeSourceId,
      signal: c.signal,
    };
    if (q) opts.q = q;
    // Debounce server-side searches to avoid hammering the API while typing.
    const delay = q ? 220 : 0;
    const id = window.setTimeout(() => {
      getFileChunks(activeCollectionId, activeFile, opts)
        .then((res) => {
          if (requestId !== chunksRequestRef.current || c.signal.aborted) return;
          const nextChunks = res.chunks || [];
          setChunks(nextChunks);
          setChunkTotal(typeof res.total === 'number' ? res.total : nextChunks.length);
        })
        .catch((err) => {
          if (requestId !== chunksRequestRef.current || c.signal.aborted) return;
          setChunksError(userFacingError(err, 'external_service_unavailable'));
        })
        .finally(() => {
          if (requestId === chunksRequestRef.current) setLoadingChunks(false);
        });
    }, delay);
    return () => { c.abort(); window.clearTimeout(id); };
  }, [activeCollectionId, activeFile, activeSourceId, chunkQuery, chunkRetry]);

  const filteredSources = useMemo(() => {
    const q = fileQuery.trim().toLowerCase();
    if (!q) return sources;
    return sources.filter((s) => s.file.toLowerCase().includes(q));
  }, [sources, fileQuery]);

  const filteredChunks = useMemo(() => chunks.slice(0, 100), [chunks]);

  const copyChunk = useCallback(async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedChunkId(id);
      window.setTimeout(() => setCopiedChunkId((cur) => (cur === id ? null : cur)), 1400);
    } catch {
      /* ignore */
    }
  }, []);

  const refreshSources = useCallback(() => {
    if (!activeCollectionId) return;
    const requestId = ++sourcesRequestRef.current;
    const c = new AbortController();
    setLoadingSources(true);
    setSourcesError(null);
    getCollectionSources(activeCollectionId, c.signal)
      .then((res) => {
        if (requestId !== sourcesRequestRef.current || c.signal.aborted) return;
        setSources(res.sources || []);
      })
      .catch((err) => {
        if (requestId !== sourcesRequestRef.current || c.signal.aborted) return;
        setSourcesError(userFacingError(err, 'external_service_unavailable'));
      })
      .finally(() => {
        if (requestId === sourcesRequestRef.current && !c.signal.aborted) setLoadingSources(false);
      });
    return () => c.abort();
  }, [activeCollectionId]);

  const handleDeleteFile = useCallback(async (file: string, sourceId: string | null) => {
    const identity = sourceIdentity(file, sourceId);
    setDeletingFile(identity);
    try {
      const res = await deleteSource(activeCollectionId, file, sourceId);
      toast.toast(t('sourceDeleted').replace('{file}', file.split('/').pop() || file).replace('{count}', String(res.deleted)), 'info');
      // If we're viewing this file, clear the view
      if (activeFile === file && activeSourceId === sourceId) {
        setActiveFile(null);
        setActiveSourceId(null);
        setChunks([]);
        setChunkTotal(0);
      }
      // Refresh the source list
      refreshSources();
    } catch (err) {
      toast.toast(userFacingError(err, 'external_service_unavailable'), 'error');
    } finally {
      setDeletingFile(null);
      setConfirmDelete(null);
    }
  }, [activeCollectionId, activeFile, activeSourceId, refreshSources, t, toast]);

  const handleDeleteAll = useCallback(async () => {
    setDeletingFile('__all__');
    try {
      const result = await deleteCollectionSources(activeCollectionId);
      toast.toast(t('allSourcesDeleted').replace('{count}', String(result.deleted)), 'info');
      setActiveFile(null);
      setActiveSourceId(null);
      setChunks([]);
      setChunkTotal(0);
      refreshSources();
    } catch {
      toast.toast(t('sourceDeleteFailed'), 'error');
    } finally {
      setDeletingFile(null);
    }
  }, [activeCollectionId, refreshSources, t, toast]);

  const bg = isDark ? 'bg-black/70 text-white' : 'bg-white/70 text-gray-900';
  const border = isDark ? 'border-white/[0.06]' : 'border-gray-200';
  const panelBg = isDark ? 'bg-white/[0.02]' : 'bg-gray-50';
  const hover = isDark ? 'hover:bg-white/[0.04]' : 'hover:bg-gray-100';
  const muted = isDark ? 'text-white/45' : 'text-gray-500';
  const selected = isDark ? 'bg-[#006bbd]/15 text-white' : 'bg-[#006bbd]/10 text-gray-900';
  const placeholder = isDark ? 'placeholder-white/25' : 'placeholder-gray-400';
  const inputStyle = isDark
    ? 'bg-white/[0.03] border-white/[0.06] text-white/80'
    : 'bg-white border-gray-200 text-gray-800';

  const renderStatus = (loading: boolean, error: string | null, retry: () => void) => (
    <>
      {loading && <p aria-live="polite" className={`px-3 py-2 text-xs ${muted}`}>{t('loading')}</p>}
      {error && (
        <div aria-live="polite" className="px-3 py-2 text-xs">
          <p className={muted}>{error}</p>
          <button type="button" onClick={retry} className="mt-1 text-[#006bbd] underline underline-offset-2">{t('retry')}</button>
        </div>
      )}
    </>
  );

  // Shared file list renderer (used by both desktop and mobile)
  const renderFileList = (compact: boolean) => (
    <div className="flex-1 overflow-y-auto">
      {renderStatus(loadingSources, sourcesError, refreshSources)}
      {!loadingSources && !sourcesError && filteredSources.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 px-4 py-8 text-center">
          <MdFolderOpen size={32} className={`opacity-25 ${isDark ? 'text-white' : 'text-gray-900'}`} />
          <p className={`text-xs ${muted}`}>{sources.length === 0 ? t('noIndexedFiles') : t('noMatches')}</p>
        </div>
      ) : filteredSources.length > 0 && (
        filteredSources.map((s) => (
          <div
            key={sourceIdentity(s.file, s.source_id)}
            className={`browser-file-row group flex items-center border-b ${border}`}
          >
            <button
              onClick={() => {
                setActiveFile(s.file);
                setActiveSourceId(s.source_id || null);
                if (compact) setMobileView('chunks');
              }}
              className={`flex-1 min-w-0 text-left px-3 py-2 ${activeFile === s.file && activeSourceId === (s.source_id || null) ? selected : `${muted} ${hover}`}`}
              aria-selected={activeFile === s.file && activeSourceId === (s.source_id || null)}
            >
              <div className="flex items-center gap-2 min-w-0">
                <MdDescription size={14} className="shrink-0 opacity-70" />
                <span className={`text-xs truncate ${isDark ? 'text-white/80' : 'text-gray-800'}`}>{s.file}</span>
              </div>
              <div className={`mt-1 text-[10px] ${muted} flex items-center gap-2`}>
                <span>{s.chunks} {t('chunksUnit')}</span>
                <span>|</span>
                <span>{formatBytes(s.size)}</span>
                {s.source_id && (
                  <>
                    <span>|</span>
                    <span className="truncate" title={s.source_id}>{s.source_id}</span>
                  </>
                )}
              </div>
            </button>
            {canManageSystem && <button
              onClick={(e) => {
                e.stopPropagation();
                setConfirmDelete({
                  file: s.file,
                  name: s.file.split('/').pop() || s.file,
                  sourceId: s.source_id || null,
                });
              }}
              disabled={deletingFile === sourceIdentity(s.file, s.source_id)}
              className="shrink-0 p-2 mr-1 rounded-lg opacity-0 group-hover:opacity-100
                         text-red-400/70 hover:text-red-400 hover:bg-red-400/10
                         disabled:opacity-30 transition-[background-color,color,border-color,opacity,transform]"
              aria-label={`${t('delete')} ${s.file}`}
              title={t('delete')}
            >
              <MdDelete size={14} />
            </button>}
          </div>
        ))
      )}
    </div>
  );

  // Shared chunk panel renderer
  const renderChunkPanel = (compact: boolean) => (
    <>
      {!activeFile ? (
        <div className={`flex-1 flex flex-col items-center justify-center gap-3 text-sm ${muted}`}>
          <MdDescription size={36} className="opacity-20" />
          <span className="text-xs">{t('selectFilePrompt')}</span>
        </div>
      ) : (
        <>
          <div className={`${compact ? 'px-3' : 'px-4'} py-3 border-b ${border} ${panelBg} shrink-0`}>
            {!compact && (
              <div className="flex items-center gap-2 min-w-0">
                <MdDescription size={16} className={`shrink-0 ${muted}`} />
                <span className={`text-sm font-mono truncate ${isDark ? 'text-white/80' : 'text-gray-800'}`}>{activeFile}</span>
              </div>
            )}
            <div className={`${compact ? 'text-[10px]' : 'mt-1 text-[11px]'} ${muted}`}>
              {chunkTotal} {t('chunksTotal')}
            </div>
            <div className={`mt-2 flex items-center gap-2 rounded-lg border px-2 py-1.5 ${inputStyle}`}>
              <MdSearch size={14} className={muted} />
              <input
                value={chunkQuery}
                onChange={(e) => setChunkQuery(e.target.value)}
                placeholder={t('searchChunks')}
                aria-label={t('searchChunks')}
                className={`min-w-0 flex-1 rounded bg-transparent text-xs ${placeholder} focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${isDark ? 'text-white/80' : 'text-gray-800'}`}
              />
            </div>
          </div>
          <div className="flex-1 overflow-y-auto px-3 sm:px-4 py-3 space-y-3">
            {renderStatus(loadingChunks, chunksError, () => setChunkRetry((value) => value + 1))}
            {!loadingChunks && !chunksError && filteredChunks.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
                <MdSearch size={28} className={`opacity-25 ${isDark ? 'text-white' : 'text-gray-900'}`} />
                <p className={`text-xs ${muted}`}>{chunks.length === 0 ? t('noChunks') : t('noMatches')}</p>
              </div>
            ) : filteredChunks.length > 0 && (
              filteredChunks.map((chunk, idx) => (
                <motion.div
                  key={chunk.id}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.18 }}
                  className={`rounded-xl border ${border} p-3 ${panelBg}`}
                >
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className={`text-[10px] font-mono ${muted}`}>#{idx + 1}{chunk.metadata?.page ? ` | ${t('pageAbbrev')}${chunk.metadata.page}` : ''}</span>
                    <button
                      onClick={() => copyChunk(chunk.text, chunk.id)}
                      className={`p-1 rounded ${muted} ${hover}`}
                      aria-label={t('copyChunk')}
                      title={t('copy')}
                    >
                      {copiedChunkId === chunk.id ? <MdCheck size={14} /> : <MdContentCopy size={14} />}
                    </button>
                  </div>
                  <pre className={`whitespace-pre-wrap break-words text-xs leading-relaxed ${isDark ? 'text-white/80' : 'text-gray-800'} font-mono`}>
                    {highlightText(chunk.text, chunkQuery)}
                  </pre>
                </motion.div>
              ))
            )}
          </div>
        </>
      )}
    </>
  );

  return (
    <div className={`browser-page h-full flex flex-col min-w-0 ${bg}`}>
      {/* Header */}
      <div className={`page-header shrink-0 flex items-center gap-3 px-4 pt-[env(safe-area-inset-top,0px)] pb-3 border-b ${border}`}>
        <BackButton onClick={onBack} label={t('back')} isDark={isDark} className="-ml-2" />
        <h1 className="text-sm font-medium">{t('knowledgeBrowser')}</h1>
      </div>

      {/* ── Desktop: 3-column layout (sm+) ── */}
      <div className="hidden sm:flex flex-1 min-h-0">
        {/* Collections column */}
        <aside className={`browser-panel w-44 sm:w-52 shrink-0 border-r ${border} overflow-y-auto`}>
          <div className={`px-3 py-2 text-[10px] uppercase tracking-widest ${muted}`}>{t('collectionsLabel')}</div>
          {renderStatus(loadingCollections, collectionsError, () => loadCollections())}
          {!loadingCollections && !collectionsError && collections.length === 0 && <p className={`px-3 py-4 text-xs ${muted}`}>{t('noCollections')}</p>}
          {collections.map((col) => (
            <button
              key={col.id}
              onClick={() => { setActiveCollectionId(col.id); setActiveFile(null); setActiveSourceId(null); }}
              className={`w-full text-left flex items-center gap-2 px-3 py-2 text-sm ${col.id === activeCollectionId ? selected : `${muted} ${hover}`}`}
              aria-selected={col.id === activeCollectionId}
            >
              <MdFolder size={14} className="shrink-0 opacity-70" />
              <span className="truncate">{col.name}</span>
            </button>
          ))}
        </aside>

        {/* Files column */}
        <div className={`browser-panel w-56 sm:w-72 shrink-0 border-r ${border} flex flex-col min-h-0`}>
          <div className={`px-3 py-2 flex items-center gap-2 border-b ${border} ${panelBg}`}>
            <MdSearch size={14} className={muted} />
            <input
              value={fileQuery}
              onChange={(e) => setFileQuery(e.target.value)}
              placeholder={t('searchFiles')}
              aria-label={t('searchFiles')}
              name="knowledge-file-search"
              autoComplete="off"
              className={`min-w-0 flex-1 rounded bg-transparent text-sm ${placeholder} focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${isDark ? 'text-white/80' : 'text-gray-800'}`}
            />
            {fileQuery && (
              <button onClick={() => setFileQuery('')} className={`p-0.5 rounded ${muted} ${hover}`} aria-label={t('clearFilter')}>
                <MdClose size={14} />
              </button>
            )}
            {canManageSystem && sources.length > 0 && (
              <button
                onClick={() => {
                  if (confirm(t('deleteAllSourcesConfirm'))) {
                    void handleDeleteAll();
                  }
                }}
                disabled={deletingFile === '__all__'}
                className={`p-0.5 rounded ${muted} ${hover} disabled:opacity-30`}
                aria-label={t('deleteAllSources')}
                title={t('deleteAllSources')}
              >
                <MdDeleteSweep size={14} />
              </button>
            )}
          </div>
          {renderFileList(false)}
        </div>

        {/* Chunks column */}
        <div className="flex-1 flex flex-col min-h-0 min-w-0">{renderChunkPanel(false)}</div>
      </div>

      {/* ── Mobile: single-panel with bottom tab bar (below sm) ── */}
      <div className="flex sm:hidden flex-1 flex-col min-h-0 min-w-0">
        {/* Panel: Collections */}
        {mobileView === 'collections' && (
          <div className="flex-1 flex flex-col min-h-0">
            <div className={`px-3 py-2 text-[10px] uppercase tracking-widest ${muted} shrink-0`}>{t('collectionsLabel')}</div>
            <div className="flex-1 overflow-y-auto">
              {renderStatus(loadingCollections, collectionsError, () => loadCollections())}
              {!loadingCollections && !collectionsError && collections.length === 0 && <p className={`px-3 py-4 text-xs ${muted}`}>{t('noCollections')}</p>}
              {collections.map((col) => (
                <button
                  key={col.id}
                  onClick={() => { setActiveCollectionId(col.id); setActiveFile(null); setActiveSourceId(null); setMobileView('files'); }}
                  className={`w-full flex items-center justify-between gap-2 px-4 py-3 border-b ${border} ${col.id === activeCollectionId ? selected : `${muted} ${hover}`}`}
                  aria-selected={col.id === activeCollectionId}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <MdFolder size={16} className="shrink-0 opacity-70" />
                    <span className="text-sm truncate">{col.name}</span>
                  </div>
                  <MdChevronRight size={18} className="shrink-0 opacity-50" />
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Panel: Files */}
        {mobileView === 'files' && (
          <div className="flex-1 flex flex-col min-h-0">
            <div className={`shrink-0 flex items-center gap-2 px-2 py-2 border-b ${border} ${panelBg}`}>
              <BackButton
                onClick={() => { setMobileView('collections'); setActiveFile(null); setActiveSourceId(null); }}
                label={t('back')}
                isDark={isDark}
                className="-ml-2"
              />
              <span className={`text-xs font-medium truncate ${isDark ? 'text-white/80' : 'text-gray-800'}`}>
                {collections.find((c) => c.id === activeCollectionId)?.name || activeCollectionId}
              </span>
              {canManageSystem && sources.length > 0 && (
                <button
                  onClick={() => {
                    if (confirm(t('deleteAllSourcesConfirm'))) {
                      void handleDeleteAll();
                    }
                  }}
                  disabled={deletingFile === '__all__'}
                  className={`ml-auto p-1.5 rounded-lg ${muted} ${hover} disabled:opacity-30`}
                  aria-label={t('deleteAllSources')}
                >
                  <MdDeleteSweep size={16} />
                </button>
              )}
            </div>
            <div className={`px-3 py-2 flex items-center gap-2 border-b ${border}`}>
              <MdSearch size={14} className={muted} />
              <input
                value={fileQuery}
                onChange={(e) => setFileQuery(e.target.value)}
                placeholder={t('searchFiles')}
                aria-label={t('searchFiles')}
                name="knowledge-mobile-file-search"
                autoComplete="off"
                className={`min-w-0 flex-1 rounded bg-transparent text-sm ${placeholder} focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${isDark ? 'text-white/80' : 'text-gray-800'}`}
              />
              {fileQuery && (
                <button onClick={() => setFileQuery('')} className={`p-0.5 rounded ${muted} ${hover}`} aria-label={t('clearFilter')}>
                  <MdClose size={14} />
                </button>
              )}
            </div>
            {renderFileList(true)}
          </div>
        )}

        {/* Panel: Chunks */}
        {mobileView === 'chunks' && (
          <div className="flex-1 flex flex-col min-h-0 min-w-0">
            <div className={`shrink-0 flex items-center gap-2 px-2 py-2 border-b ${border} ${panelBg}`}>
              <BackButton
                onClick={() => { setMobileView('files'); }}
                label={t('back')}
                isDark={isDark}
                className="-ml-2"
              />
              <span className={`text-xs font-mono font-medium truncate ${isDark ? 'text-white/80' : 'text-gray-800'}`}>
                {activeFile?.split('/').pop() || activeFile}
              </span>
            </div>
            {renderChunkPanel(true)}
          </div>
        )}

        {/* Mobile bottom tab bar */}
        <div role="tablist" className={`shrink-0 flex border-t ${border} ${panelBg}`} style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}>
          {(['collections', 'files', 'chunks'] as const).map((view) => {
            const icons = { collections: <MdFolder size={18} />, files: <MdDescription size={18} />, chunks: <MdSearch size={18} /> };
            const labels = { collections: t('collectionsLabel'), files: t('sources'), chunks: t('chunksUnit') };
            const disabled = (view === 'files' && !collections.length) || (view === 'chunks' && !activeFile);
            return (
              <button
                key={view}
                role="tab"
                onClick={() => { if (!disabled) setMobileView(view); }}
                disabled={disabled}
                aria-label={labels[view]}
                aria-selected={mobileView === view}
                className={`flex-1 flex flex-col items-center justify-center gap-0.5 py-2 text-[10px] font-medium transition-colors ${
                  mobileView === view
                    ? 'text-[#006bbd]'
                    : disabled ? 'opacity-30' : muted
                }`}
              >
                {icons[view]}
                <span>{labels[view]}</span>
              </button>
            );
          })}
        </div>
      </div>

      <ConfirmModal
        open={Boolean(canManageSystem && confirmDelete)}
        title={t('deleteSourceConfirm')}
        message={confirmDelete?.name || ''}
        confirmLabel={deletingFile ? t('deleting') : t('delete')}
        cancelLabel={t('cancel')}
        danger
        confirmDisabled={Boolean(deletingFile)}
        onCancel={() => setConfirmDelete(null)}
        onConfirm={() => {
          if (confirmDelete) void handleDeleteFile(confirmDelete.file, confirmDelete.sourceId);
        }}
      />
    </div>
  );
}

function highlightText(text: string, query: string) {
  const q = query.trim();
  if (!q) return text;
  const tokens = q.split(/\s+/).filter((t) => t.length >= 2);
  if (tokens.length === 0) return text;
  const pattern = new RegExp(`(${tokens.map(escapeRegExp).join('|')})`, 'gi');
  const parts = text.split(pattern);
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <mark key={i} className="bg-[#006bbd]/30 text-inherit rounded px-0.5">
        {part}
      </mark>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}
