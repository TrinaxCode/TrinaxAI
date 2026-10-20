import { useState, type ChangeEventHandler, type Dispatch, type RefObject, type SetStateAction } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { MdAdd, MdClose, MdFolder, MdImage, MdMic, MdSend, MdStop, MdUploadFile } from 'react-icons/md';
import type { AgentSession } from '../../hooks/useAgentHistory';
import type { AgentModelMode, AgentStep, AgentTurn, AttachedAgentDocument } from './agentTypes';
import type { Translate } from '../chat/types';
import { DOCUMENT_FILE_ACCEPT, IMAGE_FILE_ACCEPT } from '../../lib/attachmentAccept';
import FolderPicker from '../FolderPicker';
import ComposerLayout from '../chat/ComposerLayout';
import ConfirmModal from '../ConfirmModal';
import SpeakingIndicator from '../chat/SpeakingIndicator';
import AgentEmptyState from './AgentEmptyState';
import AgentHeader from './AgentHeader';
import AgentHistoryDrawer from './AgentHistoryDrawer';
import AgentTurns from './AgentTurns';
import '../chat/chat.css';
import '../chat/chat-modern.css';

export interface AgentHistoryView {
  sessions: AgentSession[];
  activeId: string | null;
  deleteSession: (id: string) => void;
}

export interface AgentInterfaceViewProps {
  onBack: () => void;
  isDark: boolean;
  t: Translate;
  historyOpen: boolean;
  historyClosing: boolean;
  historyDialogRef: RefObject<HTMLDivElement | null>;
  historyDialogId: string;
  historyTitleId: string;
  historyCloseButtonRef: RefObject<HTMLButtonElement | null>;
  search: string;
  setSearch: Dispatch<SetStateAction<string>>;
  filteredSessions: AgentSession[];
  history: AgentHistoryView;
  closeHistory: () => void;
  openSession: (id: string) => void;
  openHistory: () => void;
  pickerOpen: boolean;
  workspace: string;
  persistWorkspace: (value: string) => void;
  setPickerOpen: Dispatch<SetStateAction<boolean>>;
  mobileToolsOpen: boolean;
  mobileToolsRef: RefObject<HTMLDivElement | null>;
  mainContentRef: RefObject<HTMLDivElement | null>;
  setMobileToolsOpen: Dispatch<SetStateAction<boolean>>;
  running: boolean;
  knowledgeSearch: boolean;
  setKnowledgeSearch: Dispatch<SetStateAction<boolean>>;
  webSearch: boolean;
  setWebSearch: Dispatch<SetStateAction<boolean>>;
  deepResearch: boolean;
  setDeepResearch: Dispatch<SetStateAction<boolean>>;
  yoloMode: boolean;
  handleYoloChange: (enabled: boolean) => void;
  modelMode: AgentModelMode;
  setModelMode: Dispatch<SetStateAction<AgentModelMode>>;
  /** Concrete model configured for each non-auto mode, shown in the model picker. */
  modelNames: Partial<Record<AgentModelMode, string>>;
  startNewSession: () => void;
  /** Bumps on every new session so the welcome copy reshuffles like a new chat. */
  sessionResetKey: number;
  setWorkspace: Dispatch<SetStateAction<string>>;
  scrollRef: RefObject<HTMLDivElement | null>;
  turns: AgentTurn[];
  setInput: Dispatch<SetStateAction<string>>;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  editingIndex: number | null;
  editingText: string;
  setEditingText: Dispatch<SetStateAction<string>>;
  saveEdit: () => void;
  cancelEdit: () => void;
  startEdit: (index: number) => void;
  copyText: (text: string, key: string) => Promise<void>;
  copiedKey: string | null;
  regenerate: (index: number) => void;
  agentActivity: string;
  analyzingImage: boolean;
  approve: (step: AgentStep, approved: boolean) => void | Promise<void>;
  attachedImage: string | null;
  setAttachedImage: Dispatch<SetStateAction<string | null>>;
  attachedDocs: AttachedAgentDocument[];
  setAttachedDocs: Dispatch<SetStateAction<AttachedAgentDocument[]>>;
  imageError: string;
  setImageError: Dispatch<SetStateAction<string>>;
  imageInputRef: RefObject<HTMLInputElement | null>;
  onPickImage: ChangeEventHandler<HTMLInputElement>;
  docInputRef: RefObject<HTMLInputElement | null>;
  onPickDocs: ChangeEventHandler<HTMLInputElement>;
  input: string;
  placeholder: string;
  attachmentMenuRef: RefObject<HTMLDivElement | null>;
  attachmentMenuOpen: boolean;
  setAttachmentMenuOpen: Dispatch<SetStateAction<boolean>>;
  dictationAvailable: boolean;
  listening: boolean;
  toggleDictation: () => void;
  stop: () => void;
  send: () => void | Promise<void>;
  yoloConfirmOpen: boolean;
  setYoloMode: Dispatch<SetStateAction<boolean>>;
  setYoloConfirmOpen: Dispatch<SetStateAction<boolean>>;
  userDisplayName: string;
  ttsSupported: boolean;
  ttsActiveKey: string | null;
  ttsSpeaking: boolean;
  speak: (text: string, key: string) => void;
  stopSpeak: () => void;
}

