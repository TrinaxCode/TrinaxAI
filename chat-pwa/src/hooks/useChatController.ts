import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { useToast } from '../components/Toast';
import { formatUserFacingError, startLocalAi, thinkingModeEnabled, userFacingErrorDetails, type ChatMessage, type ChatEngine, type Collection } from '../lib/api';
import { getCollections, getWebSearchSettings, nextActiveCollections, normalizeActiveCollections, WEB_SEARCH_SETTINGS_EVENT, type WebSearchSettings } from '../lib/api';
import { getPreferredUserName } from '../lib/userProfile';
import { useStreamChat } from './useStreamChat';
import { audioManager } from '../services/audioManager';
import { onSharedStateUpdated } from '../lib/sharedState';
import { useChatScroll } from './useChatScroll';
import { useWaitingSound } from './useWaitingSound';
import { pickActivityMessage, type ActivityKind } from '../components/chat/activityMessages';
import { sanitizeExportFilename, serializeChatExport } from '../lib/chatExport';
import type { AgentHandoff } from '../components/chat/modeRouter';
import { localizedBuiltins, QUICK_CHIP_POOL } from '../components/chat/commands';
import type { BuiltinKind, ChatPrompt, QuickChipDef } from '../components/chat/types';
import { isLocalHostBrowser } from '../lib/authHeaders';
import { useChatVoice, type ChatSendOptions } from './useChatVoice';
import { useChatDocuments } from './useChatDocuments';
import { useChatAttachments } from './useChatAttachments';
import { useChatMessageActions } from './useChatMessageActions';
import { useChatSend } from './useChatSend';

export interface ChatInterfaceProps {
  messages: ChatMessage[];
  engine: ChatEngine;
  temporary?: boolean;
  onMessagesChange: (messages: ChatMessage[]) => void;
  onEngineChange: (engine: ChatEngine) => void;
  onMenuToggle: () => void;
  onNavigate?: (page: 'settings' | 'indexing' | 'browser' | 'memory' | 'docs' | 'agent') => void;
  onAgentHandoff?: (handoff: AgentHandoff) => void;
  onWebSearchBlocked?: () => void;
  folderContext?: Array<{ title: string; messages: ChatMessage[] }>;
}

