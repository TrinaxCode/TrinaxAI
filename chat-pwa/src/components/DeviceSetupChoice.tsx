import { useEffect, useRef, useState } from 'react';
import { MdAddCircleOutline, MdDevices } from 'react-icons/md';

import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import DevicePairingCard from './DevicePairingCard';
import BackButton from './BackButton';
import OnboardingShell from './onboarding/OnboardingShell';

interface Props {
  onNewDevice: () => void | Promise<void>;
  preferExisting?: boolean;
}

/** First-run choice keeps private state protected until the device is paired. */
export default function DeviceSetupChoice({ onNewDevice, preferExisting = false }: Props) {
  const { t } = useI18n();
  const { isDark } = useTheme();
  const [mode, setMode] = useState<'choose' | 'existing'>(preferExisting ? 'existing' : 'choose');
  const [newDeviceBusy, setNewDeviceBusy] = useState(false);
  const [newDeviceError, setNewDeviceError] = useState(false);
  const previousMode = useRef(mode);
  const existingButtonRef = useRef<HTMLButtonElement>(null);
  const backButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (previousMode.current !== mode) {
      (mode === 'existing' ? backButtonRef.current : existingButtonRef.current)?.focus({ preventScroll: true });
      previousMode.current = mode;
    }
  }, [mode]);

  const handleNewDevice = async () => {
    setNewDeviceBusy(true);
    setNewDeviceError(false);
    try {
      await onNewDevice();
    } catch {
      setNewDeviceError(true);
    } finally {
      setNewDeviceBusy(false);
    }
  };

  return (
    <OnboardingShell className="z-[60]">
      {mode === 'choose' ? (
        <>
          <div className="mb-6">
            <p className="onb-muted mb-1 text-sm font-medium">{t('deviceSetupEyebrow')}</p>
            <h1 className="onb-title">{t('deviceSetupTitle')}</h1>
            <p className="onb-lead mt-2">{t('deviceSetupHint')}</p>
          </div>
          <div className="grid gap-3">
            <button type="button" ref={existingButtonRef} className="onb-choice" data-primary="true" onClick={() => setMode('existing')}>
              <span className="onb-choice-icon"><MdDevices size={24} aria-hidden="true" /></span>
              <span className="min-w-0">
                <strong className="block text-base">{t('deviceSetupExisting')}</strong>
                <small className="onb-muted mt-1 block text-[0.9375rem] leading-relaxed">{t('deviceSetupExistingHint')}</small>
              </span>
            </button>
            <button type="button" className="onb-choice" onClick={() => void handleNewDevice()} disabled={newDeviceBusy} aria-busy={newDeviceBusy}>
              <span className="onb-choice-icon"><MdAddCircleOutline size={24} aria-hidden="true" /></span>
              <span className="min-w-0">
                <strong className="flex items-center gap-2 text-base">
                  {newDeviceBusy && <span className="onb-spinner" aria-hidden="true" />}
                  {newDeviceBusy ? t('loading') : t('deviceSetupNew')}
                </strong>
                <small className="onb-muted mt-1 block text-[0.9375rem] leading-relaxed">{t('deviceSetupNewHint')}</small>
              </span>
            </button>
            {newDeviceError && <p role="alert" className="onb-note" data-tone="danger">{t('deviceSetupNewError')}</p>}
          </div>
        </>
      ) : (
        <>
          <BackButton buttonRef={backButtonRef} onClick={() => setMode('choose')} label={t('back')} isDark={isDark} className="-ml-2 mb-1 self-start" />
          <p className="onb-muted mb-1 text-sm font-medium">{t('deviceSetupEyebrow')}</p>
          <h1 className="onb-title">{preferExisting ? t('deviceSetupRestoreTitle') : t('deviceSetupExisting')}</h1>
          <p className="onb-lead mt-2">{t('deviceSetupPairingTutorial')}</p>
          <div className="mt-5"><DevicePairingCard isDark={isDark} /></div>
        </>
      )}
    </OnboardingShell>
  );
}
