import { useEffect, useState } from 'react';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import ConfirmModal from './ConfirmModal';
import ErrorRepairModal from './ErrorRepairModal';
import PermissionNotice from './PermissionNotice';
import {
  deleteWebSearchCredential,
  getWebSearchSettings,
  notifyWebSearchSettingsUpdated,
  saveWebSearchSettings,
  resetWebSearchSettings,
  testWebSearchProvider,
  userFacingError,
  type WebSearchSettings as Settings,
} from '../lib/api';

const PROVIDERS = ['auto', 'duckduckgo', 'brave', 'searxng'] as const;
type Provider = typeof PROVIDERS[number];
const WEB_SEARCH_PROVIDER_KEY = 'tc-web-search-provider';

function validProvider(value: string | undefined, fallback: Provider = 'auto'): Provider {
  return PROVIDERS.includes(value as Provider) ? value as Provider : fallback;
}

function rememberedProvider(): Provider {
  try { return validProvider(localStorage.getItem(WEB_SEARCH_PROVIDER_KEY) || undefined); } catch { return 'auto'; }
}

export default function WebSearchSettings({ canManageSystem, onBack }: { canManageSystem: boolean; onBack?: () => void }) {
  const { t } = useI18n();
  const { isDark } = useTheme();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [provider, setProvider] = useState<Provider>(rememberedProvider());
  const [enabled, setEnabled] = useState(true);
  const [braveKey, setBraveKey] = useState('');
  const [searxngUrl, setSearxngUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [repairError, setRepairError] = useState('');
  const [repairOpen, setRepairOpen] = useState(false);
  const [confirmDeleteKey, setConfirmDeleteKey] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const card = isDark ? 'border-white/10 bg-white/[0.03]' : 'border-slate-200 bg-white';
  const input = isDark ? 'border-white/15 bg-black/20 text-white' : 'border-slate-200 bg-slate-50 text-slate-900';
  const muted = isDark ? 'text-white/65' : 'text-slate-600';
  const secondaryButton = `min-h-11 rounded-xl border px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] disabled:opacity-50 ${isDark ? 'border-white/15 text-white/85 hover:bg-white/[0.08]' : 'border-slate-200 text-slate-700 hover:bg-slate-50'}`;
  const clearMessage = () => {
    setMessage('');
    setRepairError('');
  };
  const showError = (error: unknown) => {
    const next = userFacingError(error, 'external_service_unavailable');
    setMessage(next);
    setRepairError(next);
  };

  useEffect(() => {
    if (!canManageSystem) return;
    const controller = new AbortController();
    getWebSearchSettings(controller.signal).then((value) => {
      const nextProvider = validProvider(value.preferred_provider, validProvider(value.active_provider, rememberedProvider()));
      setSettings(value); setEnabled(value.enabled);
      setProvider(nextProvider);
      if (value.enabled) {
        try { localStorage.setItem(WEB_SEARCH_PROVIDER_KEY, nextProvider); } catch { /* ignore */ }
      }
      setSearxngUrl(value.providers.searxng?.base_url || '');
    }).catch((error) => { if (!controller.signal.aborted) showError(error); });
    return () => controller.abort();
  }, [canManageSystem]);

  const save = async (): Promise<boolean> => {
    setBusy(true); clearMessage();
    try {
      const next = await saveWebSearchSettings({
        ...(!settings?.externally_managed.preferred_provider ? { enabled, preferred_provider: provider } : {}),
        ...(braveKey.trim() && !settings?.externally_managed.brave_api_key ? { brave_api_key: braveKey.trim() } : {}),
        ...(provider === 'searxng' && !settings?.externally_managed.searxng_url ? { searxng_url: searxngUrl.trim() } : {}),
      });
      setSettings(next);
      setEnabled(next.enabled);
      const nextProvider = validProvider(next.preferred_provider, provider);
      setProvider(nextProvider);
      if (next.enabled) {
        try { localStorage.setItem(WEB_SEARCH_PROVIDER_KEY, nextProvider); } catch { /* ignore */ }
      }
      setBraveKey('');
      notifyWebSearchSettingsUpdated(next);
      setMessage(t('webSearchSaved'));
      setRepairError('');
      return true;
    } catch (error) { showError(error); return false; }
    finally { setBusy(false); }
  };

  const test = async () => {
    setBusy(true); setMessage(t('webSearchTesting')); setRepairError('');
    try {
      if (braveKey.trim() || (provider === 'searxng' && searxngUrl.trim() !== settings?.providers.searxng?.base_url)) {
        if (!await save()) return;
        setBusy(true);
      }
      const result = await testWebSearchProvider(provider);
      setMessage(t('webSearchConnectionSuccess').replace('{provider}', result.provider));
    } catch (error) { showError(error); }
    finally { setBusy(false); }
  };

  if (!canManageSystem) return (
    <div className="fixed inset-0 z-[70]">
      <PermissionNotice feature="web" remoteWebSearch onBack={onBack ?? (() => undefined)} />
    </div>
  );
  const repairModal = (
    <ErrorRepairModal
      open={repairOpen}
      dark={isDark}
      title={t('errorRepairTitle')}
      message={t('errorRepairMessage')}
      details={repairError ? `${repairError}\n\n${t('errorRepairHint')}` : ''}
      confirmLabel={t('close')}
      showCancel={false}
      onConfirm={() => setRepairOpen(false)}
      onCancel={() => setRepairOpen(false)}
    />
  );
  if (!settings) return <>
    <section className={`rounded-2xl border p-5 ${card}`} aria-label={t('webSearchSettingsTitle')}>
      <p role={repairError ? 'alert' : 'status'} className={`text-sm leading-relaxed ${muted}`}>{message || t('webSearchLoading')}</p>
      {repairError && <button type="button" onClick={() => setRepairOpen(true)} className={`mt-2 min-h-11 rounded-lg px-2 text-sm font-medium underline underline-offset-2 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${isDark ? 'text-[#8ac9f5]' : 'text-[#0059a0]'}`}>{t('fixError')}</button>}
    </section>
    {repairModal}
  </>;
  const configured = settings.providers[provider]?.configured;
  const providerExternal = settings.externally_managed.preferred_provider;
  const hasExternal = Object.values(settings.externally_managed).some(Boolean);
  const feedback = repairError
    ? isDark ? 'border-red-400/25 bg-red-400/10 text-red-200' : 'border-red-200 bg-red-50 text-red-800'
    : isDark ? 'border-white/10 bg-white/[0.04] text-white/80' : 'border-slate-200 bg-slate-50 text-slate-700';

  const removeBraveKey = async () => {
    setBusy(true); clearMessage();
    try {
      const next = await deleteWebSearchCredential('brave');
      setSettings(next);
      setEnabled(next.enabled);
      setProvider(validProvider(next.preferred_provider, provider));
      notifyWebSearchSettingsUpdated(next);
    }
    catch (error) { showError(error); }
    finally { setBusy(false); }
  };

  const reset = async () => {
    setBusy(true); clearMessage();
    try {
      const next = await resetWebSearchSettings();
      setSettings(next);
      setEnabled(next.enabled);
      setProvider(validProvider(next.preferred_provider, provider));
      notifyWebSearchSettingsUpdated(next);
    }
    catch (error) { showError(error); }
    finally { setBusy(false); }
  };

  return <section className={`space-y-5 rounded-2xl border p-4 sm:p-5 ${card}`} aria-labelledby="web-search-settings-title">
    <div>
      <h2 id="web-search-settings-title" className={`text-lg font-semibold ${isDark ? 'text-white/90' : 'text-slate-900'}`}>{t('webSearchSettingsTitle')}</h2>
      <p className={`mt-1 text-sm leading-relaxed ${muted}`}>{t('webSearchCredentialsLocalOnly')}</p>
    </div>
    <label className={`flex min-h-11 cursor-pointer items-center justify-between gap-3 text-sm font-medium ${isDark ? 'text-white/85' : 'text-slate-800'}`}>
      <span>{t('webSearchEnable')}</span>
      <input name="web-search-enabled" type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} disabled={providerExternal || busy} className="h-5 w-5 shrink-0 accent-[#006bbd] disabled:opacity-50" />
    </label>
    <label className="block space-y-1">
      <span className={`text-sm font-medium ${isDark ? 'text-white/85' : 'text-slate-800'}`}>{t('webSearchPreferredProvider')}</span>
      <select name="web-search-provider" autoComplete="off" aria-label={t('webSearchPreferredProvider')} value={provider} onChange={(event) => setProvider(event.target.value as typeof provider)} disabled={providerExternal || busy} className={`min-h-11 w-full rounded-xl border px-3 py-2 text-base outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] disabled:opacity-50 sm:text-sm ${input}`}>
        <option value="auto">{t('webSearchAutomatic')}</option><option value="duckduckgo">DuckDuckGo</option><option value="brave">Brave Search</option><option value="searxng">SearXNG</option>
      </select>
    </label>
    {provider === 'auto' && <p className={`text-sm leading-relaxed ${muted}`}>{t('webSearchAutoDescription')}</p>}
    {provider === 'duckduckgo' && <p className={`text-sm leading-relaxed ${muted}`}>{t('webSearchDuckDescription')}</p>}
    {provider === 'brave' && <div className="space-y-1">
      <label className="block space-y-1">
        <span className={`text-sm font-medium ${isDark ? 'text-white/85' : 'text-slate-800'}`}>{t('webSearchBraveApiKey')} · {configured ? t('webSearchConfigured') : t('webSearchNotConfigured')}</span>
        <input name="brave-api-key" type="password" autoComplete="new-password" disabled={settings.externally_managed.brave_api_key || busy} value={braveKey} onChange={(event) => setBraveKey(event.target.value)} placeholder={configured ? t('webSearchReplaceKey') : 'BSA...'} className={`min-h-11 w-full rounded-xl border px-3 py-2 text-base outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] disabled:opacity-50 sm:text-sm ${input}`} />
      </label>
      {configured && !settings.externally_managed.brave_api_key && <button type="button" onClick={() => setConfirmDeleteKey(true)} className={`min-h-11 rounded-lg px-2 text-sm font-medium underline underline-offset-2 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${isDark ? 'text-red-300' : 'text-red-700'}`}>{t('webSearchDeleteKey')}</button>}
    </div>}
    {provider === 'searxng' && <label className="block space-y-1">
      <span className={`text-sm font-medium ${isDark ? 'text-white/85' : 'text-slate-800'}`}>{t('webSearchPublicSearxUrl')}</span>
      <input name="searxng-url" type="url" autoComplete="off" disabled={settings.externally_managed.searxng_url || busy} value={searxngUrl} onChange={(event) => setSearxngUrl(event.target.value)} placeholder="https://search.example.org..." className={`min-h-11 w-full rounded-xl border px-3 py-2 text-base outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] disabled:opacity-50 sm:text-sm ${input}`} />
    </label>}
    {hasExternal && <p className={`rounded-xl border px-3 py-2 text-sm leading-relaxed ${isDark ? 'border-amber-300/20 bg-amber-300/5 text-amber-200' : 'border-amber-200 bg-amber-50 text-amber-900'}`}>{t('webSearchEnvironmentManaged')}</p>}
    <div className="flex flex-wrap gap-2">
      <button type="button" disabled={busy} onClick={save} className="min-h-11 rounded-xl bg-[#006bbd] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#0059a0] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] disabled:opacity-50">{busy ? t('webSearchSaving') : t('save')}</button>
      <button type="button" disabled={busy} onClick={test} className={secondaryButton}>{t('webSearchTestButton')}</button>
      <button type="button" disabled={busy || hasExternal} onClick={() => setConfirmReset(true)} className={secondaryButton}>{t('webSearchResetButton')}</button>
    </div>
    {message && <div role={repairError ? 'alert' : 'status'} className={`rounded-xl border px-3 py-2 text-sm leading-relaxed ${feedback}`}>
      <p>{message}</p>
      {repairError && <button type="button" onClick={() => setRepairOpen(true)} className="mt-1 min-h-11 rounded-lg px-2 font-medium underline underline-offset-2 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed]">{t('fixError')}</button>}
    </div>}
    <ConfirmModal
      open={confirmDeleteKey}
      title={t('webSearchDeleteKey')}
      message={t('webSearchDeleteKeyConfirm')}
      confirmLabel={t('webSearchDeleteKey')}
      confirmDisabled={busy}
      danger
      onConfirm={() => { setConfirmDeleteKey(false); void removeBraveKey(); }}
      onCancel={() => setConfirmDeleteKey(false)}
    />
    <ConfirmModal
      open={confirmReset}
      title={t('webSearchResetButton')}
      message={t('webSearchResetConfirm')}
      confirmLabel={t('webSearchResetButton')}
      confirmDisabled={busy}
      danger
      onConfirm={() => { setConfirmReset(false); void reset(); }}
      onCancel={() => setConfirmReset(false)}
    />
    {repairModal}
  </section>;
}
