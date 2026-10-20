import { motion, AnimatePresence } from 'framer-motion';
import { MdChat, MdChevronLeft, MdDelete, MdClose, MdAdd, MdSettings, MdSearch, MdFolder, MdCreateNewFolder, MdVisibilityOff, MdExpandMore, MdMoreHoriz } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { useState, useRef, useCallback, useEffect } from 'react';
import ConfirmModal from './ConfirmModal';
import type { ChatSession, ChatEngine, ChatFolder } from '../lib/api';

interface ChatSidebarProps {
  sessions: ChatSession[];
  activeId: string | null;
  isOpen: boolean;
  onToggle: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onCreate: (engine: ChatEngine) => void;
  onCreateTemporary: (engine: ChatEngine) => void;
  engine: ChatEngine;
  onSettings: () => void;
  onBrowser?: () => void;
  folders: ChatFolder[];
  onCreateFolder: (name: string) => void;
  onMoveToFolder: (sessionId: string, folderId?: string) => void;
  onDeleteFolder: (folderId: string) => void;
}

const sidebarVariants = {
  open: {
    x: 0,
    transition: { duration: 0.24, ease: [0.22, 1, 0.36, 1] },
  },
  closed: {
    x: '-100%',
    transition: { duration: 0.2, ease: [0.4, 0, 1, 1] },
  },
};

