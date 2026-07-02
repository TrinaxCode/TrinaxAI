import { useEffect, useRef, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { MdRefresh } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { useToast } from './Toast';
import { getUsageStats, type UsageStats } from '../lib/api';

function fmtDate(ts: number | null | undefined): string {
  if (!ts) return '—';
  try { return new Date(ts * 1000).toLocaleString(); } catch { return '—'; }
}

function fmtNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

export default function StatsPanel() {
  const { t } = useI18n();
  const { isDark } = useTheme();
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
      const msg = err instanceof Error ? err.message.slice(0, 180) : t('noStatsAvailable');
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

  const cardBg = isDark ? 'bg-white/[0.03] border-white/[0.06]' : 'bg-gray-50 border-gray-200';
  const muted = isDark ? 'text-white/45' : 'text-gray-500';
  const label = isDark ? 'text-white/80' : 'text-gray-800';
  const value = isDark ? 'text-white' : 'text-gray-900';

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className={`text-sm font-medium ${label}`}>{t('usageStatsTitle')}</div>
          <div className={`text-[11px] break-words ${muted}`}>
            {t('usageStatsDesc')}
          </div>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${isDark ? 'bg-white/[0.06] text-white/70 hover:bg-white/[0.1]' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'} disabled:opacity-50`}
        >
          <MdRefresh size={14} /> {t('refresh')}
        </button>
      </div>

      {!stats ? (
        loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 animate-pulse">
            {[1,2,3,4].map((i) => (
              <div key={i} className={`min-w-0 rounded-xl border p-3 ${cardBg}`}>
                <div className={`h-3 w-16 rounded ${isDark ? 'bg-white/[0.08]' : 'bg-gray-200'}`} />
                <div className={`mt-2 h-6 w-20 rounded ${isDark ? 'bg-white/[0.06]' : 'bg-gray-200'}`} />
              </div>
            ))}
          </div>
        ) : (
          <p className={`text-[11px] ${muted}`}>
            {loadError
              ? t('statsUnavailableOffline')
              : t('loading')}
          </p>
        )
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <StatCard label={t('statsTotalMessages')} value={fmtNumber(stats.messages_total)} cardBg={cardBg} valueCls={value} labelCls={muted} />
            <StatCard label={t('statsEstimatedTokens')} value={fmtNumber(stats.tokens_estimated)} cardBg={cardBg} valueCls={value} labelCls={muted} />
            <StatCard label={t('statsFirstSeen')} value={fmtDate(stats.first_seen)} cardBg={cardBg} valueCls={value} labelCls={muted} small />
            <StatCard label={t('statsLastSeen')} value={fmtDate(stats.last_seen)} cardBg={cardBg} valueCls={value} labelCls={muted} small />
          </div>

          {/* Top models bar */}
          {stats.top_models.length > 0 && (
            <div className={`rounded-xl border p-3 space-y-2 ${cardBg}`}>
              <div className={`text-[10px] uppercase tracking-widest ${muted}`}>{t('statsTopModels')}</div>
              <BarList items={stats.top_models.map((m) => ({ key: m.model, count: m.count }))} total={stats.messages_total} isDark={isDark} />
            </div>
          )}

          {/* Top collections bar */}
          {stats.top_collections.length > 0 && (
            <div className={`rounded-xl border p-3 space-y-2 ${cardBg}`}>
              <div className={`text-[10px] uppercase tracking-widest ${muted}`}>{t('statsTopCollections')}</div>
              <BarList items={stats.top_collections.map((c) => ({ key: c.id, count: c.count }))} total={stats.messages_total} isDark={isDark} />
            </div>
          )}

          {/* Engine split */}
          {Object.keys(stats.messages_by_engine).length > 0 && (
            <div className={`rounded-xl border p-3 space-y-2 ${cardBg}`}>
              <div className={`text-[10px] uppercase tracking-widest ${muted}`}>{t('statsEngineSplit')}</div>
              <BarList items={Object.entries(stats.messages_by_engine).map(([k, v]) => ({ key: k, count: v }))} total={stats.messages_total} isDark={isDark} />
            </div>
          )}
        </>
      )}
    </section>
  );
}

function StatCard({ label, value, cardBg, valueCls, labelCls, small }: { label: string; value: string; cardBg: string; valueCls: string; labelCls: string; small?: boolean }) {
  return (
    <div className={`min-w-0 rounded-xl border p-3 ${cardBg}`}>
      <div className={`text-[10px] uppercase tracking-widest break-words ${labelCls}`}>{label}</div>
      <div className={`mt-1 ${small ? 'text-xs' : 'text-lg'} font-semibold tabular-nums break-words ${valueCls}`}>{value}</div>
    </div>
  );
}

function BarList({ items, total, isDark }: { items: Array<{ key: string; count: number }>; total: number; isDark: boolean }) {
  return (
    <div className="space-y-1.5">
      {items.map((it) => {
        const pct = total > 0 ? (it.count / total) * 100 : 0;
        return (
          <div key={it.key} className="flex items-center gap-2 min-w-0">
            <span className={`w-32 truncate text-[11px] font-mono ${isDark ? 'text-white/65' : 'text-gray-700'}`} title={it.key}>{it.key}</span>
            <div className={`flex-1 h-2 rounded-full overflow-hidden ${isDark ? 'bg-white/[0.06]' : 'bg-gray-200'}`}>
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.4 }}
                className="h-full bg-[#006bbd]"
              />
            </div>
            <span className={`w-12 text-right text-[11px] tabular-nums ${isDark ? 'text-white/55' : 'text-gray-500'}`}>{it.count}</span>
          </div>
        );
      })}
    </div>
  );
}
