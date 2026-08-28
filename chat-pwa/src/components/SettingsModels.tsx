import { useEffect, useRef, useState } from 'react';
import { MdKeyboardArrowDown, MdKeyboardArrowRight, MdTune } from 'react-icons/md';

import { useI18n } from '../i18n/I18nContext';
import {
  OLLAMA_KEEP_ALIVE_DEFAULT,
  reconcileManagedModels,
  userFacingError,
  type ModelPreset,
  type ModelSettingKey,
} from '../lib/api';
import { APP_CONFIG } from '../lib/config';
import { systemFetch } from '../lib/authHeaders';
import type { TranslationKey } from '../i18n/translations';
import { useToast } from './Toast';

const MODEL_SETTING_KEYS = [
  'tc-models-chat',
  'tc-models-deep',
  'tc-models-vision',
  'tc-models-embed',
  'tc-models-code',
  'tc-models-fast',
] as const;

interface Props {
  isDark: boolean;
  detectedProfile: ModelPreset | null;
  btnBase: string;
  bgCard: string;
  textHeading: string;
  textLabel: string;
  setLocalSetting: (key: string, value: string) => void;
  setModelPreset: (preset: ModelPreset) => void;
  getModel: (key: ModelSettingKey) => string;
}

export default function SettingsModels({
  isDark,
  detectedProfile,
  btnBase,
  bgCard,
  textHeading,
  textLabel,
  setLocalSetting,
  setModelPreset,
  getModel,
}: Props) {
  const { t } = useI18n();
  const toast = useToast();
  const [expanded, setExpanded] = useState(false);
  const [pulling, setPulling] = useState(false);
  const [pullProgress, setPullProgress] = useState<{ model: string; percent: number } | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  const getKeepAlive = () => localStorage.getItem('tc-keep-alive') || OLLAMA_KEEP_ALIVE_DEFAULT;
  const presetLabels: Record<ModelPreset, TranslationKey> = {
    '8gb': 'modelPreset8gb',
    '16gb': 'modelPreset16gb',
    '32gb': 'modelPreset32gb',
    '64gb': 'modelPreset64gb',
  };

  const pullModels = async () => {
    if (pulling) return;
    const models = Array.from(new Set(MODEL_SETTING_KEYS.map((key) => getModel(key)).filter(Boolean)));
    if (!models.length) {
      toast.toast(t('modelPullFailed').replace('{model}', t('noConfiguredModel')), 'error');
      return;
    }
    const controller = new AbortController();
    abortRef.current = controller;
    setPulling(true);
    setPullProgress(null);
    toast.toast(t('modelPulling').replace('{model}', models.join(', ')), 'info');
    try {
      await reconcileManagedModels(models, (model, completed, total) => {
        setPullProgress({ model, percent: total > 0 ? Math.round((completed / total) * 100) : 0 });
      }, controller.signal);
      toast.toast(t('modelReady').replace('{model}', models.join(', ')), 'success');
    } catch (error) {
      const cancelled = controller.signal.aborted;
      toast.toast(cancelled
        ? t('modelPullCancelled')
        : `${t('modelPullFailed').replace('{model}', models.join(', '))} ${userFacingError(error, 'network_timeout')}`,
      cancelled ? 'info' : 'error');
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      setPulling(false);
    }
  };

  const unloadModels = async () => {
    const models = Array.from(new Set(MODEL_SETTING_KEYS.map((key) => getModel(key)).filter(Boolean)));
    let unloaded = 0;
    for (const model of models) {
      try {
        await systemFetch(`${APP_CONFIG.ollamaBase}/api/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model, keep_alive: 0, prompt: '' }),
        });
        unloaded++;
      } catch { /* best effort: another model can still be unloaded */ }
    }
    toast.toast(t('modelsUnloaded').replace('{ok}', String(unloaded)).replace('{total}', String(models.length)), 'info');
  };

  return (
    <section className="min-w-0 max-w-full overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        className={`mb-3 flex w-full items-center text-xs font-medium uppercase tracking-widest ${textHeading} hover:opacity-80`}
      >
        <span className="inline-flex min-w-0 items-center gap-2">
          <MdTune size={16} aria-hidden="true" />
          <span className="truncate">{t('modelCustomize')}</span>
          {expanded
            ? <MdKeyboardArrowDown aria-hidden="true" size={19} className={isDark ? 'text-white' : 'text-black'} />
            : <MdKeyboardArrowRight aria-hidden="true" size={19} className={isDark ? 'text-white' : 'text-black'} />}
        </span>
      </button>
      {expanded && (
        <div className="space-y-2 min-w-0 max-w-full">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {(['8gb', '16gb', '32gb', '64gb'] as const).map((preset) => (
              <button key={preset} type="button" onClick={() => setModelPreset(preset)} className={`min-w-0 rounded-lg px-2 py-2 text-[11px] font-medium break-words ${btnBase}`}>
                {t(presetLabels[preset])}
              </button>
            ))}
          </div>
          {detectedProfile && <p className={`text-[11px] ${textHeading}`}>{t('hardwareProfile')}: {detectedProfile}</p>}
          {MODEL_SETTING_KEYS.map((key) => {
            const labelKey: Record<ModelSettingKey, TranslationKey> = {
              'tc-models-chat': 'modelChat',
              'tc-models-deep': 'modelDeep',
              'tc-models-vision': 'modelVision',
              'tc-models-embed': 'modelEmbedding',
              'tc-models-code': 'modelCode',
              'tc-models-fast': 'modelFast',
            };
            const label = t(labelKey[key]);
            const isEmbed = key === 'tc-models-embed';
            return (
              <div key={key} className={`flex min-w-0 max-w-full flex-col gap-1.5 overflow-hidden rounded-lg px-3 py-2 sm:flex-row sm:items-center sm:gap-2 ${bgCard}`}>
                <span className={`min-w-0 break-words text-[10px] leading-tight sm:w-24 sm:shrink-0 ${textHeading}`}>{label}</span>
                {isEmbed ? (
                  <select
                    aria-label={label}
                    value={getModel(key)}
                    onChange={(event) => setLocalSetting(key, event.target.value)}
                    className={`min-w-0 max-w-full flex-1 border-b border-transparent bg-transparent px-1 py-0.5 text-[11px] font-mono outline-none transition-colors hover:border-[#006bbd]/30 focus:border-[#006bbd] ${isDark ? 'text-white/70' : 'text-gray-700'}`}
                  >
                    <option value="qwen3-embedding:0.6b">qwen3-embedding:0.6b | 1024d</option>
                    <option value="qwen3-embedding:4b">qwen3-embedding:4b | 2560d</option>
                    <option value="bge-m3">bge-m3 | 1024d | {t('modelEmbeddingBge')}</option>
                    <option value="nomic-embed-text">nomic-embed-text | 768d | {t('modelEmbeddingNomic')}</option>
                    <option value="all-minilm">all-minilm | 384d | {t('modelEmbeddingMini')}</option>
                    <option value="mxbai-embed-large">mxbai-embed-large | 1024d</option>
                  </select>
                ) : (
                  <input
                    aria-label={label}
                    value={getModel(key)}
                    onChange={(event) => setLocalSetting(key, event.target.value)}
                    onBlur={(event) => {
                      const value = event.target.value.trim();
                      if (value && value !== event.target.value) setLocalSetting(key, value);
                    }}
                    onKeyDown={(event) => {
                      if (event.key !== 'Enter') return;
                      const value = event.currentTarget.value.trim();
                      if (value) setLocalSetting(key, value);
                      event.currentTarget.blur();
                    }}
                    className={`min-w-0 w-full max-w-full flex-1 border-b border-transparent bg-transparent px-1 py-0.5 text-[11px] font-mono outline-none transition-colors hover:border-[#006bbd]/30 focus:border-[#006bbd] ${isDark ? 'text-white/70' : 'text-gray-700'}`}
                  />
                )}
              </div>
            );
          })}
          <div className="flex flex-col gap-2 sm:flex-row">
            <button type="button" onClick={() => void pullModels()} disabled={pulling} className="min-w-0 flex-1 rounded-lg bg-[#006bbd] px-3 py-2 text-xs font-medium text-white transition-[background-color,transform] hover:bg-[#0059a0] active:scale-95 disabled:cursor-wait disabled:opacity-60">
              {pulling && pullProgress ? `${pullProgress.model} ${pullProgress.percent}%` : pulling ? t('modelPulling').replace('{model}', '') : t('modelSaveAndPull')}
            </button>
            {pulling && <button type="button" onClick={() => abortRef.current?.abort()} className="min-w-0 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs font-medium text-red-400 hover:bg-red-500/20">{t('modelPullCancel')}</button>}
            <button type="button" onClick={() => setModelPreset(detectedProfile || '16gb')} className={`min-w-0 rounded-lg px-3 py-2 text-xs font-medium ${btnBase}`}>{t('modelRestoreDefaults')}</button>
          </div>
          <div className={`rounded-xl border p-3 ${bgCard}`}>
            <p className={`text-xs font-semibold ${textLabel}`}>{t('modelHelpTitle')}</p>
            <p className={`mt-1 text-[11px] leading-relaxed ${textHeading}`}>{t('modelHelpDescription')}</p>
            <a href="https://www.canirun.ai" target="_blank" rel="noopener noreferrer" className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-[#006bbd]/20 bg-[#006bbd]/5 px-3 py-2 text-left transition-[background-color,border-color] hover:border-[#006bbd]/50 hover:bg-[#006bbd]/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4aa7ed]">
              <span className="min-w-0"><span className={`block text-xs font-medium ${textLabel}`}>{t('modelCanIRunLabel')}</span><span className={`mt-0.5 block text-[11px] leading-relaxed ${textHeading}`}>{t('modelCanIRunDescription')}</span></span>
              <span className="shrink-0 text-xs font-medium text-[#4aa7ed]">canirun.ai -&gt;</span>
            </a>
            <details className="mt-2 rounded-lg border border-dashed border-[#006bbd]/25 px-3 py-2">
              <summary className={`cursor-pointer text-xs font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${textLabel}`}>{t('modelPromptTitle')}</summary>
              <p className={`mt-2 text-[11px] leading-relaxed ${textHeading}`}>{t('modelPromptDescription')}</p>
              <pre className={`mt-2 max-h-56 overflow-y-auto whitespace-pre-wrap break-words rounded-lg p-2 text-[10px] leading-relaxed ${isDark ? 'bg-black/30 text-white/60' : 'bg-gray-100 text-gray-600'}`}>{t('modelPromptText')}</pre>
              <button type="button" onClick={() => { void navigator.clipboard?.writeText(t('modelPromptText')).then(() => toast.toast(t('modelPromptCopied'), 'success')); }} className="mt-2 rounded-lg bg-[#006bbd]/15 px-3 py-2 text-xs font-medium text-[#006bbd] transition-[background-color,transform] hover:bg-[#006bbd]/25 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4aa7ed] active:scale-95">{t('modelPromptCopy')}</button>
            </details>
          </div>
          <div className={`mt-3 space-y-3 rounded-lg border p-3 ${bgCard}`}>
            <div className={`text-[10px] uppercase tracking-widest ${textHeading}`}>{t('performance')}</div>
            <label className="flex cursor-pointer items-start justify-between gap-2"><span className="min-w-0"><span className={`block break-words text-xs ${textLabel}`}>{t('thinkingMode')}</span><span className={`mt-0.5 block text-[11px] leading-relaxed ${textHeading}`}>{t('thinkingModeDescription')}</span></span><input type="checkbox" aria-label={t('thinkingMode')} checked={localStorage.getItem('tc-thinking-mode') !== '0'} onChange={(event) => setLocalSetting('tc-thinking-mode', event.target.checked ? '1' : '0')} className="mt-0.5 accent-[#006bbd]" /></label>
            <label className="flex cursor-pointer items-center justify-between gap-2"><span className={`min-w-0 break-words text-xs ${textLabel}`}>{t('aggressiveQuant')}</span><input type="checkbox" checked={localStorage.getItem('tc-aggressive-quant') === '1'} onChange={(event) => setLocalSetting('tc-aggressive-quant', event.target.checked ? '1' : '0')} className="accent-[#006bbd]" /></label>
            <div className="space-y-1"><div className="flex items-center justify-between gap-2"><span className={`min-w-0 break-words text-xs ${textLabel}`}>{t('keepModelsLoaded')}</span><span className={`text-[10px] font-mono ${textHeading}`}>{getKeepAlive()}</span></div><input type="range" aria-label={t('keepModelsLoaded')} min="0" max="60" step="5" value={parseInt(getKeepAlive().replace(/[^0-9]/g, '') || '0', 10)} onChange={(event) => setLocalSetting('tc-keep-alive', event.target.value === '0' ? '0s' : `${event.target.value}m`)} className="w-full accent-[#006bbd]" /><div className={`flex justify-between text-[9px] ${textHeading}`}><span>{t('keepAliveOff')}</span><span>30m</span><span>60m</span></div></div>
            <button type="button" onClick={() => void unloadModels()} className={`w-full rounded-lg py-2 text-xs font-medium ${btnBase}`}>{t('unloadAllModelsNow')}</button>
          </div>
        </div>
      )}
    </section>
  );
}
