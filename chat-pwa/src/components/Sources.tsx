import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { useTheme } from '../theme/ThemeContext';
import { useI18n } from '../i18n/I18nContext';
import { MdContentCopy, MdCheck, MdLibraryBooks, MdOpenInNew, MdKeyboardArrowDown } from 'react-icons/md';
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

function safeExternalUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? value : null;
  } catch {
    return null;
  }
}

/** Web results have no place in the indexed knowledge base; only RAG hits do. */
function isLocalSource(source: Source): boolean {
  return source.kind !== 'web' && !source.provider;
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
  const copyResetTimerRef = useRef<number | null>(null);
  const { isDark } = useTheme();
  const { t } = useI18n();
  const sourcesId = useId();
  const terms = useMemo(() => extractTerms(query || ''), [query]);

  useEffect(() => () => {
    if (copyResetTimerRef.current !== null) window.clearTimeout(copyResetTimerRef.current);
  }, []);

  const hasSources = sources && sources.length > 0;
  const firstLocalSource = (sources || []).find(isLocalSource);
  const webProviders = [...new Set((sources || []).map((source) => source.provider).filter(Boolean))];
  if (!model && !hasSources) return null;

  const copyPath = async (path: string, idx: number) => {
    try {
      await navigator.clipboard.writeText(path);
      setCopiedIdx(idx);
      if (copyResetTimerRef.current !== null) window.clearTimeout(copyResetTimerRef.current);
      copyResetTimerRef.current = window.setTimeout(() => {
        setCopiedIdx((cur) => (cur === idx ? null : cur));
        copyResetTimerRef.current = null;
      }, 1400);
    } catch { /* ignore */ }
  };

  return (
    <div className="mt-2">
      {hasSources ? (
        <div className="tc-sources-card">
          <div className="flex items-center justify-between gap-2">
            <span className={`inline-flex items-center gap-1.5 text-sm font-semibold ${isDark ? 'text-white/80' : 'text-gray-700'}`}>
              <MdLibraryBooks size={14} className="text-[#2ac9b6]" aria-hidden="true" />
              {t('sources')}
            </span>
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              className={`inline-flex min-h-10 items-center gap-1 rounded-full border px-3 text-sm font-medium transition-colors ${isDark ? 'border-[#2ac9b6]/25 bg-[#2ac9b6]/10 text-[#2ac9b6] hover:border-[#2ac9b6]/45' : 'border-[#00756b]/25 bg-[#00756b]/10 text-[#00756b] hover:border-[#00756b]/45'}`}
              aria-expanded={open}
              aria-controls={sourcesId}
            >
              {sources!.length} {sources!.length === 1 ? t('source') : t('sources')}
              <MdKeyboardArrowDown size={13} className={`transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
            </button>
          </div>

          {/* Kept mounted so the disclosure animates both ways; inert while
              closed keeps the rows out of keyboard and screen-reader reach. */}
          <div
            id={sourcesId}
            inert={!open}
            aria-hidden={!open}
            className={`grid overflow-hidden transition-[grid-template-rows,opacity] duration-300 ease-out ${open ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}
          >
            <div className="min-h-0 overflow-hidden">
            {sources!.map((s, i) => {
              const externalUrl = safeExternalUrl(s.url);
              const meta = [s.collection, s.page ? `${t('pageAbbrev')} ${s.page}` : null].filter(Boolean).join(' · ');
              return (
                <div key={`${s.file}-${i}`} className="tc-sources-row">
                  <span className="tc-sources-icon" aria-hidden="true">
                    <MdLibraryBooks size={15} />
                  </span>
                  <div className="min-w-0">
                    {externalUrl ? (
                      <a
                        href={externalUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`block min-h-10 truncate text-sm font-semibold leading-10 hover:underline ${isDark ? 'text-white/85' : 'text-gray-800'}`}
                        title={externalUrl}
                      >
                        {s.title || externalUrl}
                      </a>
                    ) : (
                      <button
                        type="button"
                        className={`block min-h-10 max-w-full truncate text-left text-sm font-semibold leading-10 hover:underline ${isDark ? 'text-white/85' : 'text-gray-800'}`}
                        onClick={() => copyPath(s.file, i)}
                        title={`${s.file} | ${t('clickToCopy')}`}
                        aria-label={`${t('copy')}: ${s.file}`}
                      >
                        {s.file.split('/').pop() || s.file}
                      </button>
                    )}
                    <span className={`mt-0.5 block truncate font-mono text-xs ${isDark ? 'text-white/65' : 'text-gray-600'}`}>
                      {s.file}{meta ? ` · ${meta}` : ''}
                    </span>
                  </div>
                  <div className="tc-sources-actions flex items-center gap-1.5">
                    {s.score != null && <span className="tc-sources-score">{s.score}</span>}
                    <button
                      type="button"
                      onClick={() => copyPath(externalUrl || s.file, i)}
                      className={`inline-flex h-10 w-10 items-center justify-center rounded-lg transition-colors ${isDark ? 'text-white/65 hover:bg-white/[0.06] hover:text-white' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-800'}`}
                      aria-label={t('copy')}
                      title={t('copy')}
                    >
                      {copiedIdx === i ? <MdCheck size={16} /> : <MdContentCopy size={16} />}
                    </button>
                    {externalUrl ? (
                      <a
                        href={externalUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`inline-flex h-10 w-10 items-center justify-center rounded-lg transition-colors ${isDark ? 'text-white/65 hover:bg-white/[0.06] hover:text-white' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-800'}`}
                        aria-label={`${t('openInBrowser')}: ${s.title || externalUrl}`}
                        title={t('openInBrowser')}
                      >
                        <MdOpenInNew size={16} />
                      </a>
                    ) : onOpenInBrowser && isLocalSource(s) ? (
                      <button
                        type="button"
                        onClick={() => onOpenInBrowser(s.file, s.collection_id)}
                        className={`inline-flex h-10 w-10 items-center justify-center rounded-lg transition-colors ${isDark ? 'text-white/65 hover:bg-white/[0.06] hover:text-white' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-800'}`}
                        aria-label={t('openInBrowser')}
                        title={t('openInKnowledgeBrowser')}
                      >
                        <MdLibraryBooks size={16} />
                      </button>
                    ) : null}
                  </div>
                  <pre className={`col-span-3 mt-1 max-h-32 overflow-y-auto whitespace-pre-wrap break-words border-t pt-2 font-mono text-sm leading-relaxed ${isDark ? 'border-white/[0.06] text-white/80' : 'border-gray-200 text-gray-800'}`}>
                    {highlight(s.snippet, terms)}
                  </pre>
                </div>
              );
            })}
            </div>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
            {project && <span className={`text-xs ${isDark ? 'text-white/65' : 'text-gray-600'}`}>{project}</span>}
            {webProviders.length > 0 && <span className={`text-xs ${isDark ? 'text-white/65' : 'text-gray-600'}`}>{t('sourceWeb')}: {webProviders.join(', ')}</span>}
            {onOpenInBrowser && firstLocalSource && (
              <button
                type="button"
                onClick={() => onOpenInBrowser(firstLocalSource.file, firstLocalSource.collection_id)}
                className={`ml-auto inline-flex min-h-10 items-center gap-1 text-sm font-medium transition-colors ${isDark ? 'text-[#4ea3e0] hover:text-[#7cc0f0]' : 'text-[#005a9e] hover:text-[#004d8a]'}`}
              >
                <MdLibraryBooks size={12} aria-hidden="true" />
                {t('openInKnowledgeBrowser')}
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          {project && <span className={isDark ? 'text-white/65' : 'text-gray-600'}>{project}</span>}
          {webProviders.length > 0 && <span className={isDark ? 'text-white/65' : 'text-gray-600'}>{t('sourceWeb')}: {webProviders.join(', ')}</span>}
        </div>
      )}
    </div>
  );
}
