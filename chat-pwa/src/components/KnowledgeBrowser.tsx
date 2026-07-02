import { useEffect, useMemo, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { MdArrowBack, MdSearch, MdFolder, MdDescription, MdContentCopy, MdCheck, MdClose, MdFolderOpen } from 'react-icons/md';
import { useTheme } from '../theme/ThemeContext';
import { useI18n } from '../i18n/I18nContext';
import { escapeRegExp } from '../utils/str';
import { getCollections, getCollectionSources, getFileChunks, type Collection, type CollectionSourceRow, type FileChunk } from '../lib/api';

interface Props {
  onBack: () => void;
  /** Optional: open straight to a specific (collection, file) pair. */
  initialCollection?: string;
  initialFile?: string;
}

interface PendingBrowserTarget {
  collection?: unknown;
  file?: unknown;
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function KnowledgeBrowser({ onBack, initialCollection, initialFile }: Props) {
  const { isDark } = useTheme();
  const { t } = useI18n();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [activeCollectionId, setActiveCollectionId] = useState<string>(initialCollection || 'default');
  const [sources, setSources] = useState<CollectionSourceRow[]>([]);
  const [loadingSources, setLoadingSources] = useState(false);
  const [fileQuery, setFileQuery] = useState('');
  const [activeFile, setActiveFile] = useState<string | null>(initialFile || null);
  const [chunks, setChunks] = useState<FileChunk[]>([]);
  const [chunkTotal, setChunkTotal] = useState(0);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [chunkQuery, setChunkQuery] = useState('');
  const [copiedChunkId, setCopiedChunkId] = useState<string | null>(null);

  // Load collections on mount
  useEffect(() => {
    const c = new AbortController();
    getCollections(c.signal)
      .then((items) => {
        const next = items.length ? items : [{ id: 'default', name: 'General', created_at: Date.now() / 1000, updated_at: Date.now() / 1000 }];
        setCollections(next);
        if (!next.some((x) => x.id === activeCollectionId)) {
          setActiveCollectionId(next[0].id);
        }
      })
      .catch(() => undefined);
    return () => c.abort();
  }, []);

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
      setActiveCollectionId(collection);
      if (file) {
        setActiveFile(file);
        setFileQuery(file.split('/').pop() || file);
      }
    }
  }, []);

  // Load sources when collection changes
  useEffect(() => {
    if (!activeCollectionId) return;
    const c = new AbortController();
    setLoadingSources(true);
    getCollectionSources(activeCollectionId, c.signal)
      .then((res) => setSources(res.sources || []))
      .catch(() => setSources([]))
      .finally(() => setLoadingSources(false));
    return () => c.abort();
  }, [activeCollectionId]);

  // Load chunks when active file changes (or when chunk query changes).
  useEffect(() => {
    if (!activeCollectionId || !activeFile) {
      setChunks([]);
      setChunkTotal(0);
      return;
    }
    const c = new AbortController();
    setLoadingChunks(true);
    const q = chunkQuery.trim();
    // Server-side search when the user has typed a query; otherwise fetch all.
    const opts: Parameters<typeof getFileChunks>[2] = { limit: 500, signal: c.signal };
    if (q) opts.q = q;
    // Debounce server-side searches to avoid hammering the API while typing.
    const delay = q ? 220 : 0;
    const id = window.setTimeout(() => {
      getFileChunks(activeCollectionId, activeFile, opts)
        .then((res) => {
          setChunks(res.chunks || []);
          setChunkTotal(res.total || (res.chunks || []).length);
        })
        .catch(() => {
          setChunks([]);
          setChunkTotal(0);
        })
        .finally(() => setLoadingChunks(false));
    }, delay);
    return () => { c.abort(); window.clearTimeout(id); };
  }, [activeCollectionId, activeFile, chunkQuery]);

  const filteredSources = useMemo(() => {
    const q = fileQuery.trim().toLowerCase();
    if (!q) return sources;
    return sources.filter((s) => s.file.toLowerCase().includes(q));
  }, [sources, fileQuery]);

  const filteredChunks = useMemo(() => chunks, [chunks]);

  const copyChunk = useCallback(async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedChunkId(id);
      window.setTimeout(() => setCopiedChunkId((cur) => (cur === id ? null : cur)), 1400);
    } catch {
      /* ignore */
    }
  }, []);

  const bg = isDark ? 'bg-black text-white' : 'bg-white text-gray-900';
  const border = isDark ? 'border-white/[0.06]' : 'border-gray-200';
  const panelBg = isDark ? 'bg-white/[0.02]' : 'bg-gray-50';
  const hover = isDark ? 'hover:bg-white/[0.04]' : 'hover:bg-gray-100';
  const muted = isDark ? 'text-white/45' : 'text-gray-500';
  const selected = isDark ? 'bg-[#006bbd]/15 text-white' : 'bg-[#006bbd]/10 text-gray-900';
  const placeholder = isDark ? 'placeholder-white/25' : 'placeholder-gray-400';
  const inputStyle = isDark
    ? 'bg-white/[0.03] border-white/[0.06] text-white/80'
    : 'bg-white border-gray-200 text-gray-800';

  return (
    <div className={`h-full flex flex-col min-w-0 ${bg}`}>
      {/* Header */}
      <div className={`shrink-0 flex items-center gap-3 px-4 pt-[env(safe-area-inset-top,0px)] pb-3 border-b ${border}`}>
        <button onClick={onBack} className={`p-2 -ml-2 ${isDark ? 'text-white/60 hover:text-white' : 'text-gray-500 hover:text-gray-800'}`}>
          <MdArrowBack size={20} />
        </button>
        <span className="text-sm font-medium">{t('knowledgeBrowser')}</span>
      </div>

      <div className="flex-1 flex min-h-0">
        {/* Collections column */}
        <aside className={`w-44 sm:w-52 shrink-0 border-r ${border} overflow-y-auto`}>
          <div className={`px-3 py-2 text-[10px] uppercase tracking-widest ${muted}`}>{t('collectionsLabel')}</div>
          {collections.map((col) => (
            <button
              key={col.id}
              onClick={() => { setActiveCollectionId(col.id); setActiveFile(null); }}
              className={`w-full text-left flex items-center gap-2 px-3 py-2 text-sm ${col.id === activeCollectionId ? selected : `${muted} ${hover}`}`}
            >
              <MdFolder size={14} className="shrink-0 opacity-70" />
              <span className="truncate">{col.name}</span>
            </button>
          ))}
        </aside>

        {/* Files column */}
        <div className={`w-56 sm:w-72 shrink-0 border-r ${border} flex flex-col min-h-0`}>
          <div className={`px-3 py-2 flex items-center gap-2 border-b ${border} ${panelBg}`}>
            <MdSearch size={14} className={muted} />
            <input
              value={fileQuery}
              onChange={(e) => setFileQuery(e.target.value)}
              placeholder={t('searchFiles')}
              className={`min-w-0 flex-1 bg-transparent text-sm outline-none ${placeholder} ${isDark ? 'text-white/80' : 'text-gray-800'}`}
            />
            {fileQuery && (
              <button onClick={() => setFileQuery('')} className={`p-0.5 rounded ${muted} ${hover}`} aria-label={t('clearFilter')}>
                <MdClose size={14} />
              </button>
            )}
          </div>
          <div className="flex-1 overflow-y-auto">
            {loadingSources ? (
              <p className={`px-3 py-4 text-xs ${muted}`}>{t('loading')}</p>
            ) : filteredSources.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-2 px-4 py-8 text-center">
                <MdFolderOpen size={32} className={`opacity-25 ${isDark ? 'text-white' : 'text-gray-900'}`} />
                <p className={`text-xs ${muted}`}>{sources.length === 0 ? t('noIndexedFiles') : t('noMatches')}</p>
              </div>
            ) : (
              filteredSources.map((s) => (
                <button
                  key={s.file}
                  onClick={() => setActiveFile(s.file)}
                  className={`w-full text-left px-3 py-2 border-b ${border} ${activeFile === s.file ? selected : `${muted} ${hover}`}`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <MdDescription size={14} className="shrink-0 opacity-70" />
                    <span className={`text-xs truncate ${isDark ? 'text-white/80' : 'text-gray-800'}`}>{s.file}</span>
                  </div>
                  <div className={`mt-1 text-[10px] ${muted} flex items-center gap-2`}>
                    <span>{s.chunks} {t('chunksUnit')}</span>
                    <span>·</span>
                    <span>{formatBytes(s.size)}</span>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Chunks column */}
        <div className="flex-1 flex flex-col min-h-0 min-w-0">
          {!activeFile ? (
            <div className={`flex-1 flex flex-col items-center justify-center gap-3 text-sm ${muted}`}>
              <MdDescription size={36} className="opacity-20" />
              <span className="text-xs">{t('selectFilePrompt')}</span>
            </div>
          ) : (
            <>
              <div className={`px-4 py-3 border-b ${border} ${panelBg}`}>
                <div className="flex items-center gap-2 min-w-0">
                  <MdDescription size={16} className={`shrink-0 ${muted}`} />
                  <span className={`text-sm font-mono truncate ${isDark ? 'text-white/80' : 'text-gray-800'}`}>{activeFile}</span>
                </div>
                <div className={`mt-1 text-[11px] ${muted}`}>
                  {chunkTotal} {t('chunksTotal')}
                </div>
                <div className={`mt-2 flex items-center gap-2 rounded-lg border px-2 py-1.5 ${inputStyle}`}>
                  <MdSearch size={14} className={muted} />
                  <input
                    value={chunkQuery}
                    onChange={(e) => setChunkQuery(e.target.value)}
                    placeholder={t('searchChunks')}
                    className={`min-w-0 flex-1 bg-transparent text-xs outline-none ${placeholder} ${isDark ? 'text-white/80' : 'text-gray-800'}`}
                  />
                </div>
              </div>
              <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
                {loadingChunks ? (
                  <p className={`text-xs ${muted}`}>{t('loadingChunks')}</p>
                ) : filteredChunks.length === 0 ? (
                  <div className="flex flex-col items-center justify-center gap-2 py-8 text-center">
                    <MdSearch size={28} className={`opacity-25 ${isDark ? 'text-white' : 'text-gray-900'}`} />
                    <p className={`text-xs ${muted}`}>{chunks.length === 0 ? t('noChunks') : t('noMatches')}</p>
                  </div>
                ) : (
                  filteredChunks.map((chunk, idx) => (
                    <motion.div
                      key={chunk.id}
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.18 }}
                      className={`rounded-xl border ${border} p-3 ${panelBg}`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span className={`text-[10px] font-mono ${muted}`}>#{idx + 1}{chunk.metadata?.page ? ` · p.${chunk.metadata.page}` : ''}</span>
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
        </div>
      </div>
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
