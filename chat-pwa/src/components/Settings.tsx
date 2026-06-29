import { useRef, useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import { MdArrowBack, MdAdd, MdDelete, MdTranslate, MdDarkMode, MdLightMode, MdBook, MdRefresh, MdStorage, MdWarning, MdPowerSettingsNew, MdRocketLaunch, MdStop, MdVisibility, MdMemory, MdBarChart, MdAutoFixHigh, MdBookOnline, MdFlashOn } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { useToast } from './Toast';
import ConfirmModal from './ConfirmModal';
import StatusDots from './StatusDots';
import WatcherCard from './WatcherCard';
import MemoryPanel from './MemoryPanel';
import StatsPanel from './StatsPanel';
import RecentIndexes from './RecentIndexes';
import { cancelIndexJob, createCollection, deleteCollection, folderLabelFromFiles, getCollections, getIndexJob, indexableFilesFrom, renameCollection, resetSharedAppState, startFolderIndex, type Collection, type IndexJobStatus } from '../lib/api';
import { syncSharedStateOnce } from '../lib/sharedState';

interface Props { onBack: () => void; }
interface CustomPrompt { name: string; text: string; }

interface QuickTemplate { name: string; label: string; text: string }

const QUICK_ACTION_TEMPLATES: QuickTemplate[] = [
  { name: 'explain',     label: 'Explain code',      text: 'Explain this code step-by-step in plain language, including the data flow and any subtle gotchas.' },
  { name: 'tests',       label: 'Generate tests',   text: 'Write unit tests for the following code. Cover edge cases, error paths, and at least 3 happy-path scenarios.' },
  { name: 'bugs',        label: 'Find bugs',        text: 'Review the following code for bugs, race conditions, security issues, and silent failure modes. List findings by severity.' },
  { name: 'refactor',    label: 'Refactor',         text: 'Refactor this code for readability and performance while preserving behaviour. Show the new version with brief rationale.' },
  { name: 'commit',      label: 'Commit message',   text: 'Write a conventional-commit message (type(scope): subject) for the diff below. Include a body when the change is non-trivial.' },
  { name: 'translate',   label: 'Translate EN',     text: 'Translate the following text to natural, idiomatic English. Preserve technical terms but rewrite idioms.' },
  { name: 'eli5',        label: 'Explain like 5',    text: 'Explain this like I am five years old. Use short sentences, simple analogies, and avoid jargon.' },
  { name: 'topython',    label: '→ Python',         text: 'Convert the following code to idiomatic Python 3. Preserve behaviour and add type hints where useful.' },
  { name: 'summary',     label: 'Meeting notes',    text: 'Convert raw meeting notes into a structured summary: decisions, action items (with owners), open questions, and next steps.' },
  { name: 'docstring',   label: 'Add docstring',    text: 'Add a high-quality docstring (summary, args, returns, raises, example) to the following function.' },
];

const OLLAMA_KEY = 'tc-ollama-prompts';
const RAG_KEY = 'tc-rag-prompts';

const DEF_OLLAMA_ES = 'Eres TrinaxAI, asistente de IA local-first y open-source. No eres TrinaxCode; TrinaxCode es el creador del proyecto. Responde claro, útil y sin inventar datos.';
const DEF_RAG_ES = 'Eres TrinaxAI. No eres TrinaxCode. Responde solo con datos del contexto indexado. Si falta información, dilo claramente.';
const DEF_OLLAMA_EN = 'You are TrinaxAI, a local-first open-source AI assistant. You are not TrinaxCode; TrinaxCode is the project creator. Be clear, useful, and do not invent facts.';
const DEF_RAG_EN = 'You are TrinaxAI. You are not TrinaxCode. Only respond with data from the indexed context. Do not invent.';
const MODEL_KEYS = ['tc-models-chat','tc-models-deep','tc-models-vision','tc-models-vision-quality','tc-models-embed','tc-models-code','tc-models-fast'];

function load(k: string, d: string): CustomPrompt[] {
  try { const j = localStorage.getItem(k); return j ? JSON.parse(j) : [{ name: 'system', text: d }]; }
  catch { return [{ name: 'system', text: d }]; }
}

function getDefaultOllama(lang: 'es'|'en') { return lang === 'en' ? DEF_OLLAMA_EN : DEF_OLLAMA_ES; }
function getDefaultRag(lang: 'es'|'en') { return lang === 'en' ? DEF_RAG_EN : DEF_RAG_ES; }

export default function Settings({ onBack }: Props) {
  const { t, lang, setLang } = useI18n();
  const { theme, cycleTheme, isDark } = useTheme();
  const toast = useToast();
  const [tab, setTab] = useState<'ollama' | 'rag'>('ollama');
  const [section, setSection] = useState<'general' | 'indexing' | 'prompts' | 'memory' | 'stats'>('general');

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
  const [op, setOp] = useState<CustomPrompt[]>(() => load(OLLAMA_KEY, getDefaultOllama(lang)));
  const [rp, setRp] = useState<CustomPrompt[]>(() => load(RAG_KEY, getDefaultRag(lang)));
  const [nn, setNn] = useState(''); const [nt, setNt] = useState('');
  const prompts = tab === 'ollama' ? op : rp; const setP = tab === 'ollama' ? setOp : setRp; const key = tab === 'ollama' ? OLLAMA_KEY : RAG_KEY;
  useEffect(() => {
    localStorage.setItem(key, JSON.stringify(prompts));
    const id = window.setTimeout(() => { void syncSharedStateOnce(1200); }, 450);
    return () => window.clearTimeout(id);
  }, [prompts, key]);

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
  const folderInputRef = useRef<HTMLInputElement>(null);
  const indexAbortRef = useRef<AbortController | null>(null);

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

  const add = () => {
    const n = nn.trim().toLowerCase().replace(/\s+/g,'-'); if (!n||!nt.trim()) return;
    if (prompts.some(p=>p.name===n)) { toast.toast(t('promptExists'), 'warning'); return; }
    setP([...prompts,{name:n,text:nt.trim()}]); setNn(''); setNt('');
    toast.toast(t('promptAdded'), 'success');
  };
  const upd = (name:string, f:'name'|'text', v:string) => setP(items=>items.map((item)=>item.name===name?{...item,[f]:v}:item));
  const del = (name:string) => {
    if (name === 'system') return;
    setP(items=>items.filter((item)=>item.name!==name));
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
          toast.toast(t('indexImportComplete').replace('{count}', String(job.saved)), 'success');
          setSelectedFolderFiles(null);
          setSelectedFolderTotal(0);
          done = true;
        } else if (job.status === 'cancelled') {
          toast.toast(t('indexCancelled'), 'info');
          done = true;
        } else if (job.status === 'failed') {
          toast.toast(job.error || (lang === 'en' ? 'Indexing failed.' : 'La indexación falló.'), 'error');
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
    finally { setIndexing(false); indexAbortRef.current = null; }
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
    await resetSharedAppState().catch(() => undefined);
    const resetAt = String(Date.now() / 1000);
    const keys = Object.keys(localStorage).filter(k => k.startsWith('tc-'));
    keys.forEach(k => localStorage.removeItem(k));
    localStorage.setItem('tc-reset-at', resetAt);
    await syncSharedStateOnce(1800).catch(() => undefined);
    window.location.reload();
  };

  const setModelPreset = (preset: 'low' | 'balanced' | 'max' | 'ultra') => {
    const values = preset === 'low'
      ? {
        'tc-models-chat': 'llama3.2:3b',
        'tc-models-deep': 'qwen2.5-coder:3b',
        'tc-models-vision': 'qwen2.5vl:3b',
        'tc-models-vision-quality': 'qwen2.5vl:3b',
        'tc-models-embed': 'bge-m3',
        'tc-models-code': 'qwen2.5-coder:3b',
        'tc-models-fast': 'llama3.2:3b',
      }
      : preset === 'ultra'
      ? {
        'tc-models-chat': 'llama3.2:3b',
        'tc-models-deep': 'qwen2.5-coder:14b',
        'tc-models-vision': 'qwen2.5vl:3b',
        'tc-models-vision-quality': 'qwen2.5vl:7b',
        'tc-models-embed': 'bge-m3',
        'tc-models-code': 'qwen2.5-coder:3b',
        'tc-models-fast': 'llama3.2:3b',
      }
      : preset === 'max'
      ? {
        'tc-models-chat': 'llama3.2:3b',
        'tc-models-deep': 'qwen2.5-coder:7b',
        'tc-models-vision': 'qwen2.5vl:3b',
        'tc-models-vision-quality': 'qwen2.5vl:7b',
        'tc-models-embed': 'bge-m3',
        'tc-models-code': 'qwen2.5-coder:3b',
        'tc-models-fast': 'llama3.2:3b',
      }
      : {
        'tc-models-chat': 'llama3.2:3b',
        'tc-models-deep': 'qwen2.5-coder:3b',
        'tc-models-vision': 'qwen2.5vl:3b',
        'tc-models-vision-quality': 'qwen2.5vl:7b',
        'tc-models-embed': 'bge-m3',
        'tc-models-code': 'qwen2.5-coder:3b',
        'tc-models-fast': 'llama3.2:3b',
      };
    Object.entries(values).forEach(([k, v]) => localStorage.setItem(k, v));
    toast.toast(t('modelPresetApplied'), 'success');
  };

  const getModel = (key: string, fallback: string) => localStorage.getItem(key) || fallback;
  const progress = Math.max(uploadProgress, indexJob?.progress ?? 0);
  const formatEta = (seconds: number | null | undefined) => {
    if (!seconds) return lang === 'en' ? 'calculating ETA' : 'calculando tiempo';
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
  const tabActive = 'text-[#006bbd] border-b-2 border-[#006bbd]';
  const tabInactive = isDark ? 'text-white/40 hover:text-white/70' : 'text-gray-400 hover:text-gray-600';
  const inputText = isDark ? 'text-white/70' : 'text-gray-700';
  const borderFocus = 'focus:border-[#006bbd]/40';
  const sectionBg = isDark ? 'bg-white/[0.03] border-white/[0.06]' : 'bg-gray-50 border-gray-200';

  return (<motion.div className={`h-full flex flex-col min-w-0 max-w-full ${isDark ? 'bg-black' : 'bg-white'}`} initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}>
    <div className={`shrink-0 flex items-center gap-3 px-4 pt-[env(safe-area-inset-top,0px)] pb-3 border-b ${isDark ? 'border-white/[0.06]' : 'border-gray-200'}`}>
      <button onClick={onBack} className={`p-2 -ml-2 ${isDark ? 'text-white/60 hover:text-white' : 'text-gray-500 hover:text-gray-800'}`}><MdArrowBack size={20}/></button>
      <span className={`text-sm font-medium ${textLabel}`}>{t('settingsTitle')}</span>
    </div>
    <div className={`shrink-0 flex gap-1 px-2 pt-2 pb-1 border-b ${isDark ? 'border-white/[0.04]' : 'border-gray-100'} overflow-x-auto`}>
      {([
        ['general', lang === 'en' ? 'General' : 'General'],
        ['indexing', lang === 'en' ? 'Indexing' : 'Indexado'],
        ['prompts', lang === 'en' ? 'Prompts' : 'Prompts'],
        ['memory', lang === 'en' ? 'Memory' : 'Memoria'],
        ['stats', lang === 'en' ? 'Stats' : 'Stats'],
      ] as const).map(([k, lbl]) => (
        <button
          key={k}
          onClick={() => setSection(k)}
          className={`shrink-0 px-2 py-1 rounded-lg text-[11px] font-medium transition-colors whitespace-nowrap ${
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
            title={lang === 'en' ? 'Toggle black/white theme' : 'Cambiar entre tema negro y blanco'}
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
      <section>
        <button onClick={() => setModelsExpanded(v => !v)}
          className={`w-full flex items-center justify-between text-xs font-medium uppercase tracking-widest mb-3 ${textHeading} hover:opacity-80`}>
          <span>{t('modelCustomize')}</span>
          <span className="text-[10px]">{modelsExpanded ? '▾' : '▸'}</span>
        </button>
        {modelsExpanded && (
          <div className="space-y-2">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <button onClick={() => setModelPreset('low')} className={`min-w-0 px-2 py-2 rounded-lg text-[11px] font-medium break-words ${btnBase}`}>{t('modelPresetLow')}</button>
              <button onClick={() => setModelPreset('balanced')} className={`min-w-0 px-2 py-2 rounded-lg text-[11px] font-medium break-words ${btnBase}`}>{t('modelPresetBalanced')}</button>
              <button onClick={() => setModelPreset('max')} className={`min-w-0 px-2 py-2 rounded-lg text-[11px] font-medium break-words ${btnBase}`}>{t('modelPresetMax')}</button>
              <button onClick={() => setModelPreset('ultra')} className={`min-w-0 px-2 py-2 rounded-lg text-[11px] font-medium break-words ${btnBase}`}>{t('modelPresetUltra')}</button>
            </div>
            {[
              { k: 'tc-models-chat', label: t('modelChat'), def: 'llama3.2:3b' },
              { k: 'tc-models-deep', label: t('modelDeep'), def: 'qwen2.5-coder:3b' },
              { k: 'tc-models-vision', label: t('modelVision'), def: 'qwen2.5vl:3b' },
              { k: 'tc-models-vision-quality', label: t('modelVisionQuality'), def: 'qwen2.5vl:7b' },
              { k: 'tc-models-embed', label: t('modelEmbedding'), def: 'bge-m3', isEmbed: true },
              { k: 'tc-models-code', label: t('modelCode'), def: 'qwen2.5-coder:3b' },
              { k: 'tc-models-fast', label: t('modelFast'), def: 'llama3.2:3b' },
            ].map(({ k, label, def, isEmbed }) => (
              <div key={k} className={`flex flex-col sm:flex-row sm:items-center gap-2 px-3 py-2 rounded-lg ${bgCard}`}>
                <span className={`min-w-0 text-[10px] sm:w-28 sm:shrink-0 break-words ${textHeading}`}>{label}</span>
                {isEmbed ? (
                  <select
                    value={localStorage.getItem(k) || def}
                    onChange={(e) => localStorage.setItem(k, e.target.value)}
                    className={`min-w-0 flex-1 text-[11px] font-mono bg-transparent outline-none border-b border-transparent hover:border-[#006bbd]/30 focus:border-[#006bbd] px-1 py-0.5 transition-colors ${isDark ? 'text-white/70' : 'text-gray-700'}`}
                  >
                    <option value="bge-m3">bge-m3 · 1024d · multilingual (recommended)</option>
                    <option value="nomic-embed-text">nomic-embed-text · 768d · faster</option>
                    <option value="all-minilm">all-minilm · 384d · fastest (English)</option>
                    <option value="mxbai-embed-large">mxbai-embed-large · 1024d</option>
                  </select>
                ) : (
                  <input
                    defaultValue={getModel(k, def)}
                    onBlur={(e) => { const v = e.target.value.trim(); if (v) localStorage.setItem(k, v); }}
                    onKeyDown={(e) => { if (e.key === 'Enter') { const v = (e.target as HTMLInputElement).value.trim(); if (v) localStorage.setItem(k, v); (e.target as HTMLInputElement).blur(); } }}
                    className={`min-w-0 flex-1 text-[11px] font-mono bg-transparent outline-none border-b border-transparent hover:border-[#006bbd]/30 focus:border-[#006bbd] px-1 py-0.5 transition-colors ${isDark ? 'text-white/70' : 'text-gray-700'}`}
                  />
                )}
              </div>
            ))}
            <div className="flex flex-col sm:flex-row gap-2">
              <button onClick={async () => {
                const models = MODEL_KEYS.map(k => localStorage.getItem(k)).filter(Boolean) as string[];
                for (const m of models) {
                  if (!m) continue;
                  toast.toast(t('modelPulling').replace('{model}', m), 'info');
                  try {
                    await fetch('/api/ollama/api/pull', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name: m, stream: false}) });
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
              <div className={`text-[10px] uppercase tracking-widest ${textHeading}`}>{lang === 'en' ? 'Performance' : 'Rendimiento'}</div>

              <label className="flex items-center justify-between gap-2 cursor-pointer">
                <span className={`min-w-0 text-xs break-words ${textLabel}`}>{lang === 'en' ? 'Aggressive quantization (Q4_K_M, offload to CPU)' : 'Quantization agresiva (Q4_K_M, offload a CPU)'}</span>
                <input
                  type="checkbox"
                  checked={localStorage.getItem('tc-aggressive-quant') === '1'}
                  onChange={(e) => localStorage.setItem('tc-aggressive-quant', e.target.checked ? '1' : '0')}
                  className="accent-[#006bbd]"
                />
              </label>

              <div className="space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <span className={`min-w-0 text-xs break-words ${textLabel}`}>{lang === 'en' ? 'Keep models loaded' : 'Mantener modelos cargados'}</span>
                  <span className={`text-[10px] font-mono ${textHeading}`}>{localStorage.getItem('tc-keep-alive') || '0s'}</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="60"
                  step="5"
                  value={parseInt(localStorage.getItem('tc-keep-alive')?.replace(/[^0-9]/g, '') || '0', 10)}
                  onChange={(e) => localStorage.setItem('tc-keep-alive', `${e.target.value}m`)}
                  className="w-full accent-[#006bbd]"
                />
                <div className={`flex justify-between text-[9px] ${textHeading}`}>
                  <span>0m (off)</span><span>30m</span><span>60m</span>
                </div>
              </div>

              <button
                onClick={async () => {
                  const models = MODEL_KEYS.map(k => localStorage.getItem(k)).filter(Boolean) as string[];
                  let ok = 0;
                  for (const m of models) {
                    try {
                      await fetch('/api/ollama/api/generate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ model: m, keep_alive: 0, prompt: '' }),
                      });
                      ok++;
                    } catch { /* ignore */ }
                  }
                  toast.toast(lang === 'en' ? `Unloaded ${ok}/${models.length} models` : `Descargados ${ok}/${models.length} modelos`, 'info');
                }}
                className={`w-full py-2 rounded-lg text-xs font-medium ${btnBase}`}
              >
                {lang === 'en' ? 'Unload all models now' : 'Descargar todos los modelos ahora'}
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
      <WatcherCard collections={collections} />
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
            <span className="min-w-0 break-words">{indexing ? t('indexing') : t('chooseFolderIndex')}</span>
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
          </div>
        )}
      </section>
      </>)}

      {section === 'prompts' && (<>
        <div className={`flex border-b ${isDark ? 'border-white/[0.06]' : 'border-gray-200'}`}>
          {(['ollama','rag']as const).map(tb=>(<button key={tb} onClick={()=>{setTab(tb);setNn('');setNt('')}} className={`px-4 py-2 text-sm font-medium ${tab===tb?tabActive:tabInactive}`}>{tb==='ollama'?t('ollamaEngine'):t('ragEngine')}</button>))}
        </div>
        {/* ── Quick Action templates ── */}
        <section>
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <h3 className={`text-xs font-medium uppercase tracking-widest ${textHeading}`}>{lang === 'en' ? 'Quick Action templates' : 'Plantillas de acción rápida'}</h3>
            <span className={`text-[10px] ${textHeading}`}>{lang === 'en' ? 'Click to add as slash command' : 'Click para añadir como slash'}</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {QUICK_ACTION_TEMPLATES.map((tmpl) => {
              const exists = prompts.some((p) => p.name === tmpl.name);
              return (
                <button
                  key={tmpl.name}
                  onClick={() => {
                    if (exists) { toast.toast(lang === 'en' ? 'Already added' : 'Ya existe', 'warning'); return; }
                    setP([...prompts, { name: tmpl.name, text: tmpl.text }]);
                    toast.toast(lang === 'en' ? `Added /${tmpl.name}` : `Añadido /${tmpl.name}`, 'success');
                  }}
                className={`min-w-0 flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
                    exists
                      ? isDark ? 'bg-white/[0.03] border-white/[0.06] text-white/30 cursor-not-allowed' : 'bg-gray-100 border-gray-200 text-gray-400 cursor-not-allowed'
                      : isDark ? 'bg-white/[0.03] border-white/[0.06] text-white/65 hover:text-white hover:border-white/[0.15]' : 'bg-white border-gray-200 text-gray-600 hover:text-gray-800 hover:border-gray-300'
                  }`}
                  disabled={exists}
                >
                  <span className="font-mono text-[10px] text-[#006bbd]">/{tmpl.name}</span>
                  <span className="min-w-0 break-words opacity-80">{tmpl.label}</span>
                </button>
              );
            })}
          </div>
        </section>

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
        message={lang === 'en' ? 'Are you sure you want to shut down the AI system? This will stop Ollama and the RAG API.' : '¿Estás seguro de que quieres apagar el sistema IA? Esto detendrá Ollama y la API RAG.'}
        confirmLabel={t('shutdownAI')}
        danger
        onConfirm={() => { setConfirmShutdown(false); sys('shutdown'); }}
        onCancel={() => setConfirmShutdown(false)}
      />
      <ConfirmModal
        open={confirmStartup}
        title={t('startupAI')}
        message={lang === 'en' ? 'Start the AI system? This will launch Ollama and the RAG API.' : '¿Iniciar el sistema IA? Esto lanzará Ollama y la API RAG.'}
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
