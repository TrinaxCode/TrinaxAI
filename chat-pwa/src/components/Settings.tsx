import { useRef, useState, useEffect, type KeyboardEvent } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MdAdd, MdDelete, MdDeleteSweep, MdTranslate, MdDarkMode, MdLightMode, MdBook, MdRefresh, MdStorage, MdPowerSettingsNew, MdRocketLaunch, MdStop, MdPerson, MdCheck, MdFolder, MdVolumeOff, MdVolumeUp, MdFavoriteBorder, MdStar, MdShare, MdCode, MdTune, MdSearch, MdTerminal, MdPsychology, MdInsights, MdBuild, MdWarning } from 'react-icons/md';
import { FaGithub } from 'react-icons/fa';
import type { IconType } from 'react-icons';
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

type SettingsSection = 'general' | 'web-search' | 'indexing' | 'prompts' | 'memory' | 'stats' | 'advanced' | 'help';

interface Props {
  onBack: () => void;
  onOpenDocs: () => void;
  initialSection?: SettingsSection;
  onSectionChange?: (section: SettingsSection) => void;
  canManageSystem?: boolean;
}

const formatSeconds = (seconds: number) => {
  const total = Math.max(0, Math.round(seconds));
  if (total < 60) return `${total}s`;
  return `${Math.floor(total / 60)}m ${String(total % 60).padStart(2, '0')}s`;
};

