import { useCallback, type Dispatch, type RefObject, type SetStateAction } from 'react';
import { MAX_CONTINUATIONS, mergeContinuation, type ChatEngine, type ChatMessage } from '../lib/api';
import { deleteChatAttachments } from '../lib/chatAttachments';
import {
  decideAssistantMode,
  persistTurnDecision,
  restoreTurnDecision,
} from '../components/chat/modeRouter';
import type { ActivityKind } from '../components/chat/activityMessages';
import type { Lang } from '../i18n/translations';
import type { DispatchTurnInput } from './useChatTurn';
import type { SendOptions, SendResult } from './useStreamChat';

type MessageDisplayContent = (message: ChatMessage) => string;
type BuildTurnContextMessages = (messages: ChatMessage[]) => Promise<ChatMessage[]>;
type DispatchTurn = (input: DispatchTurnInput) => Promise<void>;
type RebuildStoredDocumentContext = (message: ChatMessage) => Promise<string>;

export interface ChatMessageActionsOptions {
  abort: (discard?: boolean) => void;
  activeCollectionsForRequest: string[];
  buildTurnContextMessages: BuildTurnContextMessages;
  busy: boolean;
  dispatchTurn: DispatchTurn;
  editInputRef: RefObject<HTMLTextAreaElement | null>;
  editingIndex: number | null;
  editingText: string;
  engine: ChatEngine;
  lang: Lang;
  messageDisplayContent: MessageDisplayContent;
  messages: ChatMessage[];
  onMessagesChange: (messages: ChatMessage[]) => void;
  rebuildStoredDocumentContext: RebuildStoredDocumentContext;
  sendMessage: (messages: ChatMessage[], engine: ChatEngine, options?: SendOptions) => Promise<SendResult>;
  setEditingIndex: Dispatch<SetStateAction<number | null>>;
  setEditingText: Dispatch<SetStateAction<string>>;
  startActivity: (kind: ActivityKind) => void;
  stopActivity: () => void;
  stopSpeak: () => void;
  streaming: boolean;
  temporary: boolean;
}
export function useChatMessageActions({
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
}: ChatMessageActionsOptions) {
  // Start editing a user message
  const startEdit = useCallback(
    (index: number) => {
      if (streaming) abort(true);
      stopSpeak();
      setEditingIndex(index);
      setEditingText(messageDisplayContent(messages[index]));
      requestAnimationFrame(() => {
        const el = editInputRef.current;
        if (!el) return;
        el.style.height = 'auto';
        el.style.height = `${el.scrollHeight}px`;
        el.focus();
      });
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
    const previousDisplay = previous?.role === 'user' ? messageDisplayContent(previous) : '';
    // Legacy sessions may still contain extracted document text inline. Use it
    // for this request once, but do not write it back into durable history.
    const legacyRequestContext = previous?.role === 'user' && previous.content.startsWith(previousDisplay)
      ? previous.content.slice(previousDisplay.length)
      : '';
    const route = restoreTurnDecision(previous?.turn) ?? decideAssistantMode(editingText.trim(), {
      history: sliced,
      hasImage: Boolean(previous?.image),
      hasDocuments: Boolean(previous?.documentAttachments?.some((attachment) => attachment.kind === 'document')),
      engine,
    });
    const turnCollections = previous?.turn?.collections?.length
      ? previous.turn.collections
      : activeCollectionsForRequest;
    const userMsg: ChatMessage = {
      role: 'user',
      content: editingText.trim(),
      displayContent: editingText.trim(),
      image: previous?.role === 'user' ? previous.image : undefined,
      documentAttachments: previous?.role === 'user' ? previous.documentAttachments : undefined,
      inputMode: previous?.role === 'user' ? previous.inputMode : 'text',
      turn: persistTurnDecision(route, turnCollections),
    };
    const updated = [...sliced, userMsg];
    void deleteChatAttachments(messages.slice(editingIndex + 1));
    onMessagesChange(updated);
    setEditingIndex(null);
    const rebuiltContext = legacyRequestContext || await rebuildStoredDocumentContext(userMsg);
    const requestMessages = rebuiltContext
      ? [...sliced, { ...userMsg, content: `${userMsg.content}${rebuiltContext}` }]
      : updated;
    const contextMessages = await buildTurnContextMessages(sliced);
    await dispatchTurn({
      persistedMessages: updated,
      requestMessages,
      prompt: editingText.trim(),
      route,
      collections: turnCollections,
      contextMessages,
      hasImage: Boolean(userMsg.image),
      hasDocuments: Boolean(userMsg.documentAttachments?.some((attachment) => attachment.kind === 'document')),
    });
  }, [
    abort,
    activeCollectionsForRequest,
    buildTurnContextMessages,
    dispatchTurn,
    editingIndex,
    editingText,
    engine,
    messageDisplayContent,
    messages,
    onMessagesChange,
    rebuildStoredDocumentContext,
    stopSpeak,
  ]);

  const regenerateFrom = useCallback(async (assistantIndex: number) => {
    if (streaming) abort(true);
    stopSpeak();
    const updated = messages.slice(0, assistantIndex);
    // A router notice belongs to the answer being regenerated, not to history.
    while (updated.at(-1)?.routerNotice) updated.pop();
    const userMessage = [...updated].reverse().find((message) => message.role === 'user');
    if (!userMessage) return;
    void deleteChatAttachments(messages.slice(assistantIndex));
    onMessagesChange(updated);
    const prompt = messageDisplayContent(userMessage);
    const route = restoreTurnDecision(userMessage.turn) ?? decideAssistantMode(prompt, {
      history: updated.slice(0, updated.lastIndexOf(userMessage)),
      hasImage: Boolean(userMessage.image),
      hasDocuments: Boolean(userMessage.documentAttachments?.some((attachment) => attachment.kind === 'document')),
      engine,
    });
    const turnCollections = userMessage.turn?.collections?.length
      ? userMessage.turn.collections
      : activeCollectionsForRequest;
    const legacyRequestContext = userMessage.content.startsWith(prompt)
      ? userMessage.content.slice(prompt.length)
      : '';
    const rebuiltContext = legacyRequestContext || await rebuildStoredDocumentContext(userMessage);
    const userIndex = updated.lastIndexOf(userMessage);
    const requestMessages = rebuiltContext
      ? updated.map((message, index) => index === userIndex
        ? { ...message, content: `${prompt}${rebuiltContext}` }
        : message)
      : updated;
    const contextMessages = await buildTurnContextMessages(updated.slice(0, -1));
    await dispatchTurn({
      persistedMessages: updated,
      requestMessages,
      prompt,
      route,
      collections: turnCollections,
      contextMessages,
      hasImage: Boolean(userMessage.image),
      hasDocuments: Boolean(userMessage.documentAttachments?.some((attachment) => attachment.kind === 'document')),
    });
  }, [
    abort,
    activeCollectionsForRequest,
    buildTurnContextMessages,
    dispatchTurn,
    engine,
    messageDisplayContent,
    messages,
    onMessagesChange,
    rebuildStoredDocumentContext,
    stopSpeak,
    streaming,
  ]);

  const continueResponse = useCallback(async (assistantIndex: number) => {
    if (busy || assistantIndex < 0 || assistantIndex >= messages.length) return;
    const assistant = messages[assistantIndex];
    if (assistant.role !== 'assistant' || !assistant.canContinue) return;
    const baseMessages = messages.slice(0, assistantIndex);
    const userMessage = [...baseMessages].reverse().find((message) => message.role === 'user');
    if (!userMessage) return;
    const route = restoreTurnDecision(userMessage.turn) ?? decideAssistantMode(userMessage.content, {
      history: baseMessages.slice(0, baseMessages.lastIndexOf(userMessage)),
      hasImage: Boolean(userMessage.image),
      hasDocuments: Boolean(userMessage.documentAttachments?.some((attachment) => attachment.kind === 'document')),
      engine,
    });
    const turnCollections = userMessage.turn?.collections?.length ? userMessage.turn.collections : activeCollectionsForRequest;
    const selectedEngine: ChatEngine = route.mode === 'rag' ? 'rag' : engine;
    const continuationPrompt = lang === 'es'
      ? 'Continúa exactamente desde el punto donde termina tu respuesta anterior. No repitas nada; entrega sólo el texto faltante y cierra correctamente cualquier bloque Markdown o código abierto.'
      : 'Continue exactly from where your previous answer ends. Do not repeat anything; output only the missing text and close any open Markdown or code fence correctly.';
    const requestMessages: ChatMessage[] = [
      ...baseMessages,
      { role: 'assistant', content: assistant.content },
      { role: 'user', content: continuationPrompt },
    ];
    const contextMessages = await buildTurnContextMessages(baseMessages);
    startActivity('thinking');
    try {
      const result = await sendMessage([...contextMessages, ...requestMessages], selectedEngine, { collections: turnCollections, temporary });
      const count = (assistant.continuationCount || 0) + 1;
      const merged = mergeContinuation(assistant.content, result.content);
      const pending = Boolean(result.meta.canContinue || result.meta.finishReason === 'length');
      const meta = {
        ...assistant,
        content: merged,
        thinking: [assistant.thinking, result.thinking].filter(Boolean).join('\n') || undefined,
        thinkingDurationMs: result.thinkingDurationMs ?? assistant.thinkingDurationMs,
        finishReason: result.meta.finishReason,
        completionStatus: pending ? 'pending' : result.meta.completionStatus,
        canContinue: pending,
        continuationCount: count,
        maxContinuations: result.meta.maxContinuations ?? MAX_CONTINUATIONS,
      };
      onMessagesChange([...baseMessages, meta]);
    } catch {
      onMessagesChange([...baseMessages, { ...assistant, completionStatus: 'error', canContinue: false }]);
    } finally {
      stopActivity();
    }
  }, [activeCollectionsForRequest, buildTurnContextMessages, busy, engine, lang, messages, onMessagesChange, sendMessage, startActivity, stopActivity, temporary]);


  return { startEdit, saveEdit, regenerateFrom, continueResponse };
}
