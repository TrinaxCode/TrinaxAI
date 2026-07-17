import { useState, useEffect, useLayoutEffect, useCallback, useMemo, lazy, Suspense, useRef } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useTheme } from './theme/ThemeContext';
import { useI18n } from './i18n/I18nContext';
import Intro from './components/Intro';
import Background from './components/Background';
import ErrorBoundary from './components/ErrorBoundary';
import ChatSidebar from './components/ChatSidebar';
import { useChatHistory } from './hooks/useChatHistory';
import { onSharedStateUpdated, startSharedStateSync, syncSharedStateOnce } from './lib/sharedState';
import type { ChatEngine, ChatMessage, ChatSession } from './lib/api';
import type { AgentHandoff } from './components/chat/modeRouter';
import { DEVICE_ACCESS_REVOKED_EVENT, deviceSessionHasScope } from './lib/authHeaders';
import { startDeviceRevocationMonitor } from './lib/devicePairing';
import { wipeRevokedDeviceData } from './lib/deviceWipe';
import {
  formatAppRoute,
  parseAppRoute,
  type AppPage,
  type AppRoute,
  type SettingsSection,
} from './lib/appRoute';

const Settings = lazy(() => import('./components/Settings'));
const OnboardingWizard = lazy(() => import('./components/OnboardingWizard'));
const DeviceSetupChoice = lazy(() => import('./components/DeviceSetupChoice'));
const Docs = lazy(() => import('./components/Docs'));
const KnowledgeBrowser = lazy(() => import('./components/KnowledgeBrowser'));
// Markdown, math rendering, voice and attachment support make the chat view
// the heaviest route. Loading it behind the intro keeps first paint responsive.
const ChatInterface = lazy(() => import('./components/ChatInterface'));
const AgentInterface = lazy(() => import('./components/AgentInterface'));
const PermissionNotice = lazy(() => import('./components/PermissionNotice'));

type NavigateTarget = 'settings' | 'indexing' | 'browser' | 'memory' | 'docs' | 'agent';

function hasCompletedOnboarding(): boolean {
  try { return localStorage.getItem('tc-onboarding-complete') === 'true'; } catch { return false; }
}

