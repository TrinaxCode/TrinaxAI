import { useEffect, useRef, useState } from 'react';
import { MdAddCircleOutline, MdDevices } from 'react-icons/md';

import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import DevicePairingCard from './DevicePairingCard';
import BackButton from './BackButton';

interface Props {
  onNewDevice: () => void;
  preferExisting?: boolean;
}

/** First-run choice keeps private state protected until the device is paired. */
export default function DeviceSetupChoice({ onNewDevice, preferExisting = false }: Props) {
  const { t } = useI18n();
  const { isDark } = useTheme();
  const [mode, setMode] = useState<'choose' | 'existing'>(preferExisting ? 'existing' : 'choose');
  const previousMode = useRef(mode);
  const existingButtonRef = useRef<HTMLButtonElement>(null);
  const backButtonRef = useRef<HTMLButtonElement>(null);
  const card = isDark ? 'bg-gray-900/90 border-white/[0.09] text-white' : 'bg-white border-gray-200 text-gray-900';
  const muted = isDark ? 'text-white/60' : 'text-gray-600';

  useEffect(() => {
    if (previousMode.current !== mode) {
      (mode === 'existing' ? backButtonRef.current : existingButtonRef.current)?.focus({ preventScroll: true });
      previousMode.current = mode;
    }
  }, [mode]);

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center overflow-y-auto p-4" role="main">
      <section className={`w-full max-w-md rounded-3xl border p-6 shadow-2xl ${card}`}>
        {mode === 'choose' ? (
          <>
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#006bbd]/15 text-[#4aa7ed]">
                <MdDevices size={24} aria-hidden="true" />
              </div>
              <div>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${muted}`}>{t('deviceSetupEyebrow')}</p>
                <h1 className="text-xl font-semibold">{t('deviceSetupTitle')}</h1>
              </div>
            </div>
            <p className={`text-sm leading-relaxed ${muted}`}>{t('deviceSetupHint')}</p>
            <div className="mt-6 grid gap-3">
              <button
                type="button"
                ref={existingButtonRef}
                onClick={() => setMode('existing')}
                className="group flex min-h-20 items-center gap-3 rounded-2xl border border-[#006bbd]/45 bg-[#006bbd]/10 p-4 text-left transition-[background-color,border-color,transform] hover:border-[#006bbd] hover:bg-[#006bbd]/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4aa7ed] active:scale-[0.99]"
              >
                <MdDevices size={25} className="shrink-0 text-[#4aa7ed]" aria-hidden="true" />
                <span className="min-w-0">
                  <strong className="block text-sm">{t('deviceSetupExisting')}</strong>
                  <small className={`mt-1 block leading-relaxed ${muted}`}>{t('deviceSetupExistingHint')}</small>
                </span>
              </button>
              <button
                type="button"
                onClick={onNewDevice}
                className={`group flex min-h-16 items-center gap-3 rounded-2xl border p-4 text-left transition-[background-color,border-color,transform] hover:bg-[#006bbd]/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4aa7ed] active:scale-[0.99] ${isDark ? 'border-white/[0.1]' : 'border-gray-200'}`}
              >
                <MdAddCircleOutline size={23} className="shrink-0 text-[#4aa7ed]" aria-hidden="true" />
                <span className="min-w-0">
                  <strong className="block text-sm">{t('deviceSetupNew')}</strong>
                  <small className={`mt-1 block leading-relaxed ${muted}`}>{t('deviceSetupNewHint')}</small>
                </span>
              </button>
            </div>
          </>
        ) : (
          <>
            <BackButton buttonRef={backButtonRef} onClick={() => setMode('choose')} label={t('back')} isDark={isDark} className="mb-1 self-start" />
            <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${muted}`}>{t('deviceSetupEyebrow')}</p>
            <h1 className="mt-2 text-xl font-semibold">{preferExisting ? t('deviceSetupRestoreTitle') : t('deviceSetupExisting')}</h1>
            <p className={`mt-2 text-sm leading-relaxed ${muted}`}>{t('deviceSetupPairingTutorial')}</p>
            <div className="mt-5"><DevicePairingCard isDark={isDark} /></div>
          </>
        )}
      </section>
    </div>
  );
}
