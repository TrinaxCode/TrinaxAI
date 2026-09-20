import { useRef } from 'react';
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
  const seq = useRef(0);
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
      <button
        type="button"
        onClick={() => toast('critical failure', 'error', {
          action: { label: 'Recuperar', onClick: actionPromise },
        })}
      >
        Recoverable
      </button>
      <button
        type="button"
        onClick={() => {
          seq.current += 1;
          toast(`queued ${seq.current}`, 'error');
        }}
      >
        Flood
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

  it('opens repair guidance from an error toast', () => {
    render(<ToastProvider><Harness /></ToastProvider>);

    fireEvent.click(screen.getByRole('button', { name: 'Normal' }));
    fireEvent.click(screen.getByRole('button', { name: 'fixError' }));

    expect(screen.getByRole('dialog')).toHaveTextContent('normal error');
    expect(screen.getByRole('dialog')).toHaveTextContent('errorRepairHint');
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

  it('holds an error with a recovery action until it is dismissed', () => {
    vi.useFakeTimers();
    render(<ToastProvider><Harness /></ToastProvider>);

    fireEvent.click(screen.getByRole('button', { name: 'Recoverable' }));

    act(() => { vi.advanceTimersByTime(120_000); });
    expect(screen.getByText('critical failure')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'close' }));
    act(() => { vi.advanceTimersByTime(300); });
    expect(screen.queryByText('critical failure')).not.toBeInTheDocument();
  });

  it('freezes the countdown while the pointer rests on a notice', () => {
    vi.useFakeTimers();
    render(<ToastProvider><Harness /></ToastProvider>);

    fireEvent.click(screen.getByRole('button', { name: 'Normal' }));
    const notice = screen.getByRole('alert');

    fireEvent.mouseOver(notice);
    act(() => { vi.advanceTimersByTime(20_000); });
    expect(screen.getByText('normal error')).toBeInTheDocument();

    fireEvent.mouseOut(notice, { relatedTarget: document.body });
    act(() => { vi.advanceTimersByTime(6_000); });
    act(() => { vi.advanceTimersByTime(500); });
    expect(screen.queryByText('normal error')).not.toBeInTheDocument();
  });

  it('refreshes a repeated notice instead of stacking a copy', () => {
    vi.useFakeTimers();
    render(<ToastProvider><Harness /></ToastProvider>);

    fireEvent.click(screen.getByRole('button', { name: 'Normal' }));
    fireEvent.click(screen.getByRole('button', { name: 'Normal' }));

    expect(screen.getAllByText('normal error')).toHaveLength(1);
  });

  it('retires the oldest notice once the stack is full', () => {
    vi.useFakeTimers();
    render(<ToastProvider><Harness /></ToastProvider>);

    const flood = screen.getByRole('button', { name: 'Flood' });
    for (let press = 0; press < 5; press += 1) fireEvent.click(flood);

    expect(screen.queryByText('queued 1')).not.toBeInTheDocument();
    expect(screen.getByText('queued 5')).toBeInTheDocument();
    expect(screen.getAllByRole('alert')).toHaveLength(4);
  });
});
