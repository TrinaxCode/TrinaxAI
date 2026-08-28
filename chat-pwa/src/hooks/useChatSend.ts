import { useCallback, type Dispatch, type MutableRefObject, type SetStateAction } from 'react';
import {
  buildWebSearchQuery,
  runResearch,
  thinkingModeEnabled,
  type ChatDocumentAttachment,
  type ChatEngine,
  type ChatMessage,
} from '../lib/api';
import { audioManager } from '../services/audioManager';
import { storeChatAttachment } from '../lib/chatAttachments';
import { rememberFromMessage } from '../lib/userProfile';
import type { AgentHandoff } from '../components/chat/modeRouter';
import { decideAssistantMode, persistTurnDecision } from '../components/chat/modeRouter';
import { findBuiltin as findChatBuiltin } from '../components/chat/commands';
import type { ChatPrompt } from '../components/chat/types';
import { researchExportMetadata, useChatTurn } from './useChatTurn';
import type { ChatSendOptions } from './useChatVoice';
import type { AttachedDocument } from '../components/chat/types';
import type { ActivityKind } from '../components/chat/activityMessages';
import type { Lang, TranslationKey } from '../i18n/translations';
import type { ExternalStream, SendOptions, SendResult } from './useStreamChat';

type Translate = (key: TranslationKey) => string;
type MessageStateRef = MutableRefObject<ChatMessage[]>;
type ResearchAbortRef = MutableRefObject<AbortController | null>;

export interface UseChatSendOptions {
  activeCollectionsForRequest: string[];
  appendResponseToken: (token: string, speak: boolean) => void;
  assistantErrorMessage: (error: unknown) => string;
  attachedDocs: AttachedDocument[];
  attachedImages: Array<{ dataUrl: string; file: File }>;
  busy: boolean;
  callModeRef: MutableRefObject<boolean>;
  cancelPendingCapture: () => void;
  clearAttachedDocs: () => void;
  customPrompts: MutableRefObject<ChatPrompt[]>;
  engine: ChatEngine;
  exportMarkdown: () => void;
  finishResponseSpeech: (text: string, onDone: () => void) => void;
  folderContext: Array<{ title: string; messages: ChatMessage[] }>;
  handleSendTextRef: MutableRefObject<(raw: string, opts?: ChatSendOptions) => Promise<void>>;
  input: string;
  lang: Lang;
  messageStateRef: MessageStateRef;
  messages: ChatMessage[];
  onAgentHandoff?: (handoff: AgentHandoff) => void;
  onMessagesChange: (messages: ChatMessage[]) => void;
  onNavigate?: (page: 'settings' | 'indexing' | 'browser' | 'memory' | 'docs' | 'agent') => void;
  onWebSearchBlocked?: () => void;
  publishMessages: (messages: ChatMessage[]) => void;
  queueVoiceRestart: (delay: number, manual?: boolean) => void;
  researchAbortRef: ResearchAbortRef;
  researchMode: boolean;
  resetInputHeight: () => void;
  resetResponseSpeech: () => void;
  scrollToBottom: (behavior?: ScrollBehavior, force?: boolean) => void;
  sendMessage: (messages: ChatMessage[], engine: ChatEngine, options?: SendOptions) => Promise<SendResult>;
  setAttachedImages: Dispatch<SetStateAction<Array<{ dataUrl: string; file: File }>>>;
  setDocUploadStatus: Dispatch<SetStateAction<string>>;
  setInput: Dispatch<SetStateAction<string>>;
  setResearching: Dispatch<SetStateAction<boolean>>;
  setSlashOpen: Dispatch<SetStateAction<boolean>>;
  setWebSearchAvailable: Dispatch<SetStateAction<boolean | null>>;
  setWebSearchMode: Dispatch<SetStateAction<boolean>>;
  speakWithFallback: (text: string, onDone?: () => void) => void;
  startActivity: (kind: ActivityKind) => void;
  startExternalStream: () => ExternalStream;
  stopActivity: () => void;
  t: Translate;
  temporary: boolean;
  wasAborted: () => boolean;
  webSearchAvailable: boolean | null;
  webSearchMode: boolean;
}