export function useChatController({
  messages,
  engine,
  temporary = false,
  onMessagesChange,
  onEngineChange,
  onMenuToggle,
  onNavigate,
  onAgentHandoff,
  onWebSearchBlocked,
  folderContext = [],
}: ChatInterfaceProps) {
  const { t, lang } = useI18n();
  const { isDark } = useTheme();
  const voiceLang = lang === 'en' ? 'en-US' : 'es-MX';
  const toast = useToast();
  const isMobile = typeof window !== 'undefined' && window.matchMedia?.('(max-width: 640px)').matches;
  const placeholder = isMobile ? t('typeMessageShort') : t('typeMessage');
  const [input, setInput] = useState('');
  const messageStateRef = useRef(messages);
  useEffect(() => { messageStateRef.current = messages; }, [messages]);
  const publishMessages = useCallback((next: ChatMessage[]) => {
    messageStateRef.current = next;
    onMessagesChange(next);
  }, [onMessagesChange]);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editingText, setEditingText] = useState('');
  const { streaming, streamedText, sendMessage, startExternalStream, abort, wasAborted } = useStreamChat();
  const [researching, setResearching] = useState(false);
  const [activityKind, setActivityKind] = useState<ActivityKind | null>(null);
  const [activityLabel, setActivityLabel] = useState('');
  const researchAbortRef = useRef<AbortController | null>(null);
  const busy = streaming || researching;
  // Keep the waiting cue only until the first visible streamed characters.
  useWaitingSound(busy && streamedText.length === 0);
  const firstTokenSoundRef = useRef(false);
  const previousBusyRef = useRef(false);
  useEffect(() => {
    if (busy && !previousBusyRef.current) firstTokenSoundRef.current = false;
    if (busy && streamedText && !firstTokenSoundRef.current) {
      firstTokenSoundRef.current = true;
      audioManager.play('first-token');
    }
    if (!busy && previousBusyRef.current && !wasAborted()) audioManager.play('response-complete');
    previousBusyRef.current = busy;
  }, [busy, streamedText, wasAborted]);
  const startActivity = useCallback((kind: ActivityKind) => {
    const visibleKind = kind === 'thinking' && !thinkingModeEnabled() ? 'working' : kind;
    setActivityKind(visibleKind);
    setActivityLabel((previous) => pickActivityMessage(visibleKind, t, previous));
  }, [t]);
  const stopActivity = useCallback(() => {
    setActivityKind(null);
    setActivityLabel('');
  }, []);
  useEffect(() => {
    if (!busy || !activityKind || streamedText) return undefined;
    const timer = window.setInterval(() => {
      setActivityLabel((previous) => pickActivityMessage(activityKind, t, previous));
    }, 4500);
    return () => window.clearInterval(timer);
  }, [activityKind, busy, streamedText, t]);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const editInputRef = useRef<HTMLTextAreaElement>(null);
  const attachmentMenuRef = useRef<HTMLDivElement>(null);
  const handleSendTextRef = useRef<(raw: string, opts?: ChatSendOptions) => Promise<void>>(async () => {});
  const {
    appendResponseToken,
    callMode,
    callModeRef,
    cancelPendingCapture,
    dictationStopRef,
    finishResponseSpeech,
    listening,
    listeningRef,
    queueVoiceRestart,
    resetResponseSpeech,
    speak,
    speakWithFallback,
    startCall,
    startDictation,
    stopDictation,
    stopSpeak,
    stopVoice,
    ttsActiveKey,
    ttsSpeaking,
    ttsSupported,
    voiceSupported,
  } = useChatVoice({
    inputRef,
    sendTextRef: handleSendTextRef,
    setInput,
    streaming,
    t: t,
    toast,
    voiceLang,
  });
  useEffect(() => {
    if (callMode) return undefined;
    const frame = window.requestAnimationFrame(() => {
      inputRef.current?.focus({ preventScroll: true });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [callMode]);
  const handleStop = useCallback(() => {
    audioManager.play(callModeRef.current ? 'call-exit' : 'cancel');
    stopVoice();
    researchAbortRef.current?.abort();
    abort();
  }, [abort, callModeRef, stopVoice]);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const { messagesRef, showScrollButton, updateScrollState, scrollToBottom } = useChatScroll({
    messageCount: messages.length,
    streamedText,
    streaming: busy,
  });
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
  const {
    attachedDocs,
    clearAttachedDocs,
    docConvertProgress,
    docIndexCollectionId,
    docInputRef,
    docUploadStatus,
    indexAttachedDocs,
    onPickDocs,
    processDocumentFiles,
    rebuildStoredDocumentContext,
    setDocUploadStatus,
    setDocIndexCollectionId,
  } = useChatDocuments({
    collections,
    initialCollectionId: activeCollectionIds[0] || 'default',
    t,
  });
  const {
    attachedImages,
    canOpenPreview,
    clearDragActive,
    dragActive,
    fileInputRef,
    handleDragEnter,
    handleDragLeave,
    handleDragOver,
    handleDrop,
    handlePaste,
    imageError,
    onPickImage,
    openPreviewAttachment,
    openStoredAttachment,
    downloadPreviewAttachment,
    previewAttachment,
    setAttachedImages,
    setPreviewAttachment,
    textPreview,
  } = useChatAttachments({ callMode, processDocumentFiles, t });

  const [slashOpen, setSlashOpen] = useState(false);
  const [slashFilter, setSlashFilter] = useState('');
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [attachmentMenuOpen, setAttachmentMenuOpen] = useState(false);

  useEffect(() => {
    if (!attachmentMenuOpen) return undefined;
    const closeOnOutsidePointer = (event: PointerEvent) => {
      if (!attachmentMenuRef.current?.contains(event.target as Node)) {
        setAttachmentMenuOpen(false);
      }
    };
    window.addEventListener('pointerdown', closeOnOutsidePointer);
    return () => window.removeEventListener('pointerdown', closeOnOutsidePointer);
  }, [attachmentMenuOpen]);

  useEffect(() => {
    if (busy) setAttachmentMenuOpen(false);
  }, [busy]);

  useEffect(() => () => {
    researchAbortRef.current?.abort();
  }, []);

  const customPrompts = useRef<ChatPrompt[]>([]);
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

  const phrases = [
    t('motd1'), t('motd2'), t('motd3'), t('motd4'), t('motd5'), t('motd6'), t('motd7'), t('motd8'), t('motd9'), t('motd10'),
    t('motd11'), t('motd12'), t('motd13'), t('motd14'), t('motd15'), t('motd16'), t('motd17'), t('motd18'), t('motd19'), t('motd20'),
    t('motd21'), t('motd22'), t('motd23'), t('motd24'), t('motd25'), t('motd26'), t('motd27'), t('motd28'), t('motd29'), t('motd30'),
    t('motd31'), t('motd32'), t('motd33'), t('motd34'), t('motd35'), t('motd36'), t('motd37'), t('motd38'), t('motd39'), t('motd40'),
  ];

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
  const lastChipRotationRef = useRef(-1);
  const [quickChipRotation, setQuickChipRotation] = useState(0);

  useEffect(() => {
    if (messages.length > 0 || streaming) return undefined;
    const id = window.setInterval(() => setQuickChipRotation((current) => current + 1), 15_000);
    return () => window.clearInterval(id);
  }, [messages.length, streaming]);

  if (messages.length === 0 && !streaming) {
    if (prevMessageCount.current > 0 || chipDefsRef.current.length === 0 || lastChipRotationRef.current !== quickChipRotation) {
      const shuffled = [...QUICK_CHIP_POOL].sort(() => Math.random() - 0.5);
      chipDefsRef.current = shuffled.slice(0, 2);
      lastChipRotationRef.current = quickChipRotation;
    }
  }
  prevMessageCount.current = messages.length;

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const val = e.target.value;
      if (val && listeningRef.current && !callModeRef.current) dictationStopRef.current();
      setInput(val);
      const el = e.target;
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, window.innerHeight * 0.5)}px`;
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
      if (inputRef.current) inputRef.current.style.height = '42px';
    });
  }, []);

  useEffect(() => {
    requestAnimationFrame(() => {
      const el = inputRef.current;
      if (!el) return;
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, window.innerHeight * 0.5)}px`;
    });
  }, [input]);

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

  const messageDisplayContent = useCallback((msg: ChatMessage) => (
    msg.displayContent ?? (msg.content || (msg.image ? '[image]' : ''))
  ).trim(), []);

  const conversationExport = useCallback(() => serializeChatExport(messages, {
    title: t('exportConversationTitle'),
    roleLabels: { user: t('userLabel'), assistant: t('assistantLabel'), system: t('system') },
  }), [messages, t]);

  const exportFilename = useCallback((extension: string) => sanitizeExportFilename(
    `trinaxai-chat-${new Date().toISOString().slice(0, 10)}.${extension}`,
  ), []);

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
    const blob = new Blob([conversationExport().markdown], { type: 'text/markdown;charset=utf-8' });
    triggerDownload(blob, exportFilename('md'));
  }, [conversationExport, exportFilename, triggerDownload]);

  const exportPdf = useCallback(() => {
    const win = window.open('', '_blank');
    if (!win) {
      toast.toast(t('exportPdfPopupBlocked'), 'error');
      return;
    }
    win.document.write(conversationExport().html);
    win.document.close();
    win.focus();
    win.print();
  }, [conversationExport, toast, t]);

  const exportWord = useCallback(() => {
    const blob = new Blob([conversationExport().html], { type: 'application/msword;charset=utf-8' });
    triggerDownload(blob, exportFilename('doc'));
  }, [conversationExport, exportFilename, triggerDownload]);

  const activeCollectionsForRequest = useMemo(
    () => normalizeActiveCollections(activeCollectionIds),
    [activeCollectionIds],
  );

  const toggleCollection = useCallback((id: string) => {
    setActiveCollectionIds((prev) => nextActiveCollections(prev, id));
  }, []);

  const [researchMode, setResearchMode] = useState<boolean>(() => {
    try { return localStorage.getItem('tc-research-mode') === '1'; } catch { return false; }
  });
  useEffect(() => { try { localStorage.setItem('tc-research-mode', researchMode ? '1' : '0'); } catch { /* ignore */ } }, [researchMode]);
  const [webSearchMode, setWebSearchMode] = useState<boolean>(() => {
    try { return isLocalHostBrowser() && localStorage.getItem('tc-web-search-mode') === '1'; } catch { return false; }
  });
  const [webSearchAvailable, setWebSearchAvailable] = useState<boolean | null>(null);
  useEffect(() => { try { localStorage.setItem('tc-web-search-mode', webSearchMode ? '1' : '0'); } catch { /* ignore */ } }, [webSearchMode]);
  useEffect(() => {
    let alive = true;
    const apply = (value: WebSearchSettings) => {
      if (!alive) return;
      setWebSearchAvailable(value.enabled);
      if (!value.enabled) setWebSearchMode(false);
    };
    const onUpdated = (event: Event) => {
      const value = (event as CustomEvent<WebSearchSettings>).detail;
      if (value && typeof value.enabled === 'boolean') apply(value);
    };
    const controller = new AbortController();
    getWebSearchSettings(controller.signal).then(apply).catch(() => {
      if (alive) setWebSearchAvailable(true);
    });
    window.addEventListener(WEB_SEARCH_SETTINGS_EVENT, onUpdated);
    return () => {
      alive = false;
      controller.abort();
      window.removeEventListener(WEB_SEARCH_SETTINGS_EVENT, onUpdated);
    };
  }, []);
  const handleWebSearchModeChange = useCallback((enabled: boolean) => {
    if (enabled && !isLocalHostBrowser()) {
      onWebSearchBlocked?.();
      return;
    }
    setWebSearchMode(enabled);
  }, [onWebSearchBlocked]);

  const assistantErrorMessage = useCallback((err: unknown) => {
    if (err instanceof Error && err.message === 'TRINAXAI_SILENT_ABORT') return t('requestCancelled');
    const details = userFacingErrorDetails(err, 'external_service_unavailable');
    if (details.canOpenIndexing && onNavigate) {
      toast.toast(formatUserFacingError(err, 'external_service_unavailable'), 'error', {
        durationMs: 10_000,
        action: { label: t('openIndexing'), onClick: () => onNavigate('indexing') },
      });
    } else if (details.canStartLocalAi && isLocalHostBrowser()) {
      toast.toast(formatUserFacingError(err, 'external_service_unavailable'), 'error', {
        durationMs: 10_000,
        action: {
          label: t('startupAI'),
          pendingLabel: t('startingUp'),
          onClick: async () => {
            try {
              await startLocalAi();
              toast.toast(t('aiStarted'), 'success');
            } catch (startError) {
              toast.toast(formatUserFacingError(startError, 'external_service_unavailable'), 'error');
              throw startError;
            }
          },
        },
      });
    } else if (details.canOpenSettings && onNavigate) {
      toast.toast(formatUserFacingError(err, 'external_service_unavailable'), 'error', {
        durationMs: 10_000,
        action: { label: t('openSettings'), onClick: () => onNavigate('settings') },
      });
    }
    return `${details.message}\n\n${details.recovery}`;
  }, [onNavigate, t, toast]);

  const {
    buildTurnContextMessages,
    dispatchTurn,
    handleSend,
    handleKeyDown,
  } = useChatSend({
    activeCollectionsForRequest,
    appendResponseToken,
    assistantErrorMessage,
    attachedDocs,
    attachedImages,
    busy,
    callModeRef,
    cancelPendingCapture,
    clearAttachedDocs,
    customPrompts,
    engine,
    exportMarkdown,
    finishResponseSpeech,
    folderContext,
    handleSendTextRef,
    input,
    lang,
    messageStateRef,
    messages,
    onAgentHandoff,
    onMessagesChange,
    onNavigate,
    onWebSearchBlocked,
    publishMessages,
    queueVoiceRestart,
    researchAbortRef,
    researchMode,
    resetResponseSpeech,
    resetInputHeight,
    scrollToBottom,
    sendMessage,
    setAttachedImages,
    setDocUploadStatus,
    setInput,
    setResearching,
    setSlashOpen,
    setWebSearchAvailable,
    setWebSearchMode,
    speakWithFallback,
    startActivity,
    startExternalStream,
    stopActivity,
    t,
    temporary,
    wasAborted,
    webSearchAvailable,
    webSearchMode,
  });

  const toggleVoice = useCallback(() => {
    if (callMode) {
      handleStop();
      return;
    }
    startCall();
  }, [callMode, handleStop, startCall]);

  const toggleDictation = useCallback(() => {
    if (listening) {
      stopDictation();
      return;
    }
    startDictation();
  }, [listening, startDictation, stopDictation]);

  const { startEdit, saveEdit, regenerateFrom, continueResponse } = useChatMessageActions({
    abort,
    activeCollectionsForRequest,
    buildTurnContextMessages,
    busy,
    dispatchTurn,
    editInputRef,
    editingIndex,
    editingText,
    engine,
    lang,
    messageDisplayContent,
    messages,
    onMessagesChange,
    rebuildStoredDocumentContext,
    sendMessage,
    setEditingIndex,
    setEditingText,
    startActivity,
    stopActivity,
    stopSpeak,
    streaming,
    temporary,
  });

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

  const handlePromptSelect = (prompt: ChatPrompt) => {
    setSlashOpen(false);
    if (prompt.builtin) {
      if (prompt.kind === 'navigate_settings') { onNavigate?.('settings'); return; }
      if (prompt.kind === 'navigate_indexing') { onNavigate?.('indexing'); return; }
      if (prompt.kind === 'navigate_browser') { onNavigate?.('browser'); return; }
      if (prompt.kind === 'navigate_memory') { onNavigate?.('memory'); return; }
      if (prompt.kind === 'navigate_docs') { onNavigate?.('docs'); return; }
      if (prompt.kind === 'export_markdown') { exportMarkdown(); return; }
    }
    setInput(`/${prompt.name} `);
    inputRef.current?.focus();
  };

  const openInBrowser = (file: string, collection?: string) => {
    (window as any).__tc_browser_open = {
      file,
      collection: collection || activeCollectionsForRequest[0] || 'default',
    };
    onNavigate?.('browser');
  };

  return {
    activeCollectionIds,
    activeCollectionsForRequest,
    activityLabel,
    attachmentMenuRef,
    attachedDocs,
    attachedImages,
    attachmentMenuOpen,
    busy,
    callMode,
    canOpenPreview,
    clearAttachedDocs,
    clearDragActive,
    collections,
    continueResponse,
    copiedKey,
    copyMessage,
    customPrompts,
    displayChips,
    docConvertProgress,
    docIndexCollectionId,
    docInputRef,
    docUploadStatus,
    downloadPreviewAttachment,
    dragActive,
    editInputRef,
    editingIndex,
    editingText,
    engine,
    exportMenuOpen,
    exportMarkdown,
    exportPdf,
    exportWord,
    fileInputRef,
    handleDragEnter,
    handleDragLeave,
    handleDragOver,
    handleDrop,
    handleInputChange,
    handleKeyDown,
    handlePaste,
    handlePromptSelect,
    handleSend,
    handleStop,
    imageError,
    indexAttachedDocs,
    input,
    inputRef,
    isDark,
    isMobile,
    listening,
    messages,
    messagesRef,
    motd,
    onEngineChange,
    onMenuToggle,
    onNavigate,
    onPickDocs,
    onPickImage,
    openInBrowser,
    openPreviewAttachment,
    openStoredAttachment,
    placeholder,
    previewAttachment,
    quickChipRotation,
    regenerateFrom,
    researchMode,
    saveEdit,
    showScrollButton,
    scrollToBottom,
    setAttachedImages,
    setAttachmentMenuOpen,
    setDocIndexCollectionId,
    setEditingIndex,
    setEditingText,
    setExportMenuOpen,
    setPreviewAttachment,
    setResearchMode,
    slashFilter,
    slashOpen,
    speak,
    stopSpeak,
    startEdit,
    streamedText,
    streaming,
    temporary,
    textPreview,
    t,
    toggleCollection,
    toggleDictation,
    toggleVoice,
    ttsActiveKey,
    ttsSpeaking,
    ttsSupported,
    updateScrollState,
    userDisplayName,
    voiceSupported,
    webSearchAvailable,
    webSearchMode,
    handleWebSearchModeChange,
  };

}

export type ChatController = ReturnType<typeof useChatController>;
