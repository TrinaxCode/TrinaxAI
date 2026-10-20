import type { ChangeEvent, KeyboardEvent, RefObject } from 'react';
import { useEffect, useId } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { MdAdd, MdClose, MdImage, MdMic, MdPhone, MdSend, MdStop, MdUploadFile } from 'react-icons/md';
import type { ChatEngine, Collection } from '../../lib/api';
import { useI18n } from '../../i18n/I18nContext';
import { DOCUMENT_FILE_ACCEPT, IMAGE_FILE_ACCEPT } from '../../lib/attachmentAccept';
import { getBuiltinHint } from './commands';
import type { AttachedDocument, ChatPrompt } from './types';
import ComposerLayout from './ComposerLayout';

interface ChatComposerProps {
  engine: ChatEngine;
  isDark: boolean;
  collections: Collection[];
  activeCollectionIds: string[];
  docUploadStatus: string;
  docConvertProgress: { file: string; progress: number } | null;
  attachedDocs: AttachedDocument[];
  docIndexCollectionId: string;
  attachedImages: Array<{ dataUrl: string; file: File }>;
  imageError: string;
  streaming: boolean;
  /** While TrinaxAI speaks, the speaking banner sits right above the composer. */
  speaking?: boolean;
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
  onRemoveImage: (index: number) => void;
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
  attachedImages,
  imageError,
  streaming,
  speaking = false,
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
  const prefersReducedMotion = useReducedMotion();
  const filteredPrompts = prompts.filter((prompt) => prompt.name.includes(slashFilter));
  const canSend = Boolean(input.trim() || attachedImages.length > 0 || attachedDocs.length > 0);
  const hasAttachmentSurface = Boolean(docUploadStatus || docConvertProgress || attachedDocs.length || attachedImages.length || imageError);
  const showCallButton = !canSend;
  // Keep the mic control visible while composing so dictation can always be
  // stopped manually, even after text has been recognized into the input.
  const showDictationButton = !callMode;

