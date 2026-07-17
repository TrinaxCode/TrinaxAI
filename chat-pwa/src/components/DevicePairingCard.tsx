import { useEffect, useState } from 'react';
import { MdCheck, MdContentCopy, MdDevices, MdLink, MdLinkOff } from 'react-icons/md';

import { useI18n } from '../i18n/I18nContext';
import {
  claimDevice,
  createPairingCode,
  getCurrentPairedDevice,
  listPairedDevices,
  revokePairedDevice,
  revokeCurrentPairedDevice,
  type PairedDevice,
} from '../lib/devicePairing';
import ConfirmModal from './ConfirmModal';

function pairingCodeFromLocation(): string {
  try {
    const direct = new URLSearchParams(window.location.search).get('pair');
    if (direct) return direct;
    const query = window.location.hash.split('?', 2)[1] || '';
    return new URLSearchParams(query).get('pair') || '';
  } catch { return ''; }
}

function clearPairingCodeFromLocation(): void {
  try {
    const url = new URL(window.location.href);
    url.searchParams.delete('pair');
    if (url.hash.includes('?')) url.hash = url.hash.split('?', 1)[0];
    window.history.replaceState(window.history.state, '', url);
  } catch { /* history may be unavailable in embedded webviews */ }
}

function formatPairingCode(value: string): string {
  const compact = value.replace(/[^a-z0-9]/gi, '').slice(0, 8).toUpperCase();
  return compact.length > 4 ? `${compact.slice(0, 4)}-${compact.slice(4)}` : compact;
}

