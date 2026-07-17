import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { I18nProvider } from '../i18n/I18nContext';
import { ThemeProvider } from '../theme/ThemeContext';
import OnboardingWizard from './OnboardingWizard';

vi.mock('../lib/sharedState', () => ({
  onSharedStateUpdated: () => () => undefined,
  syncSharedStateOnce: () => Promise.resolve(true),
}));

describe('OnboardingWizard permissions', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    Object.defineProperty(navigator, 'language', { configurable: true, value: 'en-US' });
  });

  it('keeps an unprivileged device to language, theme, name, and the minimal summary', async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    render(
      <I18nProvider>
        <ThemeProvider>
          <OnboardingWizard onComplete={onComplete} canConfigureSystem={false} />
        </ThemeProvider>
      </I18nProvider>,
    );

    expect(screen.getByText('Which language do you prefer?')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Light or dark mode?')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('What should TrinaxAI call you?')).toBeInTheDocument();
    await user.type(screen.getByRole('textbox'), 'Ana');
    await user.click(screen.getByRole('button', { name: 'Next' }));

    expect(await screen.findByText("That's it! 🎉")).toBeInTheDocument();
    expect(screen.getByText('Ana')).toBeInTheDocument();
    expect(screen.getByText(/Theme:/)).toBeInTheDocument();
    expect(screen.getByText(/Language:/)).toBeInTheDocument();
    expect(screen.queryByText('Model setup')).not.toBeInTheDocument();
    expect(screen.queryByText('Ollama & Indexing')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '🚀 Start now' }));
    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce());
    expect(localStorage.getItem('tc-models-chat')).toBeNull();
  });

  it('keeps host configuration steps available to a privileged device', async () => {
    const user = userEvent.setup();
    render(
      <I18nProvider>
        <ThemeProvider>
          <OnboardingWizard onComplete={() => undefined} canConfigureSystem />
        </ThemeProvider>
      </I18nProvider>,
    );

    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));

    expect(await screen.findByText('Model setup')).toBeInTheDocument();
  });
});