export default function Settings({ onBack, onOpenDocs, initialSection = 'general', onSectionChange, canManageSystem = false }: Props) {
  const { t, lang, setLang } = useI18n();
  const { theme, cycleTheme, isDark } = useTheme();
  const toast = useToast();
  const [section, setSection] = useState<SettingsSection>(initialSection);
  const [stopAllConfirmText, setStopAllConfirmText] = useState('');
  const stopAllConfirmWord = lang === 'es' ? 'DETENER TODO' : 'STOP ALL';
  const [soundEffects, setSoundEffects] = useState(() => audioManager.enabled());
  const [detectedProfile, setDetectedProfile] = useState<ModelPreset | null>(null);
  const changeSection = (next: SettingsSection) => {
    setSection(next);
    onSectionChange?.(next);
  };

  const settingsSections: { key: SettingsSection; label: string; Icon: IconType }[] = [
    { key: 'general', label: t('settingsGeneral'), Icon: MdTune },
    { key: 'web-search', label: t('webSearchSettingsTitle'), Icon: MdSearch },
    { key: 'indexing', label: t('settingsIndexing'), Icon: MdStorage },
    { key: 'prompts', label: t('settingsPrompts'), Icon: MdTerminal },
    { key: 'memory', label: t('settingsMemory'), Icon: MdPsychology },
    { key: 'stats', label: t('settingsStats'), Icon: MdInsights },
    { key: 'advanced', label: t('settingsAdvanced'), Icon: MdBuild },
    { key: 'help', label: t('helpProjectTitle'), Icon: MdFavoriteBorder },
  ];
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const onTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const last = settingsSections.length - 1;
    let next = index;
    if (event.key === 'ArrowRight') next = index === last ? 0 : index + 1;
    else if (event.key === 'ArrowLeft') next = index === 0 ? last : index - 1;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = last;
    else return;
    event.preventDefault();
    changeSection(settingsSections[next].key);
    tabRefs.current[next]?.focus();
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
      if (detail?.section && ['general', 'web-search', 'indexing', 'prompts', 'memory', 'stats', 'advanced', 'help'].includes(detail.section)) {
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

  // On unmount, abort any in-flight indexing poll.
  useEffect(() => {
    return () => { indexAbortRef.current?.abort(); };
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

  const retryCurrentIndex = async () => {
    if (!indexJob) return;
    setIndexing(true);
    const controller = new AbortController();
    indexAbortRef.current = controller;
    try {
      let job = await retryIndexJob(indexJob.id, controller.signal);
      setIndexJob(job);
      while (!controller.signal.aborted && !['completed', 'failed', 'cancelled'].includes(job.status)) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        job = await getIndexJob(job.id, controller.signal);
        setIndexJob(job);
      }
    } catch (err) {
      toast.toast(userFacingError(err, 'external_service_unavailable'), 'error');
    } finally {
      setIndexing(false);
      indexAbortRef.current = null;
    }
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
  // The upload counter is always exact; the indexer reports whether its own
  // percentage comes from real counters or is still only an estimate.
  const progressExact = uploadProgress > 0 ? true : Boolean(indexJob?.progress_exact ?? true);
  const etaSeconds = typeof indexJob?.eta_seconds === 'number' && indexJob.eta_seconds > 0 ? indexJob.eta_seconds : null;
  const filesProcessed = indexJob?.files_processed || indexJob?.saved || 0;
  const filesTotal = indexJob?.files_total || selectedFolderFiles?.length || indexJob?.saved || 0;
  const hasIndexFailures = Boolean(indexJob && (indexJob.skipped > 0 || indexJob.failures.length > 0 || indexJob.retry_recommended));
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
    : 'bg-red-600 border-red-600 text-white hover:bg-red-700 hover:border-red-700';
  const startupButton = isDark
    ? 'bg-green-500/10 border-green-400/30 text-green-300 hover:bg-green-500/20'
    : 'bg-emerald-700 border-emerald-700 text-white hover:bg-emerald-800 hover:border-emerald-800';

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
      <a href={APP_CONFIG.repoUrl} target="_blank" rel="noopener noreferrer" aria-label={t('githubRepoLabel')} title={t('githubRepoLabel')} className={`ml-auto grid h-8 w-8 shrink-0 place-items-center rounded-lg ${textValue} hover:text-[#006bbd] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50`}>
        <FaGithub size={16} aria-hidden="true" />
      </a>
    </div>
    <div className={`page-tabs shrink-0 flex gap-1 sm:gap-2 overflow-x-auto overscroll-x-contain border-b px-3 sm:px-5 ${isDark ? 'border-white/[0.06]' : 'border-gray-200'}`}>
      {settingsSections.map(({ key, label, Icon }, index) => (
        <button
          key={key}
          ref={(element) => { tabRefs.current[index] = element; }}
          type="button"
          onClick={() => changeSection(key)}
          onKeyDown={(event) => onTabKeyDown(event, index)}
          aria-current={section === key ? 'page' : undefined}
          className={`relative flex shrink-0 items-center gap-1.5 border-b-2 px-2 pb-2.5 pt-3 text-[11px] font-medium transition-colors whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 sm:px-2.5 sm:text-xs ${
            section === key
              ? isDark
                ? 'border-[#168de2] text-[#168de2]'
                : 'border-[#006bbd] text-[#006bbd]'
              : isDark
                ? 'border-transparent text-white/45 hover:text-white/80'
                : 'border-transparent text-gray-500 hover:text-gray-800'
          }`}
        >
          <Icon size={14} className="shrink-0" aria-hidden="true" />
          {label}
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
            <MdPerson size={18} className={isDark ? 'text-white/30' : 'text-gray-400'} aria-hidden="true" />
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
                  spellCheck={false}
                  className={`min-w-0 flex-1 bg-transparent text-sm outline-none border-b ${isDark ? 'text-white/80 border-[#006bbd]/40 placeholder-white/20' : 'text-gray-800 border-[#006bbd]/40 placeholder-gray-400'} focus:border-[#006bbd] px-1 py-0.5`}
                />
                <button
                  onClick={saveNickname}
                  className={`p-1.5 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${isDark ? 'text-[#006bbd] hover:bg-white/[0.06]' : 'text-[#006bbd] hover:bg-gray-100'}`}
                  title={t('save')}
                  aria-label={t('save')}
                >
                  <MdCheck size={18} aria-hidden="true" />
                </button>
              </>
            ) : (
              <>
                <span className={`min-w-0 flex-1 text-sm ${isDark ? 'text-white/70' : 'text-gray-700'}`}>
                  {nickname.trim() || t('userLabel')}
                </span>
                <button
                  onClick={() => setNicknameEditing(true)}
                  className={`px-2 py-1 rounded-lg text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${
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
            type="button"
            onClick={() => setLang(lang === 'es' ? 'en' : 'es')}
            className={`min-w-0 flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl border text-sm font-medium text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${
              isDark
                ? 'bg-white/[0.03] border-white/[0.06] text-white/70 hover:bg-white/[0.06]'
                : 'bg-gray-50 border-gray-200 text-gray-700 hover:bg-gray-100'
            }`}
          >
            <MdTranslate size={18} aria-hidden="true" />
            {lang === 'es' ? t('languageSpanish') : t('languageEnglish')}
          </button>

          {/* Theme toggle */}
          <button
            type="button"
            onClick={cycleTheme}
            className={`min-w-0 flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl border text-sm font-medium text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${
              isDark
                ? 'bg-white/[0.03] border-white/[0.06] text-white/70 hover:bg-white/[0.06]'
                : 'bg-gray-50 border-gray-200 text-gray-700 hover:bg-gray-100'
            }`}
            title={t('toggleTheme')}
          >
            {isDark ? <MdDarkMode size={18} aria-hidden="true" /> : <MdLightMode size={18} aria-hidden="true" />}
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
          className={`${bgCard} flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${isDark ? 'hover:bg-white/[0.05]' : 'hover:bg-gray-100'}`}
        >
          {soundEffects ? <MdVolumeUp size={20} className="text-[#006bbd]" aria-hidden="true" /> : <MdVolumeOff size={20} className={textHeading} aria-hidden="true" />}
          <span className="min-w-0 flex-1">
            <span className={`block text-sm font-medium ${isDark ? 'text-white/75' : 'text-gray-700'}`}>{t('soundEffects')}</span>
            <span className={`block text-[11px] ${textHeading}`}>{t('soundEffectsHint')}</span>
          </span>
          <span className={`h-6 w-11 rounded-full p-0.5 transition-colors ${soundEffects ? 'bg-[#006bbd]' : isDark ? 'bg-white/15' : 'bg-gray-300'}`}>
            <span className={`block h-5 w-5 rounded-full bg-white transition-transform ${soundEffects ? 'translate-x-5' : ''}`} />
          </span>
        </button>
      </section>

      {/* ── Docs Link ── */}
      <section>
        <button type="button" onClick={onOpenDocs}
          className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl border text-sm font-medium transition-[background-color,color,border-color,transform] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${btnBase} active:scale-95`}>
          <MdBook size={16} aria-hidden="true" />
          {t('viewDocs')}
        </button>
      </section>

      </>)}

      {section === 'advanced' && (<>
      <section className={`${bgCard} rounded-2xl border px-4 py-4`}>
        <div className="flex items-start gap-3">
          <MdBuild className="mt-0.5 shrink-0 text-[#006bbd]" size={20} aria-hidden="true" />
          <div>
            <h2 className={`text-base font-semibold ${textLabel}`}>{t('settingsAdvanced')}</h2>
            <p className={`mt-1 text-xs leading-relaxed ${textHeading}`}>{t('settingsAdvancedDescription')}</p>
          </div>
        </div>
      </section>

      {!canManageSystem && <div role="note" className={`${bgCard} rounded-xl border px-4 py-3 text-xs leading-relaxed ${textHeading}`}>
        {t('deviceSystemScopeHint')}
      </div>}

      {/* ── System Section ── */}
      <section>
        <h3 className={`mb-3 text-xs font-medium uppercase tracking-widest ${textHeading}`}>{t('system')}</h3>
        <DevicePairingCard isDark={isDark} canManageSystem={canManageSystem} />
        {canManageSystem && <div className={`${bgCard} mb-3 space-y-1.5 rounded-xl border px-4 py-3`}>
          <label className={`text-[10px] uppercase tracking-wider ${textHeading}`}>{t('agentSettingsTitle')} | {t('agentWorkspaceRootLabel')}</label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={agentWorkspace}
              spellCheck={false}
              onChange={(event) => setAgentWorkspace(event.target.value)}
              onBlur={(event) => { try { localStorage.setItem('tc-agent-workspace', event.target.value.trim()); } catch { /* ignore */ } }}
              placeholder={t('agentWorkspacePlaceholder')}
              aria-label={`${t('agentSettingsTitle')} | ${t('agentWorkspaceRootLabel')}`}
              name="agent-workspace"
              autoComplete="off"
              className={`min-w-0 flex-1 rounded-lg border bg-transparent px-3 py-2 font-mono text-xs outline-none focus:border-[#006bbd] ${isDark ? 'border-white/[0.08] text-white/80 placeholder-white/25' : 'border-gray-200 text-gray-800 placeholder-gray-400'}`}
            />
            <button type="button" onClick={() => setAgentPickerOpen(true)} className={`flex shrink-0 items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${isDark ? 'border-white/[0.08] text-white/70 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-600 hover:bg-gray-100'}`}>
              <MdFolder size={14} className="text-[#006bbd]" aria-hidden="true" /> {t('agentPickFolder')}
            </button>
          </div>
          <p className={`text-[10px] ${textHeading}`}>{t('agentWorkspaceRootHint')}</p>
        </div>}
        {canManageSystem && <div className="flex flex-col gap-3 sm:flex-row">
          <button type="button" onClick={() => setConfirmShutdown(true)} disabled={sd} className={`min-w-0 flex-1 flex items-center justify-center gap-1.5 px-4 py-3 rounded-xl border text-sm font-medium text-center disabled:opacity-50 active:scale-95 transition-[background-color,border-color,opacity,transform] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${dangerButton}`}><MdPowerSettingsNew className="shrink-0" size={16} aria-hidden="true" /><span className="min-w-0 break-words">{sd?t('shuttingDown'):t('shutdownAI')}</span></button>
          <button type="button" onClick={() => setConfirmStartup(true)} disabled={su} className={`min-w-0 flex-1 flex items-center justify-center gap-1.5 px-4 py-3 rounded-xl border text-sm font-medium text-center disabled:opacity-50 active:scale-95 transition-[background-color,border-color,opacity,transform] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${startupButton}`}><MdRocketLaunch className="shrink-0" size={16} aria-hidden="true" /><span className="min-w-0 break-words">{su?t('startingUp'):t('startupAI')}</span></button>
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

      {/* ── Restore Config (Danger Zone) ── */}
      {canManageSystem && <section className="relative pb-8">
        <div className={`rounded-xl border p-4 ${isDark ? 'border-red-400/20 bg-red-500/[0.04]' : 'border-red-200 bg-red-50/70'}`}>
          <div className="flex items-start gap-3">
            <MdWarning className="mt-0.5 shrink-0 text-amber-500" size={18} aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <h3 className={`text-xs font-medium uppercase tracking-widest ${textHeading}`}>{t('dangerZone')}</h3>
              <p className={`mt-1 text-[11px] leading-relaxed ${textHeading}`}>{t('dangerZoneHint')}</p>
            </div>
          </div>
        </div>
        <div className="mt-3">
        <AnimatePresence mode="popLayout" initial={false}>
        {!showRestore ? (
          <motion.button
            key="restore-trigger"
            type="button"
            onClick={() => setShowRestore(true)}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl border text-sm font-medium transition-[background-color,transform] active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${dangerButton}`}>
            <MdRefresh size={16} aria-hidden="true" />
            {t('restoreConfig')}
          </motion.button>
        ) : (
          <motion.div
            key="restore-confirm"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
          <div className="space-y-3 rounded-xl border border-red-500/20 bg-red-500/5 p-4">
            <p className="text-xs text-red-400/80">{t('restoreConfigConfirm')}</p>
            <input
              type="text"
              name="restore-confirm"
              aria-label={t('restoreConfigWarning')}
              value={restoreConfirm}
              onChange={(e) => setRestoreConfirm(e.target.value)}
              placeholder={t('restoreConfigWarning')}
              autoComplete="off"
              spellCheck={false}
              className={`w-full rounded-lg border border-red-500/20 bg-transparent px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-red-500/50 ${isDark ? 'text-white placeholder-white/20' : 'text-gray-900 placeholder-gray-400'}`}
            />
            <div className="flex gap-2">
              <button type="button" onClick={() => { setShowRestore(false); setRestoreConfirm(''); }}
                className={`flex-1 rounded-lg py-2 text-xs font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${btnBase}`}>
                {t('cancel')}
              </button>
              <button type="button" onClick={doRestore}
                disabled={restoreConfirm !== 'RESTAURAR' && restoreConfirm !== 'RESTORE'}
                className={`flex-1 rounded-lg py-2 text-xs font-medium transition-[background-color,opacity] disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${dangerButton}`}>
                {t('restoreConfig')}
              </button>
            </div>
          </div>
          </motion.div>
        )}
        </AnimatePresence>
        <button type="button" onClick={() => { setStopAllConfirmText(''); setConfirmStopAll(true); }}
          disabled={stoppingAll}
          className={`mt-3 w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl border text-sm font-medium transition-[background-color,transform] active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${dangerButton}`}>
          <MdPowerSettingsNew size={16} aria-hidden="true" />
          {stoppingAll ? t('shuttingDown') : t('stopAllTrinaxAI')}
        </button>
        </div>
      </section>}
      </>)}

      {section === 'web-search' && <WebSearchSettings canManageSystem={canManageSystem} onBack={() => changeSection('general')} />}

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
            style={{ colorScheme: isDark ? 'dark' : 'light' }}
            className={`min-w-0 flex-1 bg-transparent text-sm outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${inputText}`}
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
            className={`min-w-0 flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl border text-sm font-medium text-center transition-[background-color,color,border-color,opacity,transform] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${btnBase} disabled:opacity-50 active:scale-95`}>
            <MdStorage className="shrink-0" size={16} aria-hidden="true" />
            <span className="min-w-0 break-words">
              {indexing ? t('indexing') : lastIndexedLabel ? t('indexFolderSelected').replace('{folder}', lastIndexedLabel).replace('{count}', '-') : t('chooseFolderIndex')}
            </span>
          </button>
          {indexing && (
            <button
              onClick={cancelIndex}
              className="flex min-h-12 flex-1 items-center justify-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm font-semibold text-red-400 shadow-sm transition-[background-color,border-color,transform] hover:border-red-500/50 hover:bg-red-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400/60 active:scale-[.98] sm:flex-none"
              aria-label={t('indexCancel')}
              title={t('indexCancel')}
            >
              <MdStop size={16} aria-hidden="true" />
              <span>{t('indexCancel')}</span>
            </button>
          )}
        </div>
        <p className={`mt-2 text-[11px] ${textHeading}`}>{t('indexFolderBrowserHint')}</p>
        {(indexing || indexJob) && (
          <div className={`tc-index-card mt-3 space-y-2`}>
            {indexing ? (
              <>
                <div className="flex items-center justify-between gap-3">
                  <span className={`text-xs font-medium ${textLabel}`}>{phaseLabel(indexJob?.phase || (uploadProgress > 0 ? 'saving' : 'queued'))}</span>
                  <span className="flex items-baseline gap-1.5">
                    <span className={`text-xs font-semibold tabular-nums ${textLabel}`}>{progress}%</span>
                    {!progressExact && <span className={`text-[10px] uppercase tracking-wide ${textHeading}`}>{t('indexApprox')}</span>}
                  </span>
                </div>
                <div
                  className="tc-index-track"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={progress}
                  aria-valuetext={`${progress}%${progressExact ? '' : ` ${t('indexApprox')}`}`}
                  aria-label={phaseLabel(indexJob?.phase || 'indexing')}
                >
                  <div
                    className={`tc-index-fill${progressExact ? '' : ' tc-index-fill--live'}`}
                    style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
                  />
                </div>
                <div className="flex flex-wrap items-center gap-2 text-[11px]">
                  <span className="tc-index-metric tabular-nums">{t('indexElapsed')}: <strong className={textLabel}>{formatSeconds(indexJob?.elapsed_seconds ?? 0)}</strong></span>
                  {etaSeconds !== null && <span className="tc-index-metric tabular-nums">{t('indexEta')}: <strong className={textLabel}>~{formatSeconds(etaSeconds)}</strong></span>}
                  <span className="tc-index-metric tabular-nums">{t('indexFiles')}: <strong className={textLabel}>{filesProcessed} / {filesTotal}</strong></span>
                  {!!indexJob?.pages_total && <span className="tc-index-metric tabular-nums">{t('indexPages')}: <strong className={textLabel}>{indexJob.pages_processed}/{indexJob.pages_total}</strong></span>}
                  {!!indexJob?.chunks_generated && <span className="tc-index-metric tabular-nums">{t('indexChunks')}: <strong className={textLabel}>{indexJob.chunks_generated}</strong></span>}
                  {!!indexJob?.skipped && <span className="tc-index-metric tabular-nums">{t('indexSkipped')}: <strong className={textLabel}>{indexJob.skipped}</strong></span>}
                </div>
                {!!indexJob?.recent_activity && (
                  <p className={`tc-index-metric text-[11px] ${textHeading}`}>{t('indexRecentActivity')}: {indexJob.recent_activity}</p>
                )}
              </>
            ) : indexJob?.status === 'completed' ? (
              <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm min-w-0">
                  <MdCheck className="text-green-400 text-base shrink-0" aria-hidden="true" />
                  <span className={`font-medium ${textLabel} truncate`}>{t('indexComplete')}</span>
                  <span className={`${textHeading} shrink-0`}>({indexJob.saved} {t('indexFiles').toLowerCase()})</span>
                </div>
                <button
                  onClick={() => folderInputRef.current?.click()}
                  className="shrink-0 flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-[#006bbd]/15 text-[#006bbd] hover:bg-[#006bbd]/25 active:scale-95 transition-[background-color,transform] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50"
                  title={t('chooseFolderIndex')}
                  aria-label={t('indexAgain')}
                >
                  <MdRefresh size={14} aria-hidden="true" />
                  <span className="hidden sm:inline">{t('indexAgain')}</span>
                </button>
              </div>
              {hasIndexFailures && (
                <div role="alert" className="flex flex-wrap items-center gap-2 text-xs text-amber-400">
                  <span>{indexJob.skipped || indexJob.failures.length ? t('indexPartialWarning').replace('{count}', String(indexJob.skipped || indexJob.failures.length)) : t('indexNeedsAttention')}</span>
                  <button type="button" onClick={retryCurrentIndex} className="rounded-lg bg-amber-400/15 px-3 py-1.5 font-semibold text-amber-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60">{t('retry')}</button>
                </div>
              )}
              {indexJob.failures.slice(0, 3).map((failure) => <p key={`${failure.path}:${failure.reason}`} className={`text-[11px] ${textHeading}`}>{failure.path}: {failure.reason}</p>)}
              </div>
            ) : indexJob?.status === 'failed' ? (
              <div className="flex items-center justify-between gap-3 text-sm text-red-400">
                <span><strong>{phaseLabel(indexJob.phase)}</strong>: {indexJob.error || t('indexFailed')}</span>
                <button type="button" className="shrink-0 rounded-lg bg-[#006bbd]/15 px-3 py-1.5 text-xs text-[#4ea3e0] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50" onClick={retryCurrentIndex}>{t('retry')}</button>
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
                name={`collection-name-${collection.id}`}
                aria-label={t('collectionName')}
                autoComplete="off"
                spellCheck={false}
                onBlur={(e) => updateCollectionName(collection.id, collection.name, e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') (e.target as HTMLInputElement).blur();
                }}
                className={`min-w-0 flex-1 rounded-md bg-transparent text-sm outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 disabled:opacity-60 ${inputText}`}
              />
              {canManageSystem && (
                <button
                  onClick={() => setCollectionClearId(collection.id)}
                  disabled={clearingCollectionId === collection.id}
                  className={`p-1.5 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${isDark ? 'text-white/25 hover:text-amber-400 hover:bg-white/[0.05]' : 'text-gray-300 hover:text-amber-600 hover:bg-gray-100'} disabled:opacity-30`}
                  aria-label={`${t('clearCollection')} ${collection.name}`}
                  title={t('clearCollection')}
                >
                  <MdDeleteSweep size={16} aria-hidden="true" />
                </button>
              )}
              {collection.id !== 'default' && (
                <button
                  onClick={() => setCollectionDeleteId(collection.id)}
                  className={`p-1.5 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${isDark ? 'text-white/25 hover:text-red-400 hover:bg-white/[0.05]' : 'text-gray-300 hover:text-red-500 hover:bg-gray-100'}`}
                  aria-label={t('delete')}
                  title={t('delete')}
                >
                  <MdDelete size={16} aria-hidden="true" />
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
              aria-label={t('collectionName')}
              name="new-collection-name"
              autoComplete="off"
              spellCheck={false}
              className={`min-w-0 flex-1 rounded-md bg-transparent text-sm outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${textValue} ${textPlaceholder}`}
            />
            <button
              onClick={addCollection}
              className="shrink-0 flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-[#006bbd]/15 text-[#006bbd] hover:bg-[#006bbd]/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50"
            >
              <MdAdd size={14} aria-hidden="true"/> {t('add')}
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
            <a href={APP_CONFIG.repoUrl} target="_blank" rel="noopener noreferrer" className={`rounded-xl border p-4 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 sm:col-span-2 ${btnBase}`}>
              <div className="flex items-center gap-3 text-sm font-medium">
                <MdStar className="shrink-0 text-[#eab308]" size={20} aria-hidden="true" />
                {t('helpProjectRate')}
              </div>
              <p className={`mt-2 text-xs leading-relaxed ${textHeading}`}>{t('helpProjectRateHint')}</p>
            </a>
            <button type="button" onClick={() => void shareProject()} className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-left text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${btnBase}`}>
              <MdShare className="shrink-0 text-[#006bbd]" size={20} aria-hidden="true" />
              {t('helpProjectShare')}
            </button>
            <a href={`${APP_CONFIG.repoUrl}/issues`} target="_blank" rel="noopener noreferrer" className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#006bbd]/50 ${btnBase}`}>
              <MdCode className="shrink-0 text-[#006bbd]" size={20} aria-hidden="true" />
              {t('helpProjectContribute')}
            </a>
          </div>
          <p className={`text-center text-xs leading-relaxed ${textHeading}`}>{t('helpProjectOpenSource')}</p>
        </section>
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
        confirmDisabled={stopAllConfirmText.trim().toUpperCase() !== stopAllConfirmWord}
        danger
        onConfirm={() => { setConfirmStopAll(false); setStopAllConfirmText(''); void sys('stop-all'); }}
        onCancel={() => { setConfirmStopAll(false); setStopAllConfirmText(''); }}
      >
        <label className={`block text-xs ${isDark ? 'text-white/65' : 'text-gray-600'}`}>
          {t('stopAllConfirmWarning')}
          <input
            type="text"
            name="stop-all-confirm"
            value={stopAllConfirmText}
            onChange={(event) => setStopAllConfirmText(event.target.value)}
            placeholder={stopAllConfirmWord}
            autoComplete="off"
            spellCheck={false}
            className={`mt-2 w-full rounded-lg border bg-transparent px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-red-500/50 ${isDark ? 'border-red-500/25 text-white placeholder-white/25' : 'border-red-200 text-gray-900 placeholder-gray-400'}`}
          />
        </label>
      </ConfirmModal>
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
