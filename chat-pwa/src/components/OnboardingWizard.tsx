import { useState, useCallback, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MdContentCopy, MdCheck } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { APP_CONFIG } from '../lib/config';
import { cancelIndexJob, folderLabelFromFiles, getIndexJob, indexableFilesFrom, startFolderIndex, type IndexJobStatus } from '../lib/api';
import { syncSharedStateOnce } from '../lib/sharedState';
import { FaGithub } from 'react-icons/fa';

interface Props {
  onComplete: () => void;
}

const DEFAULT_MODELS = {
  chat: 'llama3.2:3b',
  deep: 'qwen2.5-coder:3b',
  vision: 'qwen2.5vl:3b',
  visionQuality: 'qwen2.5vl:7b',
  embed: 'bge-m3',
  code: 'qwen2.5-coder:3b',
  fast: 'llama3.2:3b',
};

type Step = 1 | 2 | 3 | 4 | 5 | 6;

const stepVariants = {
  enter: { opacity: 0, x: 40, scale: 0.97 },
  center: { opacity: 1, x: 0, scale: 1 },
  exit: { opacity: 0, x: -40, scale: 0.97 },
};

export default function OnboardingWizard({ onComplete }: Props) {
  const { t, lang, setLang } = useI18n();
  const { isDark, setTheme } = useTheme();
  const [step, setStep] = useState<Step>(1);
  const [nickname, setNickname] = useState('');
  const [finishing, setFinishing] = useState(false);
  const [modelChoice, setModelChoice] = useState<'default' | 'custom' | 'test' | null>(null);
  const [customModels, setCustomModels] = useState(DEFAULT_MODELS);
  const [customStep, setCustomStep] = useState(0);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const [ollamaDetected, setOllamaDetected] = useState<boolean | null>(null);
  const [indexing, setIndexing] = useState(false);
  const [selectedFolderName, setSelectedFolderName] = useState('');
  const [selectedFolderCount, setSelectedFolderCount] = useState(0);
  const [indexJob, setIndexJob] = useState<IndexJobStatus | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [testResults, setTestResults] = useState<Record<string, boolean> | null>(null);
  const [copiedCmd, setCopiedCmd] = useState<string | null>(null);
  const indexAbortRef = useRef<AbortController | null>(null);

  const copyToClipboard = useCallback(async (text: string, key: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedCmd(key);
      setTimeout(() => setCopiedCmd(null), 1800);
    } catch { /* ignore */ }
  }, []);

  const saveAndNext = useCallback(() => {
    if (step < 6) setStep((s) => (s + 1) as Step);
    else finish();
  }, [step]);

  const prev = useCallback(() => {
    if (step > 1) setStep((s) => (s - 1) as Step);
  }, [step]);

  const finish = useCallback(() => {
    setFinishing(true);
    localStorage.setItem('tc-onboarding-complete', 'true');
    const preferredName = nickname.trim();
    if (preferredName) localStorage.setItem('tc-user-nickname', preferredName);
    localStorage.removeItem('tc-user-name');
    localStorage.removeItem('tc-user-avatar');
    const models = modelChoice === 'custom' ? customModels : DEFAULT_MODELS;
    localStorage.setItem('tc-models-chat', models.chat);
    localStorage.setItem('tc-models-deep', models.deep);
    localStorage.setItem('tc-models-vision', models.vision);
    localStorage.setItem('tc-models-vision-quality', models.visionQuality);
    localStorage.setItem('tc-models-embed', models.embed);
    localStorage.setItem('tc-models-code', models.code);
    localStorage.setItem('tc-models-fast', models.fast);
    syncSharedStateOnce(2500, true).finally(() => {
      setFinishing(false);
      onComplete();
    });
  }, [nickname, modelChoice, customModels, onComplete]);

  const runSystemTest = useCallback(async () => {
    setTestResults(null);
    const results: Record<string, boolean> = {};
    try {
      const r = await fetch(`${APP_CONFIG.ollamaBase}/api/tags`, { signal: AbortSignal.timeout(5000) });
      results.ollama = r.ok;
    } catch { results.ollama = false; }
    try {
      const r = await fetch(`${APP_CONFIG.ragBase}/health`, { signal: AbortSignal.timeout(5000) });
      if (r.ok) {
        const d = await r.json();
        results.rag = true;
        results.index = !!d.indexed;
      } else { results.rag = false; results.index = false; }
    } catch { results.rag = false; results.index = false; }
    results.speech = typeof window !== 'undefined' && 'speechSynthesis' in window;
    setTestResults(results);
  }, []);

  const checkOllama = useCallback(async () => {
    try {
      const r = await fetch(`${APP_CONFIG.ollamaBase}/api/tags`, { signal: AbortSignal.timeout(5000) });
      setOllamaDetected(r.ok);
    } catch { setOllamaDetected(false); }
  }, []);

  const triggerIndex = useCallback(async (files: File[]) => {
    setIndexing(true);
    setIndexJob(null);
    setUploadProgress(0);
    const controller = new AbortController();
    indexAbortRef.current = controller;
    try {
      const result = await startFolderIndex(files, {
        signal: controller.signal,
        onUploadProgress: setUploadProgress,
      });
      setSelectedFolderName(folderLabelFromFiles(files));
      setSelectedFolderCount(result.saved);
      if (!result.job_id) return;
      while (!controller.signal.aborted) {
        const job = await getIndexJob(result.job_id, controller.signal);
        setIndexJob(job);
        setSelectedFolderCount(job.saved || result.saved);
        if (['completed', 'failed', 'cancelled'].includes(job.status)) break;
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
      // Completion state clearing & auto-advance handled by the useEffect below
    } catch { /* user can continue and retry later from Settings */ }
    finally {
      setIndexing(false);
      indexAbortRef.current = null;
    }
  }, []);

  // Auto-advance to next step after successful indexing
  useEffect(() => {
    if (!indexing && indexJob?.status === 'completed' && step === 5) {
      const timer = setTimeout(() => {
        setIndexJob(null);
        setStep(6);
      }, 2500);
      return () => clearTimeout(timer);
    }
  }, [indexing, indexJob?.status, indexJob?.id, step]);

  const cancelIndex = useCallback(async () => {
    indexAbortRef.current?.abort();
    if (indexJob?.id) {
      const cancelled = await cancelIndexJob(indexJob.id).catch(() => null);
      if (cancelled) setIndexJob(cancelled);
    }
    setIndexing(false);
  }, [indexJob]);

  const modelKeys = [
    { key: 'chat' as const, label: t('modelChat') },
    { key: 'deep' as const, label: t('modelDeep') },
    { key: 'vision' as const, label: t('modelVision') },
    { key: 'visionQuality' as const, label: t('modelVisionQuality') },
    { key: 'embed' as const, label: t('modelEmbedding') },
    { key: 'code' as const, label: t('modelCode') },
    { key: 'fast' as const, label: t('modelFast') },
  ];

  const bg = isDark ? 'bg-black' : 'bg-white';
  const cardBg = isDark ? 'bg-white/[0.03] border-white/[0.06]' : 'bg-gray-50 border-gray-200';
  const textMain = isDark ? 'text-white' : 'text-gray-900';
  const textSub = isDark ? 'text-white/50' : 'text-gray-500';
  const inputBg = isDark ? 'bg-white/[0.05] border-white/[0.1] text-white placeholder-white/30' : 'bg-white border-gray-300 text-gray-900 placeholder-gray-400';
  const btnPrimary = 'bg-[#006bbd] text-white hover:bg-[#0059a0] active:scale-95';
  const btnSecondary = isDark ? 'bg-white/[0.06] text-white/70 hover:bg-white/[0.1]' : 'bg-gray-100 text-gray-700 hover:bg-gray-200';
  const selectedCard = 'border-[#006bbd] bg-[#006bbd]/5 ring-1 ring-[#006bbd]/30';
  const stepDot = (s: Step) => step === s ? 'bg-[#006bbd] w-3' : (step > s ? 'bg-[#006bbd]/40' : (isDark ? 'bg-white/[0.15]' : 'bg-gray-300'));
  const indexProgress = Math.max(uploadProgress, indexJob?.progress ?? 0);

  return (
    <motion.div
      className={`fixed inset-0 z-50 flex flex-col items-center justify-center ${bg} px-4 transition-colors duration-300`}
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
    >
      <div className="w-full max-w-lg flex flex-col gap-5 sm:gap-6 px-1 sm:px-0">
        {/* Progress dots */}
        <div className="flex justify-center gap-2">
          {([1,2,3,4,5,6] as Step[]).map((s) => (
            <motion.div
              key={s}
              className={`h-1.5 rounded-full transition-all duration-300 ${stepDot(s)}`}
              animate={{ width: step === s ? 24 : 8 }}
            />
          ))}
        </div>

        <AnimatePresence mode="wait">
          {/* Step 1: Language */}
          {step === 1 && (
            <motion.div key="s1" variants={stepVariants} initial="enter" animate="center" exit="exit" transition={{ duration: 0.25 }} className="flex flex-col gap-5">
              <h2 className={`text-2xl font-semibold text-center ${textMain}`}>{t('onboardingStep1Title')}</h2>
              <p className={`text-sm text-center ${textSub}`}>{t('onboardingStep1Desc')}</p>
              <div className="grid grid-cols-2 gap-3">
                {(['es', 'en'] as const).map((l) => (
                  <motion.button
                    key={l}
                    whileTap={{ scale: 0.96 }}
                    onClick={() => setLang(l)}
                    className={`p-5 rounded-2xl border-2 text-center transition-all ${lang === l ? selectedCard : `border-transparent ${cardBg} hover:border-white/10`}`}
                  >
                    <span className="text-3xl">{l === 'es' ? '🇪🇸' : '🇺🇸'}</span>
                    <p className={`mt-2 font-medium ${textMain}`}>{l === 'es' ? 'Español' : 'English'}</p>
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}

          {/* Step 2: Theme */}
          {step === 2 && (
            <motion.div key="s2" variants={stepVariants} initial="enter" animate="center" exit="exit" transition={{ duration: 0.25 }} className="flex flex-col gap-5">
              <h2 className={`text-2xl font-semibold text-center ${textMain}`}>{t('onboardingStep2Title')}</h2>
              <p className={`text-sm text-center ${textSub}`}>{t('onboardingStep2Desc')}</p>
              <div className="grid grid-cols-2 gap-3">
                {(['dark', 'light'] as const).map((mode) => (
                  <motion.button
                    key={mode}
                    whileTap={{ scale: 0.96 }}
                    onClick={() => setTheme(mode)}
                    className={`p-5 rounded-2xl border-2 text-center transition-all ${(mode === 'dark') === isDark ? selectedCard : `border-transparent ${cardBg} hover:border-white/10`}`}
                  >
                    <div className={`mx-auto w-16 h-10 rounded-lg mb-2 border ${mode === 'dark' ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-300'}`}>
                      <div className={`h-2 w-8 mx-auto mt-1.5 rounded ${mode === 'dark' ? 'bg-gray-700' : 'bg-gray-200'}`} />
                      <div className={`h-1.5 w-5 mx-auto mt-1 rounded ${mode === 'dark' ? 'bg-gray-600' : 'bg-gray-300'}`} />
                    </div>
                    <p className={`font-medium ${textMain}`}>{mode === 'dark' ? t('darkMode') : t('lightMode')}</p>
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}

          {/* Step 3: Name */}
          {step === 3 && (
            <motion.div key="s3" variants={stepVariants} initial="enter" animate="center" exit="exit" transition={{ duration: 0.25 }} className="flex flex-col gap-5">
              <h2 className={`text-2xl font-semibold text-center ${textMain}`}>{t('onboardingStep3Title')}</h2>
              <p className={`text-sm text-center ${textSub}`}>{t('onboardingStep3Desc')}</p>
              <div className="space-y-4">
                <input
                  type="text"
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value)}
                  placeholder={t('onboardingStep3NicknameLabel')}
                  className={`w-full px-4 py-3 rounded-xl border text-sm outline-none focus:border-[#006bbd]/40 transition-colors ${inputBg}`}
                  autoFocus
                />
              </div>
            </motion.div>
          )}

          {/* Step 4: Models */}
          {step === 4 && (
            <motion.div key="s4" variants={stepVariants} initial="enter" animate="center" exit="exit" transition={{ duration: 0.25 }} className="flex flex-col gap-4">
              <h2 className={`text-2xl font-semibold text-center ${textMain}`}>{t('onboardingStep5Title')}</h2>
              <p className={`text-sm text-center ${textSub}`}>{t('onboardingStep5Desc')}</p>

              {!modelChoice && (
                <div className="space-y-3">
                  {(['default', 'test', 'custom'] as const).map((choice) => (
                    <motion.button
                      key={choice}
                      whileTap={{ scale: 0.97 }}
                      onClick={() => {
                        if (choice === 'default') { setModelChoice('default'); saveAndNext(); }
                        else if (choice === 'test') { setModelChoice('test'); runSystemTest(); }
                        else setModelChoice(choice);
                      }}
                      className={`w-full p-4 rounded-xl border text-left transition-all ${modelChoice === choice ? selectedCard : `${cardBg} hover:border-white/10`}`}
                    >
                      <p className={`font-medium text-sm ${textMain}`}>{t(`onboardingStep5${choice === 'default' ? 'Default' : choice === 'custom' ? 'Custom' : 'AutoTest'}` as any)}</p>
                      <p className={`text-xs mt-1 ${textSub}`}>{t(`onboardingStep5${choice === 'default' ? 'Default' : choice === 'custom' ? 'Custom' : 'AutoTest'}Desc` as any)}</p>
                    </motion.button>
                  ))}
                  <div className={`p-3 rounded-xl text-xs ${cardBg}`}>
                    <span className={textSub}>{t('onboardingStep5Info')} </span>
                    <a href="https://www.canirun.ai" target="_blank" rel="noopener noreferrer" className="text-[#006bbd] underline">{t('onboardingStep5InfoLink')}</a>
                    <span className={textSub}> {t('onboardingStep5InfoText')}</span>
                  </div>
                  <details className={`p-3 rounded-xl text-xs ${cardBg}`}>
                    <summary className={`font-medium cursor-pointer ${textMain}`}>{t('onboardingStep5PromptTitle')}</summary>
                    <pre className={`mt-2 p-2 rounded-lg text-[11px] whitespace-pre-wrap ${isDark ? 'bg-black/30 text-white/60' : 'bg-gray-200 text-gray-600'}`}>
                      {t('onboardingStep5PromptText')}
                    </pre>
                  </details>
                </div>
              )}

              {/* Back to model choice */}
              {modelChoice && (
                <button onClick={() => { setModelChoice(null); setTestResults(null); setCustomStep(0); }}
                  className={`text-xs ${isDark ? 'text-white/30 hover:text-white/60' : 'text-gray-400 hover:text-gray-600'} transition-colors self-start`}>
                  {t('onboardingBack')}
                </button>
              )}
              {modelChoice === 'test' && testResults && (
                <div className={`p-4 rounded-xl ${cardBg} space-y-2`}>
                  <div className="flex items-center justify-between">
                    <p className={`text-sm font-medium ${textMain}`}>{t('systemCheckTitle')}</p>
                    <button onClick={() => { setModelChoice(null); setTestResults(null); }}
                      className={`text-xs ${isDark ? 'text-white/30 hover:text-white/60' : 'text-gray-400 hover:text-gray-600'}`}>
                      {t('onboardingBack')}
                    </button>
                  </div>
                  {Object.entries(testResults).map(([k, v]) => (
                    <div key={k} className="flex items-center gap-2 text-xs">
                      <span className={v ? 'text-green-400' : 'text-red-400'}>{v ? '✅' : '❌'}</span>
                      <span className={textSub}>{t(k as any)}</span>
                    </div>
                  ))}
                  <motion.button whileTap={{ scale: 0.96 }} onClick={() => { setModelChoice('default'); setTestResults(null); saveAndNext(); }} className={`mt-2 w-full py-2 rounded-lg text-sm font-medium ${btnPrimary}`}>
                    {t('onboardingNext')}
                  </motion.button>
                </div>
              )}

              {/* Custom model picker */}
              {modelChoice === 'custom' && (
                <div className={`p-4 rounded-xl ${cardBg} space-y-3`}>
                  {customStep < modelKeys.length ? (
                    <>
                      <p className={`text-xs ${textSub}`}>{modelKeys[customStep].label}</p>
                      <input
                        type="text"
                        value={customModels[modelKeys[customStep].key]}
                        onChange={(e) => setCustomModels((m) => ({ ...m, [modelKeys[customStep].key]: e.target.value }))}
                        className={`w-full px-3 py-2 rounded-lg border text-sm outline-none ${inputBg}`}
                        autoFocus
                      />
                      <div className="flex gap-2">
                        <motion.button whileTap={{ scale: 0.96 }} onClick={() => setCustomStep((s) => s + 1)} className={`flex-1 py-2 rounded-lg text-sm font-medium ${btnPrimary}`}>
                          {customStep < modelKeys.length - 1 ? t('onboardingNext') : t('onboardingFinish')}
                        </motion.button>
                      </div>
                    </>
                  ) : (
                    <motion.button whileTap={{ scale: 0.96 }} onClick={() => setModelChoice('default')} className={`w-full py-2 rounded-lg text-sm font-medium ${btnSecondary}`}>
                      {t('modelRestoreDefaults')}
                    </motion.button>
                  )}
                </div>
              )}
            </motion.div>
          )}

          {/* Step 5: Ollama + Indexing */}
          {step === 5 && (
            <motion.div key="s5" variants={stepVariants} initial="enter" animate="center" exit="exit" transition={{ duration: 0.25 }} className="flex flex-col gap-5">
              <h2 className={`text-2xl font-semibold text-center ${textMain}`}>{t('onboardingStep6Title')}</h2>
              <p className={`text-sm text-center ${textSub}`}>{t('onboardingStep6Desc')}</p>

              <div className={`p-4 rounded-xl ${cardBg} text-center`}>
                {ollamaDetected === null ? (
                  <div className="space-y-3">
                    <p className={`text-sm ${textSub}`}>{t('ollamaCheckTitle')}</p>
                    <motion.button whileTap={{ scale: 0.96 }} onClick={checkOllama} className={`px-6 py-2.5 rounded-xl text-sm font-medium ${btnPrimary}`}>
                      {t('modelTestConnection')}
                    </motion.button>
                  </div>
                ) : ollamaDetected ? (
                  <p className="text-green-400 text-sm font-medium">{t('ollamaDetected')}</p>
                ) : (
                  <div className="space-y-3 text-left">
                    <p className="text-amber-400 text-sm font-medium">{t('ollamaNotDetected')}</p>
                    <div className="space-y-2 text-xs">
                      <details className={`p-2 rounded-lg ${cardBg}`}>
                        <summary className="font-medium cursor-pointer">{t('platformLinux')}</summary>
                        <div className="mt-1 flex items-center gap-2">
                          <pre className="flex-1 p-2 rounded text-[11px] bg-black/20 overflow-x-auto">curl -fsSL https://ollama.com/install.sh | sh</pre>
                          <button
                            onClick={(e) => { e.stopPropagation(); copyToClipboard('curl -fsSL https://ollama.com/install.sh | sh', 'linux'); }}
                            className={`shrink-0 p-1.5 rounded-md transition-colors ${copiedCmd === 'linux' ? 'text-green-400 bg-green-400/10' : isDark ? 'text-white/30 hover:text-white/70 hover:bg-white/[0.06]' : 'text-gray-400 hover:text-gray-700 hover:bg-gray-100'}`}
                            title={t('copy')}
                          >
                            {copiedCmd === 'linux' ? <MdCheck size={14} /> : <MdContentCopy size={14} />}
                          </button>
                        </div>
                      </details>
                      <details className={`p-2 rounded-lg ${cardBg}`}>
                        <summary className="font-medium cursor-pointer">{t('platformMac')}</summary>
                        <div className="mt-1 flex items-center gap-2">
                          <pre className="flex-1 p-2 rounded text-[11px] bg-black/20 overflow-x-auto">brew install ollama</pre>
                          <button
                            onClick={(e) => { e.stopPropagation(); copyToClipboard('brew install ollama', 'mac'); }}
                            className={`shrink-0 p-1.5 rounded-md transition-colors ${copiedCmd === 'mac' ? 'text-green-400 bg-green-400/10' : isDark ? 'text-white/30 hover:text-white/70 hover:bg-white/[0.06]' : 'text-gray-400 hover:text-gray-700 hover:bg-gray-100'}`}
                            title={t('copy')}
                          >
                            {copiedCmd === 'mac' ? <MdCheck size={14} /> : <MdContentCopy size={14} />}
                          </button>
                        </div>
                      </details>
                      <details className={`p-2 rounded-lg ${cardBg}`}>
                        <summary className="font-medium cursor-pointer">{t('platformWindows')}</summary>
                        <pre className="mt-1 p-2 rounded text-[11px] bg-black/20">{t('ollamaWindowsDownload')}</pre>
                      </details>
                    </div>
                  </div>
                )}
              </div>

              <div className="space-y-3">
                <p className={`text-sm text-center ${textSub}`}>
                  {t('indexFolderLabel')}
                </p>
                <input
                  ref={folderInputRef}
                  type="file"
                  multiple
                  className="hidden"
                  onChange={(e) => {
                    const files = e.target.files;
                    const frozen = Array.from(files ?? []);
                    const indexable = indexableFilesFrom(frozen);
                    if (frozen.length && indexable.length) {
                      setSelectedFolderName(folderLabelFromFiles(frozen));
                      setSelectedFolderCount(indexable.length);
                      triggerIndex(indexable);
                    } else if (frozen.length) {
                      setSelectedFolderName('');
                      setSelectedFolderCount(0);
                    }
                    e.target.value = '';
                  }}
                  {...{ webkitdirectory: '', directory: '' }}
                />
                <motion.button whileTap={{ scale: 0.96 }} onClick={() => folderInputRef.current?.click()} disabled={indexing} className={`w-full py-3 rounded-xl text-sm font-medium transition-all ${btnSecondary} disabled:opacity-50`}>
                  {selectedFolderName
                    ? t('indexFolderSelected').replace('{folder}', selectedFolderName).replace('{count}', String(selectedFolderCount))
                    : t('chooseFolder')}
                </motion.button>
                {(indexing || indexJob) && (
                  <div className={`p-3 rounded-xl ${cardBg} space-y-2`}>
                    {indexing ? (
                      <>
                        <div className="flex items-center justify-between text-xs">
                          <span className={textSub}>{indexJob?.phase ? t('indexing') : t('loading')}</span>
                          <span className={textSub}>{indexProgress}%</span>
                        </div>
                        <div className={`h-2 w-full overflow-hidden rounded-full ${isDark ? 'bg-white/[0.08]' : 'bg-gray-200'}`}>
                          <div className="h-full rounded-full bg-[#006bbd] transition-all duration-500" style={{ width: `${Math.min(100, indexProgress)}%` }} />
                        </div>
                        <button onClick={cancelIndex} className="w-full py-2 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20">
                          {t('indexCancel')}
                        </button>
                      </>
                    ) : indexJob?.status === 'completed' ? (
                      <div className="flex items-center gap-2 text-sm">
                        <span className="text-green-400">✅</span>
                        <span className={`font-medium ${textMain}`}>{t('indexComplete')}</span>
                        <span className={textSub}>({indexJob.saved} {t('indexFiles').toLowerCase()})</span>
                      </div>
                    ) : null}
                  </div>
                )}
                <p className={`text-[11px] text-center text-amber-400/80`}>{t('onboardingStep6Warning')}</p>
                <div className="flex gap-3">
                  <motion.button whileTap={{ scale: 0.96 }} onClick={saveAndNext} className={`flex-1 py-3 rounded-xl text-sm font-medium ${btnSecondary} active:scale-95`}>
                    {t('onboardingStep6IndexLater')}
                  </motion.button>
                </div>
              </div>
            </motion.div>
          )}

          {/* Step 6: Done */}
          {step === 6 && (
            <motion.div key="s6" variants={stepVariants} initial="enter" animate="center" exit="exit" transition={{ duration: 0.25 }} className="flex flex-col gap-5 items-center text-center">
              <h2 className={`text-2xl font-semibold ${textMain}`}>{t('onboardingStep7Title')}</h2>
              <p className={`text-sm ${textSub}`}>{t('onboardingStep7Desc')}</p>

              <div className={`w-full p-4 rounded-xl ${cardBg} space-y-2 text-left text-sm`}>
                <p className={textSub}>🌐 {t('language')}: <strong className={textMain}>{lang === 'es' ? 'Español' : 'English'}</strong></p>
                <p className={textSub}>🎨 {t('theme')}: <strong className={textMain}>{isDark ? t('darkMode') : t('lightMode')}</strong></p>
                <p className={textSub}>👤 {t('onboardingStep3NameLabel')}: <strong className={textMain}>{nickname || t('onboardingDefaultName')}</strong></p>
                <p className={textSub}>🧠 {t('onboardingStep5Title')}: <strong className={textMain}>{modelChoice === 'custom' ? t('modelCustomize') : t('modelUseDefaults')}</strong></p>
              </div>

              <motion.button
                whileTap={{ scale: 0.95 }}
                onClick={finish}
                className={`w-full py-4 rounded-xl text-lg font-semibold ${btnPrimary} shadow-lg shadow-[#006bbd]/25 animate-pulse`}
              >
                {t('onboardingStartNow')}
              </motion.button>

              <div className="flex flex-col items-center gap-1 mt-2">
                <a href={APP_CONFIG.repoUrl} target="_blank" rel="noopener noreferrer" className={`flex items-center gap-2 text-sm ${textSub} hover:text-[#006bbd] transition-colors`}>
                  <FaGithub size={18} />
                  <span>{APP_CONFIG.repoUrl.replace(/^https?:\/\//, '')}</span>
                </a>
                <p className={`text-xs mt-1`}>
                  <a href={APP_CONFIG.repoUrl} target="_blank" rel="noopener noreferrer" className="text-[#006bbd] hover:underline">
                    {t('onboardingStarRepo')}
                  </a>
                </p>
                <p className={`text-xs ${isDark ? 'text-white/30' : 'text-gray-400'}`}>{t('onboardingStarRepoDesc')}</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Bottom nav: Skip + Back/Next */}
        {step < 6 && (
          <div className="flex items-center gap-3">
            <motion.button
              whileTap={{ scale: 0.96 }}
              onClick={finish}
              disabled={finishing}
              className={`text-xs ${isDark ? 'text-white/30 hover:text-white/60' : 'text-gray-400 hover:text-gray-600'} transition-colors disabled:opacity-50`}
            >
              {t('onboardingSkip')}
            </motion.button>
            <div className="flex-1" />
            {step > 1 && (
              <motion.button whileTap={{ scale: 0.96 }} onClick={prev} disabled={finishing} className={`px-5 py-2.5 rounded-xl text-sm font-medium ${btnSecondary} active:scale-95 disabled:opacity-50`}>
                {t('onboardingBack')}
              </motion.button>
            )}
            <motion.button whileTap={{ scale: 0.96 }} onClick={saveAndNext} disabled={finishing} className={`px-5 py-2.5 rounded-xl text-sm font-medium ${btnPrimary} disabled:opacity-50`}>
              {finishing ? t('onboardingFinish') : step === 5 ? t('onboardingFinish') : t('onboardingNext')}
            </motion.button>
          </div>
        )}
      </div>
    </motion.div>
  );
}
