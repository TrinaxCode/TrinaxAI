import { useEffect, useState } from 'react';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { checkStatus } from '../lib/api';
import { onSharedStateUpdated } from '../lib/sharedState';

const STATUS_INTERVAL_MS = 4000;

const DEFAULT_STATUS = { ollama: false, rag: false, indexed: false, ramPercent: null as number | null, profile: null as string | null };

export default function StatusDots() {
  const { t } = useI18n();
  const { isDark } = useTheme();
  const [s, setS] = useState(DEFAULT_STATUS);
  const [known, setKnown] = useState(false);

  useEffect(() => {
    let alive = true;
    let inFlight = false;
    const tick = async () => {
      if (document.hidden || inFlight) return;
      inFlight = true;
      try {
        const r = await checkStatus();
        if (alive) { setS(r); setKnown(true); }
      } catch {
        if (alive) setKnown(false);
      } finally {
        inFlight = false;
      }
    };
    const onVisible = () => { if (!document.hidden) void tick(); };
    void tick();
    const id = window.setInterval(() => { void tick(); }, STATUS_INTERVAL_MS);
    const unsubscribe = onSharedStateUpdated(onVisible);
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('focus', onVisible);
    return () => {
      alive = false;
      window.clearInterval(id);
      unsubscribe();
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('focus', onVisible);
    };
  }, []);

  const dot = (ok: boolean, warn = false) =>
    !known ? 'bg-slate-400' : ok ? (warn ? 'bg-amber-400' : 'bg-emerald-500') : 'bg-red-500';
  const ollamaState = !known ? t('statusUnknown') : s.ollama ? t('statusReady') : t('statusUnavailable');
  const ragState = !known ? t('statusUnknown') : !s.rag ? t('statusUnavailable') : s.indexed ? t('statusReady') : t('statusLimited');

  return (
    <div
      className={`flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-sm font-medium ${
        isDark ? 'text-white/70' : 'text-gray-800'
      }`}
      title={t('status')}
    >
      <span className="flex items-center gap-1.5" title={`${t('ollamaStatus')}: ${ollamaState}`}>
        <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${dot(s.ollama)}`} />
        <span>{t('ollamaStatus')}</span>
        <span className={isDark ? 'text-white/85' : 'text-gray-900'}>· {ollamaState}</span>
      </span>
      <span className="flex items-center gap-1.5" title={`${t('ragStatus')}: ${ragState}`}>
        <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${dot(s.rag, s.rag && !s.indexed)}`} />
        <span>{t('ragStatus')}</span>
        <span className={isDark ? 'text-white/85' : 'text-gray-900'}>· {ragState}</span>
      </span>
      {known && s.ramPercent != null && (
        <span className="hidden sm:inline tabular-nums">
          RAM {Math.round(s.ramPercent)}%
        </span>
      )}
      {known && s.profile && (
        <span className="hidden sm:inline uppercase tabular-nums">
          {t('hardwareProfile')}: {s.profile}
        </span>
      )}
    </div>
  );
}
