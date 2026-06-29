import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react';
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

function applyTheme(theme: Theme) {
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
  const [theme, setTheme] = useState<Theme>(loadTheme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => onSharedStateUpdated(() => {
    setTheme(loadTheme());
  }), []);

  const cycleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem(THEME_KEY, next); } catch { /* ignore */ }
      return next;
    });
  }, []);

  const setThemeDirect = useCallback((t: Theme) => {
    try { localStorage.setItem(THEME_KEY, t); } catch { /* ignore */ }
    setTheme(t);
  }, []);

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
