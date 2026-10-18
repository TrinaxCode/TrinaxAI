import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { MdAddCircleOutline, MdDevices } from 'react-icons/md';

import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import DevicePairingCard from './DevicePairingCard';
import BackButton from './BackButton';

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
  const card = isDark ? 'border-white/10 bg-[#111c29] text-white' : 'border-slate-200 bg-white text-slate-900';
  const muted = isDark ? 'text-white/70' : 'text-slate-600';

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
    <motion.div
      className={`fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto px-4 py-6 ${isDark ? 'bg-[#080f18]' : 'bg-[#f5f8fc]'}`}
      role="main"
      initial={{ opacity: 0, scale: 0.985 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.985 }}
      transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
    >
      <section className={`my-auto w-full max-w-md rounded-3xl border p-6 shadow-[0_24px_70px_rgba(4,19,35,0.18)] sm:p-8 ${card}`}>
        {mode === 'choose' ? (
          <>
            <div className="mb-6 flex items-center gap-3">
              <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${isDark ? 'bg-[#4aa7ed]/15 text-[#8ac9f5]' : 'bg-[#006bbd]/10 text-[#0059a0]'}`}>
                <MdDevices size={24} aria-hidden="true" />
              </div>
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.12em] ${muted}`}>{t('deviceSetupEyebrow')}</p>
                <h1 className="text-xl font-semibold">{t('deviceSetupTitle')}</h1>
              </div>
            </div>
            <p className={`text-sm leading-relaxed ${muted}`}>{t('deviceSetupHint')}</p>
            <div className="mt-6 grid gap-3">
              <button
                type="button"
                ref={existingButtonRef}
                onClick={() => setMode('existing')}
                className="group flex min-h-20 items-center gap-3 rounded-2xl border border-[#006bbd]/35 bg-[#006bbd]/10 p-4 text-left transition-[background-color,border-color,transform] hover:border-[#006bbd] hover:bg-[#006bbd]/15 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] active:scale-[0.99]"
              >
                <MdDevices size={25} className={`shrink-0 ${isDark ? 'text-[#8ac9f5]' : 'text-[#0059a0]'}`} aria-hidden="true" />
                <span className="min-w-0">
                  <strong className="block text-sm">{t('deviceSetupExisting')}</strong>
                  <small className={`mt-1 block text-sm leading-relaxed ${muted}`}>{t('deviceSetupExistingHint')}</small>
                </span>
              </button>
              <button
                type="button"
                onClick={() => void handleNewDevice()}
                disabled={newDeviceBusy}
                aria-busy={newDeviceBusy}
                className={`group flex min-h-16 items-center gap-3 rounded-2xl border p-4 text-left transition-[background-color,border-color,transform] hover:bg-[#006bbd]/10 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] active:scale-[0.99] ${isDark ? 'border-white/15' : 'border-slate-200'}`}
              >
                <MdAddCircleOutline size={23} className={`shrink-0 ${isDark ? 'text-[#8ac9f5]' : 'text-[#0059a0]'}`} aria-hidden="true" />
                <span className="min-w-0">
                  <strong className="block text-sm">{newDeviceBusy ? t('loading') : t('deviceSetupNew')}</strong>
                  <small className={`mt-1 block text-sm leading-relaxed ${muted}`}>{t('deviceSetupNewHint')}</small>
                </span>
              </button>
              {newDeviceError && <p role="alert" className={`rounded-xl border px-3 py-2 text-sm leading-relaxed ${isDark ? 'border-red-400/25 bg-red-400/10 text-red-200' : 'border-red-200 bg-red-50 text-red-800'}`}>{t('deviceSetupNewError')}</p>}
            </div>
          </>
        ) : (
          <>
            <BackButton buttonRef={backButtonRef} onClick={() => setMode('choose')} label={t('back')} isDark={isDark} className="mb-1 self-start" />
            <p className={`text-xs font-semibold uppercase tracking-[0.12em] ${muted}`}>{t('deviceSetupEyebrow')}</p>
            <h1 className="mt-2 text-xl font-semibold">{preferExisting ? t('deviceSetupRestoreTitle') : t('deviceSetupExisting')}</h1>
            <p className={`mt-2 text-sm leading-relaxed ${muted}`}>{t('deviceSetupPairingTutorial')}</p>
            <div className="mt-5"><DevicePairingCard isDark={isDark} /></div>
          </>
        )}
      </section>
    </motion.div>
  );
}
