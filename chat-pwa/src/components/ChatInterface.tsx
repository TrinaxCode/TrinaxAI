import { memo, useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import { MdSend, MdStop, MdMenu, MdMic, MdVolumeUp, MdImage, MdClose, MdContentCopy, MdCheck, MdUploadFile, MdDownload, MdDescription, MdRefresh, MdEdit, MdScience, MdKeyboardArrowDown } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import ToggleSwitch from './ToggleSwitch';
import Sources from './Sources';
import { useToast } from './Toast';
import type { ChatMessage, ChatEngine, Collection, ChatDocumentAttachment } from '../lib/api';
import { extractDocumentText, getCollections, getIndexJob, indexableFilesFrom, nextActiveCollections, normalizeActiveCollections, prepareImageForVision, runResearch, startFolderIndex, getMemorySummary } from '../lib/api';
import { getPreferredUserName, rememberFromMessage } from '../lib/userProfile';
import { useStreamChat } from '../hooks/useStreamChat';
import { detectBackendVoice, detectSpeechSynthesis, speakBackend, transcribeAudio } from '../services/voice';
import { startAudioRecorder } from '../utils/audioRecorder';
import { onSharedStateUpdated } from '../lib/sharedState';
import { getChatAttachmentUrl, storeChatAttachment } from '../lib/chatAttachments';

interface ChatInterfaceProps {
  messages: ChatMessage[];
  engine: ChatEngine;
  onMessagesChange: (messages: ChatMessage[]) => void;
  onEngineChange: (engine: ChatEngine) => void;
  onMenuToggle: () => void;
  sidebarOpen: boolean;
  onNavigate?: (page: 'settings' | 'indexing' | 'browser' | 'memory' | 'docs') => void;
  onRequestExport?: (kind: 'markdown') => void;
  folderContext?: Array<{ title: string; messages: ChatMessage[] }>;
}

interface AttachedDocument {
  name: string;
  size: number;
  content: string;
  file: File;
  truncated: boolean;
}

const DOC_MAX_CHARS = 120_000;
const DOC_TOTAL_MAX_CHARS = 220_000;

function textPreviewDocument(text: string): string {
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  return `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{margin:0;padding:16px;background:#fff;color:#202124;font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap;overflow-wrap:anywhere}</style></head><body>${escaped}</body></html>`;
}

function formatAttachmentSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Built-in slash commands. Each is identified by its `name` and a behaviour kind.
 * - navigate_* — switch the page and stop (don't send the message).
 * - deep_research — call /v1/research with the remainder text.
 * - summarize — call regular chat completion summarising the conversation.
 * - export_* — trigger a download via the parent's onRequestExport callback.
 */
type BuiltinKind =
  | 'navigate_settings' | 'navigate_indexing' | 'navigate_browser' | 'navigate_memory' | 'navigate_docs'
  | 'deep_research' | 'summarize' | 'export_markdown' | 'noop';

interface BuiltinCommand { name: string; text: string; builtin: true; kind: BuiltinKind; hint: string }

const BUILTIN_COMMANDS: BuiltinCommand[] = [
  { name: 'index',     text: '',                builtin: true, kind: 'navigate_indexing', hint: 'Ajustes → Indexar carpeta' },
  { name: 'browse',    text: '',                builtin: true, kind: 'navigate_browser',  hint: 'Knowledge Browser' },
  { name: 'memory',    text: '',                builtin: true, kind: 'navigate_memory',  hint: 'Notas persistentes' },
  { name: 'watch',     text: '',                builtin: true, kind: 'navigate_indexing', hint: 'Watcher de archivos' },
  { name: 'research',  text: '',                builtin: true, kind: 'deep_research',    hint: 'Multi-pass deep research' },
  { name: 'summarize', text: '',                builtin: true, kind: 'summarize',        hint: 'Resumir conversación' },
  { name: 'export',    text: '',                builtin: true, kind: 'export_markdown',  hint: 'Exportar como Markdown' },
  { name: 'sources',   text: '',                builtin: true, kind: 'navigate_browser',  hint: 'Ver fuentes indexadas' },
];

function getBuiltinHint(name: string, lang: 'es' | 'en'): string {
  const hints: Record<string, { es: string; en: string }> = {
    index:     { es: 'Ajustes → Indexar carpeta', en: 'Settings → Index folder' },
    browse:    { es: 'Navegador de conocimiento', en: 'Knowledge Browser' },
    memory:    { es: 'Notas persistentes', en: 'Persistent notes' },
    watch:     { es: 'Watcher de archivos', en: 'File watcher' },
    research:  { es: 'Investigación profunda', en: 'Multi-pass deep research' },
    summarize: { es: 'Resumir conversación', en: 'Summarize conversation' },
    resumir:   { es: 'Resumir conversación', en: 'Summarize conversation' },
    export:    { es: 'Descargar chat (MD, PDF, Word)', en: 'Download chat (MD, PDF, Word)' },
    sources:   { es: 'Ver fuentes indexadas', en: 'View indexed sources' },
  };
  return hints[name]?.[lang] ?? '';
}

function localizedBuiltins(lang: 'es' | 'en'): BuiltinCommand[] {
  return BUILTIN_COMMANDS.map((command) => command.kind === 'summarize'
    ? { ...command, name: lang === 'es' ? 'resumir' : 'summarize' }
    : command);
}

function findBuiltin(name: string, lang: 'es' | 'en'): BuiltinCommand | undefined {
  const lc = name.toLowerCase();
  return localizedBuiltins(lang).find((b) => b.name === lc);
}

// ── Quick-start chip pool (28 options, 2 randomly shown per new chat) ──
interface QuickChipDef {
  labelKey: string;
  icon: string;
  kind: 'navigate' | 'slash' | 'prompt' | 'callMode' | 'pickImage' | 'pickFile' | 'toggleResearch';
  page?: string;
  command?: string;
  promptKey?: string;
}

const QUICK_CHIP_POOL: QuickChipDef[] = [
  { labelKey: 'quickChipIndex',        icon: '📂', kind: 'navigate', page: 'indexing' },
  { labelKey: 'quickChipExplain',      icon: '💡', kind: 'prompt',   promptKey: 'quickChipExplainPrompt' },
  { labelKey: 'quickChipSummarize',    icon: '📝', kind: 'slash',    command: '/summarize' },
  { labelKey: 'quickChipResearch',     icon: '🔬', kind: 'slash',    command: '/research ' },
  { labelKey: 'quickChipFindBugs',     icon: '🐛', kind: 'prompt',   promptKey: 'quickChipFindBugsPrompt' },
  { labelKey: 'quickChipGenerateTests',icon: '🧪', kind: 'prompt',   promptKey: 'quickChipGenerateTestsPrompt' },
  { labelKey: 'quickChipWriteDocs',    icon: '📄', kind: 'prompt',   promptKey: 'quickChipWriteDocsPrompt' },
  { labelKey: 'quickChipRefactor',     icon: '🔄', kind: 'prompt',   promptKey: 'quickChipRefactorPrompt' },
  { labelKey: 'quickChipOptimize',     icon: '⚡', kind: 'prompt',   promptKey: 'quickChipOptimizePrompt' },
  { labelKey: 'quickChipCodeReview',   icon: '🔍', kind: 'prompt',   promptKey: 'quickChipCodeReviewPrompt' },
  { labelKey: 'quickChipTranslate',    icon: '🌐', kind: 'prompt',   promptKey: 'quickChipTranslatePrompt' },
  { labelKey: 'quickChipFixErrors',    icon: '🛠️', kind: 'prompt',   promptKey: 'quickChipFixErrorsPrompt' },
  { labelKey: 'quickChipDatabase',     icon: '🗄️', kind: 'prompt',   promptKey: 'quickChipDatabasePrompt' },
  { labelKey: 'quickChipSetupProject', icon: '🚀', kind: 'prompt',   promptKey: 'quickChipSetupProjectPrompt' },
  { labelKey: 'quickChipSnippet',      icon: '📋', kind: 'prompt',   promptKey: 'quickChipSnippetPrompt' },
  { labelKey: 'quickChipUI',           icon: '🎨', kind: 'prompt',   promptKey: 'quickChipUIPrompt' },
  { labelKey: 'quickChipSecurity',     icon: '🔒', kind: 'prompt',   promptKey: 'quickChipSecurityPrompt' },
  { labelKey: 'quickChipAnalyze',      icon: '📊', kind: 'prompt',   promptKey: 'quickChipAnalyzePrompt' },
  { labelKey: 'quickChipApiEndpoint',  icon: '🔌', kind: 'prompt',   promptKey: 'quickChipApiEndpointPrompt' },
  { labelKey: 'quickChipDeploy',       icon: '🚢', kind: 'prompt',   promptKey: 'quickChipDeployPrompt' },
  { labelKey: 'quickChipDebug',        icon: '🐞', kind: 'prompt',   promptKey: 'quickChipDebugPrompt' },
  { labelKey: 'quickChipGitCommit',    icon: '💬', kind: 'prompt',   promptKey: 'quickChipGitCommitPrompt' },
  // ── Tool chips (TrinaxAI features) ──
  { labelKey: 'quickChipCallMode',          icon: '📞', kind: 'callMode' },
  { labelKey: 'quickChipReviewImage',       icon: '🖼️', kind: 'pickImage',   promptKey: 'quickChipReviewImagePrompt' },
  { labelKey: 'quickChipSummarizeFile',     icon: '📎', kind: 'pickFile',    promptKey: 'quickChipSummarizeFilePrompt' },
  { labelKey: 'quickChipWhatRemember',      icon: '🧠', kind: 'prompt',      promptKey: 'quickChipWhatRememberPrompt' },
  { labelKey: 'quickChipBrowseKnowledge',   icon: '📚', kind: 'navigate',    page: 'browser' },
  { labelKey: 'quickChipExportChat',        icon: '📥', kind: 'slash',       command: '/export' },
  { labelKey: 'quickChipDeepResearchToggle',icon: '🔭', kind: 'toggleResearch' },
];

const PLAIN_URL_RE = /(^|[\s(])((?:https?:\/\/|www\.)[^\s<>()]+)(?=[\s)]|$)/g;

/** Trailing punctuation that should NOT be part of a URL. */
const TRAILING_PUNCT_RE = /[.,;:!?'"»]+$/;

function linkifyPlainUrls(text: string): string {
  return text
    .split(/(```[\s\S]*?```|`[^`]*`)/g)
    .map((part) => {
      if (part.startsWith('`')) return part;
      return part.replace(PLAIN_URL_RE, (match, prefix: string, url: string, offset: number, source: string) => {
        if (prefix === '(' && source[offset - 1] === ']') return match;
        // Strip trailing sentence punctuation so it isn't included in the link
        let cleanUrl = url;
        let trailing = '';
        const punctMatch = cleanUrl.match(TRAILING_PUNCT_RE);
        if (punctMatch) {
          trailing = punctMatch[0];
          cleanUrl = cleanUrl.slice(0, -trailing.length);
        }
        const href = cleanUrl.startsWith('www.') ? `https://${cleanUrl}` : cleanUrl;
        return `${prefix}[${cleanUrl}](${href})${trailing}`;
      });
    })
    .join('');
}

const MarkdownContent = memo(function MarkdownContent({ text, isDark }: { text: string; isDark: boolean }) {
  return (
    <div className={`chat-markdown prose prose-sm min-w-0 max-w-full break-words [overflow-wrap:anywhere] ${isDark ? 'prose-invert' : ''}`}>
      <ReactMarkdown
        rehypePlugins={[rehypeSanitize]}
        components={{
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className={`underline decoration-1 underline-offset-2 ${
                isDark
                  ? 'text-blue-400 hover:text-blue-300'
                  : 'text-blue-600 hover:text-blue-700'
              }`}
            >
              {children}
            </a>
          ),
        }}
      >
        {linkifyPlainUrls(text)}
      </ReactMarkdown>
    </div>
  );
});

export default function ChatInterface({
  messages,
  engine,
  onMessagesChange,
  onEngineChange,
  onMenuToggle,
  sidebarOpen,
  onNavigate,
  onRequestExport,
  folderContext = [],
}: ChatInterfaceProps) {
  const { t, lang } = useI18n();
  const { isDark } = useTheme();
  const voiceLang = lang === 'en' ? 'en-US' : 'es-ES';
  const toast = useToast();
  const [input, setInput] = useState('');
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editingText, setEditingText] = useState('');
  const { streaming, streamedText, sendMessage, abort, wasAborted } = useStreamChat();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const messagesRef = useRef<HTMLDivElement>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const showScrollButtonRef = useRef(false);
  const autoScrollUntilRef = useRef(0);
  const scrollButtonTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [userDisplayName, setUserDisplayName] = useState(() => getPreferredUserName(lang));
  const [collections, setCollections] = useState<Collection[]>([]);
  const [activeCollectionIds, setActiveCollectionIds] = useState<string[]>(() => {
    try {
      const parsed = JSON.parse(localStorage.getItem('tc-active-collections') || '["default"]');
      return Array.isArray(parsed) && parsed.every((v) => typeof v === 'string') && parsed.length
        ? normalizeActiveCollections(parsed)
        : ['default'];
    } catch {
      return ['default'];
    }
  });
  const [docUploadStatus, setDocUploadStatus] = useState('');
  const [docConvertProgress, setDocConvertProgress] = useState<{ file: string; progress: number } | null>(null);
  const [attachedDocs, setAttachedDocs] = useState<AttachedDocument[]>([]);
  const [docIndexCollectionId, setDocIndexCollectionId] = useState(() => activeCollectionIds[0] || 'default');
  const docInputRef = useRef<HTMLInputElement>(null);

  const [slashOpen, setSlashOpen] = useState(false);
  const [slashFilter, setSlashFilter] = useState('');
  const [exportMenuOpen, setExportMenuOpen] = useState(false);

  const customPrompts = useRef<Array<{
    name: string;
    text: string;
    builtin?: boolean;
    kind?: BuiltinKind;
  }>>([]);
  const reloadLocalProfile = useCallback(() => {
    const readPrompts = (key: string) => {
      try {
        const parsed = JSON.parse(localStorage.getItem(key) || '[]');
        return Array.isArray(parsed) ? parsed : [];
      } catch {
        return [];
      }
    };
    const shared = readPrompts('tc-prompts');
    const legacy = shared.length ? [] : [...readPrompts('tc-ollama-prompts'), ...readPrompts('tc-rag-prompts')];
    customPrompts.current = [...localizedBuiltins(lang), ...shared, ...legacy]
      .filter((p: any) => p?.name && p.name !== 'system')
      .map((p: any) => ({
        name: String(p.name),
        text: String(p.text || ''),
        builtin: Boolean(p.builtin),
        kind: p.kind as BuiltinKind | undefined,
      }));
    const nextName = getPreferredUserName(lang);
    setUserDisplayName((current) => (current === nextName ? current : nextName));
  }, [lang]);

  useEffect(() => {
    reloadLocalProfile();
    return onSharedStateUpdated(reloadLocalProfile);
  }, [reloadLocalProfile]);

  useEffect(() => {
    localStorage.setItem('tc-active-collections', JSON.stringify(activeCollectionIds));
  }, [activeCollectionIds]);

  useEffect(() => {
    if (collections.length && !collections.some((item) => item.id === docIndexCollectionId)) {
      setDocIndexCollectionId(collections[0]?.id || 'default');
    }
  }, [collections, docIndexCollectionId]);

  useEffect(() => {
    const controller = new AbortController();
    getCollections(controller.signal)
      .then((items) => {
        const next = items.length ? items : [{ id: 'default', name: 'General', created_at: Date.now() / 1000, updated_at: Date.now() / 1000 }];
        setCollections(next);
        const valid = new Set(next.map((item) => item.id));
        setActiveCollectionIds((prev) => {
          return normalizeActiveCollections(prev, valid);
        });
      })
      .catch(() => {
        setCollections([{ id: 'default', name: 'General', created_at: Date.now() / 1000, updated_at: Date.now() / 1000 }]);
      });
    return () => controller.abort();
  }, []);

  const [motdIndex, setMotdIndex] = useState(0);

  const phrases = [t('motd1'), t('motd2'), t('motd3'), t('motd4'), t('motd5'), t('motd6'), t('motd7'), t('motd8'), t('motd9'), t('motd10')];

  // Rotate the motivational message every 4 seconds
  useEffect(() => {
    if (messages.length > 0 || streaming) return undefined;
    const id = setInterval(() => {
      setMotdIndex((prev) => (prev + 1) % phrases.length);
    }, 4000);
    return () => clearInterval(id);
  }, [messages.length, streaming, phrases.length]);

  const motd = phrases[motdIndex];

  // ── Random quick-start chips (2 per new chat) ──
  // Uses a ref updated in render-phase so chips are immediately visible.
  // Regenerates when transitioning from non-empty → empty chat.
  const chipDefsRef = useRef<QuickChipDef[]>([]);
  const prevMessageCount = useRef(messages.length);

  if (messages.length === 0 && !streaming) {
    if (prevMessageCount.current > 0 || chipDefsRef.current.length === 0) {
      const shuffled = [...QUICK_CHIP_POOL].sort(() => Math.random() - 0.5);
      chipDefsRef.current = shuffled.slice(0, 2);
    }
  }
  prevMessageCount.current = messages.length;

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const val = e.target.value;
      setInput(val);
      const el = e.target;
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
      if (val.startsWith('/') && !val.includes(' ')) {
        setSlashOpen(true);
        setSlashFilter(val.slice(1).toLowerCase());
      } else {
        setSlashOpen(false);
      }
    },
    [],
  );

  const resetInputHeight = useCallback(() => {
    requestAnimationFrame(() => {
      if (inputRef.current) inputRef.current.style.height = '40px';
    });
  }, []);

  const updateScrollState = useCallback(() => {
    const el = messagesRef.current;
    if (!el) return;
    const scrollable = el.scrollHeight > el.clientHeight + 16;
    // While auto-scrolling, keep the button hidden.
    if (Date.now() < autoScrollUntilRef.current) {
      if (showScrollButtonRef.current) {
        showScrollButtonRef.current = false;
        setShowScrollButton(false);
      }
      return;
    }
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    const shouldShow = scrollable && distance > 200;

    // Always cancel any pending show timer when we shouldn't show.
    if (!shouldShow) {
      if (scrollButtonTimerRef.current) {
        clearTimeout(scrollButtonTimerRef.current);
        scrollButtonTimerRef.current = null;
      }
    }

    if (!shouldShow && showScrollButtonRef.current) {
      showScrollButtonRef.current = false;
      setShowScrollButton(false);
      return;
    }

    if (shouldShow && !showScrollButtonRef.current && !scrollButtonTimerRef.current) {
      scrollButtonTimerRef.current = setTimeout(() => {
        scrollButtonTimerRef.current = null;
        // Re-check distance at fire time — user may have scrolled back down.
        const el2 = messagesRef.current;
        if (!el2) return;
        const d2 = el2.scrollHeight - el2.scrollTop - el2.clientHeight;
        if (d2 <= 200) return;
        showScrollButtonRef.current = true;
        setShowScrollButton(true);
      }, 250);
    }
  }, []);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    const el = messagesRef.current;
    if (!el) return;
    autoScrollUntilRef.current = Date.now() + (behavior === 'smooth' ? 750 : 120);
    el.scrollTo({ top: el.scrollHeight, behavior });
    showScrollButtonRef.current = false;
    setShowScrollButton(false);
    if (scrollButtonTimerRef.current) {
      clearTimeout(scrollButtonTimerRef.current);
      scrollButtonTimerRef.current = null;
    }
    window.setTimeout(() => {
      autoScrollUntilRef.current = 0;
      updateScrollState();
    }, behavior === 'smooth' ? 780 : 140);
  }, [updateScrollState]);

  useEffect(() => {
    requestAnimationFrame(updateScrollState);
  }, [messages.length, streamedText, streaming, updateScrollState]);

  const copyMessage = useCallback(async (text: string, key: string) => {
    if (!text.trim()) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      window.setTimeout(() => setCopiedKey((current) => current === key ? null : current), 1400);
    } catch {
      // Clipboard permissions vary by browser; failing silently keeps the chat calm.
    }
  }, []);

  const visibleMessageContent = useCallback((text: string) => text.trim(), []);
  const messageDisplayContent = useCallback((msg: ChatMessage) => (
    msg.displayContent ?? (msg.content || (msg.image ? '[image]' : ''))
  ).trim(), []);

