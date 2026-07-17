import { lazy, Suspense, type RefObject } from 'react';
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
import type { ChatDocumentAttachment, ChatMessage } from '../../lib/api';
import { useI18n } from '../../i18n/I18nContext';
import Sources from '../Sources';

// Markdown + KaTeX is the largest optional client feature. Do not download or
// evaluate it for a brand-new/empty chat; load it with the first saved answer.
const ChatMarkdown = lazy(() => import('./ChatMarkdown'));

function formatAttachmentSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function getLastUserText(messages: ChatMessage[], beforeMessage?: ChatMessage): string {
  const end = beforeMessage ? messages.indexOf(beforeMessage) + 1 : messages.length;
  for (let index = end - 1; index >= 0; index -= 1) {
    if (messages[index].role === 'user') return messages[index].displayContent ?? messages[index].content;
  }
  return '';
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
  ttsSpeaking: boolean;
  showScrollButton: boolean;
  activeCollections: string[];
  onScroll: () => void;
  onEditingTextChange: (text: string) => void;
  onCancelEdit: () => void;
  onSaveEdit: () => void;
  onStartEdit: (index: number) => void;
  onRegenerate: (index: number) => void;
  onCopy: (text: string, key: string) => void;
  onSpeak: (text: string, key: string) => void;
  onStopSpeak: () => void;
  onOpenAttachment: (attachment: ChatDocumentAttachment, inlineUrl?: string) => void;
  onOpenBrowser?: (file: string, collection?: string) => void;
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
  ttsSpeaking,
  showScrollButton,
  activeCollections,
  onScroll,
  onEditingTextChange,
  onCancelEdit,
  onSaveEdit,
  onStartEdit,
  onRegenerate,
  onCopy,
  onSpeak,
  onStopSpeak,
  onOpenAttachment,
  onOpenBrowser,
  onScrollToBottom,
}: MessageListProps) {
  const { t } = useI18n();
  const displayContent = (message: ChatMessage) => (
    message.displayContent ?? (message.content || (message.image ? '[image]' : ''))
  ).trim();

  return (
    <div className={`${messages.length === 0 && !streaming ? 'hidden' : 'relative flex-1'} min-h-0 min-w-0 max-w-full`}>
      <div
        ref={messagesRef}
        onScroll={onScroll}
        className="chat-messages h-full min-h-0 min-w-0 max-w-full space-y-4 overflow-y-auto overflow-x-hidden px-2 py-4 sm:px-4"
        style={{ overscrollBehavior: 'contain', WebkitOverflowScrolling: 'touch' }}
      >
        {messages.map((message, index) => (
          <motion.div
            key={`${index}-${message.role}`}
            initial={{ opacity: 0, y: 12, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.3, delay: 0, ease: [0.16, 1, 0.3, 1] }}
            className={`chat-row flex w-full min-w-0 max-w-full gap-2 sm:gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {message.role === 'assistant' && (
              <img src="/new-logo-for-AI.webp" alt="TrinaxAI" className="mt-0.5 h-7 w-7 shrink-0 rounded-full object-cover" width={28} height={28} />
            )}

            {editingIndex === index ? (
              <div className="chat-bubble-wrap min-w-0 flex-1">
                <textarea
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
                <div className={`chat-bubble min-w-0 overflow-hidden rounded-2xl rounded-bl-md px-4 py-2.5 text-sm leading-relaxed ${isDark ? 'bg-white/[0.06] text-white/90' : 'bg-gray-100 text-gray-800'}`}>
                  <Suspense fallback={<p className="chat-plain-text whitespace-pre-wrap">{message.content.trim()}</p>}>
                    <ChatMarkdown text={message.content.trim()} isDark={isDark} sources={message.sources} />
                  </Suspense>
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <button
                    onClick={() => onCopy(message.content.trim(), `msg-copy-${index}`)}
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
                      onClick={() => ttsActiveKey === `msg-${index}` ? onStopSpeak() : onSpeak(message.content.trim(), `msg-${index}`)}
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
                <div className="chat-bubble group/msg min-w-0 max-w-full rounded-2xl rounded-br-md bg-[#006bbd] px-4 py-2.5 text-sm leading-relaxed text-white transition-colors">
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
        ))}

        {streaming && (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, scale: 0.96 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="chat-row flex w-full min-w-0 max-w-full justify-start gap-2 sm:gap-3"
          >
            <img src="/new-logo-for-AI.webp" alt="TrinaxAI" className="mt-0.5 h-7 w-7 shrink-0 rounded-full object-cover" width={28} height={28} />
            <div className="chat-bubble-wrap min-w-0">
              <div className={`chat-bubble min-w-0 overflow-hidden rounded-2xl rounded-bl-md px-4 py-2.5 text-sm leading-relaxed ${isDark ? 'bg-white/[0.06] text-white/90' : 'bg-gray-100 text-gray-800'}`}>
                {activityLabel ? (
                  <div className="flex items-center gap-1.5">
                    <span className={`text-xs ${isDark ? 'text-white/50' : 'text-gray-400'}`}>{activityLabel}</span>
                    <span className="flex gap-0.5 pt-0.5" aria-hidden="true">
                      {[0, 200, 400].map((delay) => <span key={delay} className="h-1 w-1 animate-pulse rounded-full bg-[#006bbd]" style={{ animationDelay: `${delay}ms` }} />)}
                    </span>
                  </div>
                ) : streamedText ? (
                  <p className="chat-plain-text min-w-0 max-w-full whitespace-pre-wrap">{streamedText.trim()}</p>
                ) : (
                  <div className="flex items-center gap-1.5">
                    <span className={`text-xs ${isDark ? 'text-white/50' : 'text-gray-400'}`}>{ttsSpeaking ? t('speaking') : t('thinking')}</span>
                    <span className="flex gap-0.5 pt-0.5" aria-hidden="true">
                      {[0, 200, 400].map((delay) => <span key={delay} className="h-1 w-1 animate-pulse rounded-full bg-[#006bbd]" style={{ animationDelay: `${delay}ms` }} />)}
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
          <div className="fixed bottom-[calc(env(safe-area-inset-bottom,0px)+6rem)] left-1/2 z-30 -translate-x-1/2">
            <motion.button
              type="button" onClick={onScrollToBottom}
              initial={{ opacity: 0, scale: 0.94 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.94 }}
              transition={{ duration: 0.16, ease: 'easeOut' }}
              className={`grid h-11 w-11 place-items-center rounded-full border shadow-lg backdrop-blur-xl transition-[background-color,color,border-color,transform] active:scale-95 ${isDark ? 'border-white/[0.08] bg-black/85 text-white/80 hover:bg-[#006bbd] hover:text-white' : 'border-gray-200 bg-white/95 text-gray-600 hover:bg-[#006bbd] hover:text-white'}`}
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
