import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { I18nProvider } from '../i18n/I18nContext';
import { ThemeProvider } from '../theme/ThemeContext';
import OnboardingWizard from './OnboardingWizard';
import { expectNoA11yViolations } from '../test/a11y';

const { checkStatusMock } = vi.hoisted(() => ({ checkStatusMock: vi.fn() }));

vi.mock('../lib/api', async (importOriginal) => ({
  ...await importOriginal<typeof import('../lib/api')>(),
  checkStatus: checkStatusMock,
}));

vi.mock('../lib/sharedState', () => ({
  onSharedStateUpdated: () => () => undefined,
  syncSharedStateOnce: () => Promise.resolve(true),
}));

describe('OnboardingWizard permissions', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    checkStatusMock.mockReset();
    checkStatusMock.mockResolvedValue({ ollama: true, rag: true, indexed: false, ramPercent: 20, profile: '16gb' });
    Object.defineProperty(navigator, 'language', { configurable: true, value: 'en-US' });
  });

  it('keeps an unprivileged device to language, theme, name input, and the minimal summary', async () => {
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
    await expectNoA11yViolations(document.body);
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Light or dark mode?')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.queryByRole('heading', { name: 'What should TrinaxAI call you?' })).not.toBeInTheDocument();
    expect(await screen.findByRole('textbox', { name: 'What should TrinaxAI call you?' })).toBeInTheDocument();
    await user.type(screen.getByRole('textbox'), 'Ana');
    await user.click(screen.getByRole('button', { name: 'Next' }));

    expect(await screen.findByText("That's it!")).toBeInTheDocument();
    expect(screen.getByText('Ana')).toBeInTheDocument();
    expect(screen.getByText(/Theme:/)).toBeInTheDocument();
    expect(screen.getByText(/Language:/)).toBeInTheDocument();
    expect(screen.queryByText('Model setup')).not.toBeInTheDocument();
    expect(screen.queryByText('Ollama & Indexing')).not.toBeInTheDocument();
    expect(screen.queryByText('canirun.ai')).not.toBeInTheDocument();
    expect(screen.queryByText('Pass this prompt to the AI')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Start now' }));
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

  it('saves the models recommended by the backend-detected profile', async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    checkStatusMock.mockResolvedValue({ ollama: true, rag: true, indexed: false, ramPercent: 20, profile: '32gb' });
    render(
      <I18nProvider>
        <ThemeProvider>
          <OnboardingWizard onComplete={onComplete} canConfigureSystem />
        </ThemeProvider>
      </I18nProvider>,
    );

    await waitFor(() => expect(checkStatusMock).toHaveBeenCalledOnce());
    await user.click(screen.getByRole('button', { name: 'Skip' }));
    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce());

    expect(localStorage.getItem('tc-models-chat')).toBe('qwen3.5:9b');
    expect(localStorage.getItem('tc-models-embed')).toBe('qwen3-embedding:4b');
  });

  it('preserves edited custom values when profile detection finishes later', async () => {
    const user = userEvent.setup();
    let resolveStatus!: (status: Awaited<ReturnType<typeof import('../lib/api').checkStatus>>) => void;
    checkStatusMock.mockReturnValue(new Promise((resolve) => { resolveStatus = resolve; }));
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
    await user.click(await screen.findByRole('button', { name: /Choose my own models/ }));
    const modelInput = screen.getByRole('textbox');
    await user.clear(modelInput);
    await user.type(modelInput, 'custom-chat:latest');

    resolveStatus({ ollama: true, rag: true, indexed: false, ramPercent: 20, profile: '64gb' });
    await waitFor(() => expect(modelInput).toHaveValue('custom-chat:latest'));
    await user.click(screen.getByRole('button', { name: 'Skip' }));

    expect(localStorage.getItem('tc-models-chat')).toBe('custom-chat:latest');
    expect(localStorage.getItem('tc-models-deep')).toBe('qwen3.5:35b');
  });

  it.each(['rejected status', 'missing profile'])('does not write guessed defaults for %s', async (failure) => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    localStorage.setItem('tc-models-chat', 'existing-chat:latest');
    if (failure === 'rejected status') checkStatusMock.mockRejectedValue(new Error('offline'));
    else checkStatusMock.mockResolvedValue({ ollama: false, rag: false, indexed: false, ramPercent: null, profile: null });
    render(
      <I18nProvider>
        <ThemeProvider>
          <OnboardingWizard onComplete={onComplete} canConfigureSystem />
        </ThemeProvider>
      </I18nProvider>,
    );

    await waitFor(() => expect(checkStatusMock).toHaveBeenCalledOnce());
    await user.click(screen.getByRole('button', { name: 'Skip' }));
    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce());

    expect(localStorage.getItem('tc-models-chat')).toBe('existing-chat:latest');
    expect(localStorage.getItem('tc-models-embed')).toBeNull();
  });

  it('saves only explicit custom values when profile detection fails', async () => {
    const user = userEvent.setup();
    checkStatusMock.mockRejectedValue(new Error('offline'));
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
    await user.click(await screen.findByRole('button', { name: /Choose my own models/ }));
    const modelInput = screen.getByRole('textbox');
    await user.clear(modelInput);
    await user.type(modelInput, 'custom-chat:latest');
    await user.click(screen.getByRole('button', { name: 'Skip' }));

    expect(localStorage.getItem('tc-models-chat')).toBe('custom-chat:latest');
    expect(localStorage.getItem('tc-models-deep')).toBeNull();
  });
});