function getLastUserText(messages: ChatMessage[], beforeMsg?: ChatMessage): string {
  const upto = beforeMsg ? messages.slice(0, messages.indexOf(beforeMsg) + 1) : messages;
  for (let i = upto.length - 1; i >= 0; i--) {
    if (upto[i].role === 'user') return upto[i].displayContent ?? upto[i].content;
  }
  return '';
}

  const conversationMarkdown = useCallback(() => {
    const lines = ['# TrinaxAI Conversation', ''];
    for (const msg of messages) {
      lines.push(`## ${msg.role === 'user' ? 'User' : 'TrinaxAI'}`, '', messageDisplayContent(msg), '');
      if (msg.documentAttachments?.length) {
        lines.push('Attachments:', ...msg.documentAttachments.map((doc) => `- ${doc.name}`), '');
      }
      if (msg.sources?.length) {
        lines.push('Sources:', ...msg.sources.map((source) => `- ${source.file}${source.page ? ` p. ${source.page}` : ''}${source.collection ? ` (${source.collection})` : ''}`), '');
      }
    }
    return lines.join('\n');
  }, [messages, messageDisplayContent]);

  // Robust blob download: the anchor MUST be in the DOM for the click to fire
  // in Firefox/Safari, and the object URL must outlive the click (revoking it
  // synchronously cancels the download). Defer revocation to the next tick.
  const triggerDownload = useCallback((blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.rel = 'noopener';
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 1000);
  }, []);

  const exportMarkdown = useCallback(() => {
    const blob = new Blob([conversationMarkdown()], { type: 'text/markdown;charset=utf-8' });
    triggerDownload(blob, `trinaxai-chat-${new Date().toISOString().slice(0, 10)}.md`);
  }, [conversationMarkdown, triggerDownload]);

  const exportHtmlBody = useCallback(() => {
    const escapeHtml = (value: string) => value
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
    return messages.map((msg) => `
      <section>
        <h2>${msg.role === 'user' ? 'User' : 'TrinaxAI'}</h2>
        <pre>${escapeHtml(messageDisplayContent(msg))}${msg.documentAttachments?.length ? `\n\nAttachments:\n${msg.documentAttachments.map((doc) => `- ${escapeHtml(doc.name)}`).join('\n')}` : ''}</pre>
      </section>
    `).join('');
  }, [messages, messageDisplayContent]);

  const exportPdf = useCallback(() => {
    const win = window.open('', '_blank');
    if (!win) {
      toast.toast(t('exportPdfPopupBlocked'), 'error');
      return;
    }
    win.document.write(`<!doctype html><html><head><title>TrinaxAI Conversation</title><style>
      body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:32px;color:#111;line-height:1.5}
      h1{font-size:22px}h2{font-size:14px;margin-top:24px;color:#006bbd}
      pre{white-space:pre-wrap;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
    </style></head><body><h1>TrinaxAI Conversation</h1>${exportHtmlBody()}</body></html>`);
    win.document.close();
    win.focus();
    win.print();
  }, [exportHtmlBody, toast, t]);

  const exportWord = useCallback(() => {
    const html = `<!doctype html><html><head><meta charset="utf-8"><title>TrinaxAI Conversation</title><style>
      body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:32px;color:#111;line-height:1.5}
      h1{font-size:22px}h2{font-size:14px;margin-top:24px;color:#006bbd}
      pre{white-space:pre-wrap;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
    </style></head><body><h1>TrinaxAI Conversation</h1>${exportHtmlBody()}</body></html>`;
    const blob = new Blob([html], { type: 'application/msword;charset=utf-8' });
    triggerDownload(blob, `trinaxai-chat-${new Date().toISOString().slice(0, 10)}.doc`);
  }, [exportHtmlBody, triggerDownload]);

  const activeCollectionsForRequest = useMemo(
    () => normalizeActiveCollections(activeCollectionIds),
    [activeCollectionIds],
  );

  const toggleCollection = useCallback((id: string) => {
    setActiveCollectionIds((prev) => nextActiveCollections(prev, id));
  }, []);

  const indexAttachedDocs = useCallback(async () => {
    if (!attachedDocs.length) return;
    const files = attachedDocs.map((doc) => doc.file);
    const collectionName = collections.find((item) => item.id === docIndexCollectionId)?.name || 'General';
    setDocUploadStatus(t('chatUploadStarting').replace('{collection}', collectionName));
    try {
      const started = await startFolderIndex(files, { collectionId: docIndexCollectionId });
      if (!started.job_id) {
        setDocUploadStatus(t('chatUploadQueued').replace('{count}', String(started.saved)));
        return;
      }
      let done = false;
      while (!done) {
        await new Promise((resolve) => setTimeout(resolve, 1100));
        const job = await getIndexJob(started.job_id);
        if (job.status === 'completed') {
          setDocUploadStatus(t('chatUploadDone').replace('{count}', String(job.saved)));
          done = true;
        } else if (job.status === 'failed') {
          setDocUploadStatus(job.error || t('chatUploadFailed'));
          done = true;
        } else if (job.status === 'cancelled') {
          setDocUploadStatus(t('indexCancelled'));
          done = true;
        } else {
          setDocUploadStatus(`${t('indexing')} ${job.progress}%`);
        }
      }
      window.setTimeout(() => setDocUploadStatus(''), 4500);
    } catch (err: unknown) {
      setDocUploadStatus(err instanceof Error ? err.message.slice(0, 180) : t('chatUploadFailed'));
    }
  }, [attachedDocs, collections, docIndexCollectionId, t]);

  const onPickDocs = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files ?? []);
    e.target.value = '';
    if (!selected.length) return;
    const files = indexableFilesFrom(selected);
    if (!files.length) {
      setDocUploadStatus(t('chatUploadNoFiles'));
      return;
    }
    try {
      let remaining = DOC_TOTAL_MAX_CHARS;
      const docs: AttachedDocument[] = [];
      const selectedDocs = files.slice(0, 5);
      for (let index = 0; index < selectedDocs.length; index += 1) {
        const file = selectedDocs[index];
        setDocUploadStatus(t('chatDocConverting').replace('{file}', file.name));
        setDocConvertProgress({ file: file.name, progress: Math.max(1, Math.round((index / selectedDocs.length) * 100)) });
        const extracted = await extractDocumentText(file, {
          onUploadProgress: (progress) => {
            const current = Math.min(95, Math.round(((index * 100) + progress) / selectedDocs.length));
            setDocConvertProgress({ file: file.name, progress: current });
            if (progress >= 70) {
              setDocUploadStatus(t('chatDocConverting').replace('{file}', file.name));
            }
          },
        });
        const raw = extracted.text;
        const room = Math.max(0, remaining);
        const content = raw.slice(0, Math.min(DOC_MAX_CHARS, room));
        remaining -= content.length;
        docs.push({
          name: file.name,
          size: file.size,
          content,
          file,
          truncated: extracted.truncated || content.length < raw.length,
        });
        if (remaining <= 0) break;
      }
      setDocConvertProgress(null);
      setAttachedDocs(docs);
      setDocUploadStatus(t('chatDocsAttached').replace('{count}', String(docs.length)));
    } catch (err: unknown) {
      setDocConvertProgress(null);
      setDocUploadStatus(err instanceof Error ? err.message.slice(0, 180) : t('chatDocReadFailed'));
    }
  }, [t]);

  // ── Voz (estado) ──
  const [listening, setListening] = useState(false);
  const [callMode, setCallMode] = useState(false);
  const recognitionRef = useRef<any>(null);
  const callModeRef = useRef(false);
  const startVoiceRef = useRef<(continuous: boolean) => void>(() => {});
  const handleSendTextRef = useRef<(raw: string, opts?: { viaVoice?: boolean; continueCall?: boolean }) => Promise<void>>(async () => {});
  const ttsActiveKeyRef = useRef<string | null>(null);
  const [ttsActiveKey, setTtsActiveKey] = useState<string | null>(null);
  const [ttsSpeaking, setTtsSpeaking] = useState(false);
  const [voiceVersion, setVoiceVersion] = useState(0);
  const ttsTailRef = useRef('');
  const ttsSpeakingRef = useRef(false);
  const ttsEndRef = useRef<(() => void) | null>(null);
  const ttsPumpRef = useRef<number | null>(null);
  const voiceToastAtRef = useRef(0);
  const flushVoiceTtsRef = useRef<(force?: boolean, onDone?: () => void) => void>(() => {});
  const ttsCancellingRef = useRef(false);
  const wakeLockRef = useRef<WakeLockSentinel | null>(null);
  const backendRecorderStopRef = useRef<(() => void) | null>(null);
  const voiceSupported = typeof window !== 'undefined' &&
    !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
  const secureVoiceContext = typeof window !== 'undefined' &&
    (window.isSecureContext || ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname));

  const showVoiceToast = useCallback((message: string, type: 'warning' | 'error' = 'warning') => {
    const now = Date.now();
    if (now - voiceToastAtRef.current < 1800) return;
    voiceToastAtRef.current = now;
    toast.toast(message, type);
  }, [toast]);

  useEffect(() => {
    callModeRef.current = callMode;
  }, [callMode]);

  // Wake lock helpers / helpers de wake lock
  const requestWakeLock = useCallback(async () => {
    try {
      wakeLockRef.current = await (navigator as any).wakeLock?.request?.('screen');
    } catch { /* ignore */ }
  }, []);

  const releaseWakeLock = useCallback(() => {
    wakeLockRef.current?.release().catch(() => {});
    wakeLockRef.current = null;
  }, []);

  // Backend voice capture / captura de voz por backend
  const startBackendVoiceCapture = useCallback(async (continuous: boolean) => {
    if (!detectBackendVoice()) {
      showVoiceToast(t('voiceRecognitionUnsupported'), 'warning');
      setCallMode(false);
      setListening(false);
      return;
    }
    if (streaming) return;
    setListening(true);
    try {
      const recorder = await startAudioRecorder({
        onSilence: async (blob) => {
          if (!callModeRef.current) return;
          setListening(false);
          backendRecorderStopRef.current = null;
          try {
            const text = await transcribeAudio(blob, voiceLang);
            if (text.trim()) {
              handleSendTextRef.current(text.trim(), { viaVoice: true, continueCall: continuous });
            } else if (continuous && callModeRef.current) {
              window.setTimeout(() => startBackendVoiceCapture(true), 500);
            }
          } catch {
            showVoiceToast(t('voiceRecognitionFailed'), 'warning');
            if (continuous && callModeRef.current) {
              window.setTimeout(() => startBackendVoiceCapture(true), 900);
            }
          }
        },
        onError: () => {
          setListening(false);
          backendRecorderStopRef.current = null;
          showVoiceToast(t('voiceRecognitionFailed'), 'warning');
          setCallMode(false);
        },
      }, 1500);
      backendRecorderStopRef.current = recorder.stop;
    } catch {
      setListening(false);
      showVoiceToast(t('voiceMicPermissionDenied'), 'error');
      setCallMode(false);
    }
  }, [showVoiceToast, streaming, t, voiceLang]);

  // ── TTS (leer respuestas en voz alta) ──
  const ttsSupported = typeof window !== 'undefined' && 'speechSynthesis' in window;
  useEffect(() => {
    if (!ttsSupported) return undefined;
    const refreshVoices = () => setVoiceVersion((value) => value + 1);
    window.speechSynthesis.getVoices();
    window.speechSynthesis.addEventListener?.('voiceschanged', refreshVoices);
    const id = window.setTimeout(refreshVoices, 300);
    return () => {
      window.clearTimeout(id);
      window.speechSynthesis.removeEventListener?.('voiceschanged', refreshVoices);
    };
  }, [ttsSupported]);

  const pickVoice = useCallback(() => {
    if (!ttsSupported) return undefined;
    const voices = window.speechSynthesis.getVoices();
    const baseLang = voiceLang.slice(0, 2);
    return voices.find((vo) => vo.lang === voiceLang)
      || voices.find((vo) => vo.lang.toLowerCase().startsWith(baseLang))
      || voices[0];
  }, [ttsSupported, voiceLang, voiceVersion]);

  const assistantErrorMessage = useCallback((err: unknown) => {
    if (err instanceof Error && err.message && err.message !== 'TRINAXAI_SILENT_ABORT') {
      return err.message.length > 700 ? `${err.message.slice(0, 700)}...` : err.message;
    }
    return t('systemOffline');
  }, [t]);

  const splitSpeech = useCallback((text: string) => {
    const chunks: string[] = [];
    let rest = text.trim();
    while (rest.length > 0) {
      if (rest.length <= 220) {
        chunks.push(rest);
        break;
      }
      const cut = Math.max(
        rest.lastIndexOf('. ', 220),
        rest.lastIndexOf('? ', 220),
        rest.lastIndexOf('! ', 220),
        rest.lastIndexOf(', ', 180),
        180,
      );
      chunks.push(rest.slice(0, cut + 1).trim());
      rest = rest.slice(cut + 1).trim();
    }
    return chunks;
  }, []);

  const clearTtsState = useCallback(() => {
    ttsActiveKeyRef.current = null;
    setTtsActiveKey(null);
    ttsTailRef.current = '';
    ttsSpeakingRef.current = false;
    setTtsSpeaking(false);
    ttsEndRef.current = null;
  }, []);

  const stopTtsPump = useCallback(() => {
    if (ttsPumpRef.current != null) {
      window.clearInterval(ttsPumpRef.current);
      ttsPumpRef.current = null;
    }
  }, []);

  const startTtsPump = useCallback(() => {
    stopTtsPump();
    ttsPumpRef.current = window.setInterval(() => {
      if (!ttsSupported || !ttsSpeakingRef.current) {
        stopTtsPump();
        return;
      }
      window.speechSynthesis.resume();
    }, 7000);
  }, [stopTtsPump, ttsSupported]);

  useEffect(() => () => stopTtsPump(), [stopTtsPump]);

  const stopSpeak = useCallback(() => {
    ttsCancellingRef.current = true;
    if (ttsSupported) window.speechSynthesis.cancel();
    stopTtsPump();
    clearTtsState();
    // Reset the cancelling flag after pending error events fire.
    window.setTimeout(() => { ttsCancellingRef.current = false; }, 200);
  }, [clearTtsState, stopTtsPump, ttsSupported]);

  const unlockSpeech = useCallback(() => {
    if (!ttsSupported) return;
    try {
      window.speechSynthesis.resume();
      const u = new SpeechSynthesisUtterance('.');
      u.lang = voiceLang;
      u.volume = 0.01;
      u.rate = 1.2;
      window.speechSynthesis.speak(u);
      window.setTimeout(() => {
        if (!ttsSpeakingRef.current) window.speechSynthesis.cancel();
        window.speechSynthesis.resume();
      }, 120);
    } catch {
      showVoiceToast(t('ttsUnavailable'));
    }
  }, [showVoiceToast, t, ttsSupported, voiceLang]);

  const speak = useCallback((text: string, onDone?: () => void, key?: string) => {
    if (!ttsSupported || !text) {
      onDone?.();
      return;
    }
    if (key && ttsActiveKeyRef.current === key && (window.speechSynthesis.speaking || window.speechSynthesis.pending)) {
      stopSpeak();
      return;
    }
    ttsCancellingRef.current = false;
    const clean = text
      .replace(/```[\s\S]*?```/g, t('ttsCodeBlockReplacement'))
      .replace(/`[^`]*`/g, '')
      .replace(/\[(.*?)\]\(.*?\)/g, '$1')
      .replace(/[#*_>~|]/g, '')
      .replace(/\s+/g, ' ')
      .trim();
    window.speechSynthesis.cancel();
    window.speechSynthesis.resume();
    ttsActiveKeyRef.current = key ?? null;
    setTtsActiveKey(key ?? null);
    ttsSpeakingRef.current = true;
    setTtsSpeaking(true);
    startTtsPump();
    const v = pickVoice();
    const parts = splitSpeech(clean);
    if (parts.length === 0) {
      stopTtsPump();
      clearTtsState();
      onDone?.();
      return;
    }
    parts.forEach((part, index) => {
      const u = new SpeechSynthesisUtterance(part);
      u.lang = voiceLang;
      u.rate = 1.04;
      u.pitch = 1;
      u.volume = 1;
      if (v) u.voice = v;
      if (index === parts.length - 1) {
        u.onend = () => { stopTtsPump(); clearTtsState(); onDone?.(); };
      }
      u.onerror = () => {
        stopTtsPump();
        clearTtsState();
        if (!ttsCancellingRef.current) showVoiceToast(t('ttsUnavailable'));
        onDone?.();
      };
      try {
        window.speechSynthesis.speak(u);
      } catch {
        stopTtsPump();
        clearTtsState();
        if (!ttsCancellingRef.current) showVoiceToast(t('ttsUnavailable'));
        onDone?.();
      }
    });
  }, [clearTtsState, pickVoice, showVoiceToast, splitSpeech, startTtsPump, stopSpeak, stopTtsPump, t, ttsSupported, voiceLang]);

  const speakWithFallback = useCallback((text: string, onDone?: () => void, key?: string) => {
    if (detectSpeechSynthesis()) {
      speak(text, onDone, key);
    } else {
      setTtsSpeaking(true);
      ttsSpeakingRef.current = true;
      speakBackend({
        text,
        lang: voiceLang,
        onEnded: () => {
          setTtsSpeaking(false);
          ttsSpeakingRef.current = false;
          onDone?.();
        },
        onError: () => {
          setTtsSpeaking(false);
          ttsSpeakingRef.current = false;
          showVoiceToast(t('ttsUnavailable'));
          onDone?.();
        },
      });
    }
  }, [speak, showVoiceToast, t, voiceLang]);

  const cleanSpeechText = useCallback((text: string) => text
    .replace(/```[\s\S]*?```/g, t('ttsCodeBlockReplacement'))
    .replace(/`[^`]*`/g, '')
    .replace(/\[(.*?)\]\(.*?\)/g, '$1')
    .replace(/[#*_>~|]/g, '')
    .replace(/\s+/g, ' ')
    .trim(), []);

  const queueSpeech = useCallback((text: string, onDone?: () => void) => {
    if (!ttsSupported || !text) {
      onDone?.();
      return;
    }
    const v = pickVoice();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = voiceLang;
    u.rate = 1.04;
    u.pitch = 1;
    u.volume = 1;
    if (v) u.voice = v;
    u.onend = () => {
      stopTtsPump();
      ttsActiveKeyRef.current = null;
      setTtsActiveKey(null);
      ttsSpeakingRef.current = false;
      setTtsSpeaking(false);
      const done = ttsEndRef.current ?? onDone;
      if (cleanSpeechText(ttsTailRef.current)) {
        window.setTimeout(() => flushVoiceTtsRef.current(true, done ?? undefined), 0);
      } else {
        ttsEndRef.current = null;
        done?.();
      }
    };
    u.onerror = () => {
      stopTtsPump();
      ttsSpeakingRef.current = false;
      setTtsSpeaking(false);
      const done = ttsEndRef.current ?? onDone;
      ttsEndRef.current = null;
      if (!ttsCancellingRef.current) showVoiceToast(t('ttsUnavailable'));
      done?.();
    };
    ttsSpeakingRef.current = true;
    setTtsSpeaking(true);
    startTtsPump();
    try {
      window.speechSynthesis.resume();
      window.speechSynthesis.speak(u);
    } catch {
      stopTtsPump();
      ttsSpeakingRef.current = false;
      setTtsSpeaking(false);
      if (!ttsCancellingRef.current) showVoiceToast(t('ttsUnavailable'));
      onDone?.();
    }
  }, [cleanSpeechText, pickVoice, showVoiceToast, startTtsPump, stopTtsPump, t, ttsSupported, voiceLang]);

  // Some browsers occasionally omit SpeechSynthesisUtterance.onend. Keep the
  // indicator tied to the actual browser queue so it cannot remain stuck on
  // “TrinaxAI is speaking” after audio has finished.
  useEffect(() => {
    if (!ttsSpeaking || !ttsSupported) return undefined;
    let idleSince = 0;
    const timer = window.setInterval(() => {
      const active = window.speechSynthesis.speaking || window.speechSynthesis.pending;
      if (active || ttsTailRef.current) {
        idleSince = 0;
        return;
      }
      if (!idleSince) idleSince = Date.now();
      if (Date.now() - idleSince < 700) return;
      stopTtsPump();
      ttsActiveKeyRef.current = null;
      setTtsActiveKey(null);
      ttsSpeakingRef.current = false;
      setTtsSpeaking(false);
      const done = ttsEndRef.current;
      ttsEndRef.current = null;
      done?.();
    }, 250);
    return () => window.clearInterval(timer);
  }, [stopTtsPump, ttsSpeaking, ttsSupported]);

  const flushVoiceTts = useCallback((force = false, onDone?: () => void) => {
    const clean = cleanSpeechText(ttsTailRef.current);
    if (!clean) {
      onDone?.();
      return;
    }
    if (!force && clean.length < 90 && !/[.!?]\s*$/.test(clean)) return;
    ttsTailRef.current = '';
    queueSpeech(clean, onDone);
  }, [cleanSpeechText, queueSpeech]);

  useEffect(() => {
    flushVoiceTtsRef.current = flushVoiceTts;
  }, [flushVoiceTts]);

  // ── Imagen adjunta (visión) ──
  const [attachedImage, setAttachedImage] = useState<string | null>(null);
  const [attachedImageFile, setAttachedImageFile] = useState<File | null>(null);
  const [previewAttachment, setPreviewAttachment] = useState<{ attachment: ChatDocumentAttachment; url: string } | null>(null);
  const [isSmallViewport, setIsSmallViewport] = useState(false);
  const [textPreview, setTextPreview] = useState<string | null>(null);
  const [imageError, setImageError] = useState('');
  const openStoredAttachment = useCallback(async (attachment: ChatDocumentAttachment, inlineUrl?: string) => {
    const url = inlineUrl || await getChatAttachmentUrl(attachment.storageKey, attachment.mimeType);
    if (url) setPreviewAttachment({ attachment, url });
  }, []);
  useEffect(() => {
    const media = window.matchMedia('(max-width: 639px)');
    const update = () => setIsSmallViewport(media.matches);
    update();
    media.addEventListener?.('change', update);
    return () => media.removeEventListener?.('change', update);
  }, []);
  useEffect(() => {
    let cancelled = false;
    setTextPreview(null);
    if (!previewAttachment) return undefined;
    const isText = previewAttachment.attachment.mimeType?.startsWith('text/') || /\.(md|txt|csv|json|xml|html|css|js|ts|tsx|jsx|py|java|c|cpp|h|log)$/i.test(previewAttachment.attachment.name);
    if (!isText) return undefined;
    fetch(previewAttachment.url).then((response) => response.text()).then((text) => { if (!cancelled) setTextPreview(text); }).catch(() => { if (!cancelled) setTextPreview(null); });
    return () => { cancelled = true; };
  }, [previewAttachment, isSmallViewport]);
  const [researchMode, setResearchMode] = useState<boolean>(() => {
    try { return localStorage.getItem('tc-research-mode') === '1'; } catch { return false; }
  });
  useEffect(() => { try { localStorage.setItem('tc-research-mode', researchMode ? '1' : '0'); } catch { /* ignore */ } }, [researchMode]);
  const memoryCacheRef = useRef<{ summary: string; ts: number } | null>(null);

  // Invalidate the memory-summary cache when the user updates memories from
  // another component (MemoryPanel).
  useEffect(() => {
    const onUpd = () => { memoryCacheRef.current = null; };
    window.addEventListener('tc-memory-updated', onUpd);
    return () => window.removeEventListener('tc-memory-updated', onUpd);
  }, []);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const onPickImage = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      setImageError('');
      setAttachedImageFile(file);
      setAttachedImage(await prepareImageForVision(file));
    } catch (err: unknown) {
      setAttachedImage(null);
      setAttachedImageFile(null);
      setImageError(err instanceof Error ? err.message : t('imagePrepFailed'));
    } finally {
      e.target.value = '';
    }
  }, []);

  // ── Envío central (texto/voz/imagen) ──

  // Built-in slash-command helpers (must be declared before handleSendText).
  const runBuiltinDeepResearch = useCallback(async (query: string, baseMessages: ChatMessage[]) => {
    const placeholder: ChatMessage = { role: 'assistant', content: t('deepResearchInProgress') };
    const withPlaceholder = [...baseMessages, placeholder];
    onMessagesChange(withPlaceholder);
    try {
      const res = await runResearch(query, { collections: activeCollectionsForRequest, depth: 2 });
      const finalMsg: ChatMessage = {
        role: 'assistant',
        content: res.answer,
        sources: res.sources,
        model: res.model,
      };
      onMessagesChange([...baseMessages, finalMsg]);
    } catch (err) {
      const msg = err instanceof Error ? err.message.slice(0, 400) : t('deepResearchFailed');
      onMessagesChange([...baseMessages, { role: 'assistant', content: `❌ ${msg}` }]);
    }
  }, [activeCollectionsForRequest, onMessagesChange]);

  const runBuiltinSummarize = useCallback(async (baseMessages: ChatMessage[]) => {
    const summaryPrompt: ChatMessage = {
      role: 'user',
      content: `${lang === 'es' ? 'Resume los puntos clave de esta conversación en 5-7 viñetas y añade 1-2 frases con la conclusión general.' : 'Summarize the key points of this conversation in 5-7 bullet points, plus 1-2 sentences on the overall conclusion.'} ${lang === 'es' ? 'Conversación' : 'Conversation'}:\n\n${
        baseMessages.map((m) => `[${m.role}] ${m.content}`).join('\n\n').slice(-3000)
      }`,
    };
    const withPlaceholder = [...baseMessages, { role: 'assistant' as const, content: t('summarizingConversation') }];
    onMessagesChange(withPlaceholder);
    try {
      const { content, meta } = await sendMessage([...baseMessages, summaryPrompt], 'ollama');
      onMessagesChange([...baseMessages, {
        role: 'assistant',
        content: `${content}`,
        sources: meta.sources,
        model: meta.model,
        project: meta.project,
      }]);
    } catch (err) {
      const msg = err instanceof Error ? err.message.slice(0, 400) : assistantErrorMessage(err);
      onMessagesChange([...baseMessages, { role: 'assistant', content: `❌ ${msg}` }]);
    }
  }, [lang, onMessagesChange, sendMessage, assistantErrorMessage]);

  const handleSendText = useCallback(async (raw: string, opts?: { viaVoice?: boolean; continueCall?: boolean }) => {
    let trimmed = raw.trim();
    const image = attachedImage;
    const docs = attachedDocs;
    if ((!trimmed && !image && docs.length === 0) || streaming) return;
    setSlashOpen(false);
    recognitionRef.current?.abort?.();  // descarta resultados de voz pendientes
    setListening(false);

    // Handle built-in slash commands FIRST (they short-circuit the chat).
    if (trimmed.startsWith('/')) {
      const head = trimmed.split(' ')[0].slice(1).toLowerCase();
      const tail = trimmed.includes(' ') ? trimmed.slice(trimmed.indexOf(' ') + 1) : '';
      const builtin = findBuiltin(head, lang);
      if (builtin) {
        setInput('');
        resetInputHeight();
        switch (builtin.kind) {
          case 'navigate_settings': onNavigate?.('settings'); return;
          case 'navigate_indexing': onNavigate?.('indexing'); return;
          case 'navigate_browser':  onNavigate?.('browser');  return;
          case 'navigate_memory':   onNavigate?.('memory');   return;
          case 'navigate_docs':     onNavigate?.('docs');     return;
          case 'export_markdown':   exportMarkdown(); return;
          case 'deep_research': {
            const prompt = tail || (lang === 'es' ? 'Dame una visión general detallada.' : 'Give me a thorough overview.');
            const userMsg: ChatMessage = { role: 'user', content: prompt };
            onMessagesChange([...messages, userMsg]);
            requestAnimationFrame(() => scrollToBottom('smooth'));
            setInput(''); resetInputHeight();
            await runBuiltinDeepResearch(prompt, [...messages, userMsg]);
            return;
          }
          case 'summarize':
            await runBuiltinSummarize(messages);
            return;
          default:
            return;
        }
      }
      // Otherwise resolve user-defined slash command
      const match = customPrompts.current.find(p => p.name === head && !p.builtin);
      if (match) {
        trimmed = match.text + '\n\n' + tail;
      }
    }

    rememberFromMessage(trimmed);

    // Build context system messages from project memory + auto-summary (cached for 60s).
    const contextMessages: ChatMessage[] = [];
    const projectNotes = (() => { try { return localStorage.getItem('tc-project-memory')?.trim() || ''; } catch { return ''; } })();
    if (projectNotes) {
      contextMessages.push({ role: 'system', content: `Project memory (user-defined, always injected):\n${projectNotes}` });
    }
    if (folderContext.length) {
      const relatedChats = folderContext.map((chat) => {
        const transcript = chat.messages
          .filter((message) => message.role === 'user' || message.role === 'assistant')
          .slice(-12)
          .map((message) => `${message.role === 'user' ? 'Usuario' : 'TrinaxAI'}: ${(message.displayContent ?? message.content).slice(0, 2500)}`)
          .join('\n');
        return `CHAT "${chat.title}"\n${transcript}`;
      }).join('\n\n');
      contextMessages.push({ role: 'system', content: `Contexto de la carpeta actual. Usa estos chats como referencia cuando sea relevante; no inventes datos y no menciones este bloque salvo que el usuario lo pida:\n\n${relatedChats}` });
    }
    try {
      const now = Date.now();
      const cache = memoryCacheRef.current;
      if (cache && now - cache.ts < 60_000) {
        if (cache.summary) {
          contextMessages.push({ role: 'system', content: `Persistent memory summary (auto-generated from /memory):\n${cache.summary}` });
        }
      } else {
        const sum = await getMemorySummary();
        memoryCacheRef.current = { summary: sum.summary, ts: now };
        if (sum.summary) {
          contextMessages.push({ role: 'system', content: `Persistent memory summary (auto-generated from /memory):\n${sum.summary}` });
        }
      }
    } catch { /* ignore */ }

    const docContext = docs.map((doc) => (
      `\n\n[Archivo adjunto temporal: ${doc.name}${doc.truncated ? ' (truncado)' : ''}]\n`
      + '```text\n'
      + doc.content
      + '\n```'
    )).join('');
    const displayContent = trimmed || t('analyzeAttachedFiles');
    const messageContent = `${displayContent}${docContext}`;
    const storedDocuments = await Promise.all(docs.map((doc) => storeChatAttachment(doc.file, 'document').catch(() => ({ name: doc.name, size: doc.size }))));
    const storedImage = attachedImageFile
      ? await storeChatAttachment(attachedImageFile, 'image').catch(() => undefined)
      : undefined;
    const documentAttachments: ChatDocumentAttachment[] = docs.map((doc, index) => ({
      ...storedDocuments[index], name: doc.name, size: doc.size, truncated: doc.truncated, kind: 'document',
    }));
    if (storedImage) documentAttachments.unshift(storedImage);

    const userMsg: ChatMessage = {
      role: 'user',
      content: messageContent,
      displayContent,
      image: image || undefined,
      documentAttachments: documentAttachments.length ? documentAttachments : undefined,
      inputMode: opts?.viaVoice ? 'voice' : 'text',
    };
    const updated = [...messages, userMsg];
    onMessagesChange(updated);
    requestAnimationFrame(() => scrollToBottom('smooth'));
    setInput('');
    resetInputHeight();
    setAttachedImage(null);
    setAttachedImageFile(null);
    setAttachedDocs([]);

    // Deep-research mode short-circuits to /v1/research when there's no image/voice.
    if (researchMode && !image && !opts?.viaVoice) {
      try {
        const res = await runResearch(trimmed || t('analyzeAttachedFiles'), {
          collections: activeCollectionsForRequest,
          depth: 2,
        });
        onMessagesChange([...updated, {
          role: 'assistant',
          content: res.answer,
          sources: res.sources,
          model: res.model,
          project: null,
        }]);
      } catch (err) {
        const msg = err instanceof Error ? err.message.slice(0, 400) : assistantErrorMessage(err);
        onMessagesChange([...updated, { role: 'assistant', content: `❌ ${msg}` }]);
      }
      return;
    }

    // Imagen → modo visión (Ollama); si no, el motor seleccionado.
    const useEngine: ChatEngine = image || docs.length > 0 ? 'ollama' : engine;

    try {
      ttsTailRef.current = '';
      ttsSpeakingRef.current = false;
      setTtsSpeaking(false);
      ttsEndRef.current = null;
      const { content, meta } = await sendMessage([...contextMessages, ...updated], useEngine, {
        collections: activeCollectionsForRequest,
        ...(opts?.viaVoice ? {
          onToken: (token) => {
            if (!callModeRef.current && !opts.continueCall) return;
            ttsTailRef.current += token;
            if (!ttsSpeakingRef.current) flushVoiceTts(false);
          },
        } : {}),
      });
      const cancelledByUser = wasAborted() && !content;
      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: cancelledByUser ? `_${t('requestCancelled')}_` : content,
        sources: meta.sources, model: meta.model, project: meta.project,
      };
      onMessagesChange([...updated, assistantMsg]);
      if (cancelledByUser) return;
      if (opts?.viaVoice) {
        const onDone = () => {
          if (opts.continueCall && callModeRef.current) {
            window.setTimeout(() => startVoiceRef.current(true), 350);
          }
        };
        if (ttsSpeakingRef.current || ttsTailRef.current) {
          ttsEndRef.current = onDone;
          window.setTimeout(() => {
            if (!ttsSpeakingRef.current) flushVoiceTts(true, ttsEndRef.current ?? undefined);
          }, 120);
        } else {
          speakWithFallback(content, onDone);
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.message === 'TRINAXAI_SILENT_ABORT') return;
      const msg = assistantErrorMessage(err);
      const errorMsg: ChatMessage = { role: 'assistant', content: msg };
      onMessagesChange([...updated, errorMsg]);
      if (opts?.continueCall && callModeRef.current) {
        window.setTimeout(() => startVoiceRef.current(true), 800);
      }
    }
  }, [attachedImage, attachedImageFile, attachedDocs, messages, streaming, engine, sendMessage, onMessagesChange, speak, activeCollectionsForRequest, t, resetInputHeight, assistantErrorMessage, researchMode, onNavigate, exportMarkdown, runBuiltinDeepResearch, runBuiltinSummarize, scrollToBottom, folderContext]);

  // Keep the ref in sync so voice callbacks (declared earlier) can call handleSendText.
  handleSendTextRef.current = handleSendText;

  const handleSend = useCallback(() => { handleSendText(input); }, [handleSendText, input]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleStop = useCallback(() => {
    setCallMode(false);
    callModeRef.current = false;
    recognitionRef.current?.abort?.();
    backendRecorderStopRef.current?.();
    backendRecorderStopRef.current = null;
    releaseWakeLock();
    abort();
    stopSpeak();
  }, [abort, stopSpeak, releaseWakeLock]);

  const startVoiceCapture = useCallback((continuous: boolean) => {
    if (streaming) return;
    if (!secureVoiceContext) {
      showVoiceToast(t('voiceNeedsSecureContext'), 'error');
      setCallMode(false);
      callModeRef.current = false;
      setListening(false);
      return;
    }
    if (!voiceSupported) {
      showVoiceToast(t('voiceRecognitionUnsupported'), 'warning');
      setCallMode(false);
      callModeRef.current = false;
      setListening(false);
      return;
    }
    recognitionRef.current?.abort?.();
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const rec = new SR();
    rec.lang = voiceLang;
    rec.interimResults = true;
    rec.continuous = false;
    let finalText = '';
    let stopAfterError = false;
    rec.onresult = (e: any) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const tr = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalText += tr; else interim += tr;
      }
      setInput((finalText + interim).trim());
    };
    rec.onend = () => {
      setListening(false);
      recognitionRef.current = null;
      if (stopAfterError) return;
      const text = finalText.trim();
      if (text) {
        handleSendTextRef.current(text, { viaVoice: true, continueCall: continuous });
      } else if (continuous && callModeRef.current) {
        window.setTimeout(() => startVoiceRef.current(true), 500);
      } else {
        inputRef.current?.focus();
      }
    };
    rec.onerror = (event: any) => {
      setListening(false);
      recognitionRef.current = null;
      const error = String(event?.error || 'unknown');
      const permanent = ['not-allowed', 'service-not-allowed', 'audio-capture', 'network', 'language-not-supported'].includes(error);
      if (permanent) {
        stopAfterError = true;
        setCallMode(false);
        callModeRef.current = false;
        const message = error === 'not-allowed'
          ? t('voiceMicPermissionDenied')
          : error === 'audio-capture'
          ? t('voiceNoMicrophone')
          : error === 'network' || error === 'service-not-allowed'
          ? t('voiceRecognitionUnsupported')
          : t('voiceRecognitionFailed');
        showVoiceToast(message, error === 'not-allowed' ? 'error' : 'warning');
        return;
      }
      if (continuous && callModeRef.current && error === 'no-speech') {
        window.setTimeout(() => startVoiceRef.current(true), 900);
      }
    };
    recognitionRef.current = rec;
    setListening(true);
    try {
      rec.start();
    } catch {
      recognitionRef.current = null;
      setListening(false);
      setCallMode(false);
      callModeRef.current = false;
      showVoiceToast(t('voiceRecognitionFailed'), 'warning');
    }
  }, [secureVoiceContext, showVoiceToast, streaming, t, voiceLang, voiceSupported]);

  useEffect(() => {
    startVoiceRef.current = startVoiceCapture;
  }, [startVoiceCapture]);

  // ── Dictado por voz → auto-envío → respuesta hablada (TTS) ──
  const toggleVoice = useCallback(() => {
    if (callMode) {
      handleStop();
      return;
    }
    if (!secureVoiceContext) {
      showVoiceToast(t('voiceNeedsSecureContext'), 'error');
      return;
    }
    if (!voiceSupported && !detectBackendVoice()) {
      showVoiceToast(t('voiceRecognitionUnsupported'), 'warning');
      return;
    }
    setCallMode(true);
    callModeRef.current = true;
    requestWakeLock();
    if (voiceSupported) {
      unlockSpeech();
      startVoiceCapture(true);
    } else {
      startBackendVoiceCapture(true);
    }
  }, [callMode, secureVoiceContext, showVoiceToast, startVoiceCapture, startBackendVoiceCapture, handleStop, t, unlockSpeech, voiceSupported, requestWakeLock]);

  // Start editing a user message
  const startEdit = useCallback(
    (index: number) => {
      if (streaming) abort(true);
      stopSpeak();
      setEditingIndex(index);
      setEditingText(messageDisplayContent(messages[index]));
    },
    [messages, streaming, abort, stopSpeak, messageDisplayContent],
  );

  // Save edit: trim messages after the edited one and resend
  const saveEdit = useCallback(async () => {
    if (editingIndex === null || !editingText.trim()) {
      setEditingIndex(null);
      return;
    }
    const sliced = messages.slice(0, editingIndex);
    abort(true);
    stopSpeak();
    const previous = messages[editingIndex];
    const userMsg: ChatMessage = {
      role: 'user',
      content: editingText.trim(),
      image: previous?.role === 'user' ? previous.image : undefined,
      inputMode: previous?.role === 'user' ? previous.inputMode : 'text',
    };
    const updated = [...sliced, userMsg];
    onMessagesChange(updated);
    setEditingIndex(null);

    try {
      // For edits, prepend memory/project context too.
      const ctxForEdit: ChatMessage[] = [];
      const pn = (() => { try { return localStorage.getItem('tc-project-memory')?.trim() || ''; } catch { return ''; } })();
      if (pn) ctxForEdit.push({ role: 'system', content: `Project memory (user-defined):\n${pn}` });
      try {
        const sum = await getMemorySummary();
        if (sum.summary) ctxForEdit.push({ role: 'system', content: `Persistent memory summary:\n${sum.summary}` });
      } catch { /* ignore */ }
      const { content, meta } = await sendMessage([...ctxForEdit, ...updated], engine, {
        collections: activeCollectionsForRequest,
      });
      const assistantMsg: ChatMessage = {
        role: 'assistant', content,
        sources: meta.sources, model: meta.model, project: meta.project,
      };
      onMessagesChange([...updated, assistantMsg]);
    } catch (err: unknown) {
      if (err instanceof Error && err.message === 'TRINAXAI_SILENT_ABORT') return;
      const msg = assistantErrorMessage(err);
      onMessagesChange([...updated, { role: 'assistant', content: msg }]);
    }
  }, [editingIndex, editingText, messages, engine, sendMessage, abort, stopSpeak, onMessagesChange, assistantErrorMessage, activeCollectionsForRequest]);

  const regenerateFrom = useCallback(async (assistantIndex: number) => {
    if (streaming) abort(true);
    stopSpeak();
    const updated = messages.slice(0, assistantIndex);
    if (!updated.some((msg) => msg.role === 'user')) return;
    onMessagesChange(updated);
    try {
      const ctxForRegen: ChatMessage[] = [];
      const pn = (() => { try { return localStorage.getItem('tc-project-memory')?.trim() || ''; } catch { return ''; } })();
      if (pn) ctxForRegen.push({ role: 'system', content: `Project memory (user-defined):\n${pn}` });
      try {
        const sum = await getMemorySummary();
        if (sum.summary) ctxForRegen.push({ role: 'system', content: `Persistent memory summary:\n${sum.summary}` });
      } catch { /* ignore */ }
      const { content, meta } = await sendMessage([...ctxForRegen, ...updated], engine, {
        collections: activeCollectionsForRequest,
      });
      onMessagesChange([...updated, {
        role: 'assistant',
        content,
        sources: meta.sources,
        model: meta.model,
        project: meta.project,
      }]);
    } catch (err: unknown) {
      if (err instanceof Error && err.message === 'TRINAXAI_SILENT_ABORT') return;
      onMessagesChange([...updated, { role: 'assistant', content: assistantErrorMessage(err) }]);
    }
  }, [messages, streaming, abort, stopSpeak, onMessagesChange, engine, sendMessage, activeCollectionsForRequest, assistantErrorMessage]);

  // ── Compute display chips (after all callbacks / refs are in scope) ──
  const displayChips = chipDefsRef.current.map((def, i) => {
    let action: () => void;
    switch (def.kind) {
      case 'navigate':
        action = () => onNavigate?.(def.page as 'indexing' | 'settings' | 'browser' | 'memory' | 'docs');
        break;
      case 'slash': {
        const cmd = def.labelKey === 'quickChipSummarize'
          ? (lang === 'es' ? '/resumir' : '/summarize')
          : def.command!;
        action = () => { setInput(cmd); inputRef.current?.focus(); };
        break;
      }
      case 'callMode':
        action = () => { toggleVoice(); };
        break;
      case 'pickImage':
        action = () => { setInput(t(def.promptKey as any)); fileInputRef.current?.click(); };
        break;
      case 'pickFile':
        action = () => { setInput(t(def.promptKey as any)); docInputRef.current?.click(); };
        break;
      case 'toggleResearch':
        action = () => { setResearchMode(prev => !prev); };
        break;
      default: // prompt
        action = () => { setInput(t(def.promptKey as any)); inputRef.current?.focus(); };
    }
    return { label: t(def.labelKey as any), icon: def.icon, action, idx: i };
  });

  return (
    <div className="flex flex-col h-full min-h-0 min-w-0 max-w-full overflow-hidden transition-colors duration-300">
      {/* Navbar — items centered vertically with proper safe-area padding.
          `relative z-50` lifts the whole navbar's stacking context above the
          messages area below it, so the export dropdown renders on top and
          stays clickable (its backdrop-blur creates a stacking context that
          would otherwise trap the menu behind the messages). */}
      <nav className={`relative z-50 shrink-0 flex items-center px-2 sm:px-3 border-b ${isDark ? 'bg-black/80 border-white/[0.06]' : 'bg-white/90 border-gray-200'} backdrop-blur-xl`}
           style={{ minHeight: '44px', paddingTop: 'env(safe-area-inset-top, 0px)' }}>
        {/* Left: menu button + animated branding */}
        <div className="flex items-center shrink-0 gap-1">
          <button
            onClick={onMenuToggle}
            className={`p-2 rounded-xl transition-all ${
              isDark ? 'text-white/60 hover:text-white hover:bg-white/[0.06]' : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
            }`}
            aria-label={sidebarOpen ? t('closeMenu') : t('openMenu')}
          >
            <MdMenu size={20} />
          </button>
          <span
            className="text-lg sm:text-xl md:text-xl font-bold tracking-normal animate-brand"
          >
            TrinaxAI
          </span>
        </div>

        {/* Right: toggle + actions */}
        <div className="flex items-center gap-0.5 sm:gap-2 md:gap-3 ml-auto">
          <div className="flex items-center gap-0">
            {/* Download button with format dropdown */}
            <div className="relative">
              <button
                onClick={() => setExportMenuOpen((v) => !v)}
                disabled={messages.length === 0}
                className={`h-8 w-8 sm:h-9 sm:w-9 rounded-lg sm:rounded-xl transition-colors flex items-center justify-center ${
                  messages.length === 0
                    ? isDark ? 'text-white/20 cursor-not-allowed' : 'text-gray-300 cursor-not-allowed'
                    : isDark ? 'text-white/55 hover:text-white hover:bg-white/[0.06]' : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
                }`}
                aria-label={t('exportChat')}
                title={t('exportChat')}
              >
                <MdDownload size={17} />
              </button>
              <AnimatePresence>
                {exportMenuOpen && messages.length > 0 && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setExportMenuOpen(false)} />
                    <motion.div
                      initial={{ opacity: 0, scale: 0.92, y: -4 }}
                      animate={{ opacity: 1, scale: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.92, y: -4 }}
                      transition={{ duration: 0.15 }}
                      className={`absolute right-0 top-full mt-1.5 z-50 w-48 rounded-xl border py-1 shadow-lg backdrop-blur-xl ${
                        isDark
                          ? 'border-white/[0.08] bg-[#1a1a1a]/95 shadow-black/40'
                          : 'border-gray-200 bg-white/95 shadow-gray-200/80'
                      }`}
                    >
                      <button
                        onClick={() => { exportMarkdown(); setExportMenuOpen(false); }}
                        className={`w-full text-left px-4 py-2.5 text-sm flex items-center gap-3 transition-colors ${
                          isDark ? 'text-white/70 hover:text-white hover:bg-white/[0.05]' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                        }`}
                      >
                        <MdDownload size={16} />
                        {t('exportAsMd')}
                      </button>
                      <button
                        onClick={() => { exportPdf(); setExportMenuOpen(false); }}
                        className={`w-full text-left px-4 py-2.5 text-sm flex items-center gap-3 transition-colors ${
                          isDark ? 'text-white/70 hover:text-white hover:bg-white/[0.05]' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                        }`}
                      >
                        <MdDescription size={16} />
                        {t('exportAsPdf')}
                      </button>
                      <button
                        onClick={() => { exportWord(); setExportMenuOpen(false); }}
                        className={`w-full text-left px-4 py-2.5 text-sm flex items-center gap-3 transition-colors ${
                          isDark ? 'text-white/70 hover:text-white hover:bg-white/[0.05]' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                        }`}
                      >
                        <MdDescription size={16} />
                        {t('exportAsWord')}
                      </button>
                    </motion.div>
                  </>
                )}
              </AnimatePresence>
            </div>
            <button
              onClick={() => setResearchMode((v) => !v)}
              className={`h-8 w-8 sm:h-9 sm:w-9 rounded-lg sm:rounded-xl transition-colors flex items-center justify-center ${
                researchMode
                  ? 'bg-[#006bbd]/20 text-[#006bbd] ring-1 ring-[#006bbd]/40 animate-soft-pulse'
                  : isDark ? 'text-white/55 hover:text-white hover:bg-white/[0.06]' : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
              }`}
              aria-label={t('toggleDeepResearch')}
              title={t('deepResearchTitle')}
            >
              <MdScience size={17} />
            </button>
          </div>
          <ToggleSwitch engine={engine} onChange={onEngineChange} />
        </div>
      </nav>

      {/* Empty state — logo + rotating motivational message + quick-start chips */}
      {messages.length === 0 && !streaming && (
        <motion.div
          className="flex-1 flex flex-col items-center justify-center gap-6 px-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="animate-float"
          >
            <img
              src="/new-logo-for-AI.webp"
              alt="TrinaxAI"
              className="w-16 h-16 md:w-20 md:h-20 rounded-full object-cover
                         opacity-85 shadow-lg animate-glow"
            />
          </motion.div>
          <AnimatePresence mode="wait">
            <motion.p
              key={motd}
              className={`text-sm md:text-base text-center font-light tracking-wide max-w-xs ${isDark ? 'text-white/50' : 'text-gray-400'}`}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.5, ease: 'easeInOut' }}
            >
              {motd}
            </motion.p>
          </AnimatePresence>
          {/* Quick-start chips — 2 random suggestions per new chat */}
          <div className="flex flex-wrap items-center justify-center gap-2.5 max-w-md">
            {displayChips.map((chip) => (
              <motion.button
                key={chip.label + chip.idx}
                initial={{ opacity: 0, y: 10, scale: 0.9 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{
                  duration: 0.45,
                  delay: 0.15 + chip.idx * 0.09,
                  ease: [0.16, 1, 0.3, 1],
                }}
                whileHover={{ scale: 1.05, y: -2 }}
                whileTap={{ scale: 0.96 }}
                onClick={chip.action}
                className={`chip-elegant relative flex items-center gap-2 pl-2 pr-3.5 py-1.5 rounded-full text-xs font-medium border overflow-hidden ${
                  isDark
                    ? 'text-white/70 border-white/[0.09] bg-gradient-to-b from-white/[0.06] to-white/[0.015]'
                    : 'text-gray-600 border-gray-200/80 bg-gradient-to-b from-white to-gray-50'
                }`}
              >
                <span className="chip-elegant-icon flex items-center justify-center w-5 h-5 rounded-full text-[13px] leading-none shrink-0">
                  {chip.icon}
                </span>
                <span className="relative z-[1] whitespace-nowrap">{chip.label}</span>
              </motion.button>
            ))}
          </div>
        </motion.div>
      )}

      {/* Messages */}
      <div className={`${messages.length === 0 && !streaming ? 'hidden' : 'relative flex-1'} min-h-0 min-w-0 max-w-full`}>
        <div
          ref={messagesRef}
          onScroll={updateScrollState}
          className="chat-messages h-full min-h-0 min-w-0 max-w-full overflow-y-auto overflow-x-hidden px-2 sm:px-4 py-4 space-y-4"
          style={{ overscrollBehavior: 'contain', WebkitOverflowScrolling: 'touch' }}
        >
          {messages.map((msg, i) => (
            <motion.div
              key={`${i}-${msg.role}`}
              initial={{ opacity: 0, y: 12, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.3, delay: 0, ease: [0.16, 1, 0.3, 1] }}
              className={`chat-row flex min-w-0 w-full max-w-full gap-2 sm:gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {/* Avatar (AI) */}
              {msg.role === 'assistant' && (
                <img
                  src="/new-logo-for-AI.webp"
                  alt="TrinaxAI"
                  className="w-7 h-7 rounded-full shrink-0 mt-0.5 object-cover"
                  width={28}
                  height={28}
                />
              )}

              {/* Bubble */}
              {editingIndex === i ? (
                /* Edit mode */
                <div className="chat-bubble-wrap min-w-0 flex-1">
                  <textarea
                    autoFocus
                    value={editingText}
                    onChange={(e) => setEditingText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        saveEdit();
                      }
                      if (e.key === 'Escape') setEditingIndex(null);
                    }}
                    className={`w-full border border-[#006bbd]/40 rounded-xl px-3 py-2 text-sm resize-none outline-none focus:border-[#006bbd] ${
                      isDark ? 'bg-[#006bbd]/20 text-white placeholder-white/30' : 'bg-[#006bbd]/10 text-gray-900 placeholder-gray-400'
                    }`}
                    rows={2}
                  />
                  <div className="flex gap-2 mt-1">
                    <button
                      onClick={saveEdit}
                      className="text-xs px-2 py-1 rounded-lg bg-[#006bbd] text-white"
                    >
                      {t('saveAndResend')}
                    </button>
                    <button
                      onClick={() => setEditingIndex(null)}
                      className={`text-xs px-2 py-1 rounded-lg ${
                        isDark ? 'bg-white/10 text-white/70 hover:text-white' : 'bg-gray-200 text-gray-700 hover:text-gray-900'
                      }`}
                    >
                      {t('cancel')}
                    </button>
                  </div>
                </div>
              ) : msg.role === 'assistant' ? (
                <div className="chat-bubble-wrap min-w-0 flex flex-col items-start">
                  <div className={`chat-bubble min-w-0 overflow-hidden px-4 py-2.5 rounded-2xl rounded-bl-md text-sm leading-relaxed ${isDark ? 'bg-white/[0.06] text-white/90' : 'bg-gray-100 text-gray-800'}`}>
                    <MarkdownContent text={visibleMessageContent(msg.content)} isDark={isDark} />
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <button
                      onClick={() => copyMessage(visibleMessageContent(msg.content), `msg-copy-${i}`)}
                      className={`p-1 rounded-md transition-colors ${
                        copiedKey === `msg-copy-${i}`
                          ? 'text-[#006bbd] bg-[#006bbd]/10'
                          : isDark ? 'text-white/30 hover:text-white/70 hover:bg-white/[0.06]' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
                      }`}
                      title={copiedKey === `msg-copy-${i}` ? t('copied') : t('copy')}
                      aria-label={copiedKey === `msg-copy-${i}` ? t('copied') : t('copy')}
                    >
                      {copiedKey === `msg-copy-${i}` ? <MdCheck size={15} /> : <MdContentCopy size={15} />}
                    </button>
                    <button
                      onClick={() => regenerateFrom(i)}
                      disabled={streaming}
                      className={`p-1 rounded-md transition-colors ${
                        isDark ? 'text-white/30 hover:text-white/70 hover:bg-white/[0.06]' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
                      } disabled:opacity-30`}
                      title={t('regenerate')}
                      aria-label={t('regenerate')}
                    >
                      <MdRefresh size={15} />
                    </button>
                    {ttsSupported && (
                      <button
                        onClick={() => {
                          if (ttsActiveKey === `msg-${i}`) {
                            stopSpeak();
                          } else {
                            speak(visibleMessageContent(msg.content), undefined, `msg-${i}`);
                          }
                        }}
                        className={`p-1 rounded-md transition-colors ${
                          ttsActiveKey === `msg-${i}`
                            ? 'text-[#006bbd] bg-[#006bbd]/10'
                            : isDark ? 'text-white/30 hover:text-white/70 hover:bg-white/[0.06]' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
                        }`}
                        title={ttsActiveKey === `msg-${i}` ? t('stop') : t('listen')}
                        aria-label={ttsActiveKey === `msg-${i}` ? t('stop') : t('listen')}
                      >
                        {ttsActiveKey === `msg-${i}` ? <MdStop size={15} /> : <MdVolumeUp size={15} />}
                      </button>
                    )}
                  </div>
                  <Sources
                sources={msg.sources}
                model={msg.model}
                project={msg.project}
                query={getLastUserText(messages, msg)}
                onOpenInBrowser={onNavigate ? (file, col) => {
                  // Stash the target on window so KnowledgeBrowser can pick it up on mount.
                  (window as any).__tc_browser_open = { file, collection: col || activeCollectionsForRequest[0] || 'default' };
                  onNavigate('browser');
                } : undefined}
              />
                </div>
              ) : (
                <div className="chat-bubble-wrap min-w-0 flex flex-col items-end">
                  <div
                    className="chat-bubble min-w-0 max-w-full max-h-[22rem] overflow-y-auto overflow-x-hidden px-4 py-2.5 rounded-2xl rounded-br-md text-sm leading-relaxed
                               bg-[#006bbd] text-white transition-all group/msg"
                  >
                    {msg.image && (
                      <button type="button" onClick={() => openStoredAttachment({ name: t('attachedImage'), size: 0, mimeType: 'image/*', kind: 'image' }, msg.image)}>
                        <img src={msg.image} alt={t('attachedImage')} className="rounded-lg mb-2 max-h-52 max-w-full w-auto object-contain" />
                      </button>
                    )}
                    {!msg.image && msg.documentAttachments?.some((doc) => doc.kind === 'image') && (
                      <div className="mb-2 flex flex-wrap gap-1.5">
                        {msg.documentAttachments.filter((doc) => doc.kind === 'image').map((doc, docIndex) => (
                          <button type="button" key={`image-${doc.id || docIndex}`} onClick={() => openStoredAttachment(doc)} className="inline-flex items-center gap-1.5 rounded-lg bg-white/15 px-2 py-1 text-[11px] text-white/90">
                            <MdImage size={14} /> {doc.name || t('attachedImage')}
                          </button>
                        ))}
                      </div>
                    )}
                    {msg.documentAttachments?.length ? (
                      <div className="mb-2 flex max-w-full flex-wrap gap-1.5">
                        {msg.documentAttachments.filter((doc) => doc.kind !== 'image').map((doc, docIndex) => (
                          <button type="button" onClick={() => openStoredAttachment(doc)}
                            key={`${doc.name}-${docIndex}`}
                            className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-lg bg-white/15 px-2 py-1 text-[11px] text-white/90"
                          >
                            <MdUploadFile size={14} className="shrink-0" />
                            <span className="min-w-0 max-w-48 truncate">{doc.name}</span>
                            {formatAttachmentSize(doc.size) && (
                              <span className="shrink-0 text-white/60">{formatAttachmentSize(doc.size)}</span>
                            )}
                            {doc.truncated && <span className="shrink-0 text-amber-200">{t('truncated')}</span>}
                          </button>
                        ))}
                      </div>
                    ) : null}
                    {messageDisplayContent(msg) && (
                      <p className="chat-plain-text min-w-0 max-w-full whitespace-pre-wrap">{messageDisplayContent(msg)}</p>
                    )}
                  </div>
                  <div className="mt-1 flex items-center gap-1">
                    <button
                      onClick={() => startEdit(i)}
                      className={`p-1 rounded-md transition-colors ${
                        isDark ? 'text-white/35 hover:text-white/75 hover:bg-white/[0.06]' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                      }`}
                      title={t('clickToEdit')}
                      aria-label={t('clickToEdit')}
                    >
                      <MdEdit size={15} />
                    </button>
                    <button
                      onClick={() => copyMessage(messageDisplayContent(msg), `msg-copy-${i}`)}
                      className={`p-1 rounded-md transition-colors ${
                        copiedKey === `msg-copy-${i}`
                          ? 'text-[#006bbd] bg-[#006bbd]/10'
                          : isDark ? 'text-white/30 hover:text-white/70 hover:bg-white/[0.06]' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
                      }`}
                      title={copiedKey === `msg-copy-${i}` ? t('copied') : t('copy')}
                      aria-label={copiedKey === `msg-copy-${i}` ? t('copied') : t('copy')}
                    >
                      {copiedKey === `msg-copy-${i}` ? <MdCheck size={15} /> : <MdContentCopy size={15} />}
                    </button>
                  </div>
                </div>
              )}

              {/* Avatar (user) */}
              {msg.role === 'user' && (
                <div
                  className="w-7 h-7 rounded-full shrink-0 mt-0.5 grid place-items-center bg-[#006bbd] text-white text-xs font-semibold"
                  aria-label={t('userAvatar')}
                  title={userDisplayName}
                >
                  {(userDisplayName.trim()[0] || 'U').toUpperCase()}
                </div>
              )}
            </motion.div>
          ))}

          {/* Streaming bubble with typing animation */}
          {streaming && (
            <motion.div
              initial={{ opacity: 0, y: 8, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              className="chat-row flex min-w-0 w-full max-w-full gap-2 sm:gap-3 justify-start"
            >
              <img
                src="/new-logo-for-AI.webp"
                alt="TrinaxAI"
                className="w-7 h-7 rounded-full shrink-0 mt-0.5 object-cover"
                width={28}
                height={28}
              />
              <div className="chat-bubble-wrap min-w-0">
                <div className={`chat-bubble min-w-0 overflow-hidden px-4 py-2.5 rounded-2xl rounded-bl-md text-sm leading-relaxed ${isDark ? 'bg-white/[0.06] text-white/90' : 'bg-gray-100 text-gray-800'}`}>
                  {streamedText ? (
                    <p className="chat-plain-text min-w-0 max-w-full whitespace-pre-wrap">
                      {visibleMessageContent(streamedText)}
                    </p>
                  ) : (
                    <div className="flex items-center gap-1.5">
                      <span className={`text-xs ${isDark ? 'text-white/50' : 'text-gray-400'}`}>
                        {ttsSpeaking ? t('speaking') : t('thinking')}
                      </span>
                      <span className="flex gap-0.5 pt-0.5">
                        <span className="w-1 h-1 rounded-full bg-[#006bbd] animate-pulse" style={{ animationDelay: '0ms' }} />
                        <span className="w-1 h-1 rounded-full bg-[#006bbd] animate-pulse" style={{ animationDelay: '200ms' }} />
                        <span className="w-1 h-1 rounded-full bg-[#006bbd] animate-pulse" style={{ animationDelay: '400ms' }} />
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </div>

        <AnimatePresence>
          {showScrollButton && (
            <motion.button
              type="button"
              onClick={() => scrollToBottom('smooth')}
              initial={{ opacity: 0, scale: 0.94 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.94 }}
              transition={{ duration: 0.16, ease: 'easeOut' }}
              className={`fixed bottom-[calc(env(safe-area-inset-bottom,0px)+6rem)] left-1/2 ${sidebarOpen ? 'md:left-[calc(50%+9rem)] z-20 pointer-events-none' : 'z-30'} grid h-11 w-11 -translate-x-1/2 place-items-center rounded-full border shadow-lg backdrop-blur-xl transition-all active:scale-95 ${
                isDark
                  ? 'border-white/[0.08] bg-black/85 text-white/80 hover:bg-[#006bbd] hover:text-white'
                  : 'border-gray-200 bg-white/95 text-gray-600 hover:bg-[#006bbd] hover:text-white'
              }`}
              aria-label={t('scrollToBottom')}
              title={t('scrollToBottom')}
            >
              <MdKeyboardArrowDown size={30} />
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      {/* ── Speaking indicator bar ── */}
      <AnimatePresence>
        {ttsSpeaking && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="shrink-0 flex items-center justify-center gap-3 px-4 py-2.5
                       bg-[#006bbd]/10 border-t border-[#006bbd]/20"
          >
            <div className="flex items-center gap-0.5 h-6">
              {[3, 12, 6, 16, 4, 10, 5].map((h, i) => (
                <motion.div
                  key={i}
                  className="w-1 bg-[#006bbd] rounded-full"
                  animate={{ height: [Math.max(2, h-6), h, Math.max(2, h-4), h] }}
                  transition={{ repeat: Infinity, repeatType: 'reverse', duration: 0.35 + i * 0.1, ease: 'easeInOut' }}
                />
              ))}
            </div>
            <span className="text-xs text-[#006bbd] font-medium">{t('speaking')}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input Area */}
      <div
        className={`shrink-0 px-2 sm:px-4 pt-2 border-t ${isDark ? 'border-white/[0.06]' : 'border-gray-200'}`}
        style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 12px)' }}
      >
        {engine === 'rag' && collections.length > 0 && (
          <div className="mb-2 flex items-center gap-2 overflow-x-auto pb-1">
            <span className={`shrink-0 text-[10px] uppercase tracking-wider ${isDark ? 'text-white/35' : 'text-gray-400'}`}>
              {t('activeCollections')}
            </span>
            {collections.map((collection) => {
              const active = activeCollectionIds.includes(collection.id);
              return (
                <button
                  key={collection.id}
                  onClick={() => toggleCollection(collection.id)}
                  className={`shrink-0 max-w-36 truncate rounded-full border px-3 py-1 text-[11px] font-medium transition-all active:scale-95 ${
                    active
                      ? 'border-[#006bbd]/50 bg-[#006bbd]/15 text-[#4ea3e0] animate-soft-pulse'
                      : isDark ? 'border-white/[0.08] bg-white/[0.03] text-white/45 hover:text-white/75' : 'border-gray-200 bg-gray-50 text-gray-500 hover:text-gray-800'
                  }`}
                  title={collection.name}
                >
                  {collection.name}
                </button>
              );
            })}
          </div>
        )}
        {(docUploadStatus || docConvertProgress) && (
          <div className={`mb-2 rounded-xl border px-3 py-2 ${isDark ? 'bg-white/[0.03] border-white/[0.08]' : 'bg-gray-50 border-gray-200'}`}>
            {docUploadStatus && (
              <p className={`text-xs ${isDark ? 'text-white/55' : 'text-gray-600'}`}>{docUploadStatus}</p>
            )}
            {docConvertProgress && (
              <div className="mt-2">
                <div className={`h-1.5 w-full overflow-hidden rounded-full ${isDark ? 'bg-white/[0.08]' : 'bg-gray-200'}`}>
                  <div
                    className="h-full rounded-full bg-[#006bbd] transition-all duration-300"
                    style={{ width: `${Math.max(2, Math.min(100, docConvertProgress.progress))}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        )}
        {attachedDocs.length > 0 && (
          <div className={`mb-2 rounded-xl border px-3 py-2 space-y-2 ${isDark ? 'bg-white/[0.03] border-white/[0.08]' : 'bg-gray-50 border-gray-200'}`}>
            <div className="flex flex-wrap items-center gap-2">
              {attachedDocs.map((doc) => (
                <span key={doc.name} className={`inline-flex max-w-full items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] ${isDark ? 'bg-white/[0.06] text-white/60' : 'bg-white text-gray-600'}`}>
                  <MdUploadFile size={14} />
                  <span className="truncate max-w-48">{doc.name}</span>
                  {doc.truncated && <span className="text-amber-400">{t('truncated')}</span>}
                </span>
              ))}
              <button
                onClick={() => setAttachedDocs([])}
                className={`ml-auto p-1 rounded-md ${isDark ? 'text-white/35 hover:text-white hover:bg-white/[0.06]' : 'text-gray-400 hover:text-gray-700 hover:bg-gray-100'}`}
                aria-label={t('removeDocument')}
                title={t('removeDocument')}
              >
                <MdClose size={16} />
              </button>
            </div>
            {engine === 'rag' && (
              <div className="flex flex-wrap items-center gap-2">
                <span className={`text-[11px] ${isDark ? 'text-white/35' : 'text-gray-400'}`}>{t('indexAttachedQuestion')}</span>
                <select
                  value={docIndexCollectionId}
                  onChange={(e) => setDocIndexCollectionId(e.target.value)}
                  className={`min-w-0 rounded-lg border px-2 py-1 text-[11px] outline-none ${isDark ? 'bg-black border-white/[0.08] text-white/70' : 'bg-white border-gray-200 text-gray-700'}`}
                >
                  {collections.map((collection) => (
                    <option key={collection.id} value={collection.id}>{collection.name}</option>
                  ))}
                </select>
                <button
                  onClick={indexAttachedDocs}
                  className="rounded-lg bg-[#006bbd]/15 px-2.5 py-1 text-[11px] font-medium text-[#4ea3e0] hover:bg-[#006bbd]/25"
                >
                  {t('indexAttachedNow')}
                </button>
              </div>
            )}
          </div>
        )}
        {/* Preview de imagen adjunta */}
        {attachedImage && (
          <div className="mb-2 relative inline-block">
            <img src={attachedImage} alt={t('attachedImage')}
                 className="h-20 w-auto rounded-lg border border-white/[0.1] object-cover" />
            <button
              onClick={() => setAttachedImage(null)}
              className="absolute -top-2 -right-2 p-0.5 rounded-full bg-black/80 border border-white/20 text-white/80 hover:text-white"
              aria-label={t('removeImage')}
            >
              <MdClose size={14} />
            </button>
          </div>
        )}
        {imageError && (
          <p className="mb-2 text-xs text-red-300/90">{imageError}</p>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={onPickImage}
        />
        <input
          ref={docInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={onPickDocs}
        />
        <div
          className={`flex items-center gap-1 sm:gap-2 rounded-2xl border px-2 sm:px-3 py-1.5 transition-all duration-300 relative focus-within:animate-border-glow ${
            isDark
              ? 'bg-white/[0.04] border-white/[0.08] focus-within:border-[#006bbd]/40 focus-within:shadow-[0_0_20px_rgba(0,107,189,0.15)]'
              : 'bg-gray-100 border-gray-200 focus-within:border-[#006bbd]/40 focus-within:shadow-[0_0_20px_rgba(0,107,189,0.1)]'
          }`}
        >
          {slashOpen && customPrompts.current.filter(p => p.name.includes(slashFilter)).length > 0 && (
            <div className={`absolute bottom-full left-0 right-0 mb-2 rounded-xl overflow-hidden z-30 max-h-48 overflow-y-auto ${isDark ? 'bg-black/95 border-white/[0.08]' : 'bg-white border-gray-200 shadow-lg'}`}>
              <div className="relative">
                {customPrompts.current.filter(p => p.name.includes(slashFilter)).map(p => (
                  <button key={p.name} onClick={() => {
                    if (p.builtin) {
                      // Navigation commands execute directly. Chat commands are
                      // only inserted; selecting an option must never submit a
                      // stale input value such as just "/".
                      if (p.kind === 'navigate_settings') { setSlashOpen(false); onNavigate?.('settings'); return; }
                      if (p.kind === 'navigate_indexing') { setSlashOpen(false); onNavigate?.('indexing'); return; }
                      if (p.kind === 'navigate_browser') { setSlashOpen(false); onNavigate?.('browser'); return; }
                      if (p.kind === 'navigate_memory') { setSlashOpen(false); onNavigate?.('memory'); return; }
                      if (p.kind === 'navigate_docs') { setSlashOpen(false); onNavigate?.('docs'); return; }
                      if (p.kind === 'export_markdown') { setSlashOpen(false); exportMarkdown(); return; }
                      setInput('/' + p.name + ' ');
                      setSlashOpen(false);
                      inputRef.current?.focus();
                    } else {
                      setInput('/'+p.name+' '); setSlashOpen(false); inputRef.current?.focus();
                    }
                  }}
                    className={`w-full text-left px-4 py-2.5 text-sm flex items-center gap-3 ${isDark ? 'text-white/60 hover:text-white hover:bg-white/[0.04]' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}`}>
                    <span className="text-[10px] text-[#006bbd] font-mono">/{p.name}</span>
                    {p.builtin && (
                      <span className="text-[8px] font-bold uppercase tracking-wider px-1 py-0.5 rounded bg-[#006bbd]/15 text-[#006bbd]">{t('builtInCommand')}</span>
                    )}
                    <span className={`truncate ${isDark ? 'text-white/30' : 'text-gray-400'}`}>
                      {p.builtin ? getBuiltinHint(p.name, lang) : (p.text || '').slice(0, 50) + '…'}
                    </span>
                  </button>
                ))}
                {/* Fade-out mask at bottom when scrollable */}
                <div className={`sticky bottom-0 left-0 right-0 h-6 pointer-events-none bg-gradient-to-t ${isDark ? 'from-black/95' : 'from-white'} to-transparent`} />
              </div>
            </div>
          )}
          <textarea
            ref={inputRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder={t('typeMessage')}
            aria-label={t('typeMessage')}
            className={`flex-1 min-w-0 min-h-[40px] max-h-[160px] bg-transparent text-sm resize-none outline-none overflow-y-auto py-1.5 leading-6 ${isDark ? 'text-white placeholder-white/30' : 'text-gray-800 placeholder-gray-400'}`}
            disabled={streaming}
          />

          {!streaming && (
            <button
              onClick={() => docInputRef.current?.click()}
              className={`p-2 rounded-xl shrink-0 transition-colors ${isDark ? 'bg-white/[0.06] text-white/50 hover:text-white hover:bg-white/[0.1]' : 'bg-gray-200 text-gray-500 hover:text-gray-700 hover:bg-gray-300'}`}
              aria-label={t('attachDocument')}
              title={t('attachDocument')}
            >
              <MdUploadFile size={18} />
            </button>
          )}

          {!streaming && (
            <button
              onClick={() => fileInputRef.current?.click()}
              className={`p-2 rounded-xl shrink-0 transition-colors ${isDark ? 'bg-white/[0.06] text-white/50 hover:text-white hover:bg-white/[0.1]' : 'bg-gray-200 text-gray-500 hover:text-gray-700 hover:bg-gray-300'}`}
              aria-label={t('attachImage')}
              title={t('attachImage')}
            >
              <MdImage size={18} />
            </button>
          )}

          {!streaming && (
            <button
              onClick={toggleVoice}
              className={`p-2 rounded-xl shrink-0 transition-colors ${
                !voiceSupported
                  ? isDark
                    ? 'bg-white/[0.03] text-white/25 hover:text-white/45'
                    : 'bg-gray-100 text-gray-300 hover:text-gray-500'
                : callMode
                  ? 'bg-[#006bbd]/30 text-white ring-1 ring-[#006bbd]/50'
                  : listening
                  ? 'bg-red-500/30 text-red-400 animate-pulse'
                  : isDark
                  ? 'bg-white/[0.06] text-white/50 hover:text-white hover:bg-white/[0.1]'
                  : 'bg-gray-200 text-gray-500 hover:text-gray-700 hover:bg-gray-300'
              }`}
              aria-label={!voiceSupported ? t('voiceUnavailable') : callMode ? t('exitVoiceMode') : t('voiceMode')}
              title={!voiceSupported ? t('voiceUnavailable') : callMode ? t('exitVoiceMode') : t('voiceMode')}
            >
              <MdMic size={18} />
            </button>
          )}

          {streaming ? (
            <button
              onClick={handleStop}
              className="p-2 rounded-xl bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors shrink-0"
              aria-label={t('stop')}
            >
              <MdStop size={18} />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim() && !attachedImage && attachedDocs.length === 0}
              className={`p-2 rounded-xl bg-[#006bbd] text-white
                         hover:bg-[#0059a0] disabled:opacity-30 disabled:cursor-not-allowed
                         transition-all shrink-0 ${
                           (input.trim() || attachedImage || attachedDocs.length > 0) && !streaming
                             ? 'animate-soft-pulse'
                             : ''
                         }`}
              aria-label={t('send')}
            >
              <MdSend size={18} />
            </button>
          )}
        </div>
      </div>
      <AnimatePresence>
        {previewAttachment && (
          <motion.div
            className="fixed inset-0 z-[80] flex items-center justify-center bg-black/75 p-4"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => { if (previewAttachment.url.startsWith('blob:')) URL.revokeObjectURL(previewAttachment.url); setPreviewAttachment(null); }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.94, y: 18 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.94, y: 18 }}
              className={`relative flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl ${isDark ? 'bg-[#111]' : 'bg-white'}`}
              onClick={(event) => event.stopPropagation()}
            >
              <div className={`flex items-center justify-between border-b px-4 py-3 text-sm ${isDark ? 'border-white/[0.08] text-white/80' : 'border-gray-200 text-gray-800'}`}>
                <span className="min-w-0 truncate">{previewAttachment.attachment.name}</span>
                <div className="flex items-center gap-2">
                  <a href={previewAttachment.url} download={previewAttachment.attachment.name} className="rounded-lg bg-[#006bbd] px-3 py-1.5 text-xs text-white">{t('download')}</a>
                  <button type="button" onClick={() => { if (previewAttachment.url.startsWith('blob:')) URL.revokeObjectURL(previewAttachment.url); setPreviewAttachment(null); }} className="rounded-lg p-1" aria-label={t('close')}><MdClose size={20} /></button>
                </div>
              </div>
              <div className="min-h-0 flex-1 overflow-auto p-3">
                {(previewAttachment.attachment.kind === 'image' || previewAttachment.attachment.mimeType?.startsWith('image/')) ? (
                  <img src={previewAttachment.url} alt={previewAttachment.attachment.name} className="mx-auto max-h-[78vh] max-w-full object-contain" />
                ) : (previewAttachment.attachment.mimeType?.startsWith('text/') || /\.(md|txt|csv|json|xml|html|css|js|ts|tsx|jsx|py|java|c|cpp|h|log)$/i.test(previewAttachment.attachment.name)) ? (
                  <iframe title={previewAttachment.attachment.name} srcDoc={textPreview === null ? '' : textPreviewDocument(textPreview)} className="h-[78vh] w-full rounded-lg bg-white" />
                ) : previewAttachment.attachment.mimeType === 'application/pdf' || previewAttachment.attachment.name.toLowerCase().endsWith('.pdf') ? (
                  <object data={previewAttachment.url} type="application/pdf" className="h-[78vh] w-full rounded-lg"><iframe title={previewAttachment.attachment.name} src={previewAttachment.url} className="h-full w-full" /><a href={previewAttachment.url} download={previewAttachment.attachment.name}>{t('download')}</a></object>
                ) : (
                  <div className={`p-6 text-center text-sm ${isDark ? 'text-white/60' : 'text-gray-600'}`}>{t('downloadFileToOpen')}</div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
