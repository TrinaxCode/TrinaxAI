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
    const metadata = lang === 'es'
      ? {
          title: 'TrinaxAI Chat',
          description: 'TrinaxAI — Ollama y RAG al alcance de tu mano.',
        }
      : {
          title: 'TrinaxAI Chat',
          description: 'TrinaxAI — Ollama & RAG at your fingertips.',
        };
    document.title = metadata.title;
    document.querySelector('meta[name="description"]')?.setAttribute('content', metadata.description);
    document.querySelector('meta[property="og:title"]')?.setAttribute('content', metadata.title);
    document.querySelector('meta[property="og:description"]')?.setAttribute('content', metadata.description);
    document.querySelector('meta[name="twitter:title"]')?.setAttribute('content', metadata.title);
    document.querySelector('meta[name="twitter:description"]')?.setAttribute('content', metadata.description);
    document.querySelector('meta[name="application-name"]')?.setAttribute('content', metadata.title);
    document.querySelector('meta[name="apple-mobile-web-app-title"]')?.setAttribute('content', metadata.title);
    const manifest = document.querySelector<HTMLLinkElement>('link[rel="manifest"]');
    if (manifest) manifest.href = `/manifest.${lang}.webmanifest`;
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