export default function ChatSidebar({
  sessions,
  activeId,
  isOpen,
  onToggle,
  onSelect,
  onDelete,
  onCreate,
  onCreateTemporary,
  engine,
  onSettings,
  onBrowser,
  folders,
  onCreateFolder,
  onMoveToFolder,
  onDeleteFolder,
}: ChatSidebarProps) {
  const { t } = useI18n();
  const { isDark } = useTheme();
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [createFolderOpen, setCreateFolderOpen] = useState(false);
  const [folderName, setFolderName] = useState('');
  const [selectedFolderIds, setSelectedFolderIds] = useState<string[]>([]);
  const [collapsedFolders, setCollapsedFolders] = useState<Set<string>>(new Set());
  const [folderMenuId, setFolderMenuId] = useState<string | null>(null);
  const [deleteFolderId, setDeleteFolderId] = useState<string | null>(null);
  const touchStartX = useRef(0);
  const touchStartY = useRef(0);
  const folderMenuRef = useRef<HTMLDivElement>(null);
  const folderMenuPanelRef = useRef<HTMLDivElement>(null);
  const folderMenuTriggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!folderMenuId) return;
    folderMenuPanelRef.current?.scrollIntoView?.({ block: 'nearest' });
    const onPointerDown = (event: PointerEvent) => {
      if (!folderMenuRef.current?.contains(event.target as Node)) setFolderMenuId(null);
    };
    const onEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      setFolderMenuId(null);
      folderMenuTriggerRef.current?.focus();
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onEscape);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onEscape);
    };
  }, [folderMenuId]);

  const handleOverlayTouchStart = useCallback((e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
    touchStartY.current = e.touches[0].clientY;
  }, []);

  const handleOverlayTouchEnd = useCallback((e: React.TouchEvent) => {
    const dx = e.changedTouches[0].clientX - touchStartX.current;
    const dy = e.changedTouches[0].clientY - touchStartY.current;
    // Swipe LEFT on overlay → close sidebar
    if (dx < -50 && Math.abs(dx) > Math.abs(dy) * 1.2) {
      onToggle();
    }
  }, [onToggle]);
  const filteredSessions = sessions.filter((session) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return session.title.toLowerCase().includes(q)
      || session.messages.some((msg) => msg.content.toLowerCase().includes(q));
  });

  const sidebarBg = isDark
    ? 'bg-black/65 border-white/[0.06]'
    : 'bg-white border-gray-200';
  const headerBorder = isDark ? 'border-white/[0.06]' : 'border-gray-200';
  const textMuted = isDark ? 'text-white/65' : 'text-gray-600';
  const hoverBg = isDark ? 'hover:bg-white/[0.06]' : 'hover:bg-gray-100';
  const emptyText = isDark ? 'text-white/60' : 'text-gray-600';
  const activeBg = isDark ? 'bg-[#006bbd]/15 text-white' : 'bg-[#006bbd]/10 text-gray-900';
  const inactiveText = isDark ? 'text-white/70 hover:text-white' : 'text-gray-600 hover:text-gray-800';
  const looseSessions = filteredSessions.filter((session) => !session.folderId || !folders.some((folder) => folder.id === session.folderId));
  const isSearching = query.trim().length > 0;
  const toggleFolder = (folderId: string) => setSelectedFolderIds((current) => current.includes(folderId) ? current.filter((id) => id !== folderId) : [...current, folderId]);
  const toggleCollapsed = (id: string) => setCollapsedFolders((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const renderSession = (session: ChatSession) => (
    <motion.div
      key={session.id}
      initial={false}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20, height: 0 }}
      transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
      className="group relative"
      style={{ zIndex: folderMenuId === session.id ? 20 : undefined }}
    >
      <div
        data-session-row
        data-active={session.id === activeId ? 'true' : undefined}
        data-options-open={folderMenuId === session.id ? 'true' : undefined}
        className={`sidebar-session-row relative w-full rounded-xl text-left text-sm transition-colors ${session.id === activeId ? activeBg : `${inactiveText} ${hoverBg}`}`}
      >
        {session.id === activeId && <span aria-hidden="true" className="sidebar-active-indicator" />}
        <button
          type="button"
          onClick={() => onSelect(session.id)}
          aria-label={session.title}
          aria-current={session.id === activeId ? 'page' : undefined}
          className={`sidebar-session-select block w-full min-w-0 py-2.5 pl-3.5 text-left text-sm ${session.id === activeId ? 'pl-4' : ''}`}
        >
          <span className="sidebar-session-copy flex min-w-0 items-center gap-2.5">
          <MdChat size={16} className="shrink-0 opacity-60" />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm">{session.title}</span>
            {session.messages.length > 0 && <span className={`mt-0.5 block truncate text-xs ${isDark ? 'text-white/60' : 'text-gray-600'}`}>{session.messages[session.messages.length - 1].content.replace(/\n/g, ' ').slice(0, 60)}</span>}
          </span>
          </span>
        </button>
        <div ref={folderMenuId === session.id ? folderMenuRef : undefined} className="absolute right-1 top-1/2 -translate-y-1/2">
          <button
            onClick={(event) => { event.stopPropagation(); folderMenuTriggerRef.current = event.currentTarget; setFolderMenuId((current) => current === session.id ? null : session.id); }}
            className={`sidebar-session-options grid h-11 w-11 place-items-center rounded-lg transition-[background-color,color,opacity,transform] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${isDark ? 'text-white/65 hover:bg-white/[0.08] hover:text-white' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-800'}`}
            aria-label={`${t('chatOptions')}: ${session.title}`}
            aria-expanded={folderMenuId === session.id}
            title={t('chatOptions')}
          >
            <MdMoreHoriz size={20} />
          </button>
          <AnimatePresence>
            {folderMenuId === session.id && (
              <motion.div
                ref={folderMenuPanelRef}
                initial={{ opacity: 0, y: 5, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 5, scale: 0.96 }}
                className={`absolute right-0 top-full z-50 mt-1 max-h-64 w-52 overflow-x-hidden overflow-y-auto rounded-xl border p-1 shadow-xl ${isDark ? 'border-white/[0.1] bg-gray-900' : 'border-gray-200 bg-white'}`}
                onClick={(event) => event.stopPropagation()}
              >
                <div className={`px-2.5 py-2 text-xs font-semibold ${isDark ? 'text-white/65' : 'text-gray-600'}`}>{t('moveChatToFolder')}</div>
                <button onClick={() => { onMoveToFolder(session.id, undefined); setFolderMenuId(null); }} className={`flex min-h-11 w-full items-center gap-2 rounded-lg px-2.5 text-left text-sm ${isDark ? 'text-white/80 hover:bg-white/[0.08]' : 'text-gray-700 hover:bg-gray-100'}`}>{t('generalFolder')}</button>
                {folders.map((folder) => <button key={folder.id} onClick={() => { onMoveToFolder(session.id, folder.id); setFolderMenuId(null); }} className={`flex min-h-11 w-full items-center gap-2 rounded-lg px-2.5 text-left text-sm ${isDark ? 'text-white/80 hover:bg-white/[0.08]' : 'text-gray-700 hover:bg-gray-100'}`}><MdFolder size={15} /><span className="min-w-0 truncate">{folder.name}</span></button>)}
                <button onClick={() => { setFolderMenuId(null); setDeleteId(session.id); }} className={`mt-1 flex min-h-11 w-full items-center gap-2 border-t px-2.5 text-left text-sm ${isDark ? 'border-white/10 text-red-300 hover:bg-red-500/10' : 'border-gray-200 text-red-700 hover:bg-red-50'}`}><MdDelete size={16} />{t('deleteChat')}</button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            className="sidebar-backdrop fixed inset-0 z-[55] bg-black/50 lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{ willChange: 'opacity' }}
            onClick={onToggle}
            onTouchStart={handleOverlayTouchStart}
            onTouchEnd={handleOverlayTouchEnd}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        aria-label={t('history')}
        aria-hidden={!isOpen}
        inert={!isOpen}
        className={`sidebar-surface fixed left-0 top-0 z-[60] h-dvh w-[calc(100vw-1.5rem)] max-w-[280px] sm:w-[280px] ${sidebarBg} border-r shadow-none flex flex-col`}
        style={{
          paddingBottom: 'env(safe-area-inset-bottom, 0px)',
          contain: 'layout paint',
          willChange: 'transform',
        }}
        variants={sidebarVariants}
        initial="closed"
        animate={isOpen ? 'open' : 'closed'}
      >
        {/* Header with logo */}
        <div className={`px-1 pt-[env(safe-area-inset-top,0px)] pb-1 border-b ${headerBorder}`}>
          <div className="sidebar-history-header flex items-center">
            <div className="sidebar-history-logo ml-0 flex shrink-0 items-center justify-center rounded-full p-1">
              <img
                src="/logo-for-ai-transparent.webp"
                alt="TrinaxAI"
                className="h-full w-full rounded-full object-contain"
                width={40}
                height={40}
                draggable={false}
              />
            </div>
            <span className={`ml-1 text-sm font-semibold ${isDark ? 'text-white/80' : 'text-gray-700'}`}>
              {t('history')}
            </span>
            <div className="ml-auto flex shrink-0 items-center gap-0">
            {onBrowser && (
              <button
                onClick={onBrowser}
                className={`grid min-h-11 min-w-11 place-items-center rounded-lg p-2 ${isDark ? 'text-white/65 hover:text-white' : 'text-gray-600 hover:text-gray-900'} ${hoverBg} transition-colors`}
                aria-label={t('knowledgeBrowser')}
              >
                <MdFolder size={18} />
              </button>
            )}
            <button
              onClick={onSettings}
              className={`grid min-h-11 min-w-11 place-items-center rounded-lg p-2 ${isDark ? 'text-white/65 hover:text-white' : 'text-gray-600 hover:text-gray-900'} ${hoverBg} transition-colors`}
              aria-label={t('settings')}
            >
              <MdSettings size={18} />
            </button>
            {/* The header toggle sits behind the drawer on phones, so the
                drawer carries its own close arrow below the desktop breakpoint. */}
            <button
              type="button"
              onClick={onToggle}
              data-sidebar-close
              className={`grid min-h-11 min-w-11 place-items-center rounded-lg p-2 lg:hidden ${isDark ? 'text-white/65 hover:text-white' : 'text-gray-600 hover:text-gray-900'} ${hoverBg} transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed]`}
              aria-label={t('closeMenu')}
            >
              <MdChevronLeft size={24} />
            </button>
            </div>
          </div>
        </div>

        <div
          className={`mx-3 mt-3 mb-2 flex min-h-11 items-center gap-2 rounded-xl border px-3 py-2 transition-[background-color,border-color,box-shadow] duration-300 focus-within:animate-border-glow ${isDark ? 'bg-white/[0.03] border-white/[0.06] focus-within:border-[#006bbd]/40' : 'bg-gray-50/70 border-gray-200 focus-within:border-[#006bbd]/40'}`}
        >
          <MdSearch size={16} className={isDark ? 'text-white/60' : 'text-gray-600'} />
          <input data-group-focus value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('searchChats')} aria-label={t('searchChats')} className={`min-w-0 flex-1 bg-transparent text-base outline-hidden sm:text-sm ${isDark ? 'text-white/90 placeholder-white/50' : 'text-slate-900 placeholder-slate-500'}`} />
          {query && <button onClick={() => setQuery('')} className={`grid h-11 w-11 shrink-0 place-items-center rounded-lg ${isDark ? 'text-white/65 hover:bg-white/[0.06]' : 'text-gray-600 hover:bg-gray-100'}`} aria-label={t('clearSearch')}><MdClose size={16} /></button>}
        </div>

        {/* Folders: horizontal multi-selection below search */}
        <div className="mx-3 mb-1 flex items-center gap-1.5 overflow-x-auto py-1 [scrollbar-width:thin]">
          <button onClick={() => { setFolderName(''); setCreateFolderOpen(true); }} className={`flex min-h-11 shrink-0 items-center gap-2 rounded-lg px-2.5 text-sm ${isDark ? 'text-white/75 hover:bg-white/[0.08] hover:text-white' : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'}`} aria-label={t('createFolder')} title={t('createFolder')}><MdCreateNewFolder size={18} />{folders.length === 0 && <span>{t('createFolder')}</span>}</button>
          {folders.map((folder) => (
            <div key={folder.id} className={`flex shrink-0 items-center overflow-hidden rounded-lg ${selectedFolderIds.includes(folder.id) ? 'bg-[#006bbd] text-white' : isDark ? 'bg-white/[0.04] text-white/60' : 'bg-gray-100 text-gray-600'}`}>
              <button onClick={() => toggleFolder(folder.id)} className="flex min-h-11 max-w-36 items-center gap-1.5 px-2.5 text-sm" title={folder.name} aria-pressed={selectedFolderIds.includes(folder.id)}>
                <MdFolder size={15} /><span className="truncate">{folder.name}</span><span className="opacity-60">{sessions.filter((session) => session.folderId === folder.id).length}</span>
              </button>
              <button onClick={() => setDeleteFolderId(folder.id)} className="grid h-11 w-11 place-items-center opacity-70 hover:opacity-100" aria-label={`${t('delete')} ${folder.name}`} title={t('deleteFolder')}><MdDelete size={15} /></button>
            </div>
          ))}
        </div>

        {/* Session List */}
        <div className="relative min-h-0 flex-1">
          <div className="h-full overflow-y-auto px-2 py-3 space-y-1 [mask-image:linear-gradient(to_bottom,transparent,#000_1.25rem,#000_calc(100%-1.5rem),transparent)]">
            {(isSearching ? [{ id: 'general', name: t('generalFolder'), items: looseSessions }, ...folders.map((folder) => ({ id: folder.id, name: folder.name, items: filteredSessions.filter((session) => session.folderId === folder.id) }))] : [...folders.filter((folder) => selectedFolderIds.includes(folder.id)).map((folder) => ({ id: folder.id, name: folder.name, items: filteredSessions.filter((session) => session.folderId === folder.id) })), { id: 'general', name: t('generalFolder'), items: looseSessions }]).filter((group) => !isSearching || group.items.length > 0).map((group) => {
            const isCollapsed = collapsedFolders.has(group.id);
            return (
            <motion.div key={group.id} layout="position" transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }} className="relative mb-3" style={{ zIndex: group.items.some((session) => session.id === folderMenuId) ? 20 : undefined }}>
              <button onClick={() => toggleCollapsed(group.id)} aria-expanded={!isCollapsed} className={`mb-1 flex min-h-11 w-full items-center gap-2 rounded-lg px-3 text-left text-xs font-semibold uppercase tracking-wider ${textMuted} ${hoverBg}`}>
                {group.id !== 'general' && <MdFolder size={14} />} <span className="min-w-0 flex-1 truncate">{group.name}</span><span>{group.items.length}</span>
                <motion.span animate={{ rotate: isCollapsed ? -90 : 0 }} transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }} className="flex text-base" aria-hidden="true"><MdExpandMore /></motion.span>
              </button>
              {!isCollapsed && (
                <div className="space-y-1 pb-1">
                  <AnimatePresence initial={false}>{group.items.map(renderSession)}</AnimatePresence>
                </div>
              )}
            </motion.div>
            );
            })}

            <AnimatePresence initial={false}>
              {filteredSessions.length === 0 && (
                <motion.p
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 6 }}
                  transition={{ duration: 0.18, ease: 'easeOut' }}
                  className={`px-4 py-12 text-center text-sm ${emptyText}`}
                >
                  {query.trim() ? t('noChatResults') : t('noChats')}
                </motion.p>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* New and temporary chats */}
        <div className="mx-3 my-2 flex items-center gap-2">
          <button
            onClick={() => onCreate(engine)}
            className={`flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl border border-[#006bbd]/30 px-3 py-2 text-sm font-medium transition-colors hover:bg-[#006bbd]/10 ${isDark ? 'text-[#4aa7ed]' : 'text-[#006bbd]'}`}
          >
            <MdAdd size={18} />
            {t('newChat')}
          </button>
          <button
            onClick={() => onCreateTemporary(engine)}
             className={`flex h-11 min-h-11 min-w-11 shrink-0 items-center justify-center rounded-xl border p-2 transition-colors ${isDark ? 'border-white/[0.12] text-white/60 hover:bg-white/[0.08] hover:text-white' : 'border-gray-200 text-gray-500 hover:bg-gray-100 hover:text-gray-800'}`}
            aria-label={t('temporaryChat')}
            title={t('temporaryChat')}
          >
            <MdVisibilityOff size={18} />
          </button>
        </div>

      </motion.aside>

      <ConfirmModal
        open={deleteId !== null}
        title={t('deleteChat')}
        message={t('deleteChatConfirm')}
        confirmLabel={t('delete')}
        danger
        onConfirm={() => { if (deleteId) { onDelete(deleteId); setDeleteId(null); } }}
        onCancel={() => setDeleteId(null)}
      />
      <ConfirmModal
        open={deleteFolderId !== null}
        title={t('deleteFolder')}
        message={t('deleteFolderConfirm')}
        confirmLabel={t('delete')}
        danger
        onConfirm={() => { if (deleteFolderId) { onDeleteFolder(deleteFolderId); setSelectedFolderIds((current) => current.filter((id) => id !== deleteFolderId)); setDeleteFolderId(null); } }}
        onCancel={() => setDeleteFolderId(null)}
      />
      <ConfirmModal
        open={createFolderOpen}
        title={t('createFolder')}
        message={t('folderNameHint')}
        confirmLabel={t('createFolder')}
        confirmDisabled={!folderName.trim()}
        onConfirm={() => { const trimmed = folderName.trim(); if (!trimmed) return; onCreateFolder(trimmed); setCreateFolderOpen(false); setFolderName(''); }}
        onCancel={() => { setCreateFolderOpen(false); setFolderName(''); }}
      >
        <input
          autoFocus
          value={folderName}
          onChange={(event) => setFolderName(event.target.value)}
          onKeyDown={(event) => { if (event.key === 'Enter' && folderName.trim()) { event.preventDefault(); onCreateFolder(folderName.trim()); setCreateFolderOpen(false); setFolderName(''); } }}
          placeholder={t('folderName')}
          aria-label={t('folderName')}
          className={`w-full rounded-xl border px-3 py-2.5 text-base outline-hidden focus:border-[#006bbd] sm:text-sm ${isDark ? 'border-white/[0.1] bg-white/[0.05] text-white placeholder-white/50' : 'border-gray-200 bg-gray-50 text-gray-900 placeholder-gray-600'}`}
        />
      </ConfirmModal>
    </>
  );
}