export function useChatSend({
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
  resetInputHeight,
  resetResponseSpeech,
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
}: UseChatSendOptions) {
  // ── Envío central (texto/voz/imagen) ──

  // Built-in slash-command helpers (must be declared before handleSendText).
  const runBuiltinDeepResearch = useCallback(async (query: string, baseMessages: ChatMessage[]) => {
    const controller = new AbortController();
    researchAbortRef.current = controller;
    setResearching(true);
    startActivity('web');
    let externalStream: ReturnType<typeof startExternalStream> | null = null;
    try {
      const webPlan = webSearchMode ? buildWebSearchQuery(query, baseMessages) : undefined;
      const stream = startExternalStream();
      externalStream = stream;
      const res = await runResearch(query, {
        collections: activeCollectionsForRequest,
        depth: webSearchMode ? 3 : 2,
        webSearch: webSearchMode,
        searchQuery: webPlan?.searchQuery,
        context: webPlan?.context,
        signal: controller.signal,
        thinking: thinkingModeEnabled(),
        onToken: (token) => {
          stopActivity();
          stream.onToken(token);
        },
      });
      const answer = typeof res.answer === 'string' ? res.answer.trim() : '';
      if (!answer) throw new Error(t('emptyResearchResponse'));
      const revealed = await externalStream?.finish(answer);
      const finalMsg: ChatMessage = {
        role: 'assistant',
        content: revealed || `_${t('requestCancelled')}_`,
        sources: res.sources,
        model: res.model,
        research: researchExportMetadata(res),
        finishReason: res.finish_reason,
        completionStatus: res.completion_status,
      };
      onMessagesChange([...baseMessages, finalMsg]);
    } catch (err) {
      externalStream?.cancel();
      if (err instanceof Error && err.message === 'TRINAXAI_SILENT_ABORT') return;
      const cancelled = controller.signal.aborted;
      const msg = assistantErrorMessage(err);
      onMessagesChange([...baseMessages, { role: 'assistant', content: cancelled ? `_${t('requestCancelled')}_` : `${t('errorPrefix')}: ${msg}` }]);
    } finally {
      if (researchAbortRef.current === controller) researchAbortRef.current = null;
      setResearching(false);
    }
  }, [activeCollectionsForRequest, assistantErrorMessage, onMessagesChange, startActivity, startExternalStream, stopActivity, t, webSearchMode]);

  const runBuiltinSummarize = useCallback(async (baseMessages: ChatMessage[]) => {
    const summaryPrompt: ChatMessage = {
      role: 'user',
      content: `${t('summarizePrompt')} ${t('conversationLabel')}:\n\n${
        baseMessages.map((m) => `[${m.role}] ${m.content}`).join('\n\n').slice(-3000)
      }`,
    };
    const withPlaceholder = [...baseMessages, { role: 'assistant' as const, content: t('summarizingConversation') }];
    onMessagesChange(withPlaceholder);
    try {
      const { content, meta, thinking, thinkingDurationMs } = await sendMessage([...baseMessages, summaryPrompt], 'ollama');
      onMessagesChange([...baseMessages, {
        role: 'assistant',
        content: `${content}`,
        sources: meta.sources,
        model: meta.model,
        project: meta.project,
        thinking,
        thinkingDurationMs,
      }]);
    } catch (err) {
      const msg = assistantErrorMessage(err);
      onMessagesChange([...baseMessages, { role: 'assistant', content: `${t('errorPrefix')}: ${msg}` }]);
    }
  }, [assistantErrorMessage, onMessagesChange, sendMessage, t]);

  const { buildTurnContextMessages, dispatchTurn } = useChatTurn({
    appendResponseToken,
    assistantErrorMessage,
    callModeRef,
    engine,
    finishResponseSpeech,
    folderContext,
    lang,
    onAgentHandoff,
    onWebSearchBlocked,
    publishMessages,
    queueVoiceRestart,
    researchAbortRef,
    resetResponseSpeech,
    sendMessage,
    setResearching,
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
  });

  const handleSendText = useCallback(async (raw: string, opts?: ChatSendOptions) => {
    let trimmed = raw.trim();
    const image = opts?.imageOverride?.dataUrl ?? attachedImages[0]?.dataUrl;
    const imageFile = opts?.imageOverride?.file ?? attachedImages[0]?.file;
    const docs = opts?.documentsOverride ?? attachedDocs;
    const baseMessages = opts?.baseMessages ?? messageStateRef.current;
    if ((!trimmed && !image && docs.length === 0) || busy || researchAbortRef.current) return;
    setSlashOpen(false);
    cancelPendingCapture();

    // Handle built-in slash commands FIRST (they short-circuit the chat).
    if (trimmed.startsWith('/')) {
      const head = trimmed.split(' ')[0].slice(1).toLowerCase();
      const tail = trimmed.includes(' ') ? trimmed.slice(trimmed.indexOf(' ') + 1) : '';
      const builtin = findChatBuiltin(head, lang);
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
            if (temporary) {
              onMessagesChange([...messages, { role: 'assistant', content: t('temporaryChatResearchUnavailable') }]);
              setInput(''); resetInputHeight();
              return;
            }
            const prompt = tail || t('deepResearchDefaultPrompt');
            const userMsg: ChatMessage = { role: 'user', content: prompt };
            onMessagesChange([...messages, userMsg]);
            requestAnimationFrame(() => scrollToBottom('smooth', true));
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

    // Each image is an independent prompt. Keep the loop sequential so only
    // one vision model is resident and the next request sees the prior reply.
    if (!opts?.imageOverride && attachedImages.length > 1) {
      const pendingImages = attachedImages;
      const pendingDocs = attachedDocs;
      let currentMessages = baseMessages;
      for (const [index, pendingImage] of pendingImages.entries()) {
        await handleSendText(trimmed, {
          ...opts,
          imageOverride: pendingImage,
          documentsOverride: index === 0 ? pendingDocs : [],
          baseMessages: currentMessages,
        });
        currentMessages = messageStateRef.current;
        if (wasAborted()) break;
      }
      return;
    }

    // A temporary chat must not feed the persistent user profile/memory.
    if (!temporary) rememberFromMessage(trimmed);

    const docContext = docs.map((doc) => (
      `\n\n[Archivo adjunto temporal: ${doc.name}${doc.truncated ? ' (truncado)' : ''}]\n`
      + '```text\n'
      + doc.content
      + '\n```'
    )).join('');
    const displayContent = trimmed || t('analyzeAttachedFiles');
    const storedDocuments = temporary
      ? []
      : await Promise.all(docs.map((doc) => storeChatAttachment(doc.file, 'document').catch(() => ({ name: doc.name, size: doc.size, localOnly: true }))));
    const storedImage = !temporary && imageFile
      ? await storeChatAttachment(imageFile, 'image').catch(() => ({
         name: imageFile.name,
         size: imageFile.size,
         mimeType: imageFile.type,
        kind: 'image' as const,
        localOnly: true,
      }))
      : undefined;
    const documentAttachments: ChatDocumentAttachment[] = docs.map((doc, index) => {
      const stored = storedDocuments[index] as Partial<ChatDocumentAttachment> | undefined;
      return {
        ...stored,
        name: stored?.name || doc.name,
        size: stored?.size ?? doc.size,
        mimeType: stored?.mimeType || doc.file.type || 'application/octet-stream',
        truncated: doc.truncated,
        kind: 'document',
      };
    });
    if (storedImage) documentAttachments.unshift(storedImage);
    if (documentAttachments.some((attachment) => attachment.localOnly)) {
      setDocUploadStatus(t('chatAttachmentLocalOnly'));
    }

    const route = decideAssistantMode(displayContent, {
      history: baseMessages,
      hasImage: Boolean(image),
      hasDocuments: docs.length > 0,
      webMode: webSearchMode,
      researchMode: researchMode && !temporary,
      engine,
    });
    const turn = persistTurnDecision(route, activeCollectionsForRequest);

    const userMsg: ChatMessage = {
      role: 'user',
      // Extracted document text is request-only. The durable history keeps the
      // attachment ID/metadata, avoiding a second full copy in localStorage and
      // app-state. Older messages containing inline context remain readable.
      content: displayContent,
      displayContent,
      image: image || undefined,
      documentAttachments: documentAttachments.length ? documentAttachments : undefined,
      inputMode: opts?.viaVoice ? 'voice' : 'text',
      turn,
    };
    const updated = [...baseMessages, userMsg];
    const requestUserMsg: ChatMessage = docContext
      ? { ...userMsg, content: `${displayContent}${docContext}` }
      : userMsg;
    const requestMessages = [...baseMessages, requestUserMsg];
    publishMessages(updated);
    audioManager.play('message-send');
    requestAnimationFrame(() => scrollToBottom('smooth', true));
    setInput('');
    resetInputHeight();
    setAttachedImages([]);
    clearAttachedDocs();
    const contextMessages = await buildTurnContextMessages(baseMessages);
    await dispatchTurn({
      persistedMessages: updated,
      requestMessages,
      prompt: displayContent,
      route,
      collections: activeCollectionsForRequest,
      contextMessages,
      hasImage: Boolean(image),
      hasDocuments: docs.length > 0,
      viaVoice: opts?.viaVoice,
      continueCall: opts?.continueCall,
    });
  }, [
    activeCollectionsForRequest,
    attachedDocs,
    attachedImages,
    buildTurnContextMessages,
    busy,
    cancelPendingCapture,
    clearAttachedDocs,
    dispatchTurn,
    engine,
    exportMarkdown,
    lang,
    messages,
    onMessagesChange,
    publishMessages,
    onNavigate,
    researchMode,
    resetInputHeight,
    runBuiltinDeepResearch,
    runBuiltinSummarize,
    scrollToBottom,
    setDocUploadStatus,
    t,
    temporary,
    webSearchMode,
    wasAborted,
  ]);

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


  return { buildTurnContextMessages, dispatchTurn, handleSend, handleKeyDown };
}
