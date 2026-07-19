import { useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { useDialogAccessibility } from './useDialogAccessibility';

function Harness() {
  const [open, setOpen] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);
  const modal = useDialogAccessibility(open, () => setOpen(false), closeRef);
  return <>
    <button onClick={() => setOpen(true)}>Open</button>
    {open && createPortal(
      <div data-modal-root>
        <div ref={modal.dialogRef} role="dialog" onKeyDown={modal.onKeyDown}>
          <button ref={closeRef} onClick={() => setOpen(false)}>Close</button>
          <button>Last</button>
        </div>
      </div>, document.body,
    )}
  </>;
}

describe('useDialogAccessibility', () => {
  it('focuses the dialog, traps Tab, closes on Escape, and restores focus', async () => {
    const user = userEvent.setup();
    const { container } = render(<Harness />);
    const trigger = screen.getByRole('button', { name: 'Open' });
    await user.click(trigger);
    const close = screen.getByRole('button', { name: 'Close' });
    await waitFor(() => expect(close).toHaveFocus());
    expect((container as HTMLElement).inert).toBe(true);
    await user.tab({ shift: true });
    expect(screen.getByRole('button', { name: 'Last' })).toHaveFocus();
    await user.keyboard('{Escape}');
    await waitFor(() => expect(trigger).toHaveFocus());
    expect((container as HTMLElement).inert).not.toBe(true);
  });
});
