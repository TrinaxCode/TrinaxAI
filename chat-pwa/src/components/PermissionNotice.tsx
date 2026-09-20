import { motion } from 'framer-motion';
import { MdLockOutline } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';

interface Props { feature: 'rag' | 'web' | 'knowledge' | 'memory' | 'stats' | 'index' | 'agent'; onBack: () => void; remoteWebSearch?: boolean; }

export default function PermissionNotice({ feature, onBack, remoteWebSearch = false }: Props) {
  const { t } = useI18n();
  const { isDark } = useTheme();
  const hostOnly = feature === 'index' || feature === 'agent';
  const backLabel = remoteWebSearch ? t('remoteWebSearchNoticeButton') : feature === 'rag' ? t('permissionBackToOllama') : feature === 'agent' ? t('permissionBackToChat') : t('back');
  return (
    <motion.div
      className="flex h-full min-h-0 items-center justify-center overflow-y-auto p-4"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 16 }}
      transition={{ duration: 0.26, ease: [0.16, 1, 0.3, 1] }}
    >
      <section className={`w-full max-w-md rounded-2xl border p-6 text-center shadow-xl ${isDark ? 'border-white/10 bg-gray-900/95 text-white' : 'border-gray-200 bg-white text-gray-900'}`}>
        <MdLockOutline className="mx-auto text-[#4aa7ed]" size={42} aria-hidden="true" />
        <h2 className="mt-3 text-xl font-semibold">{remoteWebSearch ? t('remoteWebSearchNoticeTitle') : t('permissionRequiredTitle')}</h2>
        <p className={`mt-2 text-sm ${isDark ? 'text-white/65' : 'text-gray-600'}`}>{remoteWebSearch ? t('remoteWebSearchNoticeMessage') : t(`permissionFeature_${feature}`)}</p>
        {!remoteWebSearch && <div className={`mt-4 rounded-xl p-4 text-left text-xs leading-relaxed ${isDark ? 'bg-white/[0.05] text-white/65' : 'bg-gray-50 text-gray-600'}`}>{t(hostOnly ? 'permissionHostOnly' : 'permissionTutorial')}</div>}
        <button type="button" onClick={onBack} className="mt-5 min-h-11 w-full rounded-xl bg-[#006bbd] px-4 py-2 text-sm font-medium text-white hover:bg-[#00599d]">{backLabel}</button>
      </section>
    </motion.div>
  );
}
