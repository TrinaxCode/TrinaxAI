import { useEffect, useState } from 'react';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { checkStatus } from '../lib/api';

export default function StatusDots() {
  const { t } = useI18n();
  const { isDark } = useTheme();
  const [s, setS] = useState({ ollama: false, rag: false, indexed: false, ramPercent: null as number | null });

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      const r = await checkStatus();
      if (alive) setS(r);
    };
    tick();
    const id = setInterval(tick, 12000);
    return () => { alive = false; clearInterval(id); };
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
    </div>
  );
}
