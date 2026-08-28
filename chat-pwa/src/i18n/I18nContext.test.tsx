import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { I18nProvider, useI18n } from './I18nContext';
import { translations } from './translations';

function LanguageProbe() {
  const { lang, setLang, t } = useI18n();
  return (
    <>
      <span data-testid="language">{lang}</span>
      <span data-testid="open-indexing">{t('openIndexing')}</span>
      <button type="button" onClick={() => setLang(lang === 'es' ? 'en' : 'es')}>toggle</button>
    </>
  );
}

function setDeviceLanguage(language: string) {
  Object.defineProperty(navigator, 'language', { configurable: true, value: language });
}

describe('I18nProvider device-language detection', () => {
  afterEach(() => {
    localStorage.clear();
    setDeviceLanguage('en-US');
  });

  it('selects Spanish for a Spanish device', () => {
    setDeviceLanguage('es-MX');
    render(<I18nProvider><LanguageProbe /></I18nProvider>);
    expect(screen.getByTestId('language')).toHaveTextContent('es');
    expect(document.documentElement.lang).toBe('es');
  });

  it('selects English for an English or unsupported device language', () => {
    setDeviceLanguage('fr-FR');
    render(<I18nProvider><LanguageProbe /></I18nProvider>);
    expect(screen.getByTestId('language')).toHaveTextContent('en');
    expect(document.documentElement.lang).toBe('en');
  });

  it('updates the indexing action when the selected language changes', () => {
    localStorage.setItem('tc-lang', 'en');
    render(<I18nProvider><LanguageProbe /></I18nProvider>);

    expect(screen.getByTestId('open-indexing')).toHaveTextContent('Open indexing');
    fireEvent.click(screen.getByRole('button', { name: 'toggle' }));
    expect(screen.getByTestId('open-indexing')).toHaveTextContent('Abrir indexación');
  });
});

describe('translation catalog', () => {
  it('keeps English and Spanish keys in parity', () => {
    expect(Object.keys(translations.en).sort()).toEqual(Object.keys(translations.es).sort());
    expect(Object.values(translations.en).every((value) => typeof value === 'string')).toBe(true);
    expect(Object.values(translations.es).every((value) => typeof value === 'string')).toBe(true);
  });
});
