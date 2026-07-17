import { createContext, useContext, useState, useCallback, useEffect, useRef, type ReactNode } from 'react';
import { flushSync } from 'react-dom';
import { onSharedStateUpdated } from '../lib/sharedState';

const THEME_KEY = 'tc-theme';
type Theme = 'dark' | 'light';

function loadTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === 'dark' || stored === 'light') return stored;
    if (stored === 'sepia' || stored === 'contrast') {
      localStorage.setItem(THEME_KEY, 'dark');
      return 'dark';
    }
  } catch { /* ignore */ }
  if (typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: light)').matches) {
    return 'light';
  }
  return 'dark';
}

function applyHtmlTheme(theme: Theme) {
  const root = document.documentElement;
  root.classList.toggle('light', theme === 'light');
  root.classList.toggle('dark', theme === 'dark');
  root.classList.remove('sepia', 'contrast');
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    meta.setAttribute('content', theme === 'dark' ? '#000000' : '#ffffff');
  }
  const appleMeta = document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]');
  if (appleMeta) {
    appleMeta.setAttribute('content', theme === 'dark' ? 'black-translucent' : 'default');
  }
}

interface ThemeContextValue {
  theme: Theme;
  setTheme: (t: Theme) => void;
  cycleTheme: () => void;
  isDark: boolean;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const initial = loadTheme();
  const [theme, setTheme] = useState<Theme>(initial);
  const themeRef = useRef<Theme>(initial);

  // Apply the initial theme on first render (no animation)
  useEffect(() => {
    applyHtmlTheme(initial);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => onSharedStateUpdated(() => {
    const stored = loadTheme();
    if (stored === themeRef.current) {
      // The React value may already match while the root class still reflects
      // the pre-pairing browser preference. Keep both sources synchronized.
      applyHtmlTheme(stored);
      return;
    }
    themeRef.current = stored;
    // Shared state is applied as one visual commit. Without updating the root
    // class here, components using `isDark` and CSS using `.dark` disagree.
    flushSync(() => setTheme(stored));
    applyHtmlTheme(stored);
  }), []);

  const switchTheme = useCallback((next: Theme) => {
    themeRef.current = next;
    try { localStorage.setItem(THEME_KEY, next); } catch { /* ignore */ }

    const st = document as any;
    if (!st.startViewTransition) {
      // No View Transition API — just apply synchronously
      flushSync(() => setTheme(next));
      applyHtmlTheme(next);
      return;
    }

    // Use View Transition API: the callback runs synchronously inside
    // the transition lifecycle.  We flushSync the React state first so
    // all components re-render with the NEW theme colours, *then* flip
    // the html class.  The browser captures:
    //   old snapshot → current (old) theme
    //   new snapshot → new theme (components + html class)
    st.startViewTransition(() => {
      flushSync(() => setTheme(next));
      applyHtmlTheme(next);
    });
  }, []);

  const cycleTheme = useCallback(() => {
    const next = themeRef.current === 'dark' ? 'light' : 'dark';
    switchTheme(next);
  }, [switchTheme]);

  const setThemeDirect = useCallback((t: Theme) => {
    switchTheme(t);
  }, [switchTheme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme: setThemeDirect, cycleTheme, isDark: theme === 'dark' }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
