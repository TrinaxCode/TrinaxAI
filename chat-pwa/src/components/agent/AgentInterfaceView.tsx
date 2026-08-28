import type { ChangeEventHandler, Dispatch, RefObject, SetStateAction } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { MdAdd, MdBuild, MdCheck, MdClose, MdContentCopy, MdDelete, MdEdit, MdFolder, MdHistory, MdImage, MdMic, MdPublic, MdRefresh, MdScience, MdSearch, MdSend, MdSmartToy, MdStop, MdStorage, MdUploadFile } from 'react-icons/md';
import type { AgentSession } from '../../hooks/useAgentHistory';
import type { AgentModelMode, AgentStep, AgentTurn, AttachedAgentDocument } from './agentTypes';
import type { Translate } from '../chat/types';
import { DOCUMENT_FILE_ACCEPT, IMAGE_FILE_ACCEPT } from '../../lib/attachmentAccept';
import FolderPicker from '../FolderPicker';
import BackButton from '../BackButton';
import ChatMarkdown from '../chat/ChatMarkdown';
import ComposerLayout from '../chat/ComposerLayout';
import ConfirmModal from '../ConfirmModal';

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
  historyDialogRef: RefObject<HTMLElement | null>;
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
  startNewSession: () => void;
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
  startNewSession,
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
}: AgentInterfaceViewProps) {
  const surface = isDark ? 'text-white' : 'text-gray-900';
  const subtle = isDark ? 'text-white/50' : 'text-gray-500';
  const cardBg = isDark ? 'bg-white/[0.04] border-white/[0.08]' : 'bg-gray-50 border-gray-200';

  return (
    <div className={`agent-page relative flex h-full min-h-0 w-full overflow-hidden ${surface}`}>
      {/* History sidebar */}
      {historyOpen && (
        <>
          <div aria-hidden="true" className={`fixed inset-0 z-[55] bg-black/40 ${historyClosing ? 'animate-overlay-out' : 'animate-overlay-in'}`} onClick={closeHistory} />
          <aside
            ref={historyDialogRef}
            id={historyDialogId}
            role="dialog"
            aria-modal="true"
            aria-labelledby={historyTitleId}
            className={`fixed left-0 top-0 z-[60] flex h-dvh w-[85vw] max-w-[300px] flex-col border-r backdrop-blur-xl sm:w-72 ${historyClosing ? 'animate-drawer-out' : 'animate-drawer-in'} ${isDark ? 'border-white/10 bg-black/85' : 'border-gray-200 bg-white/90'}`}
            style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
          >
            <div className={`flex items-center gap-2 border-b px-3 py-3 ${isDark ? 'border-white/10' : 'border-gray-200'}`} style={{ paddingTop: 'calc(env(safe-area-inset-top, 0px) + 0.75rem)' }}>
              <MdHistory size={18} className="text-[#006bbd]" />
              <h2 id={historyTitleId} className="text-sm font-semibold">{t('agentHistory')}</h2>
              <button ref={historyCloseButtonRef} onClick={closeHistory} className={`ml-auto rounded-lg p-1 ${isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`} aria-label={t('close')}>
                <MdClose size={18} />
              </button>
            </div>
            <div className="p-2">
              <div className={`flex items-center gap-2 rounded-lg border px-2.5 py-1.5 ${isDark ? 'border-white/10 bg-white/[0.03]' : 'border-gray-200 bg-gray-50'}`}>
                <MdSearch size={15} className={subtle} />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={t('agentSearchHistory')}
                  aria-label={t('agentSearchHistory')}
                  className="min-w-0 flex-1 bg-transparent text-xs outline-none"
                />
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
              {filteredSessions.length === 0 ? (
                <p className={`px-2 py-6 text-center text-xs ${subtle}`}>{t('agentNoHistory')}</p>
              ) : (
                filteredSessions.map((session) => (
                  <div
                    key={session.id}
                    className={`group flex items-center gap-1 rounded-lg px-2 py-2 text-sm ${session.id === history.activeId ? (isDark ? 'bg-white/10' : 'bg-gray-100') : isDark ? 'hover:bg-white/[0.05]' : 'hover:bg-gray-50'}`}
                  >
                    <button onClick={() => openSession(session.id)} className="min-w-0 flex-1 truncate text-left">
                      {session.title || t('agentUntitled')}
                    </button>
                    <button
                      onClick={() => history.deleteSession(session.id)}
                      className={`shrink-0 rounded p-1 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:opacity-100 ${isDark ? 'text-white/40 hover:text-red-400' : 'text-gray-500 hover:text-red-600'}`}
                      aria-label={t('delete')}
                    >
                      <MdDelete size={15} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </aside>
        </>
      )}

      {pickerOpen && (
        <FolderPicker
          initialPath={workspace}
          onSelect={(path) => { persistWorkspace(path); setPickerOpen(false); }}
          onClose={() => setPickerOpen(false)}
        />
      )}

      <div ref={mainContentRef} className="relative z-10 flex h-full min-h-0 w-full flex-col">
        {/* Header */}
        <nav
          className={`page-header relative z-10 flex shrink-0 items-center gap-2 border-b px-3 backdrop-blur-xl ${isDark ? 'border-white/[0.06] bg-black/40' : 'border-gray-200 bg-white/50'}`}
          style={{ minHeight: '46px', paddingTop: 'env(safe-area-inset-top, 0px)' }}
        >
          <BackButton onClick={onBack} label={t('back')} isDark={isDark} />
          <button
            onClick={openHistory}
            className={`rounded-xl p-2 transition-colors ${isDark ? 'text-white/60 hover:bg-white/[0.06] hover:text-white' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'}`}
            aria-label={t('agentHistory')}
          >
            <MdHistory size={19} />
          </button>
          <h1 className="animate-brand min-w-0 truncate text-base font-bold tracking-normal sm:text-lg">{t('agentTitle')}</h1>
          <div className="ml-auto flex shrink-0 items-center gap-0.5 sm:gap-1">
            <div className="hidden items-center gap-0.5 sm:flex">
              <button
                type="button"
                onClick={() => setKnowledgeSearch((value) => !value)}
                disabled={running}
                className={`flex h-9 w-9 items-center justify-center rounded-lg transition-colors disabled:opacity-40 ${knowledgeSearch ? 'bg-[#006bbd] text-white' : isDark ? 'text-white/55 hover:bg-white/[0.06] hover:text-white' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'}`}
                aria-label={knowledgeSearch ? t('agentRagOn') : t('agentRagOff')}
                title={t('agentRag')}
                aria-pressed={knowledgeSearch}
              >
                <MdStorage size={18} />
              </button>
              <button
                type="button"
                onClick={() => setWebSearch((value) => !value)}
                disabled={running}
                className={`flex h-9 w-9 items-center justify-center rounded-lg transition-colors disabled:opacity-40 ${webSearch ? 'bg-[#006bbd] text-white' : isDark ? 'text-white/55 hover:bg-white/[0.06] hover:text-white' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'}`}
                aria-label={webSearch ? t('agentWebSearchOn') : t('agentWebSearchOff')}
                title={t('agentWebSearch')}
                aria-pressed={webSearch}
              >
                <MdPublic size={18} />
              </button>
              <button
                type="button"
                onClick={() => setDeepResearch((value) => !value)}
                disabled={running}
                className={`flex h-9 w-9 items-center justify-center rounded-lg transition-colors disabled:opacity-40 ${deepResearch ? 'bg-[#006bbd] text-white' : isDark ? 'text-white/55 hover:bg-white/[0.06] hover:text-white' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'}`}
                aria-label={t('agentDeepResearch')}
                title={t('agentDeepResearch')}
                aria-pressed={deepResearch}
              >
                <MdScience size={18} />
              </button>
              <AgentYoloButton enabled={yoloMode} disabled={running} onChange={handleYoloChange} isDark={isDark} t={t} />
            </div>
            <div ref={mobileToolsRef} className="relative mr-1 sm:hidden">
              <button
                type="button"
                onClick={() => setMobileToolsOpen((open) => !open)}
                className={`grid min-h-10 min-w-10 place-items-center rounded-xl transition-colors ${mobileToolsOpen ? 'bg-[#006bbd]/20 text-[#006bbd] ring-1 ring-[#006bbd]/40' : isDark ? 'text-white/65 hover:bg-white/[0.06] hover:text-white' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-800'}`}
                aria-label={t('agentTools')}
                aria-expanded={mobileToolsOpen}
                title={t('agentTools')}
              >
                <MdBuild size={17} />
              </button>
              <AnimatePresence>
                {mobileToolsOpen && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setMobileToolsOpen(false)} />
                    <motion.div
                      initial={{ opacity: 0, scale: 0.94, y: -6 }}
                      animate={{ opacity: 1, scale: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.94, y: -6 }}
                      transition={{ duration: 0.15 }}
                      className={`absolute right-[-0.5rem] top-full z-50 mt-1.5 max-h-[calc(100dvh-4rem)] w-[min(17rem,calc(100vw-1rem))] overflow-y-auto overflow-x-hidden rounded-xl border p-1 shadow-lg backdrop-blur-xl ${isDark ? 'border-white/[0.08] bg-[#1a1a1a]/95 shadow-black/40' : 'border-gray-200 bg-white/95 shadow-gray-200/80'}`}
                    >
                      <button
                        type="button"
                        onClick={() => { setKnowledgeSearch((value) => !value); setMobileToolsOpen(false); }}
                        disabled={running}
                        className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition-colors disabled:opacity-40 ${knowledgeSearch ? 'bg-[#006bbd]/15 text-[#4ea3e0]' : isDark ? 'text-white/75 hover:bg-white/[0.06]' : 'text-gray-700 hover:bg-gray-100'}`}
                        aria-label={knowledgeSearch ? t('agentRagOn') : t('agentRagOff')}
                        aria-pressed={knowledgeSearch}
                      >
                        <MdStorage size={17} />
                        <span className="min-w-0 flex-1 truncate">{t('agentRag')}</span>
                        {knowledgeSearch && <MdCheck size={14} aria-hidden="true" />}
                      </button>
                      <button
                        type="button"
                        onClick={() => { setWebSearch((value) => !value); setMobileToolsOpen(false); }}
                        disabled={running}
                        className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition-colors disabled:opacity-40 ${webSearch ? 'bg-[#006bbd]/15 text-[#4ea3e0]' : isDark ? 'text-white/75 hover:bg-white/[0.06]' : 'text-gray-700 hover:bg-gray-100'}`}
                        aria-label={webSearch ? t('agentWebSearchOn') : t('agentWebSearchOff')}
                        aria-pressed={webSearch}
                      >
                        <MdPublic size={17} />
                        <span className="min-w-0 flex-1 truncate">{t('agentWebSearch')}</span>
                        {webSearch && <MdCheck size={14} aria-hidden="true" />}
                      </button>
                      <button
                        type="button"
                        onClick={() => { setDeepResearch((value) => !value); setMobileToolsOpen(false); }}
                        disabled={running}
                        className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition-colors disabled:opacity-40 ${deepResearch ? 'bg-[#006bbd]/15 text-[#4ea3e0]' : isDark ? 'text-white/75 hover:bg-white/[0.06]' : 'text-gray-700 hover:bg-gray-100'}`}
                        aria-label={t('agentDeepResearch')}
                        aria-pressed={deepResearch}
                      >
                        <MdScience size={17} />
                        <span className="min-w-0 flex-1 truncate">{t('agentDeepResearch')}</span>
                        {deepResearch && <MdCheck size={14} aria-hidden="true" />}
                      </button>
                      <div className={`my-1 border-t ${isDark ? 'border-white/[0.08]' : 'border-gray-200'}`} />
                      <AgentYoloButton enabled={yoloMode} disabled={running} onChange={(value) => { handleYoloChange(value); setMobileToolsOpen(false); }} isDark={isDark} t={t} mobile />
                      <label className={`flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs ${isDark ? 'text-white/75' : 'text-gray-700'}`}>
                        <span className="min-w-0 flex-1 truncate">{t('agentModel')}</span>
                        <select
                          value={modelMode}
                          onChange={(event) => { setModelMode(event.target.value as AgentModelMode); setMobileToolsOpen(false); }}
                          disabled={running}
                          aria-label={t('agentModel')}
                          className={`max-w-32 rounded-lg border px-2 py-1 text-xs outline-none disabled:opacity-40 ${isDark ? 'border-white/10 bg-black text-white/70' : 'border-gray-200 bg-white text-gray-600'}`}
                        >
                          <option value="auto">{t('agentModelAuto')}</option>
                          <option value="chat">{t('agentModelChat')}</option>
                          <option value="deep">{t('agentModelDeep')}</option>
                          <option value="fast">{t('agentModelFast')}</option>
                        </select>
                      </label>
                    </motion.div>
                  </>
                )}
              </AnimatePresence>
            </div>
            <select
              value={modelMode}
              onChange={(event) => setModelMode(event.target.value as AgentModelMode)}
              disabled={running}
              aria-label={t('agentModel')}
              title={t('agentModel')}
              className={`hidden max-w-28 rounded-lg border px-2 py-1 text-xs outline-none disabled:opacity-40 sm:block ${isDark ? 'border-white/10 bg-black/40 text-white/70' : 'border-gray-200 bg-white/70 text-gray-600'}`}
            >
              <option value="auto">{t('agentModelAuto')}</option>
              <option value="chat">{t('agentModelChat')}</option>
              <option value="deep">{t('agentModelDeep')}</option>
              <option value="fast">{t('agentModelFast')}</option>
            </select>
          </div>
          <button
            onClick={startNewSession}
            className={`rounded-xl p-2 transition-colors ${isDark ? 'text-white/60 hover:bg-white/[0.06] hover:text-white' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'}`}
            aria-label={t('agentNewSession')}
            title={t('agentNewSession')}
          >
            <MdAdd size={20} />
          </button>
        </nav>

        {/* Workspace selector */}
        <div className={`flex shrink-0 items-center gap-2 border-b px-3 py-2 text-xs backdrop-blur-xl ${isDark ? 'border-white/[0.06] bg-black/30' : 'border-gray-200 bg-white/40'}`}>
          <button
            onClick={() => setPickerOpen(true)}
            className={`flex shrink-0 items-center gap-1.5 rounded-lg border px-2 py-1 font-medium transition-colors ${isDark ? 'border-white/10 text-white/70 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-600 hover:bg-gray-100'}`}
            title={t('agentPickFolder')}
          >
            <MdFolder size={14} className="text-[#006bbd]" />
            {t('agentPickFolder')}
          </button>
          <input
            aria-label={t('agentWorkspaceRootLabel')}
            value={workspace}
            onChange={(e) => setWorkspace(e.target.value)}
            onBlur={(e) => persistWorkspace(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { persistWorkspace((e.target as HTMLInputElement).value); (e.target as HTMLInputElement).blur(); } }}
            spellCheck={false}
            className={`min-w-0 flex-1 rounded-md border bg-transparent px-2 py-1 font-mono text-xs outline-none ${isDark ? 'border-white/10 text-white/80 focus:border-[#006bbd]/50' : 'border-gray-200 text-gray-700 focus:border-[#006bbd]/50'}`}
          />
        </div>

        {/* Conversation */}
        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-3 py-4 sm:px-4">
          {turns.length === 0 ? (
            <div className={`agent-empty-state flex h-full flex-col items-center justify-center gap-5 px-6 text-center ${subtle}`}>
              <MdSmartToy size={76} className="agent-empty-avatar animate-agent-avatar animate-float" />
              <p className="max-w-sm text-sm leading-relaxed">{t('agentEmptyHint')}</p>
              <div className="flex max-w-lg flex-wrap justify-center gap-2">
                {[
                  ['quickChipFindBugs', 'quickChipFindBugsPrompt'],
                  ['quickChipCodeReview', 'quickChipCodeReviewPrompt'],
                  ['quickChipExplainCode', 'quickChipExplainCodePrompt'],
                ].map(([label, prompt]) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => { setInput(t(prompt as Parameters<typeof t>[0])); inputRef.current?.focus(); }}
                    className={`rounded-full border px-3 py-2 text-xs font-medium transition-colors ${isDark ? 'border-white/10 bg-white/[0.04] text-white/70 hover:bg-white/[0.08] hover:text-white' : 'border-gray-200 bg-white/70 text-gray-600 hover:bg-gray-100 hover:text-gray-900'}`}
                  >
                    {t(label as Parameters<typeof t>[0])}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-4">
              {turns.map((turn, idx) => (
                <div key={idx} className={`animate-fade-up ${turn.role === 'user' ? 'flex justify-end' : 'flex justify-start'}`}>
                  {turn.role === 'user' ? (
                    editingIndex === idx ? (
                      <div className="flex w-full max-w-[85%] flex-col gap-2">
                        <textarea
                          aria-label={t('saveAndResend')}
                          value={editingText}
                          onChange={(e) => {
                            setEditingText(e.target.value);
                            e.target.style.height = 'auto';
                            e.target.style.height = `${e.target.scrollHeight}px`;
                          }}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); saveEdit(); }
                            if (e.key === 'Escape') cancelEdit();
                          }}
                          rows={1}
                          className={`w-full resize-none overflow-hidden rounded-xl border border-[#006bbd]/40 px-3 py-2 text-sm outline-none focus:border-[#006bbd] ${isDark ? 'bg-[#006bbd]/20 text-white' : 'bg-[#006bbd]/10 text-gray-900'}`}
                        />
                        <div className="flex justify-end gap-2">
                          <button onClick={saveEdit} className="rounded-lg bg-[#006bbd] px-2.5 py-1 text-xs font-medium text-white hover:bg-[#0059a0]">{t('saveAndResend')}</button>
                          <button onClick={cancelEdit} className={`rounded-lg px-2.5 py-1 text-xs font-medium ${isDark ? 'bg-white/10 text-white/70 hover:text-white' : 'bg-gray-200 text-gray-700 hover:text-gray-900'}`}>{t('cancel')}</button>
                        </div>
                      </div>
                    ) : (
                      <div className="group flex max-w-[85%] flex-col items-end gap-2">
                        {turn.image && (
                          <img src={turn.image} alt={t('agentAttachImage')} className="max-h-48 w-auto rounded-2xl rounded-br-md border border-white/10 object-cover" width={320} height={192} />
                        )}
                        {turn.documents?.length ? (
                          <div className="flex max-w-full flex-wrap justify-end gap-1.5">
                            {turn.documents.map((document) => (
                              <div key={document.name} className="max-w-64 overflow-hidden rounded-xl bg-[#006bbd]/80 px-2.5 py-2 text-left text-white/90">
                                <div className="flex min-w-0 items-center gap-1.5 text-[11px] font-medium"><MdUploadFile size={14} className="shrink-0" /><span className="truncate">{document.name}</span>{document.truncated && <span className="text-amber-200">{t('truncated')}</span>}</div>
                                {document.preview && <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-[10px] leading-relaxed text-white/65">{document.preview}</p>}
                              </div>
                            ))}
                          </div>
                        ) : null}
                        {turn.content && (
                          <div className="rounded-2xl bg-[#006bbd] px-4 py-2.5 text-sm text-white">
                            {turn.content}
                          </div>
                        )}
                        <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                          <button
                            onClick={() => startEdit(idx)}
                            disabled={running}
                            className={`rounded-md p-1 transition-colors disabled:opacity-30 ${isDark ? 'text-white/35 hover:bg-white/[0.06] hover:text-white/75' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'}`}
                            title={t('edit')} aria-label={t('edit')}
                          >
                            <MdEdit size={15} />
                          </button>
                          <button
                            onClick={() => copyText(turn.content, `u-${idx}`)}
                            className={`rounded-md p-1 transition-colors ${copiedKey === `u-${idx}` ? 'bg-[#006bbd]/10 text-[#006bbd]' : isDark ? 'text-white/35 hover:bg-white/[0.06] hover:text-white/75' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'}`}
                            title={copiedKey === `u-${idx}` ? t('copied') : t('copy')} aria-label={copiedKey === `u-${idx}` ? t('copied') : t('copy')}
                          >
                            {copiedKey === `u-${idx}` ? <MdCheck size={15} /> : <MdContentCopy size={15} />}
                          </button>
                        </div>
                      </div>
                    )
                    ) : (
                      <div className="group w-full min-w-0">
                        {running && idx === turns.length - 1 && (agentActivity || analyzingImage) && (
                          <AgentThinkingDisclosure
                            activity={analyzingImage ? t('agentAnalyzingImage') : agentActivity || t('agentWorking')}
                            isDark={isDark}
                          />
                        )}
                        {turn.steps?.map((step) => (
                        <AgentStepCard key={step.id} step={step} isDark={isDark} cardBg={cardBg} subtle={subtle} onApprove={approve} t={t} />
                      ))}
                      {turn.content && (
                        <div className="mt-1">
                          {running && idx === turns.length - 1
                            ? <p className="whitespace-pre-wrap text-sm leading-relaxed">{turn.content}</p>
                            : <ChatMarkdown text={turn.content} isDark={isDark} />}
                        </div>
                      )}
                      {running && idx === turns.length - 1 && !turn.content && !(agentActivity || analyzingImage) && (
                        <div className={`flex items-center gap-2 text-xs ${subtle}`}>
                          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#006bbd]" />
                          {analyzingImage ? t('agentAnalyzingImage') : agentActivity || t('agentThinking')}
                        </div>
                      )}
                      {turn.content && !(running && idx === turns.length - 1) && (
                        <div className="mt-1 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                          <button
                            onClick={() => copyText(turn.content, `a-${idx}`)}
                            className={`rounded-md p-1 transition-colors ${copiedKey === `a-${idx}` ? 'bg-[#006bbd]/10 text-[#006bbd]' : isDark ? 'text-white/30 hover:bg-white/[0.06] hover:text-white/70' : 'text-gray-400 hover:bg-gray-100 hover:text-gray-600'}`}
                            title={copiedKey === `a-${idx}` ? t('copied') : t('copy')} aria-label={copiedKey === `a-${idx}` ? t('copied') : t('copy')}
                          >
                            {copiedKey === `a-${idx}` ? <MdCheck size={15} /> : <MdContentCopy size={15} />}
                          </button>
                          <button
                            onClick={() => regenerate(idx)}
                            disabled={running}
                            className={`rounded-md p-1 transition-colors disabled:opacity-30 ${isDark ? 'text-white/30 hover:bg-white/[0.06] hover:text-white/70' : 'text-gray-400 hover:bg-gray-100 hover:text-gray-600'}`}
                            title={t('regenerate')} aria-label={t('regenerate')}
                          >
                            <MdRefresh size={15} />
                          </button>
                        </div>
                      )}
                      {turn.completionStatus && turn.completionStatus !== 'complete' && (
                        <p role="status" className={`mt-1 text-[11px] ${turn.completionStatus === 'error' ? 'text-red-600' : 'text-amber-600'}`}>
                          {turn.completionStatus === 'cancelled' ? t('requestCancelled') : turn.completionStatus === 'pending' ? t('completionPending') : t('completionError')}
                        </p>
                      )}
                      {turn.model && (
                        <p className={`mt-1 font-mono text-[10px] ${subtle}`}>{turn.model}</p>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Composer */}
        <div className="shrink-0 px-2 pt-2 sm:px-4" style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 0.75rem)' }}>
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-2">
            {attachedImage && (
              <div className="relative inline-block w-max">
                <img src={attachedImage} alt={t('agentAttachImage')} className="h-20 w-auto rounded-lg border border-white/10 object-cover" width={160} height={80} />
                <button
                  onClick={() => { setAttachedImage(null); setImageError(''); }}
                  className="absolute -right-2 -top-2 rounded-full border border-white/20 bg-black/80 p-0.5 text-white/80 hover:text-white"
                  aria-label={t('agentRemoveImage')}
                >
                  <MdClose size={14} />
                </button>
              </div>
            )}
            {attachedDocs.length > 0 && (
              <div className={`grid max-h-44 grid-cols-1 gap-2 overflow-y-auto rounded-xl border p-2 sm:grid-cols-2 ${isDark ? 'border-white/[0.08] bg-white/[0.03]' : 'border-gray-200 bg-gray-50'}`}>
                {attachedDocs.map((document) => (
                  <div key={document.name} className={`min-w-0 rounded-lg px-2.5 py-2 text-[11px] ${isDark ? 'bg-white/[0.06] text-white/60' : 'bg-white text-gray-600'}`}>
                    <div className="flex min-w-0 items-center gap-1.5"><MdUploadFile size={14} className="shrink-0" /><span className="truncate font-medium">{document.name}</span>{document.truncated && <span className="text-amber-400">{t('truncated')}</span>}<button type="button" onClick={() => setAttachedDocs((current) => current.filter((item) => item.name !== document.name))} className="ml-auto shrink-0 text-current/60 hover:text-current" aria-label={t('removeDocument')}><MdClose size={13} /></button></div>
                    <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-[10px] leading-relaxed opacity-70">{document.content.slice(0, 180)}</p>
                  </div>
                ))}
              </div>
            )}
            {imageError && <p role="alert" className="text-xs text-red-400">{imageError}</p>}

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
                  <button type="button" onClick={() => setAttachmentMenuOpen((open) => !open)} disabled={running} className={`grid h-11 w-11 place-items-center rounded-xl transition-colors disabled:opacity-40 ${isDark ? 'bg-white/[0.06] text-white/55 hover:bg-white/[0.1] hover:text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200 hover:text-gray-700'}`} aria-label={`${t('agentAttachImage')} / ${t('attachDocument')}`} aria-expanded={attachmentMenuOpen}><MdAdd size={20} /></button>
                  <AnimatePresence>
                    {attachmentMenuOpen && <motion.div initial={{ opacity: 0, y: 8, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8, scale: 0.96 }} transition={{ duration: 0.16, ease: [0.16, 1, 0.3, 1] }} className={`absolute bottom-full left-0 z-40 mb-2 min-w-44 overflow-hidden rounded-xl border p-1 shadow-xl ${isDark ? 'border-white/[0.08] bg-[#151515]' : 'border-gray-200 bg-white'}`}>
                      <button type="button" onClick={() => { setAttachmentMenuOpen(false); imageInputRef.current?.click(); }} className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${isDark ? 'text-white/75 hover:bg-white/[0.08]' : 'text-gray-700 hover:bg-gray-100'}`}><MdImage size={18} /> {t('agentAttachImage')}</button>
                      <button type="button" onClick={() => { setAttachmentMenuOpen(false); docInputRef.current?.click(); }} className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${isDark ? 'text-white/75 hover:bg-white/[0.08]' : 'text-gray-700 hover:bg-gray-100'}`}><MdUploadFile size={18} /> {t('attachDocument')}</button>
                    </motion.div>}
                  </AnimatePresence>
                </div>
              )}
              rightActions={(
                <>
                  <AnimatePresence initial={false}>
                    {dictationAvailable && !running && <motion.button type="button" initial={{ opacity: 0, scale: 0.72, width: 0 }} animate={{ opacity: 1, scale: 1, width: 42 }} exit={{ opacity: 0, scale: 0.72, width: 0 }} transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }} onClick={toggleDictation} className={`flex h-[42px] shrink-0 items-center justify-center overflow-hidden rounded-xl transition-colors ${listening ? 'animate-pulse bg-red-500/30 text-red-400' : isDark ? 'bg-white/[0.06] text-white/55 hover:bg-white/[0.1] hover:text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200 hover:text-gray-700'}`} aria-label={listening ? t('agentExitVoiceMode') : t('agentVoiceMode')} title={listening ? t('agentExitVoiceMode') : t('agentVoiceMode')} aria-pressed={listening}><MdMic size={19} /></motion.button>}
                  </AnimatePresence>
                  {running ? <button onClick={stop} className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-xl bg-red-500/90 text-white transition-colors hover:bg-red-500" aria-label={t('agentStop')}><MdStop size={20} /></button> : <button onClick={() => void send()} disabled={!input.trim() && !attachedImage && attachedDocs.length === 0} className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-xl bg-[#006bbd] text-white transition-colors hover:bg-[#0059a0] disabled:cursor-not-allowed disabled:opacity-40" aria-label={t('agentSend')} title={t('agentSend')}><MdSend size={19} /></button>}
                </>
              )}
            />
          </div>
        </div>
      </div>
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

function AgentThinkingDisclosure({
  activity,
  isDark,
}: {
  activity: string;
  isDark: boolean;
}) {
  if (!activity) return null;
  return (
    <div className={`agent-activity mb-2 flex items-center gap-2 text-xs ${isDark ? 'text-white/55' : 'text-gray-500'}`} role="status" aria-live="polite">
      <span className="agent-activity-dot" aria-hidden="true" />
      <AnimatePresence initial={false} mode="wait">
        <motion.span
          key={activity}
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -5 }}
          transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
        >
          {activity}
        </motion.span>
      </AnimatePresence>
    </div>
  );
}

const DANGEROUS_HINT: Record<string, 'toolWrite' | 'toolEdit' | 'toolRun'> = {
  write_file: 'toolWrite',
  edit_file: 'toolEdit',
  run_command: 'toolRun',
};

function argSummary(tool: string, args: Record<string, string>): string {
  if (tool === 'run_command') return args.command ?? '';
  if (tool === 'write_file') return args.path ?? '';
  if (tool === 'edit_file') return args.path ?? '';
  if (tool === 'read_file' || tool === 'list_dir') return args.path ?? '.';
  if (tool === 'glob' || tool === 'grep') return args.pattern ?? '';
  if (tool === 'search_knowledge' || tool === 'web_search') return args.query ?? '';
  return Object.values(args).join(' ');
}

interface AgentYoloButtonProps {
  enabled: boolean;
  disabled: boolean;
  onChange: (enabled: boolean) => void;
  isDark: boolean;
  t: Translate;
  mobile?: boolean;
}

function AgentYoloButton({ enabled, disabled, onChange, isDark, t, mobile = false }: AgentYoloButtonProps) {
  return (
    <div className={mobile ? 'w-full' : ''}>
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        aria-label={enabled ? t('agentYoloModeOn') : t('agentYoloModeOff')}
        title={enabled ? t('agentYoloModeOn') : t('agentYoloModeOff')}
        onClick={() => onChange(!enabled)}
        disabled={disabled}
        className={`${mobile ? 'flex w-full items-center px-2.5 py-2 text-left' : 'px-2 py-1'} rounded-lg text-[10px] font-bold uppercase tracking-wide transition-[background-color,color,transform] active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/70 disabled:opacity-40 ${enabled ? 'bg-red-500/15 text-red-500 hover:bg-red-500/25' : isDark ? 'text-white/40 hover:bg-white/[0.06] hover:text-white/75' : 'text-gray-400 hover:bg-gray-100 hover:text-gray-700'}`}
      >
        {t('agentYoloMode')}
      </button>
    </div>
  );
}

interface StepCardProps {
  step: AgentStep;
  isDark: boolean;
  cardBg: string;
  subtle: string;
  onApprove: (step: AgentStep, approved: boolean) => void | Promise<void>;
  t: Translate;
}

function AgentStepCard({ step, isDark, cardBg, subtle, onApprove, t }: StepCardProps) {
  const statusIcon = {
    running: <span className="h-2 w-2 animate-pulse rounded-full bg-[#006bbd]" />,
    awaiting: <span className="h-2 w-2 rounded-full bg-amber-400" />,
    done: <MdCheck size={14} className="text-green-500" />,
    denied: <MdClose size={14} className="text-red-500" />,
  }[step.status];

  const summary = argSummary(step.tool, step.args);
  const dangerKey = DANGEROUS_HINT[step.tool];

  return (
    <div className={`mb-1.5 animate-fade-up rounded-xl border px-3 py-2 text-xs ${cardBg}`}>
      <div className="flex items-center gap-2">
        {statusIcon}
        <span className={`font-mono font-semibold ${isDark ? 'text-white/80' : 'text-gray-700'}`}>{step.tool}</span>
        {summary && <span className={`min-w-0 flex-1 truncate font-mono ${subtle}`} title={summary}>{summary}</span>}
      </div>

      {/* Preview for dangerous actions awaiting approval */}
      {step.status === 'awaiting' && (
        <div className="mt-2">
          {step.tool === 'write_file' && (
            <pre className={`mb-2 max-h-40 overflow-auto rounded-lg p-2 font-mono text-[11px] ${isDark ? 'bg-black/40 text-white/70' : 'bg-white text-gray-700'}`}>{(step.args.content ?? '').slice(0, 1200)}</pre>
          )}
          {step.tool === 'edit_file' && (
            <pre className={`mb-2 max-h-40 overflow-auto rounded-lg p-2 font-mono text-[11px] ${isDark ? 'bg-black/40' : 'bg-white'}`}>
              <span className="text-red-400">- {(step.args.old ?? '').slice(0, 400)}</span>{'\n'}
              <span className="text-green-400">+ {(step.args.new ?? '').slice(0, 400)}</span>
            </pre>
          )}
          {step.tool === 'run_command' && (
            <pre className={`mb-2 overflow-auto rounded-lg p-2 font-mono text-[11px] ${isDark ? 'bg-black/40 text-white/70' : 'bg-white text-gray-700'}`}>$ {step.args.command}</pre>
          )}
          <div className="flex items-center gap-2">
            <span className={`flex-1 ${subtle}`}>{dangerKey ? t(dangerKey) : t('agentApprovePrompt')}</span>
            <button
              onClick={() => onApprove(step, false)}
              className={`rounded-lg px-3 py-1 font-medium transition-colors ${isDark ? 'bg-white/[0.06] text-white/70 hover:bg-white/10' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >
              {t('agentReject')}
            </button>
            <button
              onClick={() => onApprove(step, true)}
              className="rounded-lg bg-[#006bbd] px-3 py-1 font-medium text-white transition-colors hover:bg-[#0059a0]"
            >
              {t('agentApprove')}
            </button>
          </div>
        </div>
      )}

      {/* Result line for completed / denied steps */}
      {step.result && step.status !== 'awaiting' && (
        <pre className={`mt-1.5 max-h-32 overflow-auto whitespace-pre-wrap break-words font-mono text-[11px] ${subtle}`}>{step.result.slice(0, 800)}</pre>
      )}
    </div>
  );
}
