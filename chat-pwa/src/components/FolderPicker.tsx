import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { MdArrowUpward, MdClose, MdFolder, MdHome, MdLock } from 'react-icons/md';
import { useTheme } from '../theme/ThemeContext';
import { useI18n } from '../i18n/I18nContext';
import { browseDirectories, userFacingError, type DirectoryListing } from '../lib/api';
import { useDialogAccessibility } from '../hooks/useDialogAccessibility';
import ErrorRepairModal from './ErrorRepairModal';

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
  const [repairOpen, setRepairOpen] = useState(false);
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
        setError(userFacingError(err, 'permission_denied'));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [t]);

  useEffect(() => load(initialPath), [load, initialPath]);

  const panel = isDark ? 'bg-[#101a26] border-white/10 text-white' : 'bg-white border-gray-200 text-gray-900';
  const rowHover = isDark ? 'hover:bg-white/[0.06]' : 'hover:bg-gray-100';
  const subtle = isDark ? 'text-white/60' : 'text-gray-600';

  return createPortal(
    <div data-modal-root className="fixed inset-0 z-[60] flex items-center justify-center p-3 sm:p-4">
      <div className={`absolute inset-0 bg-black/50 backdrop-blur-sm ${closing ? 'animate-overlay-out' : 'animate-overlay-in'}`} onClick={handleClose} />
      <div ref={dialogRef} onKeyDown={onKeyDown} role="dialog" aria-modal="true" aria-label={t('agentPickFolder')} className={`relative z-10 flex h-[calc(100dvh-1.5rem)] max-h-[640px] w-full max-w-lg flex-col overscroll-contain overflow-hidden rounded-2xl border shadow-2xl sm:h-[70dvh] ${closing ? 'animate-modal-out' : 'animate-modal-in'} ${panel}`}>
        {/* Header */}
        <div className={`flex shrink-0 items-center gap-2 border-b px-4 py-3 ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
          <MdFolder size={20} className={isDark ? 'text-[#4aa7ed]' : 'text-[#006bbd]'} />
          <span className="text-base font-semibold">{t('agentPickFolder')}</span>
          <button ref={closeButtonRef} onClick={handleClose} className={`ml-auto grid h-11 w-11 place-items-center rounded-lg ${rowHover}`} aria-label={t('close')}>
            <MdClose size={18} />
          </button>
        </div>

        {/* Path bar */}
        <div className={`flex shrink-0 items-center gap-1.5 border-b px-3 py-2 ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
          <button
            onClick={() => load(listing?.home)}
            className={`grid h-11 w-11 shrink-0 place-items-center rounded-lg ${rowHover}`}
            title={t('agentHomeFolder')}
            aria-label={t('agentHomeFolder')}
          >
            <MdHome size={16} />
          </button>
          <button
            onClick={() => listing?.parent && load(listing.parent)}
            disabled={!listing?.parent}
            className={`grid h-11 w-11 shrink-0 place-items-center rounded-lg ${rowHover} disabled:opacity-30`}
            title={t('agentParentFolder')}
            aria-label={t('agentParentFolder')}
          >
            <MdArrowUpward size={16} />
          </button>
          <span className={`min-w-0 flex-1 truncate font-mono text-sm ${subtle}`} title={listing?.path}>
            {listing?.path ?? '...'}
          </span>
        </div>

        {/* Directory list */}
        <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
          {loading ? (
            <div className={`py-8 text-center text-sm ${subtle}`}>{t('loading')}</div>
          ) : error ? (
            <div role="alert" className={`px-3 py-8 text-center text-sm ${isDark ? 'text-red-300' : 'text-red-700'}`}>
              <p>{error}</p>
              <button type="button" onClick={() => setRepairOpen(true)} className="mt-2 min-h-10 text-[#006bbd] underline underline-offset-2">
                {t('fixError')}
              </button>
            </div>
          ) : listing && listing.directories.length === 0 ? (
            <div className={`py-8 text-center text-sm ${subtle}`}>{t('agentNoSubfolders')}</div>
          ) : (
            listing?.directories.map((dir) => (
              <button
                key={dir.path}
                onClick={() => dir.readable && load(dir.path)}
                disabled={!dir.readable}
                className={`flex min-h-11 w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm ${rowHover} disabled:opacity-40`}
              >
                {dir.readable ? <MdFolder size={17} className={`shrink-0 ${isDark ? 'text-[#4aa7ed]' : 'text-[#006bbd]'}`} /> : <MdLock size={15} className={`shrink-0 ${subtle}`} />}
                <span className="min-w-0 truncate">{dir.name}</span>
              </button>
            ))
          )}
        </div>

        {/* Footer — confirm current directory */}
        <div className={`flex shrink-0 flex-col-reverse gap-2 border-t px-4 py-3 sm:flex-row sm:justify-end ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
          <button
            onClick={handleClose}
            className={`min-h-11 w-full rounded-lg px-3 text-sm font-medium sm:w-auto ${isDark ? 'bg-white/[0.06] text-white/70 hover:bg-white/10' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
          >
            {t('cancel')}
          </button>
          <button
            onClick={() => listing && handleSelect(listing.path)}
            disabled={!listing}
            className="min-h-11 w-full rounded-lg bg-[#006bbd] px-4 text-sm font-medium text-white hover:bg-[#0059a0] disabled:opacity-40 sm:w-auto"
          >
            {t('agentUseThisFolder')}
          </button>
        </div>
      </div>
      <ErrorRepairModal
        open={repairOpen}
        dark={isDark}
        title={t('errorRepairTitle')}
        message={t('errorRepairMessage')}
        details={`${error ?? ''}\n\n${t('errorRepairHint')}`}
        confirmLabel={t('retry')}
        cancelLabel={t('cancel')}
        onConfirm={() => {
          setRepairOpen(false);
          load(listing?.path ?? initialPath);
        }}
        onCancel={() => setRepairOpen(false)}
      />
    </div>,
    document.body,
  );
}
