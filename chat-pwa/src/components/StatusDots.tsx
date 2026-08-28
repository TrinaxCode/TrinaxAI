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

  useEffect(() => {
    let alive = true;
    let inFlight = false;
    const tick = async () => {
      if (document.hidden || inFlight) return;
      inFlight = true;
      try {
        const r = await checkStatus();
        if (alive) setS(r);
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
    ok ? (warn ? 'bg-amber-400' : 'bg-green-400') : 'bg-red-500/70';

  return (
    <div
      className={`flex items-center justify-center gap-4 text-xs font-semibold ${
        isDark ? 'text-white/70' : 'text-gray-800'
      }`}
      title={t('status')}
    >
      <span className="flex items-center gap-1.5">
        <span className={`w-2.5 h-2.5 rounded-full ${dot(s.ollama)}`} />{t('ollamaStatus')}
      </span>
      <span className="flex items-center gap-1.5">
        <span className={`w-2.5 h-2.5 rounded-full ${dot(s.rag, s.rag && !s.indexed)}`} />{t('ragStatus')}
      </span>
      {s.ramPercent != null && (
        <span className="hidden sm:inline tabular-nums">
          RAM {Math.round(s.ramPercent)}%
        </span>
      )}
      {s.profile && (
        <span className="hidden sm:inline uppercase tabular-nums">
          {t('hardwareProfile')}: {s.profile}
        </span>
      )}
    </div>
  );
}
