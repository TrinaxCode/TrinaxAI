import { MdLockOutline } from 'react-icons/md';
import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';

interface Props { feature: 'rag' | 'knowledge' | 'memory' | 'stats' | 'index' | 'agent'; onBack: () => void; }

export default function PermissionNotice({ feature, onBack }: Props) {
  const { t } = useI18n();
  const { isDark } = useTheme();
  const backLabel = feature === 'rag' ? t('permissionBackToOllama') : feature === 'agent' ? t('permissionBackToChat') : t('back');
  return (
    <div className="flex h-full min-h-0 items-center justify-center overflow-y-auto p-4">
      <section className={`w-full max-w-md rounded-2xl border p-6 text-center shadow-xl ${isDark ? 'border-white/10 bg-gray-900/95 text-white' : 'border-gray-200 bg-white text-gray-900'}`}>
        <MdLockOutline className="mx-auto text-[#4aa7ed]" size={42} aria-hidden="true" />
        <h2 className="mt-3 text-xl font-semibold">{t('permissionRequiredTitle')}</h2>
        <p className={`mt-2 text-sm ${isDark ? 'text-white/65' : 'text-gray-600'}`}>{t(`permissionFeature_${feature}`)}</p>
        <div className={`mt-4 rounded-xl p-4 text-left text-xs leading-relaxed ${isDark ? 'bg-white/[0.05] text-white/65' : 'bg-gray-50 text-gray-600'}`}>{t('permissionTutorial')}</div>
        <button type="button" onClick={onBack} className="mt-5 min-h-11 w-full rounded-xl bg-[#006bbd] px-4 py-2 text-sm font-medium text-white hover:bg-[#00599d]">{backLabel}</button>
      </section>
    </div>
  );
}
