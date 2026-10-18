import { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { MdDelete, MdFolder, MdRefresh, MdSync, MdVisibility, MdVisibilityOff } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { useToast } from './Toast';
import ConfirmModal from './ConfirmModal';
import {
  deleteIndexedImport,
  getWatchStatus,
  startFolderIndex,
  startWatch,
  stopWatch,
  type WatchJobStatus,
  userFacingError,
} from '../lib/api';

interface Props {
  collections: Array<{ id: string; name: string }>;
}

type DirectoryHandleLike = {
  name: string;
  entries(): AsyncIterableIterator<[string, DirectoryHandleLike | FileSystemFileHandle]>;
};

type WatchedFolder = {
  id: string;
  name: string;
  collectionId: string;
  files?: File[];
  handle?: DirectoryHandleLike;
  fingerprint: string;
  importPath?: string;
};

type PickerWindow = Window & { showDirectoryPicker?: () => Promise<DirectoryHandleLike> };

function folderFilesFromInput(files: FileList): File[] {
  return Array.from(files);
}

async function filesFromHandle(handle: DirectoryHandleLike, prefix = ''): Promise<File[]> {
  const files: File[] = [];
  for await (const [name, entry] of handle.entries()) {
    const path = prefix ? `${prefix}/${name}` : name;
    if ('getFile' in entry) {
      const source = await entry.getFile();
      // The upload API uses the file name as its relative destination.
      files.push(new File([source], path, { type: source.type, lastModified: source.lastModified }));
    } else {
      files.push(...await filesFromHandle(entry, path));
    }
  }
  return files;
}

function fingerprint(files: File[]): string {
  return files.map((file) => `${file.name}:${file.size}:${file.lastModified}`).sort().join('|');
}

export default function WatcherCard({ collections }: Props) {
  const { t } = useI18n();
  const { isDark } = useTheme();
  const toast = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const foldersRef = useRef<WatchedFolder[]>([]);
  const statusVersionRef = useRef(0);
  const [folders, setFolders] = useState<WatchedFolder[]>([]);
  const [collectionId, setCollectionId] = useState(() => collections[0]?.id || 'default');
  const [running, setRunning] = useState(false);
  const [serverWatching, setServerWatching] = useState(false);
  const [hostPath, setHostPath] = useState('');
  const [events, setEvents] = useState(0);
  const [busy, setBusy] = useState(false);
  const [serverJob, setServerJob] = useState<WatchJobStatus | null>(null);
  const [pendingRemoveFolder, setPendingRemoveFolder] = useState<WatchedFolder | null>(null);

  const updateFolders = useCallback((next: WatchedFolder[]) => {
    foldersRef.current = next;
    setFolders(next);
  }, []);

  const syncFolder = useCallback(async (folder: WatchedFolder, files: File[]) => {
    const result = await startFolderIndex(files, { collectionId: folder.collectionId, watchId: folder.id });
    const next = foldersRef.current.map((item) => item.id === folder.id
      ? { ...item, files, fingerprint: fingerprint(files), importPath: result.path || item.importPath }
      : item);
    updateFolders(next);
    setEvents((count) => count + 1);
  }, [updateFolders]);

  const addFiles = useCallback(async (name: string, files: File[], handle?: DirectoryHandleLike) => {
    if (!files.length) {
      toast.toast(t('indexNoIndexableFiles'), 'warning');
      return;
    }
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const folder = { id, name, collectionId, files, handle, fingerprint: fingerprint(files) };
    updateFolders([...foldersRef.current, folder]);
    setBusy(true);
    try {
      await syncFolder(folder, files);
      toast.toast(t('watcherFoldersActive').replace('{count}', String(foldersRef.current.length)), 'success');
    } catch (error) {
      updateFolders(foldersRef.current.filter((item) => item.id !== id));
      toast.toast(userFacingError(error, 'external_service_unavailable'), 'error');
    } finally {
      setBusy(false);
    }
  }, [collectionId, syncFolder, t, toast, updateFolders]);

  const chooseFolder = useCallback(async () => {
    const picker = (window as PickerWindow).showDirectoryPicker;
    if (!picker) {
      fileInputRef.current?.click();
      return;
    }
    try {
      const handle = await picker();
      const files = await filesFromHandle(handle);
      await addFiles(handle.name, files, handle);
    } catch (error) {
      // Canceling the native picker is not an error worth surfacing.
      if (error instanceof DOMException && error.name === 'AbortError') return;
      toast.toast(userFacingError(error, 'external_service_unavailable'), 'error');
    }
  }, [addFiles, t, toast]);

  const onInputChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files;
    if (!selected?.length) return;
    const files = folderFilesFromInput(selected);
    const firstPath = (files[0] as File & { webkitRelativePath?: string }).webkitRelativePath;
    const name = firstPath?.split('/')[0] || t('indexSelectedFolderFallback');
    void addFiles(name, files);
    event.target.value = '';
  }, [addFiles, t]);

  const removeFolder = useCallback(async (folder: WatchedFolder) => {
    updateFolders(foldersRef.current.filter((item) => item.id !== folder.id));
    if (!folder.importPath) return;
    try {
      await deleteIndexedImport(folder.importPath, folder.collectionId);
    } catch (error) {
      toast.toast(userFacingError(error, 'external_service_unavailable'), 'error');
    }
  }, [toast, updateFolders]);

  const toggleWatcher = useCallback(async () => {
    if (running) {
      if (serverWatching) {
        setBusy(true);
        try {
          await stopWatch();
        } catch (error) {
          toast.toast(userFacingError(error, 'external_service_unavailable'), 'error');
          return;
        } finally {
          setBusy(false);
        }
      }
      statusVersionRef.current += 1;
      setServerWatching(false);
      setServerJob(null);
      setRunning(false);
      return;
    }
    statusVersionRef.current += 1;
    const normalizedPath = hostPath.trim();
    if (normalizedPath) {
      setBusy(true);
      try {
        await startWatch({ paths: [normalizedPath], collection: collectionId });
        setServerWatching(true);
        setRunning(true);
      } catch (error) {
        toast.toast(userFacingError(error, 'external_service_unavailable'), 'error');
      } finally {
        setBusy(false);
      }
      return;
    }
    if (!foldersRef.current.some((folder) => folder.handle)) {
      toast.toast(t('watcherPickerUnsupported'), 'warning');
      return;
    }
    setRunning(true);
  }, [collectionId, hostPath, running, serverWatching, t, toast]);

  useEffect(() => {
    if (!serverWatching && statusVersionRef.current > 0) return;
    const controller = new AbortController();
    const statusVersion = statusVersionRef.current;
    let active = true;
    const refreshStatus = async () => {
      try {
        const status = await getWatchStatus(controller.signal);
        if (!active || statusVersion !== statusVersionRef.current) return;
        setServerJob(status.job || null);
        if (status.running) {
          setEvents(status.events_seen);
          setServerWatching(true);
          setRunning(true);
        } else if (serverWatching) {
          setServerWatching(false);
          setRunning(false);
        }
      } catch {
        // The regular API health indicator owns connectivity errors.
      }
    };
    void refreshStatus();
    const timer = serverWatching ? window.setInterval(() => void refreshStatus(), 2500) : undefined;
    return () => {
      active = false;
      controller.abort();
      if (timer !== undefined) window.clearInterval(timer);
    };
  }, [serverWatching]);

  useEffect(() => {
    if (!running) return;
    let syncInFlight = false;
    const timer = window.setInterval(() => {
      if (document.hidden || syncInFlight) return;
      syncInFlight = true;
      void (async () => {
        try {
          for (const folder of foldersRef.current) {
            if (!folder.handle) continue;
            try {
              const files = await filesFromHandle(folder.handle);
              if (fingerprint(files) !== folder.fingerprint) await syncFolder(folder, files);
            } catch {
              toast.toast(t('watcherSyncFailed'), 'error');
            }
          }
        } finally {
          syncInFlight = false;
        }
      })();
    }, 10000);
    return () => window.clearInterval(timer);
  }, [running, syncFolder, t, toast]);

  const cardBg = isDark ? 'bg-white/[0.03] border-white/[0.06]' : 'bg-gray-50 border-gray-200';
  const muted = isDark ? 'text-white/65' : 'text-gray-600';
  const label = isDark ? 'text-white/80' : 'text-gray-800';
  const field = isDark ? 'bg-black/20 border-white/[0.08] text-white/90 placeholder-white/55' : 'bg-white border-gray-200 text-gray-800 placeholder-gray-600';
  const visibleFolders = folders.filter((folder) => folder.collectionId === collectionId);

  return (
    <section className={`rounded-xl border p-4 space-y-3 ${cardBg}`}>
      <input ref={fileInputRef} type="file" className="hidden" onChange={onInputChange} {...{ webkitdirectory: '', directory: '' }} />
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className={`text-base font-semibold ${label}`}>{t('watcherTitle')}</h2>
          <div role="status" className={`mt-1 flex items-center gap-1.5 text-sm ${muted}`}>
            <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${running ? 'bg-emerald-400' : isDark ? 'bg-white/40' : 'bg-gray-400'}`} />
            {running ? t('watcherActive').replace('{count}', String(events)) : t('watcherInactive')}
          </div>
        </div>
        <button onClick={() => void toggleWatcher()} disabled={busy || (!running && folders.length === 0 && !hostPath.trim())} className={`flex min-h-11 shrink-0 items-center gap-1.5 rounded-lg px-3 text-sm font-medium transition-colors disabled:opacity-50 ${running ? `border bg-red-500/10 hover:bg-red-500/20 ${isDark ? 'border-red-400/20 text-red-400' : 'border-red-700/20 text-red-700'}` : 'bg-[#006bbd] text-white hover:bg-[#0059a0]'}`}>
          {running ? <><MdVisibilityOff size={14} /> {t('stop')}</> : <><MdVisibility size={14} /> {t('start')}</>}
        </button>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row">
        <button onClick={() => void chooseFolder()} disabled={busy} className="flex min-h-11 items-center justify-center gap-1.5 rounded-lg bg-[#006bbd] px-3 text-sm font-medium text-white hover:bg-[#0059a0] disabled:opacity-50"><MdFolder size={15} />{t('watcherAddFolder')}</button>
        <select value={collectionId} onChange={(event) => setCollectionId(event.target.value)} aria-label={t('collectionsLabel')} name="watcher-collection" className={`min-h-11 min-w-0 flex-1 rounded-lg border px-3 py-2 text-base outline-hidden sm:text-sm ${field}`}>
          {(collections.length ? collections : [{ id: 'default', name: t('generalCollection') }]).map((collection) => <option key={collection.id} value={collection.id}>{collection.name} ({folders.filter((folder) => folder.collectionId === collection.id).length})</option>)}
        </select>
      </div>

      <div className="space-y-1">
        <input
          value={hostPath}
          onChange={(event) => setHostPath(event.target.value)}
          disabled={running}
          placeholder={t('watcherHostPath')}
          aria-label={t('watcherHostPath')}
          name="watcher-host-path"
          autoComplete="off"
          className={`min-h-11 w-full rounded-lg border px-3 py-2 text-base outline-hidden sm:text-sm ${field}`}
        />
        <p className={`text-sm ${muted}`}>{t('watcherHostPathDesc')}</p>
      </div>

      <AnimatePresence initial={false}>
        {visibleFolders.length > 0 && (
          <motion.div
            key="watcher-folders"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="space-y-1.5 overflow-hidden"
          >
            {visibleFolders.map((folder) => <motion.div key={folder.id} layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, height: 0 }} className={`flex min-h-12 items-center gap-2 rounded-lg border px-2.5 py-1 text-sm ${field}`}>
              <MdFolder size={15} className="shrink-0 opacity-70" /><span className="min-w-0 flex-1 truncate" title={folder.name}>{folder.name}</span><span className={`text-xs ${muted}`}>{folder.files?.length || 0}</span>
              <button onClick={() => setPendingRemoveFolder(folder)} className={`grid h-11 w-11 shrink-0 place-items-center rounded-lg ${isDark ? 'text-red-400 hover:text-red-300' : 'text-red-700 hover:text-red-800'}`} aria-label={`${t('deleteFolder')} ${folder.name}`} title={t('deleteFolder')}><MdDelete size={15} /></button>
            </motion.div>)}
          </motion.div>
        )}
      </AnimatePresence>

      <p className={`flex items-center gap-1.5 text-sm ${muted}`}><MdRefresh size={12} className="opacity-60" />{t('watcherChooseFolders')}</p>
      <AnimatePresence initial={false}>
        {running && (
          <motion.p
            key="watcher-running"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className={`flex items-center gap-1.5 overflow-hidden text-sm ${muted}`}
          >
            <MdSync size={12} className="opacity-60" />{t('watcherAutoReindexDesc')}
          </motion.p>
        )}
        {serverJob && serverJob.status !== 'idle' && (
          <motion.p
            key="watcher-status"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className={`overflow-hidden text-sm ${muted}`}
            aria-live="polite"
          >
            {t('watcherIndexStatus').replace('{status}', serverJob.status)}
            {serverJob.pending_events > 0 ? ` | ${t('watcherPendingEvents').replace('{count}', String(serverJob.pending_events))}` : ''}
          </motion.p>
        )}
        {serverJob?.last_error && (
          <motion.p
            key="watcher-error"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className={`overflow-hidden text-sm ${isDark ? 'text-red-400' : 'text-red-700'}`}
            role="alert"
          >
            {t('watcherLastError').replace('{error}', serverJob.last_error.slice(0, 500))}
          </motion.p>
        )}
      </AnimatePresence>
      <ConfirmModal
        open={Boolean(pendingRemoveFolder)}
        title={t('deleteFolder')}
        message={t('watcherRemoveFolderConfirm')}
        confirmLabel={t('delete')}
        danger
        onConfirm={() => {
          if (pendingRemoveFolder) void removeFolder(pendingRemoveFolder);
          setPendingRemoveFolder(null);
        }}
        onCancel={() => setPendingRemoveFolder(null)}
      />
    </section>
  );
}