export function AgentInterfaceView({
  onBack,
  isDark,
  t,
  historyOpen,
  historyClosing,
  historyDialogRef,
  historyDialogId,
  historyTitleId,
  historyCloseButtonRef,
  search,
  setSearch,
  filteredSessions,
  history,
  closeHistory,
  openSession,
  openHistory,
  pickerOpen,
  workspace,
  persistWorkspace,
  setPickerOpen,
  mobileToolsOpen,
  mobileToolsRef,
  setMobileToolsOpen,
  mainContentRef,
  running,
  knowledgeSearch,
  setKnowledgeSearch,
  webSearch,
  setWebSearch,
  deepResearch,
  setDeepResearch,
  yoloMode,
  handleYoloChange,
  modelMode,
  setModelMode,
  modelNames,
  startNewSession,
  sessionResetKey,
  setWorkspace,
  scrollRef,
  turns,
  setInput,
  inputRef,
  editingIndex,
  editingText,
  setEditingText,
  saveEdit,
  cancelEdit,
  startEdit,
  copyText,
  copiedKey,
  regenerate,
  agentActivity,
  analyzingImage,
  approve,
  attachedImage,
  setAttachedImage,
  attachedDocs,
  setAttachedDocs,
  imageError,
  setImageError,
  imageInputRef,
  onPickImage,
  docInputRef,
  onPickDocs,
  input,
  placeholder,
  attachmentMenuRef,
  attachmentMenuOpen,
  setAttachmentMenuOpen,
  dictationAvailable,
  listening,
  toggleDictation,
  stop,
  send,
  yoloConfirmOpen,
  setYoloMode,
  setYoloConfirmOpen,
  userDisplayName,
  ttsSupported,
  ttsActiveKey,
  ttsSpeaking,
  speak,
  stopSpeak,
}: AgentInterfaceViewProps) {
  const surface = isDark ? 'text-white' : 'text-gray-900';
  const [pendingDeleteSession, setPendingDeleteSession] = useState<AgentSession | null>(null);
  const prefersReducedMotion = useReducedMotion();
  // Real model reported by the backend for the latest turn, so the header never
  // shows a stale or guessed label.
  const activeModelName = [...turns].reverse().find((turn) => turn.role === 'assistant' && turn.model)?.model ?? '';
  const attachmentSurface = isDark ? 'border-white/[0.08] bg-white/[0.03]' : 'border-gray-200 bg-gray-50';

  return (
    <div className={`agent-page relative flex h-full min-h-0 w-full overflow-hidden ${surface}`}>
      {historyOpen && (
        <AgentHistoryDrawer
          isDark={isDark}
          t={t}
          closing={historyClosing}
          dialogRef={historyDialogRef}
          dialogId={historyDialogId}
          titleId={historyTitleId}
          closeButtonRef={historyCloseButtonRef}
          search={search}
          setSearch={setSearch}
          sessions={filteredSessions}
          activeId={history.activeId}
          close={closeHistory}
          openSession={openSession}
          newSession={startNewSession}
          requestDelete={setPendingDeleteSession}
        />
      )}

      {pickerOpen && (
        <FolderPicker
          initialPath={workspace}
          onSelect={(path) => { persistWorkspace(path); setPickerOpen(false); }}
          onClose={() => setPickerOpen(false)}
        />
      )}

      <div ref={mainContentRef} className="relative z-10 flex h-full min-h-0 w-full flex-col">
        <AgentHeader
          onBack={onBack}
          isDark={isDark}
          t={t}
          running={running}
          openHistory={openHistory}
          startNewSession={startNewSession}
          knowledgeSearch={knowledgeSearch}
          setKnowledgeSearch={setKnowledgeSearch}
          webSearch={webSearch}
          setWebSearch={setWebSearch}
          deepResearch={deepResearch}
          setDeepResearch={setDeepResearch}
          yoloMode={yoloMode}
          handleYoloChange={handleYoloChange}
          modelMode={modelMode}
          setModelMode={setModelMode}
          modelNames={modelNames}
          activeModelName={activeModelName}
          mobileToolsOpen={mobileToolsOpen}
          mobileToolsRef={mobileToolsRef}
          setMobileToolsOpen={setMobileToolsOpen}
        />

        {/* Workspace selector */}
        <div className={`flex shrink-0 items-center gap-2 border-b px-3 py-1.5 text-xs ${isDark ? 'border-white/[0.06]' : 'border-gray-200'}`}>
          <button
            onClick={() => setPickerOpen(true)}
            aria-label={t('agentPickFolder')}
            className={`grid h-11 w-11 shrink-0 place-items-center rounded-lg border transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${isDark ? 'border-white/10 text-[#4ea3e0] hover:bg-white/[0.06]' : 'border-gray-200 text-[#006bbd] hover:bg-gray-100'}`}
            title={t('agentPickFolder')}
          >
            <MdFolder size={15} />
          </button>
          <div className={`flex min-h-11 min-w-0 flex-1 items-center gap-1.5 rounded-lg border px-2 py-1 transition-colors ${isDark ? 'border-white/10 focus-within:border-[#006bbd]/50' : 'border-gray-200 focus-within:border-[#006bbd]/50'}`}>
            <input
              aria-label={t('agentWorkspaceRootLabel')}
              value={workspace}
              placeholder={t('agentWorkspaceRootLabel')}
              onChange={(e) => setWorkspace(e.target.value)}
              onBlur={(e) => persistWorkspace(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { persistWorkspace((e.target as HTMLInputElement).value); (e.target as HTMLInputElement).blur(); } }}
              spellCheck={false}
              className={`min-w-0 flex-1 bg-transparent font-mono text-base outline-hidden sm:text-sm ${isDark ? 'text-white/85 placeholder:text-white/55' : 'text-gray-800 placeholder:text-gray-500'}`}
            />
          </div>
        </div>

        {/* Conversation */}
        {turns.length === 0 ? (
          <div ref={scrollRef} className="flex min-h-0 flex-1 flex-col">
            <AgentEmptyState
              isDark={isDark}
              t={t}
              paused={running || Boolean(input.trim()) || historyOpen || pickerOpen}
              resetKey={sessionResetKey}
              onSelect={(prompt) => { setInput(prompt); inputRef.current?.focus(); }}
            />
          </div>
        ) : (
          <AgentTurns
            isDark={isDark}
            t={t}
            scrollRef={scrollRef}
            turns={turns}
            running={running}
            agentActivity={agentActivity}
            analyzingImage={analyzingImage}
            userDisplayName={userDisplayName}
            editingIndex={editingIndex}
            editingText={editingText}
            setEditingText={setEditingText}
            saveEdit={saveEdit}
            cancelEdit={cancelEdit}
            startEdit={startEdit}
            copyText={copyText}
            copiedKey={copiedKey}
            regenerate={regenerate}
            approve={approve}
            ttsSupported={ttsSupported}
            ttsActiveKey={ttsActiveKey}
            speak={speak}
            stopSpeak={stopSpeak}
          />
        )}

        <SpeakingIndicator speaking={ttsSpeaking} />

        {/* Composer — same footprint as the chat composer. */}
        <div
          className="chat-composer relative z-40 mx-auto w-full max-w-[56rem] shrink-0 px-3 pt-3 sm:px-6"
          style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 12px)' }}
        >
          <AnimatePresence initial={false}>
            {attachedDocs.length > 0 && (
              <motion.div
                layout
                initial={prefersReducedMotion ? false : { opacity: 0, height: 0, y: 8 }}
                animate={{ opacity: 1, height: 'auto', y: 0 }}
                exit={prefersReducedMotion ? { opacity: 1 } : { opacity: 0, height: 0, y: 8 }}
                transition={{ duration: prefersReducedMotion ? 0 : 0.22, ease: [0.16, 1, 0.3, 1] }}
                className={`mb-2 grid max-h-44 grid-cols-1 gap-2 overflow-y-auto rounded-xl border p-2 sm:grid-cols-2 ${attachmentSurface}`}
              >
                <AnimatePresence initial={false}>
                  {attachedDocs.map((document) => (
                    <motion.div
                      layout
                      key={document.name}
                      initial={prefersReducedMotion ? false : { opacity: 0, scale: 0.94, y: 6 }}
                      animate={{ opacity: 1, scale: 1, y: 0 }}
                      exit={prefersReducedMotion ? { opacity: 1 } : { opacity: 0, scale: 0.94, y: 6 }}
                      transition={{ duration: prefersReducedMotion ? 0 : 0.18, ease: [0.16, 1, 0.3, 1] }}
                      className={`min-w-0 rounded-lg px-2.5 py-2 text-xs ${isDark ? 'bg-white/[0.06] text-white/75' : 'bg-white text-gray-700'}`}
                    >
                      <div className="flex min-w-0 items-center gap-1.5">
                        <MdUploadFile size={14} className="shrink-0" />
                        <span className="truncate font-medium">{document.name}</span>
                        {document.truncated && <span className="text-amber-400">{t('truncated')}</span>}
                        <button type="button" onClick={() => setAttachedDocs((current) => current.filter((item) => item.name !== document.name))} className="ml-auto grid h-11 w-11 shrink-0 place-items-center rounded-lg text-current/70 hover:bg-white/[0.08] hover:text-current focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed]" aria-label={t('removeDocument')}><MdClose size={16} /></button>
                      </div>
                      <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-xs leading-relaxed opacity-80">{document.content.slice(0, 180)}</p>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </motion.div>
            )}
          </AnimatePresence>
          <AnimatePresence initial={false}>
            {attachedImage && (
              <motion.div
                initial={prefersReducedMotion ? false : { opacity: 0, scale: 0.82, y: 8 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={prefersReducedMotion ? { opacity: 1 } : { opacity: 0, scale: 0.82, y: 8 }}
                transition={{ duration: prefersReducedMotion ? 0 : 0.2, ease: [0.16, 1, 0.3, 1] }}
                className="relative mb-2 inline-block w-max"
              >
                <img src={attachedImage} alt={t('agentAttachImage')} className={`h-20 w-20 rounded-lg border object-cover ${isDark ? 'border-white/10' : 'border-gray-200'}`} width={80} height={80} />
                <button
                  onClick={() => { setAttachedImage(null); setImageError(''); }}
                  className="absolute right-1 top-1 grid h-11 w-11 place-items-center rounded-full border border-white/20 bg-black/80 text-white hover:bg-black focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed]"
                  aria-label={t('agentRemoveImage')}
                >
                  <MdClose size={16} />
                </button>
              </motion.div>
            )}
          </AnimatePresence>
          {imageError && <p role="alert" className={`mb-2 text-sm leading-relaxed ${isDark ? 'text-red-300' : 'text-red-700'}`}>{imageError}</p>}

          <input ref={imageInputRef} type="file" accept={IMAGE_FILE_ACCEPT} aria-label={t('agentAttachImage')} className="hidden" onChange={onPickImage} />
          <input ref={docInputRef} type="file" accept={DOCUMENT_FILE_ACCEPT} aria-label={t('attachDocument')} multiple className="hidden" onChange={onPickDocs} />

          <ComposerLayout
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send(); } }}
            placeholder={placeholder}
            name="agent-prompt"
            inputRef={inputRef}
            disabled={running}
            isDark={isDark}
            expandLabel={t('expandComposer')}
            closeLabel={t('closeExpandedComposer')}
            leftActions={(
              <div ref={attachmentMenuRef} className="relative grid h-11 w-11 shrink-0 place-items-center">
                <button type="button" onClick={() => setAttachmentMenuOpen((open) => !open)} disabled={running} className={`grid h-11 w-11 place-items-center rounded-xl transition-colors disabled:opacity-40 ${isDark ? 'text-white/55 hover:text-white' : 'text-gray-500 hover:text-gray-700'}`} aria-label={`${t('agentAttachImage')} / ${t('attachDocument')}`} aria-expanded={attachmentMenuOpen}><MdAdd size={18} /></button>
                <AnimatePresence>
                  {attachmentMenuOpen && <motion.div initial={{ opacity: 0, y: 8, scale: 0.96 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, y: 8, scale: 0.96 }} transition={{ duration: 0.16, ease: [0.16, 1, 0.3, 1] }} className={`absolute bottom-full left-0 z-40 mb-2 min-w-44 overflow-hidden rounded-xl border p-1 shadow-xl ${isDark ? 'border-white/[0.08] bg-[#101a26]' : 'border-gray-200 bg-white'}`}>
                    <button type="button" onClick={() => { setAttachmentMenuOpen(false); imageInputRef.current?.click(); }} className={`flex min-h-11 w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${isDark ? 'text-white/75 hover:bg-white/[0.08]' : 'text-gray-700 hover:bg-gray-100'}`}><MdImage size={18} /> {t('agentAttachImage')}</button>
                    <button type="button" onClick={() => { setAttachmentMenuOpen(false); docInputRef.current?.click(); }} className={`flex min-h-11 w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${isDark ? 'text-white/75 hover:bg-white/[0.08]' : 'text-gray-700 hover:bg-gray-100'}`}><MdUploadFile size={18} /> {t('attachDocument')}</button>
                  </motion.div>}
                </AnimatePresence>
              </div>
            )}
            rightActions={(
              <>
                <AnimatePresence initial={false}>
                  {dictationAvailable && !running && <motion.button type="button" initial={{ opacity: 0, scale: 0.72, width: 0 }} animate={{ opacity: 1, scale: 1, width: 44 }} exit={{ opacity: 0, scale: 0.72, width: 0 }} transition={{ duration: prefersReducedMotion ? 0 : 0.18, ease: [0.16, 1, 0.3, 1] }} onClick={toggleDictation} className={`grid h-11 shrink-0 place-items-center overflow-hidden rounded-xl transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${isDark ? 'text-white/50 hover:text-white' : 'text-gray-500 hover:text-gray-700'}`} aria-label={listening ? t('agentExitVoiceMode') : t('agentVoiceMode')} title={listening ? t('agentExitVoiceMode') : t('agentVoiceMode')} aria-pressed={listening}><MdMic size={18} /></motion.button>}
                </AnimatePresence>
                {running ? <button onClick={stop} className="composer-action-primary grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-red-500/20 text-red-400 transition-colors hover:bg-red-500/30 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed]" aria-label={t('agentStop')}><MdStop size={18} /></button> : <button onClick={() => void send()} disabled={!input.trim() && !attachedImage && attachedDocs.length === 0} className="composer-action-primary grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-[#006bbd] text-white transition-colors hover:bg-[#0059a0] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] disabled:cursor-not-allowed disabled:opacity-40" aria-label={t('agentSend')} title={t('agentSend')}><MdSend size={18} /></button>}
              </>
            )}
          />
        </div>
      </div>
      <ConfirmModal
        open={Boolean(pendingDeleteSession)}
        title={t('delete')}
        message={t('agentDeleteSessionConfirm')}
        confirmLabel={t('delete')}
        danger
        onConfirm={() => {
          if (pendingDeleteSession) history.deleteSession(pendingDeleteSession.id);
          setPendingDeleteSession(null);
        }}
        onCancel={() => setPendingDeleteSession(null)}
      />
      <ConfirmModal
        open={yoloConfirmOpen}
        title={t('agentYoloConfirmTitle')}
        message={t('agentYoloConfirmMessage')}
        confirmLabel={t('agentYoloConfirm')}
        danger
        onConfirm={() => { setYoloMode(true); setYoloConfirmOpen(false); }}
        onCancel={() => setYoloConfirmOpen(false)}
      />
    </div>
  );
}
