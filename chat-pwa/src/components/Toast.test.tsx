import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider, useToast } from './Toast';

vi.mock('../i18n/I18nContext', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('../services/audioManager', () => ({
  audioManager: { play: vi.fn() },
}));

function Harness() {
  const { toast } = useToast();
  return (
    <>
      <button type="button" onClick={() => toast('normal error', 'error')}>Normal</button>
      <button
        type="button"
        onClick={() => toast('local service unavailable', 'error', {
          durationMs: 10_000,
          action: {
            label: 'Encender IA',
            pendingLabel: 'Iniciando...',
            onClick: actionPromise,
          },
        })}
      >
        Local
      </button>
    </>
  );
}

let resolveAction: (() => void) | undefined;
const actionPromise = vi.fn(() => new Promise<void>((resolve) => {
  resolveAction = resolve;
}));

describe('ToastProvider actions', () => {
  afterEach(() => {
    vi.useRealTimers();
    actionPromise.mockClear();
    resolveAction = undefined;
  });

  it('keeps normal errors at their default duration', () => {
    vi.useFakeTimers();
    render(<ToastProvider><Harness /></ToastProvider>);

    fireEvent.click(screen.getByRole('button', { name: 'Normal' }));
    expect(screen.getByText('normal error')).toBeInTheDocument();

    act(() => { vi.advanceTimersByTime(6_000); });
    expect(screen.getByText('normal error')).toBeInTheDocument();
    act(() => { vi.advanceTimersByTime(250); });
    expect(screen.queryByText('normal error')).not.toBeInTheDocument();
  });

  it('keeps the local-service action visible for ten seconds and prevents duplicate runs', async () => {
    vi.useFakeTimers();
    render(<ToastProvider><Harness /></ToastProvider>);

    fireEvent.click(screen.getByRole('button', { name: 'Local' }));
    const action = screen.getByRole('button', { name: 'Encender IA' });
    expect(action).toBeInTheDocument();

    act(() => { vi.advanceTimersByTime(9_999); });
    expect(screen.getByRole('button', { name: 'Encender IA' })).toBeInTheDocument();

    fireEvent.click(action);
    fireEvent.click(action);
    expect(actionPromise).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: 'Iniciando...' })).toBeDisabled();

    await act(async () => {
      resolveAction?.();
      await Promise.resolve();
    });
    act(() => { vi.advanceTimersByTime(250); });
    expect(screen.queryByText('local service unavailable')).not.toBeInTheDocument();
  });
});
