import { useCallback, useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { MdDelete, MdFolder, MdRefresh, MdSync, MdVisibility, MdVisibilityOff } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { useToast } from './Toast';
import {
  deleteIndexedImport,
  getWatchStatus,
  startFolderIndex,
  startWatch,
  stopWatch,
  type WatchJobStatus,
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
  const [folders, setFolders] = useState<WatchedFolder[]>([]);
  const [collectionId, setCollectionId] = useState(() => collections[0]?.id || 'default');
  const [running, setRunning] = useState(false);
  const [serverWatching, setServerWatching] = useState(false);
  const [hostPath, setHostPath] = useState('');
  const [events, setEvents] = useState(0);
  const [busy, setBusy] = useState(false);
  const [serverJob, setServerJob] = useState<WatchJobStatus | null>(null);

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
      toast.toast(error instanceof Error ? error.message.slice(0, 220) : t('watcherSyncFailed'), 'error');
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
      toast.toast(error instanceof Error ? error.message.slice(0, 180) : t('watcherSyncFailed'), 'error');
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
      toast.toast(error instanceof Error ? error.message.slice(0, 180) : t('watcherSyncFailed'), 'error');
    }
  }, [t, toast, updateFolders]);

  const toggleWatcher = useCallback(async () => {
    if (running) {
      if (serverWatching) await stopWatch().catch(() => undefined);
      setServerWatching(false);
      setServerJob(null);
      setRunning(false);
      return;
    }
    const normalizedPath = hostPath.trim();
    if (normalizedPath) {
      setBusy(true);
      try {
        await startWatch({ paths: [normalizedPath], collection: collectionId });
        setServerWatching(true);
        setRunning(true);
      } catch (error) {
        toast.toast(error instanceof Error ? error.message.slice(0, 180) : t('watcherSyncFailed'), 'error');
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
    const controller = new AbortController();
    const refreshStatus = async () => {
      try {
        const status = await getWatchStatus(controller.signal);
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
  const muted = isDark ? 'text-white/45' : 'text-gray-500';
  const label = isDark ? 'text-white/80' : 'text-gray-800';
  const field = isDark ? 'bg-black/20 border-white/[0.08] text-white/80' : 'bg-white border-gray-200 text-gray-800';
  const visibleFolders = folders.filter((folder) => folder.collectionId === collectionId);

  return (
    <section className={`rounded-xl border p-4 space-y-3 ${cardBg}`}>
      <input ref={fileInputRef} type="file" className="hidden" onChange={onInputChange} {...{ webkitdirectory: '', directory: '' }} />
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className={`text-sm font-medium ${label}`}>{t('watcherTitle')}</div>
          <div className={`text-[11px] ${muted} mt-0.5`}>{running ? t('watcherActive').replace('{count}', String(events)) : t('watcherInactive')}</div>
        </div>
        <button onClick={() => void toggleWatcher()} disabled={busy || (folders.length === 0 && !hostPath.trim())} className={`px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-30 transition-colors flex items-center gap-1.5 ${running ? 'bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20' : 'bg-[#006bbd] text-white hover:bg-[#0059a0]'}`}>
          {running ? <><MdVisibilityOff size={14} /> {t('stop')}</> : <><MdVisibility size={14} /> {t('start')}</>}
        </button>
      </div>

      <div className="flex gap-2">
        <button onClick={() => void chooseFolder()} disabled={busy} className="rounded-lg bg-[#006bbd] px-3 py-2 text-xs font-medium text-white hover:bg-[#0059a0] disabled:opacity-50 flex items-center gap-1.5"><MdFolder size={15} />{t('watcherAddFolder')}</button>
        <select value={collectionId} onChange={(event) => setCollectionId(event.target.value)} aria-label={t('collectionsLabel')} name="watcher-collection" className={`min-w-0 flex-1 rounded-lg border px-3 py-2 text-xs outline-none ${field}`}>
          {(collections.length ? collections : [{ id: 'default', name: 'General' }]).map((collection) => <option key={collection.id} value={collection.id}>{collection.name} ({folders.filter((folder) => folder.collectionId === collection.id).length})</option>)}
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
          className={`w-full rounded-lg border px-3 py-2 text-xs outline-none ${field}`}
        />
        <p className={`text-[10px] ${muted}`}>{t('watcherHostPathDesc')}</p>
      </div>

      {visibleFolders.length > 0 && <div className="space-y-1.5">
        {visibleFolders.map((folder) => <motion.div key={folder.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className={`flex items-center gap-2 rounded-lg border px-2.5 py-2 text-xs ${field}`}>
          <MdFolder size={15} className="shrink-0 opacity-70" /><span className="min-w-0 flex-1 truncate" title={folder.name}>{folder.name}</span><span className={`text-[10px] ${muted}`}>{folder.files?.length || 0}</span>
          <button onClick={() => void removeFolder(folder)} className="p-1 text-red-400 hover:text-red-300" aria-label={`${t('deleteFolder')} ${folder.name}`} title={t('deleteFolder')}><MdDelete size={15} /></button>
        </motion.div>)}
      </div>}

      <p className={`text-[11px] ${muted} flex items-center gap-1.5`}><MdRefresh size={12} className="opacity-60" />{t('watcherChooseFolders')}</p>
      {running && <p className={`text-[11px] ${muted} flex items-center gap-1.5`}><MdSync size={12} className="opacity-60" />{t('watcherAutoReindexDesc')}</p>}
      {serverJob && serverJob.status !== 'idle' && <p className={`text-[11px] ${muted}`} aria-live="polite">
        {t('watcherIndexStatus').replace('{status}', serverJob.status)}
        {serverJob.pending_events > 0 ? ` · ${t('watcherPendingEvents').replace('{count}', String(serverJob.pending_events))}` : ''}
      </p>}
      {serverJob?.last_error && <p className="text-[11px] text-red-400" role="alert">
        {t('watcherLastError').replace('{error}', serverJob.last_error.slice(0, 500))}
      </p>}
    </section>
  );
}