  // Keyboard shortcut: "/" or Cmd/Ctrl+K focuses the composer, so the
  // conversation keeps a fast keyboard path like the rest of the UI.
  useEffect(() => {
    if (callMode) return undefined;
    const focusComposer = (event: globalThis.KeyboardEvent) => {
      const target = event.target instanceof HTMLElement ? event.target : null;
      const typing = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);
      const isShortcut = (event.key === '/' && !event.metaKey && !event.ctrlKey && !event.altKey)
        || ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k');
      if (!isShortcut || typing || event.defaultPrevented) return;
      event.preventDefault();
      inputRef.current?.focus();
    };
    document.addEventListener('keydown', focusComposer);
    return () => document.removeEventListener('keydown', focusComposer);
  }, [callMode, inputRef]);

  return (
    <div
      className="chat-composer relative z-40 mx-auto w-full max-w-[56rem] shrink-0 px-3 pt-3 sm:px-6"
      style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 12px)' }}
    >
      <AnimatePresence initial={false}>
        {(docUploadStatus || docConvertProgress) && (
          <motion.div
            initial={prefersReducedMotion ? false : { opacity: 0, height: 0, y: 8 }}
            animate={{ opacity: 1, height: 'auto', y: 0 }}
            exit={prefersReducedMotion ? { opacity: 1 } : { opacity: 0, height: 0, y: 8 }}
            transition={{ duration: prefersReducedMotion ? 0 : 0.2, ease: [0.16, 1, 0.3, 1] }}
            className={`mb-2 overflow-hidden rounded-xl border px-3 py-2 ${isDark ? 'border-white/[0.08] bg-white/[0.03]' : 'border-gray-200 bg-gray-50'}`}
            role="status"
          >
          {docUploadStatus && <p className={`text-sm leading-relaxed ${isDark ? 'text-white/70' : 'text-gray-600'}`}>{docUploadStatus}</p>}
          {docConvertProgress && (
            <div className="mt-2">
              <div
                className={`h-1.5 w-full overflow-hidden rounded-full ${isDark ? 'bg-white/[0.08]' : 'bg-gray-200'}`}
                role="progressbar"
                aria-label={docConvertProgress.file}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.max(0, Math.min(100, docConvertProgress.progress))}
              >
                <div className="h-full rounded-full bg-[#006bbd] transition-[width] duration-300" style={{ width: `${Math.max(2, Math.min(100, docConvertProgress.progress))}%` }} />
              </div>
            </div>
          )}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence initial={false}>
        {attachedDocs.length > 0 && (
          <motion.div
            layout
            initial={prefersReducedMotion ? false : { opacity: 0, height: 0, y: 8 }}
            animate={{ opacity: 1, height: 'auto', y: 0 }}
            exit={prefersReducedMotion ? { opacity: 1 } : { opacity: 0, height: 0, y: 8 }}
            transition={{ duration: prefersReducedMotion ? 0 : 0.22, ease: [0.16, 1, 0.3, 1] }}
            className={`mb-2 space-y-2 overflow-hidden rounded-xl border px-3 py-2 ${isDark ? 'border-white/[0.08] bg-white/[0.03]' : 'border-gray-200 bg-gray-50'}`}
          >
          <div className="flex items-start gap-2">
            <div className="flex max-h-28 min-w-0 flex-1 flex-wrap items-start gap-2 overflow-y-auto overscroll-contain">
              <AnimatePresence initial={false}>
              {attachedDocs.map((document) => (
                <motion.span
                  layout
                  key={document.name}
                  initial={prefersReducedMotion ? false : { opacity: 0, scale: 0.88, y: 6 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={prefersReducedMotion ? { opacity: 1 } : { opacity: 0, scale: 0.88, y: 6 }}
                  transition={{ duration: prefersReducedMotion ? 0 : 0.18, ease: [0.16, 1, 0.3, 1] }}
                  className={`inline-flex max-w-full items-center gap-1.5 rounded-lg px-2 py-1 text-xs ${isDark ? 'bg-white/[0.06] text-white/70' : 'bg-white text-gray-600'}`}
                >
                <MdUploadFile size={14} />
                <span className="max-w-48 truncate">{document.name}</span>
                {document.truncated && <span className="text-amber-400">{t('truncated')}</span>}
                </motion.span>
              ))}
              </AnimatePresence>
            </div>
            <button onClick={onClearDocs} className={`grid h-11 w-11 shrink-0 place-items-center rounded-lg ${isDark ? 'text-white/65 hover:bg-white/[0.06] hover:text-white' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-800'}`} aria-label={t('removeDocument')} title={t('removeDocument')}><MdClose size={16} /></button>
          </div>
          {engine === 'rag' && (
            <div className="flex flex-wrap items-center gap-2">
              <span className={`text-sm ${isDark ? 'text-white/65' : 'text-gray-600'}`}>{t('indexAttachedQuestion')}</span>
              <label htmlFor={documentCollectionId} className="sr-only">{t('activeCollections')}</label>
              <select
                id={documentCollectionId}
                value={docIndexCollectionId}
                onChange={(event) => onDocIndexCollectionChange(event.target.value)}
                className={`min-h-11 min-w-0 rounded-lg border px-2 text-base outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] sm:text-sm ${isDark ? 'border-white/[0.08] bg-[#101a26] text-white/80' : 'border-gray-200 bg-white text-gray-700'}`}
              >
                {collections.map((collection) => <option key={collection.id} value={collection.id}>{collection.name}</option>)}
              </select>
              <button onClick={onIndexAttachedDocs} className={`min-h-11 rounded-lg bg-[#006bbd]/15 px-3 text-sm font-medium hover:bg-[#006bbd]/25 ${isDark ? 'text-[#4aa7ed]' : 'text-[#005a9e]'}`}>{t('indexAttachedNow')}</button>
            </div>
          )}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence initial={false}>
        {attachedImages.length > 0 && (
          <motion.div
            layout
            initial={prefersReducedMotion ? false : { opacity: 0, height: 0, y: 8 }}
            animate={{ opacity: 1, height: 'auto', y: 0 }}
            exit={prefersReducedMotion ? { opacity: 1 } : { opacity: 0, height: 0, y: 8 }}
            transition={{ duration: prefersReducedMotion ? 0 : 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="mb-2 flex gap-2 overflow-x-auto overflow-y-hidden overscroll-x-contain pb-1"
          >
            <AnimatePresence initial={false}>
              {attachedImages.map((image, index) => (
                <motion.div
                  layout
                  key={`${image.file.name}-${index}`}
                  initial={prefersReducedMotion ? false : { opacity: 0, scale: 0.82, y: 8 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={prefersReducedMotion ? { opacity: 1 } : { opacity: 0, scale: 0.82, y: 8 }}
                  transition={{ duration: prefersReducedMotion ? 0 : 0.2, ease: [0.16, 1, 0.3, 1] }}
                  className="relative shrink-0"
                >
              <img src={image.dataUrl} alt={`${t('attachedImage')} ${index + 1}`} className={`h-20 w-20 rounded-lg border object-cover ${isDark ? 'border-white/[0.1]' : 'border-gray-200'}`} width={80} height={80} />
              <button onClick={() => onRemoveImage(index)} className="absolute right-1 top-1 grid h-11 w-11 place-items-center rounded-full border border-white/20 bg-black/80 text-white hover:bg-black" aria-label={`${t('removeImage')} ${index + 1}`}><MdClose size={16} /></button>
                </motion.div>
              ))}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
      {imageError && <p role="alert" className={`mb-2 text-sm leading-relaxed ${isDark ? 'text-red-300' : 'text-red-700'}`}>{imageError}</p>}
      <input ref={fileInputRef} type="file" accept={IMAGE_FILE_ACCEPT} aria-label={t('attachImage')} multiple className="hidden" onChange={onPickImage} />
      <input ref={docInputRef} type="file" accept={DOCUMENT_FILE_ACCEPT} aria-label={t('attachDocument')} multiple className="hidden" onChange={onPickDocs} />

      <div className="relative">
        <AnimatePresence>
          {engine === 'rag' && collections.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.985 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.985 }}
              transition={{ duration: prefersReducedMotion ? 0 : 0.2, ease: [0.16, 1, 0.3, 1] }}
              className={`chat-active-collections pointer-events-none z-20 mb-2 flex items-center gap-2 overflow-x-auto rounded-xl px-2 py-1.5 ${hasAttachmentSurface || speaking ? 'relative' : 'absolute bottom-full left-0 right-0'} ${isDark ? 'text-white/70' : 'text-gray-600'}`}
            >
              <span className={`shrink-0 text-[11px] uppercase tracking-wider ${isDark ? 'text-white/65' : 'text-gray-600'}`}>{t('activeCollections')}</span>
              {collections.map((collection) => {
                const active = activeCollectionIds.includes(collection.id);
                return (
                  <button
                    key={collection.id}
                    onClick={() => onToggleCollection(collection.id)}
                    className={`pointer-events-auto min-h-11 max-w-36 shrink-0 truncate rounded-full border px-3 text-sm font-medium transition-[background-color,color,border-color,transform] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] active:scale-95 ${active ? `animate-soft-pulse border-[#006bbd]/50 ${isDark ? 'text-[#4aa7ed]' : 'text-[#005a9e]'}` : isDark ? 'border-white/[0.14] text-white/65 hover:text-white/90' : 'border-gray-300 text-gray-600 hover:text-gray-900'}`}
                    title={collection.name}
                    aria-pressed={active}
                  >
                    {collection.name}
                  </button>
                );
              })}
            </motion.div>
          )}
        </AnimatePresence>

        <ComposerLayout
        value={input}
        onChange={onInputChange}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        ariaKeyShortcuts="/ Meta+K Control+K"
        inputRef={inputRef}
        disabled={streaming}
        isDark={isDark}
        expandLabel={t('expandComposer')}
        closeLabel={t('closeExpandedComposer')}
        floatingContent={(
          <AnimatePresence>
            {slashOpen && filteredPrompts.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 10, scale: 0.985 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 10, scale: 0.985 }}
                transition={{ duration: prefersReducedMotion ? 0 : 0.18, ease: [0.16, 1, 0.3, 1] }}
                className={`absolute bottom-full left-0 right-0 z-30 mb-2 max-h-48 overflow-y-auto rounded-xl border ${isDark ? 'border-white/[0.08] bg-[#101a26]/95' : 'border-gray-200 bg-white shadow-lg'}`}
              >
                {filteredPrompts.map((prompt) => (
                  <button key={prompt.name} onClick={() => onPromptSelect(prompt)} className={`flex min-h-11 w-full items-center gap-3 px-4 py-2.5 text-left text-sm ${isDark ? 'text-white/75 hover:bg-white/[0.04] hover:text-white' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'}`}>
                    <span className={`font-mono text-xs ${isDark ? 'text-[#4aa7ed]' : 'text-[#005a9e]'}`}>/{prompt.name}</span>
                    {prompt.builtin && <span className={`rounded bg-[#006bbd]/15 px-1 py-0.5 text-[10px] font-bold uppercase tracking-wider ${isDark ? 'text-[#4aa7ed]' : 'text-[#005a9e]'}`}>{t('builtInCommand')}</span>}
                    <span className="truncate">{prompt.builtin ? getBuiltinHint(prompt.name, lang) : `${(prompt.text || '').slice(0, 50)}...`}</span>
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        )}
        leftActions={!streaming && (
          <div ref={attachmentMenuRef} className="relative grid h-11 w-11 shrink-0 place-items-center">
            <button type="button" onClick={() => onAttachmentMenuChange(!attachmentMenuOpen)} className={`grid h-11 w-11 place-items-center rounded-xl transition-colors ${isDark ? 'text-white/55 hover:text-white' : 'text-gray-500 hover:text-gray-700'}`} aria-label={`${t('attachImage')} / ${t('attachDocument')}`} aria-expanded={attachmentMenuOpen} aria-controls={attachmentMenuId}><MdAdd size={18} /></button>
            <AnimatePresence>
              {attachmentMenuOpen && <motion.div id={attachmentMenuId} role="menu" initial={{ opacity: 0, y: 8, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8, scale: 0.96 }} transition={{ duration: prefersReducedMotion ? 0 : 0.16, ease: [0.16, 1, 0.3, 1] }} className={`absolute bottom-full left-0 z-40 mb-2 min-w-44 overflow-hidden rounded-xl border p-1 shadow-xl ${isDark ? 'border-white/[0.08] bg-[#101a26]' : 'border-gray-200 bg-white'}`}>
                <button type="button" role="menuitem" onClick={() => { onAttachmentMenuChange(false); fileInputRef.current?.click(); }} className={`flex min-h-11 w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${isDark ? 'text-white/75 hover:bg-white/[0.08]' : 'text-gray-700 hover:bg-gray-100'}`}><MdImage size={18} /> {t('attachImage')}</button>
                <button type="button" role="menuitem" onClick={() => { onAttachmentMenuChange(false); docInputRef.current?.click(); }} className={`flex min-h-11 w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${isDark ? 'text-white/75 hover:bg-white/[0.08]' : 'text-gray-700 hover:bg-gray-100'}`}><MdUploadFile size={18} /> {t('attachDocument')}</button>
              </motion.div>}
            </AnimatePresence>
          </div>
        )}
        rightActions={(
          <>
            <AnimatePresence initial={false}>
              {!streaming && showDictationButton && <motion.button type="button" initial={{ opacity: 0, scale: 0.72, width: 0 }} animate={{ opacity: 1, scale: 1, width: 44 }} exit={{ opacity: 0, scale: 0.72, width: 0 }} transition={{ duration: prefersReducedMotion ? 0 : 0.18, ease: [0.16, 1, 0.3, 1] }} onClick={onToggleDictation} className={`grid h-11 shrink-0 place-items-center overflow-hidden rounded-xl transition-colors ${!voiceSupported ? isDark ? 'text-white/25 hover:text-white/45' : 'text-gray-300 hover:text-gray-500' : isDark ? 'text-white/50 hover:text-white' : 'text-gray-500 hover:text-gray-700'}`} aria-label={!voiceSupported ? t('dictationUnavailable') : listening ? t('stopDictation') : t('startDictation')} title={!voiceSupported ? t('dictationUnavailable') : listening ? t('stopDictation') : t('startDictation')} aria-pressed={listening}><MdMic size={18} /></motion.button>}
            </AnimatePresence>
            {streaming ? <button onClick={onStop} className="composer-action-primary grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-red-500/20 text-red-400 transition-colors hover:bg-red-500/30" aria-label={t('stop')}><MdStop size={18} /></button> : <button onClick={showCallButton ? onToggleCall : onSend} className={`composer-action-primary grid h-11 w-11 shrink-0 place-items-center rounded-xl text-white transition-[background-color,transform] duration-200 ${showCallButton ? callMode ? 'bg-red-500/80 hover:bg-red-500' : 'bg-[#006bbd] hover:bg-[#0059a0]' : 'bg-[#006bbd] hover:bg-[#0059a0] animate-soft-pulse'}`} aria-label={showCallButton ? (callMode ? t('exitVoiceMode') : t('voiceMode')) : t('send')} title={showCallButton ? (callMode ? t('exitVoiceMode') : t('voiceMode')) : t('send')}><AnimatePresence mode="wait" initial={false}><motion.span key={showCallButton ? 'phone' : 'send'} initial={{ opacity: 0, rotate: -18, scale: 0.7 }} animate={{ opacity: 1, rotate: 0, scale: 1 }} exit={{ opacity: 0, rotate: 18, scale: 0.7 }} transition={{ duration: prefersReducedMotion ? 0 : 0.16 }}>{showCallButton ? <MdPhone size={18} /> : <MdSend size={18} />}</motion.span></AnimatePresence></button>}
          </>
        )}
        />
      </div>
    </div>
  );
}
