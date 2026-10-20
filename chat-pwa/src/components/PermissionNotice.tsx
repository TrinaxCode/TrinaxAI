import { motion } from 'framer-motion';
import { MdLockOutline } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';

interface Props { feature: 'rag' | 'web' | 'knowledge' | 'memory' | 'stats' | 'index' | 'agent'; onBack: () => void; remoteWebSearch?: boolean; }

export default function PermissionNotice({ feature, onBack, remoteWebSearch = false }: Props) {
  const { t } = useI18n();
  const { isDark } = useTheme();
  const grantedByHost = feature === 'index' || feature === 'agent';
  const backLabel = remoteWebSearch ? t('remoteWebSearchNoticeButton') : feature === 'rag' ? t('permissionBackToOllama') : feature === 'agent' ? t('permissionBackToChat') : t('back');
  return (
    <motion.div
      className="flex h-full min-h-0 items-center justify-center overflow-y-auto p-4"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 16 }}
      transition={{ duration: 0.26, ease: [0.16, 1, 0.3, 1] }}
    >
      <section className={`w-full max-w-md rounded-3xl border p-6 text-center shadow-[0_24px_70px_rgba(4,19,35,0.2)] sm:p-8 ${isDark ? 'border-white/10 bg-[#111c29]/95 text-white' : 'border-slate-200 bg-white text-slate-900'}`}>
        <span className={`mx-auto grid h-14 w-14 place-items-center rounded-2xl ${isDark ? 'bg-[#4aa7ed]/15 text-[#8ac9f5]' : 'bg-[#006bbd]/10 text-[#0059a0]'}`} aria-hidden="true"><MdLockOutline size={30} /></span>
        <h2 className="mt-5 text-xl font-semibold leading-tight">{remoteWebSearch ? t('remoteWebSearchNoticeTitle') : t('permissionRequiredTitle')}</h2>
        <p className={`mt-3 text-sm leading-relaxed ${isDark ? 'text-white/75' : 'text-slate-600'}`}>{remoteWebSearch ? t('remoteWebSearchNoticeMessage') : t(`permissionFeature_${feature}`)}</p>
        {!remoteWebSearch && <div className={`mt-5 rounded-xl border p-4 text-left text-sm leading-relaxed ${isDark ? 'border-white/10 bg-white/[0.04] text-white/75' : 'border-slate-200 bg-slate-50 text-slate-700'}`}>{t(grantedByHost ? 'permissionGrantTutorial' : 'permissionTutorial')}</div>}
        <button type="button" onClick={onBack} className="mt-6 min-h-11 w-full rounded-xl bg-[#006bbd] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[#0059a0] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed]">{backLabel}</button>
      </section>
    </motion.div>
  );
}
