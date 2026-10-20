import type { Dispatch, RefObject, SetStateAction } from 'react';
import { MdAdd, MdClose, MdDelete, MdHistory, MdSearch } from 'react-icons/md';
import type { AgentSession } from '../../hooks/useAgentHistory';
import type { Translate } from '../chat/types';

export interface AgentHistoryDrawerProps {
  isDark: boolean;
  t: Translate;
  closing: boolean;
  dialogRef: RefObject<HTMLDivElement | null>;
  dialogId: string;
  titleId: string;
  closeButtonRef: RefObject<HTMLButtonElement | null>;
  search: string;
  setSearch: Dispatch<SetStateAction<string>>;
  sessions: AgentSession[];
  activeId: string | null;
  close: () => void;
  openSession: (id: string) => void;
  newSession: () => void;
  requestDelete: (session: AgentSession) => void;
}

/** The agent's history drawer wears the same surface as the chat sidebar. */
export default function AgentHistoryDrawer({
  isDark,
  t,
  closing,
  dialogRef,
  dialogId,
  titleId,
  closeButtonRef,
  search,
  setSearch,
  sessions,
  activeId,
  close,
  openSession,
  newSession,
  requestDelete,
}: AgentHistoryDrawerProps) {
  const subtle = isDark ? 'text-white/60' : 'text-gray-600';
  const hoverBg = isDark ? 'hover:bg-white/[0.06]' : 'hover:bg-gray-100';
  const locale = typeof document !== 'undefined' ? document.documentElement.lang || 'en' : 'en';

  return (
    <>
      <div aria-hidden="true" className={`absolute inset-0 z-[55] bg-black/50 ${closing ? 'animate-overlay-out' : 'animate-overlay-in'}`} onClick={close} />
      <div
        ref={dialogRef}
        id={dialogId}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        data-agent-history
        className={`sidebar-surface absolute left-0 top-0 z-[60] flex h-full w-[calc(100%-1.5rem)] max-w-[280px] flex-col border-r sm:w-[280px] ${closing ? 'animate-drawer-out' : 'animate-drawer-in'} ${isDark ? 'border-white/[0.06] bg-black/65' : 'border-gray-200 bg-white'}`}
        style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
      >
        <div className={`border-b px-1 pb-1 ${isDark ? 'border-white/[0.06]' : 'border-gray-200'}`} style={{ paddingTop: 'env(safe-area-inset-top, 0px)' }}>
          <div className="flex items-center">
            <div className="sidebar-history-logo ml-0 flex shrink-0 items-center justify-center rounded-full p-1">
              <img src="/logo-for-ai-transparent.webp" alt="" className="h-full w-full rounded-full object-contain" width={40} height={40} draggable={false} />
            </div>
            <h2 id={titleId} className={`ml-1 min-w-0 flex-1 truncate text-sm font-semibold ${isDark ? 'text-white/80' : 'text-gray-700'}`}>{t('agentHistory')}</h2>
            <button ref={closeButtonRef} type="button" onClick={close} className={`grid min-h-11 min-w-11 place-items-center rounded-lg p-2 transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${isDark ? 'text-white/65 hover:text-white' : 'text-gray-600 hover:text-gray-900'} ${hoverBg}`} aria-label={t('close')}>
              <MdClose size={18} />
            </button>
          </div>
        </div>

        <div className={`mx-3 mt-3 mb-2 flex min-h-11 items-center gap-2 rounded-xl border px-3 py-2 transition-[background-color,border-color] duration-300 ${isDark ? 'border-white/[0.06] bg-white/[0.03] focus-within:border-[#006bbd]/40' : 'border-gray-200 bg-gray-50/70 focus-within:border-[#006bbd]/40'}`}>
          <MdSearch size={16} className={subtle} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t('agentSearchHistory')}
            aria-label={t('agentSearchHistory')}
            className={`min-w-0 flex-1 bg-transparent text-base outline-hidden sm:text-sm ${isDark ? 'text-white/90 placeholder-white/50' : 'text-slate-900 placeholder-slate-500'}`}
          />
        </div>

        <div className="relative min-h-0 flex-1">
          <div className="h-full space-y-1 overflow-y-auto px-2 py-3 [mask-image:linear-gradient(to_bottom,transparent,#000_1.25rem,#000_calc(100%-1.5rem),transparent)]">
            {sessions.length === 0 ? (
              <div className={`flex h-full flex-col items-center justify-center gap-3 px-3 text-center text-sm ${subtle}`}>
                <span aria-hidden="true" className={`grid h-12 w-12 place-items-center rounded-2xl ${isDark ? 'bg-[#168de2]/10 text-[#4aa7ed]' : 'bg-sky-50 text-[#006bbd]'}`}><MdHistory size={24} /></span>
                <p>{t(search.trim() ? 'noChatResults' : 'agentNoHistory')}</p>
              </div>
            ) : (
              sessions.map((session) => {
                const active = session.id === activeId;
                return (
                  <div
                    key={session.id}
                    data-agent-session
                    data-session-row
                    data-active={active ? 'true' : undefined}
                    className={`sidebar-session-row group relative flex items-center rounded-xl text-sm transition-colors ${active ? isDark ? 'bg-[#006bbd]/15 text-white' : 'bg-[#006bbd]/10 text-gray-900' : `${isDark ? 'text-white/70 hover:text-white' : 'text-gray-600 hover:text-gray-800'} ${hoverBg}`}`}
                  >
                    {active && <span aria-hidden="true" className="sidebar-active-indicator" />}
                    <button
                      type="button"
                      onClick={() => openSession(session.id)}
                      aria-current={active ? 'page' : undefined}
                      className={`min-h-11 min-w-0 flex-1 rounded-xl py-2.5 pr-1 text-left focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${active ? 'pl-4' : 'pl-3.5'}`}
                    >
                      <span className="block truncate">{session.title || t('agentUntitled')}</span>
                      <span className={`mt-0.5 block truncate text-xs ${subtle}`}>
                        {session.turns.length} · {new Date(session.updatedAt).toLocaleDateString(locale === 'es' ? 'es-ES' : 'en-US', { day: 'numeric', month: 'short' })}
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => requestDelete(session)}
                      className={`hover-reveal mr-1 grid h-11 w-11 shrink-0 place-items-center rounded-lg transition-[opacity,background-color,color] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${isDark ? 'text-white/65 hover:bg-red-500/10 hover:text-red-300' : 'text-gray-600 hover:bg-red-50 hover:text-red-700'}`}
                      aria-label={`${t('delete')} ${session.title || t('agentUntitled')}`}
                    >
                      <MdDelete size={17} />
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>

        <div className="mx-3 my-2">
          <button
            type="button"
            onClick={newSession}
            className={`flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-[#006bbd]/30 px-3 py-2 text-sm font-medium transition-colors hover:bg-[#006bbd]/10 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${isDark ? 'text-[#4aa7ed]' : 'text-[#006bbd]'}`}
          >
            <MdAdd size={18} />
            {t('agentNewSession')}
          </button>
        </div>
      </div>
    </>
  );
}