export default function App() {
  const initialRoute = useMemo(() => parseAppRoute(window.location.hash), []);
  const [showIntro, setShowIntro] = useState(true);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [showDeviceSetup, setShowDeviceSetup] = useState(false);
  const [blockedFeature, setBlockedFeature] = useState<'rag' | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [page, setPage] = useState<AppPage>(initialRoute.page);
  const [settingsSection, setSettingsSection] = useState<SettingsSection>(initialRoute.settingsSection ?? 'general');
  const [routeChatId, setRouteChatId] = useState<string | undefined>(initialRoute.chatId);
  const [pendingAgentRequest, setPendingAgentRequest] = useState<AgentHandoff | null>(null);
  const [sharedReady, setSharedReady] = useState(false);
  const { isDark } = useTheme();
  const { t } = useI18n();
  const resizeTimerRef = useRef<number>(0);
  const prevPageRef = useRef<AppPage>('chat');
  const lastChatIdRef = useRef<string | undefined>(initialRoute.chatId);
  const [chatAnimKey, setChatAnimKey] = useState(0);
  // Mount the heavy chat UI behind the still-opaque splash (see the effect
  // below) so its first-mount cost is paid before the intro fades out.
  const [preMount, setPreMount] = useState(false);

  const applyRoute = useCallback((route: AppRoute) => {
    setPage(route.page);
    if (route.settingsSection) setSettingsSection(route.settingsSection);
    setRouteChatId(route.chatId);
    setSidebarOpen(false);
  }, []);

  const navigate = useCallback((route: AppRoute, replace = false) => {
    const nextHash = formatAppRoute(route);
    if (window.location.hash !== nextHash) {
      const url = `${window.location.pathname}${window.location.search}${nextHash}`;
      if (replace) window.history.replaceState(null, '', url);
      else window.history.pushState(null, '', url);
    }
    applyRoute(route);
  }, [applyRoute]);

  // Swipe gesture — context-aware navigation on mobile
  const touchStartX = useRef(0);
  const touchStartY = useRef(0);

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    const t = e.touches[0];
    touchStartX.current = t.clientX;
    touchStartY.current = t.clientY;
  }, []);

  const handleTouchEnd = useCallback((e: React.TouchEvent) => {
    const t = e.changedTouches[0];
    const dx = t.clientX - touchStartX.current;
    const dy = t.clientY - touchStartY.current;
    // Only react to clearly horizontal swipes
    if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 1.5) return;

    if (dx > 0) {
      // Swipe RIGHT →
      if (page !== 'chat') {
        // In a sub-page → go back to chat with animation
        prevPageRef.current = page;
        setChatAnimKey((k) => k + 1);
        navigate({ page: 'chat', chatId: lastChatIdRef.current });
      } else if (!sidebarOpen) {
        // In chat with sidebar closed → open sidebar
        setSidebarOpen(true);
      }
    } else {
      // Swipe LEFT ←
      if (sidebarOpen) {
        // Sidebar open → close it
        setSidebarOpen(false);
      }
    }
  }, [navigate, page, sidebarOpen]);

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
    return () => {
      window.clearTimeout(resizeTimerRef.current);
      window.removeEventListener('resize', debouncedResize);
    };
  }, []);

  useEffect(() => {
    const syncFromLocation = () => applyRoute(parseAppRoute(window.location.hash));
    window.addEventListener('hashchange', syncFromLocation);
    // pushState navigation is handled synchronously by `navigate`; popstate is
    // required for browser Back/Forward in browsers that omit hashchange.
    window.addEventListener('popstate', syncFromLocation);
    return () => {
      window.removeEventListener('hashchange', syncFromLocation);
      window.removeEventListener('popstate', syncFromLocation);
    };
  }, [applyRoute]);

  useEffect(() => {
    // Local state is immediately usable. Remote/LAN state syncs in the
    // background so an unavailable RAG service never delays PWA startup.
    setSharedReady(true);
    const stopSharedStateSync = startSharedStateSync();
    const stopDeviceRevocationMonitor = startDeviceRevocationMonitor();
    return () => {
      stopSharedStateSync?.();
      stopDeviceRevocationMonitor?.();
    };
  }, []);

  // Handle intro completion → check if onboarding needed
  useEffect(() => {
    if (!showIntro && sharedReady) {
      if (!hasCompletedOnboarding()) {
        setShowDeviceSetup(true);
      }
    }
  }, [showIntro, sharedReady]);

  useEffect(() => onSharedStateUpdated(() => {
    if (hasCompletedOnboarding()) {
      setShowOnboarding(false);
      setShowDeviceSetup(false);
    } else {
      navigate({ page: 'chat', chatId: lastChatIdRef.current }, true);
      setSidebarOpen(false);
      setShowIntro(false);
      setShowOnboarding(true);
    }
  }), [navigate]);

  useEffect(() => {
    const onPaired = () => { void syncSharedStateOnce(3000, true); };
    window.addEventListener('trinaxai-device-paired', onPaired);
    return () => window.removeEventListener('trinaxai-device-paired', onPaired);
  }, []);

  useEffect(() => {
    const onAccessRevoked = async () => {
      await wipeRevokedDeviceData();
      navigate({ page: 'chat' }, true);
      setSidebarOpen(false);
      setShowIntro(false);
      setShowOnboarding(false);
      setShowDeviceSetup(true);
      // Remount from a pristine origin so mounted history/theme hooks cannot
      // write stale in-memory state back after the wipe.
      window.location.replace(`${window.location.pathname}${window.location.search}`);
    };
    window.addEventListener(DEVICE_ACCESS_REVOKED_EVENT, onAccessRevoked);
    return () => window.removeEventListener(DEVICE_ACCESS_REVOKED_EVENT, onAccessRevoked);
  }, [navigate]);

  const handleOnboardingComplete = useCallback(() => {
    setShowOnboarding(false);
    void syncSharedStateOnce(2500, true);
  }, []);

  const handleIntroFinish = useCallback(() => {
    setShowIntro(false);
  }, []);

  // Mount the heavy chat UI behind the opaque splash so its ~0.2s first-mount
  // cost is paid while the intro covers the screen — not on the reveal frame,
  // where it showed as a freeze. We wait for the splash's first paint (a double
  // rAF) so the splash still appears instantly, then mount during the logo's
  // early fade-up-from-opacity-0, the least perceptible moment (the title and
  // loading-line animations are still on their delays and so aren't janked).
  // Gated on sharedReady so we never mount before local state is usable; the
  // onboarding wizard, when shown, covers this naturally.
  useEffect(() => {
    if (!showIntro) { setPreMount(true); return undefined; }
    if (!sharedReady) return undefined;
    let raf2 = 0;
    const raf1 = window.requestAnimationFrame(() => {
      raf2 = window.requestAnimationFrame(() => setPreMount(true));
    });
    return () => { window.cancelAnimationFrame(raf1); window.cancelAnimationFrame(raf2); };
  }, [showIntro, sharedReady]);

  const {
    sessions,
    activeSession,
    activeId,
    createSession,
    deleteSession,
    selectSession,
    updateSession,
    setEngine,
    folders,
    createFolder,
    moveSessionToFolder,
    deleteFolder,
  } = useChatHistory();

  // Pre-warm the chat session WHILE the intro is still animating, so it already
  // exists the moment the splash fades out. We intentionally do NOT gate on
  // `!showIntro` here: doing so forced session-create + the heavy ChatInterface
  // mount to happen in a single synchronous pass right after the animation,
  // which froze the main thread for a beat before everything popped in.
  // Creating it during the ~2.6s intro window means the post-intro render is a
  // single non-blocking pass (and this layout effect is a no-op by then, since
  // a session already exists — so it also can't reintroduce the freeze).
  // The onboarding gate still holds: `showOnboarding` only flips true after the
  // intro, and a blank default session is never persisted, so this is harmless
  // for first-time users.
  useLayoutEffect(() => {
    if (!sharedReady || showOnboarding || showDeviceSetup) return;
    if (routeChatId) {
      const requested = sessions.find((session) => session.id === routeChatId);
      if (requested && activeId !== requested.id) {
        selectSession(requested.id);
        return;
      }
    }
    if (!activeSession) {
      const created = createSession('ollama', t('newChat'));
      lastChatIdRef.current = created.id;
      if (page === 'chat') navigate({ page: 'chat', chatId: created.id }, true);
    }
  }, [
    activeId,
    activeSession,
    createSession,
    navigate,
    page,
    routeChatId,
    selectSession,
    sessions,
    sharedReady,
    showOnboarding,
    showDeviceSetup,
    t,
  ]);

  useEffect(() => {
    if (!activeId) return;
    lastChatIdRef.current = activeId;
    if (page === 'chat' && routeChatId !== activeId) {
      navigate({ page: 'chat', chatId: activeId }, true);
    }
  }, [activeId, navigate, page, routeChatId]);

  const currentEngine: ChatEngine = activeSession?.engine ?? 'ollama';
  const folderContext = useMemo(() => activeSession?.folderId
    ? sessions
      .filter((session) => !session.temporary && session.folderId === activeSession.folderId && session.id !== activeSession.id)
      .slice(0, 12)
      .map((session: ChatSession) => ({ title: session.title, messages: session.messages }))
    : [], [activeSession?.folderId, activeSession?.id, sessions]);

  const handleEngineChange = useCallback((engine: ChatEngine) => {
    if (engine === 'rag' && !deviceSessionHasScope('read_private')) {
      setBlockedFeature('rag');
      return;
    }
    setEngine(engine);
  }, [setEngine]);

  const handleMessagesChange = useCallback((messages: ChatMessage[]) => {
    updateSession(messages);
  }, [updateSession]);

  const handleMenuToggle = useCallback(() => setSidebarOpen((v) => !v), []);

  const handleCreate = useCallback((engine: ChatEngine) => {
    const created = createSession(engine, t('newChat'));
    navigate({ page: 'chat', chatId: created.id });
    setSidebarOpen(false);
  }, [createSession, navigate, t]);

  const handleCreateTemporary = useCallback((engine: ChatEngine) => {
    const created = createSession(engine, t('temporaryChat'), undefined, true);
    navigate({ page: 'chat', chatId: created.id });
    setSidebarOpen(false);
  }, [createSession, navigate, t]);

  const handleNavigate = useCallback((target: NavigateTarget) => {
    setSidebarOpen(false);
    if (target === 'browser') {
      navigate({ page: 'browser' });
      return;
    }
    if (target === 'agent') {
      navigate({ page: 'agent' });
      return;
    }
    if (target === 'docs') {
      navigate({ page: 'docs' });
      return;
    }
    navigate({
      page: 'settings',
      settingsSection: target === 'memory' ? 'memory' : target === 'indexing' ? 'indexing' : 'general',
    });
  }, [navigate]);

  const handleAgentHandoff = useCallback((handoff: AgentHandoff) => {
    setSidebarOpen(false);
    setPendingAgentRequest(handoff);
    navigate({ page: 'agent' });
  }, [navigate]);

  const handleAgentRequestConsumed = useCallback((id: string) => {
    setPendingAgentRequest((current) => current?.id === id ? null : current);
  }, []);

  const handleBackToChat = useCallback(() => {
    prevPageRef.current = page;
    setChatAnimKey((k) => k + 1);
    navigate({ page: 'chat', chatId: lastChatIdRef.current });
  }, [navigate, page]);

  const protectedFeature = page === 'browser' && !deviceSessionHasScope('read_private')
    ? 'knowledge'
    : page === 'agent' && !deviceSessionHasScope('agent')
      ? 'agent'
      : page === 'settings' && settingsSection === 'indexing' && !deviceSessionHasScope('index')
        ? 'index'
      : page === 'settings' && settingsSection === 'memory' && !deviceSessionHasScope('read_private')
        ? 'memory'
        : page === 'settings' && settingsSection === 'stats' && !deviceSessionHasScope('read_private')
          ? 'stats'
          : null;

  return (
    <div data-app-shell className="app-shell w-full max-w-full min-w-0 overflow-hidden relative transition-colors duration-300">
      <a
        href="#tc-main-content"
        className="skip-link"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById('tc-main-content')?.focus();
        }}
      >
        {t('skipToContent')}
      </a>
      {/* Keep the single shared canvas running behind the opaque intro so its
          first visible frame is already in motion when the splash fades out. */}
      <Background
        isDark={isDark}
        variant={page === 'agent' ? 'stars' : 'waves'}
      />

      {/* Intro Splash */}
      <AnimatePresence>
        {showIntro && <Intro onFinish={handleIntroFinish} />}
      </AnimatePresence>

      {/* Onboarding Wizard (first time only) */}
      {showOnboarding && (
        <Suspense fallback={null}>
          <OnboardingWizard
            onComplete={handleOnboardingComplete}
            canConfigureSystem={deviceSessionHasScope('system') && deviceSessionHasScope('index')}
          />
        </Suspense>
      )}
      {showDeviceSetup && !showOnboarding && (
        <Suspense fallback={null}>
          <DeviceSetupChoice onNewDevice={() => { setShowDeviceSetup(false); setShowOnboarding(true); }} />
        </Suspense>
      )}
      {blockedFeature && (
        <div className="fixed inset-0 z-[70]">
          <Suspense fallback={null}>
            <PermissionNotice feature={blockedFeature} onBack={() => { setEngine('ollama'); setBlockedFeature(null); }} />
          </Suspense>
        </div>
      )}

      {/* Main App — gated on `preMount` (not `!showIntro`) so the heavy tree
          mounts behind the opaque splash and its fade-in completes before the
          intro lifts. The intro is z-50 opaque; this is z-10, safely covered. */}
      {preMount && sharedReady && !showOnboarding && !showDeviceSetup && (
        <motion.div
          className="relative z-10 h-full w-full min-h-0 flex"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          {/* Sidebar */}
          <ErrorBoundary>
            <ChatSidebar
              sessions={sessions.filter((session) => !session.temporary)}
              activeId={activeId}
              isOpen={sidebarOpen}
              onToggle={() => setSidebarOpen((v) => !v)}
              onSelect={(id) => {
                selectSession(id);
                navigate({ page: 'chat', chatId: id });
                setSidebarOpen(false);
              }}
              onDelete={deleteSession}
              onCreate={handleCreate}
              onCreateTemporary={handleCreateTemporary}
              onSettings={() => { navigate({ page: 'settings', settingsSection: 'general' }); setSidebarOpen(false); }}
              onBrowser={() => { navigate({ page: 'browser' }); setSidebarOpen(false); }}
              engine={currentEngine}
              folders={folders}
              onCreateFolder={createFolder}
              onMoveToFolder={moveSessionToFolder}
              onDeleteFolder={deleteFolder}
            />
          </ErrorBoundary>

          {/* Main Area */}
          <main
            id="tc-main-content"
            tabIndex={-1}
            // The sidebar is fixed and overlays this area. Keeping the main
            // column unchanged prevents the chat from reflowing on open.
            className="relative min-w-0 min-h-0 h-full flex-1 basis-0 overflow-hidden"
            onTouchStart={handleTouchStart}
            onTouchEnd={handleTouchEnd}
          >
            <ErrorBoundary>
            {activeSession && page === 'chat' ? (
              <motion.div
                key={`chat-${chatAnimKey}`}
                className="h-full"
                initial={prevPageRef.current !== 'chat' ? { x: -40, opacity: 0 } : false}
                animate={{ x: 0, opacity: 1 }}
                transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                onAnimationComplete={() => { prevPageRef.current = 'chat'; }}
              >
                <Suspense fallback={<div className={`h-full flex items-center justify-center text-sm ${isDark ? 'text-white/30' : 'text-gray-400'}`}>{t('loading')}</div>}>
                  <ChatInterface
                    key={activeSession.id}
                    messages={activeSession.messages}
                    engine={currentEngine}
                    temporary={Boolean(activeSession.temporary)}
                    onMessagesChange={handleMessagesChange}
                    onEngineChange={handleEngineChange}
                    onMenuToggle={handleMenuToggle}
                    onNavigate={handleNavigate}
                    onAgentHandoff={handleAgentHandoff}
                    folderContext={folderContext}
                  />
                </Suspense>
              </motion.div>
            ) : page === 'chat' ? (
              <>
                {/* Menu button when no active chat */}
                {!sidebarOpen && (
                  <button
                    onClick={() => setSidebarOpen(true)}
                    className={`fixed right-3 z-20 p-2.5 rounded-xl
                               border transition-colors ${
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
                  width={64}
                  height={64}
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
            ) : null}
            {page !== 'chat' && (
              <AnimatePresence>
                <motion.div
                  key={page}
                  className="absolute inset-0 z-30 min-h-0"
                  initial={{ x: 60, opacity: 0 }}
                  animate={{ x: 0, opacity: 1 }}
                  exit={{ x: 60, opacity: 0 }}
                  transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                >
                {protectedFeature ? (
                  <Suspense fallback={null}>
                    <PermissionNotice feature={protectedFeature} onBack={handleBackToChat} />
                  </Suspense>
                ) : page === 'settings' ? (
                  <Suspense fallback={<div className="h-full flex items-center justify-center text-black/20 dark:text-white/20 text-sm">{t('loading')}</div>}>
                    <Settings
                      key="settings"
                      onBack={handleBackToChat}
                      onOpenDocs={() => navigate({ page: 'docs' })}
                      initialSection={settingsSection}
                      onSectionChange={setSettingsSection}
                      canManageSystem={deviceSessionHasScope('system')}
                    />
                  </Suspense>
                ) : page === 'docs' ? (
                  <Suspense fallback={<div className="h-full flex items-center justify-center text-black/20 dark:text-white/20 text-sm">{t('loading')}</div>}>
                    <Docs key="docs" onBack={handleBackToChat} />
                  </Suspense>
                ) : page === 'browser' ? (
                  <Suspense fallback={<div className="h-full flex items-center justify-center text-black/20 dark:text-white/20 text-sm">{t('loading')}</div>}>
                    <KnowledgeBrowser onBack={handleBackToChat} />
                  </Suspense>
                ) : page === 'agent' ? (
                  <Suspense fallback={<div className="h-full flex items-center justify-center text-black/20 dark:text-white/20 text-sm">{t('loading')}</div>}>
                    <AgentInterface
                      key="agent"
                      onBack={handleBackToChat}
                      initialRequest={pendingAgentRequest}
                      onRequestConsumed={handleAgentRequestConsumed}
                    />
                  </Suspense>
                ) : null}
                </motion.div>
              </AnimatePresence>
            )}
            </ErrorBoundary>
          </main>
        </motion.div>
      )}
    </div>
  );
}
