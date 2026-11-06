import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { MdArrowForward } from 'react-icons/md';

import { useI18n } from '../i18n/I18nContext';
import { useTheme } from '../theme/ThemeContext';
import { MODEL_PRESETS, checkStatus, type ModelPreset } from '../lib/api';
import { syncSharedStateOnce } from '../lib/sharedState';
import OnboardingShell from './onboarding/OnboardingShell';

interface Props {
  onComplete: () => void;
  canConfigureSystem: boolean;
}

const LANGUAGES = [
  { code: 'es', short: 'ES', labelKey: 'languageSpanish' },
  { code: 'en', short: 'EN', labelKey: 'languageEnglish' },
] as const;

const THEMES = [
  { mode: 'dark', labelKey: 'darkMode' },
  { mode: 'light', labelKey: 'lightMode' },
] as const;

/** How long finishing waits for the hardware profile before moving on. */
const PROFILE_WAIT_MS = 3500;

/**
 * Models follow the hardware profile the installer already detected; the
 * wizard only copies that choice into this browser, it never asks about it.
 */
function applyProfileModels(profile: ModelPreset) {
  const preset = MODEL_PRESETS[profile];
  for (const [key, value] of Object.entries(preset)) localStorage.setItem(key, value);
  localStorage.removeItem('tc-models-vision-quality');
}

export default function OnboardingWizard({ onComplete, canConfigureSystem }: Props) {
  const { t, setLang, lang } = useI18n();
  const { theme, setTheme } = useTheme();
  const [nickname, setNickname] = useState('');
  const [finishing, setFinishing] = useState(false);
  const profileRef = useRef<Promise<ModelPreset | null>>(Promise.resolve(null));

  useEffect(() => {
    if (!canConfigureSystem) return;
    profileRef.current = Promise.resolve(checkStatus()).then((status) => status.profile).catch(() => null);
  }, [canConfigureSystem]);

  const finish = useCallback(async () => {
    if (finishing) return;
    setFinishing(true);
    const preferredName = nickname.trim();
    if (preferredName) localStorage.setItem('tc-user-nickname', preferredName);
    localStorage.removeItem('tc-user-name');
    localStorage.removeItem('tc-user-avatar');
    if (canConfigureSystem) {
      // Never write a guessed default: only a profile the service reported.
      const profile = await Promise.race([
        profileRef.current,
        new Promise<null>((resolve) => { window.setTimeout(() => resolve(null), PROFILE_WAIT_MS); }),
      ]);
      if (profile) applyProfileModels(profile);
    }
    localStorage.setItem('tc-onboarding-complete', 'true');
    await syncSharedStateOnce(2500, true).catch(() => undefined);
    setFinishing(false);
    onComplete();
  }, [canConfigureSystem, finishing, nickname, onComplete]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void finish();
  };

  return (
    <OnboardingShell>
      <form onSubmit={submit} noValidate aria-labelledby="onb-title" aria-busy={finishing}>
        <h1 id="onb-title" className="onb-title">{t('onboardingWelcome')}</h1>
        <p className="onb-lead mt-2">{t('onbLead')}</p>

        <div className="mt-6 grid gap-5">
          <fieldset className="m-0 min-w-0 border-0 p-0">
            <legend className="onb-legend">{t('onbLanguageLegend')}</legend>
            <div className="grid grid-cols-2 gap-2.5">
              {LANGUAGES.map((option) => (
                <label key={option.code} className="onb-option">
                  <input type="radio" name="onb-language" value={option.code} checked={lang === option.code} onChange={() => setLang(option.code)} />
                  <span className="onb-lang-code" aria-hidden="true">{option.short}</span>
                  <span className="font-semibold">{t(option.labelKey)}</span>
                  <span className="onb-radio" aria-hidden="true" />
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset className="m-0 min-w-0 border-0 p-0">
            <legend className="onb-legend">{t('onbThemeLegend')}</legend>
            <div className="grid grid-cols-2 gap-2.5">
              {THEMES.map((option) => (
                <label key={option.mode} className="onb-option">
                  <input type="radio" name="onb-theme" value={option.mode} checked={theme === option.mode} onChange={() => setTheme(option.mode)} />
                  <span className="onb-theme-thumb" data-mode={option.mode} aria-hidden="true"><i /><i /><i /></span>
                  <span className="font-semibold">{t(option.labelKey)}</span>
                  <span className="onb-radio" aria-hidden="true" />
                </label>
              ))}
            </div>
          </fieldset>

          <div>
            <label htmlFor="onboarding-nickname" className="onb-legend block">{t('onbNameLabel')}</label>
            <input
              id="onboarding-nickname"
              name="nickname"
              type="text"
              className="onb-input"
              value={nickname}
              maxLength={40}
              autoComplete="nickname"
              aria-describedby="onb-name-hint"
              onChange={(event) => setNickname(event.target.value)}
            />
            <p id="onb-name-hint" className="onb-muted mt-2 text-sm">{t('onbNameHint')}</p>
          </div>
        </div>

        <button type="submit" className="onb-btn mt-7 w-full" data-variant="primary" disabled={finishing}>
          {finishing ? <span className="onb-spinner" aria-hidden="true" style={{ borderTopColor: '#fff', borderColor: 'rgba(255,255,255,.4)' }} /> : null}
          {finishing ? t('onbFinishing') : t('onboardingStartNow')}
          {!finishing && <MdArrowForward size={20} aria-hidden="true" />}
        </button>
      </form>
    </OnboardingShell>
  );
}
