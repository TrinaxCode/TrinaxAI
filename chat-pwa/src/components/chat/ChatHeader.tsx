import { AnimatePresence, motion } from 'framer-motion';
import { MdBuild, MdDescription, MdDownload, MdMenu, MdPublic, MdScience, MdSmartToy, MdVisibilityOff } from 'react-icons/md';
import { useEffect, useRef, useState } from 'react';
import type { ChatEngine } from '../../lib/api';
import { useI18n } from '../../i18n/I18nContext';
import ToggleSwitch from '../ToggleSwitch';

interface ChatHeaderProps {
  engine: ChatEngine;
  temporary?: boolean;
  isDark: boolean;
  messageCount: number;
  researchMode: boolean;
  webSearchMode: boolean;
  exportMenuOpen: boolean;
  onMenuToggle: () => void;
  onEngineChange: (engine: ChatEngine) => void;
  onResearchModeChange: (enabled: boolean) => void;
  onWebSearchModeChange: (enabled: boolean) => void;
  onExportMenuChange: (open: boolean) => void;
  onExportMarkdown: () => void;
  onExportPdf: () => void;
  onExportWord: () => void;
  onOpenAgent?: () => void;
}

export default function ChatHeader({
  engine,
  temporary = false,
  isDark,
  messageCount,
  researchMode,
  webSearchMode,
  exportMenuOpen,
  onMenuToggle,
  onEngineChange,
  onResearchModeChange,
  onWebSearchModeChange,
  onExportMenuChange,
  onExportMarkdown,
  onExportPdf,
  onExportWord,
  onOpenAgent,
}: ChatHeaderProps) {
  const { t } = useI18n();
  const [mobileToolsOpen, setMobileToolsOpen] = useState(false);
  const mobileToolsRef = useRef<HTMLDivElement>(null);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!mobileToolsOpen) return undefined;
    const closeOnOutsideInteraction = (event: PointerEvent) => {
      if (!mobileToolsRef.current?.contains(event.target as Node)) setMobileToolsOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileToolsOpen(false);
    };
    document.addEventListener('pointerdown', closeOnOutsideInteraction);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsideInteraction);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [mobileToolsOpen]);

  useEffect(() => {
    if (!exportMenuOpen) return undefined;
    const closeOnOutsideInteraction = (event: PointerEvent) => {
      if (!exportMenuRef.current?.contains(event.target as Node)) onExportMenuChange(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onExportMenuChange(false);
    };
    document.addEventListener('pointerdown', closeOnOutsideInteraction);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsideInteraction);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [exportMenuOpen, onExportMenuChange]);

  const exportAction = (action: () => void) => {
    action();
    onExportMenuChange(false);
  };

  return (
    <nav
      className={`relative z-50 flex shrink-0 items-center border-b px-2 backdrop-blur-xl sm:px-3 ${isDark ? 'border-white/[0.06] bg-black/80' : 'border-gray-200 bg-white/90'}`}
      style={{ minHeight: '44px', paddingTop: 'env(safe-area-inset-top, 0px)' }}
    >
      <div className="flex shrink-0 items-center gap-1">
        <button
          onClick={onMenuToggle}
          className={`rounded-xl p-2 transition-colors ${isDark ? 'text-white/60 hover:bg-white/[0.06] hover:text-white' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'}`}
          aria-label={t('openMenu')}
        >
          <MdMenu size={20} />
        </button>
        <span className="animate-brand min-w-0 truncate text-lg font-bold tracking-normal sm:text-xl">TrinaxAI</span>
        {temporary && (
          <span
            className={`ml-1 inline-flex shrink-0 items-center rounded-full border p-1.5 text-[10px] font-semibold uppercase tracking-wide sm:gap-1 sm:px-2 sm:py-1 sm:text-[11px] ${isDark ? 'border-amber-300/25 bg-amber-300/10 text-amber-200' : 'border-amber-500/30 bg-amber-50 text-amber-700'}`}
            title={t('temporaryChatDescription')}
            aria-label={t('temporaryChat')}
          >
            <MdVisibilityOff size={13} />
            <span className="hidden sm:inline">{t('temporaryChat')}</span>
          </span>
        )}
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-0.5 sm:gap-2 md:gap-3">
        <div className="hidden items-center gap-1.5 sm:flex">
          <div ref={exportMenuRef} className="relative">
            <button
              onClick={() => onExportMenuChange(!exportMenuOpen)}
              disabled={messageCount === 0}
              className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors sm:h-9 sm:w-9 sm:rounded-xl ${
                messageCount === 0
                  ? isDark ? 'cursor-not-allowed text-white/20' : 'cursor-not-allowed text-gray-300'
                  : isDark ? 'text-white/55 hover:bg-white/[0.06] hover:text-white' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-800'
              }`}
              aria-label={t('exportChat')}
              title={t('exportChat')}
            >
              <MdDownload size={17} />
            </button>
            <AnimatePresence>
              {exportMenuOpen && messageCount > 0 && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => onExportMenuChange(false)} />
                  <motion.div
                    initial={{ opacity: 0, scale: 0.92, y: -4 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.92, y: -4 }}
                    transition={{ duration: 0.15 }}
                    className={`absolute right-0 top-full z-50 mt-1.5 w-48 rounded-xl border py-1 shadow-lg backdrop-blur-xl ${isDark ? 'border-white/[0.08] bg-[#1a1a1a]/95 shadow-black/40' : 'border-gray-200 bg-white/95 shadow-gray-200/80'}`}
                  >
                    {[
                      { label: t('exportAsMd'), Icon: MdDownload, action: onExportMarkdown },
                      { label: t('exportAsPdf'), Icon: MdDescription, action: onExportPdf },
                      { label: t('exportAsWord'), Icon: MdDescription, action: onExportWord },
                    ].map(({ label, Icon, action }) => (
                      <button
                        key={label}
                        onClick={() => exportAction(action)}
                        className={`flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors ${isDark ? 'text-white/70 hover:bg-white/[0.05] hover:text-white' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'}`}
                      >
                        <Icon size={16} /> {label}
                      </button>
                    ))}
                  </motion.div>
                </>
              )}
            </AnimatePresence>
          </div>
          <button
            onClick={() => onResearchModeChange(!researchMode)}
            className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors sm:h-9 sm:w-9 sm:rounded-xl ${researchMode ? 'animate-soft-pulse bg-[#006bbd]/20 text-[#006bbd] ring-1 ring-[#006bbd]/40' : isDark ? 'text-white/55 hover:bg-white/[0.06] hover:text-white' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-800'}`}
            aria-label={t('toggleDeepResearch')}
            title={t('deepResearchTitle')}
          >
            <MdScience size={17} />
          </button>
          <button
            onClick={() => onWebSearchModeChange(!webSearchMode)}
            className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors sm:h-9 sm:w-9 sm:rounded-xl ${webSearchMode ? 'animate-soft-pulse bg-[#006bbd]/20 text-[#006bbd] ring-1 ring-[#006bbd]/40' : isDark ? 'text-white/55 hover:bg-white/[0.06] hover:text-white' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-800'}`}
            aria-label={t('toggleWebSearch')}
            title={t('webSearchTitle')}
          >
            <MdPublic size={18} />
          </button>
          {onOpenAgent && (
            <button
              onClick={onOpenAgent}
              className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors sm:h-9 sm:w-9 sm:rounded-xl ${isDark ? 'text-white/55 hover:bg-white/[0.06] hover:text-white' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-800'}`}
              aria-label={t('openAgent')}
              title={t('agentTitle')}
            >
              <MdSmartToy size={18} />
            </button>
          )}
        </div>
        <div ref={mobileToolsRef} className="relative mr-1.5 sm:hidden">
          <button
            type="button"
            onClick={() => setMobileToolsOpen((open) => !open)}
            className={`grid h-8 w-8 place-items-center rounded-lg transition-colors ${mobileToolsOpen ? 'bg-[#006bbd]/20 text-[#006bbd] ring-1 ring-[#006bbd]/40' : isDark ? 'text-white/65 hover:bg-white/[0.06] hover:text-white' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-800'}`}
            aria-label={t('tools')}
            aria-expanded={mobileToolsOpen}
            title={t('tools')}
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
                  className={`absolute right-0 top-full z-50 mt-1.5 w-60 overflow-hidden rounded-xl border p-1 shadow-lg backdrop-blur-xl ${isDark ? 'border-white/[0.08] bg-[#1a1a1a]/95 shadow-black/40' : 'border-gray-200 bg-white/95 shadow-gray-200/80'}`}
                >
                  <button
                    onClick={() => { onResearchModeChange(!researchMode); setMobileToolsOpen(false); }}
                    className={`flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left text-sm transition-colors ${researchMode ? 'bg-[#006bbd]/15 text-[#4ea3e0]' : isDark ? 'text-white/75 hover:bg-white/[0.06]' : 'text-gray-700 hover:bg-gray-100'}`}
                    aria-label={t('toggleDeepResearch')}
                    aria-pressed={researchMode}
                  >
                    <MdScience size={19} />
                    <span className="flex-1">{t('deepResearchTitle')}</span>
                    <span className="text-xs">{researchMode ? '✓' : ''}</span>
                  </button>
                  <button
                    onClick={() => { onWebSearchModeChange(!webSearchMode); setMobileToolsOpen(false); }}
                    className={`flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left text-sm transition-colors ${webSearchMode ? 'bg-[#006bbd]/15 text-[#4ea3e0]' : isDark ? 'text-white/75 hover:bg-white/[0.06]' : 'text-gray-700 hover:bg-gray-100'}`}
                    aria-label={t('toggleWebSearch')}
                    aria-pressed={webSearchMode}
                  >
                    <MdPublic size={19} />
                    <span className="flex-1">{t('webSearchTitle')}</span>
                    <span className="text-xs">{webSearchMode ? '✓' : ''}</span>
                  </button>
                  {onOpenAgent && (
                    <button
                      onClick={() => { onOpenAgent(); setMobileToolsOpen(false); }}
                      className={`flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left text-sm transition-colors ${isDark ? 'text-white/75 hover:bg-white/[0.06]' : 'text-gray-700 hover:bg-gray-100'}`}
                      aria-label={t('openAgent')}
                    >
                      <MdSmartToy size={19} />
                      <span>{t('agentTitle')}</span>
                    </button>
                  )}
                  {messageCount > 0 && (
                    <div className={`mt-1 border-t pt-1 ${isDark ? 'border-white/[0.08]' : 'border-gray-200'}`}>
                      {[
                        { label: t('exportAsMd'), Icon: MdDownload, action: onExportMarkdown },
                        { label: t('exportAsPdf'), Icon: MdDescription, action: onExportPdf },
                        { label: t('exportAsWord'), Icon: MdDescription, action: onExportWord },
                      ].map(({ label, Icon, action }) => (
                        <button key={label} onClick={() => { exportAction(action); setMobileToolsOpen(false); }} className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm ${isDark ? 'text-white/60 hover:bg-white/[0.06] hover:text-white' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-800'}`}>
                          <Icon size={17} /> {label}
                        </button>
                      ))}
                    </div>
                  )}
                </motion.div>
              </>
            )}
          </AnimatePresence>
        </div>
        <ToggleSwitch engine={engine} onChange={onEngineChange} />
      </div>
    </nav>
  );
}
