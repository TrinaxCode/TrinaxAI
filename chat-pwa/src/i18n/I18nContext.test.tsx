import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { I18nProvider, useI18n } from './I18nContext';

function LanguageProbe() {
  const { lang } = useI18n();
  return <span data-testid="language">{lang}</span>;
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
});
