import { memo, useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import { MdSend, MdStop, MdMenu, MdMic, MdVolumeUp, MdImage, MdClose, MdContentCopy, MdCheck, MdUploadFile, MdDownload, MdPictureAsPdf, MdRefresh, MdEdit, MdScience, MdKeyboardArrowDown } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import ToggleSwitch from './ToggleSwitch';
import Sources from './Sources';
import type { ChatMessage, ChatEngine, Collection } from '../lib/api';
import { extractDocumentText, getCollections, getIndexJob, indexableFilesFrom, prepareImageForVision, runResearch, startFolderIndex, getMemorySummary } from '../lib/api';
import { getPreferredUserName, getUserAvatar, rememberFromMessage } from '../lib/userProfile';
import { useStreamChat } from '../hooks/useStreamChat';
import { onSharedStateUpdated } from '../lib/sharedState';

interface ChatInterfaceProps {
  messages: ChatMessage[];
  engine: ChatEngine;
  onMessagesChange: (messages: ChatMessage[]) => void;
  onEngineChange: (engine: ChatEngine) => void;
  onMenuToggle: () => void;
  sidebarOpen: boolean;
  onNavigate?: (page: 'settings' | 'browser' | 'memory' | 'docs') => void;
  onRequestExport?: (kind: 'markdown') => void;
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

/**
 * Built-in slash commands. Each is identified by its `name` and a behaviour kind.
 * - navigate_* — switch the page and stop (don't send the message).
 * - deep_research — call /v1/research with the remainder text.
 * - summarize — call regular chat completion summarising the conversation.
 * - export_* — trigger a download via the parent's onRequestExport callback.
 */
type BuiltinKind =
  | 'navigate_settings' | 'navigate_browser' | 'navigate_memory' | 'navigate_docs'
  | 'deep_research' | 'summarize' | 'export_markdown' | 'noop';

interface BuiltinCommand { name: string; text: string; builtin: true; kind: BuiltinKind; hint: string }

const BUILTIN_COMMANDS: BuiltinCommand[] = [
  { name: 'index',     text: '',                builtin: true, kind: 'navigate_settings', hint: 'Ajustes → Indexar carpeta' },
  { name: 'browse',    text: '',                builtin: true, kind: 'navigate_browser',  hint: 'Knowledge Browser' },
  { name: 'memory',    text: '',                builtin: true, kind: 'navigate_memory',  hint: 'Notas persistentes' },
  { name: 'watch',     text: '',                builtin: true, kind: 'navigate_settings', hint: 'Watcher de archivos' },
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
    export:    { es: 'Exportar como Markdown', en: 'Export as Markdown' },
    sources:   { es: 'Ver fuentes indexadas', en: 'View indexed sources' },
  };
  return hints[name]?.[lang] ?? '';
}

function builtinBadgeLabel(lang: 'es' | 'en'): string {
  return lang === 'en' ? 'built-in' : 'integrado';
}

function findBuiltin(name: string): BuiltinCommand | undefined {
  const lc = name.toLowerCase();
  return BUILTIN_COMMANDS.find((b) => b.name === lc);
}

const BUILTIN_BY_NAME: Record<string, BuiltinCommand> = BUILTIN_COMMANDS.reduce(
  (acc, b) => { acc[b.name] = b; return acc; },
  {} as Record<string, BuiltinCommand>,
);

const MarkdownContent = memo(function MarkdownContent({ text, isDark }: { text: string; isDark: boolean }) {
  return (
    <div className={`chat-markdown prose prose-sm min-w-0 max-w-full break-words [overflow-wrap:anywhere] ${isDark ? 'prose-invert' : ''}`}>
      <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{text}</ReactMarkdown>
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
}: ChatInterfaceProps) {
  const { t, lang } = useI18n();
  const { isDark } = useTheme();
  const [input, setInput] = useState('');
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editingText, setEditingText] = useState('');
  const { streaming, streamedText, sendMessage, abort } = useStreamChat();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const messagesRef = useRef<HTMLDivElement>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [userAvatar, setUserAvatar] = useState('');
  const [userDisplayName, setUserDisplayName] = useState(() => getPreferredUserName(lang));
  const [collections, setCollections] = useState<Collection[]>([]);
  const [activeCollectionIds, setActiveCollectionIds] = useState<string[]>(() => {
    try {
      const parsed = JSON.parse(localStorage.getItem('tc-active-collections') || '["default"]');
      return Array.isArray(parsed) && parsed.every((v) => typeof v === 'string') && parsed.length ? parsed : ['default'];
    } catch {
      return ['default'];
    }
  });
  const [docUploadStatus, setDocUploadStatus] = useState('');
  const [attachedDocs, setAttachedDocs] = useState<AttachedDocument[]>([]);
  const [docIndexCollectionId, setDocIndexCollectionId] = useState(() => activeCollectionIds[0] || 'default');
  const docInputRef = useRef<HTMLInputElement>(null);

  const [slashOpen, setSlashOpen] = useState(false);
  const [slashFilter, setSlashFilter] = useState('');

  const customPrompts = useRef<Array<{name:string;text:string;builtin?:boolean}>>([]);
  const reloadLocalProfile = useCallback(() => {
    const readPrompts = (key: string) => {
      try {
        const parsed = JSON.parse(localStorage.getItem(key) || '[]');
        return Array.isArray(parsed) ? parsed : [];
      } catch {
        return [];
      }
    };
    const op = readPrompts('tc-ollama-prompts');
    const rp = readPrompts('tc-rag-prompts');
    customPrompts.current = [...BUILTIN_COMMANDS, ...op, ...rp]
      .filter((p: any) => p?.name && p.name !== 'system')
      .map((p: any) => ({ name: String(p.name), text: String(p.text || ''), builtin: false }));
    const nextAvatar = getUserAvatar();
    const nextName = getPreferredUserName(lang);
    setUserAvatar((current) => (current === nextAvatar ? current : nextAvatar));
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
          const kept = prev.filter((id) => valid.has(id));
          return kept.length ? kept : ['default'];
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
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    const atBottom = distance < 96;
    setShowScrollButton(!atBottom && el.scrollHeight > el.clientHeight + 16);
  }, []);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    const el = messagesRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior });
    setShowScrollButton(false);
  }, []);

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

