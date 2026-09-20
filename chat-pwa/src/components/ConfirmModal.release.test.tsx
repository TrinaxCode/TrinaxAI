import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ConfirmModal from './ConfirmModal';

vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ isDark: false }) }));
vi.mock('../i18n/I18nContext', () => ({ useI18n: () => ({ t: (key: string) => key }) }));

describe('ConfirmModal release branches', () => {
  it('supports an enabled no-cancel action, custom content, and backdrop dismissal', () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    const sibling = document.createElement('div');
    sibling.setAttribute('aria-hidden', 'false');
    document.body.appendChild(sibling);
    const view = render(
      <ConfirmModal open title="Delete" message="Confirm" showCancel={false} onConfirm={onConfirm} onCancel={onCancel}>
        <input aria-label="extra" />
      </ConfirmModal>,
    );
    const dialog = screen.getByRole('dialog', { name: 'Delete' });
    expect(screen.queryByRole('button', { name: 'cancelDefault' })).not.toBeInTheDocument();
    const confirm = screen.getByRole('button', { name: 'confirmDefault' });
    fireEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledOnce();
    fireEvent.click(dialog.parentElement?.querySelector('[aria-hidden="true"]') as HTMLElement);
    expect(onCancel).toHaveBeenCalledOnce();
    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(onCancel).toHaveBeenCalledTimes(2);
    view.unmount();
    expect(sibling).toHaveAttribute('aria-hidden', 'false');
    sibling.remove();
  });

  it('keeps a disabled confirmation inert and wraps focus at both ends', () => {
    const onConfirm = vi.fn();
    const view = render(<ConfirmModal open title="Disabled" message="Wait" confirmDisabled onConfirm={onConfirm} onCancel={vi.fn()} />);
    const dialog = screen.getByRole('dialog', { name: 'Disabled' });
    const confirm = screen.getByRole('button', { name: 'confirmDefault' });
    expect(confirm).toBeDisabled();
    fireEvent.click(confirm);
    expect(onConfirm).not.toHaveBeenCalled();
    view.rerender(<ConfirmModal open title="Disabled" message="Wait" onConfirm={onConfirm} onCancel={vi.fn()} />);
    const focusable = dialog.querySelectorAll<HTMLElement>('button, input, select, textarea, [tabindex]:not([tabindex="-1"])');
    document.body.setAttribute('tabindex', '-1');
    document.body.focus();
    fireEvent.keyDown(dialog, { key: 'Tab', shiftKey: true });
    fireEvent.keyDown(dialog, { key: 'Tab' });
    document.body.removeAttribute('tabindex');
    focusable[0].focus();
    fireEvent.keyDown(dialog, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(focusable[focusable.length - 1]);
    fireEvent.keyDown(dialog, { key: 'Tab' });
    expect(document.activeElement).toBe(focusable[0]);
    fireEvent.keyDown(dialog, { key: 'Enter' });
  });
});
