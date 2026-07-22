import type { ChangeEvent, KeyboardEvent, RefObject } from 'react';
import { useId } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { MdAdd, MdClose, MdImage, MdMic, MdPhone, MdSend, MdStop, MdUploadFile } from 'react-icons/md';
import type { ChatEngine, Collection } from '../../lib/api';
import { useI18n } from '../../i18n/I18nContext';
import { DOCUMENT_FILE_ACCEPT, IMAGE_FILE_ACCEPT } from '../../lib/attachmentAccept';
import { getBuiltinHint } from './commands';
import type { AttachedDocument, ChatPrompt } from './types';

interface ChatComposerProps {
  engine: ChatEngine;
  isDark: boolean;
  collections: Collection[];
  activeCollectionIds: string[];
  docUploadStatus: string;
  docConvertProgress: { file: string; progress: number } | null;
  attachedDocs: AttachedDocument[];
  docIndexCollectionId: string;
  attachedImage: string | null;
  imageError: string;
  streaming: boolean;
  attachmentMenuOpen: boolean;
  slashOpen: boolean;
  slashFilter: string;
  prompts: ChatPrompt[];
  input: string;
  placeholder: string;
  voiceSupported: boolean;
  callMode: boolean;
  listening: boolean;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  fileInputRef: RefObject<HTMLInputElement | null>;
  docInputRef: RefObject<HTMLInputElement | null>;
  attachmentMenuRef: RefObject<HTMLDivElement | null>;
  onToggleCollection: (id: string) => void;
  onDocIndexCollectionChange: (id: string) => void;
  onIndexAttachedDocs: () => void;
  onClearDocs: () => void;
  onRemoveImage: () => void;
  onPickImage: (event: ChangeEvent<HTMLInputElement>) => void;
  onPickDocs: (event: ChangeEvent<HTMLInputElement>) => void;
  onAttachmentMenuChange: (open: boolean) => void;
  onPromptSelect: (prompt: ChatPrompt) => void;
  onInputChange: (event: ChangeEvent<HTMLTextAreaElement>) => void;
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onToggleCall: () => void;
  onToggleDictation: () => void;
  onStop: () => void;
  onSend: () => void;
}