function getLastUserText(messages: ChatMessage[], beforeMsg?: ChatMessage): string {
  const upto = beforeMsg ? messages.slice(0, messages.indexOf(beforeMsg) + 1) : messages;
  for (let i = upto.length - 1; i >= 0; i--) {
    if (upto[i].role === 'user') return upto[i].content;
  }
  return '';
}

  const conversationMarkdown = useCallback(() => {
    const lines = ['# TrinaxAI Conversation', ''];
    for (const msg of messages) {
      lines.push(`## ${msg.role === 'user' ? 'User' : 'TrinaxAI'}`, '', visibleMessageContent(msg.content || (msg.image ? '[image]' : '')), '');
      if (msg.sources?.length) {
        lines.push('Sources:', ...msg.sources.map((source) => `- ${source.file}${source.page ? ` p. ${source.page}` : ''}${source.collection ? ` (${source.collection})` : ''}`), '');
      }
    }
    return lines.join('\n');
  }, [messages, visibleMessageContent]);

  const exportMarkdown = useCallback(() => {
    const blob = new Blob([conversationMarkdown()], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `trinaxai-chat-${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }, [conversationMarkdown]);

  const exportPdf = useCallback(() => {
    const escapeHtml = (value: string) => value
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
    const win = window.open('', '_blank');
    if (!win) return;
    const body = messages.map((msg) => `
      <section>
        <h2>${msg.role === 'user' ? 'User' : 'TrinaxAI'}</h2>
        <pre>${escapeHtml(visibleMessageContent(msg.content || (msg.image ? '[image]' : '')))}</pre>
      </section>
    `).join('');
    win.document.write(`<!doctype html><html><head><title>TrinaxAI Conversation</title><style>
      body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:32px;color:#111;line-height:1.5}
      h1{font-size:22px}h2{font-size:14px;margin-top:24px;color:#006bbd}
      pre{white-space:pre-wrap;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
    </style></head><body><h1>TrinaxAI Conversation</h1>${body}</body></html>`);
    win.document.close();
    win.focus();
    win.print();
  }, [messages, visibleMessageContent]);

  const activeCollectionsForRequest = activeCollectionIds.length ? activeCollectionIds : ['default'];

  const toggleCollection = useCallback((id: string) => {
    setActiveCollectionIds((prev) => {
      if (prev.includes(id)) {
        const next = prev.filter((value) => value !== id);
        return next.length ? next : prev;
      }
      return [...prev, id];
    });
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
      for (const file of files.slice(0, 5)) {
        const extracted = await extractDocumentText(file);
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
      setAttachedDocs(docs);
      setDocUploadStatus(t('chatDocsAttached').replace('{count}', String(docs.length)));
    } catch (err: unknown) {
      setDocUploadStatus(err instanceof Error ? err.message.slice(0, 180) : t('chatDocReadFailed'));
    }
  }, [t]);

  // ── Voz (estado) ──
  const [listening, setListening] = useState(false);
  const [callMode, setCallMode] = useState(false);
  const recognitionRef = useRef<any>(null);
  const callModeRef = useRef(false);
  const startVoiceRef = useRef<(continuous: boolean) => void>(() => {});
  const ttsActiveKeyRef = useRef<string | null>(null);
  const [ttsActiveKey, setTtsActiveKey] = useState<string | null>(null);
  const [ttsSpeaking, setTtsSpeaking] = useState(false);
  const [voiceVersion, setVoiceVersion] = useState(0);
  const ttsTailRef = useRef('');
  const ttsSpeakingRef = useRef(false);
  const ttsEndRef = useRef<(() => void) | null>(null);
  const flushVoiceTtsRef = useRef<(force?: boolean, onDone?: () => void) => void>(() => {});
  const voiceSupported = typeof window !== 'undefined' &&
    !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);

  useEffect(() => {
    callModeRef.current = callMode;
  }, [callMode]);

  // ── TTS (leer respuestas en voz alta) ──
  const ttsSupported = typeof window !== 'undefined' && 'speechSynthesis' in window;
  const voiceLang = lang === 'en' ? 'en-US' : 'es-ES';
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

  const stopSpeak = useCallback(() => {
    if (ttsSupported) window.speechSynthesis.cancel();
    clearTtsState();
  }, [clearTtsState, ttsSupported]);

  const unlockSpeech = useCallback(() => {
    if (!ttsSupported) return;
    window.speechSynthesis.resume();
    const u = new SpeechSynthesisUtterance('.');
    u.lang = voiceLang;
    u.volume = 0;
    window.speechSynthesis.speak(u);
    window.setTimeout(() => {
      if (!ttsSpeakingRef.current) window.speechSynthesis.cancel();
      window.speechSynthesis.resume();
    }, 60);
  }, [ttsSupported, voiceLang]);

  const speak = useCallback((text: string, onDone?: () => void, key?: string) => {
    if (!ttsSupported || !text) {
      onDone?.();
      return;
    }
    if (key && ttsActiveKeyRef.current === key && (window.speechSynthesis.speaking || window.speechSynthesis.pending)) {
      stopSpeak();
      return;
    }
    const clean = text
      .replace(/```[\s\S]*?```/g, ' bloque de código. ')
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
    const v = pickVoice();
    const parts = splitSpeech(clean);
    if (parts.length === 0) {
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
        u.onend = () => { clearTtsState(); onDone?.(); };
        u.onerror = () => { clearTtsState(); onDone?.(); };
      }
      window.speechSynthesis.speak(u);
    });
  }, [clearTtsState, pickVoice, splitSpeech, stopSpeak, ttsSupported, voiceLang]);

  const cleanSpeechText = useCallback((text: string) => text
    .replace(/```[\s\S]*?```/g, ' bloque de código. ')
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
      ttsSpeakingRef.current = false;
      setTtsSpeaking(false);
      const done = ttsEndRef.current ?? onDone;
      ttsEndRef.current = null;
      done?.();
    };
    ttsSpeakingRef.current = true;
    setTtsSpeaking(true);
    window.speechSynthesis.resume();
    window.speechSynthesis.speak(u);
  }, [cleanSpeechText, pickVoice, ttsSupported, voiceLang]);

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
  const [imageError, setImageError] = useState('');
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
      setAttachedImage(await prepareImageForVision(file));
    } catch (err: unknown) {
      setAttachedImage(null);
      setImageError(err instanceof Error ? err.message : 'No se pudo preparar la imagen.');
    } finally {
      e.target.value = '';
    }
  }, []);

  // ── Envío central (texto/voz/imagen) ──

  // Built-in slash-command helpers (must be declared before handleSendText).
  const runBuiltinDeepResearch = useCallback(async (query: string, baseMessages: ChatMessage[]) => {
    const placeholder: ChatMessage = { role: 'assistant', content: '🔍 *Deep research en curso...*' };
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
      const msg = err instanceof Error ? err.message.slice(0, 400) : 'Deep research failed';
      onMessagesChange([...baseMessages, { role: 'assistant', content: `❌ ${msg}` }]);
    }
  }, [activeCollectionsForRequest, onMessagesChange]);

  const runBuiltinSummarize = useCallback(async (baseMessages: ChatMessage[]) => {
    const summaryPrompt: ChatMessage = {
      role: 'user',
      content: `Summarize the key points of this conversation in 5-7 bullet points, plus 1-2 sentences on the overall conclusion. Conversation:\n\n${
        baseMessages.map((m) => `[${m.role}] ${m.content}`).join('\n\n').slice(-3000)
      }`,
    };
    const withPlaceholder = [...baseMessages, { role: 'assistant' as const, content: '✍️ *Resumiendo conversación...*' }];
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
  }, [onMessagesChange, sendMessage, assistantErrorMessage]);

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
      const builtin = findBuiltin(head);
      if (builtin) {
        setInput('');
        resetInputHeight();
        switch (builtin.kind) {
          case 'navigate_settings': onNavigate?.('settings'); return;
          case 'navigate_browser':  onNavigate?.('browser');  return;
          case 'navigate_memory':   onNavigate?.('memory');   return;
          case 'navigate_docs':     onNavigate?.('docs');     return;
          case 'export_markdown':   exportMarkdown(); return;
          case 'deep_research': {
            const prompt = tail || 'Give me a thorough overview.';
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
    const messageContent = `${trimmed || t('analyzeAttachedFiles')}${docContext}`;

    const userMsg: ChatMessage = {
      role: 'user',
      content: messageContent,
      image: image || undefined,
      inputMode: opts?.viaVoice ? 'voice' : 'text',
    };
    const updated = [...messages, userMsg];
    onMessagesChange(updated);
    requestAnimationFrame(() => scrollToBottom('smooth'));
    setInput('');
    resetInputHeight();
    setAttachedImage(null);
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
      const assistantMsg: ChatMessage = {
        role: 'assistant', content,
        sources: meta.sources, model: meta.model, project: meta.project,
      };
      onMessagesChange([...updated, assistantMsg]);
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
          speak(content, onDone);
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
  }, [attachedImage, attachedDocs, messages, streaming, engine, sendMessage, onMessagesChange, speak, activeCollectionsForRequest, t, resetInputHeight, assistantErrorMessage, researchMode, onNavigate, exportMarkdown, runBuiltinDeepResearch, runBuiltinSummarize, scrollToBottom]);

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
    abort();
    stopSpeak();
  }, [abort, stopSpeak]);

  const startVoiceCapture = useCallback((continuous: boolean) => {
    if (!voiceSupported || streaming) return;
    recognitionRef.current?.abort?.();
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const rec = new SR();
    rec.lang = voiceLang;
    rec.interimResults = true;
    rec.continuous = false;
    let finalText = '';
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
      const text = finalText.trim();
      if (text) {
        handleSendText(text, { viaVoice: true, continueCall: continuous });
      } else if (continuous && callModeRef.current) {
        window.setTimeout(() => startVoiceRef.current(true), 500);
      } else {
        inputRef.current?.focus();
      }
    };
    rec.onerror = () => {
      setListening(false);
      recognitionRef.current = null;
      if (continuous && callModeRef.current) {
        window.setTimeout(() => startVoiceRef.current(true), 900);
      }
    };
    recognitionRef.current = rec;
    setListening(true);
    rec.start();
  }, [handleSendText, streaming, voiceSupported]);

  useEffect(() => {
    startVoiceRef.current = startVoiceCapture;
  }, [startVoiceCapture]);

  // ── Dictado por voz → auto-envío → respuesta hablada (TTS) ──
  const toggleVoice = useCallback(() => {
    if (!voiceSupported) return;
    if (callMode) {
      setCallMode(false);
      callModeRef.current = false;
      recognitionRef.current?.abort?.();
      stopSpeak();
      setListening(false);
      return;
    }
    setCallMode(true);
    callModeRef.current = true;
    unlockSpeech();
    startVoiceCapture(true);
  }, [callMode, startVoiceCapture, stopSpeak, unlockSpeech, voiceSupported]);

  // Start editing a user message
  const startEdit = useCallback(
    (index: number) => {
      if (streaming) abort(true);
      stopSpeak();
      setEditingIndex(index);
      setEditingText(messages[index].content);
    },
    [messages, streaming, abort, stopSpeak],
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

  return (
    <div className="flex flex-col h-full min-h-0 min-w-0 max-w-full overflow-hidden transition-colors duration-300">
      {/* Navbar — items centered vertically with proper safe-area padding */}
      <nav className={`shrink-0 flex items-center px-2 sm:px-3 border-b ${isDark ? 'bg-black/80 border-white/[0.06]' : 'bg-white/90 border-gray-200'} backdrop-blur-xl`}
           style={{ minHeight: '44px', paddingTop: 'env(safe-area-inset-top, 0px)' }}>
        {/* Left: animated branding */}
        <div className="flex items-center shrink-0">
          <span
            className="text-lg sm:text-xl md:text-xl font-bold tracking-normal animate-brand"
          >
            TrinaxAI
          </span>
        </div>

        {/* Right: toggle + menu */}
        <div className="flex items-center gap-1 sm:gap-2 md:gap-3 ml-auto">
          <div className="flex items-center gap-0.5 sm:gap-1">
            <button
              onClick={exportMarkdown}
              disabled={messages.length === 0}
              className={`p-2 sm:p-2 rounded-xl transition-colors ${
                messages.length === 0
                  ? isDark ? 'text-white/20 cursor-not-allowed' : 'text-gray-300 cursor-not-allowed'
                  : isDark ? 'text-white/55 hover:text-white hover:bg-white/[0.06]' : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
              }`}
              aria-label={t('exportMarkdown')}
              title={t('exportMarkdown')}
            >
              <MdDownload size={18} />
            </button>
            <button
              onClick={exportPdf}
              disabled={messages.length === 0}
              className={`p-2 sm:p-2 rounded-xl transition-colors ${
                messages.length === 0
                  ? isDark ? 'text-white/20 cursor-not-allowed' : 'text-gray-300 cursor-not-allowed'
                  : isDark ? 'text-white/55 hover:text-white hover:bg-white/[0.06]' : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
              }`}
              aria-label={t('exportPdf')}
              title={t('exportPdf')}
            >
              <MdPictureAsPdf size={18} />
            </button>
            <button
              onClick={() => setResearchMode((v) => !v)}
              className={`p-2 sm:p-2 rounded-xl transition-colors ${
                researchMode
                  ? 'bg-[#006bbd]/20 text-[#006bbd] ring-1 ring-[#006bbd]/40 animate-soft-pulse'
                  : isDark ? 'text-white/55 hover:text-white hover:bg-white/[0.06]' : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
              }`}
              aria-label={lang === 'en' ? 'Toggle Deep Research' : 'Activar Deep Research'}
              title={lang === 'en' ? 'Deep Research (multi-pass)' : 'Deep Research (multi-pass)'}
            >
              <MdScience size={18} />
            </button>
          </div>
          <ToggleSwitch engine={engine} onChange={onEngineChange} />
          <button
            onClick={onMenuToggle}
            className={`p-2 rounded-xl transition-all ${
              isDark ? 'text-white/60 hover:text-white hover:bg-white/[0.06]' : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
            }`}
            aria-label={sidebarOpen ? t('closeMenu') : t('openMenu')}
          >
            <MdMenu size={20} />
          </button>
        </div>
      </nav>

      {/* Empty state — logo + rotating motivational message */}
      {messages.length === 0 && !streaming && (
        <motion.div
          className="flex-1 flex flex-col items-center justify-center gap-4 px-6"
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
                      <img src={msg.image} alt={t('attachedImage')}
                           className="rounded-lg mb-2 max-h-52 max-w-full w-auto object-contain" />
                    )}
                    {msg.content && <p className="chat-plain-text min-w-0 max-w-full whitespace-pre-wrap">{msg.content}</p>}
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
                  </div>
                </div>
              )}

              {/* Avatar (user) */}
              {msg.role === 'user' && (
                userAvatar ? (
                  <img
                    src={userAvatar}
                    alt={t('userAvatar')}
                    className="w-7 h-7 rounded-full shrink-0 mt-0.5 object-cover"
                    width={28}
                    height={28}
                  />
                ) : (
                  <div
                    className="w-7 h-7 rounded-full shrink-0 mt-0.5 grid place-items-center bg-[#006bbd] text-white text-xs font-semibold"
                    aria-label={t('userAvatar')}
                    title={userDisplayName}
                  >
                    {(userDisplayName.trim()[0] || 'U').toUpperCase()}
                  </div>
                )
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
                    <MarkdownContent text={visibleMessageContent(streamedText)} isDark={isDark} />
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
              className={`fixed bottom-[calc(env(safe-area-inset-bottom,0px)+6rem)] left-1/2 ${sidebarOpen ? 'z-20 pointer-events-none' : 'z-30'} grid h-11 w-11 -translate-x-1/2 place-items-center rounded-full border shadow-lg backdrop-blur-xl transition-colors active:scale-95 ${
                isDark
                  ? 'border-white/[0.08] bg-black/85 text-white/80 hover:bg-[#006bbd] hover:text-white'
                  : 'border-gray-200 bg-white/95 text-gray-600 hover:bg-[#006bbd] hover:text-white'
              }`}
              aria-label={lang === 'en' ? 'Scroll to bottom' : 'Ir al final del chat'}
              title={lang === 'en' ? 'Scroll to bottom' : 'Ir al final del chat'}
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
        {docUploadStatus && (
          <p className={`mb-2 text-xs ${isDark ? 'text-white/45' : 'text-gray-500'}`}>{docUploadStatus}</p>
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
          className={`flex items-end gap-1 sm:gap-2 rounded-2xl border px-2 sm:px-3 py-2 transition-all duration-300 relative focus-within:animate-border-glow ${
            isDark
              ? 'bg-white/[0.04] border-white/[0.08] focus-within:border-[#006bbd]/40 focus-within:shadow-[0_0_20px_rgba(0,107,189,0.15)]'
              : 'bg-gray-100 border-gray-200 focus-within:border-[#006bbd]/40 focus-within:shadow-[0_0_20px_rgba(0,107,189,0.1)]'
          }`}
        >
          {slashOpen && customPrompts.current.filter(p => p.name.includes(slashFilter)).length > 0 && (
            <div className={`absolute bottom-full left-0 right-0 mb-2 rounded-xl overflow-hidden z-30 max-h-48 overflow-y-auto ${isDark ? 'bg-black/95 border-white/[0.08]' : 'bg-white border-gray-200 shadow-lg'}`}>
              {customPrompts.current.filter(p => p.name.includes(slashFilter)).map(p => (
                <button key={p.name} onClick={() => {
                  if (p.builtin) {
                    // Send as-is so handleSendText intercepts the built-in.
                    setInput('/' + p.name + ' ');
                    setSlashOpen(false);
                    inputRef.current?.focus();
                    window.setTimeout(() => {
                      const ta = inputRef.current;
                      if (!ta) return;
                      ta.focus();
                      // Trigger Enter via form: easier — just call handleSend.
                      handleSend();
                    }, 30);
                  } else {
                    setInput('/'+p.name+' '); setSlashOpen(false); inputRef.current?.focus();
                  }
                }}
                  className={`w-full text-left px-4 py-2.5 text-sm flex items-center gap-3 ${isDark ? 'text-white/60 hover:text-white hover:bg-white/[0.04]' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}`}>
                  <span className="text-[10px] text-[#006bbd] font-mono">/{p.name}</span>
                  {p.builtin && (
                    <span className="text-[8px] font-bold uppercase tracking-wider px-1 py-0.5 rounded bg-[#006bbd]/15 text-[#006bbd]">{builtinBadgeLabel(lang)}</span>
                  )}
                  <span className={`truncate ${isDark ? 'text-white/30' : 'text-gray-400'}`}>
                    {p.builtin ? (getBuiltinHint(p.name, lang)) : (p.text || '').slice(0, 50) + '…'}
                  </span>
                </button>
              ))}
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
            className={`flex-1 min-w-0 min-h-[40px] max-h-[160px] bg-transparent text-sm resize-none outline-none overflow-y-auto py-2 leading-6 ${isDark ? 'text-white placeholder-white/30' : 'text-gray-800 placeholder-gray-400'}`}
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
              onClick={voiceSupported ? toggleVoice : undefined}
              disabled={!voiceSupported}
              className={`p-2 rounded-xl shrink-0 transition-colors ${
                !voiceSupported
                  ? isDark
                    ? 'bg-white/[0.03] text-white/20 cursor-not-allowed'
                    : 'bg-gray-100 text-gray-300 cursor-not-allowed'
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
    </div>
  );
}
