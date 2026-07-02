import { useState, useEffect, useCallback, lazy, Suspense, useRef } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useTheme } from './theme/ThemeContext';
import { useI18n } from './i18n/I18nContext';
import Intro from './components/Intro';
import Background from './components/Background';
import ErrorBoundary from './components/ErrorBoundary';
import ChatSidebar from './components/ChatSidebar';
import ChatInterface from './components/ChatInterface';
import { useChatHistory } from './hooks/useChatHistory';
import { onSharedStateUpdated, startSharedStateSync, syncSharedStateOnce } from './lib/sharedState';
import type { ChatEngine, ChatMessage } from './lib/api';

const Settings = lazy(() => import('./components/Settings'));
const OnboardingWizard = lazy(() => import('./components/OnboardingWizard'));
const Docs = lazy(() => import('./components/Docs'));
const KnowledgeBrowser = lazy(() => import('./components/KnowledgeBrowser'));

type Page = 'chat' | 'settings' | 'docs' | 'browser';
type NavigateTarget = 'settings' | 'indexing' | 'browser' | 'memory' | 'docs';
type SettingsSection = 'general' | 'indexing' | 'prompts' | 'memory' | 'stats';

function hasCompletedOnboarding(): boolean {
  try { return localStorage.getItem('tc-onboarding-complete') === 'true'; } catch { return false; }
}

