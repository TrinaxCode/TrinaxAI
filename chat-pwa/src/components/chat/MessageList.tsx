import {
  lazy,
  Suspense,
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  MdCheck,
  MdContentCopy,
  MdEdit,
  MdImage,
  MdKeyboardArrowDown,
  MdRefresh,
  MdStop,
  MdUploadFile,
  MdVolumeUp,
} from 'react-icons/md';
import { isCollectionEmptyMessage, type ChatDocumentAttachment, type ChatMessage } from '../../lib/api';
import { useI18n } from '../../i18n/I18nContext';
import Sources from '../Sources';

// Markdown + KaTeX is the largest optional client feature. Do not download or
// evaluate it for a brand-new/empty chat; load it with the first saved answer.
const ChatMarkdown = lazy(() => import('./ChatMarkdown'));

const ESTIMATED_MESSAGE_HEIGHT = 96;
const ESTIMATED_STREAMING_HEIGHT = 64;
const VIRTUAL_GAP = 16;
const VIRTUAL_OVERSCAN = 640;
const FALLBACK_VIEWPORT_HEIGHT = 640;
const STREAMING_ROW_KEY = 'streaming-message';

interface VirtualLayout {
  keys: string[];
  offsets: number[];
  heights: number[];
  totalHeight: number;
}

interface VirtualAnchor {
  key: string;
  index: number;
  distance: number;
}

interface MeasuredRowProps {
  itemKey: string;
  top: number;
  onResize: (itemKey: string, height: number) => void;
  children: ReactNode;
}

function MeasuredRow({ itemKey, top, onResize, children }: MeasuredRowProps) {
  const rowRef = useRef<HTMLDivElement>(null);
  const measure = useCallback(() => {
    const row = rowRef.current;
    if (!row) return;
    const height = row.getBoundingClientRect().height || row.offsetHeight || row.scrollHeight;
    if (height > 0) onResize(itemKey, height);
  }, [itemKey, onResize]);

  useLayoutEffect(() => {
    const row = rowRef.current;
    if (!row) return undefined;
    measure();
    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(measure);
      observer.observe(row);
      return () => observer.disconnect();
    }
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [measure]);

  return (
    <div
      ref={rowRef}
      style={{ position: 'absolute', top, left: 0, width: '100%' }}
    >
      {children}
    </div>
  );
}

function firstItemAtOrAfter(layout: VirtualLayout, target: number): number {
  let low = 0;
  let high = layout.keys.length - 1;
  let result = layout.keys.length;
  while (low <= high) {
    const middle = Math.floor((low + high) / 2);
    if (layout.offsets[middle] + layout.heights[middle] >= target) {
      result = middle;
      high = middle - 1;
    } else {
      low = middle + 1;
    }
  }
  return result;
}

