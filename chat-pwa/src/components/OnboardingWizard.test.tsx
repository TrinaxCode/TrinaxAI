import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { I18nProvider } from '../i18n/I18nContext';
import { ThemeProvider } from '../theme/ThemeContext';
import OnboardingWizard from './OnboardingWizard';
import { expectNoA11yViolations } from '../test/a11y';

const { checkStatusMock, syncMock } = vi.hoisted(() => ({
  checkStatusMock: vi.fn(),
  syncMock: vi.fn(),
}));

vi.mock('../lib/api', async (importOriginal) => ({
  ...await importOriginal<typeof import('../lib/api')>(),
  checkStatus: checkStatusMock,
}));

vi.mock('../lib/sharedState', () => ({
  onSharedStateUpdated: () => () => undefined,
  syncSharedStateOnce: syncMock,
}));

function renderWizard(props: { canConfigureSystem: boolean; onComplete?: () => void }) {
  return render(
    <I18nProvider>
      <ThemeProvider>
        <OnboardingWizard onComplete={props.onComplete ?? (() => undefined)} canConfigureSystem={props.canConfigureSystem} />
      </ThemeProvider>
    </I18nProvider>,
  );
}

describe('OnboardingWizard', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    checkStatusMock.mockReset();
    syncMock.mockReset();
    syncMock.mockResolvedValue(true);
    checkStatusMock.mockResolvedValue({ ollama: true, rag: true, indexed: false, ramPercent: 20, profile: '16gb' });
    Object.defineProperty(navigator, 'language', { configurable: true, value: 'en-US' });
  });

  it('asks only for language, appearance and an optional name on one accessible screen', async () => {
    renderWizard({ canConfigureSystem: false });

    expect(screen.getByRole('heading', { level: 1, name: 'Welcome to TrinaxAI' })).toBeInTheDocument();
    expect(screen.getByRole('group', { name: 'Language' })).toBeInTheDocument();
    expect(screen.getByRole('group', { name: 'Appearance' })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'What should we call you?' })).toBeInTheDocument();
    // Hardware, models, Ollama and indexing are handled by the installer or Settings.
    expect(screen.queryByText(/GB of RAM|Ollama|models/i)).not.toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'TrinaxAI' })).toHaveAttribute('src', '/logo-for-ai-transparent.webp');
    await expectNoA11yViolations(document.body);
  });

  it('switches the interface language as soon as it is chosen', async () => {
    const user = userEvent.setup();
    renderWizard({ canConfigureSystem: false });

    await user.click(screen.getByRole('radio', { name: /Spanish/ }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Bienvenido a TrinaxAI' })).toBeInTheDocument();
    expect(localStorage.getItem('tc-lang')).toBe('es');
  });

  it('saves the name, completes onboarding and leaves models alone on an unprivileged device', async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    renderWizard({ canConfigureSystem: false, onComplete });

    await user.type(screen.getByRole('textbox', { name: 'What should we call you?' }), '  Ana  ');
    await user.click(screen.getByRole('button', { name: 'Start chatting' }));

    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce());
    expect(localStorage.getItem('tc-user-nickname')).toBe('Ana');
    expect(localStorage.getItem('tc-onboarding-complete')).toBe('true');
    expect(localStorage.getItem('tc-models-chat')).toBeNull();
    expect(checkStatusMock).not.toHaveBeenCalled();
    expect(syncMock).toHaveBeenCalledWith(2500, true);
  });

  it('submits with Enter from the name field', async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    renderWizard({ canConfigureSystem: false, onComplete });

    await user.type(screen.getByRole('textbox', { name: 'What should we call you?' }), 'Ana{Enter}');
    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce());
  });

  it('does not store a nickname when the field is left blank', async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    renderWizard({ canConfigureSystem: false, onComplete });

    await user.click(screen.getByRole('button', { name: 'Start chatting' }));
    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce());
    expect(localStorage.getItem('tc-user-nickname')).toBeNull();
  });

  it('copies the installer-detected hardware profile into the browser without asking', async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    checkStatusMock.mockResolvedValue({ ollama: true, rag: true, indexed: false, ramPercent: 20, profile: '32gb' });
    localStorage.setItem('tc-models-vision-quality', 'high');
    renderWizard({ canConfigureSystem: true, onComplete });

    await user.click(screen.getByRole('button', { name: 'Start chatting' }));
    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce());

    expect(localStorage.getItem('tc-models-chat')).toBe('qwen3.5:9b');
    expect(localStorage.getItem('tc-models-embed')).toBe('qwen3-embedding:4b');
    expect(localStorage.getItem('tc-models-fast')).toBe('qwen3.5:4b');
    expect(localStorage.getItem('tc-models-vision-quality')).toBeNull();
  });

  it('waits for a slow hardware check instead of leaving the wrong defaults', async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    let resolveStatus!: (status: Awaited<ReturnType<typeof import('../lib/api').checkStatus>>) => void;
    checkStatusMock.mockReturnValue(new Promise((resolve) => { resolveStatus = resolve; }));
    renderWizard({ canConfigureSystem: true, onComplete });

    await user.click(screen.getByRole('button', { name: 'Start chatting' }));
    expect(screen.getByRole('button', { name: 'Saving…' })).toBeDisabled();
    expect(onComplete).not.toHaveBeenCalled();

    resolveStatus({ ollama: true, rag: true, indexed: false, ramPercent: 20, profile: '64gb' });
    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce());
    expect(localStorage.getItem('tc-models-chat')).toBe('qwen3.5:35b');
    expect(localStorage.getItem('tc-models-code')).toBe('qwen3-coder:30b');
  });

  it.each(['rejected status', 'missing profile'])('does not write guessed defaults for %s', async (failure) => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    localStorage.setItem('tc-models-chat', 'existing-chat:latest');
    if (failure === 'rejected status') checkStatusMock.mockRejectedValue(new Error('offline'));
    else checkStatusMock.mockResolvedValue({ ollama: false, rag: false, indexed: false, ramPercent: null, profile: null });
    renderWizard({ canConfigureSystem: true, onComplete });

    await user.click(screen.getByRole('button', { name: 'Start chatting' }));
    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce());

    expect(localStorage.getItem('tc-models-chat')).toBe('existing-chat:latest');
    expect(localStorage.getItem('tc-models-embed')).toBeNull();
  });

  it('completes even when the shared-state sync fails', async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    syncMock.mockRejectedValue(new Error('offline'));
    renderWizard({ canConfigureSystem: false, onComplete });

    await user.click(screen.getByRole('button', { name: 'Start chatting' }));
    await waitFor(() => expect(onComplete).toHaveBeenCalledOnce());
    expect(localStorage.getItem('tc-onboarding-complete')).toBe('true');
  });
});
