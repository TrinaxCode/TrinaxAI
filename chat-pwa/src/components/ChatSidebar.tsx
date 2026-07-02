import { motion, AnimatePresence } from 'framer-motion';
import { MdChat, MdDelete, MdClose, MdAdd, MdSettings, MdBook, MdSearch } from 'react-icons/md';
import { FaGithub } from 'react-icons/fa';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { useState } from 'react';
import ConfirmModal from './ConfirmModal';
import type { ChatSession, ChatEngine } from '../lib/api';

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
  onDocs: () => void;
  onBrowser?: () => void;
}

const sidebarVariants = {
  open: {
    x: 0,
    transition: { type: 'spring', stiffness: 300, damping: 30 },
  },
  closed: {
    x: '100%',
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
  onDocs,
  onBrowser,
}: ChatSidebarProps) {
  const { t } = useI18n();
  const { isDark } = useTheme();
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const filteredSessions = sessions.filter((session) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return session.title.toLowerCase().includes(q)
      || session.messages.some((msg) => msg.content.toLowerCase().includes(q));
  });

  const sidebarBg = isDark
    ? 'bg-black/95 border-white/[0.06]'
    : 'bg-white border-gray-200 shadow-xl';
  const headerBorder = isDark ? 'border-white/[0.06]' : 'border-gray-200';
  const textMuted = isDark ? 'text-white/50' : 'text-gray-500';
  const textWhite = isDark ? 'text-white' : 'text-gray-900';
  const hoverBg = isDark ? 'hover:bg-white/[0.06]' : 'hover:bg-gray-100';
  const footerBorder = isDark ? 'border-white/[0.06]' : 'border-gray-200';
  const emptyText = isDark ? 'text-white/30' : 'text-gray-400';
  const activeBg = isDark ? 'bg-[#006bbd]/15 text-white' : 'bg-[#006bbd]/10 text-gray-900';
  const inactiveText = isDark ? 'text-white/50 hover:text-white/80' : 'text-gray-500 hover:text-gray-800';

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            className="fixed inset-0 z-30 bg-black/30 backdrop-blur-md"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onToggle}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        className={`fixed right-0 top-0 z-40 h-dvh w-[85vw] max-w-[300px] sm:w-72 ${sidebarBg} border-l flex flex-col`}
        style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
        variants={sidebarVariants}
        initial="closed"
        animate={isOpen ? 'open' : 'closed'}
      >
        {/* Header with logo */}
        <div className={`px-4 pt-[env(safe-area-inset-top,0px)] pb-3 border-b ${headerBorder}`}>
          <div className="flex items-center justify-between mb-2">
            <span className={`text-sm font-medium tracking-wide ${isDark ? 'text-white/70' : 'text-gray-600'}`}>
              {t('history')}
            </span>
            <div className="flex items-center gap-1">
            <button
              onClick={onDocs}
              className={`p-2 rounded-lg ${isDark ? 'text-white/40 hover:text-white/80' : 'text-gray-400 hover:text-gray-700'} ${hoverBg} transition-colors`}
              aria-label={t('viewDocs')}
            >
              <MdBook size={18} />
            </button>
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
          {/* App logo */}
          <div className="flex justify-center">
            <img
              src="/logo-of-app.webp"
              alt="TrinaxAI"
              className="w-16 h-16 md:w-20 md:h-20 rounded-xl opacity-90"
              width={56}
              height={56}
            />
          </div>
        </div>

        <div
          className={`mx-3 mt-3 mb-2 flex items-center gap-2 rounded-xl border px-3 py-2 transition-all duration-300 focus-within:animate-border-glow ${
            isDark
              ? 'bg-white/[0.03] border-white/[0.06] focus-within:border-[#006bbd]/40 focus-within:shadow-[0_0_20px_rgba(0,107,189,0.15)]'
              : 'bg-gray-50 border-gray-200 focus-within:border-[#006bbd]/40 focus-within:shadow-[0_0_20px_rgba(0,107,189,0.1)]'
          }`}
        >
          <MdSearch size={16} className={isDark ? 'text-white/30' : 'text-gray-400'} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('searchChats')}
            className={`min-w-0 flex-1 bg-transparent text-sm outline-none ${isDark ? 'text-white/70 placeholder-white/25' : 'text-gray-700 placeholder-gray-400'}`}
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className={`p-0.5 rounded-md ${isDark ? 'text-white/30 hover:text-white hover:bg-white/[0.06]' : 'text-gray-400 hover:text-gray-700 hover:bg-gray-100'}`}
              aria-label={t('clearSearch')}
              title={t('clearSearch')}
            >
              <MdClose size={16} />
            </button>
          )}
        </div>

        {/* Session List */}
        <div className="flex-1 overflow-y-auto px-2 py-3 space-y-1">
          <AnimatePresence initial={false}>
            {filteredSessions.map((session) => (
              <motion.div
                key={session.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20, height: 0 }}
                transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                className="group"
              >
                <div
                  onClick={() => {
                    onSelect(session.id);
                    if (window.innerWidth < 768) onToggle();
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelect(session.id);
                      if (window.innerWidth < 768) onToggle();
                    } else if (e.key === 'ArrowDown') {
                      e.preventDefault();
                      (e.currentTarget.nextElementSibling?.querySelector('[role="button"]') as HTMLElement)?.focus();
                    } else if (e.key === 'ArrowUp') {
                      e.preventDefault();
                      (e.currentTarget.previousElementSibling?.querySelector('[role="button"]') as HTMLElement)?.focus();
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-left
                              text-sm transition-all cursor-pointer ${
                                session.id === activeId
                                  ? activeBg
                                  : `${inactiveText} ${hoverBg}`
                              }`}
                >
                  <MdChat
                    size={16}
                    className="shrink-0 opacity-60"
                  />
                  <span className="truncate flex-1">{session.title}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteId(session.id);
                    }}
                    className="p-1 rounded-md dark:text-white/20 text-gray-300 hover:text-red-400
                               hover:bg-red-400/10 opacity-0 group-hover:opacity-100 transition-all"
                    aria-label={`${t('delete')} ${session.title}`}
                  >
                    <MdDelete size={14} />
                  </button>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

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
    </>
  );
}
