import { useEffect, useState } from 'react';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import {
  deleteWebSearchCredential,
  getWebSearchSettings,
  saveWebSearchSettings,
  resetWebSearchSettings,
  testWebSearchProvider,
  type WebSearchSettings as Settings,
} from '../lib/api';

const PROVIDERS = ['auto', 'duckduckgo', 'brave', 'searxng'] as const;

export default function WebSearchSettings({ canManageSystem }: { canManageSystem: boolean }) {
  const { lang } = useI18n();
  const { isDark } = useTheme();
  const es = lang === 'es';
  const [settings, setSettings] = useState<Settings | null>(null);
  const [provider, setProvider] = useState<'auto' | 'duckduckgo' | 'brave' | 'searxng'>('auto');
  const [enabled, setEnabled] = useState(true);
  const [braveKey, setBraveKey] = useState('');
  const [searxngUrl, setSearxngUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const card = isDark ? 'border-white/10 bg-white/[0.03]' : 'border-gray-200 bg-gray-50';
  const input = isDark ? 'border-white/10 bg-black/20 text-white' : 'border-gray-200 bg-white text-gray-900';

  useEffect(() => {
    const controller = new AbortController();
    getWebSearchSettings(controller.signal).then((value) => {
      setSettings(value); setEnabled(value.enabled);
      if (PROVIDERS.includes(value.preferred_provider as typeof PROVIDERS[number])) {
        setProvider(value.preferred_provider as typeof provider);
      } else setProvider(value.active_provider as typeof provider);
      setSearxngUrl(value.providers.searxng?.base_url || '');
    }).catch((error) => { if (!controller.signal.aborted) setMessage(String(error?.message || error)); });
    return () => controller.abort();
  }, []);

  const save = async (): Promise<boolean> => {
    setBusy(true); setMessage('');
    try {
      const next = await saveWebSearchSettings({
        ...(!settings?.externally_managed.preferred_provider ? { enabled, preferred_provider: provider } : {}),
        ...(braveKey.trim() && !settings?.externally_managed.brave_api_key ? { brave_api_key: braveKey.trim() } : {}),
        ...(provider === 'searxng' && !settings?.externally_managed.searxng_url ? { searxng_url: searxngUrl.trim() } : {}),
      });
      setSettings(next); setBraveKey('');
      setMessage(es ? 'Configuración guardada.' : 'Settings saved.');
      return true;
    } catch (error) { setMessage(String((error as Error).message)); return false; }
    finally { setBusy(false); }
  };

  const test = async () => {
    setBusy(true); setMessage(es ? 'Probando conexión…' : 'Testing connection…');
    try {
      if (braveKey.trim() || (provider === 'searxng' && searxngUrl.trim() !== settings?.providers.searxng?.base_url)) {
        if (!await save()) return;
        setBusy(true);
      }
      const result = await testWebSearchProvider(provider);
      setMessage((es ? 'Conexión correcta: ' : 'Connection successful: ') + result.provider);
    } catch (error) { setMessage(String((error as Error).message)); }
    finally { setBusy(false); }
  };

  if (!canManageSystem) return <p role="alert">{es ? 'Se requiere el permiso system.' : 'The system permission is required.'}</p>;
  if (!settings) return <p>{message || (es ? 'Cargando…' : 'Loading…')}</p>;
  const configured = settings.providers[provider]?.configured;
  const providerExternal = settings.externally_managed.preferred_provider;
  const hasExternal = Object.values(settings.externally_managed).some(Boolean);

  const removeBraveKey = async () => {
    if (!window.confirm(es ? '¿Eliminar API key?' : 'Delete API key?')) return;
    setBusy(true); setMessage('');
    try { setSettings(await deleteWebSearchCredential('brave')); }
    catch (error) { setMessage(String((error as Error).message)); }
    finally { setBusy(false); }
  };

  const reset = async () => {
    if (!window.confirm(es ? '¿Restablecer la búsqueda web?' : 'Reset web-search settings?')) return;
    setBusy(true); setMessage('');
    try { setSettings(await resetWebSearchSettings()); }
    catch (error) { setMessage(String((error as Error).message)); }
    finally { setBusy(false); }
  };

  return <section className={`rounded-xl border p-4 space-y-4 ${card}`} aria-labelledby="web-search-settings-title">
    <div>
      <h3 id="web-search-settings-title" className="font-semibold">{es ? 'Búsqueda web' : 'Web search'}</h3>
      <p className="text-xs opacity-60">{es ? 'Las credenciales se guardan únicamente en el backend local.' : 'Credentials are stored only by the local backend.'}</p>
    </div>
    <label className="flex items-center justify-between gap-3">
      <span>{es ? 'Activar búsqueda web' : 'Enable web search'}</span>
      <input name="web-search-enabled" type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} disabled={providerExternal || busy} />
    </label>
    <label className="block space-y-1">
      <span>{es ? 'Motor de búsqueda preferido' : 'Preferred search engine'}</span>
      <select name="web-search-provider" autoComplete="off" aria-label={es ? 'Motor de búsqueda preferido' : 'Preferred search engine'} value={provider} onChange={(event) => setProvider(event.target.value as typeof provider)} disabled={providerExternal || busy} className={`w-full rounded-lg border p-2 ${input}`}>
        <option value="auto">{es ? 'Automático' : 'Automatic'}</option><option value="duckduckgo">DuckDuckGo</option><option value="brave">Brave Search</option><option value="searxng">SearXNG</option>
      </select>
    </label>
    {provider === 'auto' && <p className="text-sm">{es ? 'Usa Brave o SearXNG si están configurados; después DuckDuckGo y el fallback público integrado.' : 'Uses configured Brave or SearXNG first, then DuckDuckGo and the built-in public fallback.'}</p>}
    {provider === 'duckduckgo' && <p className="text-sm">{es ? 'No requiere API key; puede aplicar límites contra automatización.' : 'No API key required; automated searches may be rate-limited.'}</p>}
    {provider === 'brave' && <label className="block space-y-1">
      <span>Brave Search API key — {configured ? (es ? 'Configurada' : 'Configured') : (es ? 'No configurada' : 'Not configured')}</span>
      <input name="brave-api-key" type="password" autoComplete="new-password" disabled={settings.externally_managed.brave_api_key || busy} value={braveKey} onChange={(event) => setBraveKey(event.target.value)} placeholder={configured ? (es ? 'Configurada — introduce una nueva para reemplazarla' : 'Configured — enter a new value to replace it') : 'BSA…'} className={`w-full rounded-lg border p-2 disabled:opacity-60 ${input}`} />
      {configured && !settings.externally_managed.brave_api_key && <button type="button" onClick={removeBraveKey} className="text-sm text-red-500">{es ? 'Eliminar API key' : 'Delete API key'}</button>}
    </label>}
    {provider === 'searxng' && <label className="block space-y-1">
      <span>{es ? 'URL pública de la instancia SearXNG' : 'Public SearXNG instance URL'}</span>
      <input name="searxng-url" type="url" autoComplete="off" disabled={settings.externally_managed.searxng_url || busy} value={searxngUrl} onChange={(event) => setSearxngUrl(event.target.value)} placeholder="https://search.example.org…" className={`w-full rounded-lg border p-2 disabled:opacity-60 ${input}`} />
    </label>}
    {hasExternal && <p className="text-sm text-amber-500">{es ? 'Algunos campos están configurados mediante variables de entorno.' : 'Some fields are managed by environment variables.'}</p>}
    <div className="flex flex-wrap gap-2">
      <button type="button" disabled={busy} onClick={save} className="rounded-lg bg-[#006bbd] px-4 py-2 text-white disabled:opacity-50">{busy ? (es ? 'Guardando…' : 'Saving…') : (es ? 'Guardar' : 'Save')}</button>
      <button type="button" disabled={busy} onClick={test} className="rounded-lg border px-4 py-2 disabled:opacity-50">{es ? 'Probar conexión' : 'Test connection'}</button>
      <button type="button" disabled={busy || hasExternal} onClick={reset} className="rounded-lg border px-4 py-2 disabled:opacity-50">{es ? 'Restablecer' : 'Reset'}</button>
    </div>
    {message && <p role="status" className="text-sm">{message}</p>}
  </section>;
}
