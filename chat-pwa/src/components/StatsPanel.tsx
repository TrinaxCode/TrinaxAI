import { useEffect, useRef, useState, useCallback } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { MdRefresh } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { useToast } from './Toast';
import { getUsageStats, userFacingError, type UsageStats } from '../lib/api';

function fmtDate(ts: number | null | undefined, lang: string): string {
  if (!ts) return '-';
  try { return new Date(ts * 1000).toLocaleString(lang); } catch { return '-'; }
}

function fmtNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

export default function StatsPanel() {
  const { t, lang } = useI18n();
  const { isDark } = useTheme();
  const prefersReducedMotion = useReducedMotion();
  const toast = useToast();
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const connectionToastShownRef = useRef(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const s = await getUsageStats();
      setStats(s);
      setLoadError('');
      connectionToastShownRef.current = false;
    } catch (err) {
      const msg = userFacingError(err, 'external_service_unavailable');
      setLoadError(msg);
      if (!connectionToastShownRef.current) {
        connectionToastShownRef.current = true;
        toast.toast(msg, 'error');
      }
    } finally {
      setLoading(false);
    }
  }, [toast, t]);

  useEffect(() => { void refresh(); }, [refresh]);

  const cardBg = isDark ? 'bg-white/[0.04] border-white/10' : 'bg-white border-slate-200';
  const muted = isDark ? 'text-white/65' : 'text-gray-600';
  const label = isDark ? 'text-white/80' : 'text-gray-800';
  const value = isDark ? 'text-white' : 'text-gray-900';

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className={`text-lg font-semibold ${label}`}>{t('usageStatsTitle')}</h2>
          <p className={`mt-1 break-words text-sm leading-relaxed ${muted}`}>
            {t('usageStatsDesc')}
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className={`flex min-h-11 items-center gap-2 rounded-xl px-3 text-sm font-medium transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] ${isDark ? 'bg-white/[0.08] text-white/85 hover:bg-white/[0.14]' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'} disabled:opacity-50`}
        >
          <MdRefresh size={18} aria-hidden="true" /> {t('refresh')}
        </button>
      </div>

      <AnimatePresence mode="wait" initial={false}>
      {!stats ? (
        loading ? (
          <motion.div
            key="stats-loading"
            initial={prefersReducedMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: prefersReducedMotion ? 0 : 0.16 }}
            className="grid grid-cols-1 sm:grid-cols-2 gap-3 animate-pulse"
          >
            {[1,2,3,4].map((i) => (
              <div key={i} className={`min-w-0 rounded-xl border p-3 ${cardBg}`}>
                <div className={`h-3 w-16 rounded ${isDark ? 'bg-white/[0.08]' : 'bg-gray-200'}`} />
                <div className={`mt-2 h-6 w-20 rounded ${isDark ? 'bg-white/[0.06]' : 'bg-gray-200'}`} />
              </div>
            ))}
          </motion.div>
        ) : (
          <motion.div
            key="stats-empty"
            role="status"
            initial={prefersReducedMotion ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: prefersReducedMotion ? 0 : 0.2, ease: [0.16, 1, 0.3, 1] }}
            className={`rounded-xl border p-5 text-center text-sm leading-relaxed ${cardBg} ${muted}`}
          >
            {loadError || t('loading')}
          </motion.div>
        )
      ) : (
        <motion.div
          key="stats-content"
          initial={prefersReducedMotion ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }}
          transition={{ duration: prefersReducedMotion ? 0 : 0.26, ease: [0.16, 1, 0.3, 1] }}
          className="space-y-4"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <StatCard label={t('statsTotalMessages')} value={fmtNumber(stats.messages_total)} cardBg={cardBg} valueCls={value} labelCls={muted} />
            <StatCard label={t('statsEstimatedTokens')} value={fmtNumber(stats.tokens_estimated)} cardBg={cardBg} valueCls={value} labelCls={muted} />
            <StatCard label={t('statsFirstSeen')} value={fmtDate(stats.first_seen, lang)} cardBg={cardBg} valueCls={value} labelCls={muted} small />
            <StatCard label={t('statsLastSeen')} value={fmtDate(stats.last_seen, lang)} cardBg={cardBg} valueCls={value} labelCls={muted} small />
          </div>

          {/* Top models bar */}
          {stats.top_models.length > 0 && (
            <div className={`space-y-3 rounded-xl border p-4 ${cardBg}`}>
              <h3 className={`text-sm font-semibold ${label}`}>{t('statsTopModels')}</h3>
              <BarList items={stats.top_models.map((m) => ({ key: m.model, count: m.count }))} total={stats.messages_total} isDark={isDark} reduceMotion={!!prefersReducedMotion} />
            </div>
          )}

          {/* Top collections bar */}
          {stats.top_collections.length > 0 && (
            <div className={`space-y-3 rounded-xl border p-4 ${cardBg}`}>
              <h3 className={`text-sm font-semibold ${label}`}>{t('statsTopCollections')}</h3>
              <BarList items={stats.top_collections.map((c) => ({ key: c.id, count: c.count }))} total={stats.messages_total} isDark={isDark} reduceMotion={!!prefersReducedMotion} />
            </div>
          )}

          {/* Engine split */}
          {Object.keys(stats.messages_by_engine).length > 0 && (
            <div className={`space-y-3 rounded-xl border p-4 ${cardBg}`}>
              <h3 className={`text-sm font-semibold ${label}`}>{t('statsEngineSplit')}</h3>
              <BarList items={Object.entries(stats.messages_by_engine).map(([k, v]) => ({ key: k, count: v }))} total={stats.messages_total} isDark={isDark} reduceMotion={!!prefersReducedMotion} />
            </div>
          )}
        </motion.div>
      )}
      </AnimatePresence>
    </section>
  );
}

function StatCard({ label, value, cardBg, valueCls, labelCls, small }: { label: string; value: string; cardBg: string; valueCls: string; labelCls: string; small?: boolean }) {
  return (
    <div className={`min-w-0 rounded-xl border p-4 ${cardBg}`}>
      <div className={`break-words text-xs font-semibold uppercase tracking-wide ${labelCls}`}>{label}</div>
      <div className={`mt-2 break-words font-semibold tabular-nums ${small ? 'text-sm' : 'text-2xl'} ${valueCls}`}>{value}</div>
    </div>
  );
}

function BarList({ items, total, isDark, reduceMotion }: { items: Array<{ key: string; count: number }>; total: number; isDark: boolean; reduceMotion: boolean }) {
  return (
    <div className="space-y-3">
      {items.map((it) => {
        const pct = total > 0 ? (it.count / total) * 100 : 0;
        return (
          <div key={it.key} className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5">
            <span className={`min-w-0 truncate text-sm ${isDark ? 'text-white/80' : 'text-slate-700'}`} title={it.key}>{it.key}</span>
            <span className={`text-right text-sm font-semibold tabular-nums ${isDark ? 'text-white/85' : 'text-slate-800'}`}>{it.count}</span>
            <div aria-hidden="true" className={`col-span-2 h-2 overflow-hidden rounded-full ${isDark ? 'bg-white/10' : 'bg-slate-200'}`}>
              <motion.div
                initial={reduceMotion ? false : { width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: reduceMotion ? 0 : 0.4 }}
                className="h-full bg-[#006bbd]"
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
