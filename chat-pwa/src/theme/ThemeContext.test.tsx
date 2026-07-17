import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { ThemeProvider, useTheme } from './ThemeContext';

const defaultMatchMedia = window.matchMedia;

function ThemeProbe() {
  const { theme } = useTheme();
  return <span data-testid="theme">{theme}</span>;
}

describe('ThemeProvider shared-device synchronization', () => {
  afterEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove('dark', 'light');
    window.matchMedia = defaultMatchMedia;
  });

  it('applies a remotely synchronized theme to React and the document atomically', () => {
    localStorage.setItem('tc-theme', 'light');
    render(<ThemeProvider><ThemeProbe /></ThemeProvider>);
    expect(screen.getByTestId('theme')).toHaveTextContent('light');

    localStorage.setItem('tc-theme', 'dark');
    act(() => window.dispatchEvent(new Event('trinaxai:shared-state-updated')));

    expect(screen.getByTestId('theme')).toHaveTextContent('dark');
    expect(document.documentElement).toHaveClass('dark');
    expect(document.documentElement).not.toHaveClass('light');
  });

  it('uses the device color scheme when no preference has been saved', () => {
    window.matchMedia = ((query: string) => ({
      matches: query === '(prefers-color-scheme: light)',
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    })) as typeof window.matchMedia;

    render(<ThemeProvider><ThemeProbe /></ThemeProvider>);

    expect(screen.getByTestId('theme')).toHaveTextContent('light');
    expect(document.documentElement).toHaveClass('light');
  });
});