function lastItemAtOrBefore(layout: VirtualLayout, target: number): number {
  let low = 0;
  let high = layout.keys.length - 1;
  let result = -1;
  while (low <= high) {
    const middle = Math.floor((low + high) / 2);
    if (layout.offsets[middle] <= target) {
      result = middle;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }
  return result;
}

function visibleItems(layout: VirtualLayout, scrollTop: number, viewportHeight: number): number[] {
  if (!layout.keys.length) return [];
  const first = Math.min(
    layout.keys.length - 1,
    Math.max(0, firstItemAtOrAfter(layout, scrollTop - VIRTUAL_OVERSCAN)),
  );
  const last = Math.min(
    layout.keys.length - 1,
    lastItemAtOrBefore(layout, scrollTop + viewportHeight + VIRTUAL_OVERSCAN),
  );
  if (last < first) return [first];
  return Array.from({ length: last - first + 1 }, (_, index) => first + index);
}

function formatAttachmentSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getLastUserText(messages: ChatMessage[], beforeMessage?: ChatMessage): string {
  const end = beforeMessage ? messages.indexOf(beforeMessage) + 1 : messages.length;
  for (let index = end - 1; index >= 0; index -= 1) {
    if (messages[index].role === 'user') return messages[index].displayContent ?? messages[index].content;
  }
  return '';
}

function needsIndexingAction(message: ChatMessage): boolean {
  if (message.research?.error_code === 'collection_empty') return true;
  return /contains no indexed documents|no contiene documentos indexados|no indexed knowledge base|no indexed retriever|documents must be indexed first|documentos deben indexarse primero|aún no hay índice|aun no hay indice|selected rag collection is empty|colecci[oó]n rag.*vac[ií]a/i.test(message.content);
}

function assistantContent(message: ChatMessage, collectionEmpty: string): string {
  const content = message.content.trim();
  if (message.research?.error_code === 'collection_empty' || isCollectionEmptyMessage(content)) {
    return collectionEmpty;
  }
  return message.content;
}

type MessageWithOptionalId = ChatMessage & { id?: string | number };

function messageId(message: ChatMessage): string | undefined {
  const id = (message as MessageWithOptionalId).id;
  if (typeof id === 'number' && Number.isFinite(id)) return String(id);
  if (typeof id === 'string' && id.trim()) return id.trim();
  return undefined;
}

function legacyMessageFingerprint(message: ChatMessage): string {
  const value = [
    message.role,
    message.content,
    message.displayContent ?? '',
    message.image ?? '',
    ...(message.documentAttachments ?? []).map((attachment) => [
      attachment.id ?? '',
      attachment.name,
      attachment.size,
      attachment.mimeType ?? '',
      attachment.storageKey ?? '',
      attachment.kind ?? '',
    ].join('\u0001')),
  ].join('\u0000');

  // ponytail: 32-bit legacy fingerprint; real message ids cover new records,
  // while occurrence suffixes keep legacy collisions unique.
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}

function getMessageKeys(messages: ChatMessage[]): string[] {
  const occurrences = new Map<string, number>();
  const used = new Set<string>();

  return messages.map((message) => {
    const id = messageId(message);
    const base = id
      ? `message-${id}`
      : `legacy-${legacyMessageFingerprint(message)}`;
    let occurrence = occurrences.get(base) ?? 0;
    let key = occurrence === 0 ? base : `${base}-${occurrence}`;
    while (used.has(key)) {
      occurrence += 1;
      key = `${base}-${occurrence}`;
    }
    occurrences.set(base, occurrence + 1);
    used.add(key);
    return key;
  });
}

interface MessageListProps {
  messages: ChatMessage[];
  streaming: boolean;
  activityLabel?: string;
  streamedText: string;
  isDark: boolean;
  userDisplayName: string;
  messagesRef: RefObject<HTMLDivElement | null>;
  editInputRef: RefObject<HTMLTextAreaElement | null>;
  editingIndex: number | null;
  editingText: string;
  copiedKey: string | null;
  ttsSupported: boolean;
  ttsActiveKey: string | null;
  showScrollButton: boolean;
  activeCollections: string[];
  onScroll: () => void;
  onEditingTextChange: (text: string) => void;
  onCancelEdit: () => void;
  onSaveEdit: () => void;
  onStartEdit: (index: number) => void;
  onRegenerate: (index: number) => void;
  onContinue?: (index: number) => void;
  onCopy: (text: string, key: string) => void;
  onSpeak: (text: string, key: string) => void;
  onStopSpeak: () => void;
  onOpenAttachment: (attachment: ChatDocumentAttachment, inlineUrl?: string) => void;
  onOpenBrowser?: (file: string, collection?: string) => void;
  onOpenIndexing?: () => void;
  onScrollToBottom: () => void;
}

export default function MessageList({
  messages,
  streaming,
  activityLabel = '',
  streamedText,
  isDark,
  userDisplayName,
  messagesRef,
  editInputRef,
  editingIndex,
  editingText,
  copiedKey,
  ttsSupported,
  ttsActiveKey,
  showScrollButton,
  activeCollections,
  onScroll,
  onEditingTextChange,
  onCancelEdit,
  onSaveEdit,
  onStartEdit,
  onRegenerate,
  onContinue = () => undefined,
  onCopy,
  onSpeak,
  onStopSpeak,
  onOpenAttachment,
  onOpenBrowser,
  onOpenIndexing,
  onScrollToBottom,
}: MessageListProps) {
  const { t } = useI18n();
  const messageKeys = useMemo(() => getMessageKeys(messages), [messages]);
  const displayContent = (message: ChatMessage) => (
    message.displayContent ?? (message.content || (message.image ? '[image]' : ''))
  ).trim();
  const [scrollElement, setScrollElement] = useState<HTMLDivElement | null>(null);
  const scrollElementRef = useRef<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(FALLBACK_VIEWPORT_HEIGHT);
  const measuredHeightsRef = useRef(new Map<string, number>());
  const [measurementVersion, setMeasurementVersion] = useState(0);
  const layoutRef = useRef<VirtualLayout | null>(null);
  const anchorRef = useRef<VirtualAnchor | null>(null);
  const followBottomRef = useRef(false);

  const captureAnchor = useCallback((layout: VirtualLayout, element: HTMLDivElement) => {
    if (!layout.keys.length) {
      anchorRef.current = null;
      return;
    }
    const index = Math.min(firstItemAtOrAfter(layout, element.scrollTop), layout.keys.length - 1);
    anchorRef.current = {
      key: layout.keys[index],
      index,
      distance: layout.offsets[index] - element.scrollTop,
    };
  }, []);

  const setMessagesElement = useCallback((element: HTMLDivElement | null) => {
    (messagesRef as { current: HTMLDivElement | null }).current = element;
    scrollElementRef.current = element;
    setScrollElement(element);
  }, [messagesRef]);

  const onScrollInternal = useCallback(() => {
    const element = scrollElementRef.current;
    const layout = layoutRef.current;
    if (element) {
      followBottomRef.current = element.scrollHeight - element.scrollTop - element.clientHeight <= 32;
      if (layout) captureAnchor(layout, element);
      setScrollTop((current) => current === element.scrollTop ? current : element.scrollTop);
    }
    onScroll();
  }, [captureAnchor, onScroll]);

  useLayoutEffect(() => {
    if (!scrollElement) return undefined;
    const updateViewport = () => {
      const nextHeight = scrollElement.clientHeight || FALLBACK_VIEWPORT_HEIGHT;
      setViewportHeight((current) => current === nextHeight ? current : nextHeight);
      setScrollTop((current) => current === scrollElement.scrollTop ? current : scrollElement.scrollTop);
    };
    updateViewport();
    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(updateViewport);
      observer.observe(scrollElement);
      return () => observer.disconnect();
    }
    window.addEventListener('resize', updateViewport);
    return () => window.removeEventListener('resize', updateViewport);
  }, [scrollElement]);

  const rowKeys = useMemo(
    () => streaming ? [...messageKeys, STREAMING_ROW_KEY] : messageKeys,
    [messageKeys, streaming],
  );
  const layout = useMemo<VirtualLayout>(() => {
    const offsets: number[] = [];
    const heights = rowKeys.map((key, index) => (
      measuredHeightsRef.current.get(key)
      ?? (index === messages.length && streaming ? ESTIMATED_STREAMING_HEIGHT : ESTIMATED_MESSAGE_HEIGHT)
    ));
    let totalHeight = 0;
    rowKeys.forEach((_, index) => {
      offsets.push(totalHeight);
      totalHeight += heights[index];
      if (index < rowKeys.length - 1) totalHeight += VIRTUAL_GAP;
    });
    return { keys: rowKeys, offsets, heights, totalHeight };
  }, [messages.length, measurementVersion, rowKeys, streaming]);

  const onRowResize = useCallback((itemKey: string, height: number) => {
    const nextHeight = Math.max(1, Math.ceil(height));
    const previousHeight = measuredHeightsRef.current.get(itemKey);
    if (previousHeight !== undefined && Math.abs(previousHeight - nextHeight) < 1) return;
    measuredHeightsRef.current.set(itemKey, nextHeight);

    const element = scrollElementRef.current;
    const previousLayout = layoutRef.current;
    if (element && previousLayout) {
      const index = previousLayout.keys.indexOf(itemKey);
      const previousEstimate = index >= 0 ? previousLayout.heights[index] : previousHeight;
      if (index >= 0 && previousEstimate !== undefined && previousLayout.offsets[index] + previousEstimate <= element.scrollTop) {
        element.scrollTop += nextHeight - previousEstimate;
        setScrollTop(element.scrollTop);
      }
    }
    setMeasurementVersion((version) => version + 1);
  }, []);

  useLayoutEffect(() => {
    const element = scrollElement;
    if (!element) return;
    const previousLayout = layoutRef.current;
    if (previousLayout && previousLayout !== layout && layout.keys.length) {
      const wasAtBottom = followBottomRef.current
        || previousLayout.totalHeight + 32 - element.scrollTop - element.clientHeight <= 32;
      if (wasAtBottom) {
        element.scrollTop = Math.max(0, element.scrollHeight - element.clientHeight);
        followBottomRef.current = true;
        setScrollTop(element.scrollTop);
      } else if (anchorRef.current) {
        const anchor = anchorRef.current;
        const matchingIndex = layout.keys.indexOf(anchor.key);
        const index = matchingIndex >= 0 ? matchingIndex : Math.min(anchor.index, layout.keys.length - 1);
        const nextScrollTop = Math.max(0, layout.offsets[index] - anchor.distance);
        if (Math.abs(nextScrollTop - element.scrollTop) > 0.5) {
          element.scrollTop = nextScrollTop;
          setScrollTop(nextScrollTop);
        }
      }
    }
    layoutRef.current = layout;
    if (anchorRef.current === null) captureAnchor(layout, element);
  }, [captureAnchor, layout, scrollElement]);

  const visibleItemIndexes = useMemo(() => {
    const indexes = visibleItems(layout, scrollTop, viewportHeight);
    if (editingIndex !== null && editingIndex >= 0 && editingIndex < messages.length && !indexes.includes(editingIndex)) {
      indexes.push(editingIndex);
      indexes.sort((left, right) => left - right);
    }
    return indexes;
  }, [editingIndex, layout, messages.length, scrollTop, viewportHeight]);
  const visibleMessageIndexes = visibleItemIndexes.filter((index) => index < messages.length);

  return (
    <div className={`${messages.length === 0 && !streaming ? 'hidden' : 'relative flex-1'} min-h-0 min-w-0 max-w-full`}>
      <div
        ref={setMessagesElement}
        onScroll={onScrollInternal}
        className="chat-messages h-full min-h-0 min-w-0 max-w-full space-y-4 overflow-y-auto overflow-x-hidden px-2 py-4 sm:px-4"
        style={{ overscrollBehavior: 'contain', overflowAnchor: 'none', WebkitOverflowScrolling: 'touch' }}
      >
        <div style={{ position: 'relative', width: '100%', height: layout.totalHeight }}>
        {visibleMessageIndexes.map((index) => {
          const message = messages[index];
          const messageKey = messageKeys[index];
          const content = message.role === 'assistant' ? assistantContent(message, t('collectionEmpty')) : message.content;
          return (
          <MeasuredRow key={messageKey} itemKey={messageKey} top={layout.offsets[index]} onResize={onRowResize}>
          <motion.div
            initial={{ opacity: 0, y: 12, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.3, delay: 0, ease: [0.16, 1, 0.3, 1] }}
            className={`chat-row flex w-full min-w-0 max-w-full gap-2 sm:gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {message.role === 'assistant' && (
              <div className={`chat-assistant-avatar mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full p-1 ${isDark ? 'chat-assistant-avatar-dark' : 'chat-assistant-avatar-light'}`}>
                <img src="/logo-for-ai.webp" alt="TrinaxAI" className="h-full w-full rounded-full object-contain" width={28} height={28} draggable={false} />
              </div>
            )}

            {editingIndex === index ? (
              <div className="chat-bubble-wrap min-w-0 flex-1">
                <textarea
                  aria-label={t('clickToEdit')}
                  ref={editInputRef}
                  value={editingText}
                  onChange={(event) => {
                    onEditingTextChange(event.target.value);
                    event.target.style.height = 'auto';
                    event.target.style.height = `${event.target.scrollHeight}px`;
                  }}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault();
                      onSaveEdit();
                    }
                    if (event.key === 'Escape') onCancelEdit();
                  }}
                  className={`w-full resize-none overflow-hidden rounded-xl border border-[#006bbd]/40 px-3 py-2 text-sm outline-none focus:border-[#006bbd] ${isDark ? 'bg-[#006bbd]/20 text-white placeholder-white/30' : 'bg-[#006bbd]/10 text-gray-900 placeholder-gray-400'}`}
                  rows={1}
                />
                <div className="mt-1 flex gap-2">
                  <button onClick={onSaveEdit} className="rounded-lg bg-[#006bbd] px-2 py-1 text-xs text-white">{t('saveAndResend')}</button>
                  <button onClick={onCancelEdit} className={`rounded-lg px-2 py-1 text-xs ${isDark ? 'bg-white/10 text-white/70 hover:text-white' : 'bg-gray-200 text-gray-700 hover:text-gray-900'}`}>{t('cancel')}</button>
                </div>
              </div>
            ) : message.role === 'assistant' ? (
              <div className="chat-bubble-wrap flex min-w-0 flex-col items-start">
                <div className={`chat-bubble chat-bubble-assistant min-w-0 max-w-full overflow-hidden rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${isDark ? 'chat-bubble-assistant-dark' : 'chat-bubble-assistant-light'}`}>
                  <Suspense fallback={<p className="chat-plain-text whitespace-pre-wrap">{content.trim()}</p>}>
                    <ChatMarkdown text={content.trim()} isDark={isDark} sources={message.sources} />
                  </Suspense>
                  {needsIndexingAction(message) && onOpenIndexing && (
                    <button
                      type="button"
                      onClick={onOpenIndexing}
                      className={`mt-3 inline-flex min-h-9 items-center rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors ${isDark ? 'border-blue-300/35 text-blue-200 hover:bg-blue-300/10' : 'border-[#006bbd]/40 text-[#006bbd] hover:bg-[#006bbd]/10'}`}
                    >
                      {t('openIndexing')}
                    </button>
                  )}
                </div>
                <div className="mt-1 flex items-center gap-2">
                  {message.completionStatus === 'pending' && (
                    <span role="status" className="text-[11px] text-amber-600">{message.canContinue && (message.maxContinuations === undefined || (message.continuationCount || 0) < message.maxContinuations) ? t('completionPending') : t('completionLimitReached')}</span>
                  )}
                  {message.completionStatus === 'cancelled' && <span role="status" className="text-[11px] text-gray-500">{t('requestCancelled')}</span>}
                  {message.completionStatus === 'error' && <span role="status" className="text-[11px] text-red-600">{t('completionError')}</span>}
                  {message.canContinue && message.completionStatus === 'pending' && (
                    <button
                      type="button"
                      onClick={() => onContinue(index)}
                      className="rounded-md bg-[#006bbd]/10 px-2 py-1 text-[11px] font-medium text-[#006bbd] hover:bg-[#006bbd]/20"
                    >
                      {t('continueResponse')}
                    </button>
                  )}
                  <button
                    onClick={() => onCopy(content.trim(), `msg-copy-${index}`)}
                    className={`rounded-md p-1 transition-colors ${copiedKey === `msg-copy-${index}` ? 'bg-[#006bbd]/10 text-[#006bbd]' : isDark ? 'text-white/30 hover:bg-white/[0.06] hover:text-white/70' : 'text-gray-400 hover:bg-gray-100 hover:text-gray-600'}`}
                    title={copiedKey === `msg-copy-${index}` ? t('copied') : t('copy')}
                    aria-label={copiedKey === `msg-copy-${index}` ? t('copied') : t('copy')}
                  >
                    {copiedKey === `msg-copy-${index}` ? <MdCheck size={15} /> : <MdContentCopy size={15} />}
                  </button>
                  <button onClick={() => onRegenerate(index)} disabled={streaming} className={`rounded-md p-1 transition-colors disabled:opacity-30 ${isDark ? 'text-white/30 hover:bg-white/[0.06] hover:text-white/70' : 'text-gray-400 hover:bg-gray-100 hover:text-gray-600'}`} title={t('regenerate')} aria-label={t('regenerate')}>
                    <MdRefresh size={15} />
                  </button>
                  {ttsSupported && (
                    <button
                      onClick={() => ttsActiveKey === `msg-${index}` ? onStopSpeak() : onSpeak(content.trim(), `msg-${index}`)}
                      className={`rounded-md p-1 transition-colors ${ttsActiveKey === `msg-${index}` ? 'bg-[#006bbd]/10 text-[#006bbd]' : isDark ? 'text-white/30 hover:bg-white/[0.06] hover:text-white/70' : 'text-gray-400 hover:bg-gray-100 hover:text-gray-600'}`}
                      title={ttsActiveKey === `msg-${index}` ? t('stop') : t('listen')}
                      aria-label={ttsActiveKey === `msg-${index}` ? t('stop') : t('listen')}
                    >
                      {ttsActiveKey === `msg-${index}` ? <MdStop size={15} /> : <MdVolumeUp size={15} />}
                    </button>
                  )}
                </div>
                <Sources
                  sources={message.sources}
                  model={message.model}
                  project={message.project}
                  query={getLastUserText(messages, message)}
                  onOpenInBrowser={onOpenBrowser ? (file, collection) => onOpenBrowser(file, collection || activeCollections[0] || 'default') : undefined}
                />
              </div>
            ) : (
              <div className="chat-bubble-wrap flex min-w-0 flex-col items-end">
                <div className="chat-bubble group/msg min-w-0 max-w-full rounded-2xl bg-[#006bbd] px-4 py-2.5 text-sm leading-relaxed text-white transition-colors">
                  {message.image && (
                    <div className="mb-2 flex w-full justify-center">
                      <button type="button" className="flex max-w-full justify-center" onClick={() => onOpenAttachment({ name: t('attachedImage'), size: 0, mimeType: 'image/*', kind: 'image' }, message.image)}>
                        <img src={message.image} alt={t('attachedImage')} className="mx-auto block max-h-52 w-auto max-w-full rounded-lg object-contain" width={320} height={208} />
                      </button>
                    </div>
                  )}
                  {!message.image && message.documentAttachments?.some((attachment) => attachment.kind === 'image') && (
                    <div className="mb-2 flex flex-wrap gap-1.5">
                      {message.documentAttachments.filter((attachment) => attachment.kind === 'image').map((attachment, attachmentIndex) => (
                        <button type="button" key={`image-${attachment.id || attachmentIndex}`} onClick={() => onOpenAttachment(attachment)} className="inline-flex items-center gap-1.5 rounded-lg bg-white/15 px-2 py-1 text-[11px] text-white/90">
                          <MdImage size={14} /> {attachment.name || t('attachedImage')}
                          {attachment.localOnly && <span title={t('chatAttachmentLocalOnly')} className="shrink-0 text-amber-200">{t('localOnlyAttachment')}</span>}
                        </button>
                      ))}
                    </div>
                  )}
                  {message.documentAttachments?.length ? (
                    <div className="mb-2 flex max-w-full flex-wrap gap-1.5">
                      {message.documentAttachments.filter((attachment) => attachment.kind !== 'image').map((attachment, attachmentIndex) => (
                        <button type="button" onClick={() => onOpenAttachment(attachment)} key={`${attachment.name}-${attachmentIndex}`} className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-lg bg-white/15 px-2 py-1 text-[11px] text-white/90">
                          <MdUploadFile size={14} className="shrink-0" />
                          <span className="min-w-0 max-w-48 truncate">{attachment.name}</span>
                          {formatAttachmentSize(attachment.size) && <span className="shrink-0 text-white/60">{formatAttachmentSize(attachment.size)}</span>}
                          {attachment.truncated && <span className="shrink-0 text-amber-200">{t('truncated')}</span>}
                          {attachment.localOnly && <span title={t('chatAttachmentLocalOnly')} className="shrink-0 text-amber-200">{t('localOnlyAttachment')}</span>}
                        </button>
                      ))}
                    </div>
                  ) : null}
                  {displayContent(message) && <p className="chat-plain-text min-w-0 max-w-full whitespace-pre-wrap">{displayContent(message)}</p>}
                </div>
                <div className="mt-1 flex items-center gap-1">
                  <button onClick={() => onStartEdit(index)} className={`rounded-md p-1 transition-colors ${isDark ? 'text-white/35 hover:bg-white/[0.06] hover:text-white/75' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'}`} title={t('clickToEdit')} aria-label={t('clickToEdit')}><MdEdit size={15} /></button>
                  <button
                    onClick={() => onCopy(displayContent(message), `msg-copy-${index}`)}
                    className={`rounded-md p-1 transition-colors ${copiedKey === `msg-copy-${index}` ? 'bg-[#006bbd]/10 text-[#006bbd]' : isDark ? 'text-white/30 hover:bg-white/[0.06] hover:text-white/70' : 'text-gray-400 hover:bg-gray-100 hover:text-gray-600'}`}
                    title={copiedKey === `msg-copy-${index}` ? t('copied') : t('copy')}
                    aria-label={copiedKey === `msg-copy-${index}` ? t('copied') : t('copy')}
                  >
                    {copiedKey === `msg-copy-${index}` ? <MdCheck size={15} /> : <MdContentCopy size={15} />}
                  </button>
                </div>
              </div>
            )}

            {message.role === 'user' && (
              <div className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-[#006bbd] text-xs font-semibold text-white" aria-label={t('userAvatar')} title={userDisplayName}>
                {(userDisplayName.trim()[0] || 'U').toUpperCase()}
              </div>
            )}
          </motion.div>
          </MeasuredRow>
          );
        })}

        {streaming && visibleItemIndexes.includes(messages.length) && (
          <MeasuredRow itemKey={STREAMING_ROW_KEY} top={layout.offsets[messages.length]} onResize={onRowResize}>
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, scale: 0.96 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="chat-row flex w-full min-w-0 max-w-full justify-start gap-2 sm:gap-3"
          >
            <div className={`chat-assistant-avatar mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full p-1 ${isDark ? 'chat-assistant-avatar-dark' : 'chat-assistant-avatar-light'}`}>
              <img src="/logo-for-ai.webp" alt="TrinaxAI" className="h-full w-full rounded-full object-contain" width={28} height={28} draggable={false} />
            </div>
            <div className="chat-bubble-wrap min-w-0">
              <div className={`chat-bubble chat-bubble-assistant chat-bubble-streaming min-w-0 max-w-full overflow-hidden rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${isDark ? 'chat-bubble-assistant-dark' : 'chat-bubble-assistant-light'}`}>
                {streamedText ? (
                  <p className="chat-plain-text min-w-0 max-w-full whitespace-pre-wrap">{streamedText.trim()}</p>
                ) : (
                  <div className="chat-generating-indicator" role="status" aria-live="polite" aria-label={activityLabel || t('assistantGenerating')}>
                    <span className="chat-generating-label" aria-hidden="true">
                      <AnimatePresence initial={false} mode="wait">
                        <motion.span
                          key={activityLabel || 'assistant-generating'}
                          initial={{ opacity: 0, y: 5 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -5 }}
                          transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
                        >
                          {activityLabel || t('assistantGenerating')}
                        </motion.span>
                      </AnimatePresence>
                    </span>
                    <span className="chat-generating-dots" aria-hidden="true">
                      {[0, 160, 320].map((delay) => <span key={delay} style={{ animationDelay: `${delay}ms` }} />)}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
          </MeasuredRow>
        )}
        </div>
      </div>

      <AnimatePresence>
        {showScrollButton && (
          <div className="fixed bottom-[calc(env(safe-area-inset-bottom,0px)+6rem)] left-1/2 z-30 -translate-x-1/2">
            <motion.button
              type="button" onClick={onScrollToBottom}
              initial={{ opacity: 0, scale: 0.94 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.94 }}
              transition={{ duration: 0.16, ease: 'easeOut' }}
              className={`grid h-11 w-11 place-items-center rounded-full border shadow-lg backdrop-blur-xl transition-[background-color,color,border-color,transform] active:scale-95 ${isDark ? 'border-white/[0.08] bg-black/60 text-white/80 hover:bg-[#006bbd] hover:text-white' : 'border-gray-200 bg-white/80 text-gray-600 hover:bg-[#006bbd] hover:text-white'}`}
              aria-label={t('scrollToBottom')} title={t('scrollToBottom')}
            >
              <MdKeyboardArrowDown size={30} />
            </motion.button>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
