import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { MdArrowUpward, MdClose, MdFolder, MdHome, MdLock } from 'react-icons/md';
import { useTheme } from '../theme/ThemeContext';
import { useI18n } from '../i18n/I18nContext';
import { browseDirectories, type DirectoryListing } from '../lib/api';
import { useDialogAccessibility } from '../hooks/useDialogAccessibility';

interface FolderPickerProps {
  initialPath?: string;
  onSelect: (path: string) => void;
  onClose: () => void;
}

/**
 * A server-side directory browser modal. The backend (`/v1/agent/browse`) lists
 * sub-directories of a host path; the user drills in and confirms one as the
 * agent workspace. Directory-only and read-only — never lists or opens files.
 */
export default function FolderPicker({ initialPath, onSelect, onClose }: FolderPickerProps) {
  const { isDark } = useTheme();
  const { t } = useI18n();
  const [listing, setListing] = useState<DirectoryListing | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [closing, setClosing] = useState(false);
  const closeTimerRef = useRef<number | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  // Play the exit animation before unmounting (mirrors the history drawer).
  const requestClose = useCallback((after: () => void) => {
    setClosing(true);
    if (closeTimerRef.current !== null) window.clearTimeout(closeTimerRef.current);
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null;
      after();
    }, 200);
  }, []);

  useEffect(() => () => {
    if (closeTimerRef.current !== null) window.clearTimeout(closeTimerRef.current);
  }, []);

  const handleClose = useCallback(() => requestClose(onClose), [requestClose, onClose]);
  const handleSelect = useCallback((path: string) => requestClose(() => onSelect(path)), [requestClose, onSelect]);
  const { dialogRef, onKeyDown } = useDialogAccessibility(true, handleClose, closeButtonRef);

  const load = useCallback((path?: string) => {
    setLoading(true);
    setError(null);
    const controller = new AbortController();
    browseDirectories(path, controller.signal)
      .then((data) => setListing(data))
      .catch((err) => {
        // Ignore aborts — they fire when the effect re-runs or the modal closes,
        // and must not clobber a successful listing or show a false error.
        if (controller.signal.aborted || (err instanceof DOMException && err.name === 'AbortError')) return;
        setError(err instanceof Error ? err.message.slice(0, 200) : t('agentBrowseError'));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [t]);

  useEffect(() => load(initialPath), [load, initialPath]);

  const panel = isDark ? 'bg-[#111] border-white/10 text-white' : 'bg-white border-gray-200 text-gray-900';
  const rowHover = isDark ? 'hover:bg-white/[0.06]' : 'hover:bg-gray-100';
  const subtle = isDark ? 'text-white/45' : 'text-gray-400';

  return createPortal(
    <div data-modal-root className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className={`absolute inset-0 bg-black/50 backdrop-blur-sm ${closing ? 'animate-overlay-out' : 'animate-overlay-in'}`} onClick={handleClose} />
      <div ref={dialogRef} onKeyDown={onKeyDown} role="dialog" aria-modal="true" aria-label={t('agentPickFolder')} className={`relative z-10 flex h-[70vh] max-h-[560px] w-full max-w-lg flex-col overscroll-contain overflow-hidden rounded-2xl border shadow-2xl ${closing ? 'animate-modal-out' : 'animate-modal-in'} ${panel}`}>
        {/* Header */}
        <div className={`flex shrink-0 items-center gap-2 border-b px-4 py-3 ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
          <MdFolder size={18} className="text-[#006bbd]" />
          <span className="text-sm font-semibold">{t('agentPickFolder')}</span>
          <button ref={closeButtonRef} onClick={handleClose} className={`ml-auto rounded-lg p-1.5 ${rowHover}`} aria-label={t('close')}>
            <MdClose size={18} />
          </button>
        </div>

        {/* Path bar */}
        <div className={`flex shrink-0 items-center gap-1.5 border-b px-3 py-2 ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
          <button
            onClick={() => load(listing?.home)}
            className={`rounded-lg p-1.5 ${rowHover}`}
            title={t('agentHomeFolder')}
            aria-label={t('agentHomeFolder')}
          >
            <MdHome size={16} />
          </button>
          <button
            onClick={() => listing?.parent && load(listing.parent)}
            disabled={!listing?.parent}
            className={`rounded-lg p-1.5 ${rowHover} disabled:opacity-30`}
            title={t('agentParentFolder')}
            aria-label={t('agentParentFolder')}
          >
            <MdArrowUpward size={16} />
          </button>
          <span className={`min-w-0 flex-1 truncate font-mono text-xs ${subtle}`} title={listing?.path}>
            {listing?.path ?? '…'}
          </span>
        </div>

        {/* Directory list */}
        <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
          {loading ? (
            <div className={`py-8 text-center text-sm ${subtle}`}>{t('loading')}</div>
          ) : error ? (
            <div className="px-3 py-8 text-center text-sm text-red-400">{error}</div>
          ) : listing && listing.directories.length === 0 ? (
            <div className={`py-8 text-center text-sm ${subtle}`}>{t('agentNoSubfolders')}</div>
          ) : (
            listing?.directories.map((dir) => (
              <button
                key={dir.path}
                onClick={() => dir.readable && load(dir.path)}
                disabled={!dir.readable}
                className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm ${rowHover} disabled:opacity-40`}
              >
                {dir.readable ? <MdFolder size={17} className="shrink-0 text-[#006bbd]" /> : <MdLock size={15} className={`shrink-0 ${subtle}`} />}
                <span className="min-w-0 truncate">{dir.name}</span>
              </button>
            ))
          )}
        </div>

        {/* Footer — confirm current directory */}
        <div className={`flex shrink-0 items-center justify-end gap-2 border-t px-4 py-3 ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
          <button
            onClick={handleClose}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${isDark ? 'bg-white/[0.06] text-white/70 hover:bg-white/10' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
          >
            {t('cancel')}
          </button>
          <button
            onClick={() => listing && handleSelect(listing.path)}
            disabled={!listing}
            className="rounded-lg bg-[#006bbd] px-4 py-1.5 text-sm font-medium text-white hover:bg-[#0059a0] disabled:opacity-40"
          >
            {t('agentUseThisFolder')}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
