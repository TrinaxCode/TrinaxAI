import { useRef, useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { MdAdd, MdDelete, MdDeleteSweep, MdTranslate, MdDarkMode, MdLightMode, MdBook, MdRefresh, MdStorage, MdPowerSettingsNew, MdRocketLaunch, MdStop, MdPerson, MdCheck, MdFolder, MdVolumeOff, MdVolumeUp, MdFavoriteBorder, MdStar, MdShare, MdCode } from 'react-icons/md';
import { FaGithub } from 'react-icons/fa';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { useToast } from './Toast';
import ConfirmModal from './ConfirmModal';
import StatusDots from './StatusDots';
import WatcherCard from './WatcherCard';
import MemoryPanel from './MemoryPanel';
import FolderPicker from './FolderPicker';
import DevicePairingCard from './DevicePairingCard';
import BackButton from './BackButton';
import StatsPanel from './StatsPanel';
import RecentIndexes from './RecentIndexes';
import { MODEL_PRESETS, apiErrorFromPayload, cancelIndexJob, checkStatus, createCollection, deleteCollection, deleteCollectionSources, folderLabelFromFiles, formatUserFacingError, getCollections, getIndexJob, indexableFilesFrom, modelSetting, renameCollection, resetSharedAppState, retryIndexJob, startFolderIndex, startLocalAi, systemRequestHeaders, userFacingError, type Collection, type IndexJobStatus, type ModelPreset, type ModelSettingKey } from '../lib/api';
import { APP_CONFIG } from '../lib/config';
import { syncSharedStateOnce } from '../lib/sharedState';
import { NICKNAME_KEY, isValidProfileName } from '../lib/userProfile';
import { audioManager } from '../services/audioManager';
import WebSearchSettings from './WebSearchSettings';
import SettingsModels from './SettingsModels';
import SettingsPrompts from './SettingsPrompts';

type SettingsSection = 'general' | 'web-search' | 'indexing' | 'prompts' | 'memory' | 'stats' | 'help';

interface Props {
  onBack: () => void;
  onOpenDocs: () => void;
  initialSection?: SettingsSection;
  onSectionChange?: (section: SettingsSection) => void;
  canManageSystem?: boolean;
}
export default function Settings({ onBack, onOpenDocs, initialSection = 'general', onSectionChange, canManageSystem = false }: Props) {
  const { t, lang, setLang } = useI18n();
  const { theme, cycleTheme, isDark } = useTheme();
  const toast = useToast();
  const [section, setSection] = useState<SettingsSection>(initialSection);
  const [soundEffects, setSoundEffects] = useState(() => audioManager.enabled());
  const [detectedProfile, setDetectedProfile] = useState<ModelPreset | null>(null);
  const changeSection = (next: SettingsSection) => {
    setSection(next);
    onSectionChange?.(next);
  };

  useEffect(() => {
    changeSection(initialSection);
  }, [initialSection]);

  useEffect(() => {
    let alive = true;
    void Promise.resolve(checkStatus()).then((status) => {
      if (alive && status?.profile) setDetectedProfile(status.profile);
    }).catch(() => undefined);
    return () => { alive = false; };
  }, []);

  // Allow external callers (e.g. /memory slash command) to jump to a specific section.
  useEffect(() => {
    const onJump = (e: Event) => {
      const detail = (e as CustomEvent).detail as { section?: string } | undefined;
      if (detail?.section && ['general', 'web-search', 'indexing', 'prompts', 'memory', 'stats', 'help'].includes(detail.section)) {
        changeSection(detail.section as typeof section);
      }
    };
    window.addEventListener('tc-open-section', onJump as EventListener);
    return () => window.removeEventListener('tc-open-section', onJump as EventListener);
  }, []);

  useEffect(() => {
    const onMem = () => changeSection('memory');
    window.addEventListener('tc-open-memory-tab', onMem);
    return () => window.removeEventListener('tc-open-memory-tab', onMem);
  }, []);
  const [sd, setSd] = useState(false); const [su, setSu] = useState(false);
  const [nickname, setNicknameValue] = useState(() => localStorage.getItem(NICKNAME_KEY) || '');
  const [nicknameEditing, setNicknameEditing] = useState(false);
  const [agentWorkspace, setAgentWorkspace] = useState(() => {
    try { return localStorage.getItem('tc-agent-workspace') || ''; } catch { return ''; }
  });
  const [agentPickerOpen, setAgentPickerOpen] = useState(false);
  const saveNickname = () => {
    const trimmed = nickname.trim();
    if (!trimmed) {
      localStorage.removeItem(NICKNAME_KEY);
    } else if (!isValidProfileName(trimmed)) {
      toast.toast(t('profileNicknameReserved'), 'warning');
      return;
    } else {
      localStorage.setItem(NICKNAME_KEY, trimmed);
    }
    setNicknameEditing(false);
    toast.toast(t('profileNicknameSaved'), 'success');
    void syncSharedStateOnce(800);
  };
  const [indexing, setIndexing] = useState(false);
  const [restoreConfirm, setRestoreConfirm] = useState('');
  const [showRestore, setShowRestore] = useState(false);
  const [confirmShutdown, setConfirmShutdown] = useState(false);
  const [confirmStartup, setConfirmStartup] = useState(false);
  const [confirmStopAll, setConfirmStopAll] = useState(false);
  const [stoppingAll, setStoppingAll] = useState(false);
  const [confirmIndex, setConfirmIndex] = useState(false);
  const [collectionDeleteId, setCollectionDeleteId] = useState<string | null>(null);
  const [collectionClearId, setCollectionClearId] = useState<string | null>(null);
  const [clearingCollectionId, setClearingCollectionId] = useState<string | null>(null);
  const [selectedFolderFiles, setSelectedFolderFiles] = useState<File[] | null>(null);
  const [selectedFolderTotal, setSelectedFolderTotal] = useState(0);
  const [indexJob, setIndexJob] = useState<IndexJobStatus | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const cancelNoticeShownRef = useRef(false);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [newCollectionName, setNewCollectionName] = useState('');
  const [indexCollectionId, setIndexCollectionId] = useState(() => localStorage.getItem('tc-index-collection') || 'default');
  const [lastIndexedLabel, setLastIndexedLabel] = useState('');
  const folderInputRef = useRef<HTMLInputElement>(null);
  const indexAbortRef = useRef<AbortController | null>(null);
  const clearJobTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [, refreshLocalSettings] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timer = 0;
    try {
      const saved = JSON.parse(localStorage.getItem('tc-last-index-import') || 'null');
      if (!saved?.jobId) return undefined;
      const poll = async () => {
        try {
          const job = await getIndexJob(String(saved.jobId));
          if (cancelled) return;
          setIndexJob(job);
          const active = ['saving', 'indexing'].includes(job.status);
          setIndexing(active);
          if (active) timer = window.setTimeout(poll, 1000);
        } catch {
          if (!cancelled) timer = window.setTimeout(poll, 2500);
        }
      };
      void poll();
    } catch { /* no resumable job */ }
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, []);

  const setLocalSetting = (key: string, value: string) => {
    localStorage.setItem(key, value);
    refreshLocalSettings((rev) => rev + 1);
  };

  const showCancelNotice = () => {
    if (cancelNoticeShownRef.current) return;
    cancelNoticeShownRef.current = true;
    toast.toast(t('indexCancelled'), 'info');
  };

  const refreshCollections = async () => {
    try {
      const items = await getCollections();
      const next = items.length ? items : [{ id: 'default', name: 'General', created_at: Date.now() / 1000, updated_at: Date.now() / 1000 }];
      setCollections(next);
      if (!next.some((item) => item.id === indexCollectionId)) setIndexCollectionId('default');
    } catch {
      setCollections([{ id: 'default', name: 'General', created_at: Date.now() / 1000, updated_at: Date.now() / 1000 }]);
    }
  };

  useEffect(() => { localStorage.setItem('tc-index-collection', indexCollectionId); }, [indexCollectionId]);
  useEffect(() => { void refreshCollections(); }, []);

  // On unmount, abort any in-flight indexing poll and clear the pending
  // clear-job timer so we never call setState on an unmounted component.
  useEffect(() => {
    return () => {
      indexAbortRef.current?.abort();
      if (clearJobTimerRef.current) {
        clearTimeout(clearJobTimerRef.current);
        clearJobTimerRef.current = null;
      }
    };
  }, []);

  const addCollection = async () => {
    const name = newCollectionName.trim();
    if (!name) return;
    try {
      const created = await createCollection(name);
      setCollections((items) => [...items, created]);
      setIndexCollectionId(created.id);
      setNewCollectionName('');
      toast.toast(t('collectionCreated'), 'success');
    } catch (err) {
      toast.toast(userFacingError(err, 'external_service_unavailable'), 'error');
    }
  };
  const updateCollectionName = async (id: string, current: string, next: string) => {
    const name = next.trim();
    if (!name || name === current) return;
    try {
      const updated = await renameCollection(id, name);
      setCollections((items) => items.map((item) => item.id === id ? updated : item));
      toast.toast(t('collectionRenamed'), 'success');
    } catch (err) {
      toast.toast(userFacingError(err, 'external_service_unavailable'), 'error');
    }
  };
  const removeCollection = async (id: string) => {
    if (id === 'default') return;
    try {
      await deleteCollection(id);
      setCollections((items) => items.filter((item) => item.id !== id));
      if (indexCollectionId === id) setIndexCollectionId('default');
      setCollectionDeleteId(null);
      toast.toast(t('collectionDeleted'), 'info');
    } catch (err) {
      toast.toast(userFacingError(err, 'external_service_unavailable'), 'error');
    }
  };
  const clearCollection = async (id: string) => {
    setClearingCollectionId(id);
    try {
      const result = await deleteCollectionSources(id);
      const collection = collections.find((item) => item.id === id);
      toast.toast(
        t('collectionSourcesCleared')
          .replace('{collection}', collection?.name || id)
          .replace('{count}', String(result.deleted)),
        'info',
      );
      setCollectionClearId(null);
    } catch (err) {
      toast.toast(userFacingError(err, 'external_service_unavailable'), 'error');
    } finally {
      setClearingCollectionId(null);
    }
  };
  const sys = async (a:'shutdown'|'startup'|'stop-all') => {
    const s = a === 'shutdown' ? setSd : a === 'startup' ? setSu : setStoppingAll; s(true);
    try {
      if (a === 'startup') {
        await startLocalAi();
        toast.toast(t('executedOk'), 'success');
        return;
      }
      const r = await fetch(`/api/system/${a}`, { method: 'POST', headers: systemRequestHeaders() });
      const d = await r.json();
      const ok = Boolean(d.ok);
      toast.toast(ok && a === 'stop-all' ? t('stopAllInitiated') : ok ? t('executedOk') : formatUserFacingError(apiErrorFromPayload(r.status, d)), ok ? 'success' : 'error');
    } catch (err) {
      toast.toast(formatUserFacingError(err, 'external_service_unavailable'), 'error');
    } finally {
      s(false);
    }
  };

  const triggerIndex = async () => {
    setIndexing(true); setConfirmIndex(false);
    setUploadProgress(0);
    setIndexJob(null);
    cancelNoticeShownRef.current = false;
    // Cancel any pending clear-job timer from a previous run
    if (clearJobTimerRef.current) { clearTimeout(clearJobTimerRef.current); clearJobTimerRef.current = null; }
    const controller = new AbortController();
    indexAbortRef.current = controller;
    try {
      if (!selectedFolderFiles?.length) {
        toast.toast(t('indexNoFolder'), 'warning');
        return;
      }
      const started = await startFolderIndex(selectedFolderFiles, {
        signal: controller.signal,
        onUploadProgress: setUploadProgress,
        collectionId: indexCollectionId,
      });
      if (!started.job_id) throw new Error('Missing index job id.');
      let done = false;
      while (!done && !controller.signal.aborted) {
        const job = await getIndexJob(started.job_id, controller.signal);
        setIndexJob(job);
        if (job.status === 'completed') {
          const label = selectedFolderFiles ? folderLabelFromFiles(selectedFolderFiles) : '';
          toast.toast(t('indexImportComplete').replace('{count}', String(job.saved)), 'success');
          setLastIndexedLabel(label);
          setSelectedFolderFiles(null);
          setSelectedFolderTotal(0);
          done = true;
        } else if (job.status === 'cancelled') {
          showCancelNotice();
          done = true;
        } else if (job.status === 'failed') {
          toast.toast(job.error ? userFacingError(new Error(job.error), 'internal_server_error') : t('indexFailed'), 'error');
          done = true;
        } else {
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }
      }
      if (controller.signal.aborted) {
        showCancelNotice();
        setSelectedFolderFiles(null);
        setSelectedFolderTotal(0);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        showCancelNotice();
      } else {
        const friendly = userFacingError(err, 'external_service_unavailable');
        toast.toast(`${t('indexBackendError')} ${friendly}`, 'error');
      }
    }
    finally {
      setIndexing(false);
      indexAbortRef.current = null;
      // Clear progress bar after a short delay so user sees the completion
      clearJobTimerRef.current = setTimeout(() => {
        clearJobTimerRef.current = null;
        setIndexJob(null);
      }, 2000);
    }
  };

  const cancelIndex = async () => {
    showCancelNotice();
    const current = indexJob;
    indexAbortRef.current?.abort();
    if (current?.id) {
      const cancelled = await cancelIndexJob(current.id).catch(() => null);
      if (cancelled) setIndexJob(cancelled);
    }
    setIndexing(false);
  };

  const doRestore = async () => {
    if (restoreConfirm !== 'RESTAURAR' && restoreConfirm !== 'RESTORE') return;
    try {
      await resetSharedAppState();
    } catch (reason) {
      toast.toast(userFacingError(reason, 'permission_denied'), 'error');
      return;
    }
    const resetAt = String(Date.now() / 1000);
    try { sessionStorage.setItem('trinaxai-resetting', '1'); } catch { /* ignore */ }
    const keys = Object.keys(localStorage).filter(k => k.startsWith('tc-'));
    keys.forEach(k => localStorage.removeItem(k));
    localStorage.setItem('tc-reset-at', resetAt);
    await syncSharedStateOnce(1800).catch(() => undefined);
    window.location.reload();
  };

  const setModelPreset = (preset: ModelPreset) => {
    const values = MODEL_PRESETS[preset];
    Object.entries(values).forEach(([k, v]) => setLocalSetting(k, v));
    toast.toast(t('modelPresetApplied'), 'success');
  };

  const getModel = (key: ModelSettingKey) => {
    const profile = detectedProfile || '16gb';
    return modelSetting(key, MODEL_PRESETS[profile][key]);
  };
  const progress = Math.max(uploadProgress, indexJob?.progress ?? 0);
  const filesProcessed = indexJob?.files_processed || indexJob?.saved || 0;
  const filesTotal = indexJob?.files_total || selectedFolderFiles?.length || indexJob?.saved || 0;
  const phaseLabel = (phase: string | undefined) => t(({
    saving: 'indexPhaseSaving',
    queued: 'indexPhaseQueued',
    starting: 'indexPhaseStarting',
    extracting: 'indexPhaseExtracting',
    indexing: 'indexPhaseIndexing',
    chunking: 'indexPhaseChunking',
    embedding: 'indexPhaseEmbedding',
    saving_index: 'indexPhaseSavingIndex',
    timeout: 'indexPhaseTimeout',
    interrupted: 'indexPhaseInterrupted',
    finishing: 'indexPhaseFinishing',
    completed: 'indexPhaseCompleted',
    cancelled: 'indexPhaseCancelled',
    failed: 'indexPhaseFailed',
    upload_limit: 'indexPhaseFailed',
    empty: 'indexPhaseFailed',
  } as Record<string, any>)[phase || ''] || 'indexPhaseIndexing');

  const btnBase = isDark
    ? 'bg-white/[0.03] border-white/[0.06] text-white/70 hover:bg-white/[0.06]'
    : 'bg-gray-50 border-gray-200 text-gray-700 hover:bg-gray-100';
  const dangerButton = isDark
    ? 'bg-red-500/10 border-red-400/30 text-red-300 hover:bg-red-500/20'
    : 'bg-red-50 border-red-200 text-red-700 hover:bg-red-100';

  const bgCard = isDark ? 'bg-white/[0.03] border-white/[0.06]' : 'bg-gray-50 border-gray-200';
  const textHeading = isDark ? 'text-white/40' : 'text-gray-500';
  const textLabel = isDark ? 'text-white/80' : 'text-gray-800';
  const textPlaceholder = isDark ? 'placeholder-white/20' : 'placeholder-gray-400';
  const textValue = isDark ? 'text-white/70' : 'text-gray-700';
  const inputText = isDark ? 'text-white/70' : 'text-gray-700';
  const borderFocus = 'focus:border-[#006bbd]/40';
  const sectionBg = isDark ? 'bg-white/[0.03] border-white/[0.06]' : 'bg-gray-50 border-gray-200';
  const shareProject = async () => {
    const shareData = { title: 'TrinaxAI', text: t('helpProjectShareText'), url: APP_CONFIG.websiteUrl };
    try {
      if (navigator.share) await navigator.share(shareData);
      else {
        await navigator.clipboard.writeText(APP_CONFIG.websiteUrl);
        toast.toast(t('helpProjectShareCopied'), 'success');
      }
    } catch { /* Sharing can be cancelled by the user. */ }
  };

  return (<motion.div className="settings-page h-full flex flex-col min-w-0 max-w-full overflow-x-hidden bg-transparent" initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}>
    <div className="page-header shrink-0 flex items-center gap-3 px-4 pt-[env(safe-area-inset-top,0px)] pb-3">
      <BackButton onClick={onBack} label={t('back')} isDark={isDark} className="-ml-2" />
      <span className={`text-sm font-medium ${textLabel}`}>{t('settingsTitle')}</span>
    </div>
    <div className="page-tabs shrink-0 flex gap-0.5 sm:gap-1 px-1 sm:px-2 pt-2 pb-1 overflow-x-auto overscroll-x-contain">
      {([
        ['general', t('settingsGeneral')],
        ['web-search', t('webSearchSettingsTitle')],
        ['indexing', t('settingsIndexing')],
        ['prompts', t('settingsPrompts')],
        ['memory', t('settingsMemory')],
        ['stats', t('settingsStats')],
        ['help', t('helpProjectTitle')],
      ] as const).map(([k, lbl]) => (
        <button
          key={k}
          onClick={() => changeSection(k)}
          className={`shrink-0 px-1.5 sm:px-2 py-1 rounded-lg text-[10px] sm:text-[11px] font-medium transition-colors whitespace-nowrap ${
            section === k
              ? 'bg-[#006bbd]/15 text-[#006bbd]'
              : isDark ? 'text-white/50 hover:text-white/80' : 'text-gray-500 hover:text-gray-800'
          }`}
        >
          {lbl}
        </button>
      ))}
    </div>
    <div className="settings-scroll flex-1 overflow-y-auto px-4 pt-6 pb-[calc(env(safe-area-inset-bottom,0px)+24px)] space-y-6">

      {section === 'general' && (<>
      {/* Status Section */}
      <section>
        <h3 className={`text-xs font-medium uppercase tracking-widest mb-3 ${textHeading}`}>{t('status')}</h3>
        <div className={`${bgCard} rounded-xl px-4 py-3`}>
          <StatusDots />
        </div>
      </section>

      {/* ── Profile ── */}
      <section>
        <h3 className={`text-xs font-medium uppercase tracking-widest mb-3 ${textHeading}`}>{t('profile')}</h3>
        <div className={`${bgCard} rounded-xl border px-4 py-3 space-y-2`}>
          <label className={`text-[10px] uppercase tracking-wider ${textHeading}`}>{t('profileNicknameLabel')}</label>
          <div className="flex items-center gap-2">
            <MdPerson size={18} className={isDark ? 'text-white/30' : 'text-gray-400'} />
            {nicknameEditing ? (
              <>
                <input
                  type="text"
                  value={nickname}
                  onChange={(e) => setNicknameValue(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') saveNickname(); if (e.key === 'Escape') { setNicknameValue(localStorage.getItem(NICKNAME_KEY) || ''); setNicknameEditing(false); } }}
                  placeholder={t('profileNicknameLabel')}
                  aria-label={t('profileNicknameLabel')}
                  name="nickname"
                  autoComplete="off"
                  className={`min-w-0 flex-1 bg-transparent text-sm outline-none border-b ${isDark ? 'text-white/80 border-[#006bbd]/40 placeholder-white/20' : 'text-gray-800 border-[#006bbd]/40 placeholder-gray-400'} focus:border-[#006bbd] px-1 py-0.5`}
                />
                <button
                  onClick={saveNickname}
                  className={`p-1.5 rounded-lg ${isDark ? 'text-[#006bbd] hover:bg-white/[0.06]' : 'text-[#006bbd] hover:bg-gray-100'}`}
                  title={t('save')}
                  aria-label={t('save')}
                >
                  <MdCheck size={18} />
                </button>
              </>
            ) : (
              <>
                <span className={`min-w-0 flex-1 text-sm ${isDark ? 'text-white/70' : 'text-gray-700'}`}>
                  {nickname.trim() || t('userLabel')}
                </span>
                <button
                  onClick={() => setNicknameEditing(true)}
                  className={`px-2 py-1 rounded-lg text-xs font-medium transition-colors ${
                    isDark ? 'text-white/40 hover:text-white/70 hover:bg-white/[0.06]' : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
                  }`}
                >
                  {t('edit')}
                </button>
              </>
            )}
          </div>
          <p className={`text-[10px] leading-relaxed ${isDark ? 'text-white/25' : 'text-gray-600'}`}>
            {t('profileNicknameHint')}
          </p>
        </div>
      </section>

      {/* ── Language & Theme ── */}
      <section>
        <h3 className={`text-xs font-medium uppercase tracking-widest mb-3 ${textHeading}`}>{t('language')} & {t('theme')}</h3>
        <div className="flex flex-col sm:flex-row gap-3">
          {/* Language Toggle */}
          <button
            onClick={() => setLang(lang === 'es' ? 'en' : 'es')}
            className={`min-w-0 flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl border text-sm font-medium text-center transition-colors ${
              isDark
                ? 'bg-white/[0.03] border-white/[0.06] text-white/70 hover:bg-white/[0.06]'
                : 'bg-gray-50 border-gray-200 text-gray-700 hover:bg-gray-100'
            }`}
          >
            <MdTranslate size={18} />
            {lang === 'es' ? t('languageSpanish') : t('languageEnglish')}
          </button>

          {/* Theme toggle */}
          <button
            onClick={cycleTheme}
            className={`min-w-0 flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl border text-sm font-medium text-center transition-colors ${
              isDark
                ? 'bg-white/[0.03] border-white/[0.06] text-white/70 hover:bg-white/[0.06]'
                : 'bg-gray-50 border-gray-200 text-gray-700 hover:bg-gray-100'
            }`}
            title={t('toggleTheme')}
          >
            {isDark ? <MdDarkMode size={18} /> : <MdLightMode size={18} />}
            {theme === 'dark' ? t('darkMode') : t('lightMode')}
          </button>
        </div>
      </section>

      <section>
        <h3 className={`text-xs font-medium uppercase tracking-widest mb-3 ${textHeading}`}>{t('soundEffects')}</h3>
        <button
          type="button"
          role="switch"
          aria-checked={soundEffects}
          onClick={() => {
            const enabled = !soundEffects;
            setSoundEffects(enabled);
            audioManager.setEnabled(enabled);
            if (enabled) audioManager.play('tool-complete');
          }}
          className={`${bgCard} flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left`}
        >
          {soundEffects ? <MdVolumeUp size={20} className="text-[#006bbd]" /> : <MdVolumeOff size={20} className={textHeading} />}
          <span className="min-w-0 flex-1">
            <span className={`block text-sm font-medium ${isDark ? 'text-white/75' : 'text-gray-700'}`}>{t('soundEffects')}</span>
            <span className={`block text-[11px] ${textHeading}`}>{t('soundEffectsHint')}</span>
          </span>
          <span className={`h-6 w-11 rounded-full p-0.5 transition-colors ${soundEffects ? 'bg-[#006bbd]' : isDark ? 'bg-white/15' : 'bg-gray-300'}`}>
            <span className={`block h-5 w-5 rounded-full bg-white transition-transform ${soundEffects ? 'translate-x-5' : ''}`} />
          </span>
        </button>
      </section>

      {/* ── System Section ── */}
      <section>
        <h3 className={`text-xs font-medium uppercase tracking-widest mb-3 ${textHeading}`}>{t('system')}</h3>
        <DevicePairingCard isDark={isDark} canManageSystem={canManageSystem} />
        {canManageSystem && <div className={`${bgCard} mb-3 rounded-xl border px-4 py-3 space-y-1.5`}>
          <label className={`text-[10px] uppercase tracking-wider ${textHeading}`}>{t('agentSettingsTitle')} | {t('agentWorkspaceRootLabel')}</label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={agentWorkspace}
              spellCheck={false}
              onChange={(event) => setAgentWorkspace(event.target.value)}
              onBlur={(event) => { try { localStorage.setItem('tc-agent-workspace', event.target.value.trim()); } catch { /* ignore */ } }}
              placeholder="/path/to/project"
              aria-label={`${t('agentSettingsTitle')} | ${t('agentWorkspaceRootLabel')}`}
              name="agent-workspace"
              autoComplete="off"
              className={`min-w-0 flex-1 rounded-lg border bg-transparent px-3 py-2 font-mono text-xs outline-none ${isDark ? 'border-white/[0.08] text-white/80 placeholder-white/25' : 'border-gray-200 text-gray-800 placeholder-gray-400'}`}
            />
            <button
              onClick={() => setAgentPickerOpen(true)}
              className={`flex shrink-0 items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium ${isDark ? 'border-white/[0.08] text-white/70 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-600 hover:bg-gray-100'}`}
            >
              <MdFolder size={14} className="text-[#006bbd]" /> {t('agentPickFolder')}
            </button>
          </div>
          <p className={`text-[10px] ${textHeading}`}>{t('agentWorkspaceRootHint')}</p>
        </div>}
        {canManageSystem && <div className="flex flex-col sm:flex-row gap-3">
          <button onClick={() => setConfirmShutdown(true)} disabled={sd} className={`min-w-0 flex-1 flex items-center justify-center gap-1.5 px-4 py-3 rounded-xl border text-sm font-medium text-center disabled:opacity-50 active:scale-95 transition-[background-color,border-color,opacity,transform] ${dangerButton}`}><MdPowerSettingsNew className="shrink-0" size={16} /><span className="min-w-0 break-words">{sd?t('shuttingDown'):t('shutdownAI')}</span></button>
          <button onClick={() => setConfirmStartup(true)} disabled={su} className={`min-w-0 flex-1 flex items-center justify-center gap-1.5 px-4 py-3 rounded-xl border text-sm font-medium text-center disabled:opacity-50 active:scale-95 transition-[background-color,border-color,opacity,transform] ${isDark ? 'bg-green-500/10 border-green-400/30 text-green-300 hover:bg-green-500/20' : 'bg-green-50 border-green-200 text-green-700 hover:bg-green-100'}`}><MdRocketLaunch className="shrink-0" size={16} /><span className="min-w-0 break-words">{su?t('startingUp'):t('startupAI')}</span></button>
        </div>}
      </section>

      {canManageSystem && <SettingsModels
        isDark={isDark}
        detectedProfile={detectedProfile}
        btnBase={btnBase}
        bgCard={bgCard}
        textHeading={textHeading}
        textLabel={textLabel}
        setLocalSetting={setLocalSetting}
        setModelPreset={setModelPreset}
        getModel={getModel}
      />}
      {/* ── Docs Link ── */}
      <section>
        <button onClick={onOpenDocs}
          className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl border text-sm font-medium transition-[background-color,color,border-color,transform] ${btnBase} active:scale-95`}>
          <MdBook size={16} />
          {t('viewDocs')}
        </button>
      </section>

      {/* ── Restore Config (Danger Zone) ── */}
      {canManageSystem && <section className="pb-8">
        {!showRestore ? (
          <button onClick={() => setShowRestore(true)}
            className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl border text-sm font-medium transition-[background-color,transform] active:scale-95 ${dangerButton}`}>
            <MdRefresh size={16} />
            {t('restoreConfig')}
          </button>
        ) : (
          <div className={`p-4 rounded-xl border border-red-500/20 bg-red-500/5 space-y-3`}>
            <p className="text-xs text-red-400/80">{t('restoreConfigConfirm')}</p>
            <input
              type="text"
              aria-label={t('restoreConfigWarning')}
              value={restoreConfirm}
              onChange={(e) => setRestoreConfirm(e.target.value)}
              placeholder={t('restoreConfigWarning')}
              className={`w-full px-3 py-2 rounded-lg border border-red-500/20 bg-transparent text-sm outline-none ${isDark ? 'text-white placeholder-white/20' : 'text-gray-900 placeholder-gray-400'}`}
            />
            <div className="flex gap-2">
              <button onClick={() => { setShowRestore(false); setRestoreConfirm(''); }}
                className={`flex-1 py-2 rounded-lg text-xs font-medium ${btnBase}`}>
                {t('cancel')}
              </button>
              <button onClick={doRestore}
                disabled={restoreConfirm !== 'RESTAURAR' && restoreConfirm !== 'RESTORE'}
                className={`flex-1 py-2 rounded-lg text-xs font-medium disabled:opacity-30 transition-[background-color,opacity] ${dangerButton}`}>
                {t('restoreConfig')}
              </button>
            </div>
          </div>
        )}
        {canManageSystem && <button onClick={() => setConfirmStopAll(true)}
          disabled={stoppingAll}
          className={`mt-3 w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl border text-sm font-medium transition-[background-color,transform] active:scale-95 ${dangerButton}`}>
          <MdPowerSettingsNew size={16} />
          {stoppingAll ? t('shuttingDown') : t('stopAllTrinaxAI')}
        </button>}
      </section>}
      </>)}

      {section === 'web-search' && <WebSearchSettings canManageSystem={canManageSystem} />}

      {section === 'indexing' && (
      <>
      {/* ── Index Section ── */}
      <section>
        <h3 className={`text-xs font-medium uppercase tracking-widest mb-3 ${textHeading}`}>{t('indexProjects')}</h3>
        <div className={`mb-3 flex items-center gap-2 px-3 py-2 rounded-xl border ${bgCard}`}>
          <span className={`text-[11px] shrink-0 ${textHeading}`}>{t('indexCollection')}</span>
          <select
            aria-label={t('indexCollection')}
            value={indexCollectionId}
            onChange={(e) => setIndexCollectionId(e.target.value)}
            className={`min-w-0 flex-1 bg-transparent text-sm outline-none ${inputText}`}
          >
            {collections.map((collection) => (
              <option key={collection.id} value={collection.id}>{collection.name}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            ref={folderInputRef}
            type="file"
            aria-label={t('chooseFolderIndex')}
            multiple
            className="hidden"
            onChange={(e) => {
              const files = Array.from(e.target.files ?? []);
              const indexable = indexableFilesFrom(files);
              if (files.length && indexable.length) {
                setSelectedFolderFiles(indexable);
                setSelectedFolderTotal(files.length);
                setConfirmIndex(true);
              } else if (files.length) {
                toast.toast(t('indexNoIndexableFiles'), 'warning');
              }
              e.target.value = '';
            }}
            {...{ webkitdirectory: '', directory: '' }}
          />
          <button onClick={() => folderInputRef.current?.click()} disabled={indexing}
            className={`min-w-0 flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl border text-sm font-medium text-center transition-[background-color,color,border-color,opacity,transform] ${btnBase} disabled:opacity-50 active:scale-95`}>
            <MdStorage className="shrink-0" size={16} />
            <span className="min-w-0 break-words">
              {indexing ? t('indexing') : lastIndexedLabel ? t('indexFolderSelected').replace('{folder}', lastIndexedLabel).replace('{count}', '-') : t('chooseFolderIndex')}
            </span>
          </button>
          {indexing && (
            <button
              onClick={cancelIndex}
              className="flex min-h-12 flex-1 items-center justify-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-400 shadow-sm transition-[background-color,border-color,transform] hover:border-red-500/50 hover:bg-red-500/20 active:scale-[.98] sm:flex-none"
              aria-label={t('indexCancel')}
              title={t('indexCancel')}
            >
              <MdStop size={16} />
              <span>{t('indexCancel')}</span>
            </button>
          )}
        </div>
        <p className={`mt-2 text-[11px] ${textHeading}`}>{t('indexFolderBrowserHint')}</p>
        {(indexing || indexJob) && (
          <div className={`mt-3 rounded-xl border p-3 space-y-2 ${bgCard}`}>
            {indexing ? (
              <>
                <div className="flex items-center justify-between gap-3">
                  <span className={`text-xs font-medium ${textLabel}`}>{phaseLabel(indexJob?.phase || (uploadProgress > 0 ? 'saving' : 'queued'))}</span>
                  <span className={`text-xs font-semibold tabular-nums ${textLabel}`}>{progress}%</span>
                </div>
                <div
                  className={`h-2.5 w-full overflow-hidden rounded-full ${isDark ? 'bg-white/[0.08]' : 'bg-gray-200'}`}
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={progress}
                  aria-label={phaseLabel(indexJob?.phase || 'indexing')}
                >
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-[#006bbd] via-[#138bd1] to-[#42c6a5] shadow-[0_0_10px_rgba(0,107,189,.35)] transition-[width] duration-500"
                    style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
                  />
                </div>
                <div className={`flex flex-wrap items-center justify-between gap-2 text-[11px] ${textHeading}`}>
                  <span>{t('indexElapsed')}: {indexJob?.elapsed_seconds ?? 0}s</span>
                  <span>{t('indexFiles')}: {filesProcessed} / {filesTotal}</span>
                  {!!indexJob?.pages_total && <span>{t('indexPages')}: {indexJob.pages_processed}/{indexJob.pages_total}</span>}
                  {!!indexJob?.chunks_generated && <span>{t('indexChunks')}: {indexJob.chunks_generated}</span>}
                  {!!indexJob?.skipped && <span>{t('indexSkipped')}: {indexJob.skipped}</span>}
                </div>
                {!!indexJob?.recent_activity && <p className={`text-[11px] ${textHeading}`}>{t('indexRecentActivity')}: {indexJob.recent_activity}</p>}
              </>
            ) : indexJob?.status === 'completed' ? (
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm min-w-0">
                  <MdCheck className="text-green-400 text-base shrink-0" aria-hidden="true" />
                  <span className={`font-medium ${textLabel} truncate`}>{t('indexComplete')}</span>
                  <span className={`${textHeading} shrink-0`}>({indexJob.saved} {t('indexFiles').toLowerCase()})</span>
                </div>
                <button
                  onClick={() => folderInputRef.current?.click()}
                  className="shrink-0 flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-[#006bbd]/15 text-[#006bbd] hover:bg-[#006bbd]/25 active:scale-95 transition-[background-color,transform]"
                  title={t('chooseFolderIndex')}
                >
                  <MdRefresh size={14} />
                  <span className="hidden sm:inline">{t('indexAgain')}</span>
                </button>
              </div>
            ) : indexJob?.status === 'failed' ? (
              <div className="flex items-center justify-between gap-3 text-sm text-red-400">
                <span><strong>{phaseLabel(indexJob.phase)}</strong>: {indexJob.error || t('indexFailed')}</span>
                <button className="shrink-0 rounded-lg bg-[#006bbd]/15 px-3 py-1.5 text-xs text-[#4ea3e0]" onClick={async () => { const job = await retryIndexJob(indexJob.id); setIndexJob(job); setIndexing(true); }}>{t('retry')}</button>
              </div>
            ) : indexJob?.status === 'cancelled' ? (
              <div className={`text-sm ${textLabel}`}>{t('indexCancelled')}</div>
            ) : null}
          </div>
        )}
      </section>

      <RecentIndexes />

      {/* ── Collections Section ── */}
      <section>
        <h3 className={`text-xs font-medium uppercase tracking-widest mb-3 ${textHeading}`}>{t('collections')}</h3>
        <div className="space-y-2">
          {collections.map((collection) => (
            <div key={collection.id} className={`flex items-center gap-2 px-3 py-2 rounded-xl border ${bgCard}`}>
              <input
                defaultValue={collection.name}
                disabled={collection.id === 'default'}
                onBlur={(e) => updateCollectionName(collection.id, collection.name, e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') (e.target as HTMLInputElement).blur();
                }}
                className={`min-w-0 flex-1 bg-transparent text-sm outline-none disabled:opacity-60 ${inputText}`}
              />
              {canManageSystem && (
                <button
                  onClick={() => setCollectionClearId(collection.id)}
                  disabled={clearingCollectionId === collection.id}
                  className={`p-1.5 rounded-lg ${isDark ? 'text-white/25 hover:text-amber-400 hover:bg-white/[0.05]' : 'text-gray-300 hover:text-amber-600 hover:bg-gray-100'} disabled:opacity-30`}
                  aria-label={`${t('clearCollection')} ${collection.name}`}
                  title={t('clearCollection')}
                >
                  <MdDeleteSweep size={16} />
                </button>
              )}
              {collection.id !== 'default' && (
                <button
                  onClick={() => setCollectionDeleteId(collection.id)}
                  className={`p-1.5 rounded-lg ${isDark ? 'text-white/25 hover:text-red-400 hover:bg-white/[0.05]' : 'text-gray-300 hover:text-red-500 hover:bg-gray-100'}`}
                  aria-label={t('delete')}
                  title={t('delete')}
                >
                  <MdDelete size={16} />
                </button>
              )}
            </div>
          ))}
          <div className={`flex items-center gap-2 rounded-xl border border-dashed px-3 py-2 ${isDark ? 'border-white/[0.08]' : 'border-gray-300'}`}>
            <input
              value={newCollectionName}
              onChange={(e) => setNewCollectionName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') addCollection(); }}
              placeholder={t('collectionName')}
              className={`min-w-0 flex-1 bg-transparent text-sm outline-none ${textValue} ${textPlaceholder}`}
            />
            <button
              onClick={addCollection}
              className="shrink-0 flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-[#006bbd]/15 text-[#006bbd] hover:bg-[#006bbd]/25"
            >
              <MdAdd size={14}/> {t('add')}
            </button>
          </div>
        </div>
      </section>

      <WatcherCard collections={collections} />
      </>)}

      {section === 'prompts' && (
        <SettingsPrompts
          isDark={isDark}
          sectionBg={sectionBg}
          textValue={textValue}
          textPlaceholder={textPlaceholder}
          borderFocus={borderFocus}
        />
      )}
      {section === 'memory' && (
      <MemoryPanel canManageSystem={canManageSystem} />
      )}

      {section === 'stats' && (
      <StatsPanel />
      )}

      {section === 'help' && (
        <section className="space-y-4">
          <div className={`rounded-2xl border p-5 ${isDark ? 'border-[#006bbd]/30 bg-[#006bbd]/[0.08]' : 'border-[#006bbd]/20 bg-[#006bbd]/[0.04]'}`}>
            <div className="flex items-center gap-3">
              <MdFavoriteBorder className="shrink-0 text-[#006bbd]" size={26} />
              <div>
                <h2 className={`text-base font-semibold ${textLabel}`}>{t('helpProjectTitle')}</h2>
                <p className={`mt-1 text-sm leading-relaxed ${textValue}`}>{t('helpProjectDescription')}</p>
              </div>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <a href={APP_CONFIG.repoUrl} target="_blank" rel="noopener noreferrer" className={`rounded-xl border p-4 transition-colors ${btnBase}`}>
              <div className="flex items-center gap-3 text-sm font-medium">
                <MdStar className="text-[#eab308]" size={20} />
                {t('helpProjectRate')}
              </div>
              <p className={`mt-2 text-xs leading-relaxed ${textHeading}`}>{t('helpProjectRateHint')}</p>
            </a>
            <a href="https://github.com/TrinaxCode" target="_blank" rel="noopener noreferrer" className={`rounded-xl border p-4 transition-colors ${btnBase}`}>
              <div className="flex items-center gap-3 text-sm font-medium">
                <FaGithub className="text-[#006bbd]" size={20} />
                {t('helpProjectSupportCreator')}
              </div>
              <p className={`mt-2 text-xs leading-relaxed ${textHeading}`}>{t('helpProjectSupportCreatorHint')}</p>
            </a>
            <button onClick={() => void shareProject()} className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-left text-sm font-medium transition-colors ${btnBase}`}>
              <MdShare className="text-[#006bbd]" size={20} />
              {t('helpProjectShare')}
            </button>
            <a href={`${APP_CONFIG.repoUrl}/issues`} target="_blank" rel="noopener noreferrer" className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-sm font-medium transition-colors ${btnBase}`}>
              <MdCode className="text-[#006bbd]" size={20} />
              {t('helpProjectContribute')}
            </a>
          </div>
          <p className={`text-center text-xs leading-relaxed ${textHeading}`}>{t('helpProjectOpenSource')}</p>
        </section>
      )}

      {section === 'general' && (
        <footer className="mt-auto pt-5 text-center">
          <a href="https://github.com/TrinaxCode" target="_blank" rel="noopener noreferrer" className={`inline-flex items-center gap-2 text-sm ${textValue} hover:text-[#006bbd] transition-colors`}>
            <FaGithub size={17} />
            <span>{t('helpProjectCreatedBy')}</span>
          </a>
        </footer>
      )}

      <ConfirmModal
        open={confirmShutdown}
        title={t('shutdownAI')}
        message={t('shutdownAIConfirm')}
        confirmLabel={t('shutdownAI')}
        danger
        onConfirm={() => { setConfirmShutdown(false); sys('shutdown'); }}
        onCancel={() => setConfirmShutdown(false)}
      />
      <ConfirmModal
        open={confirmStartup}
        title={t('startupAI')}
        message={t('startupAIConfirm')}
        confirmLabel={t('startupAI')}
        onConfirm={() => { setConfirmStartup(false); sys('startup'); }}
        onCancel={() => setConfirmStartup(false)}
      />
      <ConfirmModal
        open={confirmStopAll}
        title={t('stopAllTrinaxAIConfirmTitle')}
        message={t('stopAllTrinaxAIConfirm')}
        confirmLabel={t('stopAllTrinaxAI')}
        danger
        onConfirm={() => { setConfirmStopAll(false); void sys('stop-all'); }}
        onCancel={() => setConfirmStopAll(false)}
      />
      <ConfirmModal
        open={confirmIndex}
        title={t('indexProjects')}
        message={`${t('indexConfirmFolder').replace('{folder}', selectedFolderFiles ? folderLabelFromFiles(selectedFolderFiles) : t('indexSelectedFolderFallback')).replace('{count}', String(selectedFolderFiles?.length ?? 0))}
${selectedFolderTotal > 0 ? t('indexCompatibleFiles').replace('{count}', String(selectedFolderFiles?.length ?? 0)).replace('{total}', String(selectedFolderTotal)) : ''}

${t('indexMayTakeTime')}`}
        confirmLabel={t('onboardingStep6IndexNow')}
        onConfirm={triggerIndex}
        onCancel={() => setConfirmIndex(false)}
      />
      <ConfirmModal
        open={collectionDeleteId !== null}
        title={t('delete')}
        message={t('collectionDeleteConfirm')}
        confirmLabel={t('delete')}
        danger
        onConfirm={() => { if (collectionDeleteId) removeCollection(collectionDeleteId); }}
        onCancel={() => setCollectionDeleteId(null)}
      />
      <ConfirmModal
        open={canManageSystem && collectionClearId !== null}
        title={t('clearCollection')}
        message={t('clearCollectionConfirm').replace(
          '{collection}',
          collections.find((item) => item.id === collectionClearId)?.name || collectionClearId || '',
        )}
        confirmLabel={clearingCollectionId ? t('deleting') : t('clearCollection')}
        danger
        confirmDisabled={clearingCollectionId !== null}
        onConfirm={() => { if (collectionClearId) void clearCollection(collectionClearId); }}
        onCancel={() => setCollectionClearId(null)}
      />
      {agentPickerOpen && (
        <FolderPicker
          initialPath={agentWorkspace}
          onSelect={(path) => {
            setAgentWorkspace(path);
            try { localStorage.setItem('tc-agent-workspace', path); } catch { /* ignore */ }
            setAgentPickerOpen(false);
          }}
          onClose={() => setAgentPickerOpen(false)}
        />
      )}
    </div>
  </motion.div>);
}
