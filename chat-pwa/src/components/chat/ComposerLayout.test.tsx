import { createRef, useState } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import ComposerLayout from './ComposerLayout';

function TestComposer() {
  const [value, setValue] = useState('');
  const inputRef = createRef<HTMLTextAreaElement>();
  return (
    <ComposerLayout
      value={value}
      onChange={(event) => setValue(event.target.value)}
      onKeyDown={() => undefined}
      placeholder="Write a message"
      inputRef={inputRef}
      isDark={false}
      expandLabel="Expand editor"
      closeLabel="Close expanded editor"
      leftActions={<button type="button">+</button>}
      rightActions={<button type="button" onClick={() => setValue('sent')}>Send</button>}
    />
  );
}

describe('ComposerLayout', () => {
  it('keeps an empty or single-line draft in the compact 52px layout', () => {
    const { container } = render(<TestComposer />);
    const textarea = screen.getByRole('textbox', { name: 'Write a message' });
    const shell = container.querySelector('.relative.w-full');
    const layout = () => shell?.querySelector(':scope > div')?.className || '';

    expect(layout()).toContain('h-[52px]');
    fireEvent.change(textarea, { target: { value: 'Hola' } });
    expect(layout()).toContain('h-[52px]');
    fireEvent.change(textarea, { target: { value: '' } });
    expect(layout()).toContain('h-[52px]');
  });

  it('moves controls below a multiline draft and keeps the draft shared in expanded mode', async () => {
    const { container } = render(<TestComposer />);
    const textarea = screen.getByRole('textbox', { name: 'Write a message' });

    const longDraft = `first line\nsecond line ${'long content '.repeat(10)}`;
    fireEvent.change(textarea, { target: { value: longDraft } });
    const shell = container.querySelector('.relative.w-full');
    expect(shell?.querySelector(':scope > div')?.className).toContain('grid-cols-1');

    fireEvent.click(screen.getByRole('button', { name: 'Expand editor' }));
    const textareas = screen.getAllByRole('textbox', { name: 'Write a message', hidden: true });
    expect(textareas).toHaveLength(2);
    expect(screen.getByRole('dialog')).toHaveClass('h-[calc(100dvh-1rem)]', 'sm:h-[calc(100dvh-2rem)]', 'max-w-[96rem]');
    const expandedTextarea = textareas[1];
    expect(expandedTextarea).toHaveValue(longDraft);

    fireEvent.change(expandedTextarea, { target: { value: 'edited in fullscreen' } });
    fireEvent.click(screen.getByRole('button', { name: 'Close expanded editor' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(screen.getByRole('textbox', { name: 'Write a message' })).toHaveValue('edited in fullscreen');
  });

  it('traps focus in the expanded editor and restores it after Escape', async () => {
    const user = userEvent.setup();
    const { container } = render(<TestComposer />);
    const textarea = screen.getByRole('textbox', { name: 'Write a message' });
    fireEvent.change(textarea, { target: { value: `first line\nsecond line ${'long content '.repeat(10)}` } });
    const expandButton = screen.getByRole('button', { name: 'Expand editor' });

    await user.click(expandButton);
    const closeButton = screen.getByRole('button', { name: 'Close expanded editor' });
    await waitFor(() => expect(closeButton).toHaveFocus());
    expect((container as HTMLElement).inert).toBe(true);

    await user.tab({ shift: true });
    expect(screen.getByRole('button', { name: 'Send' })).toHaveFocus();
    await user.keyboard('{Escape}');
    await waitFor(() => expect(expandButton).toHaveFocus());
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect((container as HTMLElement).inert).not.toBe(true);
  });
});
