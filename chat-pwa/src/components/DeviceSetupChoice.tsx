import { useState } from 'react';
import { MdAddCircleOutline, MdDevices } from 'react-icons/md';

import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import DevicePairingCard from './DevicePairingCard';

interface Props {
  onNewDevice: () => void;
}

/** First-run choice keeps private state protected until the device is paired. */
export default function DeviceSetupChoice({ onNewDevice }: Props) {
  const { t } = useI18n();
  const { isDark } = useTheme();
  const [mode, setMode] = useState<'choose' | 'existing'>('choose');
  const card = isDark ? 'bg-gray-900/90 border-white/[0.09] text-white' : 'bg-white border-gray-200 text-gray-900';
  const muted = isDark ? 'text-white/60' : 'text-gray-600';

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center overflow-y-auto p-4" role="main">
      <section className={`w-full max-w-md rounded-2xl border p-5 shadow-2xl ${card}`}>
        {mode === 'choose' ? (
          <>
            <h1 className="text-center text-2xl font-semibold">{t('deviceSetupTitle')}</h1>
            <p className={`mt-2 text-center text-sm ${muted}`}>{t('deviceSetupHint')}</p>
            <div className="mt-5 grid gap-3">
              <button type="button" onClick={onNewDevice} className="flex min-h-16 items-center gap-3 rounded-xl border border-[#006bbd]/35 p-4 text-left hover:bg-[#006bbd]/10">
                <MdAddCircleOutline size={24} className="shrink-0 text-[#4aa7ed]" aria-hidden="true" />
                <span><strong className="block text-sm">{t('deviceSetupNew')}</strong><small className={muted}>{t('deviceSetupNewHint')}</small></span>
              </button>
              <button type="button" onClick={() => setMode('existing')} className="flex min-h-16 items-center gap-3 rounded-xl border border-[#006bbd]/35 p-4 text-left hover:bg-[#006bbd]/10">
                <MdDevices size={24} className="shrink-0 text-[#4aa7ed]" aria-hidden="true" />
                <span><strong className="block text-sm">{t('deviceSetupExisting')}</strong><small className={muted}>{t('deviceSetupExistingHint')}</small></span>
              </button>
            </div>
          </>
        ) : (
          <>
            <button type="button" onClick={() => setMode('choose')} className={`mb-3 text-xs ${muted}`}>← {t('back')}</button>
            <h1 className="text-center text-xl font-semibold">{t('deviceSetupExisting')}</h1>
            <p className={`mt-2 text-center text-sm ${muted}`}>{t('deviceSetupPairingTutorial')}</p>
            <div className="mt-4"><DevicePairingCard isDark={isDark} /></div>
          </>
        )}
      </section>
    </div>
  );
}
