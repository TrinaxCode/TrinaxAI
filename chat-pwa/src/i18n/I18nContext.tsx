import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react';
import { translations, type Lang, type TranslationKey } from './translations';
import { onSharedStateUpdated } from '../lib/sharedState';

const LANG_KEY = 'tc-lang';

function loadLang(): Lang {
  try {
    const stored = localStorage.getItem(LANG_KEY);
    if (stored === 'en' || stored === 'es') return stored;
    // Detect browser language
    const nav = navigator.language?.slice(0, 2).toLowerCase();
    return nav === 'es' ? 'es' : 'en';
  } catch {
    return 'en';
  }
}

interface I18nContextValue {
  lang: Lang;
  t: (key: TranslationKey) => string;
  setLang: (lang: Lang) => void;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(loadLang);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try { localStorage.setItem(LANG_KEY, l); } catch { /* ignore */ }
    document.documentElement.lang = l;
    // Update speech recognition language if we change
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  useEffect(() => onSharedStateUpdated(() => {
    setLangState(loadLang());
  }), []);

  const t = useCallback(
    (key: TranslationKey): string => {
      return translations[lang][key] ?? translations.es[key] ?? key;
    },
    [lang],
  );

  return (
    <I18nContext.Provider value={{ lang, t, setLang }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used within I18nProvider');
  return ctx;
}
