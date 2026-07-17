import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { expectNoA11yViolations } from '../test/a11y';
import ConfirmModal from './ConfirmModal';

vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({ isDark: true }) }));
vi.mock('../i18n/I18nContext', () => ({ useI18n: () => ({ t: (key: string) => key }) }));

function Harness({ danger = true }: { danger?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>Open confirmation</button>
      <ConfirmModal
        open={open}
        title="Delete item"
        message="This cannot be undone."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        danger={danger}
        onConfirm={() => setOpen(false)}
        onCancel={() => setOpen(false)}
      />
    </>
  );
}

describe('ConfirmModal accessibility', () => {
  it('inerts the background, focuses Cancel and restores the trigger', async () => {
    const user = userEvent.setup();
    const { container } = render(<Harness />);
    const trigger = screen.getByRole('button', { name: 'Open confirmation' });

    await user.click(trigger);
    const cancel = screen.getByRole('button', { name: 'Cancel' });
    await waitFor(() => expect(cancel).toHaveFocus());
    expect(container).toHaveAttribute('aria-hidden', 'true');
    expect((container as HTMLElement).inert).toBe(true);

    await user.keyboard('{Escape}');
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(container).not.toHaveAttribute('aria-hidden');
    expect((container as HTMLElement).inert).not.toBe(true);
  });

  it('has no automatically detectable dialog violations', async () => {
    const user = userEvent.setup();
    render(<Harness danger={false} />);
    await user.click(screen.getByRole('button', { name: 'Open confirmation' }));

    await expectNoA11yViolations(screen.getByRole('dialog'));
  });
});