export default function App() {
  const [showIntro, setShowIntro] = useState(true);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [page, setPage] = useState<Page>('chat');
  const [settingsSection, setSettingsSection] = useState<SettingsSection>('general');
  const [sharedReady, setSharedReady] = useState(false);
  const { isDark } = useTheme();
  const { t } = useI18n();
  const resizeTimerRef = useRef<number>(0);

  useEffect(() => {
    try { sessionStorage.removeItem('trinaxai-resetting'); } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    const setFullHeight = () => {
      root.style.setProperty('--app-height', `${window.innerHeight}px`);
    };
    setFullHeight();
    // Debounce resize events to avoid excessive style recalculations
    // on mobile devices (e.g., keyboard open/close, orientation change).
    const debouncedResize = () => {
      window.clearTimeout(resizeTimerRef.current);
      resizeTimerRef.current = window.setTimeout(setFullHeight, 150);
    };
    window.addEventListener('resize', debouncedResize);
    // Handle hash navigation (#docs)
    const hash = window.location.hash.replace('#', '');
    if (hash === 'docs') setPage('docs');
    const onHashChange = () => {
      const h = window.location.hash.replace('#', '');
      if (h === 'docs') setPage('docs');
      else if (h === 'settings') setPage('settings');
      else setPage('chat');
    };
    window.addEventListener('hashchange', onHashChange);
    return () => {
      window.clearTimeout(resizeTimerRef.current);
      window.removeEventListener('resize', debouncedResize);
      window.removeEventListener('hashchange', onHashChange);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    syncSharedStateOnce().finally(() => {
      if (!cancelled) {
        setShowIntro(true);
        setSharedReady(true);
        startSharedStateSync();
      }
    });
    return () => { cancelled = true; };
  }, []);

  // Handle intro completion → check if onboarding needed
  useEffect(() => {
    if (!showIntro && sharedReady) {
      if (!hasCompletedOnboarding()) {
        setShowOnboarding(true);
      }
    }
  }, [showIntro, sharedReady]);

  useEffect(() => onSharedStateUpdated(() => {
    if (hasCompletedOnboarding()) {
      setShowOnboarding(false);
    } else {
      setPage('chat');
      setSidebarOpen(false);
      setShowIntro(false);
      setShowOnboarding(true);
    }
  }), []);

  const handleOnboardingComplete = useCallback(() => {
    setShowOnboarding(false);
    void syncSharedStateOnce(2500, true);
  }, []);

  const handleIntroFinish = useCallback(() => {
    setShowIntro(false);
  }, []);

  const {
    sessions,
    activeSession,
    activeId,
    createSession,
    deleteSession,
    selectSession,
    updateSession,
    setEngine,
  } = useChatHistory();

  // Create a chat only when there is no active session AND onboarding is done.
  useEffect(() => {
    if (!showIntro && sharedReady && !showOnboarding && !activeSession) {
      createSession('ollama', t('newChat'));
    }
  }, [showIntro, sharedReady, showOnboarding, activeSession, createSession, t]);

  const currentEngine: ChatEngine = activeSession?.engine ?? 'ollama';

  const handleEngineChange = (engine: ChatEngine) => {
    setEngine(engine);
  };

  const handleMessagesChange = (messages: ChatMessage[]) => {
    updateSession(messages);
  };

  const handleCreate = useCallback((engine: ChatEngine) => {
    createSession(engine, t('newChat'));
  }, [createSession, t]);

  const handleNavigate = useCallback((target: NavigateTarget) => {
    setSidebarOpen(false);
    if (target === 'browser') {
      setPage('browser');
      return;
    }
    if (target === 'docs') {
      setPage('docs');
      return;
    }
    setSettingsSection(target === 'memory' ? 'memory' : target === 'indexing' ? 'indexing' : 'general');
    setPage('settings');
  }, []);

  return (
    <div className="app-shell w-full max-w-full min-w-0 overflow-hidden relative transition-colors duration-300">
      {/* Ocean Waves Background (always visible, behind everything) */}
      <Background isDark={isDark} />

      {/* Intro Splash */}
      <AnimatePresence>
        {showIntro && <Intro onFinish={handleIntroFinish} />}
      </AnimatePresence>

      {/* Onboarding Wizard (first time only) */}
      {showOnboarding && (
        <Suspense fallback={null}>
          <OnboardingWizard onComplete={handleOnboardingComplete} />
        </Suspense>
      )}

      {/* Main App */}
      {!showIntro && sharedReady && !showOnboarding && (
        <motion.div
          className="relative z-10 h-full w-full min-h-0 flex"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          {/* Sidebar */}
          <ErrorBoundary>
            <ChatSidebar
              sessions={sessions}
              activeId={activeId}
              isOpen={sidebarOpen}
              onToggle={() => setSidebarOpen((v) => !v)}
              onSelect={selectSession}
              onDelete={deleteSession}
              onCreate={handleCreate}
              onSettings={() => { setPage('settings'); setSidebarOpen(false); }}
              onDocs={() => { setPage('docs'); setSidebarOpen(false); }}
              onBrowser={() => { setPage('browser'); setSidebarOpen(false); }}
              engine={currentEngine}
            />
          </ErrorBoundary>

          {/* Main Area */}
          <main
            className={`flex-1 h-full min-h-0 transition-all duration-300 ${
              sidebarOpen ? 'md:mr-72' : ''
            }`}
          >
            <ErrorBoundary>
            {page === 'settings' ? (
              <Suspense fallback={<div className="h-full flex items-center justify-center text-black/20 dark:text-white/20 text-sm">{t('loading')}</div>}>
                <Settings key="settings" onBack={() => setPage('chat')} initialSection={settingsSection} />
              </Suspense>
            ) : page === 'docs' ? (
              <Suspense fallback={<div className="h-full flex items-center justify-center text-black/20 dark:text-white/20 text-sm">{t('loading')}</div>}>
                <Docs key="docs" onBack={() => setPage('chat')} />
              </Suspense>
            ) : page === 'browser' ? (
              <Suspense fallback={<div className="h-full flex items-center justify-center text-black/20 dark:text-white/20 text-sm">{t('loading')}</div>}>
                <KnowledgeBrowser onBack={() => setPage('chat')} />
              </Suspense>
            ) : activeSession ? (
              <ChatInterface
                key={activeSession.id}
                messages={activeSession.messages}
                engine={currentEngine}
                onMessagesChange={handleMessagesChange}
                onEngineChange={handleEngineChange}
                onMenuToggle={() => setSidebarOpen((v) => !v)}
                sidebarOpen={sidebarOpen}
                onNavigate={handleNavigate}
              />
            ) : (
              <>
                {/* Menu button when no active chat */}
                {!sidebarOpen && (
                  <button
                    onClick={() => setSidebarOpen(true)}
                    className={`fixed right-3 z-20 p-2.5 rounded-xl
                               border transition-all ${
                                 isDark
                                   ? 'bg-black/60 border-white/[0.08] text-white/60 hover:text-white hover:border-white/[0.15]'
                                   : 'bg-white/80 border-gray-200 text-gray-500 hover:text-gray-800 hover:border-gray-300'
                               }`}
                    style={{ top: 'calc(env(safe-area-inset-top, 0px) + 0.75rem)' }}
                    aria-label={t('openMenu')}
                  >
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                      <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                  </button>
                )}
                <div className={`flex flex-col items-center justify-center h-full gap-6 px-6 ${
                  isDark ? 'text-white/30' : 'text-gray-400'
                }`}>
                <img
                  src="/logo-of-app.webp"
                  alt="TrinaxAI"
                  className="w-16 h-16 opacity-30"
                />
                <p className="text-sm tracking-wide text-center">
                  {t('selectOrCreateChat')}
                </p>
                <button
                  onClick={() => handleCreate('ollama')}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl
                             border border-[#006bbd]/40 text-[#006bbd] text-sm font-medium
                             hover:bg-[#006bbd]/10 transition-colors"
                >
                  + {t('newChat')}
                </button>
              </div>
            </>
            )}
            </ErrorBoundary>
          </main>
        </motion.div>
      )}
    </div>
  );
}
