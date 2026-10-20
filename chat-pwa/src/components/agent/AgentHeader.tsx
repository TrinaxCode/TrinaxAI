import type { Dispatch, RefObject, SetStateAction } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { MdAdd, MdBuild, MdCheck, MdHistory, MdPublic, MdScience, MdStorage } from 'react-icons/md';
import type { Translate } from '../chat/types';
import BackButton from '../BackButton';
import AgentModelPicker, { AgentModelOptions } from './AgentModelPicker';
import AgentYoloSwitch from './AgentYoloSwitch';
import type { AgentModelMode } from './agentTypes';

export interface AgentHeaderProps {
  onBack: () => void;
  isDark: boolean;
  t: Translate;
  running: boolean;
  openHistory: () => void;
  startNewSession: () => void;
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
  modelNames: Partial<Record<AgentModelMode, string>>;
  activeModelName: string;
  mobileToolsOpen: boolean;
  mobileToolsRef: RefObject<HTMLDivElement | null>;
  setMobileToolsOpen: Dispatch<SetStateAction<boolean>>;
}

export default function AgentHeader({
  onBack,
  isDark,
  t,
  running,
  openHistory,
  startNewSession,
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
  activeModelName,
  mobileToolsOpen,
  mobileToolsRef,
  setMobileToolsOpen,
}: AgentHeaderProps) {
  const prefersReducedMotion = useReducedMotion();
  const idle = isDark ? 'text-white/70 hover:bg-white/[0.08] hover:text-white' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900';
  const iconButton = `flex min-h-11 min-w-11 items-center justify-center rounded-xl transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] disabled:opacity-40`;
  const activeTone = isDark ? 'text-[#168de2]' : 'text-[#006bbd]';
  const divider = <span aria-hidden="true" className={`mx-1 hidden h-6 w-px lg:block ${isDark ? 'bg-white/10' : 'bg-gray-200'}`} />;

  const tools = [
    { key: 'rag', active: knowledgeSearch, toggle: () => setKnowledgeSearch((value) => !value), Icon: MdStorage, label: knowledgeSearch ? t('agentRagOn') : t('agentRagOff'), title: t('agentRag'), text: t('agentRag') },
    { key: 'web', active: webSearch, toggle: () => setWebSearch((value) => !value), Icon: MdPublic, label: webSearch ? t('agentWebSearchOn') : t('agentWebSearchOff'), title: t('agentWebSearch'), text: t('agentWebSearch') },
    { key: 'deep', active: deepResearch, toggle: () => setDeepResearch((value) => !value), Icon: MdScience, label: t('agentDeepResearch'), title: t('agentDeepResearch'), text: t('agentDeepResearch') },
  ];

  return (
    <nav
      className={`page-header chat-header relative z-50 flex shrink-0 items-center gap-1 border-b bg-transparent px-2 sm:px-3 ${isDark ? 'border-white/[0.06]' : 'border-gray-200'}`}
      style={{ minHeight: '60px', paddingTop: 'env(safe-area-inset-top, 0px)' }}
      data-yolo={yoloMode ? 'on' : 'off'}
    >
      <BackButton onClick={onBack} label={t('back')} isDark={isDark} />
      <button
        type="button"
        onClick={openHistory}
        className={`${iconButton} ${idle}`}
        aria-label={t('agentHistory')}
        title={t('agentHistory')}
      >
        <MdHistory size={20} />
      </button>
      <h1 aria-label={t('agentTitle')} className="animate-brand min-w-0 truncate text-lg font-bold tracking-normal sm:text-xl">
        <span className="md:hidden">{t('agentButton')}</span>
        <span className="hidden md:inline">{t('agentTitle')}</span>
      </h1>

      <div className="ml-auto flex shrink-0 items-center gap-0.5 sm:gap-1">
        <motion.div
          data-header-tools
          initial={prefersReducedMotion ? false : { opacity: 0, x: 10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: prefersReducedMotion ? 0 : 0.24, delay: prefersReducedMotion ? 0 : 0.04, ease: [0.22, 1, 0.36, 1] }}
          className="hidden items-center gap-0.5 lg:flex"
        >
          {tools.map(({ key, active, toggle, Icon, label, title }) => (
            <button
              key={key}
              type="button"
              onClick={toggle}
              disabled={running}
              className={`${iconButton} ${active ? activeTone : idle}`}
              aria-label={label}
              title={title}
              aria-pressed={active}
            >
              <Icon size={18} />
            </button>
          ))}
        </motion.div>
        {divider}
        <div className="hidden items-center gap-1.5 lg:flex">
          <AgentModelPicker
            modelMode={modelMode}
            modelNames={modelNames}
            activeModelName={activeModelName}
            onSelect={setModelMode}
            isDark={isDark}
            t={t}
            disabled={running}
          />
          <AgentYoloSwitch enabled={yoloMode} disabled={running} onChange={handleYoloChange} isDark={isDark} t={t} />
        </div>

        <div ref={mobileToolsRef} className="relative lg:hidden">
          <button
            type="button"
            onClick={() => setMobileToolsOpen((open) => !open)}
            className={`${iconButton} ${mobileToolsOpen ? '' : idle} ${yoloMode ? isDark ? 'text-red-300' : 'text-red-700' : ''}`}
            aria-label={t('agentTools')}
            aria-expanded={mobileToolsOpen}
            title={t('agentTools')}
          >
            <MdBuild size={18} />
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
                  className={`fixed z-50 w-[min(19rem,calc(100vw-1rem))] overflow-y-auto overflow-x-hidden rounded-xl border p-1 shadow-lg backdrop-blur-xl ${isDark ? 'border-white/[0.08] bg-[#101a26]/95 shadow-black/40' : 'border-gray-200 bg-white/95 shadow-gray-200/80'}`}
                  style={{ top: 'calc(env(safe-area-inset-top, 0px) + 56px)', right: 'max(0.5rem, env(safe-area-inset-right, 0px))', maxHeight: 'calc(100dvh - env(safe-area-inset-top, 0px) - 4.5rem)' }}
                >
                  {tools.map(({ key, active, toggle, Icon, label, text }) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => { toggle(); setMobileToolsOpen(false); }}
                      disabled={running}
                      className={`flex min-h-11 w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] disabled:opacity-40 ${active ? isDark ? 'text-white/90' : 'text-gray-900' : isDark ? 'text-white/75 hover:bg-white/[0.06]' : 'text-gray-700 hover:bg-gray-100'}`}
                      aria-label={label}
                      aria-pressed={active}
                    >
                      <Icon size={17} />
                      <span className="min-w-0 flex-1 truncate">{text}</span>
                      {active && <MdCheck size={14} aria-hidden="true" />}
                    </button>
                  ))}
                  <div className={`my-1 border-t ${isDark ? 'border-white/[0.08]' : 'border-gray-200'}`} />
                  <AgentYoloSwitch enabled={yoloMode} disabled={running} onChange={(enabled) => { handleYoloChange(enabled); setMobileToolsOpen(false); }} isDark={isDark} t={t} mobile />
                  <div className={`my-1 border-t ${isDark ? 'border-white/[0.08]' : 'border-gray-200'}`} />
                  <p className={`px-2.5 pb-1 pt-1.5 text-xs font-semibold uppercase tracking-wider ${isDark ? 'text-white/60' : 'text-gray-600'}`}>{t('agentModel')}</p>
                  <AgentModelOptions
                    modelMode={modelMode}
                    modelNames={modelNames}
                    onSelect={(mode) => { setModelMode(mode); setMobileToolsOpen(false); }}
                    isDark={isDark}
                    t={t}
                    disabled={running}
                    label={t('agentModel')}
                  />
                </motion.div>
              </>
            )}
          </AnimatePresence>
        </div>

        <button
          type="button"
          onClick={startNewSession}
          className={`${iconButton} ${idle}`}
          aria-label={t('agentNewSession')}
          title={t('agentNewSession')}
        >
          <MdAdd size={22} />
        </button>
      </div>
      {yoloMode && (
        <>
          <span aria-hidden="true" className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-red-500/70 to-transparent" />
          <span role="status" className="sr-only">{t('agentYoloActiveBanner')}</span>
        </>
      )}
    </nav>
  );
}