export default function ChatComposer({
  engine,
  isDark,
  collections,
  activeCollectionIds,
  docUploadStatus,
  docConvertProgress,
  attachedDocs,
  docIndexCollectionId,
  attachedImage,
  imageError,
  streaming,
  attachmentMenuOpen,
  slashOpen,
  slashFilter,
  prompts,
  input,
  placeholder,
  voiceSupported,
  callMode,
  listening,
  inputRef,
  fileInputRef,
  docInputRef,
  attachmentMenuRef,
  onToggleCollection,
  onDocIndexCollectionChange,
  onIndexAttachedDocs,
  onClearDocs,
  onRemoveImage,
  onPickImage,
  onPickDocs,
  onAttachmentMenuChange,
  onPromptSelect,
  onInputChange,
  onKeyDown,
  onToggleCall,
  onToggleDictation,
  onStop,
  onSend,
}: ChatComposerProps) {
  const { t, lang } = useI18n();
  const attachmentMenuId = useId();
  const documentCollectionId = useId();
  const filteredPrompts = prompts.filter((prompt) => prompt.name.includes(slashFilter));
  const canSend = Boolean(input.trim() || attachedImage || attachedDocs.length > 0);
  const showCallButton = !canSend;
  // Keep the mic control visible while composing so dictation can always be
  // stopped manually, even after text has been recognized into the input.
  const showDictationButton = !callMode;

  return (
    <div
      className={`shrink-0 border-t px-2 pt-2 sm:px-4 ${isDark ? 'border-white/[0.06]' : 'border-gray-200'}`}
      style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 12px)' }}
    >
      {engine === 'rag' && collections.length > 0 && (
        <div className="mb-2 flex items-center gap-2 overflow-x-auto pb-1">
          <span className={`shrink-0 text-[10px] uppercase tracking-wider ${isDark ? 'text-white/35' : 'text-gray-400'}`}>{t('activeCollections')}</span>
          {collections.map((collection) => {
            const active = activeCollectionIds.includes(collection.id);
            return (
              <button
                key={collection.id}
                onClick={() => onToggleCollection(collection.id)}
                className={`max-w-36 shrink-0 truncate rounded-full border px-3 py-1 text-[11px] font-medium transition-[background-color,color,border-color,transform] active:scale-95 ${active ? 'animate-soft-pulse border-[#006bbd]/50 bg-[#006bbd]/15 text-[#4ea3e0]' : isDark ? 'border-white/[0.08] bg-white/[0.03] text-white/45 hover:text-white/75' : 'border-gray-200 bg-gray-50 text-gray-500 hover:text-gray-800'}`}
                title={collection.name}
                aria-pressed={active}
              >
                {collection.name}
              </button>
            );
          })}
        </div>
      )}

      {(docUploadStatus || docConvertProgress) && (
        <div className={`mb-2 rounded-xl border px-3 py-2 ${isDark ? 'border-white/[0.08] bg-white/[0.03]' : 'border-gray-200 bg-gray-50'}`} role="status">
          {docUploadStatus && <p className={`text-xs ${isDark ? 'text-white/55' : 'text-gray-600'}`}>{docUploadStatus}</p>}
          {docConvertProgress && (
            <div className="mt-2">
              <div
                className={`h-1.5 w-full overflow-hidden rounded-full ${isDark ? 'bg-white/[0.08]' : 'bg-gray-200'}`}
                role="progressbar"
                aria-label={docConvertProgress.file}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={docConvertProgress.progress}
              >
                <div className="h-full rounded-full bg-[#006bbd] transition-[width] duration-300" style={{ width: `${Math.max(2, Math.min(100, docConvertProgress.progress))}%` }} />
              </div>
            </div>
          )}
        </div>
      )}

      {attachedDocs.length > 0 && (
        <div className={`mb-2 space-y-2 rounded-xl border px-3 py-2 ${isDark ? 'border-white/[0.08] bg-white/[0.03]' : 'border-gray-200 bg-gray-50'}`}>
          <div className="flex flex-wrap items-center gap-2">
            {attachedDocs.map((document) => (
              <span key={document.name} className={`inline-flex max-w-full items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] ${isDark ? 'bg-white/[0.06] text-white/60' : 'bg-white text-gray-600'}`}>
                <MdUploadFile size={14} />
                <span className="max-w-48 truncate">{document.name}</span>
                {document.truncated && <span className="text-amber-400">{t('truncated')}</span>}
              </span>
            ))}
            <button onClick={onClearDocs} className={`ml-auto rounded-md p-1 ${isDark ? 'text-white/35 hover:bg-white/[0.06] hover:text-white' : 'text-gray-400 hover:bg-gray-100 hover:text-gray-700'}`} aria-label={t('removeDocument')} title={t('removeDocument')}><MdClose size={16} /></button>
          </div>
          {engine === 'rag' && (
            <div className="flex flex-wrap items-center gap-2">
              <span className={`text-[11px] ${isDark ? 'text-white/35' : 'text-gray-400'}`}>{t('indexAttachedQuestion')}</span>
              <label htmlFor={documentCollectionId} className="sr-only">{t('activeCollections')}</label>
              <select
                id={documentCollectionId}
                value={docIndexCollectionId}
                onChange={(event) => onDocIndexCollectionChange(event.target.value)}
                className={`min-w-0 rounded-lg border px-2 py-1 text-[11px] outline-none ${isDark ? 'border-white/[0.08] bg-black text-white/70' : 'border-gray-200 bg-white text-gray-700'}`}
              >
                {collections.map((collection) => <option key={collection.id} value={collection.id}>{collection.name}</option>)}
              </select>
              <button onClick={onIndexAttachedDocs} className="rounded-lg bg-[#006bbd]/15 px-2.5 py-1 text-[11px] font-medium text-[#4ea3e0] hover:bg-[#006bbd]/25">{t('indexAttachedNow')}</button>
            </div>
          )}
        </div>
      )}

      {attachedImage && (
        <div className="relative mb-2 inline-block">
          <img src={attachedImage} alt={t('attachedImage')} className="h-20 w-auto rounded-lg border border-white/[0.1] object-cover" width={160} height={80} />
          <button onClick={onRemoveImage} className="absolute -right-2 -top-2 rounded-full border border-white/20 bg-black/80 p-0.5 text-white/80 hover:text-white" aria-label={t('removeImage')}><MdClose size={14} /></button>
        </div>
      )}
      {imageError && <p className="mb-2 text-xs text-red-300/90">{imageError}</p>}
      <input ref={fileInputRef} type="file" accept={IMAGE_FILE_ACCEPT} className="hidden" onChange={onPickImage} />
      <input ref={docInputRef} type="file" accept={DOCUMENT_FILE_ACCEPT} multiple className="hidden" onChange={onPickDocs} />

      <div className={`relative flex min-h-[52px] items-end gap-2 rounded-2xl border px-2 py-1 transition-[background-color,border-color,box-shadow] duration-300 focus-within:animate-border-glow sm:px-3 ${isDark ? 'border-white/[0.08] bg-white/[0.04] focus-within:border-[#006bbd]/40 focus-within:shadow-[0_0_20px_rgba(0,107,189,0.15)]' : 'border-gray-200 bg-gray-100 focus-within:border-[#006bbd]/40 focus-within:shadow-[0_0_20px_rgba(0,107,189,0.1)]'}`}>
        {!streaming && (
          <div ref={attachmentMenuRef} className="relative grid h-10 w-10 shrink-0 self-end place-items-center">
            <button
              type="button"
              onClick={() => onAttachmentMenuChange(!attachmentMenuOpen)}
              className={`grid h-10 w-10 place-items-center rounded-xl transition-colors ${isDark ? 'bg-white/[0.06] text-white/55 hover:bg-white/[0.1] hover:text-white' : 'bg-gray-200 text-gray-500 hover:bg-gray-300 hover:text-gray-700'}`}
              aria-label={`${t('attachImage')} / ${t('attachDocument')}`}
              aria-expanded={attachmentMenuOpen}
              aria-controls={attachmentMenuId}
            >
              <MdAdd size={18} />
            </button>
            <AnimatePresence>
              {attachmentMenuOpen && (
                <motion.div
                  id={attachmentMenuId}
                  role="menu"
                  initial={{ opacity: 0, y: 8, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8, scale: 0.96 }}
                  transition={{ duration: 0.16, ease: [0.16, 1, 0.3, 1] }} style={{ transformOrigin: 'bottom left' }}
                  className={`absolute bottom-full left-0 z-40 mb-2 min-w-44 overflow-hidden rounded-xl border p-1 shadow-xl ${isDark ? 'border-white/[0.08] bg-[#151515]' : 'border-gray-200 bg-white'}`}
                >
                  <button type="button" role="menuitem" onClick={() => { onAttachmentMenuChange(false); fileInputRef.current?.click(); }} className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${isDark ? 'text-white/75 hover:bg-white/[0.08]' : 'text-gray-700 hover:bg-gray-100'}`}><MdImage size={18} /> {t('attachImage')}</button>
                  <button type="button" role="menuitem" onClick={() => { onAttachmentMenuChange(false); docInputRef.current?.click(); }} className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${isDark ? 'text-white/75 hover:bg-white/[0.08]' : 'text-gray-700 hover:bg-gray-100'}`}><MdUploadFile size={18} /> {t('attachDocument')}</button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {slashOpen && filteredPrompts.length > 0 && (
          <div className={`absolute bottom-full left-0 right-0 z-30 mb-2 max-h-48 overflow-y-auto rounded-xl ${isDark ? 'border-white/[0.08] bg-black/95' : 'border-gray-200 bg-white shadow-lg'}`}>
            <div className="relative">
              {filteredPrompts.map((prompt) => (
                <button key={prompt.name} onClick={() => onPromptSelect(prompt)} className={`flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm ${isDark ? 'text-white/60 hover:bg-white/[0.04] hover:text-white' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'}`}>
                  <span className="font-mono text-[10px] text-[#006bbd]">/{prompt.name}</span>
                  {prompt.builtin && <span className="rounded bg-[#006bbd]/15 px-1 py-0.5 text-[8px] font-bold uppercase tracking-wider text-[#006bbd]">{t('builtInCommand')}</span>}
                  <span className={`truncate ${isDark ? 'text-white/30' : 'text-gray-400'}`}>{prompt.builtin ? getBuiltinHint(prompt.name, lang) : `${(prompt.text || '').slice(0, 50)}…`}</span>
                </button>
              ))}
              <div className={`pointer-events-none sticky bottom-0 left-0 right-0 h-6 bg-gradient-to-t ${isDark ? 'from-black/95' : 'from-white'} to-transparent`} />
            </div>
          </div>
        )}

        <textarea
          data-group-focus
          ref={inputRef}
          value={input}
          onChange={onInputChange}
          onKeyDown={onKeyDown}
          rows={1}
          placeholder={placeholder}
          aria-label={placeholder}
          className={`min-h-[42px] max-h-[50dvh] min-w-0 flex-1 resize-none overflow-y-auto bg-transparent py-2 text-sm leading-6 outline-none ${isDark ? 'text-white placeholder-white/30' : 'text-gray-800 placeholder-gray-400'}`}
          style={{ maxHeight: '50dvh' }}
          disabled={streaming}
        />

        <AnimatePresence initial={false}>
          {!streaming && showDictationButton && (
            <motion.button
              type="button"
              initial={{ opacity: 0, scale: 0.72, width: 0 }}
              animate={{ opacity: 1, scale: 1, width: 40 }}
              exit={{ opacity: 0, scale: 0.72, width: 0 }}
              transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
              onClick={onToggleDictation}
              className={`grid h-10 shrink-0 self-end place-items-center overflow-hidden rounded-xl transition-colors ${!voiceSupported ? isDark ? 'bg-white/[0.03] text-white/25 hover:text-white/45' : 'bg-gray-100 text-gray-300 hover:text-gray-500' : listening ? 'animate-pulse bg-red-500/30 text-red-400' : isDark ? 'bg-white/[0.06] text-white/50 hover:bg-white/[0.1] hover:text-white' : 'bg-gray-200 text-gray-500 hover:bg-gray-300 hover:text-gray-700'}`}
              aria-label={!voiceSupported ? t('dictationUnavailable') : listening ? t('stopDictation') : t('startDictation')}
              title={!voiceSupported ? t('dictationUnavailable') : listening ? t('stopDictation') : t('startDictation')}
            >
              <MdMic size={18} />
            </motion.button>
          )}
        </AnimatePresence>

        {streaming ? (
          <button onClick={onStop} className="grid h-10 w-10 shrink-0 self-end place-items-center rounded-xl bg-red-500/20 text-red-400 transition-colors hover:bg-red-500/30" aria-label={t('stop')}><MdStop size={18} /></button>
        ) : (
          <button
            onClick={showCallButton ? onToggleCall : onSend}
            className={`grid h-10 w-10 shrink-0 self-end place-items-center rounded-xl text-white transition-[background-color,transform] duration-200 ${showCallButton ? callMode ? 'bg-red-500/80 hover:bg-red-500' : 'bg-[#006bbd] hover:bg-[#0059a0]' : 'bg-[#006bbd] hover:bg-[#0059a0] animate-soft-pulse'}`}
            aria-label={showCallButton ? (callMode ? t('exitVoiceMode') : t('voiceMode')) : t('send')}
            title={showCallButton ? (callMode ? t('exitVoiceMode') : t('voiceMode')) : t('send')}
          >
            <AnimatePresence mode="wait" initial={false}>
              <motion.span
                key={showCallButton ? 'phone' : 'send'}
                initial={{ opacity: 0, rotate: -18, scale: 0.7 }}
                animate={{ opacity: 1, rotate: 0, scale: 1 }}
                exit={{ opacity: 0, rotate: 18, scale: 0.7 }}
                transition={{ duration: 0.16 }}
              >
                {showCallButton ? <MdPhone size={18} /> : <MdSend size={18} />}
              </motion.span>
            </AnimatePresence>
          </button>
        )}
      </div>
    </div>
  );
}
