import { useCallback, useEffect, useRef, useState } from 'react';
import { MdClose, MdContentCopy, MdDeleteOutline, MdLan, MdOpenInNew, MdRefresh } from 'react-icons/md';
import { systemFetch } from '../lib/authHeaders';
import { wipeRevokedDeviceData } from '../lib/deviceWipe';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';

interface NetworkInfo {
  online: true;
  recommendedUrl: string;
  urls: string[];
  needsRefresh: boolean;
  refreshCommand: string;
  capabilities?: { manageSystem?: boolean };
}

const DISMISSED_KEY = 'tc-network-notice-dismissed';

export default function NetworkNotice({ canManageSystem }: { canManageSystem: boolean }) {
  const { t } = useI18n();
  const { isDark } = useTheme();
  const [info, setInfo] = useState<NetworkInfo | null>(null);
  const [offline, setOffline] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [readyUrl, setReadyUrl] = useState('');
  const [copied, setCopied] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [dismissed, setDismissed] = useState('');
  const copyResetTimer = useRef<number | null>(null);

  const check = useCallback(async () => {
    try {
      const response = await fetch('/api/network', { cache: 'no-store', signal: AbortSignal.timeout(4000) });
      if (!response.ok) throw new Error('network status failed');
      setInfo(await response.json() as NetworkInfo);
      setOffline(false);
    } catch {
      setOffline(true);
    }
  }, []);

  const handleOffline = useCallback(() => setOffline(true), []);

  // Dismissal is keyed by the detected addresses so a later network change asks again.
  const signature = offline ? 'offline' : (info?.urls || []).join('|');
  const dismiss = () => {
    setDismissed(signature);
    try {
      localStorage.setItem(DISMISSED_KEY, signature);
    } catch { /* Private browsing keeps the notice for the current session only. */ }
  };

  useEffect(() => {
    try {
      setDismissed(localStorage.getItem(DISMISSED_KEY) || '');
    } catch { /* Storage is unavailable; the notice stays visible. */ }
    void check();
    window.addEventListener('online', check);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', check);
      window.removeEventListener('offline', handleOffline);
      if (copyResetTimer.current !== null) window.clearTimeout(copyResetTimer.current);
    };
  }, [check, handleOffline]);

  const copyCommand = async () => {
    try {
      await navigator.clipboard.writeText(info?.refreshCommand || 'trinaxai network refresh');
      setCopied(true);
      if (copyResetTimer.current !== null) window.clearTimeout(copyResetTimer.current);
      copyResetTimer.current = window.setTimeout(() => {
        setCopied(false);
        copyResetTimer.current = null;
      }, 1800);
    } catch { /* The command remains visible for manual copying. */ }
  };

  const refreshNetwork = async () => {
    setRefreshing(true);
    try {
      const response = await systemFetch('/api/system/network-refresh', { method: 'POST' });
      const result = await response.json() as NetworkInfo & { ok?: boolean };
      if (!response.ok || !result.ok) throw new Error('refresh failed');
      setReadyUrl(result.recommendedUrl);
      setInfo(result);
    } catch {
      await copyCommand();
      setOffline(true);
    } finally {
      setRefreshing(false);
    }
  };

  const removeOldPwa = async () => {
    if (!window.confirm(t('networkRemoveOldConfirm'))) return;
    setRemoving(true);
    await wipeRevokedDeviceData();
    window.location.reload();
  };

  if (!offline && !readyUrl && !info?.needsRefresh) return null;
  if (!readyUrl && dismissed === signature) return null;
  const command = info?.refreshCommand || 'trinaxai network refresh';

  return (
    <aside
      role="status"
      aria-live="polite"
      className={`fixed inset-x-3 bottom-[calc(env(safe-area-inset-bottom,0px)+6rem)] z-[65] mx-auto max-w-xl rounded-2xl border p-4 shadow-2xl backdrop-blur-xl ${
        isDark ? 'border-amber-300/25 bg-[#111827]/95 text-white' : 'border-amber-500/30 bg-white/95 text-gray-900'
      }`}
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-amber-400/15 text-amber-500">
          <MdLan size={20} aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold">{readyUrl ? t('networkReadyTitle') : offline ? t('networkOfflineTitle') : t('networkChangedTitle')}</h2>          <p className={`mt-1 text-xs leading-relaxed ${isDark ? 'text-white/65' : 'text-gray-600'}`}>
            {readyUrl ? t('networkReadyHint') : offline ? t('networkOfflineHint') : t('networkChangedHint')}
          </p>
          {readyUrl ? (
            <a href={readyUrl} className="mt-2 block break-all font-mono text-xs text-[#168de2] underline underline-offset-2">
              {readyUrl}
            </a>
          ) : (
            <code className={`mt-2 block select-all rounded-lg px-2.5 py-2 text-xs ${isDark ? 'bg-black/35 text-white/80' : 'bg-gray-100 text-gray-700'}`}>
              {command}
            </code>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            {readyUrl ? (
              <a href={readyUrl} className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-[#006bbd] px-3 py-2 text-xs font-semibold text-white">
                <MdOpenInNew size={16} /> {t('networkOpenNewLink')}
              </a>
            ) : (info?.capabilities?.manageSystem ?? canManageSystem) && !offline ? (
              <button type="button" onClick={refreshNetwork} disabled={refreshing} className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-[#006bbd] px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">
                <MdRefresh className={refreshing ? 'animate-spin' : ''} size={16} />
                {refreshing ? t('networkRefreshing') : t('networkPrepare')}
              </button>
            ) : null}
            {!readyUrl && (
              <button type="button" onClick={copyCommand} className={`inline-flex min-h-10 items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold ${isDark ? 'border-white/15 text-white/75' : 'border-gray-200 text-gray-700'}`}>
                <MdContentCopy size={15} /> {copied ? t('copied') : t('networkCopyCommand')}
              </button>
            )}
            {offline && (
              <>
                <button type="button" onClick={() => void check()} className={`inline-flex min-h-10 items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold ${isDark ? 'border-white/15 text-white/75' : 'border-gray-200 text-gray-700'}`}>
                  <MdRefresh size={15} /> {t('networkRetry')}
                </button>
                <button type="button" onClick={() => void removeOldPwa()} disabled={removing} className={`inline-flex min-h-10 items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold disabled:opacity-50 ${isDark ? 'border-red-300/25 text-red-200' : 'border-red-200 text-red-700'}`}>
                  <MdDeleteOutline size={16} /> {removing ? t('networkRemovingOld') : t('networkRemoveOld')}
                </button>
              </>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={dismiss}
          aria-label={t('close')}
          className={`-mr-1 -mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-xl ${isDark ? 'text-white/55 hover:text-white' : 'text-gray-400 hover:text-gray-700'}`}
        >
          <MdClose size={18} />
        </button>
      </div>
    </aside>
  );
}
