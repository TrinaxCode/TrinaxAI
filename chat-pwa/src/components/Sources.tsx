import { useState, useMemo, useId } from 'react';
import { useTheme } from '../theme/ThemeContext';
import { useI18n } from '../i18n/I18nContext';
import { MdContentCopy, MdCheck, MdLibraryBooks, MdOpenInNew } from 'react-icons/md';
import { escapeRegExp } from '../utils/str';
import type { Source } from '../lib/api';

interface Props {
  sources?: Source[];
  model?: string;
  project?: string | null;
  /** Optional user query — used for snippet highlighting. */
  query?: string;
  /** Optional callback when the user clicks "Open in Browser". */
  onOpenInBrowser?: (file: string, collectionId?: string) => void;
}

const STOPWORDS = new Set([
  'el', 'la', 'los', 'las', 'a', 'an', 'the', 'y', 'o', 'u', 'or', 'and',
  'de', 'del', 'en', 'por', 'para', 'con', 'sin', 'un', 'una', 'uno',
  'que', 'qué', 'como', 'cómo', 'es', 'son', 'está', 'están', 'ser',
  'is', 'are', 'be', 'been', 'to', 'of', 'in', 'on', 'for', 'with', 'this', 'that',
]);

function extractTerms(query: string): string[] {
  if (!query) return [];
  return query
    .toLowerCase()
    .split(/\W+/)
    .filter((t) => t.length >= 3 && !STOPWORDS.has(t))
    .slice(0, 8);
}

function highlight(text: string, terms: string[]): React.ReactNode {
  if (terms.length === 0) return text;
  const pattern = new RegExp(`(${terms.map(escapeRegExp).join('|')})`, 'gi');
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

export default function Sources({ sources, model, project, query, onOpenInBrowser }: Props) {
  const [open, setOpen] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const { isDark } = useTheme();
  const { t } = useI18n();
  const sourcesId = useId();
  const terms = useMemo(() => extractTerms(query || ''), [query]);

  const hasSources = sources && sources.length > 0;
  const webProviders = [...new Set((sources || []).map((source) => source.provider).filter(Boolean))];
  if (!model && !hasSources) return null;

  const copyPath = async (path: string, idx: number) => {
    try {
      await navigator.clipboard.writeText(path);
      setCopiedIdx(idx);
      window.setTimeout(() => setCopiedIdx((cur) => (cur === idx ? null : cur)), 1400);
    } catch { /* ignore */ }
  };

  return (
    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px]">
      {project && (
        <span className={isDark ? 'text-white/40' : 'text-gray-500'}>{project}</span>
      )}
      {model && (
        <span className={isDark ? 'text-white/35' : 'text-gray-400'}>{model}</span>
      )}
      {webProviders.length > 0 && (
        <span className={isDark ? 'text-white/35' : 'text-gray-400'}>Web: {webProviders.join(', ')}</span>
      )}
      {hasSources && (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className={`hover:underline transition-colors ${isDark ? 'text-white/40 hover:text-white/70' : 'text-gray-400 hover:text-gray-600'}`}
          aria-expanded={open}
          aria-controls={sourcesId}
        >
          {open ? '▾' : '▸'} {sources!.length} {sources!.length === 1 ? t('source') : t('sources')}
        </button>
      )}

      {open && hasSources && (
        <div id={sourcesId} className="w-full flex flex-col gap-1.5 mt-1">
          {sources!.map((s, i) => (
            <div
              key={`${s.file}-${i}`}
              className={`rounded-lg border px-2.5 py-1.5 ${isDark ? 'bg-black/40 border-white/[0.06]' : 'bg-gray-50 border-gray-200'}`}
            >
              <div className="flex items-center justify-between gap-2">
                {s.url ? (
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`min-w-0 truncate text-[11px] hover:underline ${isDark ? 'text-[#4ea3e0]' : 'text-[#006bbd]'}`}
                    title={s.url}
                  >
                    {s.title || s.url}
                  </a>
                ) : (
                  <button
                    type="button"
                    className={`min-w-0 truncate text-left text-[11px] font-mono hover:underline ${isDark ? 'text-[#4ea3e0]' : 'text-[#006bbd]'}`}
                    onClick={() => copyPath(s.file, i)}
                    title={`${s.file} — ${t('clickToCopy')}`}
                    aria-label={`${t('copy')}: ${s.file}`}
                  >
                    {s.file}
                  </button>
                )}
                <div className="flex items-center gap-2 shrink-0">
                  {s.score != null && (
                    <span className={`text-[9px] ${isDark ? 'text-white/30' : 'text-gray-400'}`}>{s.score}</span>
                  )}
                  <button
                    type="button"
                    onClick={() => copyPath(s.url || s.file, i)}
                    className={`p-0.5 rounded ${isDark ? 'text-white/25 hover:text-white/70' : 'text-gray-300 hover:text-gray-600'}`}
                    aria-label={t('copy')}
                    title={t('copy')}
                  >
                    {copiedIdx === i ? <MdCheck size={11} /> : <MdContentCopy size={11} />}
                  </button>
                  {s.url ? (
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`p-0.5 rounded ${isDark ? 'text-white/25 hover:text-white/70' : 'text-gray-300 hover:text-gray-600'}`}
                      aria-label={`${t('openInBrowser')}: ${s.title || s.url}`}
                      title={t('openInBrowser')}
                    >
                      <MdOpenInNew size={11} />
                    </a>
                  ) : onOpenInBrowser && (
                    <button
                      type="button"
                      onClick={() => onOpenInBrowser(s.file, s.collection_id)}
                      className={`p-0.5 rounded ${isDark ? 'text-white/25 hover:text-white/70' : 'text-gray-300 hover:text-gray-600'}`}
                      aria-label={t('openInBrowser')}
                      title={t('openInKnowledgeBrowser')}
                    >
                      <MdLibraryBooks size={11} />
                    </button>
                  )}
                </div>
              </div>
              {(s.collection || s.page) && (
                <div className={`mt-0.5 flex flex-wrap gap-2 text-[9px] ${isDark ? 'text-white/30' : 'text-gray-400'}`}>
                  {s.collection && <span>{s.collection}</span>}
                  {s.page && <span>{t('pageAbbrev')} {s.page}</span>}
                </div>
              )}
              <pre className={`mt-1 text-[10px] whitespace-pre-wrap break-words max-h-24 overflow-y-auto font-mono ${isDark ? 'text-white/55' : 'text-gray-600'}`}>
                {highlight(s.snippet, terms)}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
