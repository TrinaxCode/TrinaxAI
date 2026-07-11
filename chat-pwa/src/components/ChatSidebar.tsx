import { motion, AnimatePresence } from 'framer-motion';
import { MdChat, MdDelete, MdClose, MdAdd, MdSettings, MdSearch, MdFolder, MdCreateNewFolder } from 'react-icons/md';
import { FaGithub } from 'react-icons/fa';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { useState, useRef, useCallback } from 'react';
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
    transition: { type: 'spring', stiffness: 300, damping: 30 },
  },
  closed: {
    x: '-100%',
    transition: { type: 'spring', stiffness: 300, damping: 30 },
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
    ? 'bg-black/65 backdrop-blur-xl border-white/[0.06]'
    : 'bg-white/75 backdrop-blur-xl border-gray-200 shadow-xl';
  const headerBorder = isDark ? 'border-white/[0.06]' : 'border-gray-200';
  const textMuted = isDark ? 'text-white/50' : 'text-gray-500';
  const textWhite = isDark ? 'text-white' : 'text-gray-900';
  const hoverBg = isDark ? 'hover:bg-white/[0.06]' : 'hover:bg-gray-100';
  const footerBorder = isDark ? 'border-white/[0.06]' : 'border-gray-200';
  const emptyText = isDark ? 'text-white/30' : 'text-gray-400';
  const activeBg = isDark ? 'bg-[#006bbd]/15 text-white' : 'bg-[#006bbd]/10 text-gray-900';
  const inactiveText = isDark ? 'text-white/50 hover:text-white/80' : 'text-gray-500 hover:text-gray-800';
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
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20, height: 0 }}
      transition={{ type: 'spring', stiffness: 400, damping: 30 }}
      className="group"
    >
      <div
        onClick={() => { onSelect(session.id); }}
        role="button"
        tabIndex={0}
        className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-left text-sm transition-all cursor-pointer ${session.id === activeId ? activeBg : `${inactiveText} ${hoverBg}`}`}
      >
        <MdChat size={16} className="shrink-0 opacity-60" />
        <div className="min-w-0 flex-1">
          <span className="block truncate text-sm">{session.title}</span>
          {session.messages.length > 0 && <span className={`block truncate text-[11px] mt-0.5 ${isDark ? 'text-white/30' : 'text-gray-400'}`}>{session.messages[session.messages.length - 1].content.replace(/\n/g, ' ').slice(0, 60)}</span>}
        </div>
        <div className="relative shrink-0">
          <button
            onClick={(event) => { event.stopPropagation(); setFolderMenuId((current) => current === session.id ? null : session.id); }}
            className={`rounded-md p-1 opacity-0 transition-all group-hover:opacity-100 focus:opacity-100 ${isDark ? 'text-white/35 hover:bg-white/[0.08] hover:text-white' : 'text-gray-400 hover:bg-gray-100 hover:text-gray-700'}`}
            aria-label={t('moveChatToFolder')}
            title={t('moveChatToFolder')}
          >
            <MdFolder size={15} />
          </button>
          <AnimatePresence>
            {folderMenuId === session.id && (
              <motion.div
                initial={{ opacity: 0, y: 5, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 5, scale: 0.96 }}
                className={`absolute right-0 top-full z-50 mt-1 min-w-36 overflow-hidden rounded-xl border p-1 shadow-xl ${isDark ? 'border-white/[0.1] bg-gray-900' : 'border-gray-200 bg-white'}`}
                onClick={(event) => event.stopPropagation()}
              >
                <button onClick={() => { onMoveToFolder(session.id, undefined); setFolderMenuId(null); }} className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs ${isDark ? 'text-white/70 hover:bg-white/[0.08]' : 'text-gray-600 hover:bg-gray-100'}`}>{t('generalFolder')}</button>
                {folders.map((folder) => <button key={folder.id} onClick={() => { onMoveToFolder(session.id, folder.id); setFolderMenuId(null); }} className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs ${isDark ? 'text-white/70 hover:bg-white/[0.08]' : 'text-gray-600 hover:bg-gray-100'}`}><MdFolder size={15} />{folder.name}</button>)}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        <button onClick={(e) => { e.stopPropagation(); setDeleteId(session.id); }} className="p-1 rounded-md dark:text-white/20 text-gray-300 hover:text-red-400 hover:bg-red-400/10 opacity-0 group-hover:opacity-100 transition-all" aria-label={`${t('delete')} ${session.title}`}><MdDelete size={14} /></button>
      </div>
    </motion.div>
  );

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            className="fixed inset-0 z-[55] bg-black/30 backdrop-blur-md"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onToggle}
            onTouchStart={handleOverlayTouchStart}
            onTouchEnd={handleOverlayTouchEnd}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        className={`fixed left-0 top-0 z-[60] h-dvh w-[85vw] max-w-[300px] sm:w-72 ${sidebarBg} border-r flex flex-col`}
        style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
        variants={sidebarVariants}
        initial="closed"
        animate={isOpen ? 'open' : 'closed'}
      >
        {/* Header with logo */}
        <div className={`px-4 pt-[env(safe-area-inset-top,0px)] pb-3 border-b ${headerBorder}`}>
          <div className="flex items-center justify-between mb-2">
            <div className="flex min-w-0 items-center gap-2">
              <img src="/logo-of-app.webp" alt="TrinaxAI" className="h-8 w-8 shrink-0 rounded-lg opacity-90" width={32} height={32} />
              <span className={`truncate text-sm font-medium tracking-wide ${isDark ? 'text-white/70' : 'text-gray-600'}`}>{t('history')}</span>
            </div>
            <div className="flex items-center gap-1">
            {onBrowser && (
              <button
                onClick={onBrowser}
                className={`p-2 rounded-lg ${isDark ? 'text-white/40 hover:text-white/80' : 'text-gray-400 hover:text-gray-700'} ${hoverBg} transition-colors`}
                aria-label={t('knowledgeBrowser')}
              >
                <MdFolder size={18} />
              </button>
            )}
            <button
              onClick={onSettings}
              className={`p-2 rounded-lg ${isDark ? 'text-white/40 hover:text-white/80' : 'text-gray-400 hover:text-gray-700'} ${hoverBg} transition-colors`}
              aria-label={t('settings')}
            >
              <MdSettings size={18} />
            </button>
            <button
              onClick={onToggle}
              className={`p-2 rounded-lg ${isDark ? 'text-white/40 hover:text-white/80' : 'text-gray-400 hover:text-gray-700'} ${hoverBg} transition-colors`}
              aria-label={t('closeMenu')}
            >
              <MdClose size={20} />
            </button>
            </div>
          </div>
        </div>

        <div
          className={`mx-3 mt-3 mb-2 flex items-center gap-2 rounded-xl border px-3 py-2 transition-all duration-300 focus-within:animate-border-glow ${isDark ? 'bg-white/[0.03] border-white/[0.06] focus-within:border-[#006bbd]/40' : 'bg-gray-50 border-gray-200 focus-within:border-[#006bbd]/40'}`}
        >
          <MdSearch size={16} className={isDark ? 'text-white/30' : 'text-gray-400'} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('searchChats')} className={`min-w-0 flex-1 bg-transparent text-sm outline-none ${isDark ? 'text-white/70 placeholder-white/25' : 'text-gray-700 placeholder-gray-400'}`} />
          {query && <button onClick={() => setQuery('')} className="p-0.5" aria-label={t('clearSearch')}><MdClose size={16} /></button>}
        </div>

        {/* Folders: horizontal multi-selection below search */}
        <div className="mx-3 mb-2 flex items-center gap-1.5 overflow-x-auto pb-1 [scrollbar-width:thin]">
          <button onClick={() => { setFolderName(''); setCreateFolderOpen(true); }} className={`flex shrink-0 items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs ${isDark ? 'text-white/50 hover:bg-white/[0.08] hover:text-white' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'}`} aria-label={t('createFolder')} title={t('createFolder')}><MdCreateNewFolder size={18} />{folders.length === 0 && <span>{t('organizeChatsPrompt')}</span>}</button>
          {folders.map((folder) => (
            <div key={folder.id} className={`flex shrink-0 items-center overflow-hidden rounded-lg ${selectedFolderIds.includes(folder.id) ? 'bg-[#006bbd] text-white' : isDark ? 'bg-white/[0.04] text-white/60' : 'bg-gray-100 text-gray-600'}`}>
              <button onClick={() => toggleFolder(folder.id)} className="flex max-w-36 items-center gap-1.5 px-2.5 py-1.5 text-xs" title={folder.name}>
                <MdFolder size={15} /><span className="truncate">{folder.name}</span><span className="opacity-60">{sessions.filter((session) => session.folderId === folder.id).length}</span>
              </button>
              <button onClick={() => setDeleteFolderId(folder.id)} className="p-1.5 opacity-60 hover:opacity-100" aria-label={`${t('delete')} ${folder.name}`} title={t('deleteFolder')}><MdDelete size={13} /></button>
            </div>
          ))}
        </div>

        {/* Session List */}
        <div className="flex-1 overflow-y-auto px-2 py-3 space-y-1">
          {(isSearching ? [{ id: 'general', name: t('generalFolder'), items: looseSessions }, ...folders.map((folder) => ({ id: folder.id, name: folder.name, items: filteredSessions.filter((session) => session.folderId === folder.id) }))] : [...folders.filter((folder) => selectedFolderIds.includes(folder.id)).map((folder) => ({ id: folder.id, name: folder.name, items: filteredSessions.filter((session) => session.folderId === folder.id) })), { id: 'general', name: t('generalFolder'), items: looseSessions }]).map((group) => (
            <div key={group.id} className="mb-3">
              <button onClick={() => toggleCollapsed(group.id)} className={`mb-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider ${textMuted} ${hoverBg}`}>
                {group.id !== 'general' && <MdFolder size={14} />} <span className="min-w-0 flex-1 truncate">{group.name}</span><span>{group.items.length}</span><span className="text-sm">{collapsedFolders.has(group.id) ? '+' : '−'}</span>
              </button>
              <AnimatePresence initial={false}>{!collapsedFolders.has(group.id) && group.items.map(renderSession)}</AnimatePresence>
            </div>
          ))}

          {filteredSessions.length === 0 && (
            <p className={`text-center ${emptyText} text-xs py-8 px-4`}>
              {query.trim() ? t('noChatResults') : t('noChats')}
            </p>
          )}
        </div>

        {/* New Chat Button */}
        <button
          onClick={() => onCreate(engine)}
          className="mx-3 my-2 flex items-center justify-center gap-2 px-3 py-2 rounded-xl
                     border border-[#006bbd]/30 text-[#006bbd] text-sm font-medium
                     hover:bg-[#006bbd]/10 transition-colors"
        >
          <MdAdd size={18} />
          {t('newChat')}
        </button>

        {/* GitHub Footer */}
        <div className={`shrink-0 px-4 py-3 border-t ${footerBorder}`}>
          <motion.a
            href="https://github.com/TrinaxCode"
            target="_blank"
            rel="noopener noreferrer"
            className={`flex w-full items-center justify-center gap-2 px-3 py-2 rounded-xl text-center ${textMuted} hover:text-[#006bbd] ${hoverBg} transition-colors text-sm`}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <FaGithub size={16} />
            <span className="font-medium">TrinaxCode</span>
          </motion.a>
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
        onConfirm={() => { const trimmed = folderName.trim(); if (!trimmed) return; onCreateFolder(trimmed); setCreateFolderOpen(false); setFolderName(''); }}
        onCancel={() => { setCreateFolderOpen(false); setFolderName(''); }}
      >
        <input
          autoFocus
          value={folderName}
          onChange={(event) => setFolderName(event.target.value)}
          onKeyDown={(event) => { if (event.key === 'Enter' && folderName.trim()) { event.preventDefault(); onCreateFolder(folderName.trim()); setCreateFolderOpen(false); setFolderName(''); } }}
          placeholder={t('folderName')}
          className={`w-full rounded-xl border px-3 py-2.5 text-sm outline-none focus:border-[#006bbd] ${isDark ? 'border-white/[0.1] bg-white/[0.05] text-white placeholder-white/30' : 'border-gray-200 bg-gray-50 text-gray-900 placeholder-gray-400'}`}
        />
      </ConfirmModal>
    </>
  );
}