export default function DevicePairingCard({ isDark }: { isDark: boolean }) {
  const { t } = useI18n();
  const [code, setCode] = useState(() => formatPairingCode(pairingCodeFromLocation()));
  const [name, setName] = useState(() => {
    try {
      const modern = navigator as Navigator & { userAgentData?: { platform?: string } };
      return modern.userAgentData?.platform || navigator.platform || 'Browser';
    }
    catch { return 'Browser'; }
  });
  const [device, setDevice] = useState<PairedDevice | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [generatedCode, setGeneratedCode] = useState('');
  const [generating, setGenerating] = useState(false);
  const [showGeneratedCode, setShowGeneratedCode] = useState(false);
  const [copiedCode, setCopiedCode] = useState(false);
  const [managedDevices, setManagedDevices] = useState<PairedDevice[]>([]);
  const [revokingId, setRevokingId] = useState('');
  const [pendingRevokeId, setPendingRevokeId] = useState<string | null>(null);
  const [canManageDevices, setCanManageDevices] = useState(false);

  const loadManagedDevices = async () => {
    try {
      setManagedDevices(await listPairedDevices());
      setCanManageDevices(true);
    } catch {
      setManagedDevices([]);
      setCanManageDevices(false);
    }
  };

  useEffect(() => {
    let active = true;
    void getCurrentPairedDevice()
      .then((value) => { if (active) setDevice(value); })
      .catch(() => { if (active) setDevice(null); });
    void loadManagedDevices();
    return () => { active = false; };
  }, []);

  const pair = async () => {
    if (!code.trim() || !name.trim()) return;
    setBusy(true); setError('');
    try {
      setDevice(await claimDevice(code, name));
      setCode('');
      clearPairingCodeFromLocation();
      window.dispatchEvent(new Event('trinaxai-device-paired'));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('devicePairingFailed'));
    } finally { setBusy(false); }
  };

  const generate = async () => {
    setGenerating(true); setError('');
    try {
      const result = await createPairingCode();
      setGeneratedCode(result.code);
      setCopiedCode(false);
      setShowGeneratedCode(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('devicePairingGenerateFailed'));
    } finally { setGenerating(false); }
  };

  const revokeManaged = async (deviceId: string) => {
    setRevokingId(deviceId); setError('');
    try {
      await revokePairedDevice(deviceId);
      await loadManagedDevices();
      if (device?.id === deviceId) setDevice(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('deviceRevokeFailed'));
    } finally { setRevokingId(''); }
  };

  const copyGeneratedCode = async () => {
    try {
      await navigator.clipboard?.writeText(generatedCode);
      setCopiedCode(true);
      window.setTimeout(() => setCopiedCode(false), 2200);
    } catch { /* copy is optional; the visible code remains usable */ }
  };

  const revoke = async () => {
    setBusy(true); setError('');
    try {
      await revokeCurrentPairedDevice();
      setDevice(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('deviceRevokeFailed'));
    } finally { setBusy(false); }
  };

  const border = isDark ? 'border-white/[0.08]' : 'border-gray-200';
  const muted = isDark ? 'text-white/40' : 'text-gray-500';
  const text = isDark ? 'text-white/80' : 'text-gray-800';
  return (
    <div className={`mb-3 rounded-xl border px-4 py-3 space-y-3 ${border} ${isDark ? 'bg-white/[0.03]' : 'bg-gray-50'}`}>
      <div className="flex items-center gap-2">
        <MdDevices size={18} className="text-[#006bbd]" aria-hidden="true" />
        <h4 className={`text-xs font-medium ${text}`}>{t('devicePairingTitle')}</h4>
      </div>
      {device ? (
        <div className="space-y-2">
          <p className={`text-sm ${text}`}>{device.name}</p>
          <p className={`text-[10px] break-words ${muted}`}>
            {t('deviceScopes')}: {device.scopes.join(', ')}
          </p>
          {!device.scopes.includes('system') && (
            <p className={`text-[10px] leading-relaxed ${muted}`}>{t('deviceSystemScopeHint')}</p>
          )}
          <button
            type="button"
            disabled={busy}
            onClick={() => setPendingRevokeId(device.id)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-red-500/20 px-3 py-2 text-xs font-medium text-red-400 hover:bg-red-500/10 disabled:opacity-50"
          >
            <MdLinkOff size={15} aria-hidden="true" /> {t('deviceRevoke')}
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <p className={`text-[10px] leading-relaxed ${muted}`}>{t('devicePairingHint')}</p>
          {canManageDevices && (
            <button
              type="button"
              disabled={generating}
              onClick={() => { void generate(); }}
              className="inline-flex items-center rounded-lg border border-[#006bbd]/40 px-3 py-2 text-xs font-medium text-[#4aa7ed] hover:bg-[#006bbd]/10 disabled:opacity-50"
            >
              {generating ? t('loading') : t('devicePairingGenerate')}
            </button>
          )}
          <div className="grid gap-2 sm:grid-cols-2">
            <input
              aria-label={t('devicePairingCode')}
              inputMode="text"
              autoCapitalize="characters"
              autoComplete="one-time-code"
              value={code}
              onChange={(event) => setCode(formatPairingCode(event.target.value))}
              placeholder={t('devicePairingCode')}
              className={`rounded-lg border bg-transparent px-3 py-2 text-sm font-mono outline-none ${border} ${text}`}
            />
            <input
              aria-label={t('deviceName')}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={t('deviceName')}
              className={`rounded-lg border bg-transparent px-3 py-2 text-sm outline-none ${border} ${text}`}
            />
          </div>
          <button
            type="button"
            disabled={busy || !code.trim() || !name.trim()}
            onClick={() => { void pair(); }}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#006bbd] px-3 py-2 text-xs font-medium text-white hover:bg-[#005ca3] disabled:opacity-50"
          >
            <MdLink size={15} aria-hidden="true" /> {busy ? t('loading') : t('devicePair')}
          </button>
        </div>
      )}
      {managedDevices.filter((item) => item.revoked_at === null).length > 0 && (
        <div className={`border-t pt-3 ${border}`}>
          <p className={`mb-2 text-[10px] uppercase tracking-wider ${muted}`}>{t('devicePairedDevices')}</p>
          <div className="space-y-2">
            {managedDevices.filter((item) => item.revoked_at === null).map((item) => (
              <div key={item.id} className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className={`truncate text-xs ${text}`}>{item.name}</p>
                  <p className={`truncate text-[10px] ${muted}`}>{item.scopes.join(', ')}</p>
                </div>
                <button type="button" disabled={Boolean(revokingId)} onClick={() => setPendingRevokeId(item.id)} className="shrink-0 rounded-lg border border-red-500/20 px-2 py-1 text-[10px] text-red-400 hover:bg-red-500/10 disabled:opacity-50">
                  {revokingId === item.id ? t('loading') : t('deviceRevoke')}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
      {error && <p role="alert" className="text-[10px] text-red-400">{error}</p>}
      <ConfirmModal
        open={pendingRevokeId !== null}
        title={t('deviceRevokeConfirmTitle')}
        message={t('deviceRevokeConfirmMessage')}
        confirmLabel={t('deviceRevoke')}
        danger
        onConfirm={() => {
          const deviceId = pendingRevokeId;
          setPendingRevokeId(null);
          if (!deviceId) return;
          if (device?.id === deviceId) void revoke();
          else void revokeManaged(deviceId);
        }}
        onCancel={() => setPendingRevokeId(null)}
      />
      {showGeneratedCode && (
        <ConfirmModal open title={t('devicePairingGenerated')} message={t('devicePairingGeneratedHint')} confirmLabel={t('close')} showCancel={false} onConfirm={() => setShowGeneratedCode(false)} onCancel={() => setShowGeneratedCode(false)}>
          <div className={`rounded-xl border px-4 py-3 text-center ${border}`}>
            <code className={`block text-2xl tracking-[0.24em] ${text}`}>{generatedCode}</code>
            <button type="button" onClick={() => { void copyGeneratedCode(); }} className="mt-3 inline-flex items-center gap-1 text-xs text-[#4aa7ed] hover:underline" aria-label={copiedCode ? t('copied') : t('copy')}>
              {copiedCode ? <MdCheck size={14} aria-hidden="true" /> : <MdContentCopy size={14} aria-hidden="true" />} {copiedCode ? t('copied') : t('copy')}
            </button>
          </div>
        </ConfirmModal>
      )}
    </div>
  );
}
