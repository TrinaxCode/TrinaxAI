import { useRef, useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import { MdArrowBack, MdAdd, MdDelete, MdTranslate, MdDarkMode, MdLightMode, MdBook, MdRefresh, MdStorage, MdWarning, MdPowerSettingsNew, MdRocketLaunch, MdStop, MdVisibility, MdMemory, MdBarChart, MdAutoFixHigh, MdBookOnline, MdFlashOn, MdPerson, MdCheck } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { useToast } from './Toast';
import ConfirmModal from './ConfirmModal';
import StatusDots from './StatusDots';
import WatcherCard from './WatcherCard';
import MemoryPanel from './MemoryPanel';
import StatsPanel from './StatsPanel';
import RecentIndexes from './RecentIndexes';
import { DEFAULT_MODEL_SETTINGS, MODEL_KEYS, MODEL_PRESETS, OLLAMA_KEEP_ALIVE_DEFAULT, cancelIndexJob, createCollection, deleteCollection, folderLabelFromFiles, getCollections, getIndexJob, indexableFilesFrom, modelSetting, renameCollection, resetSharedAppState, startFolderIndex, type Collection, type IndexJobStatus, type ModelPreset } from '../lib/api';
import { APP_CONFIG } from '../lib/config';
import { syncSharedStateOnce } from '../lib/sharedState';
import { NICKNAME_KEY, isValidProfileName } from '../lib/userProfile';

type SettingsSection = 'general' | 'indexing' | 'prompts' | 'memory' | 'stats';

interface Props {
  onBack: () => void;
  initialSection?: SettingsSection;
}
interface CustomPrompt { name: string; text: string; }

const PROMPTS_KEY = 'tc-prompts';
const LEGACY_PROMPT_KEYS = ['tc-ollama-prompts', 'tc-rag-prompts'];

const DEF_OLLAMA_ES = 'Eres TrinaxAI, asistente de IA local-first y open-source. Fuiste creado por TrinaxCode — Full Stack Developer de Tuxtla Gutiérrez, Chiapas (originario de Nicaragua), enfocado en React, TypeScript, Python, Django, PostgreSQL y Firebase. GitHub: https://github.com/TrinaxCode. LinkedIn: https://linkedin.com/in/trinaxcode. Si el usuario pregunta quién te creó, habla de TrinaxCode y comparte los links. Responde claro, útil y sin inventar datos.';
const DEF_OLLAMA_EN = 'You are TrinaxAI, a local-first open-source AI assistant. You were created by TrinaxCode — a Full Stack Developer from Tuxtla Gutiérrez, Chiapas (originally from Nicaragua), focused on React, TypeScript, Python, Django, PostgreSQL, and Firebase. GitHub: https://github.com/TrinaxCode. LinkedIn: https://linkedin.com/in/trinaxcode. If the user asks who created you, talk about TrinaxCode and share the links. Be clear, useful, and do not invent facts.';
const DEF_SHARED_ES = `${DEF_OLLAMA_ES} Si hay contexto indexado, úsalo cuando sea relevante y distingue claramente entre datos encontrados y explicaciones generales.`;
const DEF_SHARED_EN = `${DEF_OLLAMA_EN} When indexed context is available, use it when relevant and clearly distinguish found facts from general explanations.`;

function loadPrompts(lang: 'es' | 'en'): CustomPrompt[] {
  try {
    const current = JSON.parse(localStorage.getItem(PROMPTS_KEY) || 'null');
    if (Array.isArray(current) && current.length) return current;
    const legacy = LEGACY_PROMPT_KEYS.flatMap((key) => {
      try {
        const value = JSON.parse(localStorage.getItem(key) || '[]');
        return Array.isArray(value) ? value : [];
      } catch { return []; }
    });
    const unique = new Map<string, CustomPrompt>();
    legacy.forEach((prompt) => {
      if (prompt?.name && prompt.name !== 'system') unique.set(String(prompt.name), { name: String(prompt.name), text: String(prompt.text || '') });
    });
    const system = legacy.find((prompt) => prompt?.name === 'system') || {
      name: 'system',
      text: lang === 'en' ? DEF_SHARED_EN : DEF_SHARED_ES,
    };
    return [{ name: 'system', text: String(system.text || '') }, ...unique.values()];
  } catch {
    return [{ name: 'system', text: lang === 'en' ? DEF_SHARED_EN : DEF_SHARED_ES }];
  }
}

export default function Settings({ onBack, initialSection = 'general' }: Props) {
  const { t, lang, setLang } = useI18n();
  const { theme, cycleTheme, isDark } = useTheme();
  const toast = useToast();
  const [section, setSection] = useState<SettingsSection>(initialSection);

  useEffect(() => {
    setSection(initialSection);
  }, [initialSection]);

  // Allow external callers (e.g. /memory slash command) to jump to a specific section.
  useEffect(() => {
    const onJump = (e: Event) => {
      const detail = (e as CustomEvent).detail as { section?: string } | undefined;
      if (detail?.section && ['general', 'indexing', 'prompts', 'memory', 'stats'].includes(detail.section)) {
        setSection(detail.section as typeof section);
      }
    };
    window.addEventListener('tc-open-section', onJump as EventListener);
    return () => window.removeEventListener('tc-open-section', onJump as EventListener);
  }, []);

  useEffect(() => {
    const onMem = () => setSection('memory');
    window.addEventListener('tc-open-memory-tab', onMem);
    return () => window.removeEventListener('tc-open-memory-tab', onMem);
  }, []);
  const [sd, setSd] = useState(false); const [su, setSu] = useState(false);
  const [nickname, setNicknameValue] = useState(() => localStorage.getItem(NICKNAME_KEY) || '');
  const [nicknameEditing, setNicknameEditing] = useState(false);
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
  const [prompts, setPrompts] = useState<CustomPrompt[]>(() => loadPrompts(lang));
  const [nn, setNn] = useState(''); const [nt, setNt] = useState('');
  useEffect(() => {
    localStorage.setItem(PROMPTS_KEY, JSON.stringify(prompts));
    const id = window.setTimeout(() => { void syncSharedStateOnce(1200); }, 450);
    return () => window.clearTimeout(id);
  }, [prompts]);

  const [indexing, setIndexing] = useState(false);
  const [restoreConfirm, setRestoreConfirm] = useState('');
  const [showRestore, setShowRestore] = useState(false);
  const [modelsExpanded, setModelsExpanded] = useState(false);
  const [confirmShutdown, setConfirmShutdown] = useState(false);
  const [confirmStartup, setConfirmStartup] = useState(false);
  const [confirmStopAll, setConfirmStopAll] = useState(false);
  const [stoppingAll, setStoppingAll] = useState(false);
  const [confirmIndex, setConfirmIndex] = useState(false);
  const [collectionDeleteId, setCollectionDeleteId] = useState<string | null>(null);
  const [promptDeleteName, setPromptDeleteName] = useState<string | null>(null);
  const [selectedFolderFiles, setSelectedFolderFiles] = useState<File[] | null>(null);
  const [selectedFolderTotal, setSelectedFolderTotal] = useState(0);
  const [indexJob, setIndexJob] = useState<IndexJobStatus | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [newCollectionName, setNewCollectionName] = useState('');
  const [indexCollectionId, setIndexCollectionId] = useState(() => localStorage.getItem('tc-index-collection') || 'default');
  const [lastIndexedLabel, setLastIndexedLabel] = useState('');
  const folderInputRef = useRef<HTMLInputElement>(null);
  const indexAbortRef = useRef<AbortController | null>(null);
  const clearJobTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [, refreshLocalSettings] = useState(0);

  const setLocalSetting = (key: string, value: string) => {
    localStorage.setItem(key, value);
    refreshLocalSettings((rev) => rev + 1);
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

  const add = () => {
    const n = nn.trim().toLowerCase().replace(/\s+/g,'-'); if (!n||!nt.trim()) return;
    if (prompts.some(p=>p.name===n)) { toast.toast(t('promptExists'), 'warning'); return; }
    setPrompts([...prompts,{name:n,text:nt.trim()}]); setNn(''); setNt('');
    toast.toast(t('promptAdded'), 'success');
  };
  const upd = (name:string, f:'name'|'text', v:string) => setPrompts(items=>items.map((item)=>item.name===name?{...item,[f]:v}:item));
  const del = (name:string) => {
    if (name === 'system') return;
    setPrompts(items=>items.filter((item)=>item.name!==name));
    setPromptDeleteName(null);
    toast.toast(t('promptDeleted'), 'info');
  };
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
      toast.toast(err instanceof Error ? err.message.slice(0, 180) : t('collectionError'), 'error');
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
      toast.toast(err instanceof Error ? err.message.slice(0, 180) : t('collectionError'), 'error');
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
      toast.toast(err instanceof Error ? err.message.slice(0, 180) : t('collectionError'), 'error');
    }
  };
  const sys = async (a:'shutdown'|'startup'|'stop-all') => {
    const s = a === 'shutdown' ? setSd : a === 'startup' ? setSu : setStoppingAll; s(true);
    try { const r=await fetch(`/api/system/${a}`,{method:'POST'}); const d=await r.json();
      toast.toast(d.ok?t('executedOk'):`${d.error||d.output}`, d.ok?'success':'error'); }
    catch { toast.toast(t('noConnection'), 'error'); } finally { s(false); }
  };

  const triggerIndex = async () => {
    setIndexing(true); setConfirmIndex(false);
    setUploadProgress(0);
    setIndexJob(null);
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
          toast.toast(t('indexCancelled'), 'info');
          done = true;
        } else if (job.status === 'failed') {
          toast.toast(job.error || t('indexFailed'), 'error');
          done = true;
        } else {
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }
      }
      if (controller.signal.aborted) {
        toast.toast(t('indexCancelled'), 'info');
        setSelectedFolderFiles(null);
        setSelectedFolderTotal(0);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        toast.toast(t('indexCancelled'), 'info');
      } else {
        const detail = err instanceof Error ? err.message : '';
        const friendly = detail
          ? `${t('indexBackendError')} ${detail.replace(/\s+/g, ' ').slice(0, 220)}`
          : t('indexBackendOffline');
        toast.toast(friendly, 'error');
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
    const current = indexJob;
    indexAbortRef.current?.abort();
    if (current?.id) {
      const cancelled = await cancelIndexJob(current.id).catch(() => null);
      if (cancelled) setIndexJob(cancelled);
    }
    setIndexing(false);
    toast.toast(t('indexCancelled'), 'info');
  };

  const doRestore = async () => {
    if (restoreConfirm !== 'RESTAURAR' && restoreConfirm !== 'RESTORE') return;
    // Wipe local first so the push propagates a clean slate to the backend.
    const resetAt = String(Date.now() / 1000);
    try { sessionStorage.setItem('trinaxai-resetting', '1'); } catch { /* ignore */ }
    const keys = Object.keys(localStorage).filter(k => k.startsWith('tc-'));
    keys.forEach(k => localStorage.removeItem(k));
    localStorage.setItem('tc-reset-at', resetAt);
    await resetSharedAppState().catch(() => undefined);
    await syncSharedStateOnce(1800).catch(() => undefined);
    window.location.reload();
  };

  const setModelPreset = (preset: ModelPreset) => {
    const values = MODEL_PRESETS[preset];
    Object.entries(values).forEach(([k, v]) => setLocalSetting(k, v));
    toast.toast(t('modelPresetApplied'), 'success');
  };

  const getModel = (key: keyof typeof DEFAULT_MODEL_SETTINGS) => modelSetting(key, DEFAULT_MODEL_SETTINGS[key]);
  const getKeepAlive = () => localStorage.getItem('tc-keep-alive') || OLLAMA_KEEP_ALIVE_DEFAULT;
  const progress = Math.max(uploadProgress, indexJob?.progress ?? 0);
  const formatEta = (seconds: number | null | undefined) => {
    if (!seconds) return t('indexEtaCalculating');
    const min = Math.floor(seconds / 60);
    const sec = seconds % 60;
    return min > 0 ? `${min}m ${sec}s` : `${sec}s`;
  };
  const phaseLabel = (phase: string | undefined) => t(({
    saving: 'indexPhaseSaving',
    queued: 'indexPhaseQueued',
    starting: 'indexPhaseStarting',
    indexing: 'indexPhaseIndexing',
    chunking: 'indexPhaseChunking',
    embedding: 'indexPhaseEmbedding',
    saving_index: 'indexPhaseSavingIndex',
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

  const bgCard = isDark ? 'bg-white/[0.03] border-white/[0.06]' : 'bg-gray-50 border-gray-200';
  const textHeading = isDark ? 'text-white/40' : 'text-gray-500';
  const textLabel = isDark ? 'text-white/80' : 'text-gray-800';
  const textPlaceholder = isDark ? 'placeholder-white/20' : 'placeholder-gray-400';
  const textValue = isDark ? 'text-white/70' : 'text-gray-700';
  const inputText = isDark ? 'text-white/70' : 'text-gray-700';
  const borderFocus = 'focus:border-[#006bbd]/40';
  const sectionBg = isDark ? 'bg-white/[0.03] border-white/[0.06]' : 'bg-gray-50 border-gray-200';

  return (<motion.div className={`h-full flex flex-col min-w-0 max-w-full overflow-x-hidden ${isDark ? 'bg-black' : 'bg-white'}`} initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}>
    <div className={`shrink-0 flex items-center gap-3 px-4 pt-[env(safe-area-inset-top,0px)] pb-3 border-b ${isDark ? 'border-white/[0.06]' : 'border-gray-200'}`}>
      <button onClick={onBack} className={`p-2 -ml-2 ${isDark ? 'text-white/60 hover:text-white' : 'text-gray-500 hover:text-gray-800'}`}><MdArrowBack size={20}/></button>
      <span className={`text-sm font-medium ${textLabel}`}>{t('settingsTitle')}</span>
    </div>
    <div className={`shrink-0 flex gap-0.5 sm:gap-1 px-1 sm:px-2 pt-2 pb-1 border-b ${isDark ? 'border-white/[0.04]' : 'border-gray-100'} overflow-x-auto overscroll-x-contain`}>
      {([
        ['general', t('settingsGeneral')],
        ['indexing', t('settingsIndexing')],
        ['prompts', t('settingsPrompts')],
        ['memory', t('settingsMemory')],
        ['stats', t('settingsStats')],
      ] as const).map(([k, lbl]) => (
        <button
          key={k}
          onClick={() => setSection(k)}
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
    <div className="flex-1 overflow-y-auto px-4 pt-6 pb-[calc(env(safe-area-inset-bottom,0px)+24px)] space-y-6">

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
                  className={`min-w-0 flex-1 bg-transparent text-sm outline-none border-b ${isDark ? 'text-white/80 border-[#006bbd]/40 placeholder-white/20' : 'text-gray-800 border-[#006bbd]/40 placeholder-gray-400'} focus:border-[#006bbd] px-1 py-0.5`}
                  autoFocus
                />
                <button
                  onClick={saveNickname}
                  className={`p-1.5 rounded-lg ${isDark ? 'text-[#006bbd] hover:bg-white/[0.06]' : 'text-[#006bbd] hover:bg-gray-100'}`}
                  title={t('save')}
                >
                  <MdCheck size={18} />
                </button>
              </>
            ) : (
              <>
                <span className={`min-w-0 flex-1 text-sm ${isDark ? 'text-white/70' : 'text-gray-700'}`}>
                  {nickname.trim() || (lang === 'en' ? 'User' : 'Usuario')}
                </span>
                <button
                  onClick={() => setNicknameEditing(true)}
                  className={`px-2 py-1 rounded-lg text-xs font-medium transition-colors ${
                    isDark ? 'text-white/40 hover:text-white/70 hover:bg-white/[0.06]' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  {t('edit')}
                </button>
              </>
            )}
          </div>
          <p className={`text-[10px] leading-relaxed ${isDark ? 'text-white/25' : 'text-gray-400'}`}>
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
            {lang === 'es' ? 'Español' : 'English'}
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

      {/* ── System Section ── */}
      <section>
        <h3 className={`text-xs font-medium uppercase tracking-widest mb-3 ${textHeading}`}>{t('system')}</h3>
        <div className="flex flex-col sm:flex-row gap-3">
          <button onClick={() => setConfirmShutdown(true)} disabled={sd} className="min-w-0 flex-1 flex items-center justify-center gap-1.5 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm font-medium text-center hover:bg-red-500/20 disabled:opacity-50 active:scale-95 transition-all"><MdPowerSettingsNew className="shrink-0" size={16} /><span className="min-w-0 break-words">{sd?t('shuttingDown'):t('shutdownAI')}</span></button>
          <button onClick={() => setConfirmStartup(true)} disabled={su} className="min-w-0 flex-1 flex items-center justify-center gap-1.5 px-4 py-3 rounded-xl bg-green-500/10 border border-green-500/20 text-green-400 text-sm font-medium text-center hover:bg-green-500/20 disabled:opacity-50 active:scale-95 transition-all"><MdRocketLaunch className="shrink-0" size={16} /><span className="min-w-0 break-words">{su?t('startingUp'):t('startupAI')}</span></button>
        </div>
      </section>

      {/* ── Models Section (Advanced, collapsed) ── */}
      <section className="min-w-0 max-w-full overflow-hidden">
        <button onClick={() => setModelsExpanded(v => !v)}
          className={`w-full flex items-center justify-between text-xs font-medium uppercase tracking-widest mb-3 ${textHeading} hover:opacity-80`}>
          <span>{t('modelCustomize')}</span>
          <span className="text-[10px]">{modelsExpanded ? '▾' : '▸'}</span>
        </button>
        {modelsExpanded && (
          <div className="space-y-2 min-w-0 max-w-full">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <button onClick={() => setModelPreset('low')} className={`min-w-0 px-2 py-2 rounded-lg text-[11px] font-medium break-words ${btnBase}`}>{t('modelPresetLow')}</button>
              <button onClick={() => setModelPreset('balanced')} className={`min-w-0 px-2 py-2 rounded-lg text-[11px] font-medium break-words ${btnBase}`}>{t('modelPresetBalanced')}</button>
              <button onClick={() => setModelPreset('max')} className={`min-w-0 px-2 py-2 rounded-lg text-[11px] font-medium break-words ${btnBase}`}>{t('modelPresetMax')}</button>
              <button onClick={() => setModelPreset('ultra')} className={`min-w-0 px-2 py-2 rounded-lg text-[11px] font-medium break-words ${btnBase}`}>{t('modelPresetUltra')}</button>
            </div>
            {([
              { k: 'tc-models-chat', label: t('modelChat'), isEmbed: false },
              { k: 'tc-models-deep', label: t('modelDeep'), isEmbed: false },
              { k: 'tc-models-vision', label: t('modelVision'), isEmbed: false },
              { k: 'tc-models-vision-quality', label: t('modelVisionQuality'), isEmbed: false },
              { k: 'tc-models-embed', label: t('modelEmbedding'), isEmbed: true },
              { k: 'tc-models-code', label: t('modelCode'), isEmbed: false },
              { k: 'tc-models-fast', label: t('modelFast'), isEmbed: false },
            ] as const).map(({ k, label, isEmbed }) => (
              <div key={k} className={`flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-2 px-3 py-2 rounded-lg ${bgCard} min-w-0 max-w-full overflow-hidden`}>
                <span className={`min-w-0 text-[10px] sm:w-24 sm:shrink-0 break-words leading-tight ${textHeading}`}>{label}</span>
                {isEmbed ? (
                  <select
                    value={getModel(k)}
                    onChange={(e) => setLocalSetting(k, e.target.value)}
                    className={`min-w-0 flex-1 text-[11px] font-mono bg-transparent outline-none border-b border-transparent hover:border-[#006bbd]/30 focus:border-[#006bbd] px-1 py-0.5 transition-colors max-w-full ${isDark ? 'text-white/70' : 'text-gray-700'}`}
                  >
                    <option value="bge-m3">bge-m3 · 1024d · multilingual (recommended)</option>
                    <option value="nomic-embed-text">nomic-embed-text · 768d · faster</option>
                    <option value="all-minilm">all-minilm · 384d · fastest (English)</option>
                    <option value="mxbai-embed-large">mxbai-embed-large · 1024d</option>
                  </select>
                ) : (
                  <input
                    value={getModel(k)}
                    onChange={(e) => setLocalSetting(k, e.target.value)}
                    onBlur={(e) => { const v = e.target.value.trim(); if (v && v !== e.target.value) setLocalSetting(k, v); }}
                    onKeyDown={(e) => { if (e.key === 'Enter') { const v = (e.target as HTMLInputElement).value.trim(); if (v) setLocalSetting(k, v); (e.target as HTMLInputElement).blur(); } }}
                    className={`min-w-0 w-full flex-1 text-[11px] font-mono bg-transparent outline-none border-b border-transparent hover:border-[#006bbd]/30 focus:border-[#006bbd] px-1 py-0.5 transition-colors max-w-full ${isDark ? 'text-white/70' : 'text-gray-700'}`}
                  />
                )}
              </div>
            ))}
            <div className="flex flex-col sm:flex-row gap-2">
              <button onClick={async () => {
                const models = Array.from(new Set(MODEL_KEYS.map(k => getModel(k)).filter(Boolean)));
                for (const m of models) {
                  if (!m) continue;
                  toast.toast(t('modelPulling').replace('{model}', m), 'info');
                  try {
                    await fetch(`${APP_CONFIG.ollamaBase}/api/pull`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name: m, stream: false}) });
                    toast.toast(t('modelReady').replace('{model}', m), 'success');
                  } catch { toast.toast(t('modelPullFailed').replace('{model}', m), 'error'); }
                }
              }} className={`min-w-0 flex-1 px-3 py-2 rounded-lg text-xs font-medium break-words bg-[#006bbd] text-white hover:bg-[#0059a0] active:scale-95 transition-all`}>
                {t('modelSaveAndPull')}
              </button>
              <button onClick={() => {
                setModelPreset('balanced');
              }} className={`min-w-0 py-2 px-3 rounded-lg text-xs font-medium break-words ${btnBase} active:scale-95`}>
                {t('modelRestoreDefaults')}
              </button>
            </div>

            {/* Performance: aggressive quantization + OLLAMA_KEEP_ALIVE + Unload now */}
            <div className={`mt-3 p-3 rounded-lg border space-y-3 ${bgCard}`}>
              <div className={`text-[10px] uppercase tracking-widest ${textHeading}`}>{t('performance')}</div>

              <label className="flex items-center justify-between gap-2 cursor-pointer">
                <span className={`min-w-0 text-xs break-words ${textLabel}`}>{t('aggressiveQuant')}</span>
                <input
                  type="checkbox"
                  checked={localStorage.getItem('tc-aggressive-quant') === '1'}
                  onChange={(e) => setLocalSetting('tc-aggressive-quant', e.target.checked ? '1' : '0')}
                  className="accent-[#006bbd]"
                />
              </label>

              <div className="space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <span className={`min-w-0 text-xs break-words ${textLabel}`}>{t('keepModelsLoaded')}</span>
                  <span className={`text-[10px] font-mono ${textHeading}`}>{getKeepAlive()}</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="60"
                  step="5"
                  value={parseInt(getKeepAlive().replace(/[^0-9]/g, '') || '0', 10)}
                  onChange={(e) => setLocalSetting('tc-keep-alive', e.target.value === '0' ? '0s' : `${e.target.value}m`)}
                  className="w-full accent-[#006bbd]"
                />
                <div className={`flex justify-between text-[9px] ${textHeading}`}>
                  <span>{t('keepAliveOff')}</span><span>30m</span><span>60m</span>
                </div>
              </div>

              <button
                onClick={async () => {
                  const models = Array.from(new Set(MODEL_KEYS.map(k => getModel(k)).filter(Boolean)));
                  let ok = 0;
                  for (const m of models) {
                    try {
                      await fetch(`${APP_CONFIG.ollamaBase}/api/generate`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ model: m, keep_alive: 0, prompt: '' }),
                      });
                      ok++;
                    } catch { /* ignore */ }
                  }
                  toast.toast(t('modelsUnloaded').replace('{ok}', String(ok)).replace('{total}', String(models.length)), 'info');
                }}
                className={`w-full py-2 rounded-lg text-xs font-medium ${btnBase}`}
              >
                {t('unloadAllModelsNow')}
              </button>
            </div>
          </div>
        )}
      </section>

      {/* ── Docs Link ── */}
      <section>
        <button onClick={() => { window.location.hash = '#docs'; }}
          className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl border text-sm font-medium transition-all ${btnBase} active:scale-95`}>
          <MdBook size={16} />
          {t('viewDocs')}
        </button>
      </section>

      {/* ── Restore Config (Danger Zone) ── */}
      <section className="pb-8">
        {!showRestore ? (
          <button onClick={() => setShowRestore(true)}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-red-500/20 text-red-400 text-sm font-medium hover:bg-red-500/10 transition-all active:scale-95">
            <MdRefresh size={16} />
            {t('restoreConfig')}
          </button>
        ) : (
          <div className={`p-4 rounded-xl border border-red-500/20 bg-red-500/5 space-y-3`}>
            <p className="text-xs text-red-400/80">{t('restoreConfigConfirm')}</p>
            <input
              type="text"
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
                className="flex-1 py-2 rounded-lg text-xs font-medium bg-red-500/20 text-red-400 hover:bg-red-500/30 disabled:opacity-30 transition-all">
                {t('restoreConfig')}
              </button>
            </div>
          </div>
        )}
        <button onClick={() => setConfirmStopAll(true)}
          disabled={stoppingAll}
          className="mt-3 w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-red-500/30 text-red-400 text-sm font-medium hover:bg-red-500/10 transition-all active:scale-95">
          <MdPowerSettingsNew size={16} />
          {t('stopAllTrinaxAI')}
        </button>
      </section>
      </>)}

      {section === 'indexing' && (
      <>
      {/* ── Index Section ── */}
      <section>
        <h3 className={`text-xs font-medium uppercase tracking-widest mb-3 ${textHeading}`}>{t('indexProjects')}</h3>
        <div className={`mb-3 flex items-center gap-2 px-3 py-2 rounded-xl border ${bgCard}`}>
          <span className={`text-[11px] shrink-0 ${textHeading}`}>{t('indexCollection')}</span>
          <select
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
            className={`min-w-0 flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl border text-sm font-medium text-center transition-all ${btnBase} disabled:opacity-50 active:scale-95`}>
            <MdStorage className="shrink-0" size={16} />
            <span className="min-w-0 break-words">
              {indexing ? t('indexing') : lastIndexedLabel ? t('indexFolderSelected').replace('{folder}', lastIndexedLabel).replace('{count}', '—') : t('chooseFolderIndex')}
            </span>
          </button>
          {indexing && (
            <button
              onClick={cancelIndex}
              className="px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm font-medium hover:bg-red-500/20 active:scale-95 transition-all"
              aria-label={t('indexCancel')}
              title={t('indexCancel')}
            >
              <MdStop size={16} />
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
                  <span className={`text-xs tabular-nums ${textHeading}`}>{progress}%</span>
                </div>
                <div className={`h-2 w-full overflow-hidden rounded-full ${isDark ? 'bg-white/[0.08]' : 'bg-gray-200'}`}>
                  <div
                    className="h-full rounded-full bg-[#006bbd] transition-all duration-500"
                    style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
                  />
                </div>
                <div className={`flex flex-wrap items-center justify-between gap-2 text-[11px] ${textHeading}`}>
                  <span>{t('indexEta')}: {formatEta(indexJob?.eta_seconds)}</span>
                  <span>{t('indexFiles')}: {indexJob?.saved ?? 0} / {selectedFolderFiles?.length ?? indexJob?.saved ?? 0}</span>
                  {!!indexJob?.skipped && <span>{t('indexSkipped')}: {indexJob.skipped}</span>}
                </div>
              </>
            ) : indexJob?.status === 'completed' ? (
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm min-w-0">
                  <span className="text-green-400 text-base shrink-0">✅</span>
                  <span className={`font-medium ${textLabel} truncate`}>{t('indexComplete')}</span>
                  <span className={`${textHeading} shrink-0`}>({indexJob.saved} {t('indexFiles').toLowerCase()})</span>
                </div>
                <button
                  onClick={() => folderInputRef.current?.click()}
                  className="shrink-0 flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-[#006bbd]/15 text-[#006bbd] hover:bg-[#006bbd]/25 active:scale-95 transition-all"
                  title={t('chooseFolderIndex')}
                >
                  <MdRefresh size={14} />
                  <span className="hidden sm:inline">{t('indexAgain')}</span>
                </button>
              </div>
            ) : null}
          </div>
        )}
      </section>

      <RecentIndexes collections={collections} />

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

      {section === 'prompts' && (<>
        <section className="space-y-4">
          {prompts.filter(p => p.name !== 'system').map((p)=>(<div key={p.name} className={`${sectionBg} rounded-xl p-4 space-y-2`}>
            <div className="flex items-center justify-between">
              <span className={`text-[10px] font-mono ${isDark ? 'text-white/30' : 'text-gray-400'}`}>/{p.name}</span>
              {p.name!=='system'&&<button onClick={()=>setPromptDeleteName(p.name)} className={`p-1 ${isDark ? 'text-white/20' : 'text-gray-300'} hover:text-red-400`} aria-label={t('deletePrompt')} title={t('deletePrompt')}><MdDelete size={14}/></button>}
            </div>
            <textarea value={p.text} onChange={e=>upd(p.name,'text',e.target.value)} rows={3} className={`w-full bg-transparent text-sm ${textValue} ${textPlaceholder} resize-none outline-none border rounded-lg px-3 py-2 ${isDark ? 'border-white/[0.06]' : 'border-gray-200'} ${borderFocus}`}/>
          </div>))}
          <div className={`border border-dashed rounded-xl p-4 space-y-3 ${isDark ? 'border-white/[0.08]' : 'border-gray-300'}`}>
            <input value={nn} onChange={e=>setNn(e.target.value)} placeholder={t('promptName')} maxLength={30} className={`w-full bg-transparent text-sm ${textValue} ${textPlaceholder} outline-none`}/>
            <textarea value={nt} onChange={e=>setNt(e.target.value)} placeholder={t('promptText')} rows={2} className={`w-full bg-transparent text-sm ${textValue} ${textPlaceholder} resize-none outline-none border rounded-lg px-3 py-2 ${isDark ? 'border-white/[0.06]' : 'border-gray-200'} ${borderFocus}`}/>
            <button onClick={add} className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-[#006bbd]/15 text-[#006bbd] hover:bg-[#006bbd]/25"><MdAdd size={14}/> {t('addPrompt')}</button>
          </div>
        </section>
      </>)}

      {section === 'memory' && (
      <MemoryPanel />
      )}

      {section === 'stats' && (
      <StatsPanel />
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
        title={t('stopAllTrinaxAI')}
        message={t('stopAllTrinaxAIConfirm')}
        confirmLabel={t('stopAllTrinaxAI')}
        danger
        onConfirm={() => { setConfirmStopAll(false); sys('stop-all'); }}
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
        open={promptDeleteName !== null}
        title={t('deletePrompt')}
        message={t('promptDeleteConfirm').replace('{name}', promptDeleteName || '')}
        confirmLabel={t('delete')}
        danger
        onConfirm={() => { if (promptDeleteName) del(promptDeleteName); }}
        onCancel={() => setPromptDeleteName(null)}
      />
    </div>
  </motion.div>);
}
